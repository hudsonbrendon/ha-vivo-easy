"""Coordinator de atualização do Vivo Easy."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    VivoEasyApiAuthenticationError,
    VivoEasyApiError,
)
from .const import DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api import VivoEasyApiClient
    from .data import VivoEasyConfigEntry


class VivoEasyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Puxa dashboard + prime + status da linha a cada ciclo."""

    config_entry: VivoEasyConfigEntry

    def __init__(self, hass: HomeAssistant, client: VivoEasyApiClient) -> None:
        """Inicializa o coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Busca os dados. Falhas de auth tentam um relogin antes de desistir."""
        try:
            return await self._fetch_all()
        except VivoEasyApiAuthenticationError:
            # Token rotativo pode ter expirado: refaz o login uma vez.
            try:
                await self.client.async_login()
                return await self._fetch_all()
            except VivoEasyApiAuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except VivoEasyApiError as err:
                raise UpdateFailed(str(err)) from err
        except VivoEasyApiError as err:
            raise UpdateFailed(str(err)) from err

    async def _fetch_all(self) -> dict[str, Any]:
        dashboard = await self.client.async_get_dashboard()
        # Prime e status da linha são complementares: se falharem, seguem vazios.
        prime: dict[str, Any] | None = None
        line: dict[str, Any] | None = None
        try:
            prime = await self.client.async_get_prime_status()
        except VivoEasyApiError as err:
            LOGGER.debug("prime status indisponível: %s", err)
        try:
            line = await self.client.async_get_line_status()
        except VivoEasyApiError as err:
            LOGGER.debug("line status indisponível: %s", err)
        return {"dashboard": dashboard, "prime": prime, "line": line}
