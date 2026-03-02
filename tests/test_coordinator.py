"""Unit tests for coordinator helpers."""

from __future__ import annotations

import types
from unittest.mock import MagicMock

from custom_components.byd_vehicle.coordinator import BydApi, get_vehicle_display


def test_get_vehicle_display_with_model_name() -> None:
    vehicle = types.SimpleNamespace(model_name="BYD Atto 3", vin="LGXCE40B4P0000001")
    assert get_vehicle_display(vehicle) == "BYD Atto 3"


def test_get_vehicle_display_without_model_name_returns_vin() -> None:
    vehicle = types.SimpleNamespace(model_name="", vin="LGXCE40B4P0000001")
    assert get_vehicle_display(vehicle) == "LGXCE40B4P0000001"


def test_get_vehicle_display_none_model_name_returns_vin() -> None:
    vehicle = types.SimpleNamespace(model_name=None, vin="LGXCE40B4P0000002")
    assert get_vehicle_display(vehicle) == "LGXCE40B4P0000002"


# ---------------------------------------------------------------------------
# BydApi helpers that can be tested without a real HA instance
# ---------------------------------------------------------------------------


def _make_api() -> BydApi:
    """Create a BydApi bypassing __init__ (avoids HA/pybyd setup)."""
    api = object.__new__(BydApi)
    api._debug_dumps_enabled = False
    api._debug_dump_dir = MagicMock()
    api._coordinators = {}
    return api


def test_register_coordinators() -> None:
    api = _make_api()
    coords = {"VIN123": MagicMock()}
    api.register_coordinators(coords)
    assert api._coordinators is coords


def test_write_debug_dump_skipped_when_disabled() -> None:
    api = _make_api()
    api._debug_dumps_enabled = False
    # Should not raise and should not create any files
    api._write_debug_dump("test", {"key": "value"})
    api._debug_dump_dir.mkdir.assert_not_called()


def test_write_debug_dump_writes_when_enabled(tmp_path) -> None:
    api = _make_api()
    api._debug_dumps_enabled = True

    api._debug_dump_dir = tmp_path / "byd_debug"
    api._write_debug_dump("test_cat", {"k": "v"})
    files = list((tmp_path / "byd_debug").iterdir())
    assert len(files) == 1
    assert "test_cat" in files[0].name


def test_write_debug_dump_handles_exception_gracefully() -> None:
    api = _make_api()
    api._debug_dumps_enabled = True
    api._debug_dump_dir = MagicMock()
    api._debug_dump_dir.mkdir.side_effect = OSError("no space")
    # Should not raise
    api._write_debug_dump("cat", {})


# ---------------------------------------------------------------------------
# BydDataUpdateCoordinator pure helpers
# ---------------------------------------------------------------------------


from datetime import timedelta

from custom_components.byd_vehicle.coordinator import (
    BydDataUpdateCoordinator,
    BydGpsUpdateCoordinator,
)


def _make_telemetry_coordinator() -> BydDataUpdateCoordinator:
    """Create a BydDataUpdateCoordinator bypassing __init__."""
    from time import monotonic as _mono

    coordinator = object.__new__(BydDataUpdateCoordinator)
    coordinator._api = MagicMock()
    coordinator._vin = "TESTVIN123456"
    coordinator._vehicle = MagicMock()
    coordinator._fixed_interval = timedelta(seconds=60)
    coordinator._polling_enabled = True
    coordinator._force_next_refresh = False
    coordinator._last_realtime = None
    coordinator._last_hvac = None
    coordinator._optimistic_hvac_until = None
    coordinator._optimistic_ac_expected = None
    coordinator._realtime_endpoint_unsupported = False
    coordinator.data = {}
    coordinator.update_interval = timedelta(seconds=60)
    coordinator.async_set_updated_data = MagicMock()
    return coordinator


def _make_gps_coordinator() -> BydGpsUpdateCoordinator:
    """Create a BydGpsUpdateCoordinator bypassing __init__."""
    coordinator = object.__new__(BydGpsUpdateCoordinator)
    coordinator._api = MagicMock()
    coordinator._vin = "TESTVIN123456"
    coordinator._vehicle = MagicMock()
    coordinator._telemetry_coordinator = None
    coordinator._smart_polling = False
    coordinator._fixed_interval = timedelta(seconds=300)
    coordinator._active_interval = timedelta(seconds=30)
    coordinator._inactive_interval = timedelta(seconds=600)
    coordinator._current_interval = timedelta(seconds=300)
    coordinator._polling_enabled = True
    coordinator._force_next_refresh = False
    coordinator._last_gps = None
    coordinator.data = {}
    coordinator.update_interval = timedelta(seconds=300)
    coordinator.async_set_updated_data = MagicMock()
    return coordinator


