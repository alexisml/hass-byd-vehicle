"""Tests for lock module."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.byd_vehicle import lock
from custom_components.byd_vehicle.lock import BydLock


def test_lock_module_importable() -> None:
    assert hasattr(lock, "BydLock")


# ---------------------------------------------------------------------------
# BydLock entity tests
# ---------------------------------------------------------------------------


def _make_lock(realtime_obj=None) -> BydLock:
    """Create a BydLock bypassing __init__."""
    vin = "TESTVIN123"
    coordinator = MagicMock()
    coordinator.last_update_success = True
    data: dict = {"vehicles": {vin: MagicMock()}}
    if realtime_obj is not None:
        data["realtime"] = {vin: realtime_obj}
    coordinator.data = data

    entity = object.__new__(BydLock)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._api = AsyncMock()
    entity._api.async_call = AsyncMock()
    entity._attr_unique_id = f"{vin}_lock"
    entity._command_pending = False
    entity._commanded_at = None
    entity._last_command = None
    entity._last_locked = None
    entity.async_write_ha_state = MagicMock()
    return entity


def test_is_locked_returns_realtime_value() -> None:
    rt = types.SimpleNamespace(is_locked=True)
    entity = _make_lock(realtime_obj=rt)
    assert entity.is_locked is True


def test_is_locked_false_from_realtime() -> None:
    rt = types.SimpleNamespace(is_locked=False)
    entity = _make_lock(realtime_obj=rt)
    assert entity.is_locked is False


def test_is_locked_falls_back_to_last_when_no_realtime() -> None:
    entity = _make_lock(realtime_obj=None)
    entity._last_locked = True
    assert entity.is_locked is True


def test_is_locked_when_command_pending_returns_last() -> None:
    entity = _make_lock(realtime_obj=None)
    entity._command_pending = True
    entity._last_locked = False
    assert entity.is_locked is False


def test_assumed_state_true_when_no_realtime() -> None:
    entity = _make_lock(realtime_obj=None)
    assert entity.assumed_state is True


def test_assumed_state_true_when_realtime_has_none_lock() -> None:
    rt = types.SimpleNamespace(is_locked=None)
    entity = _make_lock(realtime_obj=rt)
    assert entity.assumed_state is True


def test_assumed_state_false_when_realtime_has_value() -> None:
    rt = types.SimpleNamespace(is_locked=True)
    entity = _make_lock(realtime_obj=rt)
    assert entity.assumed_state is False


def test_assumed_state_true_when_command_pending() -> None:
    rt = types.SimpleNamespace(is_locked=True)
    entity = _make_lock(realtime_obj=rt)
    entity._command_pending = True
    assert entity.assumed_state is True


def test_is_command_confirmed_no_last_locked() -> None:
    entity = _make_lock()
    entity._last_locked = None
    assert entity._is_command_confirmed() is True


def test_is_command_confirmed_matches_realtime() -> None:
    rt = types.SimpleNamespace(is_locked=True)
    entity = _make_lock(realtime_obj=rt)
    entity._last_locked = True
    assert entity._is_command_confirmed() is True


def test_is_command_confirmed_mismatch() -> None:
    rt = types.SimpleNamespace(is_locked=False)
    entity = _make_lock(realtime_obj=rt)
    entity._last_locked = True
    assert entity._is_command_confirmed() is False


def test_is_command_confirmed_no_realtime_returns_false() -> None:
    entity = _make_lock(realtime_obj=None)
    entity._last_locked = True
    assert entity._is_command_confirmed() is False


def test_handle_coordinator_update_tracks_lock_state() -> None:
    rt = types.SimpleNamespace(is_locked=True)
    entity = _make_lock(realtime_obj=rt)
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()
    assert entity._last_locked is True


def test_handle_coordinator_update_no_update_when_pending() -> None:
    rt = types.SimpleNamespace(is_locked=True)
    entity = _make_lock(realtime_obj=rt)
    entity._command_pending = True
    entity._last_locked = False  # different from realtime
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()
    # should NOT update _last_locked when command is pending
    assert entity._last_locked is False


def test_extra_state_attributes_with_last_command() -> None:
    entity = _make_lock()
    entity._last_command = "lock"
    attrs = entity.extra_state_attributes
    assert attrs["last_remote_command"] == "lock"
    assert attrs["vin"] == "TESTVIN123"


def test_extra_state_attributes_no_last_command() -> None:
    entity = _make_lock()
    attrs = entity.extra_state_attributes
    assert "last_remote_command" not in attrs


# ---------------------------------------------------------------------------
# async_lock and async_unlock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_lock_sets_last_command_and_pending() -> None:
    entity = _make_lock()
    await entity.async_lock()
    assert entity._last_command == "lock"
    assert entity._last_locked is True
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_async_unlock_sets_last_command_and_pending() -> None:
    entity = _make_lock()
    await entity.async_unlock()
    assert entity._last_command == "unlock"
    assert entity._last_locked is False
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_async_lock_executes_api_call() -> None:
    """Cover lock.py line 103: the inner _call closure calls client.lock."""
    entity = _make_lock()
    client = AsyncMock()
    client.lock = AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):  # **kwargs absorbs vin= and command= from _execute_command
        return await func(client)

    entity._api.async_call = AsyncMock(side_effect=execute_call)
    await entity.async_lock()
    client.lock.assert_called_once_with("TESTVIN123")


@pytest.mark.asyncio
async def test_async_unlock_executes_api_call() -> None:
    """Cover lock.py line 118: the inner _call closure calls client.unlock."""
    entity = _make_lock()
    client = AsyncMock()
    client.unlock = AsyncMock(return_value=None)

    async def execute_call(func, **kwargs):  # **kwargs absorbs vin= and command= from _execute_command
        return await func(client)

    entity._api.async_call = AsyncMock(side_effect=execute_call)
    await entity.async_unlock()
    client.unlock.assert_called_once_with("TESTVIN123")


# ---------------------------------------------------------------------------
# async_setup_entry (lines 23-35)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_async_setup_entry_no_vehicles_creates_no_entities() -> None:
    """Cover lock.py lines 23-35: async_setup_entry with vehicle=None."""
    from custom_components.byd_vehicle.const import DOMAIN
    from custom_components.byd_vehicle.lock import async_setup_entry

    vin = "TESTVIN123"
    coordinator = MagicMock()
    coordinator.data = {"vehicles": {}}  # vehicle is None → continue

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

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once_with([])


@pytest.mark.asyncio
async def test_lock_async_setup_entry_creates_lock_entity() -> None:
    """Cover lock.py line 33: entity created when vehicle found."""
    from custom_components.byd_vehicle.const import DOMAIN
    from custom_components.byd_vehicle.lock import async_setup_entry

    vin = "TESTVIN123"
    vehicle_mock = MagicMock()
    coordinator = MagicMock()
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

    async_add_entities = MagicMock()

    with patch(
        "custom_components.byd_vehicle.lock.BydLock.__init__",
        return_value=None,
    ):
        await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], BydLock)
