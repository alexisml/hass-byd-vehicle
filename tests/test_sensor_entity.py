"""Unit tests for BydSensor setup entry and __init__ logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.byd_vehicle.sensor import (
    BydSensor,
    BydSensorDescription,
)


def _make_sensor(
    data: dict | None = None,
    key: str = "test_sensor",
    source: str = "realtime",
    attr_key: str | None = None,
    value_fn=None,
    validator_fn=None,
) -> BydSensor:
    """Create a BydSensor without a running HA instance."""
    vin = "TESTVIN123"
    desc = BydSensorDescription(
        key=key,
        source=source,
        attr_key=attr_key,
        value_fn=value_fn,
        validator_fn=validator_fn,
    )
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = data or {"vehicles": {vin: MagicMock()}}

    sensor = object.__new__(BydSensor)
    sensor.coordinator = coordinator
    sensor._vin = vin
    sensor._vehicle = MagicMock()
    sensor.entity_description = desc
    sensor._attr_unique_id = f"{vin}_{source}_{key}"
    sensor._last_native_value = None
    sensor._command_pending = False
    sensor._commanded_at = None
    sensor.async_write_ha_state = MagicMock()
    return sensor


def _fake_coordinator_init(self, coordinator, **_):
    """Minimal stand-in for CoordinatorEntity.__init__."""
    self.coordinator = coordinator


# ---------------------------------------------------------------------------
# async_setup_entry (lines 530-549)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensor_async_setup_entry_no_vehicles() -> None:
    """Cover lines 530-549: async_setup_entry skips when vehicle is None."""
    from custom_components.byd_vehicle.const import DOMAIN
    from custom_components.byd_vehicle.sensor import async_setup_entry

    vin = "TESTVIN123"
    coordinator = MagicMock()
    coordinator.data = {"vehicles": {}}  # vehicle is None → skip

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {vin: coordinator},
                "gps_coordinators": {},
            }
        }
    }
    entry = MagicMock()
    entry.entry_id = "entry1"
    async_add_entities = MagicMock()

    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([])


@pytest.mark.asyncio
async def test_sensor_async_setup_entry_creates_entities() -> None:
    """Cover lines 530-549 + 580-594: entities created when vehicle found."""
    from custom_components.byd_vehicle.const import DOMAIN
    from custom_components.byd_vehicle.sensor import (
        SENSOR_DESCRIPTIONS,
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
            }
        }
    }
    entry = MagicMock()
    entry.entry_id = "entry1"
    async_add_entities = MagicMock()

    with patch.object(BydSensor, "__init__", return_value=None):
        await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    # All non-gps_last_updated sensors (gps_last_updated skipped
    # when no gps_coordinator)
    gps_count = sum(1 for d in SENSOR_DESCRIPTIONS if d.key == "gps_last_updated")
    expected_count = len(SENSOR_DESCRIPTIONS) - gps_count
    assert len(entities) == expected_count


# ---------------------------------------------------------------------------
# BydSensor.__init__ auto-disable logic (lines 580-594)
# ---------------------------------------------------------------------------


def test_sensor_init_auto_disables_when_no_value() -> None:
    """Cover sensor.py lines 580-594: BydSensor.__init__ auto-disables entity."""
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    from custom_components.byd_vehicle.sensor import SENSOR_DESCRIPTIONS, BydSensor

    # Pick a non-gps sensor description
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key != "gps_last_updated")
    vin = "TESTVIN123"
    # No source data → _resolve_validated_value returns None → auto-disable
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"vehicles": {vin: MagicMock()}}
    vehicle = MagicMock()

    with patch.object(CoordinatorEntity, "__init__", new=_fake_coordinator_init):
        sensor = BydSensor(coordinator, vin, vehicle, desc)

    assert sensor._attr_entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# async_setup_entry: gps_coordinator present path (line 543)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sensor_async_setup_entry_with_gps_coordinator() -> None:
    """Cover BydSensor created for gps_last_updated when gps_coordinator exists."""
    from custom_components.byd_vehicle.const import DOMAIN
    from custom_components.byd_vehicle.sensor import (
        SENSOR_DESCRIPTIONS,
        BydSensor,
        async_setup_entry,
    )

    vin = "TESTVIN123"
    vehicle_mock = MagicMock()
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"vehicles": {vin: vehicle_mock}}

    gps_coordinator = MagicMock()
    gps_coordinator.last_update_success = True
    gps_coordinator.data = {"vehicles": {vin: vehicle_mock}}

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {vin: coordinator},
                "gps_coordinators": {vin: gps_coordinator},
            }
        }
    }
    entry = MagicMock()
    entry.entry_id = "entry1"
    async_add_entities = MagicMock()

    with patch.object(BydSensor, "__init__", return_value=None):
        await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    # All descriptions including gps_last_updated (gps_coordinator exists)
    assert len(entities) == len(SENSOR_DESCRIPTIONS)
