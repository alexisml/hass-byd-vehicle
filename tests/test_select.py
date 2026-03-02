"""Unit tests for select module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd.models.realtime import SeatHeatVentState

from custom_components.byd_vehicle.select import (
    SEAT_CLIMATE_DESCRIPTIONS,
    SEAT_LEVEL_OPTIONS,
    BydSeatClimateSelect,
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


def test_seat_status_int_value_valid() -> None:
    # Pass an int that maps to a valid SeatHeatVentState with value > 0
    low_value = SeatHeatVentState.LOW.value
    result = _seat_status_to_option(low_value)
    assert result == "low"


def test_seat_status_invalid_int_returns_off() -> None:
    assert _seat_status_to_option(9999) == "off"


def test_seat_level_options_nonempty() -> None:
    assert isinstance(SEAT_LEVEL_OPTIONS, list)
    assert len(SEAT_LEVEL_OPTIONS) > 0


def test_seat_level_options_are_strings() -> None:
    for opt in SEAT_LEVEL_OPTIONS:
        assert isinstance(opt, str)


# ---------------------------------------------------------------------------
# BydSeatClimateSelect entity tests
# ---------------------------------------------------------------------------


def _make_select(hvac_val=None, realtime_val=None) -> BydSeatClimateSelect:
    """Create a BydSeatClimateSelect bypassing __init__."""
    from pybyd.models.hvac import HvacStatus

    vin = "TESTVIN123"
    desc = SEAT_CLIMATE_DESCRIPTIONS[0]  # driver_seat_heat
    coordinator = MagicMock()
    coordinator.last_update_success = True

    # Use real HvacStatus so isinstance() check in _get_hvac_status passes
    hvac = None
    if hvac_val is not None:
        hvac = HvacStatus(mainSeatHeatState=hvac_val)

    realtime = None
    if realtime_val is not None:
        realtime = MagicMock()
        setattr(realtime, desc.hvac_attr, realtime_val)

    data: dict = {
        "vehicles": {vin: MagicMock()},
        "hvac": {vin: hvac},
        "realtime": {vin: realtime},
    }
    coordinator.data = data

    entity = object.__new__(BydSeatClimateSelect)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity.entity_description = desc
    entity._api = MagicMock()
    entity._attr_unique_id = f"{vin}_select_{desc.key}"
    entity._attr_translation_key = desc.key
    entity._pending_value = None
    entity._command_pending = False
    entity._commanded_at = None
    entity.async_write_ha_state = MagicMock()
    return entity


def test_current_option_from_hvac() -> None:
    entity = _make_select(hvac_val=SeatHeatVentState.LOW)
    assert entity.current_option == "low"


def test_current_option_falls_back_to_realtime() -> None:
    entity = _make_select(hvac_val=None, realtime_val=SeatHeatVentState.HIGH)
    assert entity.current_option == "high"


def test_current_option_defaults_to_off_when_no_data() -> None:
    entity = _make_select(hvac_val=None, realtime_val=None)
    assert entity.current_option == "off"


def test_current_option_pending_returns_pending_value() -> None:
    entity = _make_select(hvac_val=SeatHeatVentState.LOW)
    entity._pending_value = "high"
    assert entity.current_option == "high"


def test_is_command_confirmed_no_pending() -> None:
    entity = _make_select()
    entity._pending_value = None
    assert entity._is_command_confirmed() is True


def test_is_command_confirmed_matches() -> None:
    entity = _make_select(hvac_val=SeatHeatVentState.LOW)
    entity._pending_value = "low"
    assert entity._is_command_confirmed() is True


def test_is_command_confirmed_mismatch() -> None:
    entity = _make_select(hvac_val=SeatHeatVentState.LOW)
    entity._pending_value = "high"
    assert entity._is_command_confirmed() is False


def test_handle_coordinator_update_clears_pending_when_confirmed() -> None:
    entity = _make_select(hvac_val=SeatHeatVentState.LOW)
    entity._pending_value = "low"
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()
    assert entity._pending_value is None


def test_handle_coordinator_update_keeps_pending_when_not_confirmed() -> None:
    entity = _make_select(hvac_val=SeatHeatVentState.LOW)
    entity._pending_value = "high"  # mismatch → not confirmed
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()
    assert entity._pending_value == "high"


def test_current_option_command_pending_no_pending_value() -> None:
    """Line 170: _command_pending=True and _pending_value=None."""
    entity = _make_select()
    entity._command_pending = True
    entity._pending_value = None
    result = entity.current_option
    assert result is None


def test_is_command_confirmed_realtime_fallback_matches() -> None:
    """Line 224: hvac attr is None, falls back to realtime."""
    # hvac has no mainSeatHeatState → returns None for hvac_attr
    entity = _make_select(hvac_val=None, realtime_val=SeatHeatVentState.LOW)
    entity._pending_value = "low"
    assert entity._is_command_confirmed() is True


@pytest.mark.asyncio
async def test_async_select_option_valid() -> None:
    """Test async_select_option with a valid option."""
    entity = _make_select()
    entity._api = MagicMock()
    from unittest.mock import AsyncMock

    entity._api.async_call = AsyncMock()
    await entity.async_select_option("low")
    assert entity._pending_value == "low"
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_async_select_option_invalid_ignores() -> None:
    """Test async_select_option with an invalid option is silently ignored."""
    entity = _make_select()
    entity._api = MagicMock()
    from unittest.mock import AsyncMock

    entity._api.async_call = AsyncMock()
    await entity.async_select_option("invalid_option")
    assert entity._pending_value is None
