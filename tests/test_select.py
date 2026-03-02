"""Unit tests for select pure helpers."""

from __future__ import annotations

from pybyd.models.realtime import SeatHeatVentState

from custom_components.byd_vehicle.select import (
    SEAT_LEVEL_OPTIONS,
    _seat_status_to_option,
)


def test_seat_status_none_returns_off() -> None:
    assert _seat_status_to_option(None) == "off"


def test_seat_status_no_data_returns_off() -> None:
    assert _seat_status_to_option(SeatHeatVentState.NO_DATA) == "off"


def test_seat_status_positive_returns_name_lower() -> None:
    # LOW has value > 0; name is "LOW" → expect "low"
    result = _seat_status_to_option(SeatHeatVentState.LOW)
    assert result == "low"


def test_seat_status_off_state() -> None:
    # OFF has value 1 (> 0) so it returns the name in lowercase
    result = _seat_status_to_option(SeatHeatVentState.OFF)
    assert result == "off"


def test_seat_level_options_nonempty() -> None:
    assert isinstance(SEAT_LEVEL_OPTIONS, list)
    assert len(SEAT_LEVEL_OPTIONS) > 0


def test_seat_level_options_are_strings() -> None:
    for opt in SEAT_LEVEL_OPTIONS:
        assert isinstance(opt, str)
