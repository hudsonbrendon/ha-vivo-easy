"""Tipos compartilhados da integração Vivo Easy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import VivoEasyApiClient
    from .coordinator import VivoEasyDataUpdateCoordinator


type VivoEasyConfigEntry = ConfigEntry[VivoEasyData]


@dataclass
class VivoEasyData:
    """Dados guardados no ConfigEntry."""

    client: VivoEasyApiClient
    coordinator: VivoEasyDataUpdateCoordinator
    integration: Integration
