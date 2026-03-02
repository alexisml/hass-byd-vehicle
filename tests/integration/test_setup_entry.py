"""Integration tests: full async_setup_entry with multiple vehicles.

Drives async_setup_entry from __init__.py with a mocked API returning two
vehicles and verifies that coordinators and gps_coordinators are populated
for each VIN.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.byd_vehicle import async_setup_entry
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

_DEVICE_PROFILE = {
    "model": "TestModel",
    "imei": "123456789012345",
    "mac": "aa:bb:cc:dd:ee:ff",
    "sdk": "28",
    "mod": "Generic",
    "imei_md5": "abc123",
    "mobile_brand": "Generic",
    "mobile_model": "TestModel",
    "device_type": "0",
    "network_type": "wifi",
    "os_type": "and",
    "os_version": "28",
    "ostype": "and",
}


@pytest.mark.asyncio
async def test_async_setup_entry_multi_vehicle_creates_coordinators() -> None:
    """async_setup_entry creates one telemetry + GPS coordinator per vehicle."""
    hass = MagicMock()
    hass.data = {}
    hass.config.time_zone = "UTC"
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=None)

    vin_a = "VIN_SETUP_AAA"
    vin_b = "VIN_SETUP_BBB"

    vehicle_a = MagicMock()
    vehicle_a.vin = vin_a
    vehicle_b = MagicMock()
    vehicle_b.vin = vin_b

    entry = MagicMock()
    entry.entry_id = "entry_setup_1"
    entry.data = {
        CONF_DEVICE_PROFILE: _DEVICE_PROFILE,
        "username": "user@test.com",
        "password": "secret",
        "base_url": "https://api.example.com",
        "country_code": "NL",
        "language": "en",
    }
    entry.options = {
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_GPS_POLL_INTERVAL: DEFAULT_GPS_POLL_INTERVAL,
        CONF_SMART_GPS_POLLING: DEFAULT_SMART_GPS_POLLING,
        CONF_GPS_ACTIVE_INTERVAL: DEFAULT_GPS_ACTIVE_INTERVAL,
        CONF_GPS_INACTIVE_INTERVAL: DEFAULT_GPS_INACTIVE_INTERVAL,
    }
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=lambda: None)

    hass.services = MagicMock()
    hass.services.has_service.return_value = False
    hass.services.async_register = MagicMock()

    with patch(
        "custom_components.byd_vehicle.async_get_clientsession",
        return_value=MagicMock(),
    ), patch("custom_components.byd_vehicle.BydApi") as MockBydApi:
        mock_api_instance = MagicMock()
        mock_api_instance.register_coordinators = MagicMock()
        mock_api_instance.async_call = AsyncMock(
            return_value=[vehicle_a, vehicle_b]
        )
        MockBydApi.return_value = mock_api_instance

        with patch(
            "custom_components.byd_vehicle.BydDataUpdateCoordinator"
        ) as MockTelemetry, patch(
            "custom_components.byd_vehicle.BydGpsUpdateCoordinator"
        ) as MockGps:
            telemetry_instances: dict[str, MagicMock] = {}
            gps_instances: dict[str, MagicMock] = {}

            def _make_telemetry(_hass, _api, _vehicle, vin, _interval):
                m = MagicMock()
                m.async_config_entry_first_refresh = AsyncMock()
                telemetry_instances[vin] = m
                return m

            def _make_gps(_hass, _api, _vehicle, vin, _interval, **kwargs):
                m = MagicMock()
                m.async_config_entry_first_refresh = AsyncMock()
                gps_instances[vin] = m
                return m

            MockTelemetry.side_effect = _make_telemetry
            MockGps.side_effect = _make_gps

            result = await async_setup_entry(hass, entry)

    assert result is True
    # Both VINs have telemetry coordinators
    assert vin_a in telemetry_instances
    assert vin_b in telemetry_instances
    # Both VINs have GPS coordinators
    assert vin_a in gps_instances
    assert vin_b in gps_instances
    # Coordinators are registered with the API
    mock_api_instance.register_coordinators.assert_called_once()
    # hass.data contains entry data
    assert entry.entry_id in hass.data[DOMAIN]
    assert "coordinators" in hass.data[DOMAIN][entry.entry_id]
    assert "gps_coordinators" in hass.data[DOMAIN][entry.entry_id]
