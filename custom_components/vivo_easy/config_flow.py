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
        placeholders: dict[str, str] = {"error": ""}
        if user_input is not None:
            msisdn = "".join(c for c in user_input[CONF_MSISDN] if c.isdigit())
            password = user_input[CONF_PASSWORD].strip()
            try:
                client = VivoEasyApiClient(
                    msisdn=msisdn,
                    password=password,
                    session=async_get_clientsession(self.hass),
                )
                await client.async_login()
            except VivoEasyApiAuthenticationError as err:
                errors["base"] = "invalid_auth"
                placeholders["error"] = str(err)
            except VivoEasyApiCommunicationError:
                errors["base"] = "cannot_connect"
            except VivoEasyApiError as err:
                errors["base"] = "unknown"
                placeholders["error"] = str(err)
            else:
                await self.async_set_unique_id(msisdn)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Vivo Easy {msisdn}",
                    data={CONF_MSISDN: msisdn, CONF_PASSWORD: password},
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
            description_placeholders=placeholders,
        )
