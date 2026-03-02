"""Unit tests for button descriptions and entity properties."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.byd_vehicle.button import (
    BUTTON_DESCRIPTIONS,
    BydButton,
    BydForcePollButton,
)


def test_button_descriptions_nonempty() -> None:
    assert isinstance(BUTTON_DESCRIPTIONS, tuple)
    assert len(BUTTON_DESCRIPTIONS) > 0


def test_button_descriptions_have_key_and_method() -> None:
    for desc in BUTTON_DESCRIPTIONS:
        assert isinstance(desc.key, str) and desc.key
        assert isinstance(desc.method, str) and desc.method


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_button(vin: str = "TESTVIN123", has_vehicle: bool = True) -> BydButton:
    desc = BUTTON_DESCRIPTIONS[0]
    coordinator = MagicMock()
    coordinator.last_update_success = True
    data: dict = {"vehicles": {vin: MagicMock()} if has_vehicle else {}}
    coordinator.data = data

    entity = object.__new__(BydButton)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._api = AsyncMock()
    entity._api.async_call = AsyncMock()
    entity.entity_description = desc
    entity._attr_unique_id = f"{vin}_button_{desc.key}"
    entity._command_pending = False
    entity._commanded_at = None
    entity.async_write_ha_state = MagicMock()
    return entity


def _make_force_poll_button(
    vin: str = "TESTVIN123", has_vehicle: bool = True, gps_coordinator=None
) -> BydForcePollButton:
    coordinator = MagicMock()
    coordinator.last_update_success = True
    data: dict = {"vehicles": {vin: MagicMock()} if has_vehicle else {}}
    coordinator.data = data

    entity = object.__new__(BydForcePollButton)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._gps_coordinator = gps_coordinator
    entity._attr_unique_id = f"{vin}_button_force_poll"
    entity._command_pending = False
    entity._commanded_at = None
    entity.async_write_ha_state = MagicMock()
    return entity


# ---------------------------------------------------------------------------
# BydButton tests
# ---------------------------------------------------------------------------


def test_button_available_true_when_vehicle_present() -> None:
    entity = _make_button(has_vehicle=True)
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is True


def test_button_available_false_when_vehicle_absent() -> None:
    entity = _make_button(has_vehicle=False)
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is False


@pytest.mark.asyncio
async def test_button_press_success() -> None:
    entity = _make_button()
    entity._api.async_call = AsyncMock()
    await entity.async_press()
    entity._api.async_call.assert_called_once()


@pytest.mark.asyncio
async def test_button_press_generic_error_raises() -> None:
    entity = _make_button()
    entity._api.async_call = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(HomeAssistantError):
        await entity.async_press()


# ---------------------------------------------------------------------------
# BydForcePollButton tests
# ---------------------------------------------------------------------------


def test_force_poll_available_true_when_vehicle_present() -> None:
    entity = _make_force_poll_button(has_vehicle=True)
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is True


def test_force_poll_available_false_when_vehicle_absent() -> None:
    entity = _make_force_poll_button(has_vehicle=False)
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is False


@pytest.mark.asyncio
async def test_force_poll_press_calls_coordinator_refresh() -> None:
    entity = _make_force_poll_button()
    entity.coordinator.async_force_refresh = AsyncMock()
    await entity.async_press()
    entity.coordinator.async_force_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_force_poll_press_calls_gps_refresh_if_present() -> None:
    gps = MagicMock()
    gps.async_force_refresh = AsyncMock()
    entity = _make_force_poll_button(gps_coordinator=gps)
    entity.coordinator.async_force_refresh = AsyncMock()
    await entity.async_press()
    gps.async_force_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_force_poll_press_raises_on_error() -> None:
    entity = _make_force_poll_button()
    entity.coordinator.async_force_refresh = AsyncMock(
        side_effect=RuntimeError("fail")
    )
    with pytest.raises(HomeAssistantError):
        await entity.async_press()


@pytest.mark.asyncio
async def test_button_press_remote_control_error_is_silent() -> None:
    from pybyd import BydRemoteControlError

    entity = _make_button()
    entity._api.async_call = AsyncMock(side_effect=BydRemoteControlError("nack"))
    # Should not raise - log warning and return
    await entity.async_press()


# ---------------------------------------------------------------------------
# Covering the _call closure paths inside async_press (lines 114-117)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_button_press_call_with_method_none_raises() -> None:
    """Lines 114-116: getattr returns None when method not found on client."""
    entity = _make_button()

    async def invoke_handler(handler, **kwargs):
        client = MagicMock(spec=[])  # spec=[] → getattr returns None
        return await handler(client)

    entity._api.async_call = invoke_handler
    with pytest.raises(HomeAssistantError):
        await entity.async_press()


@pytest.mark.asyncio
async def test_button_press_call_with_method_present_succeeds() -> None:
    """Line 117: return await method(self._vin) when method exists."""
    entity = _make_button()
    method_name = entity.entity_description.method

    async def invoke_handler(handler, **kwargs):
        client = MagicMock()
        setattr(client, method_name, AsyncMock(return_value=None))
        return await handler(client)

    entity._api.async_call = invoke_handler
    # Should not raise
    await entity.async_press()
