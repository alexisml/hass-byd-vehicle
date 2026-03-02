"""Unit tests for BydApi.async_call tests."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.byd_vehicle.coordinator import (
    BydApi,
    BydDataUpdateCoordinator,
)


def _make_api() -> BydApi:
    """Create a BydApi bypassing __init__ (avoids HA/pybyd setup)."""
    api = object.__new__(BydApi)
    api._debug_dumps_enabled = False
    api._debug_dump_dir = MagicMock()
    api._coordinators = {}
    return api


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
    # First call: BydSessionExpiredError; retry: BydAuthenticationError
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
    sleep_target = "custom_components.byd_vehicle.coordinator.asyncio.sleep"
    with patch(sleep_target, new=AsyncMock()):
        await coordinator.async_fetch_hvac_delayed(0)
    coordinator.async_fetch_hvac.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_realtime_delayed_calls_fetch() -> None:
    """async_fetch_realtime_delayed should eventually call async_fetch_realtime."""

    coordinator = _make_telemetry_coordinator()
    coordinator.async_fetch_realtime = AsyncMock()
    sleep_target = "custom_components.byd_vehicle.coordinator.asyncio.sleep"
    with patch(sleep_target, new=AsyncMock()):
        await coordinator.async_fetch_realtime_delayed(0)
    coordinator.async_fetch_realtime.assert_called_once()


@pytest.mark.asyncio
async def test_async_fetch_hvac_delayed_handles_exception() -> None:
    """async_fetch_hvac_delayed should swallow exceptions from async_fetch_hvac."""

    coordinator = _make_telemetry_coordinator()
    coordinator.async_fetch_hvac = AsyncMock(side_effect=RuntimeError("fetch failed"))
    sleep_target = "custom_components.byd_vehicle.coordinator.asyncio.sleep"
    with patch(sleep_target, new=AsyncMock()):
        # Should not raise
        await coordinator.async_fetch_hvac_delayed(0)


@pytest.mark.asyncio
async def test_async_fetch_realtime_delayed_handles_exception() -> None:
    """async_fetch_realtime_delayed should swallow exceptions."""

    coordinator = _make_telemetry_coordinator()
    coordinator.async_fetch_realtime = AsyncMock(
        side_effect=RuntimeError("fetch failed")
    )
    sleep_target = "custom_components.byd_vehicle.coordinator.asyncio.sleep"
    with patch(sleep_target, new=AsyncMock()):
        # Should not raise
        await coordinator.async_fetch_realtime_delayed(0)
