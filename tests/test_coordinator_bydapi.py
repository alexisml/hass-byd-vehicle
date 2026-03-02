"""Unit tests for BydApi helpers."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.byd_vehicle.coordinator import (
    BydApi,
    get_vehicle_display,
)


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
async def test_ensure_client_returns_existing_client() -> None:
    """_ensure_client should return existing client without creating a new one."""

    api = _make_api()
    mock_client = MagicMock()
    api._client = mock_client
    result = await api._ensure_client()
    assert result is mock_client


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


def test_bydapi_init_creates_instance() -> None:
    """Cover coordinator.py lines 90-112: BydApi.__init__."""
    from custom_components.byd_vehicle.const import (
        CONF_BASE_URL,
        CONF_CONTROL_PIN,
        CONF_COUNTRY_CODE,
        CONF_DEBUG_DUMPS,
        CONF_DEVICE_PROFILE,
        CONF_LANGUAGE,
        DEFAULT_DEBUG_DUMPS,
        DEFAULT_LANGUAGE,
        DOMAIN,
    )
    from pybyd.config import DeviceProfile

    device_profile = {
        "model": "TestModel",
        "imei": "123456789012345",
        "mac": "aa:bb:cc:dd:ee:ff",
        "sdk": "28",
        "mod": "Generic",
        "imei_md5": "abc123",
        "mobile_brand": "Generic",
        "mobile_model": "TestModel",
        "device_type": "0",
        "network_type": "wifi",
        "os_type": "and",
        "os_version": "28",
        "ostype": "and",
    }

    hass = MagicMock()
    hass.config.time_zone = "UTC"
    hass.config.path = MagicMock(return_value="/tmp/byd_test")

    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = {
        "username": "user@test.com",
        "password": "secret",
        CONF_BASE_URL: "https://api.example.com",
        CONF_COUNTRY_CODE: "NL",
        CONF_LANGUAGE: DEFAULT_LANGUAGE,
        CONF_DEVICE_PROFILE: device_profile,
        CONF_CONTROL_PIN: None,
    }
    entry.options = {CONF_DEBUG_DUMPS: DEFAULT_DEBUG_DUMPS}

    session = MagicMock()
    api = BydApi(hass, entry, session)
    assert api._client is None
    assert api._debug_dumps_enabled == DEFAULT_DEBUG_DUMPS
    assert api._coordinators == {}
