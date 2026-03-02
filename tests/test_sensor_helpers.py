"""Unit tests for sensor module helpers and entity properties."""

from __future__ import annotations

import types
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.byd_vehicle.sensor import (
    BydSensor,
    BydSensorDescription,
    _normalize_epoch,
    _round_int_attr,
)


class TestNormalizeEpoch:
    """Tests for _normalize_epoch."""

    def test_none_returns_none(self) -> None:
        assert _normalize_epoch(None) is None

    def test_datetime_with_utc_returned_as_is(self) -> None:
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        assert _normalize_epoch(dt) is dt

    def test_naive_datetime_gets_utc(self) -> None:
        dt = datetime(2024, 1, 1)
        result = _normalize_epoch(dt)
        assert result is not None
        assert result.tzinfo == UTC

    def test_integer_seconds(self) -> None:
        result = _normalize_epoch(1_000_000)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_integer_milliseconds(self) -> None:
        # Value > 1_000_000_000_000 → treated as milliseconds
        ts_ms = 1_000_000_000_001
        result = _normalize_epoch(ts_ms)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC
        # Should equal the seconds-based equivalent
        expected = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        assert result == expected

    def test_negative_returns_none(self) -> None:
        assert _normalize_epoch(-1) is None

    def test_zero_returns_none(self) -> None:
        assert _normalize_epoch(0) is None

    def test_non_numeric_string_returns_none(self) -> None:
        assert _normalize_epoch("bad") is None


class TestRoundIntAttr:
    """Tests for _round_int_attr."""

    def test_rounds_float(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace(val=5.7)
        assert fn(obj) == 6

    def test_none_attr_returns_none(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace(val=None)
        assert fn(obj) is None

    def test_missing_attr_returns_none(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace()
        assert fn(obj) is None

    def test_integer_value(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace(val=3)
        assert fn(obj) == 3


# ---------------------------------------------------------------------------
# BydSensor entity helpers
# ---------------------------------------------------------------------------


def _make_sensor(
    data: dict | None = None,
    key: str = "test_sensor",
    source: str = "realtime",
    attr_key: str | None = None,
    value_fn=None,
    validator_fn=None,
) -> BydSensor:
    """Create a BydSensor without a running HA instance."""
    vin = "TESTVIN123"
    desc = BydSensorDescription(
        key=key,
        source=source,
        attr_key=attr_key,
        value_fn=value_fn,
        validator_fn=validator_fn,
    )
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = data or {"vehicles": {vin: MagicMock()}}

    sensor = object.__new__(BydSensor)
    sensor.coordinator = coordinator
    sensor._vin = vin
    sensor._vehicle = MagicMock()
    sensor.entity_description = desc
    sensor._attr_unique_id = f"{vin}_{source}_{key}"
    sensor._last_native_value = None
    sensor._command_pending = False
    sensor._commanded_at = None
    sensor.async_write_ha_state = MagicMock()
    return sensor


def test_resolve_value_with_value_fn() -> None:
    rt = types.SimpleNamespace(speed=120)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        value_fn=lambda o: o.speed,
    )
    assert sensor._resolve_value() == 120


def test_resolve_value_with_attr_key() -> None:
    rt = types.SimpleNamespace(battery_level=80)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        attr_key="battery_level",
    )
    assert sensor._resolve_value() == 80


def test_resolve_value_returns_none_when_no_source_obj() -> None:
    sensor = _make_sensor(data={"vehicles": {"TESTVIN123": MagicMock()}})
    assert sensor._resolve_value() is None


def test_resolve_value_last_updated_with_timestamp() -> None:
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    rt = types.SimpleNamespace(timestamp=ts)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        key="last_updated",
    )
    result = sensor._resolve_value()
    assert isinstance(result, datetime)


def test_resolve_value_last_updated_no_realtime() -> None:
    sensor = _make_sensor(
        data={"vehicles": {"TESTVIN123": MagicMock()}},
        key="last_updated",
    )
    assert sensor._resolve_value() is None


def test_resolve_value_gps_last_updated() -> None:
    gps = types.SimpleNamespace(gps_timestamp=None)
    sensor = _make_sensor(
        data={
            "gps": {"TESTVIN123": gps},
            "vehicles": {"TESTVIN123": MagicMock()},
        },
        key="gps_last_updated",
    )
    assert sensor._resolve_value() is None


def test_resolve_value_enum_attr_returns_value() -> None:
    """Test that enum values with .value attribute are unwrapped."""
    enum_like = types.SimpleNamespace(value=3)
    rt = types.SimpleNamespace(charge_state=enum_like)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        attr_key="charge_state",
    )
    assert sensor._resolve_value() == 3


