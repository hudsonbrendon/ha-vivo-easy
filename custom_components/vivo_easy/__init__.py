"""Integração Vivo Easy para Home Assistant."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import VivoEasyApiClient
from .const import CONF_MSISDN
from .coordinator import VivoEasyDataUpdateCoordinator
from .data import VivoEasyConfigEntry, VivoEasyData
from .services import async_register_services

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: VivoEasyConfigEntry) -> bool:
    """Configura a integração a partir de um config entry."""
    client = VivoEasyApiClient(
        msisdn=entry.data[CONF_MSISDN],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    await client.async_login()

    coordinator = VivoEasyDataUpdateCoordinator(hass, client)
    entry.runtime_data = VivoEasyData(
        client=client,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VivoEasyConfigEntry) -> bool:
    """Descarrega o config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: VivoEasyConfigEntry) -> None:
    """Recarrega o config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
