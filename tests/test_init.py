"""Unit tests for _sanitize_interval in __init__.py."""

from __future__ import annotations

from custom_components.byd_vehicle import _sanitize_interval


def test_below_min_clamped_to_min() -> None:
    assert _sanitize_interval(1, 10, 5, 60) == 5


def test_above_max_clamped_to_max() -> None:
    assert _sanitize_interval(100, 10, 5, 60) == 60


def test_in_range_unchanged() -> None:
    assert _sanitize_interval(30, 10, 5, 60) == 30


def test_at_min_boundary() -> None:
    assert _sanitize_interval(5, 10, 5, 60) == 5


def test_at_max_boundary() -> None:
    assert _sanitize_interval(60, 10, 5, 60) == 60


def test_non_numeric_returns_default() -> None:
    assert _sanitize_interval("bad", 10, 5, 60) == 10


def test_none_returns_default() -> None:
    assert _sanitize_interval(None, 10, 5, 60) == 10


def test_numeric_string_parsed() -> None:
    assert _sanitize_interval("30", 10, 5, 60) == 30
