"""Common pytest fixtures for BYD Vehicle tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the custom_components package is importable during tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
