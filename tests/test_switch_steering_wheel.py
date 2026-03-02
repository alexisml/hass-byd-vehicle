"""Unit tests for BydSteeringWheelHeatSwitch."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd.models.hvac import HvacOverallStatus, HvacStatus
from pybyd.models.realtime import StearingWheelHeat

from custom_components.byd_vehicle.switch import BydSteeringWheelHeatSwitch


def _make_coordinator(vin: str, realtime=None, hvac=None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.last_update_success = True
    data: dict = {"vehicles": {vin: MagicMock()}}
    if realtime is not None:
        data["realtime"] = {vin: realtime}
    if hvac is not None:
        data["hvac"] = {vin: hvac}
    coordinator.data = data
    coordinator.hvac_command_pending = False
    return coordinator


def _make_steering_wheel_switch(realtime=None, hvac=None) -> BydSteeringWheelHeatSwitch:
    vin = "TESTVIN123"
    coordinator = _make_coordinator(vin, realtime=realtime, hvac=hvac)
    entity = object.__new__(BydSteeringWheelHeatSwitch)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._api = AsyncMock()
    entity._api.async_call = AsyncMock()
    entity._attr_unique_id = f"{vin}_switch_steering_wheel_heat"
    entity._command_pending = False
    entity._commanded_at = None
    entity._last_state = None
    entity.async_write_ha_state = MagicMock()
    return entity


def _fake_coordinator_init(self, coordinator, **_):
    """Minimal stand-in for CoordinatorEntity.__init__."""
    self.coordinator = coordinator


def test_steering_wheel_is_on_vehicle_off() -> None:
    rt = types.SimpleNamespace(is_vehicle_on=False, is_steering_wheel_heating=None)
    entity = _make_steering_wheel_switch(realtime=rt)
    assert entity.is_on is False


def test_steering_wheel_is_on_hvac_true() -> None:
    rt = types.SimpleNamespace(is_vehicle_on=True, is_steering_wheel_heating=None)
    hvac = HvacStatus(
        status=HvacOverallStatus.ON,
        steeringWheelHeatState=StearingWheelHeat.ON,
    )
    entity = _make_steering_wheel_switch(realtime=rt, hvac=hvac)
    assert entity.is_on is True


def test_steering_wheel_is_on_realtime_fallback() -> None:
    rt = types.SimpleNamespace(is_vehicle_on=True, is_steering_wheel_heating=True)
    entity = _make_steering_wheel_switch(realtime=rt)
    assert entity.is_on is True


def test_steering_wheel_is_on_command_pending() -> None:
    entity = _make_steering_wheel_switch()
    entity._command_pending = True
    entity._last_state = True
    assert entity.is_on is True


def test_steering_wheel_is_on_hvac_none_val_realtime_none_falls_back() -> None:
    """When hvac and realtime return None, fall back to _last_state."""
    hvac = HvacStatus()  # is_steering_wheel_heating=None
    rt = types.SimpleNamespace(is_vehicle_on=True, is_steering_wheel_heating=None)
    entity = _make_steering_wheel_switch(realtime=rt, hvac=hvac)
    entity._last_state = True
    assert entity.is_on is True


def test_steering_wheel_assumed_state_hvac_has_state() -> None:
    hvac = HvacStatus(
        status=HvacOverallStatus.ON,
        steeringWheelHeatState=StearingWheelHeat.ON,
    )
    entity = _make_steering_wheel_switch(hvac=hvac)
    assert entity.assumed_state is False


def test_steering_wheel_assumed_state_no_hvac_realtime_has_state() -> None:
    rt = types.SimpleNamespace(is_steering_wheel_heating=True)
    entity = _make_steering_wheel_switch(realtime=rt)
    assert entity.assumed_state is False


def test_steering_wheel_assumed_state_no_data() -> None:
    entity = _make_steering_wheel_switch()
    assert entity.assumed_state is True


def test_steering_wheel_assumed_state_hvac_none_state() -> None:
    hvac = HvacStatus()
    entity = _make_steering_wheel_switch(hvac=hvac)
    assert entity.assumed_state is True


def test_steering_wheel_is_command_confirmed_no_last_state() -> None:
    entity = _make_steering_wheel_switch()
    entity._last_state = None
    assert entity._is_command_confirmed() is True


def test_steering_wheel_is_command_confirmed_hvac_matches() -> None:
    hvac = HvacStatus(
        status=HvacOverallStatus.ON,
        steeringWheelHeatState=StearingWheelHeat.ON,
    )
    entity = _make_steering_wheel_switch(hvac=hvac)
    entity._last_state = True
    assert entity._is_command_confirmed() is True


def test_steering_wheel_is_command_confirmed_hvac_mismatch() -> None:
    hvac = HvacStatus(
        status=HvacOverallStatus.ON,
        steeringWheelHeatState=StearingWheelHeat.OFF,
    )
    entity = _make_steering_wheel_switch(hvac=hvac)
    entity._last_state = True
    assert entity._is_command_confirmed() is False


def test_steering_wheel_is_command_confirmed_realtime_fallback() -> None:
    rt = types.SimpleNamespace(is_steering_wheel_heating=False)
    entity = _make_steering_wheel_switch(realtime=rt)
    entity._last_state = True
    assert entity._is_command_confirmed() is False


def test_steering_wheel_is_command_confirmed_no_data() -> None:
    entity = _make_steering_wheel_switch()
    entity._last_state = True
    assert entity._is_command_confirmed() is False


@pytest.mark.asyncio
async def test_steering_wheel_turn_on_sets_state() -> None:
    entity = _make_steering_wheel_switch()
    await entity.async_turn_on()
    assert entity._last_state is True
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_steering_wheel_turn_off_sets_state() -> None:
    entity = _make_steering_wheel_switch()
    await entity.async_turn_off()
    assert entity._last_state is False
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_steering_wheel_set_heat_executes_api_call() -> None:
    """Cover switch.py line 343: inner _call closure in _set_steering_wheel_heat."""
    entity = _make_steering_wheel_switch()
    client = AsyncMock()
    client.set_seat_climate = AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = AsyncMock(side_effect=execute_call)
    await entity.async_turn_on()
    client.set_seat_climate.assert_called_once()


def test_steering_wheel_heat_switch_init() -> None:
    """Cover switch.py lines 280-285: BydSteeringWheelHeatSwitch.__init__."""
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    coordinator = MagicMock()
    api = MagicMock()
    vin = "TESTVIN123"
    vehicle = MagicMock()

    with patch.object(CoordinatorEntity, "__init__", new=_fake_coordinator_init):
        sw = BydSteeringWheelHeatSwitch(coordinator, api, vin, vehicle)

    assert sw._api is api
    assert sw._vin == vin
    assert sw._vehicle is vehicle
    assert sw._attr_unique_id == f"{vin}_switch_steering_wheel_heat"
    assert sw._last_state is None
