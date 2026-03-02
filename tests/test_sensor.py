"""Unit tests for sensor pure helpers."""

from __future__ import annotations

import types
from datetime import UTC, datetime

from custom_components.byd_vehicle.sensor import _normalize_epoch, _round_int_attr


class TestNormalizeEpoch:
    """Tests for _normalize_epoch."""

    def test_none_returns_none(self) -> None:
        assert _normalize_epoch(None) is None

    def test_datetime_with_utc_returned_as_is(self) -> None:
        dt = datetime(2024, 1, 1, tzinfo=UTC)
        assert _normalize_epoch(dt) is dt

    def test_naive_datetime_gets_utc(self) -> None:
        dt = datetime(2024, 1, 1)
        result = _normalize_epoch(dt)
        assert result is not None
        assert result.tzinfo == UTC

    def test_integer_seconds(self) -> None:
        result = _normalize_epoch(1_000_000)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_integer_milliseconds(self) -> None:
        # Value > 1_000_000_000_000 → treated as milliseconds
        ts_ms = 1_000_000_000_001
        result = _normalize_epoch(ts_ms)
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC
        # Should equal the seconds-based equivalent
        expected = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        assert result == expected

    def test_negative_returns_none(self) -> None:
        assert _normalize_epoch(-1) is None

    def test_zero_returns_none(self) -> None:
        assert _normalize_epoch(0) is None

    def test_non_numeric_string_returns_none(self) -> None:
        assert _normalize_epoch("bad") is None


class TestRoundIntAttr:
    """Tests for _round_int_attr."""

    def test_rounds_float(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace(val=5.7)
        assert fn(obj) == 6

    def test_none_attr_returns_none(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace(val=None)
        assert fn(obj) is None

    def test_missing_attr_returns_none(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace()
        assert fn(obj) is None

    def test_integer_value(self) -> None:
        fn = _round_int_attr("val")
        obj = types.SimpleNamespace(val=3)
        assert fn(obj) == 3
