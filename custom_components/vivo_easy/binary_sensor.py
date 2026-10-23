"""Binary sensors do Vivo Easy (status da linha)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import VivoEasyEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import VivoEasyDataUpdateCoordinator
    from .data import VivoEasyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VivoEasyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Cria o binary sensor de linha ativa."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([VivoEasyLineActiveSensor(coordinator)])


class VivoEasyLineActiveSensor(VivoEasyEntity, BinarySensorEntity):
    """Linha ativa (status != cancelado/bloqueado)."""

    _attr_translation_key = "line_active"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_linha_ativa"

    def _line(self) -> dict[str, Any]:
        return self.coordinator.data.get("line") or {}

    @property
    def is_on(self) -> bool | None:
        """True se a linha estiver ativa.

        Enum LineStatus.Status (RE): ADHERED/MIGRATED = ativa; CANCELLED,
        SUSPENDED_THEFT, PENDING_*, ADHERING*, MIGRATING = inativa.
        """
        line = self._line()
        status = line.get("status")
        if status is None:
            return None
        return str(status).upper() in {"ADHERED", "MIGRATED"}

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Flags do status da linha."""
        line = self._line()
        return {
            "status": line.get("status"),
            "estrangeiro": line.get("foreign"),
            "fwa": line.get("fwa"),
            "fluxo_migracao": line.get("migrationFlow"),
            "precisa_autenticar": line.get("mustAuthenticate"),
        }
