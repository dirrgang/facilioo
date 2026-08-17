"""Facilioo consumption integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FaciliooApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN, PLATFORMS
from .coordinator import FaciliooCoordinator
from .statistics import FaciliooStatisticsManager

_LOGGER = logging.getLogger(__name__)


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
    _migrate_unique_id(hass, entry, client.account_id)
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


def _migrate_unique_id(hass: HomeAssistant, entry: ConfigEntry, account_id: int | None) -> None:
    """Replace legacy identity with the stable Facilioo account ID after a successful login."""
    if account_id is None:
        return
    unique_id = str(account_id)
    if entry.unique_id == unique_id:
        return

    duplicate = next(
        (
            candidate
            for candidate in hass.config_entries.async_entries(DOMAIN)
            if candidate.entry_id != entry.entry_id and candidate.unique_id == unique_id
        ),
        None,
    )
    if duplicate is not None:
        _LOGGER.warning(
            "Cannot migrate Facilioo config entry %s to account ID %s because another entry already uses it",
            entry.entry_id,
            unique_id,
        )
        return

    hass.config_entries.async_update_entry(entry, unique_id=unique_id)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
