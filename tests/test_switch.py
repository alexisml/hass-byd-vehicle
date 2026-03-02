"""Smoke tests for switch module."""

from __future__ import annotations

from custom_components.byd_vehicle import switch


def test_switch_module_importable() -> None:
    assert hasattr(switch, "BydBatteryHeatSwitch")
    assert hasattr(switch, "BydCarOnSwitch")
    assert hasattr(switch, "BydDisablePollingSwitch")
