"""Coordinator error mapping and data processing tests."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.facilioo.api import (
    FaciliooAuthenticationError,
    FaciliooConnectionError,
)
from custom_components.facilioo.const import DOMAIN, SYNC_OVERLAP
from custom_components.facilioo.coordinator import FaciliooCoordinator
from custom_components.facilioo.models import ConsumptionMeter, ConsumptionReading, MeterKind


async def test_coordinator_aggregates(hass):
    await hass.config.async_set_time_zone("Europe/Berlin")
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


async def test_coordinator_uses_changed_since_and_merges_cached_readings(hass):
    await hass.config.async_set_time_zone("Europe/Berlin")
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 5, "unitOfMeasure": "M3"})
    january = ConsumptionReading.from_api(
        {
            "id": 10,
            "consumptionMeterId": 1,
            "currentValue": 0.5,
            "readingDate": "2026-01-31T23:00:00Z",
            "lastModified": "2026-02-10T10:00:00Z",
        }
    )
    corrected_january = ConsumptionReading.from_api(
        {
            "id": 10,
            "consumptionMeterId": 1,
            "currentValue": 0.75,
            "readingDate": "2026-01-31T23:00:00Z",
            "lastModified": "2026-08-16T18:00:00Z",
        }
    )
    february = ConsumptionReading.from_api(
        {
            "id": 11,
            "consumptionMeterId": 1,
            "currentValue": 0.25,
            "readingDate": "2026-02-28T23:00:00Z",
            "lastModified": "2026-08-16T18:00:00Z",
        }
    )
    client = AsyncMock()
    client.async_fetch_all.return_value = ((meter,), (january,))
    client.async_fetch_changes.return_value = ((meter,), (corrected_january, february))
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = FaciliooCoordinator(hass, entry, client)

    first = await coordinator._async_update_data()
    first_updated = first.updated_at
    second = await coordinator._async_update_data()

    assert first.total(MeterKind.WARM_WATER) == january.value
    assert second.total(MeterKind.WARM_WATER) == corrected_january.value + february.value
    client.async_fetch_all.assert_awaited_once()
    client.async_fetch_changes.assert_awaited_once()
    changed_since = client.async_fetch_changes.await_args.args[0]
    assert changed_since.tzinfo is not None
    assert changed_since <= first_updated
    assert first_updated - changed_since >= SYNC_OVERLAP - timedelta(seconds=1)


async def test_coordinator_delta_keeps_deletion_tombstone(hass):
    await hass.config.async_set_time_zone("Europe/Berlin")
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 5, "unitOfMeasure": "M3"})
    reading = ConsumptionReading.from_api(
        {
            "id": 10,
            "consumptionMeterId": 1,
            "currentValue": 0.5,
            "readingDate": "2026-01-31T23:00:00Z",
        }
    )
    deleted = ConsumptionReading.from_api(
        {
            "id": 10,
            "consumptionMeterId": 1,
            "currentValue": 0.5,
            "readingDate": "2026-01-31T23:00:00Z",
            "deleted": "2026-08-16T18:00:00Z",
            "lastModified": "2026-08-16T18:00:00Z",
        }
    )
    client = AsyncMock()
    client.async_fetch_all.return_value = ((meter,), (reading,))
    client.async_fetch_changes.return_value = ((meter,), (deleted,))
    coordinator = FaciliooCoordinator(hass, MockConfigEntry(domain=DOMAIN, data={}), client)

    await coordinator._async_update_data()
    updated = await coordinator._async_update_data()

    assert updated.total(MeterKind.WARM_WATER) == 0
    assert updated.readings == (deleted,)


async def test_coordinator_restores_cached_readings_after_restart(hass):
    await hass.config.async_set_time_zone("Europe/Berlin")
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 5, "unitOfMeasure": "M3"})
    reading = ConsumptionReading.from_api(
        {
            "id": 10,
            "consumptionMeterId": 1,
            "currentValue": 0.5,
            "currentValueInDifferentUnitOfMeasure": 29.075,
            "costs": 4.2,
            "isEstimated": True,
            "readingDate": "2026-01-31T23:00:00Z",
            "lastModified": "2026-02-10T10:00:00Z",
        }
    )
    entry = MockConfigEntry(domain=DOMAIN, data={})
    first_client = AsyncMock()
    first_client.async_fetch_all.return_value = ((meter,), (reading,))
    first_coordinator = FaciliooCoordinator(hass, entry, first_client)
    await first_coordinator._async_update_data()

    second_client = AsyncMock()
    second_client.async_fetch_changes.return_value = ((meter,), ())
    second_coordinator = FaciliooCoordinator(hass, entry, second_client)
    restored = await second_coordinator._async_update_data()

    latest = restored.latest(MeterKind.WARM_WATER)
    assert latest is not None
    assert latest.value == reading.value
    assert latest.value_in_different_unit == reading.value_in_different_unit
    assert latest.costs == reading.costs
    assert latest.is_estimated is True
    second_client.async_fetch_all.assert_not_awaited()
    second_client.async_fetch_changes.assert_awaited_once()


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
