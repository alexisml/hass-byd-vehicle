"""Smoke tests for config_flow module."""

from __future__ import annotations

from custom_components.byd_vehicle import config_flow


def test_config_flow_module_importable() -> None:
    assert hasattr(config_flow, "BydVehicleConfigFlow")
