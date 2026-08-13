"""Coordinator error mapping and data processing tests."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.facilioo.api import (
    FaciliooAuthenticationError,
    FaciliooConnectionError,
)
from custom_components.facilioo.const import DOMAIN
from custom_components.facilioo.coordinator import FaciliooCoordinator
from custom_components.facilioo.models import ConsumptionMeter, ConsumptionReading, MeterKind


async def test_coordinator_aggregates(hass):
    hass.config.set_time_zone("Europe/Berlin")
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 5, "unitOfMeasure": "M3"})
    reading = ConsumptionReading.from_api(
        {
            "id": 2,
            "consumptionMeterId": 1,
            "currentValue": 0.5,
            "readingDate": "2025-11-30T23:00:00Z",
        }
    )
    client = AsyncMock()
    client.async_fetch_all.return_value = ((meter,), (reading,))
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = FaciliooCoordinator(hass, entry, client)
    data = await coordinator._async_update_data()
    assert data.total(MeterKind.WARM_WATER) == reading.value


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FaciliooAuthenticationError("bad"), ConfigEntryAuthFailed),
        (FaciliooConnectionError("offline"), UpdateFailed),
    ],
)
async def test_coordinator_maps_errors(hass, error, expected):
    client = AsyncMock()
    client.async_fetch_all.side_effect = error
    coordinator = FaciliooCoordinator(hass, MockConfigEntry(domain=DOMAIN, data={}), client)
    with pytest.raises(expected):
        await coordinator._async_update_data()
