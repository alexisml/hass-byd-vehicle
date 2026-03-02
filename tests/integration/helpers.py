"""Shared factory helpers for integration tests."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from custom_components.byd_vehicle.coordinator import (
    BydDataUpdateCoordinator,
    BydGpsUpdateCoordinator,
)
from custom_components.byd_vehicle.lock import BydLock
from custom_components.byd_vehicle.sensor import BydSensor, BydSensorDescription


def make_telemetry_coordinator(
    vin: str = "TESTVIN123456",
    data: dict | None = None,
) -> BydDataUpdateCoordinator:
    """Create a BydDataUpdateCoordinator bypassing __init__."""
    coordinator = object.__new__(BydDataUpdateCoordinator)
    coordinator._api = MagicMock()
    coordinator._vin = vin
    coordinator._vehicle = MagicMock()
    coordinator._fixed_interval = timedelta(seconds=60)
    coordinator._polling_enabled = True
    coordinator._force_next_refresh = False
    coordinator._last_realtime = None
    coordinator._last_hvac = None
    coordinator._optimistic_hvac_until = None
    coordinator._optimistic_ac_expected = None
    coordinator._realtime_endpoint_unsupported = False
    coordinator.update_interval = timedelta(seconds=60)
    coordinator.last_update_success = True
    coordinator.async_set_updated_data = MagicMock()
    coordinator.data = data or {"vehicles": {vin: coordinator._vehicle}}
    return coordinator


def make_gps_coordinator(
    vin: str = "TESTVIN123456",
    telemetry: BydDataUpdateCoordinator | None = None,
    smart_polling: bool = False,
    active_interval: int = 30,
    inactive_interval: int = 600,
    poll_interval: int = 300,
) -> BydGpsUpdateCoordinator:
    """Create a BydGpsUpdateCoordinator bypassing __init__."""
    gps = object.__new__(BydGpsUpdateCoordinator)
    gps._api = MagicMock()
    gps._vin = vin
    gps._vehicle = MagicMock()
    gps._telemetry_coordinator = telemetry
    gps._smart_polling = smart_polling
    gps._fixed_interval = timedelta(seconds=poll_interval)
    gps._active_interval = timedelta(seconds=active_interval)
    gps._inactive_interval = timedelta(seconds=inactive_interval)
    gps._current_interval = timedelta(seconds=poll_interval)
    gps._polling_enabled = True
    gps._force_next_refresh = False
    gps._last_gps = None
    gps.update_interval = timedelta(seconds=poll_interval)
    gps.last_update_success = True
    gps.async_set_updated_data = MagicMock()
    gps.data = {"vehicles": {vin: gps._vehicle}}
    return gps


def make_lock_entity(coordinator: BydDataUpdateCoordinator) -> BydLock:
    """Create a BydLock wired to *coordinator*."""
    vin = coordinator._vin
    entity = object.__new__(BydLock)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = coordinator._vehicle
    entity._api = MagicMock()
    entity._api.async_call = AsyncMock()
    entity._attr_unique_id = f"{vin}_lock"
    entity._command_pending = False
    entity._commanded_at = None
    entity._last_command = None
    entity._last_locked = None
    entity.async_write_ha_state = MagicMock()
    return entity


def make_sensor_entity(
    coordinator: BydDataUpdateCoordinator,
    key: str = "elec_percent",
    source: str = "realtime",
    attr_key: str | None = None,
    value_fn=None,
) -> BydSensor:
    """Create a BydSensor wired to *coordinator*."""
    vin = coordinator._vin
    desc = BydSensorDescription(
        key=key,
        source=source,
        attr_key=attr_key,
        value_fn=value_fn,
    )
    sensor = object.__new__(BydSensor)
    sensor.coordinator = coordinator
    sensor._vin = vin
    sensor._vehicle = coordinator._vehicle
    sensor.entity_description = desc
    sensor._attr_unique_id = f"{vin}_{source}_{key}"
    sensor._last_native_value = None
    sensor._command_pending = False
    sensor._commanded_at = None
    sensor.async_write_ha_state = MagicMock()
    return sensor
