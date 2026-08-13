"""Shared anonymized test data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def facilioo_hass(recorder_mock, enable_custom_integrations, hass):
    """Return Home Assistant after Recorder and custom integrations are ready."""
    return hass


@pytest.fixture
def meter_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "meters.json").read_text(encoding="utf-8"))


@pytest.fixture
def reading_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "readings.json").read_text(encoding="utf-8"))
