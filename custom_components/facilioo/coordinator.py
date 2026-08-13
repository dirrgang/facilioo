"""Data coordinator for Facilioo."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FaciliooApiClient, FaciliooAuthenticationError, FaciliooError
from .const import DOMAIN, UPDATE_INTERVAL
from .models import ConsumptionData, MeterKind, aggregate_monthly

_LOGGER = logging.getLogger(__name__)


class FaciliooCoordinator(DataUpdateCoordinator[ConsumptionData]):
    """Fetch and process all account consumption in one daily request cycle."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: FaciliooApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> ConsumptionData:
        try:
            meters, readings = await self.client.async_fetch_all()
        except FaciliooAuthenticationError as err:
            raise ConfigEntryAuthFailed("Facilioo authentication failed") from err
        except FaciliooError as err:
            raise UpdateFailed(str(err)) from err

        monthly = aggregate_monthly(meters, readings, self.hass.config.time_zone)
        known_meters = sum(meter.kind is not MeterKind.UNKNOWN for meter in meters)
        _LOGGER.debug(
            "Facilioo sync completed: %d meters (%d supported), %d readings",
            len(meters),
            known_meters,
            len(readings),
        )
        return ConsumptionData(
            meters=meters,
            readings=readings,
            monthly=monthly,
            updated_at=datetime.now(UTC),
        )
