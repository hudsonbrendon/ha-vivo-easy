"""Setup, config flow, serviços e diagnóstico do Vivo Easy."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.vivo_easy.api import VivoEasyApiAuthenticationError
from custom_components.vivo_easy.const import CONF_MSISDN, DOMAIN

from .conftest import MSISDN, PASSWORD, setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_client.async_login.assert_awaited_once()

    registry = er.async_get(hass)
    wallet = registry.async_get_entity_id("sensor", DOMAIN, f"{MSISDN}_carteira")
    assert wallet and hass.states.get(wallet).state == "10.5"
    internet = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MSISDN}_consumo_internet"
    )
    assert hass.states.get(internet).state == "7.5"
    line = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{MSISDN}_linha_ativa"
    )
    assert hass.states.get(line).state == "on"
    client = registry.async_get_entity_id("sensor", DOMAIN, f"{MSISDN}_cliente")
    assert hass.states.get(client).attributes["cpf"] == "***.456.***-**"

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, MSISDN), mock_config_entry.entry_id
    )
    assert device is not None
    assert hass.services.has_service(DOMAIN, "comprar_pacote")

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_service_renew_prime(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    await setup_integration(hass, mock_config_entry)
    result = await hass.services.async_call(
        DOMAIN, "renovar_prime", {}, blocking=True, return_response=True
    )
    mock_client.async_renew_prime.assert_awaited_once_with()
    assert result == {"resultado": {"ok": True}}


async def test_diagnostics_redacts(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    await setup_integration(hass, mock_config_entry)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    assert diag["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert diag["entry"]["data"][CONF_MSISDN] == "**REDACTED**"
    assert diag["data"]["client"]["cpf"] == "**REDACTED**"
    assert diag["data"]["client"]["email"] == "**REDACTED**"
    assert diag["data"]["dashboard"]["consumption"]["INTERNET"]["unit"] == "GB"


async def test_config_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_client.async_login.side_effect = VivoEasyApiAuthenticationError("nope")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MSISDN: "+55 (31) 99999-9999", CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MSISDN: "+55 (31) 99999-9999", CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_MSISDN: MSISDN, CONF_PASSWORD: PASSWORD}
    assert result["result"].unique_id == MSISDN
