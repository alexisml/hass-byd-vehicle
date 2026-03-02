"""Unit tests for coordinator helpers."""

from __future__ import annotations

import types
from unittest.mock import MagicMock

from custom_components.byd_vehicle.coordinator import BydApi, get_vehicle_display


def test_get_vehicle_display_with_model_name() -> None:
    vehicle = types.SimpleNamespace(model_name="BYD Atto 3", vin="LGXCE40B4P0000001")
    assert get_vehicle_display(vehicle) == "BYD Atto 3"


def test_get_vehicle_display_without_model_name_returns_vin() -> None:
    vehicle = types.SimpleNamespace(model_name="", vin="LGXCE40B4P0000001")
    assert get_vehicle_display(vehicle) == "LGXCE40B4P0000001"


def test_get_vehicle_display_none_model_name_returns_vin() -> None:
    vehicle = types.SimpleNamespace(model_name=None, vin="LGXCE40B4P0000002")
    assert get_vehicle_display(vehicle) == "LGXCE40B4P0000002"


# ---------------------------------------------------------------------------
# BydApi helpers that can be tested without a real HA instance
# ---------------------------------------------------------------------------


def _make_api() -> BydApi:
    """Create a BydApi bypassing __init__ (avoids HA/pybyd setup)."""
    api = object.__new__(BydApi)
    api._debug_dumps_enabled = False
    api._debug_dump_dir = MagicMock()
    api._coordinators = {}
    return api


def test_register_coordinators() -> None:
    api = _make_api()
    coords = {"VIN123": MagicMock()}
    api.register_coordinators(coords)
    assert api._coordinators is coords


def test_write_debug_dump_skipped_when_disabled() -> None:
    api = _make_api()
    api._debug_dumps_enabled = False
    # Should not raise and should not create any files
    api._write_debug_dump("test", {"key": "value"})
    api._debug_dump_dir.mkdir.assert_not_called()


def test_write_debug_dump_writes_when_enabled(tmp_path) -> None:
    api = _make_api()
    api._debug_dumps_enabled = True

    api._debug_dump_dir = tmp_path / "byd_debug"
    api._write_debug_dump("test_cat", {"k": "v"})
    files = list((tmp_path / "byd_debug").iterdir())
    assert len(files) == 1
    assert "test_cat" in files[0].name


def test_write_debug_dump_handles_exception_gracefully() -> None:
    api = _make_api()
    api._debug_dumps_enabled = True
    api._debug_dump_dir = MagicMock()
    api._debug_dump_dir.mkdir.side_effect = OSError("no space")
    # Should not raise
    api._write_debug_dump("cat", {})
