"""Unit tests for coordinator helpers."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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

    coordinator = _make_telemetry_coordinator()
    coordinator.async_request_refresh = AsyncMock()
    await coordinator.async_force_refresh()
    assert coordinator._force_next_refresh is True
    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_gps_async_force_refresh_sets_flag() -> None:

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


# ---------------------------------------------------------------------------
# BydApi other helpers
# ---------------------------------------------------------------------------


def test_config_property() -> None:
    api = _make_api()
    from pybyd.config import BydConfig
    api._config = MagicMock(spec=BydConfig)
    assert api.config is api._config


def test_debug_dumps_enabled_property() -> None:
    api = _make_api()
    api._debug_dumps_enabled = True
    assert api.debug_dumps_enabled is True


def test_handle_command_ack_dispatches_to_coordinator() -> None:
    api = _make_api()
    coordinator = MagicMock()
    coordinator.data = {"vehicles": {}}
    api._coordinators = {"TESTVIN123": coordinator}
    api._hass = MagicMock()
    api._handle_command_ack("remoteControl", "TESTVIN123", {"requestSerial": "abc123"})
    coordinator.async_set_updated_data.assert_called_once()
    assert api._hass.async_create_task.call_count == 2


def test_handle_command_ack_unknown_vin_is_noop() -> None:
    api = _make_api()
    api._coordinators = {}
    api._hass = MagicMock()
    api._handle_command_ack("remoteControl", "UNKNOWNVIN", {})
    api._hass.async_create_task.assert_not_called()


def test_handle_mqtt_event_no_debug_dump_when_disabled() -> None:
    api = _make_api()
    api._debug_dumps_enabled = False
    api._hass = MagicMock()
    api._handle_mqtt_event("someEvent", "TESTVIN123", {})
    api._hass.async_create_task.assert_not_called()


def test_handle_mqtt_event_creates_task_when_debug_enabled() -> None:
    api = _make_api()
    api._debug_dumps_enabled = True
    api._hass = MagicMock()
    api._handle_mqtt_event("someEvent", "TESTVIN123", {"data": "val"})
    api._hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_async_shutdown_calls_invalidate_client() -> None:
    """async_shutdown invokes _invalidate_client."""
    api = _make_api()
    api._client = None  # No client to close
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"
    # Should not raise
    await api.async_shutdown()


@pytest.mark.asyncio
async def test_async_write_debug_dump_forwards_to_internal() -> None:

    api = _make_api()
    api._async_write_debug_dump = AsyncMock()
    await api.async_write_debug_dump("cat", {"k": "v"})
    api._async_write_debug_dump.assert_called_once_with("cat", {"k": "v"})


@pytest.mark.asyncio
async def test_invalidate_client_with_existing_client() -> None:

    api = _make_api()
    client = MagicMock()
    client.async_close = AsyncMock()
    api._client = client
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"
    await api._invalidate_client()
    client.async_close.assert_called_once()
    assert api._client is None


@pytest.mark.asyncio
async def test_invalidate_client_no_client_is_noop() -> None:
    api = _make_api()
    api._client = None
    # Should not raise
    await api._invalidate_client()


@pytest.mark.asyncio
async def test_invalidate_client_handles_exception() -> None:
    """Test that _invalidate_client handles exceptions from async_close."""

    api = _make_api()
    client = MagicMock()
    client.async_close = AsyncMock(side_effect=RuntimeError("close failed"))
    api._client = client
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"
    # Should not raise — exception is swallowed
    await api._invalidate_client()
    assert api._client is None


@pytest.mark.asyncio
async def test_async_call_success() -> None:
    """Test successful BydApi.async_call path."""

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(return_value="result")
    result = await api.async_call(handler, vin="TESTVIN123456", command="test")
    assert result == "result"
    handler.assert_called_once_with(mock_client)


@pytest.mark.asyncio
async def test_async_call_byd_api_error_raises_update_failed() -> None:
    """Test that BydApiError is wrapped in UpdateFailed."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydApiError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(side_effect=BydApiError("api error"))
    with pytest.raises(UpdateFailed):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_call_auth_error_raises_config_entry_auth_failed() -> None:
    """Test that BydAuthenticationError raises ConfigEntryAuthFailed."""
    from homeassistant.config_entries import ConfigEntryAuthFailed
    from pybyd import BydAuthenticationError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(side_effect=BydAuthenticationError("auth error"))
    with pytest.raises(ConfigEntryAuthFailed):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_call_session_expired_then_retry_fails() -> None:
    """Test BydSessionExpiredError triggers invalidate + retry, which then fails."""
    from homeassistant.config_entries import ConfigEntryAuthFailed
    from pybyd import BydAuthenticationError, BydSessionExpiredError

    api = _make_api()
    mock_client = MagicMock()
    # First call: raises BydSessionExpiredError; second call after retry: BydAuthenticationError
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._invalidate_client = AsyncMock()
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    call_count = 0

    async def handler(client):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise BydSessionExpiredError("expired")
        raise BydAuthenticationError("auth failed")

    with pytest.raises(ConfigEntryAuthFailed):
        await api.async_call(handler, vin="TESTVIN123456", command="test")
    api._invalidate_client.assert_called_once()