def test_resolve_validated_value_applies_validator() -> None:
    rt = types.SimpleNamespace(battery_level=80)
    calls = []

    def validator(prev, val):
        calls.append((prev, val))
        return val

    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        attr_key="battery_level",
        validator_fn=validator,
    )
    result = sensor._resolve_validated_value()
    assert result == 80
    assert len(calls) == 1
    assert sensor._last_native_value == 80


def test_native_value_returns_resolved() -> None:
    rt = types.SimpleNamespace(battery_level=75)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        attr_key="battery_level",
    )
    assert sensor.native_value == 75


def test_available_false_when_no_source_obj() -> None:
    sensor = _make_sensor(data={"vehicles": {"TESTVIN123": MagicMock()}})
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert sensor.available is False


def test_available_true_when_source_obj_present() -> None:
    rt = types.SimpleNamespace(battery_level=75)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        attr_key="battery_level",
    )
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert sensor.available is True


# ---------------------------------------------------------------------------
# native_unit_of_measurement for tire pressure sensors
# ---------------------------------------------------------------------------


def test_native_unit_tire_pressure_bar() -> None:
    from homeassistant.const import UnitOfPressure
    from pybyd.models.realtime import TirePressureUnit

    rt = types.SimpleNamespace(
        left_front_tire_pressure=2.3,
        tire_press_unit=TirePressureUnit.BAR,
    )
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        key="left_front_tire_pressure",
        attr_key="left_front_tire_pressure",
    )
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        unit = sensor.native_unit_of_measurement
    assert unit == UnitOfPressure.BAR


def test_native_unit_tire_pressure_falls_back_to_desc_unit() -> None:
    rt = types.SimpleNamespace(
        left_front_tire_pressure=None,
        tire_press_unit=None,
    )
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        key="left_front_tire_pressure",
        attr_key="left_front_tire_pressure",
    )
    # Should return whatever is set on the description (None here since we're
    # using a plain BydSensorDescription without a unit).
    unit = sensor.native_unit_of_measurement
    assert unit is None


def test_native_unit_non_tire_sensor_returns_desc_unit() -> None:
    rt = types.SimpleNamespace(battery_level=80)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        attr_key="battery_level",
    )
    # No unit set in description → None
    assert sensor.native_unit_of_measurement is None


# ---------------------------------------------------------------------------
# available for last_updated / gps_last_updated sensors
# ---------------------------------------------------------------------------


def test_available_last_updated_true_when_timestamp_present() -> None:
    from datetime import UTC, datetime

    ts = datetime(2024, 1, 1, tzinfo=UTC)
    rt = types.SimpleNamespace(timestamp=ts)
    sensor = _make_sensor(
        data={"realtime": {"TESTVIN123": rt}, "vehicles": {"TESTVIN123": MagicMock()}},
        key="last_updated",
    )
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert sensor.available is True


def test_available_last_updated_false_when_no_realtime() -> None:
    sensor = _make_sensor(
        data={"vehicles": {"TESTVIN123": MagicMock()}},
        key="last_updated",
    )
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert sensor.available is False


def test_normalize_epoch_overflow_returns_none() -> None:
    """_normalize_epoch should return None on OverflowError."""
    # A huge integer will cause OverflowError in datetime.fromtimestamp
    result = _normalize_epoch(2**63)
    assert result is None
