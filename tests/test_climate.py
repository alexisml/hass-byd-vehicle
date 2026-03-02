"""Unit tests for BydClimate static helpers."""

from __future__ import annotations

from custom_components.byd_vehicle.climate import BydClimate


class TestClampTemp:
    """Tests for BydClimate._clamp_temp."""

    def test_none_returns_none(self) -> None:
        assert BydClimate._clamp_temp(None) is None

    def test_in_range_unchanged(self) -> None:
        assert BydClimate._clamp_temp(23.0) == 23.0

    def test_below_min_returns_none(self) -> None:
        assert BydClimate._clamp_temp(14.0) is None

    def test_above_max_returns_none(self) -> None:
        assert BydClimate._clamp_temp(32.0) is None

    def test_at_min_boundary(self) -> None:
        assert BydClimate._clamp_temp(15) == 15.0

    def test_at_max_boundary(self) -> None:
        assert BydClimate._clamp_temp(31) == 31.0

    def test_returns_float(self) -> None:
        result = BydClimate._clamp_temp(20)
        assert isinstance(result, float)


class TestPresetFromTemp:
    """Tests for BydClimate._preset_from_temp."""

    def test_none_returns_none(self) -> None:
        assert BydClimate._preset_from_temp(None) is None

    def test_max_temp_returns_max_heat(self) -> None:
        assert BydClimate._preset_from_temp(31.0) == "max_heat"

    def test_min_temp_returns_max_cool(self) -> None:
        assert BydClimate._preset_from_temp(15.0) == "max_cool"

    def test_mid_temp_returns_none(self) -> None:
        assert BydClimate._preset_from_temp(21.0) is None

    def test_rounds_to_max_heat(self) -> None:
        # 30.6 rounds to 31 (>= _TEMP_MAX_C) → "max_heat"
        assert BydClimate._preset_from_temp(30.6) == "max_heat"

    def test_rounds_to_max_cool(self) -> None:
        assert BydClimate._preset_from_temp(15.4) == "max_cool"
