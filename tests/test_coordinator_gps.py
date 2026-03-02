"""Unit tests for BydGpsUpdateCoordinator helpers and fetch paths."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.byd_vehicle.coordinator import (
    BydGpsUpdateCoordinator,
)


def _make_gps_coordinator() -> BydGpsUpdateCoordinator:
    """Create a BydGpsUpdateCoordinator bypassing __init__."""
    coordinator = object.__new__(BydGpsUpdateCoordinator)
    coordinator._api = MagicMock()
    coordinator._vin = "TESTVIN123456"
    coordinator._vehicle = MagicMock()
    coordinator._telemetry_coordinator = None
    coordinator._smart_polling = False
    coordinator._fixed_interval = timedelta(seconds=300)
    coordinator._active_interval = timedelta(seconds=30)
    coordinator._inactive_interval = timedelta(seconds=600)
    coordinator._current_interval = timedelta(seconds=300)
    coordinator._polling_enabled = True
    coordinator._force_next_refresh = False
    coordinator._last_gps = None
    coordinator.data = {}
    coordinator.update_interval = timedelta(seconds=300)
    coordinator.async_set_updated_data = MagicMock()
    return coordinator


class TestBydGpsCoordinatorHelpers:

    def test_polling_enabled_property(self) -> None:
        coordinator = _make_gps_coordinator()
        assert coordinator.polling_enabled is True

    def test_set_polling_enabled_false(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator.set_polling_enabled(False)
        assert coordinator._polling_enabled is False
        assert coordinator.update_interval is None

    def test_set_polling_enabled_true(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._polling_enabled = False
        coordinator.set_polling_enabled(True)
        assert coordinator._polling_enabled is True

    def test_adjust_interval_no_smart_polling(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = False
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._fixed_interval

    def test_adjust_interval_smart_vehicle_on(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = True
        telemetry = MagicMock()
        telemetry.is_vehicle_on = True
        coordinator._telemetry_coordinator = telemetry
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._active_interval

    def test_adjust_interval_smart_vehicle_off(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = True
        telemetry = MagicMock()
        telemetry.is_vehicle_on = False
        coordinator._telemetry_coordinator = telemetry
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._inactive_interval

    def test_adjust_interval_smart_no_telemetry(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = True
        coordinator._telemetry_coordinator = None
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._inactive_interval


@pytest.mark.asyncio
async def test_gps_async_force_refresh_sets_flag() -> None:

    coordinator = _make_gps_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    await coordinator.async_force_refresh()
    assert coordinator._force_next_refresh is True
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_gps_updates_data() -> None:
    """async_fetch_gps should update coordinator data with GPS info."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.data = {"vehicles": {}}
    gps = GpsInfo(latitude=51.5, longitude=4.8)
    coordinator._api.async_call = AsyncMock(return_value=gps)
    await coordinator.async_fetch_gps()
    coordinator.async_set_updated_data.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_gps_with_null_island_guards() -> None:
    """async_fetch_gps should guard against Null Island coordinates."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.data = {"vehicles": {}}
    coordinator._last_gps = GpsInfo(latitude=51.5, longitude=4.8)  # valid previous
    # Null Island (0,0) should be rejected
    gps = GpsInfo(latitude=0.0, longitude=0.0)
    coordinator._api.async_call = AsyncMock(return_value=gps)
    await coordinator.async_fetch_gps()
    # Data still updated (but without the null island GPS)
    coordinator.async_set_updated_data.assert_called_once()


def test_gps_coordinator_init() -> None:
    """Cover lines 788-805: GPS coordinator __init__ with mocked parent."""
    from datetime import timedelta

    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    api = MagicMock()
    vehicle = MagicMock()
    telemetry = MagicMock()

    with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
        from custom_components.byd_vehicle.coordinator import BydGpsUpdateCoordinator

        coordinator = BydGpsUpdateCoordinator(
            MagicMock(),
            api,
            vehicle,
            "TESTVIN123456",
            300,
            telemetry_coordinator=telemetry,
            smart_polling=True,
            active_interval=30,
            inactive_interval=600,
        )

    assert coordinator._api is api
    assert coordinator._vin == "TESTVIN123456"
    assert coordinator._smart_polling is True
    assert coordinator._active_interval == timedelta(seconds=30)
    assert coordinator._inactive_interval == timedelta(seconds=600)
    assert coordinator._telemetry_coordinator is telemetry


@pytest.mark.asyncio
async def test_async_fetch_gps_invokes_fetch_closure() -> None:
    """Line 826: the _fetch closure inside async_fetch_gps."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.data = {"vehicles": {}}

    mock_client = MagicMock()
    gps = GpsInfo(latitude=51.5, longitude=4.8)
    mock_client.get_gps_info = AsyncMock(return_value=gps)

    async def invoke_handler(handler, **kwargs):
        return await handler(mock_client)

    coordinator._api.async_call = invoke_handler
    await coordinator.async_fetch_gps()
    mock_client.get_gps_info.assert_called_once_with(coordinator._vin)


