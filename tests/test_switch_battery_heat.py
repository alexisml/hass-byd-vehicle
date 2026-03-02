"""Unit tests for BydBatteryHeatSwitch."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.byd_vehicle import switch
from custom_components.byd_vehicle.switch import BydBatteryHeatSwitch


def test_switch_module_importable() -> None:
    assert hasattr(switch, "BydBatteryHeatSwitch")
    assert hasattr(switch, "BydCarOnSwitch")
    assert hasattr(switch, "BydDisablePollingSwitch")


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


def _fake_coordinator_init(self, coordinator, **_):
    """Minimal stand-in for CoordinatorEntity.__init__."""
    self.coordinator = coordinator


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


@pytest.mark.asyncio
async def test_battery_heat_turn_on_executes_api_call() -> None:
    """Cover switch.py line 110: inner _call closure in async_turn_on."""
    entity = _make_battery_heat_switch()
    client = AsyncMock()
    client.set_battery_heat = AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):  # **kwargs absorbs vin= and command=
        return await func(client)

    entity._api.async_call = AsyncMock(side_effect=execute_call)
    await entity.async_turn_on()
    client.set_battery_heat.assert_called_once()


@pytest.mark.asyncio
async def test_battery_heat_turn_off_executes_api_call() -> None:
    """Cover switch.py line 126: inner _call closure in async_turn_off."""
    entity = _make_battery_heat_switch()
    client = AsyncMock()
    client.set_battery_heat = AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = AsyncMock(side_effect=execute_call)
    await entity.async_turn_off()
    client.set_battery_heat.assert_called_once()


def test_battery_heat_switch_init() -> None:
    """Cover switch.py lines 67-72: BydBatteryHeatSwitch.__init__."""

    coordinator = MagicMock()
    api = MagicMock()
    vin = "TESTVIN123"
    vehicle = MagicMock()

    with patch.object(CoordinatorEntity, "__init__", new=_fake_coordinator_init):
        sw = BydBatteryHeatSwitch(coordinator, api, vin, vehicle)

    assert sw._api is api
    assert sw._vin == vin
    assert sw._vehicle is vehicle
    assert sw._attr_unique_id == f"{vin}_switch_battery_heat"
    assert sw._last_state is None
