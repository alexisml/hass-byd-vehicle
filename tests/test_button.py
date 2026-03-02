"""Unit tests for button descriptions."""

from __future__ import annotations

from custom_components.byd_vehicle.button import BUTTON_DESCRIPTIONS


def test_button_descriptions_nonempty() -> None:
    assert isinstance(BUTTON_DESCRIPTIONS, tuple)
    assert len(BUTTON_DESCRIPTIONS) > 0


def test_button_descriptions_have_key_and_method() -> None:
    for desc in BUTTON_DESCRIPTIONS:
        assert isinstance(desc.key, str) and desc.key
        assert isinstance(desc.method, str) and desc.method
