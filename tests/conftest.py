"""Shared anonymized test data."""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request):
    """Enable custom integrations when the Home Assistant plugin is loaded."""
    with suppress(pytest.FixtureLookupError):
        request.getfixturevalue("enable_custom_integrations")
    yield


@pytest.fixture
def meter_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "meters.json").read_text(encoding="utf-8"))


@pytest.fixture
def reading_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "readings.json").read_text(encoding="utf-8"))
