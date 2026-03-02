"""Integration tests: multiple entity types sharing one coordinator.

After a single coordinator data update, a BydSensor, a BydBinarySensor,
and a BydLock all derive their state from the same dict — verifying that
the shared data model flows correctly through every entity type.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock

from custom_components.byd_vehicle.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    BydBinarySensor,
)

from .helpers import make_lock_entity, make_sensor_entity, make_telemetry_coordinator


def test_multi_entity_types_share_coordinator_data() -> None:
    """Sensor, binary sensor, and lock all read the same coordinator data."""
    vin = "VIN_MULTI_001"
    rt = types.SimpleNamespace(
        elec_percent=65,
        is_locked=False,
        is_charging=True,
        charge_state=None,
        is_charger_connected=None,
    )
    data = {
        "vehicles": {vin: MagicMock()},
        "realtime": {vin: rt},
    }
    coordinator = make_telemetry_coordinator(vin=vin, data=data)

    # --- BydSensor (battery %)
    sensor = make_sensor_entity(coordinator, key="elec_percent", source="realtime")
    assert sensor._get_source_obj("realtime") is rt

    # --- BydBinarySensor (charging)
    charging_desc = next(
        d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "is_charging"
    )
    binary = object.__new__(BydBinarySensor)
    binary.coordinator = coordinator
    binary._vin = vin
    binary._vehicle = MagicMock()
    binary.entity_description = charging_desc
    binary._attr_unique_id = f"{vin}_charging"
    binary._command_pending = False
    binary._commanded_at = None
    binary.async_write_ha_state = MagicMock()
    assert binary.is_on is True  # is_charging=True

    # --- BydLock
    lock = make_lock_entity(coordinator)
    assert lock.is_locked is False


def test_multi_entity_types_reflect_updated_coordinator_data() -> None:
    """After a coordinator data change, all entities see the new state."""
    vin = "VIN_MULTI_002"
    rt_initial = types.SimpleNamespace(is_locked=True, elec_percent=50)
    data = {
        "vehicles": {vin: MagicMock()},
        "realtime": {vin: rt_initial},
    }
    coordinator = make_telemetry_coordinator(vin=vin, data=data)

    sensor = make_sensor_entity(coordinator, key="elec_percent", source="realtime")
    lock = make_lock_entity(coordinator)

    # Verify initial state
    assert sensor._get_source_obj("realtime").elec_percent == 50
    assert lock.is_locked is True

    # Simulate a coordinator data update (e.g. after a poll)
    rt_new = types.SimpleNamespace(is_locked=False, elec_percent=75)
    coordinator.data = {
        "vehicles": {vin: coordinator._vehicle},
        "realtime": {vin: rt_new},
    }

    # Both entities now read the updated data
    assert sensor._get_source_obj("realtime").elec_percent == 75
    assert lock.is_locked is False
