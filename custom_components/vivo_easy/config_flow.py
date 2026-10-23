"""Config flow do Vivo Easy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    VivoEasyApiAuthenticationError,
    VivoEasyApiClient,
    VivoEasyApiCommunicationError,
    VivoEasyApiError,
)
from .const import CONF_MSISDN, DOMAIN


class VivoEasyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fluxo de configuração via UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo inicial: pede número da linha e senha."""
        errors: dict[str, str] = {}
        if user_input is not None:
            msisdn = "".join(c for c in user_input[CONF_MSISDN] if c.isdigit())
            try:
                client = VivoEasyApiClient(
                    msisdn=msisdn,
                    password=user_input[CONF_PASSWORD],
                    session=async_get_clientsession(self.hass),
                )
                await client.async_login()
            except VivoEasyApiAuthenticationError:
                errors["base"] = "invalid_auth"
            except VivoEasyApiCommunicationError:
                errors["base"] = "cannot_connect"
            except VivoEasyApiError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(msisdn)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Vivo Easy {msisdn}",
                    data={CONF_MSISDN: msisdn, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MSISDN): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
