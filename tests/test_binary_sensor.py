"""Unit tests for binary_sensor module."""

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd.models.realtime import ChargingState

from custom_components.byd_vehicle.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    BydBinarySensor,
    BydBinarySensorDescription,
    _as_charging_state,
    _attr_equals,
    _attr_truthy,
    _is_charging_from_realtime,
    _is_plug_connected_from_realtime,
)


def test_as_charging_state_none() -> None:
    assert _as_charging_state(None) is None


def test_as_charging_state_invalid_string() -> None:
    assert _as_charging_state("invalid") is None


def test_as_charging_state_valid_int() -> None:
    assert _as_charging_state(1) is ChargingState.CHARGING


def test_as_charging_state_passthrough() -> None:
    assert _as_charging_state(ChargingState.CONNECTED) is ChargingState.CONNECTED


def test_is_charging_from_realtime_bool_attr() -> None:
    obj = types.SimpleNamespace(is_charging=True)
    assert _is_charging_from_realtime(obj) is True


def test_is_charging_from_realtime_no_data() -> None:
    obj = types.SimpleNamespace(is_charging=None, charge_state=None)
    assert _is_charging_from_realtime(obj) is None


def test_is_plug_connected_from_realtime_bool_attr() -> None:
    obj = types.SimpleNamespace(is_charger_connected=False)
    assert _is_plug_connected_from_realtime(obj) is False


def test_is_plug_connected_from_realtime_no_data() -> None:
    obj = types.SimpleNamespace(is_charger_connected=None, charge_state=None)
    assert _is_plug_connected_from_realtime(obj) is None


def test_attr_truthy_true() -> None:
    fn = _attr_truthy("x")
    assert fn(types.SimpleNamespace(x=True)) is True


def test_attr_truthy_none() -> None:
    fn = _attr_truthy("x")
    assert fn(types.SimpleNamespace(x=None)) is None


def test_attr_truthy_missing() -> None:
    fn = _attr_truthy("x")
    assert fn(types.SimpleNamespace()) is None


def test_attr_equals_match() -> None:
    fn = _attr_equals("x", 5)
    assert fn(types.SimpleNamespace(x=5)) is True


def test_attr_equals_no_match() -> None:
    fn = _attr_equals("x", 5)
    assert fn(types.SimpleNamespace(x=3)) is False


def test_attr_equals_none() -> None:
    fn = _attr_equals("x", 5)
    assert fn(types.SimpleNamespace(x=None)) is None


def test_binary_sensor_descriptions_nonempty() -> None:
    assert isinstance(BINARY_SENSOR_DESCRIPTIONS, tuple)
    assert len(BINARY_SENSOR_DESCRIPTIONS) > 0


def test_binary_sensor_descriptions_have_keys() -> None:
    for desc in BINARY_SENSOR_DESCRIPTIONS:
        assert isinstance(desc.key, str) and desc.key


# ---------------------------------------------------------------------------
# BydBinarySensor entity tests (bypass __init__ with object.__new__)
# ---------------------------------------------------------------------------


def _make_binary_sensor(
    realtime_obj=None,
    value_fn=None,
    attr_key=None,
    source="realtime",
) -> BydBinarySensor:
    """Create a BydBinarySensor without a running HA instance."""
    desc = BydBinarySensorDescription(
        key="test_sensor",
        source=source,
        value_fn=value_fn,
        attr_key=attr_key,
    )
    coordinator = MagicMock()
    coordinator.last_update_success = True
    vin = "TESTVIN123"
    data: dict = {}
    if realtime_obj is not None:
        data["realtime"] = {vin: realtime_obj}
    data["vehicles"] = {vin: MagicMock()}
    coordinator.data = data

    sensor = object.__new__(BydBinarySensor)
    sensor.coordinator = coordinator
    sensor._vin = vin
    sensor._vehicle = MagicMock()
    sensor.entity_description = desc
    sensor._attr_unique_id = f"{vin}_realtime_test_sensor"
    sensor._last_is_on = None
    sensor._command_pending = False
    sensor._commanded_at = None
    sensor.async_write_ha_state = MagicMock()
    return sensor


def test_resolve_value_with_value_fn() -> None:
    rt = types.SimpleNamespace(is_charging=True)
    sensor = _make_binary_sensor(realtime_obj=rt, value_fn=lambda o: o.is_charging)
    assert sensor._resolve_value() is True


def test_resolve_value_with_attr_key() -> None:
    rt = types.SimpleNamespace(door_open=True)
    sensor = _make_binary_sensor(realtime_obj=rt, attr_key="door_open")
    assert sensor._resolve_value() is True


def test_resolve_value_attr_key_none() -> None:
    rt = types.SimpleNamespace(door_open=None)
    sensor = _make_binary_sensor(realtime_obj=rt, attr_key="door_open")
    assert sensor._resolve_value() is None


def test_resolve_value_no_source_obj() -> None:
    sensor = _make_binary_sensor(realtime_obj=None)
    assert sensor._resolve_value() is None


def test_is_on_returns_value_fn_result() -> None:
    rt = types.SimpleNamespace(is_charging=False)
    sensor = _make_binary_sensor(realtime_obj=rt, value_fn=lambda o: o.is_charging)
    assert sensor.is_on is False


def test_is_on_falls_back_to_last_known() -> None:
    sensor = _make_binary_sensor(realtime_obj=None)
    sensor._last_is_on = True
    assert sensor.is_on is True


def test_available_false_when_no_source_obj() -> None:
    sensor = _make_binary_sensor(realtime_obj=None)
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert sensor.available is False


def test_available_true_when_source_obj_present() -> None:
    rt = types.SimpleNamespace(is_charging=True)
    sensor = _make_binary_sensor(realtime_obj=rt)
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert sensor.available is True


def test_handle_coordinator_update_tracks_last_is_on() -> None:
    rt = types.SimpleNamespace(is_charging=True)
    sensor = _make_binary_sensor(realtime_obj=rt, value_fn=lambda o: o.is_charging)
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        sensor._handle_coordinator_update()
    assert sensor._last_is_on is True


def test_handle_coordinator_update_no_value_no_change() -> None:
    sensor = _make_binary_sensor(realtime_obj=None)
    sensor._last_is_on = True
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        sensor._handle_coordinator_update()
    # last_is_on unchanged because _resolve_value() returned None
    assert sensor._last_is_on is True