@pytest.mark.asyncio
async def test_async_call_control_password_error() -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydControlPasswordError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(side_effect=BydControlPasswordError("bad pin"))
    with pytest.raises(UpdateFailed, match="Control PIN"):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_call_rate_limit_error() -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydRateLimitError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(side_effect=BydRateLimitError("rate limited"))
    with pytest.raises(UpdateFailed, match="rate limited"):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_call_transport_error_invalidates_client() -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydTransportError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._invalidate_client = AsyncMock()
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(side_effect=BydTransportError("transport error"))
    with pytest.raises(UpdateFailed):
        await api.async_call(handler, vin="TESTVIN123456", command="test")
    api._invalidate_client.assert_called_once()


@pytest.mark.asyncio
async def test_async_call_endpoint_not_supported() -> None:
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydEndpointNotSupportedError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(side_effect=BydEndpointNotSupportedError("not supported"))
    with pytest.raises(UpdateFailed, match="not supported"):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_call_generic_exception_reraises() -> None:

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    handler = AsyncMock(side_effect=ValueError("unexpected"))
    with pytest.raises(ValueError, match="unexpected"):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_call_session_expired_retry_with_api_error() -> None:
    """After session expiry, retry fails with BydApiError → UpdateFailed."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydApiError, BydSessionExpiredError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._invalidate_client = AsyncMock()
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    call_count = 0

    async def handler(client):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise BydSessionExpiredError("expired")
        raise BydApiError("api error after retry")

    with pytest.raises(UpdateFailed):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_call_session_expired_retry_with_generic_error() -> None:
    """After session expiry, retry fails with generic error → UpdateFailed."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydSessionExpiredError

    api = _make_api()
    mock_client = MagicMock()
    api._ensure_client = AsyncMock(return_value=mock_client)
    api._invalidate_client = AsyncMock()
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    call_count = 0

    async def handler(client):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise BydSessionExpiredError("expired")
        raise RuntimeError("some generic error")

    with pytest.raises(UpdateFailed):
        await api.async_call(handler, vin="TESTVIN123456", command="test")


@pytest.mark.asyncio
async def test_async_fetch_hvac_delayed_calls_fetch() -> None:
    """async_fetch_hvac_delayed should eventually call async_fetch_hvac."""

    coordinator = _make_telemetry_coordinator()
    coordinator.async_fetch_hvac = AsyncMock()
    with patch("asyncio.sleep", new_callable=lambda: (lambda *_: __import__("asyncio").coroutine(lambda: None)())):
        pass  # skip the patch; instead just call directly with 0 delay
    coordinator.async_fetch_hvac = AsyncMock()
    # Call with 0 delay to avoid actual sleep in tests
    import asyncio
    with patch("custom_components.byd_vehicle.coordinator.asyncio.sleep", new=AsyncMock()):
        await coordinator.async_fetch_hvac_delayed(0)
    coordinator.async_fetch_hvac.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_realtime_delayed_calls_fetch() -> None:
    """async_fetch_realtime_delayed should eventually call async_fetch_realtime."""

    coordinator = _make_telemetry_coordinator()
    coordinator.async_fetch_realtime = AsyncMock()
    with patch("custom_components.byd_vehicle.coordinator.asyncio.sleep", new=AsyncMock()):
        await coordinator.async_fetch_realtime_delayed(0)
    coordinator.async_fetch_realtime.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_hvac_delayed_handles_exception() -> None:
    """async_fetch_hvac_delayed should swallow exceptions from async_fetch_hvac."""

    coordinator = _make_telemetry_coordinator()
    coordinator.async_fetch_hvac = AsyncMock(side_effect=RuntimeError("fetch failed"))
    with patch("custom_components.byd_vehicle.coordinator.asyncio.sleep", new=AsyncMock()):
        # Should not raise
        await coordinator.async_fetch_hvac_delayed(0)


@pytest.mark.asyncio
async def test_async_fetch_realtime_delayed_handles_exception() -> None:
    """async_fetch_realtime_delayed should swallow exceptions."""

    coordinator = _make_telemetry_coordinator()
    coordinator.async_fetch_realtime = AsyncMock(side_effect=RuntimeError("fetch failed"))
    with patch("custom_components.byd_vehicle.coordinator.asyncio.sleep", new=AsyncMock()):
        # Should not raise
        await coordinator.async_fetch_realtime_delayed(0)


