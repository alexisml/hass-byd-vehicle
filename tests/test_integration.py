"""Integration tests for BYD Vehicle — multi-component flows.

These tests exercise real interactions between several components at
once rather than isolating a single class.  Each scenario drives a
realistic end-to-end path through the integration:

  1. MQTT push  → coordinator → entity state propagation
  2. Coordinator data → multiple entity types reading the same state
  3. Lock command → optimistic state → coordinator confirmation cycle
  4. Service call routing through _resolve_vins / _get_coordinators
  5. GPS smart-polling interval driven by telemetry vehicle-on state
  6. Full async_setup_entry with multiple vehicles
"""

from __future__ import annotations

import types
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.byd_vehicle import (
    _async_register_services,
    _get_coordinators,
    _resolve_vins_from_call,
)
from custom_components.byd_vehicle.binary_sensor import BydBinarySensor
from custom_components.byd_vehicle.coordinator import (
    BydDataUpdateCoordinator,
    BydGpsUpdateCoordinator,
)
from custom_components.byd_vehicle.lock import BydLock
from custom_components.byd_vehicle.sensor import BydSensor, BydSensorDescription
from custom_components.byd_vehicle.const import (
    CONF_DEVICE_PROFILE,
    CONF_GPS_ACTIVE_INTERVAL,
    CONF_GPS_INACTIVE_INTERVAL,
    CONF_GPS_POLL_INTERVAL,
    CONF_POLL_INTERVAL,
    CONF_SMART_GPS_POLLING,
    DEFAULT_GPS_ACTIVE_INTERVAL,
    DEFAULT_GPS_INACTIVE_INTERVAL,
    DEFAULT_GPS_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SMART_GPS_POLLING,
    DOMAIN,
)


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _make_telemetry_coordinator(
    vin: str = "TESTVIN123456",
    data: dict | None = None,
) -> BydDataUpdateCoordinator:
    """Create a BydDataUpdateCoordinator bypassing __init__."""
    coordinator = object.__new__(BydDataUpdateCoordinator)
    coordinator._api = MagicMock()
    coordinator._vin = vin
    coordinator._vehicle = MagicMock()
    coordinator._fixed_interval = timedelta(seconds=60)
    coordinator._polling_enabled = True
    coordinator._force_next_refresh = False
    coordinator._last_realtime = None
    coordinator._last_hvac = None
    coordinator._optimistic_hvac_until = None
    coordinator._optimistic_ac_expected = None
    coordinator._realtime_endpoint_unsupported = False
    coordinator.update_interval = timedelta(seconds=60)
    coordinator.last_update_success = True
    coordinator.async_set_updated_data = MagicMock()
    coordinator.data = data or {"vehicles": {vin: coordinator._vehicle}}
    return coordinator


def _make_gps_coordinator(
    vin: str = "TESTVIN123456",
    telemetry: BydDataUpdateCoordinator | None = None,
    smart_polling: bool = False,
    active_interval: int = 30,
    inactive_interval: int = 600,
    poll_interval: int = 300,
) -> BydGpsUpdateCoordinator:
    """Create a BydGpsUpdateCoordinator bypassing __init__."""
    gps = object.__new__(BydGpsUpdateCoordinator)
    gps._api = MagicMock()
    gps._vin = vin
    gps._vehicle = MagicMock()
    gps._telemetry_coordinator = telemetry
    gps._smart_polling = smart_polling
    gps._fixed_interval = timedelta(seconds=poll_interval)
    gps._active_interval = timedelta(seconds=active_interval)
    gps._inactive_interval = timedelta(seconds=inactive_interval)
    gps._current_interval = timedelta(seconds=poll_interval)
    gps._polling_enabled = True
    gps._force_next_refresh = False
    gps._last_gps = None
    gps.update_interval = timedelta(seconds=poll_interval)
    gps.last_update_success = True
    gps.async_set_updated_data = MagicMock()
    gps.data = {"vehicles": {vin: gps._vehicle}}
    return gps


