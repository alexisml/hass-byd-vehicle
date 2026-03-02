"""Unit tests for binary_sensor pure helpers."""

from __future__ import annotations

import types

from pybyd.models.realtime import ChargingState

from custom_components.byd_vehicle.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
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
