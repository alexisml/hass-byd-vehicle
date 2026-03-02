"""Unit tests for BydClimate async command methods and setup entry."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock as _AsyncMock
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.climate.const import HVACMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.byd_vehicle.climate import BydClimate


def _make_climate(realtime=None, hvac=None) -> BydClimate:
    """Create a BydClimate bypassing __init__."""

    vin = "TESTVIN123"
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.hvac_command_pending = False
    data: dict = {"vehicles": {vin: MagicMock()}}
    if realtime is not None:
        data["realtime"] = {vin: realtime}
    if hvac is not None:
        data["hvac"] = {vin: hvac}
    coordinator.data = data

    entity = object.__new__(BydClimate)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._api = MagicMock()
    entity._api.async_call = _AsyncMock()
    entity._attr_unique_id = f"{vin}_climate"
    entity._command_pending = False
    entity._commanded_at = None
    entity._last_mode = HVACMode.OFF
    entity._last_command = None
    entity._pending_target_temp = None
    entity._climate_duration_code = 1
    entity.async_write_ha_state = MagicMock()
    return entity


def _fake_coordinator_init(self, coordinator, **_):
    """Minimal stand-in for CoordinatorEntity.__init__."""
    self.coordinator = coordinator


# ---------------------------------------------------------------------------
# Async methods
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_hvac_mode_off_clears_optimistic() -> None:
    entity = _make_climate()
    entity.coordinator.apply_optimistic_hvac = MagicMock()
    entity._schedule_delayed_refresh = MagicMock()
    await entity.async_set_hvac_mode(HVACMode.OFF)
    assert entity._last_mode is HVACMode.OFF
    assert entity._command_pending is True
    entity.coordinator.apply_optimistic_hvac.assert_called_once()
    entity._schedule_delayed_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_set_hvac_mode_on_sets_state() -> None:
    entity = _make_climate()
    entity.coordinator.apply_optimistic_hvac = MagicMock()
    entity._schedule_delayed_refresh = MagicMock()
    await entity.async_set_hvac_mode(HVACMode.HEAT_COOL)
    assert entity._last_mode is HVACMode.HEAT_COOL
    assert entity._command_pending is True
    entity.coordinator.apply_optimistic_hvac.assert_called_once()


@pytest.mark.asyncio
async def test_set_temperature_no_temp_does_nothing() -> None:
    entity = _make_climate()
    await entity.async_set_temperature()
    assert entity._pending_target_temp is None


@pytest.mark.asyncio
async def test_set_temperature_while_climate_off_sets_pending() -> None:
    entity = _make_climate()
    entity._last_mode = HVACMode.OFF
    await entity.async_set_temperature(temperature=23.0)
    assert entity._pending_target_temp == 23.0
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_set_temperature_while_climate_on_executes_command() -> None:
    from pybyd.models.hvac import HvacOverallStatus, HvacStatus

    hvac = HvacStatus(status=HvacOverallStatus.ON)
    rt = types.SimpleNamespace(is_vehicle_on=True)
    entity = _make_climate(realtime=rt, hvac=hvac)
    await entity.async_set_temperature(temperature=25.0)
    assert entity._pending_target_temp == 25.0
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_set_preset_mode_max_heat() -> None:
    entity = _make_climate()
    await entity.async_set_preset_mode("max_heat")
    assert entity._pending_target_temp == float(BydClimate._TEMP_MAX_C)
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_set_preset_mode_max_cool() -> None:
    entity = _make_climate()
    await entity.async_set_preset_mode("max_cool")
    assert entity._pending_target_temp == float(BydClimate._TEMP_MIN_C)
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_set_preset_mode_invalid_raises() -> None:
    from homeassistant.exceptions import HomeAssistantError

    entity = _make_climate()
    with pytest.raises(HomeAssistantError):
        await entity.async_set_preset_mode("invalid_preset")


# ---------------------------------------------------------------------------
# async_setup_entry (lines 33-49)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_climate_async_setup_entry_no_vehicles() -> None:
    """Cover lines 33-49: async_setup_entry skips when vehicle is None."""
    from custom_components.byd_vehicle.climate import async_setup_entry
    from custom_components.byd_vehicle.const import DOMAIN

    vin = "TESTVIN123"
    coordinator = MagicMock()
    coordinator.data = {"vehicles": {}}  # vehicle is None → skip

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {vin: coordinator},
                "api": MagicMock(),
            }
        }
    }
    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.options = {}
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([])


@pytest.mark.asyncio
async def test_climate_async_setup_entry_creates_entity() -> None:
    """Cover lines 33-49 + 84-92: entity created and __init__ runs."""
    from custom_components.byd_vehicle.climate import BydClimate, async_setup_entry
    from custom_components.byd_vehicle.const import DOMAIN

    vin = "TESTVIN123"
    vehicle_mock = MagicMock()
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"vehicles": {vin: vehicle_mock}}

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {vin: coordinator},
                "api": MagicMock(),
            }
        }
    }
    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.options = {}
    async_add_entities = MagicMock()

    with patch.object(BydClimate, "__init__", return_value=None):
        await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], BydClimate)


# ---------------------------------------------------------------------------
# BydClimate.__init__ (lines 84-92)
# ---------------------------------------------------------------------------


def test_climate_init() -> None:
    """Cover climate.py lines 84-92: BydClimate.__init__."""

    coordinator = MagicMock()
    api = MagicMock()
    vin = "TESTVIN123"
    vehicle = MagicMock()
    climate_duration = 15

    with patch.object(CoordinatorEntity, "__init__", new=_fake_coordinator_init):
        climate = BydClimate(coordinator, api, vin, vehicle, climate_duration)

    assert climate._api is api
    assert climate._vin == vin
    assert climate._vehicle is vehicle
    assert climate._attr_unique_id == f"{vin}_climate"
    assert climate._last_mode is HVACMode.OFF
    assert climate._last_command is None
    assert climate._pending_target_temp is None


# ---------------------------------------------------------------------------
# _schedule_delayed_refresh inner _delayed closure (lines 298-302)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_climate_delayed_refresh_closure_runs() -> None:
    """Cover climate.py lines 298-302: inner _delayed coroutine body."""
    from unittest.mock import patch as _patch

    entity = _make_climate()
    entity.hass = MagicMock()
    entity.coordinator.async_force_refresh = _AsyncMock()

    captured_coro = None

    def capture_task(coro):
        nonlocal captured_coro
        captured_coro = coro

    entity.hass.async_create_task = capture_task

    sleep_mock = _AsyncMock()
    with _patch("custom_components.byd_vehicle.climate.asyncio.sleep", new=sleep_mock):
        entity._schedule_delayed_refresh()
        assert captured_coro is not None
        await captured_coro

    entity.coordinator.async_force_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# Inner _call closure bodies (lines 175-177, 220, 259)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_set_hvac_mode_off_call_invokes_stop_climate() -> None:
    """Cover climate.py line 176: _call body calls stop_climate when mode=OFF."""
    entity = _make_climate()
    entity.hass = MagicMock()
    client = MagicMock()
    client.stop_climate = _AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = _AsyncMock(side_effect=execute_call)
    entity.async_write_ha_state = MagicMock()
    await entity.async_set_hvac_mode(HVACMode.OFF)
    client.stop_climate.assert_called_once_with(entity._vin)


@pytest.mark.asyncio
async def test_async_set_hvac_mode_on_call_invokes_start_climate() -> None:
    """Cover climate.py line 177: _call body calls start_climate when mode=HEAT_COOL."""
    entity = _make_climate()
    entity.hass = MagicMock()
    client = MagicMock()
    client.start_climate = _AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = _AsyncMock(side_effect=execute_call)
    entity.async_write_ha_state = MagicMock()
    await entity.async_set_hvac_mode(HVACMode.HEAT_COOL)
    client.start_climate.assert_called_once()


@pytest.mark.asyncio
async def test_async_set_temperature_when_on_invokes_start_climate() -> None:
    """Cover climate.py line 220: _call closure invoked when climate is on."""
    from homeassistant.const import ATTR_TEMPERATURE

    entity = _make_climate()
    # Simulate climate currently on
    entity._command_pending = True
    entity._last_mode = HVACMode.HEAT_COOL

    client = MagicMock()
    client.start_climate = _AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = _AsyncMock(side_effect=execute_call)
    entity.async_write_ha_state = MagicMock()
    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})
    client.start_climate.assert_called_once()


@pytest.mark.asyncio
async def test_async_set_preset_mode_call_invokes_start_climate() -> None:
    """Cover climate.py line 259: _call closure body in async_set_preset_mode."""
    entity = _make_climate()
    client = MagicMock()
    client.start_climate = _AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):
        return await func(client)

    entity._api.async_call = _AsyncMock(side_effect=execute_call)
    entity.async_write_ha_state = MagicMock()
    await entity.async_set_preset_mode("max_heat")
    client.start_climate.assert_called_once()
