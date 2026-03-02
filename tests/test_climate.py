"""Unit tests for BydClimate static helpers and entity properties."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock as _AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.climate.const import HVACMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd.models.hvac import HvacOverallStatus, HvacStatus

from custom_components.byd_vehicle.climate import BydClimate


class TestClampTemp:
    """Tests for BydClimate._clamp_temp."""

    def test_none_returns_none(self) -> None:
        assert BydClimate._clamp_temp(None) is None

    def test_in_range_unchanged(self) -> None:
        assert BydClimate._clamp_temp(23.0) == 23.0

    def test_below_min_returns_none(self) -> None:
        assert BydClimate._clamp_temp(14.0) is None

    def test_above_max_returns_none(self) -> None:
        assert BydClimate._clamp_temp(32.0) is None

    def test_at_min_boundary(self) -> None:
        assert BydClimate._clamp_temp(15) == 15.0

    def test_at_max_boundary(self) -> None:
        assert BydClimate._clamp_temp(31) == 31.0

    def test_returns_float(self) -> None:
        result = BydClimate._clamp_temp(20)
        assert isinstance(result, float)


class TestPresetFromTemp:
    """Tests for BydClimate._preset_from_temp."""

    def test_none_returns_none(self) -> None:
        assert BydClimate._preset_from_temp(None) is None

    def test_max_temp_returns_max_heat(self) -> None:
        assert BydClimate._preset_from_temp(31.0) == "max_heat"

    def test_min_temp_returns_max_cool(self) -> None:
        assert BydClimate._preset_from_temp(15.0) == "max_cool"

    def test_mid_temp_returns_none(self) -> None:
        assert BydClimate._preset_from_temp(21.0) is None

    def test_rounds_to_max_heat(self) -> None:
        # 30.6 rounds to 31 (>= _TEMP_MAX_C) → "max_heat"
        assert BydClimate._preset_from_temp(30.6) == "max_heat"

    def test_rounds_to_max_cool(self) -> None:
        assert BydClimate._preset_from_temp(15.4) == "max_cool"


# ---------------------------------------------------------------------------
# BydClimate entity helpers
# ---------------------------------------------------------------------------


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


class TestHvacMode:
    """Tests for BydClimate.hvac_mode."""

    def test_hvac_mode_command_pending_returns_last_mode(self) -> None:
        entity = _make_climate()
        entity._command_pending = True
        entity._last_mode = HVACMode.HEAT_COOL
        assert entity.hvac_mode is HVACMode.HEAT_COOL

    def test_hvac_mode_hvac_off(self) -> None:
        hvac = HvacStatus()
        entity = _make_climate(hvac=hvac)
        assert entity.hvac_mode is HVACMode.OFF

    def test_hvac_mode_hvac_on_vehicle_on(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON)
        rt = types.SimpleNamespace(is_vehicle_on=True)
        entity = _make_climate(realtime=rt, hvac=hvac)
        assert entity.hvac_mode is HVACMode.HEAT_COOL

    def test_hvac_mode_hvac_on_vehicle_off_no_cmd(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON)
        rt = types.SimpleNamespace(is_vehicle_on=False)
        entity = _make_climate(realtime=rt, hvac=hvac)
        entity.coordinator.hvac_command_pending = False
        assert entity.hvac_mode is HVACMode.OFF

    def test_hvac_mode_no_hvac_vehicle_off(self) -> None:
        rt = types.SimpleNamespace(is_vehicle_on=False)
        entity = _make_climate(realtime=rt)
        assert entity.hvac_mode is HVACMode.OFF

    def test_hvac_mode_no_hvac_vehicle_on_returns_last(self) -> None:
        rt = types.SimpleNamespace(is_vehicle_on=True)
        entity = _make_climate(realtime=rt)
        entity._last_mode = HVACMode.HEAT_COOL
        assert entity.hvac_mode is HVACMode.HEAT_COOL


class TestAssumedState:
    """Tests for BydClimate.assumed_state."""

    def test_assumed_when_command_pending(self) -> None:
        entity = _make_climate()
        entity._command_pending = True
        assert entity.assumed_state is True

    def test_assumed_when_no_hvac(self) -> None:
        entity = _make_climate()
        assert entity.assumed_state is True

    def test_not_assumed_when_hvac_present(self) -> None:
        hvac = HvacStatus()
        entity = _make_climate(hvac=hvac)
        assert entity.assumed_state is False


class TestCurrentTemperature:
    """Tests for BydClimate.current_temperature."""

    def test_from_hvac_when_available(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON, tempInCar=22.0)
        entity = _make_climate(hvac=hvac)
        assert entity.current_temperature == 22.0

    def test_falls_back_to_realtime(self) -> None:
        rt = types.SimpleNamespace(temp_in_car=20.0)
        entity = _make_climate(realtime=rt)
        assert entity.current_temperature == 20.0

    def test_returns_none_when_no_data(self) -> None:
        entity = _make_climate()
        assert entity.current_temperature is None


class TestTargetTemperature:
    """Tests for BydClimate.target_temperature."""

    def test_returns_pending_when_set(self) -> None:
        entity = _make_climate()
        entity._pending_target_temp = 25.0
        assert entity.target_temperature == 25.0

    def test_returns_hvac_value(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON, mainSettingTempNew=23.0)
        entity = _make_climate(hvac=hvac)
        assert entity.target_temperature == 23.0

    def test_returns_default_when_no_data(self) -> None:
        entity = _make_climate()
        assert entity.target_temperature == BydClimate._DEFAULT_TEMP_C


class TestPresetMode:
    """Tests for BydClimate.preset_mode."""

    def test_preset_none_when_hvac_off(self) -> None:
        hvac = HvacStatus()
        entity = _make_climate(hvac=hvac)
        assert entity.preset_mode is None

    def test_preset_max_heat_when_max_temp(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON, mainSettingTempNew=31.0)
        rt = types.SimpleNamespace(is_vehicle_on=True)
        entity = _make_climate(realtime=rt, hvac=hvac)
        assert entity.preset_mode == "max_heat"

    def test_preset_from_pending_temp(self) -> None:
        rt = types.SimpleNamespace(is_vehicle_on=True)
        entity = _make_climate(realtime=rt)
        entity._last_mode = HVACMode.HEAT_COOL
        entity._pending_target_temp = 31.0
        assert entity.preset_mode == "max_heat"

    def test_preset_none_when_mid_temp(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON, mainSettingTempNew=22.0)
        rt = types.SimpleNamespace(is_vehicle_on=True)
        entity = _make_climate(realtime=rt, hvac=hvac)
        assert entity.preset_mode is None


class TestIsCommandConfirmed:
    """Tests for BydClimate._is_command_confirmed."""

    def test_false_when_no_hvac(self) -> None:
        entity = _make_climate()
        assert entity._is_command_confirmed() is False

    def test_false_when_ac_state_mismatch(self) -> None:
        hvac = HvacStatus()
        entity = _make_climate(hvac=hvac)
        entity._last_mode = HVACMode.HEAT_COOL
        assert entity._is_command_confirmed() is False

    def test_false_when_on_but_vehicle_off(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON)
        rt = types.SimpleNamespace(is_vehicle_on=False)
        entity = _make_climate(realtime=rt, hvac=hvac)
        entity._last_mode = HVACMode.HEAT_COOL
        assert entity._is_command_confirmed() is False

    def test_true_when_off_matches(self) -> None:
        hvac = HvacStatus()
        entity = _make_climate(hvac=hvac)
        entity._last_mode = HVACMode.OFF
        assert entity._is_command_confirmed() is True

    def test_true_when_on_and_vehicle_on(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON)
        rt = types.SimpleNamespace(is_vehicle_on=True)
        entity = _make_climate(realtime=rt, hvac=hvac)
        entity._last_mode = HVACMode.HEAT_COOL
        assert entity._is_command_confirmed() is True


class TestHandleCoordinatorUpdate:
    """Tests for BydClimate._handle_coordinator_update."""

    def test_clears_pending_temp_when_no_command_pending(self) -> None:
        entity = _make_climate()
        entity._pending_target_temp = 23.0
        entity._command_pending = False
        with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
            entity._handle_coordinator_update()
        assert entity._pending_target_temp is None

    def test_preserves_pending_temp_when_command_pending(self) -> None:
        entity = _make_climate()
        entity._pending_target_temp = 23.0
        entity._command_pending = True
        with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
            entity._handle_coordinator_update()
        assert entity._pending_target_temp == 23.0


class TestExtraStateAttributes:
    """Tests for BydClimate.extra_state_attributes."""

    def test_contains_vin(self) -> None:
        entity = _make_climate()
        attrs = entity.extra_state_attributes
        assert attrs["vin"] == "TESTVIN123"

    def test_contains_hvac_attrs_when_present(self) -> None:
        hvac = HvacStatus(status=HvacOverallStatus.ON, tempOutCar=15.0)
        entity = _make_climate(hvac=hvac)
        attrs = entity.extra_state_attributes
        assert "exterior_temperature" in attrs

    def test_last_command_in_attrs(self) -> None:
        entity = _make_climate()
        entity._last_command = "stop_climate"
        attrs = entity.extra_state_attributes
        assert attrs["last_remote_command"] == "stop_climate"

    def test_no_last_command_key_when_none(self) -> None:
        entity = _make_climate()
        attrs = entity.extra_state_attributes
        assert "last_remote_command" not in attrs


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
