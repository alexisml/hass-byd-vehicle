"""Unit tests for __init__.py lifecycle and service handler functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.byd_vehicle import (
    _async_register_services,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.byd_vehicle.const import (
    CONF_DEVICE_PROFILE,
    CONF_GPS_ACTIVE_INTERVAL,
    CONF_GPS_INACTIVE_INTERVAL,
    CONF_GPS_POLL_INTERVAL,
    CONF_POLL_INTERVAL,
    CONF_SMART_GPS_POLLING,
    DEFAULT_GPS_ACTIVE_INTERVAL,
    DEFAULT_GPS_INACTIVE_INTERVAL,
    DEFAULT_GPS_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SMART_GPS_POLLING,
    DOMAIN,
)


def _make_hass(vin: str = "VIN123", entry_id: str = "entry1") -> MagicMock:
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: MagicMock()},
            }
        }
    }
    return hass


def _make_hass_for_services(already_registered: bool = False) -> MagicMock:
    """Create a mock hass for service registration tests."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = already_registered
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    return hass


# ---------------------------------------------------------------------------
# async_unload_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_unload_entry_success() -> None:
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    # Use a MagicMock for hass.data so we can control __getitem__ and get
    domain_dict = MagicMock()
    domain_dict.pop.return_value = None  # no entry_data
    hass.data = MagicMock()
    hass.data.__getitem__ = MagicMock(return_value=domain_dict)
    hass.data.get = MagicMock(return_value={})  # Empty dict → triggers unregister
    hass.services = MagicMock()
    hass.services.async_remove = MagicMock()

    entry = MagicMock()
    entry.entry_id = "entry1"

    result = await async_unload_entry(hass, entry)
    assert result is True
    hass.config_entries.async_unload_platforms.assert_called_once()
    # Unregister services called (empty DOMAIN data)
    assert hass.services.async_remove.call_count == 3


@pytest.mark.asyncio
async def test_async_unload_entry_with_api_shutdown() -> None:
    """Cover lines 172-173: entry_data has an 'api' key."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.services = MagicMock()
    hass.services.async_remove = MagicMock()

    mock_api = MagicMock()
    mock_api.async_shutdown = AsyncMock()
    entry_data = {"api": mock_api}

    domain_dict = MagicMock()
    domain_dict.pop.return_value = entry_data
    hass.data = MagicMock()
    hass.data.__getitem__ = MagicMock(return_value=domain_dict)
    hass.data.get = MagicMock(return_value=None)  # None → falsy → unregister

    entry = MagicMock()
    entry.entry_id = "entry1"

    result = await async_unload_entry(hass, entry)
    assert result is True
    mock_api.async_shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry_failure() -> None:
    """Cover the else path (lines 178-179): unload_ok=False."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    hass.data = MagicMock()

    entry = MagicMock()
    entry.entry_id = "entry1"

    result = await async_unload_entry(hass, entry)
    assert result is False


# ---------------------------------------------------------------------------
# async_reload_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_reload_entry() -> None:
    """Cover lines 185-186: async_reload_entry delegates to HA."""
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    entry = MagicMock()
    entry.entry_id = "entry1"

    await async_reload_entry(hass, entry)
    hass.config_entries.async_reload.assert_called_once_with("entry1")


# ---------------------------------------------------------------------------
# Service handler bodies (lines 259-272): invoked via captured handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_fetch_realtime_handler_invokes_coordinator() -> None:
    """Cover lines 259-261: _handle_fetch_realtime body."""

    hass = _make_hass_for_services(already_registered=False)
    # Capture registered handlers
    captured = {}

    def capture(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = capture
    _async_register_services(hass)

    coordinator = MagicMock()
    coordinator.async_fetch_realtime = AsyncMock()
    call = MagicMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[("entry1", "VIN123")],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(coordinator, None),
    ):
        await captured["fetch_realtime"](call)

    coordinator.async_fetch_realtime.assert_called_once()


@pytest.mark.asyncio
async def test_service_fetch_gps_handler_invokes_gps_coordinator() -> None:
    """Cover lines 264-267: _handle_fetch_gps body."""

    hass = _make_hass_for_services(already_registered=False)
    captured = {}

    def capture(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = capture
    _async_register_services(hass)

    gps = MagicMock()
    gps.async_fetch_gps = AsyncMock()
    call = MagicMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[("entry1", "VIN123")],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(MagicMock(), gps),
    ):
        await captured["fetch_gps"](call)

    gps.async_fetch_gps.assert_called_once()


@pytest.mark.asyncio
async def test_service_fetch_gps_handler_skips_when_gps_none() -> None:
    """Cover line 266: if gps is not None branch when gps is None."""

    hass = _make_hass_for_services(already_registered=False)
    captured = {}

    def capture(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = capture
    _async_register_services(hass)

    call = MagicMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[("entry1", "VIN123")],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(MagicMock(), None),  # gps=None → skip
    ):
        # Should not raise
        await captured["fetch_gps"](call)


@pytest.mark.asyncio
async def test_service_fetch_hvac_handler_invokes_coordinator() -> None:
    """Cover lines 270-272: _handle_fetch_hvac body."""

    hass = _make_hass_for_services(already_registered=False)
    captured = {}

    def capture(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = capture
    _async_register_services(hass)

    coordinator = MagicMock()
    coordinator.async_fetch_hvac = AsyncMock()
    call = MagicMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[("entry1", "VIN123")],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(coordinator, None),
    ):
        await captured["fetch_hvac"](call)

    coordinator.async_fetch_hvac.assert_called_once()


# ---------------------------------------------------------------------------
# async_setup_entry partial coverage (lines 55-102)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_entry_no_vehicles_raises() -> None:
    """Cover lines 55-102 via mocked BydApi returning empty vehicle list."""
    hass = MagicMock()
    hass.data = MagicMock()
    hass.data.setdefault = MagicMock()
    hass.config.time_zone = "UTC"

    entry = MagicMock()
    entry.entry_id = "entry1"
    # Device profile already present — skips async_generate_device_profile
    entry.data = {
        CONF_DEVICE_PROFILE: {"uuid": "test-uuid", "model": "test"},
    }
    entry.options = {
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_GPS_POLL_INTERVAL: DEFAULT_GPS_POLL_INTERVAL,
        CONF_SMART_GPS_POLLING: DEFAULT_SMART_GPS_POLLING,
        CONF_GPS_ACTIVE_INTERVAL: DEFAULT_GPS_ACTIVE_INTERVAL,
        CONF_GPS_INACTIVE_INTERVAL: DEFAULT_GPS_INACTIVE_INTERVAL,
    }

    with patch(
        "custom_components.byd_vehicle.async_get_clientsession",
        return_value=MagicMock(),
    ), patch("custom_components.byd_vehicle.BydApi") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_call = AsyncMock(return_value=[])  # no vehicles

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)

    hass.data.setdefault.assert_called_once_with(DOMAIN, {})
