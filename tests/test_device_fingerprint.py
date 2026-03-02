"""Unit tests for device_fingerprint pure helpers."""

from __future__ import annotations

import hashlib
import re

from custom_components.byd_vehicle.device_fingerprint import (
    _generate_imei,
    _generate_mac,
    _luhn_check_digit,
    generate_device_profile,
)


def _luhn_valid(imei: str) -> bool:
    """Return True when the full IMEI passes the Luhn check."""
    digits = [int(d) for d in imei]
    total = 0
    for i, d in enumerate(digits[:-1]):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    check = (10 - (total % 10)) % 10
    return check == digits[-1]


def test_luhn_check_digit_known_value() -> None:
    # Partial IMEI "35131210000000" → check digit 3
    assert _luhn_check_digit("35131210000000") == "3"


def test_generate_imei_length() -> None:
    imei = _generate_imei("35131210")
    assert len(imei) == 15


def test_generate_imei_all_digits() -> None:
    imei = _generate_imei("35131210")
    assert imei.isdigit()


def test_generate_imei_passes_luhn() -> None:
    imei = _generate_imei("35131210")
    assert _luhn_valid(imei)


def test_generate_mac_format() -> None:
    mac = _generate_mac()
    assert re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", mac)


def test_generate_mac_locally_administered_bit() -> None:
    mac = _generate_mac()
    first_byte = int(mac.split(":")[0], 16)
    assert first_byte & 0x02 == 0x02


def test_generate_mac_multicast_bit_clear() -> None:
    mac = _generate_mac()
    first_byte = int(mac.split(":")[0], 16)
    assert first_byte & 0x01 == 0


def test_generate_device_profile_keys() -> None:
    expected_keys = {
        "ostype", "imei", "mac", "model", "sdk", "mod", "imei_md5",
        "mobile_brand", "mobile_model", "device_type", "network_type",
        "os_type", "os_version",
    }
    profile = generate_device_profile()
    assert expected_keys.issubset(profile.keys())


def test_generate_device_profile_ostype() -> None:
    profile = generate_device_profile()
    assert profile["ostype"] == "and"


def test_generate_device_profile_imei_digits() -> None:
    profile = generate_device_profile()
    assert len(profile["imei"]) == 15
    assert profile["imei"].isdigit()


def test_generate_device_profile_imei_md5() -> None:
    profile = generate_device_profile()
    expected_md5 = hashlib.md5(profile["imei"].encode()).hexdigest()
    assert profile["imei_md5"] == expected_md5
