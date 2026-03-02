"""Unit tests for BydDataUpdateCoordinator telemetry fetch paths."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

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


@pytest.mark.asyncio
async def test_telemetry_fetch_endpoint_not_supported_first_time() -> None:
    """Cover coordinator.py lines 503-511 + 571-579: BydEndpointNotSupportedError first time."""
    from pybyd import BydEndpointNotSupportedError

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()
    coordinator._realtime_endpoint_unsupported = False

    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(
        side_effect=BydEndpointNotSupportedError("not supported")
    )
    mock_client.get_hvac_status = AsyncMock(return_value=None)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    # Flag should now be set
    assert coordinator._realtime_endpoint_unsupported is True
    # Vehicles key present even without realtime
    assert coordinator._vin in result.get("vehicles", {})


@pytest.mark.asyncio
async def test_telemetry_fetch_endpoint_not_supported_subsequent() -> None:
    """Cover coordinator.py lines 512-517: BydEndpointNotSupportedError subsequent times."""
    from pybyd import BydEndpointNotSupportedError

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()
    coordinator._realtime_endpoint_unsupported = True  # already flagged

    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(
        side_effect=BydEndpointNotSupportedError("not supported")
    )
    mock_client.get_hvac_status = AsyncMock(return_value=None)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    assert coordinator._vin in result.get("vehicles", {})


@pytest.mark.asyncio
async def test_telemetry_fetch_realtime_recoverable_error_raises_update_failed() -> None:
    """Cover coordinator.py lines 518-522 + 580-584: _RECOVERABLE_ERRORS in realtime."""
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pybyd import BydApiError

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(side_effect=BydApiError("api error"))
    mock_client.get_hvac_status = AsyncMock(return_value=None)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_telemetry_fetch_hvac_recoverable_error_and_endpoint_failures_warning() -> None:
    """Cover coordinator.py lines 532-540 + 587: HVAC _RECOVERABLE_ERRORS + warning."""
    from pybyd import BydApiError
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = True
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(side_effect=BydApiError("hvac error"))

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    # Realtime succeeded, hvac failed with endpoint_failures warning
    assert coordinator._vin in result.get("vehicles", {})


@pytest.mark.asyncio
async def test_telemetry_fetch_hvac_guard_discard() -> None:
    """Cover coordinator.py lines 542-545: HVAC discarded by optimistic guard."""
    from time import monotonic

    from pybyd.models.hvac import HvacStatus
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()
    # Arm guard: expecting ac_on=True
    coordinator._optimistic_hvac_until = monotonic() + 60
    coordinator._optimistic_ac_expected = True

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = True
    # HVAC says ac_on=False → contradicts guard → discarded
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(return_value=HvacStatus())  # ac_on=False

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    # HVAC was discarded, _last_hvac stays None
    assert coordinator._last_hvac is None


@pytest.mark.asyncio
async def test_telemetry_fetch_hvac_accepted_updates_last_hvac_and_hvac_map() -> None:
    """Cover coordinator.py lines 554 + 568: HVAC accepted, last_hvac and hvac_map updated."""
    from pybyd.models.hvac import HvacOverallStatus, HvacStatus
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = True
    hvac = HvacStatus(status=HvacOverallStatus.ON)
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(return_value=hvac)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    assert coordinator._last_hvac is hvac  # line 554
    assert coordinator._vin in result.get("hvac", {})  # line 568


@pytest.mark.asyncio
async def test_telemetry_fetch_debug_dumps_enabled() -> None:
    """Cover coordinator.py lines 595-602: debug dump created when debug_dumps_enabled."""
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = False
    mock_realtime.model_dump = MagicMock(return_value={})
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(return_value=None)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = True
    coordinator._api.async_write_debug_dump = AsyncMock()

    await coordinator._async_update_data()
    coordinator.hass.async_create_task.assert_called()


@pytest.mark.asyncio
async def test_telemetry_fetch_realtime_auth_error_reraises() -> None:
    """Cover coordinator.py line 502: auth error re-raised from realtime _fetch."""
    from pybyd import BydAuthenticationError

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(
        side_effect=BydAuthenticationError("auth")
    )

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    with pytest.raises(BydAuthenticationError):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_telemetry_fetch_hvac_auth_error_reraises() -> None:
    """Cover coordinator.py line 533: auth error re-raised from HVAC _fetch."""
    from pybyd import BydAuthenticationError
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = True
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(
        side_effect=BydAuthenticationError("auth")
    )

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    with pytest.raises(BydAuthenticationError):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_telemetry_fetch_hvac_skipped_when_vehicle_off() -> None:
    """Cover coordinator.py line 545: HVAC fetch skipped when vehicle is off."""
    from pybyd.models.hvac import HvacStatus
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()
    coordinator._last_hvac = HvacStatus()  # has previous hvac → won't force-fetch

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = False  # vehicle off → HVAC skipped
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(return_value=None)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = False

    result = await coordinator._async_update_data()
    mock_client.get_hvac_status.assert_not_called()
    assert coordinator._vin in result.get("vehicles", {})


@pytest.mark.asyncio
async def test_telemetry_fetch_debug_dumps_with_hvac_model_dump() -> None:
    """Cover coordinator.py line 601: debug dump includes hvac.model_dump."""
    from pybyd.models.hvac import HvacOverallStatus, HvacStatus
    from pybyd.models.realtime import VehicleRealtimeData

    coordinator = _make_telemetry_coordinator()
    coordinator.hass = MagicMock()

    mock_realtime = MagicMock(spec=VehicleRealtimeData)
    mock_realtime.is_vehicle_on = True
    mock_realtime.model_dump = MagicMock(return_value={})
    hvac = HvacStatus(status=HvacOverallStatus.ON)
    mock_client = MagicMock()
    mock_client.get_vehicle_realtime = AsyncMock(return_value=mock_realtime)
    mock_client.get_hvac_status = AsyncMock(return_value=hvac)

    async def invoke_handler(func, **kwargs):
        return await func(mock_client)

    coordinator._api.async_call = AsyncMock(side_effect=invoke_handler)
    coordinator._api.debug_dumps_enabled = True
    coordinator._api.async_write_debug_dump = AsyncMock()

    await coordinator._async_update_data()
    coordinator.hass.async_create_task.assert_called()
