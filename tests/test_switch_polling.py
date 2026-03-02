"""Unit tests for BydDisablePollingSwitch and async_setup_entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.byd_vehicle.switch import (
    BydBatteryHeatSwitch,
    BydCarOnSwitch,
    BydDisablePollingSwitch,
    BydSteeringWheelHeatSwitch,
)


def _make_coordinator(vin: str, realtime=None, hvac=None) -> MagicMock:
    coordinator = MagicMock()
    coordinator.last_update_success = True
    data: dict = {"vehicles": {vin: MagicMock()}}
    if realtime is not None:
        data["realtime"] = {vin: realtime}
    if hvac is not None:
        data["hvac"] = {vin: hvac}
    coordinator.data = data
    coordinator.hvac_command_pending = False
    return coordinator


def _make_disable_polling_switch(gps_coordinator=None) -> BydDisablePollingSwitch:
    vin = "TESTVIN123"
    coordinator = _make_coordinator(vin)
    entity = object.__new__(BydDisablePollingSwitch)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = MagicMock()
    entity._gps_coordinator = gps_coordinator
    entity._attr_unique_id = f"{vin}_switch_disable_polling"
    entity._command_pending = False
    entity._commanded_at = None
    entity._disabled = False
    entity.async_write_ha_state = MagicMock()
    return entity


def _fake_coordinator_init(self, coordinator, **_):
    """Minimal stand-in for CoordinatorEntity.__init__."""
    self.coordinator = coordinator


def test_disable_polling_is_on_false_by_default() -> None:
    entity = _make_disable_polling_switch()
    assert entity.is_on is False


def test_disable_polling_is_on_true_when_disabled() -> None:
    entity = _make_disable_polling_switch()
    entity._disabled = True
    assert entity.is_on is True


def test_disable_polling_available_true_when_vehicle_present() -> None:
    entity = _make_disable_polling_switch()
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is True


def test_disable_polling_available_false_when_vehicle_absent() -> None:
    entity = _make_disable_polling_switch()
    entity.coordinator.data = {"vehicles": {}}
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert entity.available is False


def test_disable_polling_apply_enables_coordinator() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    gps = MagicMock()
    gps.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch(gps_coordinator=gps)
    entity.coordinator = coordinator
    entity._disabled = False
    entity._apply()
    coordinator.set_polling_enabled.assert_called_once_with(True)
    gps.set_polling_enabled.assert_called_once_with(True)


def test_disable_polling_apply_disables_coordinator() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch(gps_coordinator=None)
    entity.coordinator = coordinator
    entity._disabled = True
    entity._apply()
    coordinator.set_polling_enabled.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_disable_polling_turn_on_disables() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch()
    entity.coordinator = coordinator
    await entity.async_turn_on()
    assert entity._disabled is True
    coordinator.set_polling_enabled.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_disable_polling_turn_off_enables() -> None:
    coordinator = MagicMock()
    coordinator.set_polling_enabled = MagicMock()
    entity = _make_disable_polling_switch()
    entity.coordinator = coordinator
    entity._disabled = True
    await entity.async_turn_off()
    assert entity._disabled is False
    coordinator.set_polling_enabled.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_switch_async_setup_entry_no_vehicles() -> None:
    """Cover lines 31-49: async_setup_entry skips when vehicle is None."""
    from custom_components.byd_vehicle.const import DOMAIN
    from custom_components.byd_vehicle.switch import async_setup_entry

    vin = "TESTVIN123"
    coordinator = MagicMock()
    coordinator.data = {"vehicles": {}}  # vehicle is None → skip

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {vin: coordinator},
                "gps_coordinators": {},
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
async def test_switch_async_setup_entry_creates_entities() -> None:
    """Cover lines 31-49 + __init__ lines: entities created when vehicle found."""
    from custom_components.byd_vehicle.const import DOMAIN
    from custom_components.byd_vehicle.switch import (
        BydBatteryHeatSwitch,
        BydCarOnSwitch,
        BydDisablePollingSwitch,
        BydSteeringWheelHeatSwitch,
        async_setup_entry,
    )

    vin = "TESTVIN123"
    vehicle_mock = MagicMock()
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"vehicles": {vin: vehicle_mock}}

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {vin: coordinator},
                "gps_coordinators": {},
                "api": MagicMock(),
            }
        }
    }
    entry = MagicMock()
    entry.entry_id = "entry1"
    async_add_entities = MagicMock()

    with patch.object(BydBatteryHeatSwitch, "__init__", return_value=None), patch.object(
        BydCarOnSwitch, "__init__", return_value=None
    ), patch.object(
        BydSteeringWheelHeatSwitch, "__init__", return_value=None
    ), patch.object(
        BydDisablePollingSwitch, "__init__", return_value=None
    ):
        await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 4  # 1 disable-polling + 3 control switches


def test_disable_polling_switch_init() -> None:
    """Cover switch.py lines 378-383: BydDisablePollingSwitch.__init__."""
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    coordinator = MagicMock()
    gps_coordinator = MagicMock()
    vin = "TESTVIN123"
    vehicle = MagicMock()

    with patch.object(CoordinatorEntity, "__init__", new=_fake_coordinator_init):
        sw = BydDisablePollingSwitch(coordinator, gps_coordinator, vin, vehicle)

    assert sw._vin == vin
    assert sw._vehicle is vehicle
    assert sw._gps_coordinator is gps_coordinator
    assert sw._attr_unique_id == f"{vin}_switch_disable_polling"
    assert sw._disabled is False


@pytest.mark.asyncio
async def test_disable_polling_async_added_to_hass_restores_on_state() -> None:
    """Cover switch.py lines 387-391: async_added_to_hass restores 'on' state."""
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    vin = "TESTVIN123"
    entity = _make_disable_polling_switch()
    entity.coordinator.set_polling_enabled = MagicMock()

    last_state = MagicMock()
    last_state.state = "on"
    entity.async_get_last_state = AsyncMock(return_value=last_state)

    with patch.object(CoordinatorEntity, "async_added_to_hass", new=AsyncMock()):
        await entity.async_added_to_hass()

    assert entity._disabled is True


@pytest.mark.asyncio
async def test_disable_polling_async_added_to_hass_no_previous_state() -> None:
    """Cover switch.py line 389: async_added_to_hass when last state is None."""
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    entity = _make_disable_polling_switch()
    entity.coordinator.set_polling_enabled = MagicMock()
    entity.async_get_last_state = AsyncMock(return_value=None)

    with patch.object(CoordinatorEntity, "async_added_to_hass", new=AsyncMock()):
        await entity.async_added_to_hass()

    assert entity._disabled is False