def _make_lock_entity(coordinator: BydDataUpdateCoordinator) -> BydLock:
    """Create a BydLock wired to *coordinator*."""
    vin = coordinator._vin
    entity = object.__new__(BydLock)
    entity.coordinator = coordinator
    entity._vin = vin
    entity._vehicle = coordinator._vehicle
    entity._api = MagicMock()
    entity._api.async_call = AsyncMock()
    entity._attr_unique_id = f"{vin}_lock"
    entity._command_pending = False
    entity._commanded_at = None
    entity._last_command = None
    entity._last_locked = None
    entity.async_write_ha_state = MagicMock()
    return entity


def _make_sensor_entity(
    coordinator: BydDataUpdateCoordinator,
    key: str = "elec_percent",
    source: str = "realtime",
    attr_key: str | None = None,
    value_fn=None,
) -> BydSensor:
    """Create a BydSensor wired to *coordinator*."""
    vin = coordinator._vin
    desc = BydSensorDescription(
        key=key,
        source=source,
        attr_key=attr_key,
        value_fn=value_fn,
    )
    sensor = object.__new__(BydSensor)
    sensor.coordinator = coordinator
    sensor._vin = vin
    sensor._vehicle = coordinator._vehicle
    sensor.entity_description = desc
    sensor._attr_unique_id = f"{vin}_{source}_{key}"
    sensor._last_native_value = None
    sensor._command_pending = False
    sensor._commanded_at = None
    sensor.async_write_ha_state = MagicMock()
    return sensor


# ---------------------------------------------------------------------------
# 1. MQTT push → coordinator → entity state propagation
#
# Tests that BydApi._handle_vehicle_info dispatches into the coordinator,
# which then updates its data, and entities subsequently reflect the
# new realtime state — no HA event loop required.
# ---------------------------------------------------------------------------


def test_mqtt_push_updates_coordinator_and_sensor() -> None:
    """An MQTT vehicleInfo push propagates to the coordinator and sensor."""
    from pybyd.models.realtime import VehicleRealtimeData

    vin = "VIN_MQTT_001"
    coordinator = _make_telemetry_coordinator(vin=vin)
    coordinator.data = {"vehicles": {vin: coordinator._vehicle}}

    # Wire a real async_set_updated_data side-effect so data is mutated.
    received: list[dict] = []

    def _capture(new_data):
        coordinator.data = new_data
        received.append(new_data)

    coordinator.async_set_updated_data = _capture

    # Create the sensor before the push.
    sensor = _make_sensor_entity(coordinator, key="elec_percent", source="realtime")

    # Simulate an MQTT push via BydApi._handle_vehicle_info.
    from custom_components.byd_vehicle.coordinator import BydApi

    api = object.__new__(BydApi)
    api._coordinators = {vin: coordinator}
    api._debug_dumps_enabled = False
    api._hass = MagicMock()

    rt = MagicMock(spec=VehicleRealtimeData)
    rt.elec_percent = 82
    api._handle_vehicle_info(vin, rt)

    # coordinator received the realtime data
    assert coordinator._last_realtime is rt
    assert len(received) == 1
    assert received[0]["realtime"][vin] is rt

    # sensor now reads the new value from coordinator data
    assert sensor.coordinator.data["realtime"][vin].elec_percent == 82


def test_mqtt_push_for_unknown_vin_does_not_raise() -> None:
    """A vehicleInfo push for an unknown VIN is silently ignored."""
    from pybyd.models.realtime import VehicleRealtimeData
    from custom_components.byd_vehicle.coordinator import BydApi

    api = object.__new__(BydApi)
    api._coordinators = {}
    api._debug_dumps_enabled = False
    api._hass = MagicMock()

    rt = MagicMock(spec=VehicleRealtimeData)
    # Should not raise
    api._handle_vehicle_info("UNKNOWN_VIN", rt)


# ---------------------------------------------------------------------------
# 2. Coordinator data → multiple entity types reading the same state
#
# After a single coordinator data update, a BydSensor, a BydBinarySensor,
# and a BydLock all derive their state from the same dict — verifying that
# the shared data model flows through every entity type.
# ---------------------------------------------------------------------------


