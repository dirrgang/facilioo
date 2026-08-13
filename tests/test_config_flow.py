"""Tests for setup, duplicates, errors and reauthentication."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.facilioo.config_flow import account_unique_id
from custom_components.facilioo.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Keep config-flow tests isolated from component and dependency setup."""
    with (
        patch(
            "homeassistant.config_entries.async_process_deps_reqs",
            new=AsyncMock(),
        ),
        patch("homeassistant.setup.async_process_deps_reqs", new=AsyncMock()),
        patch("custom_components.facilioo.async_setup_entry", return_value=True) as setup,
    ):
        yield setup


async def test_successful_setup(hass, enable_custom_integrations, mock_setup_entry):
    with patch("custom_components.facilioo.config_flow._validate", new=AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "password"},
        )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["data"][CONF_EMAIL] == "resident@example.test"
    mock_setup_entry.assert_awaited_once()


async def test_duplicate_account(hass, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=account_unique_id("resident@example.test"),
        data={CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "old"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.facilioo.config_flow._validate", new=AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "new"},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_errors_are_presented(hass, enable_custom_integrations):
    from custom_components.facilioo.api import FaciliooConnectionError

    with patch(
        "custom_components.facilioo.config_flow._validate",
        new=AsyncMock(side_effect=FaciliooConnectionError("offline")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "password"},
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauthentication_updates_password(hass, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=account_unique_id("resident@example.test"),
        data={CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "old"},
    )
    entry.add_to_hass(hass)
    with patch("custom_components.facilioo.config_flow._validate", new=AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "new"},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