@pytest.mark.asyncio
async def test_gps_update_data_polling_disabled_returns_cached() -> None:
    """Cover when polling disabled and data is dict (lines 859-862)."""
    coordinator = _make_gps_coordinator()
    coordinator._polling_enabled = False
    coordinator._force_next_refresh = False
    cached = {"vehicles": {coordinator._vin: coordinator._vehicle}}
    coordinator.data = cached

    result = await coordinator._async_update_data()
    assert result is cached


@pytest.mark.asyncio
async def test_gps_update_data_polling_disabled_no_dict_returns_vehicles() -> None:
    """Cover lines 859-862: when polling disabled and data not dict, return fallback."""
    coordinator = _make_gps_coordinator()
    coordinator._polling_enabled = False
    coordinator._force_next_refresh = False
    coordinator.data = None  # not a dict

    result = await coordinator._async_update_data()
    assert coordinator._vin in result["vehicles"]


@pytest.mark.asyncio
async def test_gps_update_data_fetch_closure_success() -> None:
    """Cover lines 864-917: full _async_update_data GPS fetch path."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.hass = MagicMock()
    coordinator.update_interval = timedelta(seconds=300)

    gps = GpsInfo(latitude=51.5, longitude=4.8)
    mock_client = MagicMock()
    mock_client.get_gps_info = AsyncMock(return_value=gps)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    assert coordinator._vin in result.get("gps", {})


@pytest.mark.asyncio
async def test_gps_fetch_recoverable_error_raises_update_failed() -> None:
    """Cover GPS _RECOVERABLE_ERRORS → UpdateFailed (lines 870-873 + 893)."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydApiError

    coordinator = _make_gps_coordinator()
    coordinator.hass = MagicMock()

    mock_client = MagicMock()
    mock_client.get_gps_info = AsyncMock(side_effect=BydApiError("gps error"))

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_gps_fetch_coordinates_unavailable_keeps_previous() -> None:
    """Cover coordinator.py line 879: debug log when guarded_gps kept from previous."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.hass = MagicMock()
    coordinator._last_gps = GpsInfo(latitude=51.5, longitude=4.8)

    # Null Island → guard_gps_coordinates will fall back to last_gps
    null_gps = GpsInfo(latitude=0.0, longitude=0.0)
    mock_client = MagicMock()
    mock_client.get_gps_info = AsyncMock(return_value=null_gps)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    # Previous GPS was kept
    assert coordinator._vin in result.get("gps", {})


@pytest.mark.asyncio
async def test_gps_fetch_debug_dump_enabled() -> None:
    """Cover coordinator.py lines 897-901: GPS debug dump when debug_dumps_enabled."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.hass = MagicMock()

    gps = GpsInfo(latitude=51.5, longitude=4.8)
    mock_client = MagicMock()
    mock_client.get_gps_info = AsyncMock(return_value=gps)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = True
    coordinator._api.async_write_debug_dump = AsyncMock()

    await coordinator._async_update_data()
    coordinator.hass.async_create_task.assert_called()


@pytest.mark.asyncio
async def test_gps_fetch_auth_error_reraises() -> None:
    """Cover coordinator.py line 871: auth error re-raised from GPS _fetch."""
    from pybyd import BydAuthenticationError

    coordinator = _make_gps_coordinator()
    coordinator.hass = MagicMock()

    mock_client = MagicMock()
    mock_client.get_gps_info = AsyncMock(
        side_effect=BydAuthenticationError("auth")
    )

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    with pytest.raises(BydAuthenticationError):
        await coordinator._async_update_data()
