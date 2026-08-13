"""Facilioo consumption integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FaciliooApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, PLATFORMS
from .coordinator import FaciliooCoordinator
from .statistics import FaciliooStatisticsManager


@dataclass(slots=True)
class FaciliooRuntimeData:
    """Objects owned by one config entry."""

    coordinator: FaciliooCoordinator
    statistics: FaciliooStatisticsManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Facilioo from a config entry."""
    client = FaciliooApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = FaciliooCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    statistics = FaciliooStatisticsManager(hass, entry)
    await statistics.async_sync(coordinator.data)
    entry.runtime_data = FaciliooRuntimeData(coordinator, statistics)

    def _schedule_statistics_sync() -> None:
        hass.async_create_task(
            statistics.async_sync(coordinator.data),
            f"Update {entry.title} historical statistics",
        )

    entry.async_on_unload(coordinator.async_add_listener(_schedule_statistics_sync))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry and discard its in-memory access token."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.coordinator.client.clear_token()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
