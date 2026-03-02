"""Unit tests for switch module."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd.models.hvac import HvacOverallStatus, HvacStatus
from pybyd.models.realtime import StearingWheelHeat

from custom_components.byd_vehicle import switch
from custom_components.byd_vehicle.switch import (
    BydBatteryHeatSwitch,
    BydCarOnSwitch,
    BydDisablePollingSwitch,
    BydSteeringWheelHeatSwitch,
)


def test_switch_module_importable() -> None:
    assert hasattr(switch, "BydBatteryHeatSwitch")
    assert hasattr(switch, "BydCarOnSwitch")
    assert hasattr(switch, "BydDisablePollingSwitch")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_battery_heat_switch(realtime=None) -> BydBatteryHeatSwitch:
    vin = "TESTVIN123"
    coordinator = _make_coordinator(vin, realtime=realtime)
    entity = object.__new__(BydBatteryHeatSwitch)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._api = AsyncMock()
    entity._api.async_call = AsyncMock()
    entity._attr_unique_id = f"{vin}_switch_battery_heat"
    entity._command_pending = False
    entity._commanded_at = None
    entity._last_state = None
    entity.async_write_ha_state = MagicMock()
    return entity


def _make_car_on_switch(realtime=None, hvac=None) -> BydCarOnSwitch:
    vin = "TESTVIN123"
    coordinator = _make_coordinator(vin, realtime=realtime, hvac=hvac)
    entity = object.__new__(BydCarOnSwitch)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._api = AsyncMock()
    entity._api.async_call = AsyncMock()
    entity._attr_unique_id = f"{vin}_switch_car_on"
    entity._command_pending = False
    entity._commanded_at = None
    entity._last_state = None
    entity.async_write_ha_state = MagicMock()
    return entity


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


def _make_disable_polling_switch(gps_coordinator=None) -> BydDisablePollingSwitch:
    vin = "TESTVIN123"
    coordinator = _make_coordinator(vin)
    entity = object.__new__(BydDisablePollingSwitch)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._gps_coordinator = gps_coordinator
    entity._attr_unique_id = f"{vin}_switch_disable_polling"
    entity._command_pending = False
    entity._commanded_at = None
    entity._disabled = False
    entity.async_write_ha_state = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# BydBatteryHeatSwitch tests
# ---------------------------------------------------------------------------


def test_battery_heat_is_on_realtime_true() -> None:
    rt = types.SimpleNamespace(is_battery_heating=True, battery_heat_state=1)
    entity = _make_battery_heat_switch(realtime=rt)
    assert entity.is_on is True


def test_battery_heat_is_on_realtime_false() -> None:
    rt = types.SimpleNamespace(is_battery_heating=False, battery_heat_state=None)
    entity = _make_battery_heat_switch(realtime=rt)
    assert entity.is_on is False


def test_battery_heat_is_on_no_realtime_falls_back() -> None:
    entity = _make_battery_heat_switch(realtime=None)
    entity._last_state = True
    assert entity.is_on is True


def test_battery_heat_is_on_command_pending_returns_last() -> None:
    rt = types.SimpleNamespace(is_battery_heating=False, battery_heat_state=None)
    entity = _make_battery_heat_switch(realtime=rt)
    entity._command_pending = True
    entity._last_state = True
    assert entity.is_on is True


def test_battery_heat_assumed_state_no_realtime() -> None:
    entity = _make_battery_heat_switch(realtime=None)
    assert entity.assumed_state is True


def test_battery_heat_assumed_state_realtime_no_state() -> None:
    rt = types.SimpleNamespace(battery_heat_state=None)
    entity = _make_battery_heat_switch(realtime=rt)
    assert entity.assumed_state is True


def test_battery_heat_assumed_state_realtime_has_state() -> None:
    rt = types.SimpleNamespace(battery_heat_state=1)
    entity = _make_battery_heat_switch(realtime=rt)
    assert entity.assumed_state is False


def test_battery_heat_is_command_confirmed_no_last_state() -> None:
    entity = _make_battery_heat_switch()
    entity._last_state = None
    assert entity._is_command_confirmed() is True


def test_battery_heat_is_command_confirmed_no_realtime() -> None:
    entity = _make_battery_heat_switch(realtime=None)
    entity._last_state = True
    assert entity._is_command_confirmed() is False


def test_battery_heat_is_command_confirmed_matches() -> None:
    rt = types.SimpleNamespace(is_battery_heating=True, battery_heat_state=1)
    entity = _make_battery_heat_switch(realtime=rt)
    entity._last_state = True
    assert entity._is_command_confirmed() is True


def test_battery_heat_is_command_confirmed_mismatch() -> None:
    rt = types.SimpleNamespace(is_battery_heating=False, battery_heat_state=0)
    entity = _make_battery_heat_switch(realtime=rt)
    entity._last_state = True
    assert entity._is_command_confirmed() is False


def test_battery_heat_is_command_confirmed_heating_none() -> None:
    rt = types.SimpleNamespace(is_battery_heating=None, battery_heat_state=None)
    entity = _make_battery_heat_switch(realtime=rt)
    entity._last_state = True
    assert entity._is_command_confirmed() is False


# ---------------------------------------------------------------------------
# BydCarOnSwitch tests
# ---------------------------------------------------------------------------


def test_car_on_is_on_hvac_off() -> None:
    hvac = HvacStatus()
    entity = _make_car_on_switch(hvac=hvac)
    assert entity.is_on is False


def test_car_on_is_on_hvac_on_vehicle_on() -> None:
    hvac = HvacStatus(status=HvacOverallStatus.ON)
    rt = types.SimpleNamespace(is_vehicle_on=True)
    entity = _make_car_on_switch(realtime=rt, hvac=hvac)
    assert entity.is_on is True


def test_car_on_is_on_hvac_on_vehicle_off_no_hvac_cmd() -> None:
    hvac = HvacStatus(status=HvacOverallStatus.ON)
    rt = types.SimpleNamespace(is_vehicle_on=False)
    entity = _make_car_on_switch(realtime=rt, hvac=hvac)
    entity.coordinator.hvac_command_pending = False
    assert entity.is_on is False


def test_car_on_is_on_no_hvac_vehicle_off() -> None:
    rt = types.SimpleNamespace(is_vehicle_on=False)
    entity = _make_car_on_switch(realtime=rt)
    assert entity.is_on is False


def test_car_on_is_on_no_hvac_vehicle_on_falls_back() -> None:
    rt = types.SimpleNamespace(is_vehicle_on=True)
    entity = _make_car_on_switch(realtime=rt)
    entity._last_state = True
    assert entity.is_on is True


def test_car_on_is_on_command_pending() -> None:
    entity = _make_car_on_switch()
    entity._command_pending = True
    entity._last_state = True
    assert entity.is_on is True


def test_car_on_assumed_state_no_hvac() -> None:
    entity = _make_car_on_switch(hvac=None)
    assert entity.assumed_state is True


def test_car_on_assumed_state_with_hvac() -> None:
    hvac = HvacStatus()
    entity = _make_car_on_switch(hvac=hvac)
    assert entity.assumed_state is False


def test_car_on_extra_state_attributes() -> None:
    entity = _make_car_on_switch()
    attrs = entity.extra_state_attributes
    assert attrs["target_temperature_c"] == 21
    assert "vin" in attrs


# ---------------------------------------------------------------------------
# BydSteeringWheelHeatSwitch tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# BydDisablePollingSwitch tests
# ---------------------------------------------------------------------------


def test_disable_polling_is_on_false_by_default() -> None:
    entity = _make_disable_polling_switch()
    assert entity.is_on is False


def test_disable_polling_is_on_true_when_disabled() -> None:
    entity = _make_disable_polling_switch()
    entity._disabled = True
    assert entity.is_on is True


def test_disable_polling_available_true_when_vehicle_present() -> None:
    entity = _make_disable_polling_switch()
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is True


def test_disable_polling_available_false_when_vehicle_absent() -> None:
    entity = _make_disable_polling_switch()
    entity.coordinator.data = {"vehicles": {}}
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is False


def test_disable_polling_apply_enables_coordinator() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    gps = MagicMock()
    gps.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch(gps_coordinator=gps)
    entity.coordinator = coordinator
    entity._disabled = False
    entity._apply()
    coordinator.set_polling_enabled.assert_called_once_with(True)
    gps.set_polling_enabled.assert_called_once_with(True)


def test_disable_polling_apply_disables_coordinator() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch(gps_coordinator=None)
    entity.coordinator = coordinator
    entity._disabled = True
    entity._apply()
    coordinator.set_polling_enabled.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# BydBatteryHeatSwitch async methods
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.asyncio
async def test_battery_heat_turn_on_sets_state() -> None:
    entity = _make_battery_heat_switch()
    await entity.async_turn_on()
    assert entity._last_state is True
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_battery_heat_turn_off_sets_state() -> None:
    entity = _make_battery_heat_switch()
    await entity.async_turn_off()
    assert entity._last_state is False
    assert entity._command_pending is True


# ---------------------------------------------------------------------------
# BydCarOnSwitch _is_command_confirmed and async methods
# ---------------------------------------------------------------------------


def test_car_on_is_command_confirmed_no_hvac() -> None:
    entity = _make_car_on_switch()
    assert entity._is_command_confirmed() is False


def test_car_on_is_command_confirmed_ac_mismatch() -> None:
    hvac = HvacStatus()  # is_ac_on=False
    entity = _make_car_on_switch(hvac=hvac)
    entity._last_state = True  # expected on
    assert entity._is_command_confirmed() is False


def test_car_on_is_command_confirmed_on_vehicle_off() -> None:
    hvac = HvacStatus(status=HvacOverallStatus.ON)
    rt = types.SimpleNamespace(is_vehicle_on=False)
    entity = _make_car_on_switch(realtime=rt, hvac=hvac)
    entity._last_state = True
    assert entity._is_command_confirmed() is False


def test_car_on_is_command_confirmed_off_matches() -> None:
    hvac = HvacStatus()  # is_ac_on=False
    entity = _make_car_on_switch(hvac=hvac)
    entity._last_state = False
    assert entity._is_command_confirmed() is True


def test_car_on_is_command_confirmed_on_vehicle_on() -> None:
    hvac = HvacStatus(status=HvacOverallStatus.ON)
    rt = types.SimpleNamespace(is_vehicle_on=True)
    entity = _make_car_on_switch(realtime=rt, hvac=hvac)
    entity._last_state = True
    assert entity._is_command_confirmed() is True


@pytest.mark.asyncio
async def test_car_on_turn_on_sets_state() -> None:
    entity = _make_car_on_switch()
    entity.coordinator.apply_optimistic_hvac = MagicMock()
    entity._schedule_delayed_refresh = MagicMock()
    await entity.async_turn_on()
    assert entity._last_state is True
    assert entity._command_pending is True
    entity.coordinator.apply_optimistic_hvac.assert_called_once()
    entity._schedule_delayed_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_car_on_turn_off_sets_state() -> None:
    entity = _make_car_on_switch()
    entity.coordinator.apply_optimistic_hvac = MagicMock()
    entity._schedule_delayed_refresh = MagicMock()
    await entity.async_turn_off()
    assert entity._last_state is False
    assert entity._command_pending is True
    entity.coordinator.apply_optimistic_hvac.assert_called_once()
    entity._schedule_delayed_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# BydSteeringWheelHeatSwitch: fallback paths in is_on
# ---------------------------------------------------------------------------


def test_steering_wheel_is_on_hvac_none_val_realtime_none_falls_back() -> None:
    """When hvac and realtime return None, fall back to _last_state."""
    hvac = HvacStatus()  # is_steering_wheel_heating=None
    rt = types.SimpleNamespace(is_vehicle_on=True, is_steering_wheel_heating=None)
    entity = _make_steering_wheel_switch(realtime=rt, hvac=hvac)
    entity._last_state = True
    assert entity.is_on is True


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


# ---------------------------------------------------------------------------
# BydDisablePollingSwitch: async turn on/off
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disable_polling_turn_on_disables() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch()
    entity.coordinator = coordinator
    await entity.async_turn_on()
    assert entity._disabled is True
    coordinator.set_polling_enabled.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_disable_polling_turn_off_enables() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch()
    entity.coordinator = coordinator
    entity._disabled = True
    await entity.async_turn_off()
    assert entity._disabled is False
    coordinator.set_polling_enabled.assert_called_once_with(True)
