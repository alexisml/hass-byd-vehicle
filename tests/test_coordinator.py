"""Unit tests for coordinator helpers."""

from __future__ import annotations

import types

from custom_components.byd_vehicle.coordinator import get_vehicle_display


def test_get_vehicle_display_with_model_name() -> None:
    vehicle = types.SimpleNamespace(model_name="BYD Atto 3", vin="LGXCE40B4P0000001")
    assert get_vehicle_display(vehicle) == "BYD Atto 3"


def test_get_vehicle_display_without_model_name_returns_vin() -> None:
    vehicle = types.SimpleNamespace(model_name="", vin="LGXCE40B4P0000001")
    assert get_vehicle_display(vehicle) == "LGXCE40B4P0000001"


def test_get_vehicle_display_none_model_name_returns_vin() -> None:
    vehicle = types.SimpleNamespace(model_name=None, vin="LGXCE40B4P0000002")
    assert get_vehicle_display(vehicle) == "LGXCE40B4P0000002"
