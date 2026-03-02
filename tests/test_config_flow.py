"""Smoke tests and unit tests for config_flow module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.byd_vehicle import config_flow
from custom_components.byd_vehicle.config_flow import (
    BASE_URLS,
    BydVehicleConfigFlow,
    BydVehicleOptionsFlow,
    _bounded_int,
    _climate_duration_default_label,
    _climate_duration_label_to_minutes,
    _normalize_climate_duration_minutes,
    _validate_input,
)
from custom_components.byd_vehicle.const import (
    CONF_BASE_URL,
    CONF_CLIMATE_DURATION,
    CONF_COUNTRY_CODE,
    CONF_DEBUG_DUMPS,
    COUNTRY_OPTIONS,
    DEFAULT_CLIMATE_DURATION,
)


def test_config_flow_module_importable() -> None:
    assert hasattr(config_flow, "BydVehicleConfigFlow")


# ---------------------------------------------------------------------------
# _bounded_int
# ---------------------------------------------------------------------------


def test_bounded_int_returns_validator() -> None:
    import voluptuous as vol

    validator = _bounded_int(1, 100)
    assert isinstance(validator, vol.validators.All)


def test_bounded_int_accepts_valid_value() -> None:
    validator = _bounded_int(1, 100)
    assert validator(50) == 50


def test_bounded_int_rejects_below_min() -> None:
    import voluptuous as vol

    validator = _bounded_int(10, 100)
    with pytest.raises(vol.Invalid):
        validator(5)


def test_bounded_int_rejects_above_max() -> None:
    import voluptuous as vol

    validator = _bounded_int(10, 100)
    with pytest.raises(vol.Invalid):
        validator(200)


# ---------------------------------------------------------------------------
# _normalize_climate_duration_minutes
# ---------------------------------------------------------------------------


def test_normalize_none_returns_default() -> None:
    assert _normalize_climate_duration_minutes(None) == DEFAULT_CLIMATE_DURATION


def test_normalize_valid_option() -> None:
    assert _normalize_climate_duration_minutes(15) == 15


def test_normalize_legacy_code_1_returns_10() -> None:
    assert _normalize_climate_duration_minutes(1) == 10


def test_normalize_legacy_code_5_returns_30() -> None:
    assert _normalize_climate_duration_minutes(5) == 30


def test_normalize_unknown_int_returns_default() -> None:
    assert _normalize_climate_duration_minutes(999) == DEFAULT_CLIMATE_DURATION


def test_normalize_non_numeric_string_returns_default() -> None:
    assert _normalize_climate_duration_minutes("invalid") == DEFAULT_CLIMATE_DURATION


def test_normalize_numeric_string_valid() -> None:
    assert _normalize_climate_duration_minutes("20") == 20


# ---------------------------------------------------------------------------
# _climate_duration_default_label
# ---------------------------------------------------------------------------


def test_climate_duration_default_label_returns_string() -> None:
    label = _climate_duration_default_label(10)
    assert label == "10 min"


def test_climate_duration_default_label_none_returns_default() -> None:
    label = _climate_duration_default_label(None)
    assert label == f"{DEFAULT_CLIMATE_DURATION} min"


def test_climate_duration_default_label_invalid_falls_back() -> None:
    label = _climate_duration_default_label(999)
    assert label == f"{DEFAULT_CLIMATE_DURATION} min"


# ---------------------------------------------------------------------------
# _climate_duration_label_to_minutes
# ---------------------------------------------------------------------------


def test_label_to_minutes_int_passes_through() -> None:
    assert _climate_duration_label_to_minutes(20) == 20


def test_label_to_minutes_valid_label() -> None:
    assert _climate_duration_label_to_minutes("15 min") == 15


def test_label_to_minutes_non_string_non_int_returns_default() -> None:
    assert _climate_duration_label_to_minutes(None) == DEFAULT_CLIMATE_DURATION


def test_label_to_minutes_unknown_label_falls_back() -> None:
    result = _climate_duration_label_to_minutes("unknown label")
    assert result == DEFAULT_CLIMATE_DURATION


def test_label_to_minutes_numeric_string_normalizes() -> None:
    assert _climate_duration_label_to_minutes("20") == 20


# ---------------------------------------------------------------------------
# BydVehicleConfigFlow._build_user_schema
# ---------------------------------------------------------------------------


def test_build_user_schema_returns_schema() -> None:
    import voluptuous as vol

    flow = object.__new__(BydVehicleConfigFlow)
    schema = flow._build_user_schema()
    assert isinstance(schema, vol.Schema)


def test_build_user_schema_with_defaults() -> None:
    import voluptuous as vol

    country_code, _ = next(iter(COUNTRY_OPTIONS.values()))
    flow = object.__new__(BydVehicleConfigFlow)
    schema = flow._build_user_schema(
        {"username": "user@example.com", "password": "secret"}
    )
    assert isinstance(schema, vol.Schema)


def test_build_user_schema_with_matching_country() -> None:
    """Cover the country_label match branch (line 152)."""
    import voluptuous as vol

    country_code, _ = next(iter(COUNTRY_OPTIONS.values()))
    flow = object.__new__(BydVehicleConfigFlow)
    schema = flow._build_user_schema({CONF_COUNTRY_CODE: country_code})
    assert isinstance(schema, vol.Schema)


def test_build_user_schema_with_matching_base_url() -> None:
    """Cover the base_url_label match branch (line 158-159)."""
    import voluptuous as vol

    # Use the first base URL value to trigger the match
    base_url_value = next(iter(BASE_URLS.values()))
    flow = object.__new__(BydVehicleConfigFlow)
    schema = flow._build_user_schema({CONF_BASE_URL: base_url_value})
    assert isinstance(schema, vol.Schema)


# ---------------------------------------------------------------------------
# BydVehicleConfigFlow._reauth_defaults
# ---------------------------------------------------------------------------


def test_reauth_defaults_no_entry_returns_empty() -> None:
    flow = object.__new__(BydVehicleConfigFlow)
    flow._reauth_entry = None
    result = flow._reauth_defaults()
    assert result == {}


def test_reauth_defaults_with_entry() -> None:
    flow = object.__new__(BydVehicleConfigFlow)
    entry = MagicMock()
    entry.data = {
        "username": "user@test.com",
        "password": "secret",
        CONF_BASE_URL: BASE_URLS["Europe"],
        CONF_COUNTRY_CODE: "NL",
    }
    entry.options = {}
    flow._reauth_entry = entry
    result = flow._reauth_defaults()
    assert result["username"] == "user@test.com"


# ---------------------------------------------------------------------------
# BydVehicleOptionsFlow.__init__ and async_step_init
# ---------------------------------------------------------------------------


def test_options_flow_init() -> None:
    entry = MagicMock()
    flow = BydVehicleOptionsFlow(entry)
    assert flow._config_entry is entry


@pytest.mark.asyncio
async def test_options_flow_step_init_no_input_shows_form() -> None:
    """Cover async_step_init when user_input is None (lines 416-469)."""
    entry = MagicMock()
    entry.options = {}
    flow = BydVehicleOptionsFlow(entry)
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    await flow.async_step_init(user_input=None)
    flow.async_show_form.assert_called_once()


@pytest.mark.asyncio
async def test_options_flow_step_init_with_input_no_climate_duration() -> None:
    """Cover async_step_init when user_input is provided without climate_duration."""
    entry = MagicMock()
    entry.options = {}
    flow = BydVehicleOptionsFlow(entry)
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    user_input = {CONF_DEBUG_DUMPS: False}
    await flow.async_step_init(user_input=user_input)
    flow.async_create_entry.assert_called_once_with(title="", data=user_input)


@pytest.mark.asyncio
async def test_options_flow_step_init_with_climate_duration_converts() -> None:
    """Cover async_step_init when CONF_CLIMATE_DURATION is in user_input."""
    entry = MagicMock()
    entry.options = {}
    flow = BydVehicleOptionsFlow(entry)
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    user_input = {CONF_CLIMATE_DURATION: "15 min", CONF_DEBUG_DUMPS: False}
    await flow.async_step_init(user_input=user_input)
    call_args = flow.async_create_entry.call_args
    assert call_args[1]["data"][CONF_CLIMATE_DURATION] == 15


# ---------------------------------------------------------------------------
# BydVehicleConfigFlow.async_step_user (user_input=None path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_flow_step_user_no_input_shows_form() -> None:
    """Cover async_step_user when user_input is None (shows form)."""
    flow = object.__new__(BydVehicleConfigFlow)
    flow._reauth_entry = None
    flow.async_show_form = MagicMock(return_value={"type": "form"})
    result = await flow.async_step_user(user_input=None)
    flow.async_show_form.assert_called_once()
    assert result == {"type": "form"}


# ---------------------------------------------------------------------------
# _validate_input (lines 122-137) - with mocked BydClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_input_success() -> None:
    """Cover lines 122-137: _validate_input with mocked BydClient."""
    data = {
        "username": "test@example.com",
        "password": "password",
        CONF_BASE_URL: "Europe",
        CONF_COUNTRY_CODE: "Netherlands",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.login = AsyncMock()
    mock_client.get_vehicles = AsyncMock(return_value=[])

    hass = MagicMock()
    hass.config.time_zone = "UTC"

    with patch(
        "custom_components.byd_vehicle.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.byd_vehicle.config_flow.BydClient",
        return_value=mock_client,
    ):
        await _validate_input(hass, data)
        mock_client.login.assert_called_once()
        mock_client.get_vehicles.assert_called_once()


# ---------------------------------------------------------------------------
# async_get_options_flow (line 392)
# ---------------------------------------------------------------------------


def test_async_get_options_flow() -> None:
    """Cover line 392: static method returns BydVehicleOptionsFlow."""
    entry = MagicMock()
    flow = BydVehicleConfigFlow.async_get_options_flow(entry)
    assert isinstance(flow, BydVehicleOptionsFlow)


# ---------------------------------------------------------------------------
# async_step_reauth (lines 383-384)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_reauth() -> None:
    """Cover async_step_reauth sets _reauth_entry and calls async_step_user."""
    flow = object.__new__(BydVehicleConfigFlow)
    flow._get_reauth_entry = MagicMock(return_value=MagicMock())
    flow.async_step_user = AsyncMock(return_value={"type": "form"})
    result = await flow.async_step_reauth({})
    flow._get_reauth_entry.assert_called_once()
    flow.async_step_user.assert_called_once()
    assert result == {"type": "form"}
