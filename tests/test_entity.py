"""Unit tests for entity module constants."""

from __future__ import annotations

from custom_components.byd_vehicle.entity import _OPTIMISTIC_TTL_SECONDS


def test_optimistic_ttl() -> None:
    assert _OPTIMISTIC_TTL_SECONDS == 300.0
