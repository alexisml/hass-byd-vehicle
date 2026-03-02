"""Integration tests: service call routing pipeline.

Verifies _resolve_vins_from_call → _get_coordinators → coordinator methods,
covering the full service dispatch path used by fetch_realtime / fetch_gps.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers import device_registry as dr

from custom_components.byd_vehicle import (
    _async_register_services,
    _get_coordinators,
    _resolve_vins_from_call,
)
from custom_components.byd_vehicle.const import DOMAIN


def test_resolve_vins_returns_entry_vin_pair() -> None:
    """_resolve_vins_from_call resolves device → entry_id, vin correctly."""
    vin = "VIN_SVC_001"
    entry_id = "entry_svc_1"
    device_id = "device_abc"

    fake_device = MagicMock()
    fake_device.identifiers = {(DOMAIN, vin)}

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: MagicMock()},
            }
        }
    }

    call = MagicMock()
    call.data = {"device_id": device_id}

    with patch.object(dr, "async_get") as mock_reg:
        mock_reg.return_value.async_get.return_value = fake_device
        results = _resolve_vins_from_call(hass, call)

    assert (entry_id, vin) in results


def test_get_coordinators_returns_telemetry_and_gps() -> None:
    """_get_coordinators returns the correct (telemetry, gps) tuple."""
    vin = "VIN_SVC_002"
    entry_id = "entry_svc_2"

    telemetry_coord = MagicMock()
    gps_coord = MagicMock()

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: telemetry_coord},
                "gps_coordinators": {vin: gps_coord},
            }
        }
    }

    telemetry, gps = _get_coordinators(hass, entry_id, vin)
    assert telemetry is telemetry_coord
    assert gps is gps_coord


def test_get_coordinators_gps_none_when_not_present() -> None:
    """_get_coordinators returns None for gps when no GPS coordinator exists."""
    vin = "VIN_SVC_003"
    entry_id = "entry_svc_3"

    telemetry_coord = MagicMock()

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: telemetry_coord},
                # no gps_coordinators key
            }
        }
    }

    telemetry, gps = _get_coordinators(hass, entry_id, vin)
    assert telemetry is telemetry_coord
    assert gps is None


@pytest.mark.asyncio
async def test_service_fetch_realtime_reaches_coordinator() -> None:
    """Registered fetch_realtime service handler calls coordinator.async_fetch_realtime."""
    vin = "VIN_SVC_004"
    entry_id = "entry_svc_4"

    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = False

    captured: dict = {}

    def _register(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = _register
    _async_register_services(hass)

    coordinator = MagicMock()
    coordinator.async_fetch_realtime = AsyncMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[(entry_id, vin)],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(coordinator, None),
    ):
        await captured["fetch_realtime"](MagicMock())

    coordinator.async_fetch_realtime.assert_called_once()


@pytest.mark.asyncio
async def test_service_fetch_gps_reaches_gps_coordinator() -> None:
    """Registered fetch_gps service handler calls gps.async_fetch_gps."""
    vin = "VIN_SVC_005"
    entry_id = "entry_svc_5"

    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = False

    captured: dict = {}

    def _register(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = _register
    _async_register_services(hass)

    gps_coord = MagicMock()
    gps_coord.async_fetch_gps = AsyncMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[(entry_id, vin)],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(MagicMock(), gps_coord),
    ):
        await captured["fetch_gps"](MagicMock())

    gps_coord.async_fetch_gps.assert_called_once()
