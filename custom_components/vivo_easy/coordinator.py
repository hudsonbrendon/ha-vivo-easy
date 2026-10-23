"""Coordinator de atualização do Vivo Easy."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
        # O dashboard é obrigatório; o resto é complementar e tolera falha.
        dashboard = await self.client.async_get_dashboard()
        now = dt_util.now()
        complementary = {
            "prime": self.client.async_get_prime_status(),
            "line": self.client.async_get_line_status(),
            "client": self.client.async_get_client(),
            "renewals": self.client.async_get_renewals(),
            "overbalance": self.client.async_get_overbalance(),
            "mgm": self.client.async_get_mgm(),
            "internet_catalog": self.client.async_get_internet_catalog(),
            "daily_catalog": self.client.async_get_daily_catalog(),
            "notifications": self.client.async_get_notifications(),
            "purchase_history": self.client.async_get_purchase_history(
                now.year, now.month
            ),
        }
        data: dict[str, Any] = {"dashboard": dashboard}
        results = await asyncio.gather(
            *complementary.values(), return_exceptions=True
        )
        for key, result in zip(complementary, results, strict=True):
            if isinstance(result, Exception):
                LOGGER.debug("%s indisponível: %s", key, result)
                data[key] = None
            else:
                data[key] = result
        return data
