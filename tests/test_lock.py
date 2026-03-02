"""Smoke tests for lock module."""

from __future__ import annotations

from custom_components.byd_vehicle import lock


def test_lock_module_importable() -> None:
    assert hasattr(lock, "BydLock")