def test_multi_entity_types_share_coordinator_data() -> None:
    """Sensor, binary sensor, and lock all read the same coordinator data."""
    from pybyd.models.realtime import VehicleRealtimeData
    from custom_components.byd_vehicle.binary_sensor import (
        BINARY_SENSOR_DESCRIPTIONS,
        BydBinarySensor,
    )

    vin = "VIN_MULTI_001"
    rt = types.SimpleNamespace(
        elec_percent=65,
        is_locked=False,
        is_charging=True,
        charge_state=None,
        is_charger_connected=None,
    )
    data = {
        "vehicles": {vin: MagicMock()},
        "realtime": {vin: rt},
    }
    coordinator = _make_telemetry_coordinator(vin=vin, data=data)

    # --- BydSensor (battery %)
    sensor = _make_sensor_entity(coordinator, key="elec_percent", source="realtime")
    assert sensor._get_source_obj("realtime") is rt

    # --- BydBinarySensor (charging)
    charging_desc = next(
        d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "is_charging"
    )
    binary = object.__new__(BydBinarySensor)
    binary.coordinator = coordinator
    binary._vin = vin
    binary._vehicle = MagicMock()
    binary.entity_description = charging_desc
    binary._attr_unique_id = f"{vin}_charging"
    binary._command_pending = False
    binary._commanded_at = None
    binary.async_write_ha_state = MagicMock()
    assert binary.is_on is True  # is_charging=True

    # --- BydLock
    lock = _make_lock_entity(coordinator)
    assert lock.is_locked is False


def test_multi_entity_types_reflect_updated_coordinator_data() -> None:
    """After a coordinator data change, all entities see the new state."""
    vin = "VIN_MULTI_002"
    rt_initial = types.SimpleNamespace(is_locked=True, elec_percent=50)
    data = {
        "vehicles": {vin: MagicMock()},
        "realtime": {vin: rt_initial},
    }
    coordinator = _make_telemetry_coordinator(vin=vin, data=data)

    sensor = _make_sensor_entity(coordinator, key="elec_percent", source="realtime")
    lock = _make_lock_entity(coordinator)

    # Verify initial state
    assert sensor._get_source_obj("realtime").elec_percent == 50
    assert lock.is_locked is True

    # Simulate a coordinator data update (e.g. after a poll)
    rt_new = types.SimpleNamespace(is_locked=False, elec_percent=75)
    coordinator.data = {
        "vehicles": {vin: coordinator._vehicle},
        "realtime": {vin: rt_new},
    }

    # Both entities now read the updated data
    assert sensor._get_source_obj("realtime").elec_percent == 75
    assert lock.is_locked is False


# ---------------------------------------------------------------------------
# 3. Lock command → optimistic state → coordinator confirmation cycle
#
# Exercises the full round-trip:
#   async_lock() sets optimistic state
#   → coordinator push contradicts (ignored while command_pending)
#   → coordinator push confirms → flag clears
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_command_optimistic_then_confirmed() -> None:
    """Lock command holds optimistic state until coordinator confirms it."""
    vin = "VIN_LOCK_001"
    rt_unlocked = types.SimpleNamespace(is_locked=False)
    data = {
        "vehicles": {vin: MagicMock()},
        "realtime": {vin: rt_unlocked},
    }
    coordinator = _make_telemetry_coordinator(vin=vin, data=data)
    lock = _make_lock_entity(coordinator)
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
    from homeassistant.exceptions import HomeAssistantError

    vin = "VIN_LOCK_002"
    coordinator = _make_telemetry_coordinator(vin=vin)
    lock = _make_lock_entity(coordinator)
    lock._api.async_call = AsyncMock(side_effect=RuntimeError("network error"))

    with pytest.raises(HomeAssistantError):
        await lock.async_lock()

    # Rollback fired: _last_locked reset to None
    assert lock._last_locked is None


