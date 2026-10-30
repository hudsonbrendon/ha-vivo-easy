"""Fixtures: cliente Vivo Easy mockado."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vivo_easy.const import CONF_MSISDN, DOMAIN

MSISDN = "5531999999999"
PASSWORD = "senha123"

DASHBOARD = {
    "consumption": {
        "INTERNET": {
            "remainingVolume": 7.5,
            "totalVolume": 10,
            "unit": "GB",
            "unlimited": False,
        }
    },
    "wallet": {"credits": [{"name": "Bônus", "value": 10.5, "expirationDate": None}]},
    "coupons": [{"id": 1}],
    "unseenCoupons": True,
}
CLIENT = {
    "name": "Fulano",
    "email": "f@x.com",
    "cpf": "12345678901",
    "plan": {"name": "Easy"},
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in every test."""


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Patch VivoEasyApiClient in the integration and the config flow."""
    client = MagicMock()
    client.msisdn = MSISDN
    client.customer_id = "cust-1"
    client.async_login = AsyncMock()
    client.async_get_dashboard = AsyncMock(return_value=DASHBOARD)
    client.async_get_client = AsyncMock(return_value=CLIENT)
    client.async_get_line_status = AsyncMock(return_value={"status": "ADHERED"})
    for name in (
        "async_get_prime_status",
        "async_get_renewals",
        "async_get_overbalance",
        "async_get_mgm",
        "async_get_internet_catalog",
        "async_get_daily_catalog",
        "async_get_notifications",
        "async_get_purchase_history",
    ):
        setattr(client, name, AsyncMock(return_value={}))
    client.async_renew_prime = AsyncMock(return_value={"ok": True})
    with (
        patch("custom_components.vivo_easy.VivoEasyApiClient", return_value=client),
        patch(
            "custom_components.vivo_easy.config_flow.VivoEasyApiClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Config entry for the test line."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Vivo Easy {MSISDN}",
        unique_id=MSISDN,
        data={CONF_MSISDN: MSISDN, CONF_PASSWORD: PASSWORD},
        entry_id="01VIVOEASYENTRY0000000001",
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry and load it."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