class TestBydDataUpdateCoordinatorHelpers:

    def test_is_vehicle_on_none_realtime(self) -> None:
        result = BydDataUpdateCoordinator._is_vehicle_on(None)
        assert result is None

    def test_is_vehicle_on_returns_value(self) -> None:
        rt = MagicMock()
        rt.is_vehicle_on = True
        assert BydDataUpdateCoordinator._is_vehicle_on(rt) is True

    def test_is_vehicle_on_property_false_when_no_realtime(self) -> None:
        coordinator = _make_telemetry_coordinator()
        assert coordinator.is_vehicle_on is False

    def test_is_vehicle_on_property_true_when_on(self) -> None:
        coordinator = _make_telemetry_coordinator()
        rt = MagicMock()
        rt.is_vehicle_on = True
        coordinator._last_realtime = rt
        assert coordinator.is_vehicle_on is True

    def test_hvac_command_pending_false_when_no_guard(self) -> None:
        coordinator = _make_telemetry_coordinator()
        assert coordinator.hvac_command_pending is False

    def test_hvac_command_pending_true_when_guard_active(self) -> None:
        from time import monotonic

        coordinator = _make_telemetry_coordinator()
        coordinator._optimistic_hvac_until = monotonic() + 60
        assert coordinator.hvac_command_pending is True

    def test_hvac_command_pending_false_when_guard_expired(self) -> None:
        coordinator = _make_telemetry_coordinator()
        coordinator._optimistic_hvac_until = 0.0  # past
        assert coordinator.hvac_command_pending is False

    def test_should_fetch_hvac_true_when_no_last_hvac(self) -> None:
        coordinator = _make_telemetry_coordinator()
        assert coordinator._should_fetch_hvac(None) is True

    def test_should_fetch_hvac_true_when_force(self) -> None:
        coordinator = _make_telemetry_coordinator()
        from pybyd.models.hvac import HvacStatus

        coordinator._last_hvac = HvacStatus()
        assert coordinator._should_fetch_hvac(None, force=True) is True

    def test_should_fetch_hvac_false_when_vehicle_off(self) -> None:
        from pybyd.models.hvac import HvacStatus

        coordinator = _make_telemetry_coordinator()
        coordinator._last_hvac = HvacStatus()
        rt = MagicMock()
        rt.is_vehicle_on = False
        assert coordinator._should_fetch_hvac(rt) is False

    def test_should_fetch_hvac_true_when_vehicle_on(self) -> None:
        from pybyd.models.hvac import HvacStatus

        coordinator = _make_telemetry_coordinator()
        coordinator._last_hvac = HvacStatus()
        rt = MagicMock()
        rt.is_vehicle_on = True
        assert coordinator._should_fetch_hvac(rt) is True

    def test_accept_hvac_update_true_when_no_guard(self) -> None:
        from pybyd.models.hvac import HvacStatus

        coordinator = _make_telemetry_coordinator()
        assert coordinator._accept_hvac_update(HvacStatus()) is True

    def test_accept_hvac_update_true_when_guard_expired(self) -> None:
        from pybyd.models.hvac import HvacStatus

        coordinator = _make_telemetry_coordinator()
        coordinator._optimistic_hvac_until = 0.0
        assert coordinator._accept_hvac_update(HvacStatus()) is True

    def test_accept_hvac_update_true_when_confirmed(self) -> None:
        from pybyd.models.hvac import HvacOverallStatus, HvacStatus
        from time import monotonic

        coordinator = _make_telemetry_coordinator()
        coordinator._optimistic_hvac_until = monotonic() + 60
        coordinator._optimistic_ac_expected = True
        hvac = HvacStatus(status=HvacOverallStatus.ON)
        assert coordinator._accept_hvac_update(hvac) is True
        assert coordinator._optimistic_hvac_until is None

    def test_accept_hvac_update_false_when_mismatch(self) -> None:
        from pybyd.models.hvac import HvacOverallStatus, HvacStatus
        from time import monotonic

        coordinator = _make_telemetry_coordinator()
        coordinator._optimistic_hvac_until = monotonic() + 60
        coordinator._optimistic_ac_expected = True
        hvac = HvacStatus()  # ac_on=False
        assert coordinator._accept_hvac_update(hvac) is False

    def test_polling_enabled_property(self) -> None:
        coordinator = _make_telemetry_coordinator()
        assert coordinator.polling_enabled is True

    def test_set_polling_enabled_false(self) -> None:
        coordinator = _make_telemetry_coordinator()
        coordinator.set_polling_enabled(False)
        assert coordinator._polling_enabled is False
        assert coordinator.update_interval is None

    def test_set_polling_enabled_true(self) -> None:
        coordinator = _make_telemetry_coordinator()
        coordinator._polling_enabled = False
        coordinator.set_polling_enabled(True)
        assert coordinator._polling_enabled is True
        assert coordinator.update_interval == coordinator._fixed_interval

    def test_handle_mqtt_realtime_updates_data(self) -> None:
        coordinator = _make_telemetry_coordinator()
        coordinator.data = {"vehicles": {}}
        rt = MagicMock()
        coordinator.handle_mqtt_realtime(rt)
        assert coordinator._last_realtime is rt
        coordinator.async_set_updated_data.assert_called_once()

    def test_handle_mqtt_realtime_skips_when_no_dict_data(self) -> None:
        coordinator = _make_telemetry_coordinator()
        coordinator.data = None
        rt = MagicMock()
        coordinator.handle_mqtt_realtime(rt)
        assert coordinator._last_realtime is rt
        coordinator.async_set_updated_data.assert_not_called()


