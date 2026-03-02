"""Unit tests for __init__.py pure helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.byd_vehicle import (
    _async_register_services,
    _async_unregister_services,
    _get_coordinators,
    _resolve_vins_from_call,
    _sanitize_interval,
)
from custom_components.byd_vehicle.const import DOMAIN


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


# ---------------------------------------------------------------------------
# _resolve_vins_from_call
# ---------------------------------------------------------------------------


def _make_hass(vin: str = "VIN123", entry_id: str = "entry1") -> MagicMock:
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            entry_id: {
                "coordinators": {vin: MagicMock()},
            }
        }
    }
    return hass


def test_resolve_vins_from_call_returns_entry_vin_pair() -> None:
    hass = _make_hass()
    device = MagicMock()
    device.identifiers = {(DOMAIN, "VIN123")}
    dev_reg = MagicMock()
    dev_reg.async_get.return_value = device
    call = MagicMock()
    call.data = {"device_id": ["dev1"]}
    with patch("custom_components.byd_vehicle.dr.async_get", return_value=dev_reg):
        result = _resolve_vins_from_call(hass, call)
    assert result == [("entry1", "VIN123")]


def test_resolve_vins_from_call_string_device_id() -> None:
    hass = _make_hass()
    device = MagicMock()
    device.identifiers = {(DOMAIN, "VIN123")}
    dev_reg = MagicMock()
    dev_reg.async_get.return_value = device
    call = MagicMock()
    # single string instead of list
    call.data = {"device_id": "dev1"}
    with patch("custom_components.byd_vehicle.dr.async_get", return_value=dev_reg):
        result = _resolve_vins_from_call(hass, call)
    assert result == [("entry1", "VIN123")]


def test_resolve_vins_from_call_no_results_raises() -> None:
    hass = _make_hass()
    dev_reg = MagicMock()
    dev_reg.async_get.return_value = None
    call = MagicMock()
    call.data = {"device_id": ["unknown_dev"]}
    with patch("custom_components.byd_vehicle.dr.async_get", return_value=dev_reg):
        with pytest.raises(HomeAssistantError):
            _resolve_vins_from_call(hass, call)


def test_resolve_vins_from_call_empty_device_ids_raises() -> None:
    hass = _make_hass()
    dev_reg = MagicMock()
    call = MagicMock()
    call.data = {"device_id": []}
    with patch("custom_components.byd_vehicle.dr.async_get", return_value=dev_reg):
        with pytest.raises(HomeAssistantError):
            _resolve_vins_from_call(hass, call)


# ---------------------------------------------------------------------------
# _get_coordinators
# ---------------------------------------------------------------------------


def test_get_coordinators_returns_telemetry_and_gps() -> None:
    tel = MagicMock()
    gps = MagicMock()
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {"VIN123": tel},
                "gps_coordinators": {"VIN123": gps},
            }
        }
    }
    result = _get_coordinators(hass, "entry1", "VIN123")
    assert result == (tel, gps)


def test_get_coordinators_no_gps_returns_none() -> None:
    tel = MagicMock()
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "entry1": {
                "coordinators": {"VIN123": tel},
            }
        }
    }
    result = _get_coordinators(hass, "entry1", "VIN123")
    assert result[0] is tel
    assert result[1] is None


# ---------------------------------------------------------------------------
# _async_register_services / _async_unregister_services
# ---------------------------------------------------------------------------


def _make_hass_for_services(already_registered: bool = False) -> MagicMock:
    """Create a mock hass for service registration tests."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = already_registered
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    return hass


def test_register_services_registers_three_services() -> None:
    hass = _make_hass_for_services(already_registered=False)
    _async_register_services(hass)
    assert hass.services.async_register.call_count == 3


def test_register_services_idempotent_when_already_registered() -> None:
    """When service already registered, returns early without registering."""
    hass = _make_hass_for_services(already_registered=True)
    _async_register_services(hass)
    hass.services.async_register.assert_not_called()


def test_unregister_services_removes_all() -> None:
    hass = _make_hass_for_services()
    _async_unregister_services(hass)
    assert hass.services.async_remove.call_count == 3
