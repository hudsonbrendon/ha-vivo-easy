"""Entidade base do Vivo Easy."""

from __future__ import annotations

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VivoEasyDataUpdateCoordinator


class VivoEasyEntity(CoordinatorEntity[VivoEasyDataUpdateCoordinator]):
    """Base com device info compartilhado."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa a entidade."""
        super().__init__(coordinator)
        msisdn = coordinator.client.msisdn
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, msisdn)},
            manufacturer="Vivo",
            model="Vivo Easy",
            name=f"Vivo Easy {msisdn}",
        )