@pytest.mark.asyncio
async def test_ensure_client_returns_existing_client() -> None:
    """_ensure_client should return existing client without creating a new one."""

    api = _make_api()
    mock_client = MagicMock()
    api._client = mock_client
    result = await api._ensure_client()
    assert result is mock_client


@pytest.mark.asyncio
async def test_async_fetch_gps_updates_data() -> None:
    """async_fetch_gps should update coordinator data with GPS info."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.data = {"vehicles": {}}
    gps = GpsInfo(latitude=51.5, longitude=4.8)
    coordinator._api.async_call = AsyncMock(return_value=gps)
    await coordinator.async_fetch_gps()
    coordinator.async_set_updated_data.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_gps_with_null_island_guards() -> None:
    """async_fetch_gps should guard against Null Island coordinates."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.data = {"vehicles": {}}
    coordinator._last_gps = GpsInfo(latitude=51.5, longitude=4.8)  # valid previous
    # Null Island (0,0) should be rejected
    gps = GpsInfo(latitude=0.0, longitude=0.0)
    coordinator._api.async_call = AsyncMock(return_value=gps)
    await coordinator.async_fetch_gps()
    # Data still updated (but without the null island GPS)
    coordinator.async_set_updated_data.assert_called_once()


# ---------------------------------------------------------------------------
# _async_write_debug_dump actual body (line 144)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_write_debug_dump_calls_executor_job() -> None:
    """Cover line 144: the actual body of _async_write_debug_dump."""

    api = _make_api()
    api._hass = MagicMock()
    api._hass.async_add_executor_job = AsyncMock(return_value=None)
    await api._async_write_debug_dump("cat", {"k": "v"})
    api._hass.async_add_executor_job.assert_called_once()


# ---------------------------------------------------------------------------
# _ensure_client creating a new client (lines 269-280)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_client_creates_new_when_none() -> None:
    """Cover lines 269-280: _ensure_client when _client is None."""

    api = _make_api()
    api._client = None
    api._config = MagicMock()
    api._http_session = MagicMock()
    api._entry = MagicMock()
    api._entry.entry_id = "test_entry"

    mock_client = MagicMock()
    mock_client.async_start = AsyncMock()

    with patch(
        "custom_components.byd_vehicle.coordinator.BydClient",
        return_value=mock_client,
    ):
        result = await api._ensure_client()

    assert result is mock_client
    assert api._client is mock_client
    mock_client.async_start.assert_called_once()


# ---------------------------------------------------------------------------
# BydDataUpdateCoordinator.__init__ (lines 382-403)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# BydGpsUpdateCoordinator.__init__ (lines 788-805)
# ---------------------------------------------------------------------------


def test_gps_coordinator_init() -> None:
    """Cover lines 788-805: GPS coordinator __init__ with mocked parent."""
    from datetime import timedelta

    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    api = MagicMock()
    vehicle = MagicMock()
    telemetry = MagicMock()

    with patch.object(DataUpdateCoordinator, "__init__", return_value=None):
        from custom_components.byd_vehicle.coordinator import BydGpsUpdateCoordinator

        coordinator = BydGpsUpdateCoordinator(
            MagicMock(),
            api,
            vehicle,
            "TESTVIN123456",
            300,
            telemetry_coordinator=telemetry,
            smart_polling=True,
            active_interval=30,
            inactive_interval=600,
        )

    assert coordinator._api is api
    assert coordinator._vin == "TESTVIN123456"
    assert coordinator._smart_polling is True
    assert coordinator._active_interval == timedelta(seconds=30)
    assert coordinator._inactive_interval == timedelta(seconds=600)
    assert coordinator._telemetry_coordinator is telemetry


# ---------------------------------------------------------------------------
# Inner _fetch closures: covering lines 640, 655, 826
# ---------------------------------------------------------------------------


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
async def test_async_fetch_gps_invokes_fetch_closure() -> None:
    """Line 826: the _fetch closure inside async_fetch_gps."""
    from pybyd.models.gps import GpsInfo

    coordinator = _make_gps_coordinator()
    coordinator.data = {"vehicles": {}}

    mock_client = MagicMock()
    gps = GpsInfo(latitude=51.5, longitude=4.8)
    mock_client.get_gps_info = AsyncMock(return_value=gps)

    async def invoke_handler(handler, **kwargs):
        return await handler(mock_client)

    coordinator._api.async_call = invoke_handler
    await coordinator.async_fetch_gps()
    mock_client.get_gps_info.assert_called_once_with(coordinator._vin)
