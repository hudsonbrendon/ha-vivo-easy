"""Serviços (ações) da integração Vivo Easy.

Expõem as chamadas de escrita do app como serviços do Home Assistant. As ações
sensíveis mandam o header `x-auth-pwd` (PBKDF2 da senha) automaticamente; as
irreversíveis (cancelamento) exigem `confirmar: true`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import VivoEasyApiClient, VivoEasyApiError
from .const import DOMAIN

if TYPE_CHECKING:
    from .data import VivoEasyConfigEntry

SERVICE_PURCHASE = "comprar_pacote"
SERVICE_ENABLE_RENEWAL = "ativar_renovacao"
SERVICE_DISABLE_RENEWAL = "cancelar_renovacao"
SERVICE_RENEW_PRIME = "renovar_prime"
SERVICE_REACTIVATE_PRIME = "reativar_prime"
SERVICE_RATE_APP = "avaliar_app"
SERVICE_SCHEDULE_CANCELLATION = "agendar_cancelamento_linha"
SERVICE_CANCEL_LINE = "cancelar_linha"

ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_OFFER_ID = "offer_id"
ATTR_COUPON = "coupon_code"
ATTR_COMPONENT_ID = "component_id"
ATTR_STARS = "stars"
ATTR_CONFIRM = "confirmar"

_ENTRY = {vol.Optional(ATTR_CONFIG_ENTRY): cv.string}


def _client(hass: HomeAssistant, call: ServiceCall) -> VivoEasyApiClient:
    """Resolve o cliente: entrada informada, ou a única carregada."""
    entries: list[VivoEasyConfigEntry] = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state.recoverable and getattr(e, "runtime_data", None)
    ]
    entry_id = call.data.get(ATTR_CONFIG_ENTRY)
    if entry_id:
        match = next((e for e in entries if e.entry_id == entry_id), None)
        if match is None:
            msg = f"config_entry_id {entry_id} não encontrado"
            raise ServiceValidationError(msg)
        return match.runtime_data.client
    if len(entries) != 1:
        msg = "Várias linhas configuradas: informe config_entry_id"
        raise ServiceValidationError(msg)
    return entries[0].runtime_data.client


def _require_confirm(call: ServiceCall) -> None:
    if not call.data.get(ATTR_CONFIRM):
        msg = "Ação irreversível: passe confirmar: true para prosseguir"
        raise ServiceValidationError(msg)


def async_register_services(hass: HomeAssistant) -> None:  # noqa: C901
    """Registra os serviços do domínio (idempotente)."""
    if hass.services.has_service(DOMAIN, SERVICE_PURCHASE):
        return

    async def _run(call: ServiceCall, coro_name: str, **kwargs: object) -> ServiceResponse:
        client = _client(hass, call)
        try:
            result = await getattr(client, coro_name)(**kwargs)
        except VivoEasyApiError as err:
            raise HomeAssistantError(str(err)) from err
        # Dispara refresh de todos os coordinators dessa conta.
        for entry in hass.config_entries.async_entries(DOMAIN):
            if getattr(entry, "runtime_data", None):
                await entry.runtime_data.coordinator.async_request_refresh()
        return {"resultado": result} if isinstance(result, (dict, list)) else {}

    async def purchase(call: ServiceCall) -> ServiceResponse:
        return await _run(
            call,
            "async_purchase",
            offer_id=call.data[ATTR_OFFER_ID],
            coupon_code=call.data.get(ATTR_COUPON),
        )

    async def enable_renewal(call: ServiceCall) -> ServiceResponse:
        return await _run(
            call, "async_renew", body={"componentId": call.data[ATTR_COMPONENT_ID]}
        )

    async def disable_renewal(call: ServiceCall) -> ServiceResponse:
        return await _run(
            call, "async_delete_renewal", component_id=call.data[ATTR_COMPONENT_ID]
        )

    async def renew_prime(call: ServiceCall) -> ServiceResponse:
        return await _run(call, "async_renew_prime")

    async def reactivate_prime(call: ServiceCall) -> ServiceResponse:
        return await _run(call, "async_reactivate_prime")

    async def rate_app(call: ServiceCall) -> ServiceResponse:
        return await _run(call, "async_rate_app", stars=call.data[ATTR_STARS])

    async def schedule_cancellation(call: ServiceCall) -> ServiceResponse:
        _require_confirm(call)
        return await _run(call, "async_schedule_line_cancellation")

    async def cancel_line(call: ServiceCall) -> ServiceResponse:
        _require_confirm(call)
        return await _run(call, "async_cancel_line")

    reg = hass.services.async_register
    reg(
        DOMAIN,
        SERVICE_PURCHASE,
        purchase,
        schema=vol.Schema(
            {
                **_ENTRY,
                vol.Required(ATTR_OFFER_ID): cv.string,
                vol.Optional(ATTR_COUPON): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(
        DOMAIN,
        SERVICE_ENABLE_RENEWAL,
        enable_renewal,
        schema=vol.Schema({**_ENTRY, vol.Required(ATTR_COMPONENT_ID): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(
        DOMAIN,
        SERVICE_DISABLE_RENEWAL,
        disable_renewal,
        schema=vol.Schema({**_ENTRY, vol.Required(ATTR_COMPONENT_ID): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(DOMAIN, SERVICE_RENEW_PRIME, renew_prime, schema=vol.Schema(_ENTRY),
        supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, SERVICE_REACTIVATE_PRIME, reactivate_prime, schema=vol.Schema(_ENTRY),
        supports_response=SupportsResponse.OPTIONAL)
    reg(
        DOMAIN,
        SERVICE_RATE_APP,
        rate_app,
        schema=vol.Schema(
            {**_ENTRY, vol.Required(ATTR_STARS): vol.All(int, vol.Range(min=1, max=5))}
        ),
    )
    reg(
        DOMAIN,
        SERVICE_SCHEDULE_CANCELLATION,
        schedule_cancellation,
        schema=vol.Schema({**_ENTRY, vol.Required(ATTR_CONFIRM): cv.boolean}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(
        DOMAIN,
        SERVICE_CANCEL_LINE,
        cancel_line,
        schema=vol.Schema({**_ENTRY, vol.Required(ATTR_CONFIRM): cv.boolean}),
        supports_response=SupportsResponse.OPTIONAL,
    )
