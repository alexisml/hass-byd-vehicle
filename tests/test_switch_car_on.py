"""Unit tests for BydCarOnSwitch."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd.models.hvac import HvacOverallStatus, HvacStatus

from custom_components.byd_vehicle.switch import BydCarOnSwitch


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


def _fake_coordinator_init(self, coordinator, **_):
    """Minimal stand-in for CoordinatorEntity.__init__."""
    self.coordinator = coordinator


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


@pytest.mark.asyncio
async def test_car_on_turn_on_executes_api_call() -> None:
    """Cover switch.py line 190: inner _call closure in BydCarOnSwitch.async_turn_on."""
    entity = _make_car_on_switch()
    entity.coordinator.apply_optimistic_hvac = MagicMock()
    entity._schedule_delayed_refresh = MagicMock()
    client = AsyncMock()
    client.start_climate = AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = AsyncMock(side_effect=execute_call)
    await entity.async_turn_on()
    client.start_climate.assert_called_once()


@pytest.mark.asyncio
async def test_car_on_turn_off_executes_api_call() -> None:
    """Cover switch.py line 217: inner _call closure in BydCarOnSwitch.async_turn_off."""
    entity = _make_car_on_switch()
    entity.coordinator.apply_optimistic_hvac = MagicMock()
    entity._schedule_delayed_refresh = MagicMock()
    client = AsyncMock()
    client.stop_climate = AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = AsyncMock(side_effect=execute_call)
    await entity.async_turn_off()
    client.stop_climate.assert_called_once_with(entity._vin)


def test_car_on_switch_init() -> None:
    """Cover switch.py lines 155-160: BydCarOnSwitch.__init__."""
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    coordinator = MagicMock()
    api = MagicMock()
    vin = "TESTVIN123"
    vehicle = MagicMock()

    with patch.object(CoordinatorEntity, "__init__", new=_fake_coordinator_init):
        sw = BydCarOnSwitch(coordinator, api, vin, vehicle)

    assert sw._api is api
    assert sw._vin == vin
    assert sw._vehicle is vehicle
    assert sw._attr_unique_id == f"{vin}_switch_car_on"
    assert sw._last_state is None


def test_schedule_delayed_refresh_creates_task() -> None:
    """Cover switch.py lines 253-257: _schedule_delayed_refresh."""
    entity = _make_car_on_switch()
    entity.hass = MagicMock()
    entity._schedule_delayed_refresh()
    entity.hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_car_on_switch_delayed_refresh_closure_runs() -> None:
    """Cover switch.py lines 254-255: inner _delayed coroutine body."""
    entity = _make_car_on_switch()
    entity.hass = MagicMock()
    entity.coordinator.async_force_refresh = AsyncMock()

    captured_coro = None

    def capture_task(coro):
        nonlocal captured_coro
        captured_coro = coro

    entity.hass.async_create_task = capture_task

    with patch("custom_components.byd_vehicle.switch.asyncio.sleep", new=AsyncMock()):
        entity._schedule_delayed_refresh()
        assert captured_coro is not None
        await captured_coro

    entity.coordinator.async_force_refresh.assert_called_once()