class TestBydGpsCoordinatorHelpers:

    def test_polling_enabled_property(self) -> None:
        coordinator = _make_gps_coordinator()
        assert coordinator.polling_enabled is True

    def test_set_polling_enabled_false(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator.set_polling_enabled(False)
        assert coordinator._polling_enabled is False
        assert coordinator.update_interval is None

    def test_set_polling_enabled_true(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._polling_enabled = False
        coordinator.set_polling_enabled(True)
        assert coordinator._polling_enabled is True

    def test_adjust_interval_no_smart_polling(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = False
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._fixed_interval

    def test_adjust_interval_smart_vehicle_on(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = True
        telemetry = MagicMock()
        telemetry.is_vehicle_on = True
        coordinator._telemetry_coordinator = telemetry
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._active_interval

    def test_adjust_interval_smart_vehicle_off(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = True
        telemetry = MagicMock()
        telemetry.is_vehicle_on = False
        coordinator._telemetry_coordinator = telemetry
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._inactive_interval

    def test_adjust_interval_smart_no_telemetry(self) -> None:
        coordinator = _make_gps_coordinator()
        coordinator._smart_polling = True
        coordinator._telemetry_coordinator = None
        coordinator._adjust_interval()
        assert coordinator._current_interval == coordinator._inactive_interval


# ---------------------------------------------------------------------------
# BydDataUpdateCoordinator.apply_optimistic_hvac
# ---------------------------------------------------------------------------


class TestApplyOptimisticHvac:

    def test_no_op_when_data_not_dict(self) -> None:
        coordinator = _make_telemetry_coordinator()
        coordinator.data = None
        coordinator.apply_optimistic_hvac(ac_on=True)
        coordinator.async_set_updated_data.assert_not_called()

    def test_no_op_when_no_hvac_in_data(self) -> None:
        coordinator = _make_telemetry_coordinator()
        coordinator.data = {"vehicles": {}}
        coordinator.apply_optimistic_hvac(ac_on=True)
        coordinator.async_set_updated_data.assert_not_called()

    def test_no_op_when_no_updates(self) -> None:
        from pybyd.models.hvac import HvacStatus

        coordinator = _make_telemetry_coordinator()
        hvac = HvacStatus()
        coordinator.data = {"hvac": {coordinator._vin: hvac}}
        # No ac_on, no target_temp, no reset_seats → no updates
        coordinator.apply_optimistic_hvac()
        coordinator.async_set_updated_data.assert_not_called()

    def test_sets_ac_on(self) -> None:
        from pybyd.models.hvac import HvacOverallStatus, HvacStatus

        coordinator = _make_telemetry_coordinator()
        hvac = HvacStatus()
        coordinator.data = {"hvac": {coordinator._vin: hvac}}
        coordinator.apply_optimistic_hvac(ac_on=True)
        coordinator.async_set_updated_data.assert_called_once()
        assert coordinator._optimistic_ac_expected is True
        assert coordinator._optimistic_hvac_until is not None

    def test_sets_target_temp(self) -> None:
        from pybyd.models.hvac import HvacStatus

        coordinator = _make_telemetry_coordinator()
        hvac = HvacStatus()
        coordinator.data = {"hvac": {coordinator._vin: hvac}}
        coordinator.apply_optimistic_hvac(target_temp=23.0)
        coordinator.async_set_updated_data.assert_called_once()

    def test_reset_seats(self) -> None:
        from pybyd.models.hvac import HvacOverallStatus, HvacStatus
        from pybyd.models.realtime import SeatHeatVentState, StearingWheelHeat

        coordinator = _make_telemetry_coordinator()
        hvac = HvacStatus(
            status=HvacOverallStatus.ON,
            mainSeatHeatState=SeatHeatVentState.LOW,
            steeringWheelHeatState=StearingWheelHeat.ON,
        )
        coordinator.data = {"hvac": {coordinator._vin: hvac}}
        coordinator.apply_optimistic_hvac(reset_seats=True)
        coordinator.async_set_updated_data.assert_called_once()


# ---------------------------------------------------------------------------
# BydDataUpdateCoordinator async fetch helpers (mock API)
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.asyncio
async def test_async_fetch_realtime_updates_data() -> None:
    from unittest.mock import AsyncMock
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.data = {"vehicles": {}}
    rt = MagicMock(spec=VehicleRealtimeData)
    coordinator._api.async_call = AsyncMock(return_value=rt)
    await coordinator.async_fetch_realtime()
    assert coordinator._last_realtime is rt
    coordinator.async_set_updated_data.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_hvac_updates_data() -> None:
    from unittest.mock import AsyncMock
    from pybyd.models.hvac import HvacStatus

    coordinator = _make_telemetry_coordinator()
    coordinator.data = {"vehicles": {}}
    hvac = HvacStatus()
    coordinator._api.async_call = AsyncMock(return_value=hvac)
    await coordinator.async_fetch_hvac()
    assert coordinator._last_hvac is hvac
    coordinator.async_set_updated_data.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_hvac_rejected_by_guard() -> None:
    from time import monotonic
    from unittest.mock import AsyncMock
    from pybyd.models.hvac import HvacOverallStatus, HvacStatus

    coordinator = _make_telemetry_coordinator()
    coordinator.data = {"vehicles": {}}
    # Arm guard expecting ac_on=True but return ac_on=False
    coordinator._optimistic_hvac_until = monotonic() + 60
    coordinator._optimistic_ac_expected = True
    hvac = HvacStatus()  # is_ac_on=False — mismatch → rejected
    coordinator._api.async_call = AsyncMock(return_value=hvac)
    await coordinator.async_fetch_hvac()
    coordinator.async_set_updated_data.assert_not_called()


@pytest.mark.asyncio
async def test_async_force_refresh_sets_flag() -> None:
    from unittest.mock import AsyncMock

    coordinator = _make_telemetry_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    await coordinator.async_force_refresh()
    assert coordinator._force_next_refresh is True
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_gps_async_force_refresh_sets_flag() -> None:
    from unittest.mock import AsyncMock

    coordinator = _make_gps_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    await coordinator.async_force_refresh()
    assert coordinator._force_next_refresh is True
    coordinator.async_request_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# BydApi._handle_vehicle_info
# ---------------------------------------------------------------------------


def test_handle_vehicle_info_dispatches_to_coordinator() -> None:
    from pybyd.models.realtime import VehicleRealtimeData

    api = _make_api()
    coordinator = MagicMock()
    api._coordinators = {"TESTVIN123": coordinator}
    rt = MagicMock(spec=VehicleRealtimeData)
    api._handle_vehicle_info("TESTVIN123", rt)
    coordinator.handle_mqtt_realtime.assert_called_once_with(rt)


def test_handle_vehicle_info_ignores_unknown_vin() -> None:
    from pybyd.models.realtime import VehicleRealtimeData

    api = _make_api()
    api._coordinators = {}
    rt = MagicMock(spec=VehicleRealtimeData)
    # Should not raise
    api._handle_vehicle_info("UNKNOWNVIN", rt)
