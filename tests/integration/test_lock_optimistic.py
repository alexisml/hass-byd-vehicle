"""Integration tests: lock command → optimistic state → confirmation cycle.

Exercises the full round-trip:
  async_lock() sets optimistic state
  → coordinator push with stale data is ignored while command_pending
  → coordinator push confirms → flag clears
"""

from __future__ import annotations

import types
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from .helpers import make_lock_entity, make_telemetry_coordinator


@pytest.mark.asyncio
async def test_lock_command_optimistic_then_confirmed() -> None:
    """Lock command holds optimistic state until coordinator confirms it."""
    vin = "VIN_LOCK_001"
    rt_unlocked = types.SimpleNamespace(is_locked=False)
    data = {
        "vehicles": {vin: MagicMock()},
        "realtime": {vin: rt_unlocked},
    }
    coordinator = make_telemetry_coordinator(vin=vin, data=data)
    lock = make_lock_entity(coordinator)
    lock._api.async_call = AsyncMock(return_value=None)

    # Pre-condition: vehicle is unlocked
    assert lock.is_locked is False
    assert lock._command_pending is False

    # Issue lock command → optimistic state
    await lock.async_lock()
    assert lock._last_locked is True
    assert lock._command_pending is True
    assert lock.is_locked is True  # optimistic

    # Coordinator update arrives with still-unlocked data (stale cloud) →
    # entity stays optimistic (command not yet confirmed)
    lock._handle_coordinator_update()
    assert lock._command_pending is True
    assert lock.is_locked is True

    # Coordinator update arrives with confirmed locked state
    coordinator.data = {
        "vehicles": {vin: coordinator._vehicle},
        "realtime": {vin: types.SimpleNamespace(is_locked=True)},
    }
    lock._handle_coordinator_update()
    assert lock._command_pending is False
    assert lock.is_locked is True  # confirmed by real data


@pytest.mark.asyncio
async def test_lock_command_rolls_back_on_exception() -> None:
    """A non-remote-control exception rolls back the optimistic lock state."""
    vin = "VIN_LOCK_002"
    coordinator = make_telemetry_coordinator(vin=vin)
    lock = make_lock_entity(coordinator)
    lock._api.async_call = AsyncMock(side_effect=RuntimeError("network error"))

    with pytest.raises(HomeAssistantError):
        await lock.async_lock()

    # Rollback fired: _last_locked reset to None
    assert lock._last_locked is None
