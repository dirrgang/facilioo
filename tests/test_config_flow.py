"""Tests for setup, duplicates, errors and reauthentication."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.facilioo.config_flow import account_unique_id
from custom_components.facilioo.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN


async def test_successful_setup(hass):
    with patch("custom_components.facilioo.config_flow._validate", new=AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "resident@example.test", CONF_PASSWORD: "password"},
        )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_EMAIL] == "resident@example.test"


async def test_duplicate_account(hass):
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


async def test_errors_are_presented(hass):
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


async def test_reauthentication_updates_password(hass):
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
