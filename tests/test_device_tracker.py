"""Smoke tests for device_tracker module."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType

from custom_components.byd_vehicle import device_tracker


def test_device_tracker_module_importable() -> None:
    assert hasattr(device_tracker, "BydDeviceTracker")


def test_source_type_gps_exists() -> None:
    assert SourceType.GPS is not None