# ---------------------------------------------------------------------------
# 4. Service call routing: _resolve_vins_from_call → _get_coordinators
#
# Verifies the service-dispatch pipeline uses the correct data from
# hass.data to route calls to the right coordinator instances.
# ---------------------------------------------------------------------------


def test_resolve_vins_returns_entry_vin_pair() -> None:
    """_resolve_vins_from_call resolves device → entry_id, vin correctly."""
    from homeassistant.helpers import device_registry as dr

    vin = "VIN_SVC_001"
    entry_id = "entry_svc_1"
    device_id = "device_abc"

    # Build a fake device with the right identifier
    fake_device = MagicMock()
    fake_device.identifiers = {(DOMAIN, vin)}

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: MagicMock()},
            }
        }
    }

    call = MagicMock()
    call.data = {"device_id": device_id}

    with patch.object(dr, "async_get") as mock_reg:
        mock_reg.return_value.async_get.return_value = fake_device
        results = _resolve_vins_from_call(hass, call)

    assert (entry_id, vin) in results


def test_get_coordinators_returns_telemetry_and_gps() -> None:
    """_get_coordinators returns the correct (telemetry, gps) tuple."""
    vin = "VIN_SVC_002"
    entry_id = "entry_svc_2"

    telemetry_coord = MagicMock()
    gps_coord = MagicMock()

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: telemetry_coord},
                "gps_coordinators": {vin: gps_coord},
            }
        }
    }

    telemetry, gps = _get_coordinators(hass, entry_id, vin)
    assert telemetry is telemetry_coord
    assert gps is gps_coord


def test_get_coordinators_gps_none_when_not_present() -> None:
    """_get_coordinators returns None for gps when no GPS coordinator exists."""
    vin = "VIN_SVC_003"
    entry_id = "entry_svc_3"

    telemetry_coord = MagicMock()

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: telemetry_coord},
                # no gps_coordinators key
            }
        }
    }

    telemetry, gps = _get_coordinators(hass, entry_id, vin)
    assert telemetry is telemetry_coord
    assert gps is None


@pytest.mark.asyncio
async def test_service_fetch_realtime_reaches_coordinator() -> None:
    """Registered fetch_realtime service handler calls coordinator.async_fetch_realtime."""
    vin = "VIN_SVC_004"
    device_id = "dev_svc_004"
    entry_id = "entry_svc_4"

    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = False

    captured: dict = {}

    def _register(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = _register
    _async_register_services(hass)

    coordinator = MagicMock()
    coordinator.async_fetch_realtime = AsyncMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[(entry_id, vin)],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(coordinator, None),
    ):
        call = MagicMock()
        await captured["fetch_realtime"](call)

    coordinator.async_fetch_realtime.assert_called_once()


@pytest.mark.asyncio
async def test_service_fetch_gps_reaches_gps_coordinator() -> None:
    """Registered fetch_gps service handler calls gps.async_fetch_gps."""
    vin = "VIN_SVC_005"
    entry_id = "entry_svc_5"

    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = False

    captured: dict = {}

    def _register(domain, service, handler):
        captured[service] = handler

    hass.services.async_register = _register
    _async_register_services(hass)

    gps_coord = MagicMock()
    gps_coord.async_fetch_gps = AsyncMock()

    with patch(
        "custom_components.byd_vehicle._resolve_vins_from_call",
        return_value=[(entry_id, vin)],
    ), patch(
        "custom_components.byd_vehicle._get_coordinators",
        return_value=(MagicMock(), gps_coord),
    ):
        await captured["fetch_gps"](MagicMock())

    gps_coord.async_fetch_gps.assert_called_once()


# ---------------------------------------------------------------------------
# 5. GPS smart-polling interval driven by telemetry vehicle-on state
#
# BydGpsUpdateCoordinator._adjust_interval() switches between the active
# and inactive intervals based on BydDataUpdateCoordinator.is_vehicle_on.
# ---------------------------------------------------------------------------


