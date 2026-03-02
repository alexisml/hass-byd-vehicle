"""Unit tests for the value_guard helpers."""

from __future__ import annotations

import pytest
from pybyd.models.gps import GpsInfo

from custom_components.byd_vehicle.value_guard import (
    guard_gps_coordinates,
    keep_previous_when_zero,
)


class TestKeepPreviousWhenZero:
    """Tests for keep_previous_when_zero."""

    def test_returns_incoming_when_nonzero(self) -> None:
        assert keep_previous_when_zero(5, 10) == 10

    def test_returns_previous_when_incoming_is_zero(self) -> None:
        assert keep_previous_when_zero(5, 0) == 5

    def test_returns_zero_when_previous_is_none(self) -> None:
        assert keep_previous_when_zero(None, 0) == 0

    def test_returns_incoming_when_previous_is_none_and_nonzero(self) -> None:
        assert keep_previous_when_zero(None, 42) == 42

    def test_works_with_floats(self) -> None:
        assert keep_previous_when_zero(1.5, 0) == 1.5

    def test_works_with_strings(self) -> None:
        assert keep_previous_when_zero("old", "new") == "new"

    def test_returns_previous_string_when_incoming_is_zero(self) -> None:
        assert keep_previous_when_zero("old", 0) == "old"


class TestGuardGpsCoordinates:
    """Tests for guard_gps_coordinates."""

    @pytest.fixture()
    def valid_gps(self) -> GpsInfo:
        return GpsInfo(latitude=52.0, longitude=4.3)

    @pytest.fixture()
    def another_valid_gps(self) -> GpsInfo:
        return GpsInfo(latitude=48.8, longitude=2.3)

    @pytest.fixture()
    def null_island_gps(self) -> GpsInfo:
        return GpsInfo(latitude=0.0, longitude=0.0)

    @pytest.fixture()
    def near_null_island_gps(self) -> GpsInfo:
        return GpsInfo(latitude=0.05, longitude=0.05)

    @pytest.fixture()
    def none_coords_gps(self) -> GpsInfo:
        return GpsInfo(latitude=None, longitude=None)

    def test_returns_previous_when_incoming_is_none(self, valid_gps: GpsInfo) -> None:
        result = guard_gps_coordinates(valid_gps, None)
        assert result is valid_gps

    def test_returns_incoming_when_previous_is_none(self, valid_gps: GpsInfo) -> None:
        result = guard_gps_coordinates(None, valid_gps)
        assert result is valid_gps

    def test_returns_none_when_both_are_none(self) -> None:
        assert guard_gps_coordinates(None, None) is None

    def test_returns_incoming_for_valid_coordinates(
        self, valid_gps: GpsInfo, another_valid_gps: GpsInfo
    ) -> None:
        result = guard_gps_coordinates(valid_gps, another_valid_gps)
        assert result is another_valid_gps

    def test_falls_back_to_previous_for_null_island(
        self, valid_gps: GpsInfo, null_island_gps: GpsInfo
    ) -> None:
        result = guard_gps_coordinates(valid_gps, null_island_gps)
        assert result is valid_gps

    def test_falls_back_to_previous_for_near_null_island(
        self, valid_gps: GpsInfo, near_null_island_gps: GpsInfo
    ) -> None:
        result = guard_gps_coordinates(valid_gps, near_null_island_gps)
        assert result is valid_gps

    def test_returns_null_island_on_first_startup(
        self, null_island_gps: GpsInfo
    ) -> None:
        """On first startup (previous=None) always return incoming, even Null Island."""
        result = guard_gps_coordinates(None, null_island_gps)
        assert result is null_island_gps

    def test_falls_back_to_previous_for_none_coords(
        self, valid_gps: GpsInfo, none_coords_gps: GpsInfo
    ) -> None:
        result = guard_gps_coordinates(valid_gps, none_coords_gps)
        assert result is valid_gps

    def test_returns_none_coords_gps_on_first_startup(
        self, none_coords_gps: GpsInfo
    ) -> None:
        """On first startup, incoming with None coords is returned as-is."""
        result = guard_gps_coordinates(None, none_coords_gps)
        assert result is none_coords_gps

    def test_boundary_coordinate_just_above_threshold(self, valid_gps: GpsInfo) -> None:
        """Coordinates just above the threshold should be accepted."""
        incoming = GpsInfo(latitude=0.11, longitude=0.11)
        result = guard_gps_coordinates(valid_gps, incoming)
        assert result is incoming
