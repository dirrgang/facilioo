"""Tests for config entry setup and unloading."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from custom_components.facilioo import async_setup_entry, async_unload_entry
from custom_components.facilioo.const import CONF_EMAIL, CONF_PASSWORD, PLATFORMS


async def test_setup_entry_initializes_runtime_and_platforms():
    data = object()
    client = Mock()
    coordinator = Mock()
    coordinator.data = data
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_add_listener.return_value = "remove coordinator listener"
    statistics = Mock()
    statistics.async_sync = AsyncMock()
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_forward_entry_setups=AsyncMock()),
        async_create_task=Mock(),
    )
    entry = SimpleNamespace(
        data={CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "password"},
        title="Facilioo",
        entry_id="entry-id",
        async_on_unload=Mock(),
        add_update_listener=Mock(return_value="remove update listener"),
    )

    with (
        patch("custom_components.facilioo.async_get_clientsession", return_value="session"),
        patch("custom_components.facilioo.FaciliooApiClient", return_value=client) as api_class,
        patch(
            "custom_components.facilioo.FaciliooCoordinator", return_value=coordinator
        ) as coordinator_class,
        patch(
            "custom_components.facilioo.FaciliooStatisticsManager",
            return_value=statistics,
        ) as statistics_class,
    ):
        assert await async_setup_entry(hass, entry) is True

    api_class.assert_called_once_with("session", "resident@example.test", "password")
    coordinator_class.assert_called_once_with(hass, entry, client)
    coordinator.async_config_entry_first_refresh.assert_awaited_once_with()
    statistics_class.assert_called_once_with(hass, entry)
    statistics.async_sync.assert_awaited_once_with(data)
    assert entry.runtime_data.coordinator is coordinator
    assert entry.runtime_data.statistics is statistics
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(entry, PLATFORMS)
    entry.add_update_listener.assert_called_once()
    assert entry.async_on_unload.call_count == 2


async def test_unload_entry_clears_token_only_after_platforms_unload():
    client = Mock()
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(coordinator=SimpleNamespace(client=client))
    )
    unload_platforms = AsyncMock(side_effect=(False, True))
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_unload_platforms=unload_platforms))

    assert await async_unload_entry(hass, entry) is False
    client.clear_token.assert_not_called()

    assert await async_unload_entry(hass, entry) is True
    client.clear_token.assert_called_once_with()
    assert unload_platforms.await_count == 2