def test_gps_interval_active_when_vehicle_on() -> None:
    """Smart GPS polling uses the active interval when the vehicle is on."""
    vin = "VIN_GPS_001"
    telemetry = _make_telemetry_coordinator(vin=vin)
    # Simulate vehicle-on
    rt = MagicMock()
    rt.is_vehicle_on = True
    telemetry._last_realtime = rt

    gps = _make_gps_coordinator(
        vin=vin,
        telemetry=telemetry,
        smart_polling=True,
        active_interval=30,
        inactive_interval=600,
    )
    gps._adjust_interval()

    assert gps.update_interval == timedelta(seconds=30)
    assert gps._current_interval == timedelta(seconds=30)


def test_gps_interval_inactive_when_vehicle_off() -> None:
    """Smart GPS polling uses the inactive interval when the vehicle is off."""
    vin = "VIN_GPS_002"
    telemetry = _make_telemetry_coordinator(vin=vin)
    # Vehicle is off (no realtime data)
    telemetry._last_realtime = None

    gps = _make_gps_coordinator(
        vin=vin,
        telemetry=telemetry,
        smart_polling=True,
        active_interval=30,
        inactive_interval=600,
    )
    gps._adjust_interval()

    assert gps.update_interval == timedelta(seconds=600)
    assert gps._current_interval == timedelta(seconds=600)


def test_gps_interval_fixed_when_smart_polling_disabled() -> None:
    """Without smart polling the GPS coordinator always uses the fixed interval."""
    vin = "VIN_GPS_003"
    telemetry = _make_telemetry_coordinator(vin=vin)
    rt = MagicMock()
    rt.is_vehicle_on = True
    telemetry._last_realtime = rt

    gps = _make_gps_coordinator(
        vin=vin,
        telemetry=telemetry,
        smart_polling=False,
        active_interval=30,
        inactive_interval=600,
        poll_interval=120,
    )
    gps._adjust_interval()

    assert gps.update_interval == timedelta(seconds=120)


def test_gps_smart_polling_switches_interval_on_vehicle_state_change() -> None:
    """GPS interval adapts when vehicle state transitions from off to on."""
    vin = "VIN_GPS_004"
    telemetry = _make_telemetry_coordinator(vin=vin)
    telemetry._last_realtime = None  # initially off

    gps = _make_gps_coordinator(
        vin=vin,
        telemetry=telemetry,
        smart_polling=True,
        active_interval=30,
        inactive_interval=600,
    )

    # Initially off → inactive interval
    gps._adjust_interval()
    assert gps._current_interval == timedelta(seconds=600)

    # Vehicle turns on
    rt = MagicMock()
    rt.is_vehicle_on = True
    telemetry._last_realtime = rt

    gps._adjust_interval()
    assert gps._current_interval == timedelta(seconds=30)


