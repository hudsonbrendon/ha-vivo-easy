"""Diagnóstico da integração Vivo Easy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_MSISDN
from .data import VivoEasyConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_MSISDN,
    "unique_id",
    "title",
    "name",
    "email",
    "cpf",
    "customerId",
    "clientId",
    "code",
    "number",
    "msisdn",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VivoEasyConfigEntry
) -> dict[str, Any]:
    """Devolve entry + último snapshot do coordinator, com dados pessoais redigidos."""
    coordinator = entry.runtime_data.coordinator
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "unique_id": entry.unique_id}, TO_REDACT
        ),
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
