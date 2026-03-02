"""Integration tests: HVAC optimistic guard.

apply_optimistic_hvac() patches coordinator data and arms the guard;
a subsequent HVAC fetch that disagrees is rejected until confirmed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pybyd.models.hvac import HvacOverallStatus, HvacStatus

from .helpers import make_telemetry_coordinator


def test_optimistic_hvac_guard_rejects_stale_then_accepts_confirmed() -> None:
    """apply_optimistic_hvac arms a guard; mismatching API data is rejected."""
    vin = "VIN_HVAC_001"
    initial_hvac = HvacStatus()  # ac off
    data = {
        "vehicles": {vin: MagicMock()},
        "hvac": {vin: initial_hvac},
    }
    coordinator = make_telemetry_coordinator(vin=vin, data=data)

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
