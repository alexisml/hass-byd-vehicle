"""Integration tests: MQTT push → coordinator → entity state propagation.

Exercises BydApi._handle_vehicle_info dispatching into the coordinator,
which then updates its data so entities reflect the new realtime state.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pybyd.models.realtime import VehicleRealtimeData

from custom_components.byd_vehicle.coordinator import BydApi

from .helpers import make_sensor_entity, make_telemetry_coordinator


def test_mqtt_push_updates_coordinator_and_sensor() -> None:
    """An MQTT vehicleInfo push propagates to the coordinator and sensor."""
    vin = "VIN_MQTT_001"
    coordinator = make_telemetry_coordinator(vin=vin)
    coordinator.data = {"vehicles": {vin: coordinator._vehicle}}

    # Wire a real async_set_updated_data side-effect so data is mutated.
    received: list[dict] = []

    def _capture(new_data):
        coordinator.data = new_data
        received.append(new_data)

    coordinator.async_set_updated_data = _capture

    # Create the sensor before the push.
    sensor = make_sensor_entity(coordinator, key="elec_percent", source="realtime")

    # Simulate an MQTT push via BydApi._handle_vehicle_info.
    api = object.__new__(BydApi)
    api._coordinators = {vin: coordinator}
    api._debug_dumps_enabled = False
    api._hass = MagicMock()

    rt = MagicMock(spec=VehicleRealtimeData)
    rt.elec_percent = 82
    api._handle_vehicle_info(vin, rt)

    # coordinator received the realtime data
    assert coordinator._last_realtime is rt
    assert len(received) == 1
    assert received[0]["realtime"][vin] is rt

    # sensor now reads the new value from coordinator data
    assert sensor.coordinator.data["realtime"][vin].elec_percent == 82


def test_mqtt_push_for_unknown_vin_does_not_raise() -> None:
    """A vehicleInfo push for an unknown VIN is silently ignored."""
    api = object.__new__(BydApi)
    api._coordinators = {}
    api._debug_dumps_enabled = False
    api._hass = MagicMock()

    rt = MagicMock(spec=VehicleRealtimeData)
    # Should not raise
    api._handle_vehicle_info("UNKNOWN_VIN", rt)
