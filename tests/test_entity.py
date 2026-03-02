"""Unit tests for entity module."""

from __future__ import annotations

from time import monotonic
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd import BydRemoteControlError

from custom_components.byd_vehicle.entity import (
    _OPTIMISTIC_TTL_SECONDS,
    BydVehicleEntity,
)


def test_optimistic_ttl() -> None:
    assert _OPTIMISTIC_TTL_SECONDS == 300.0


# ---------------------------------------------------------------------------
# Helper: create a minimal BydVehicleEntity instance that bypasses the HA
# CoordinatorEntity.__init__ (which requires a running HA event loop).
# ---------------------------------------------------------------------------


class _ConcreteEntity(BydVehicleEntity):
    """Minimal concrete subclass so BydVehicleEntity can be instantiated."""


def _make_entity(coordinator_data: dict | None = None) -> _ConcreteEntity:
    coordinator = MagicMock()
    coordinator.data = coordinator_data or {}
    coordinator.last_update_success = True
    vehicle = MagicMock()
    vehicle.model_name = "BYD Atto 3"
    vehicle.brand_name = "BYD"
    vehicle.tbox_version = "1.0"
    entity = object.__new__(_ConcreteEntity)
    entity.coordinator = coordinator
    entity._vin = "TESTVIN1234567"
    entity._vehicle = vehicle
    entity._command_pending = False
    entity._commanded_at = None
    entity.async_write_ha_state = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# device_info
# ---------------------------------------------------------------------------


def test_device_info_identifiers() -> None:
    entity = _make_entity()
    info = entity.device_info
    assert ("byd_vehicle", "TESTVIN1234567") in info["identifiers"]


def test_device_info_manufacturer() -> None:
    entity = _make_entity()
    info = entity.device_info
    assert info["manufacturer"] == "BYD"


def test_device_info_model() -> None:
    entity = _make_entity()
    info = entity.device_info
    assert info["model"] == "BYD Atto 3"


def test_device_info_no_brand_falls_back() -> None:
    entity = _make_entity()
    entity._vehicle.brand_name = None
    info = entity.device_info
    assert info["manufacturer"] == "BYD"


# ---------------------------------------------------------------------------
# extra_state_attributes
# ---------------------------------------------------------------------------


def test_extra_state_attributes_contains_vin() -> None:
    entity = _make_entity()
    assert entity.extra_state_attributes == {"vin": "TESTVIN1234567"}


# ---------------------------------------------------------------------------
# available
# ---------------------------------------------------------------------------


def test_available_true_when_vin_in_vehicles() -> None:
    vehicle_mock = MagicMock()
    entity = _make_entity({"vehicles": {"TESTVIN1234567": vehicle_mock}})
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is True


def test_available_false_when_vin_missing() -> None:
    entity = _make_entity({"vehicles": {}})
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is False


def test_available_false_when_super_unavailable() -> None:
    """Cover entity.py line 59: return False when super().available is False."""
    entity = _make_entity({"vehicles": {"TESTVIN1234567": MagicMock()}})
    prop = property(lambda self: False)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is False


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def test_get_hvac_status_none_when_missing() -> None:
    entity = _make_entity({})
    assert entity._get_hvac_status() is None


def test_get_realtime_none_when_missing() -> None:
    entity = _make_entity({})
    assert entity._get_realtime() is None


def test_get_gps_none_when_missing() -> None:
    entity = _make_entity({})
    assert entity._get_gps() is None


def test_get_source_obj_none_when_missing() -> None:
    entity = _make_entity({})
    assert entity._get_source_obj("realtime") is None


def test_get_realtime_returns_value() -> None:
    rt = MagicMock()
    entity = _make_entity({"realtime": {"TESTVIN1234567": rt}})
    assert entity._get_realtime() is rt


def test_is_vehicle_on_false_when_no_realtime() -> None:
    entity = _make_entity({})
    assert entity._is_vehicle_on() is False


def test_is_vehicle_on_true() -> None:
    rt = MagicMock()
    rt.is_vehicle_on = True
    entity = _make_entity({"realtime": {"TESTVIN1234567": rt}})
    assert entity._is_vehicle_on() is True


# ---------------------------------------------------------------------------
# _is_command_confirmed / _handle_coordinator_update
# ---------------------------------------------------------------------------


def test_is_command_confirmed_default_true() -> None:
    entity = _make_entity()
    assert entity._is_command_confirmed() is True


def test_handle_coordinator_update_clears_when_confirmed() -> None:
    entity = _make_entity()
    entity._command_pending = True
    entity._commanded_at = monotonic()
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()
    assert entity._command_pending is False


def test_handle_coordinator_update_clears_on_ttl_expiry() -> None:
    entity = _make_entity()
    entity._command_pending = True
    entity._commanded_at = monotonic() - (_OPTIMISTIC_TTL_SECONDS + 1)

    class _NeverConfirmed(_ConcreteEntity):
        def _is_command_confirmed(self) -> bool:
            return False

    entity.__class__ = _NeverConfirmed
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()
    assert entity._command_pending is False


def test_handle_coordinator_update_no_pending_no_clear() -> None:
    entity = _make_entity()
    entity._command_pending = False
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()
    assert entity._command_pending is False


# ---------------------------------------------------------------------------
# _execute_command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_command_success() -> None:
    entity = _make_entity()
    api = AsyncMock()
    api.async_call = AsyncMock()
    await entity._execute_command(api, MagicMock(), command="test_cmd")
    assert entity._command_pending is True
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_execute_command_remote_control_error_optimistic() -> None:
    entity = _make_entity()
    api = AsyncMock()
    api.async_call = AsyncMock(side_effect=BydRemoteControlError("fail"))
    await entity._execute_command(api, MagicMock(), command="test_cmd")
    # Still treated as success (optimistic)
    assert entity._command_pending is True


@pytest.mark.asyncio
async def test_execute_command_generic_error_raises() -> None:
    entity = _make_entity()
    api = AsyncMock()
    api.async_call = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(HomeAssistantError):
        await entity._execute_command(api, MagicMock(), command="test_cmd")
    assert entity._command_pending is False


@pytest.mark.asyncio
async def test_execute_command_calls_rollback_on_error() -> None:
    entity = _make_entity()
    api = AsyncMock()
    api.async_call = AsyncMock(side_effect=RuntimeError("boom"))
    rollback = MagicMock()
    with pytest.raises(HomeAssistantError):
        await entity._execute_command(
            api, MagicMock(), command="test_cmd", on_rollback=rollback
        )
    rollback.assert_called_once()
