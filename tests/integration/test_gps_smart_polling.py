"""Integration tests: GPS smart-polling interval driven by vehicle-on state.

BydGpsUpdateCoordinator._adjust_interval() switches between active and
inactive intervals based on BydDataUpdateCoordinator.is_vehicle_on.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from .helpers import make_gps_coordinator, make_telemetry_coordinator


def test_gps_interval_active_when_vehicle_on() -> None:
    """Smart GPS polling uses the active interval when the vehicle is on."""
    vin = "VIN_GPS_001"
    telemetry = make_telemetry_coordinator(vin=vin)
    rt = MagicMock()
    rt.is_vehicle_on = True
    telemetry._last_realtime = rt

    gps = make_gps_coordinator(
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
    telemetry = make_telemetry_coordinator(vin=vin)
    telemetry._last_realtime = None  # vehicle is off

    gps = make_gps_coordinator(
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
    telemetry = make_telemetry_coordinator(vin=vin)
    rt = MagicMock()
    rt.is_vehicle_on = True
    telemetry._last_realtime = rt

    gps = make_gps_coordinator(
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
    telemetry = make_telemetry_coordinator(vin=vin)
    telemetry._last_realtime = None  # initially off

    gps = make_gps_coordinator(
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
