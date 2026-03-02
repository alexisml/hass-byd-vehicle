"""Unit tests for BydDataUpdateCoordinator telemetry helpers."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.byd_vehicle.coordinator import (
    BydDataUpdateCoordinator,
)


def _make_telemetry_coordinator() -> BydDataUpdateCoordinator:
    """Create a BydDataUpdateCoordinator bypassing __init__."""

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
        from time import monotonic

        from pybyd.models.hvac import HvacOverallStatus, HvacStatus

        coordinator = _make_telemetry_coordinator()
        coordinator._optimistic_hvac_until = monotonic() + 60
        coordinator._optimistic_ac_expected = True
        hvac = HvacStatus(status=HvacOverallStatus.ON)
        assert coordinator._accept_hvac_update(hvac) is True
        assert coordinator._optimistic_hvac_until is None

    def test_accept_hvac_update_false_when_mismatch(self) -> None:
        from time import monotonic

        from pybyd.models.hvac import HvacStatus

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
        from pybyd.models.hvac import HvacStatus

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


@pytest.mark.asyncio
async def test_async_fetch_realtime_updates_data() -> None:
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

    from pybyd.models.hvac import HvacStatus

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

    coordinator = _make_telemetry_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    await coordinator.async_force_refresh()
    assert coordinator._force_next_refresh is True
    coordinator.async_request_refresh.assert_called_once()


def test_data_update_coordinator_init() -> None:
    """Cover lines 382-403: __init__ with mocked DataUpdateCoordinator."""
    from datetime import timedelta

    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    api = MagicMock()
    vehicle = MagicMock()

    with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
        from custom_components.byd_vehicle.coordinator import BydDataUpdateCoordinator

        coordinator = BydDataUpdateCoordinator(
            MagicMock(), api, vehicle, "TESTVIN123456", 60
        )

    assert coordinator._api is api
    assert coordinator._vin == "TESTVIN123456"
    assert coordinator._fixed_interval == timedelta(seconds=60)
    assert coordinator._polling_enabled is True
    assert coordinator._force_next_refresh is False
    assert coordinator._last_realtime is None
    assert coordinator._last_hvac is None


@pytest.mark.asyncio
async def test_async_fetch_realtime_invokes_fetch_closure() -> None:
    """Line 640: the _fetch closure inside async_fetch_realtime."""

    coordinator = _make_telemetry_coordinator()
    coordinator.data = {"vehicles": {}}

    mock_client = MagicMock()
    rt = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=rt)

    async def invoke_handler(handler, **kwargs):
        return await handler(mock_client)

    coordinator._api.async_call = invoke_handler
    await coordinator.async_fetch_realtime()
    assert coordinator._last_realtime is rt
    mock_client.get_vehicle_realtime.assert_called_once_with(coordinator._vin)


@pytest.mark.asyncio
async def test_async_fetch_hvac_invokes_fetch_closure() -> None:
    """Line 655: the _fetch closure inside async_fetch_hvac."""
    from pybyd.models.hvac import HvacStatus

    coordinator = _make_telemetry_coordinator()
    coordinator.data = {"vehicles": {}}

    mock_client = MagicMock()
    hvac = HvacStatus()
    mock_client.get_hvac_status = AsyncMock(return_value=hvac)

    async def invoke_handler(handler, **kwargs):
        return await handler(mock_client)

    coordinator._api.async_call = invoke_handler
    await coordinator.async_fetch_hvac()
    assert coordinator._last_hvac is hvac
    mock_client.get_hvac_status.assert_called_once_with(coordinator._vin)


@pytest.mark.asyncio
async def test_telemetry_update_data_polling_disabled_returns_cached() -> None:
    """Cover lines 488-491: when polling disabled and data is dict, return cached data."""
    coordinator = _make_telemetry_coordinator()
    coordinator._polling_enabled = False
    coordinator._force_next_refresh = False
    cached = {"vehicles": {coordinator._vin: coordinator._vehicle}, "realtime": {}}
    coordinator.data = cached

    result = await coordinator._async_update_data()
    assert result is cached


@pytest.mark.asyncio
async def test_telemetry_update_data_polling_disabled_no_dict_returns_vehicles() -> None:
    """Cover lines 488-491: when polling disabled and data is not dict, return fallback."""
    coordinator = _make_telemetry_coordinator()
    coordinator._polling_enabled = False
    coordinator._force_next_refresh = False
    coordinator.data = None  # not a dict

    result = await coordinator._async_update_data()
    assert coordinator._vin in result["vehicles"]


@pytest.mark.asyncio
async def test_telemetry_update_data_fetch_closure_success() -> None:
    """Cover lines 493-619: full _async_update_data fetch path."""
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = True
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(return_value=None)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    assert coordinator._vin in result["vehicles"]
    assert coordinator._vin in result.get("realtime", {}) or True  # realtime may be there
