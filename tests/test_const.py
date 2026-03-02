"""Unit tests for the constants module."""

from __future__ import annotations

from custom_components.byd_vehicle.const import (
    BASE_URLS,
    CLIMATE_DURATION_OPTIONS,
    CONF_BASE_URL,
    CONF_CONTROL_PIN,
    CONF_COUNTRY_CODE,
    CONF_POLL_INTERVAL,
    COUNTRY_OPTIONS,
    DEFAULT_CLIMATE_DURATION,
    DEFAULT_COUNTRY,
    DEFAULT_GPS_ACTIVE_INTERVAL,
    DEFAULT_GPS_INACTIVE_INTERVAL,
    DEFAULT_GPS_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_GPS_ACTIVE_INTERVAL,
    MAX_GPS_INACTIVE_INTERVAL,
    MAX_GPS_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    MIN_GPS_ACTIVE_INTERVAL,
    MIN_GPS_INACTIVE_INTERVAL,
    MIN_GPS_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)


def test_domain() -> None:
    assert DOMAIN == "byd_vehicle"


def test_conf_constants_are_strings() -> None:
    for const in (
        CONF_BASE_URL,
        CONF_CONTROL_PIN,
        CONF_COUNTRY_CODE,
        CONF_POLL_INTERVAL,
    ):
        assert isinstance(const, str)


def test_default_poll_interval_within_bounds() -> None:
    assert MIN_POLL_INTERVAL <= DEFAULT_POLL_INTERVAL <= MAX_POLL_INTERVAL


def test_default_gps_poll_interval_within_bounds() -> None:
    assert MIN_GPS_POLL_INTERVAL <= DEFAULT_GPS_POLL_INTERVAL <= MAX_GPS_POLL_INTERVAL


def test_default_gps_active_interval_within_bounds() -> None:
    assert MIN_GPS_ACTIVE_INTERVAL <= DEFAULT_GPS_ACTIVE_INTERVAL
    assert DEFAULT_GPS_ACTIVE_INTERVAL <= MAX_GPS_ACTIVE_INTERVAL


def test_default_gps_inactive_interval_within_bounds() -> None:
    assert (
        MIN_GPS_INACTIVE_INTERVAL
        <= DEFAULT_GPS_INACTIVE_INTERVAL
        <= MAX_GPS_INACTIVE_INTERVAL
    )


def test_default_climate_duration_in_options() -> None:
    assert DEFAULT_CLIMATE_DURATION in CLIMATE_DURATION_OPTIONS


def test_climate_duration_options_are_positive() -> None:
    assert all(d > 0 for d in CLIMATE_DURATION_OPTIONS)


def test_default_country_in_country_options() -> None:
    assert DEFAULT_COUNTRY in COUNTRY_OPTIONS


def test_country_options_have_code_and_language() -> None:
    for country, (code, lang) in COUNTRY_OPTIONS.items():
        assert len(code) == 2, f"{country}: country code should be 2 chars"
        assert len(lang) >= 2, f"{country}: language should be at least 2 chars"


def test_base_urls_are_https() -> None:
    for region, url in BASE_URLS.items():
        assert url.startswith("https://"), f"{region}: URL should use HTTPS"