# ---------------------------------------------------------------------------
# 6. Full async_setup_entry with multiple vehicles
#
# Drives async_setup_entry from __init__.py with a mocked API returning
# two vehicles and verifies that coordinators and gps_coordinators are
# populated for each VIN.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_entry_multi_vehicle_creates_coordinators() -> None:
    """async_setup_entry creates one telemetry + GPS coordinator per vehicle."""
    from custom_components.byd_vehicle import async_setup_entry

    hass = MagicMock()
    hass.data = {}
    hass.config.time_zone = "UTC"
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=None)

    vin_a = "VIN_SETUP_AAA"
    vin_b = "VIN_SETUP_BBB"

    vehicle_a = MagicMock()
    vehicle_a.vin = vin_a
    vehicle_b = MagicMock()
    vehicle_b.vin = vin_b

    entry = MagicMock()
    entry.entry_id = "entry_setup_1"
    entry.data = {
        CONF_DEVICE_PROFILE: {
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
        },
        "username": "user@test.com",
        "password": "secret",
        "base_url": "https://api.example.com",
        "country_code": "NL",
        "language": "en",
    }
    entry.options = {
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_GPS_POLL_INTERVAL: DEFAULT_GPS_POLL_INTERVAL,
        CONF_SMART_GPS_POLLING: DEFAULT_SMART_GPS_POLLING,
        CONF_GPS_ACTIVE_INTERVAL: DEFAULT_GPS_ACTIVE_INTERVAL,
        CONF_GPS_INACTIVE_INTERVAL: DEFAULT_GPS_INACTIVE_INTERVAL,
    }
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=lambda: None)

    hass.services = MagicMock()
    hass.services.has_service.return_value = False
    hass.services.async_register = MagicMock()

    with patch(
        "custom_components.byd_vehicle.async_get_clientsession",
        return_value=MagicMock(),
    ), patch("custom_components.byd_vehicle.BydApi") as MockBydApi:
        mock_api_instance = MagicMock()
        mock_api_instance.register_coordinators = MagicMock()
        mock_api_instance.async_call = AsyncMock(
            return_value=[vehicle_a, vehicle_b]
        )
        MockBydApi.return_value = mock_api_instance

        with patch(
            "custom_components.byd_vehicle.BydDataUpdateCoordinator"
        ) as MockTelemetry, patch(
            "custom_components.byd_vehicle.BydGpsUpdateCoordinator"
        ) as MockGps:
            telemetry_instances: dict[str, MagicMock] = {}
            gps_instances: dict[str, MagicMock] = {}

            def _make_telemetry(_hass, _api, _vehicle, vin, _interval):
                m = MagicMock()
                m.async_config_entry_first_refresh = AsyncMock()
                telemetry_instances[vin] = m
                return m

            def _make_gps(_hass, _api, _vehicle, vin, _interval, **kwargs):
                m = MagicMock()
                m.async_config_entry_first_refresh = AsyncMock()
                gps_instances[vin] = m
                return m

            MockTelemetry.side_effect = _make_telemetry
            MockGps.side_effect = _make_gps

            result = await async_setup_entry(hass, entry)

    assert result is True
    # Both VINs have telemetry coordinators
    assert vin_a in telemetry_instances
    assert vin_b in telemetry_instances
    # Both VINs have GPS coordinators
    assert vin_a in gps_instances
    assert vin_b in gps_instances
    # Coordinators are registered with the API
    mock_api_instance.register_coordinators.assert_called_once()
    # hass.data contains entry data
    assert entry.entry_id in hass.data[DOMAIN]
    assert "coordinators" in hass.data[DOMAIN][entry.entry_id]
    assert "gps_coordinators" in hass.data[DOMAIN][entry.entry_id]


# ---------------------------------------------------------------------------
# 7. HVAC optimistic update + guard prevents stale API from overwriting
#
# apply_optimistic_hvac() patches coordinator data and arms the guard;
# a subsequent HVAC fetch that disagrees is rejected until confirmed.
# ---------------------------------------------------------------------------


def test_optimistic_hvac_guard_rejects_stale_then_accepts_confirmed() -> None:
    """apply_optimistic_hvac arms a guard; mismatching API data is rejected."""
    from pybyd.models.hvac import HvacOverallStatus, HvacStatus

    vin = "VIN_HVAC_001"
    initial_hvac = HvacStatus()  # ac off
    data = {
        "vehicles": {vin: MagicMock()},
        "hvac": {vin: initial_hvac},
    }
    coordinator = _make_telemetry_coordinator(vin=vin, data=data)

    received: list[dict] = []

    def _capture(new_data):
        coordinator.data = new_data
        received.append(new_data)

    coordinator.async_set_updated_data = _capture

    # Apply optimistic "AC on"
    coordinator.apply_optimistic_hvac(ac_on=True)
    assert coordinator._optimistic_hvac_until is not None
    assert coordinator._optimistic_ac_expected is True
    # Data was patched
    assert len(received) == 1
    patched_hvac = coordinator.data["hvac"][vin]
    assert patched_hvac.status == HvacOverallStatus.ON

    # API returns stale "still off" → guard rejects it
    stale = HvacStatus()  # ac off
    assert coordinator._accept_hvac_update(stale) is False

    # API returns confirmed "on" → guard clears
    confirmed = HvacStatus(status=HvacOverallStatus.ON)
    assert coordinator._accept_hvac_update(confirmed) is True
    assert coordinator._optimistic_hvac_until is None
