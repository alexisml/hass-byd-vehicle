"""Tests for device_tracker module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.device_tracker import SourceType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd.models.gps import GpsInfo

from custom_components.byd_vehicle import device_tracker
from custom_components.byd_vehicle.device_tracker import BydDeviceTracker


def test_device_tracker_module_importable() -> None:
    assert hasattr(device_tracker, "BydDeviceTracker")


def test_source_type_gps_exists() -> None:
    assert SourceType.GPS is not None


# ---------------------------------------------------------------------------
# BydDeviceTracker entity tests
# ---------------------------------------------------------------------------


def _make_tracker(gps_obj=None) -> BydDeviceTracker:
    """Create a BydDeviceTracker bypassing __init__."""
    vin = "TESTVIN123"
    coordinator = MagicMock()
    coordinator.last_update_success = True
    data: dict = {"vehicles": {vin: MagicMock()}}
    if gps_obj is not None:
        data["gps"] = {vin: gps_obj}
    coordinator.data = data

    tracker = object.__new__(BydDeviceTracker)
    tracker.coordinator = coordinator
    tracker._vin = vin
    tracker._vehicle = MagicMock()
    tracker._vehicle.model_name = "BYD Atto 3"
    tracker._attr_unique_id = f"{vin}_tracker"
    tracker._command_pending = False
    tracker._commanded_at = None
    tracker.async_write_ha_state = MagicMock()
    return tracker


def _make_gps(
    latitude=51.5, longitude=4.8, speed=30.0, direction=90.0, gps_timestamp=None
) -> GpsInfo:
    gps = MagicMock(spec=GpsInfo)
    gps.latitude = latitude
    gps.longitude = longitude
    gps.speed = speed
    gps.direction = direction
    gps.gps_timestamp = gps_timestamp
    return gps


def test_source_type_is_gps() -> None:
    tracker = _make_tracker()
    assert tracker.source_type is SourceType.GPS


def test_latitude_returns_gps_value() -> None:
    tracker = _make_tracker(gps_obj=_make_gps(latitude=51.5))
    assert tracker.latitude == 51.5


def test_latitude_none_when_no_gps() -> None:
    tracker = _make_tracker(gps_obj=None)
    assert tracker.latitude is None


def test_longitude_returns_gps_value() -> None:
    tracker = _make_tracker(gps_obj=_make_gps(longitude=4.8))
    assert tracker.longitude == 4.8


def test_longitude_none_when_no_gps() -> None:
    tracker = _make_tracker(gps_obj=None)
    assert tracker.longitude is None


def test_available_true_when_gps_present() -> None:
    tracker = _make_tracker(gps_obj=_make_gps())
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert tracker.available is True


def test_available_false_when_no_gps() -> None:
    tracker = _make_tracker(gps_obj=None)
    prop = property(lambda self: True)
    with patch.object(CoordinatorEntity, "available", new_callable=lambda: prop):
        assert tracker.available is False


def test_extra_state_attributes_with_gps() -> None:
    gps = _make_gps(speed=50.0, direction=180.0, gps_timestamp="2024-01-01T00:00:00Z")
    tracker = _make_tracker(gps_obj=gps)
    attrs = tracker.extra_state_attributes
    assert attrs["gps_speed"] == 50.0
    assert attrs["gps_direction"] == 180.0
    assert attrs["gps_timestamp"] == "2024-01-01T00:00:00Z"
    assert attrs["vin"] == "TESTVIN123"


def test_extra_state_attributes_no_gps() -> None:
    tracker = _make_tracker(gps_obj=None)
    attrs = tracker.extra_state_attributes
    assert attrs["gps_speed"] is None
    assert attrs["gps_direction"] is None
    assert attrs["gps_timestamp"] is None


def test_available_false_when_super_not_available() -> None:
    """Line 55: return False when super().available is False."""
    from custom_components.byd_vehicle.entity import BydVehicleEntity

    tracker = _make_tracker(gps_obj=_make_gps())
    prop = property(lambda self: False)
    with patch.object(BydVehicleEntity, "available", new_callable=lambda: prop):
        assert tracker.available is False
