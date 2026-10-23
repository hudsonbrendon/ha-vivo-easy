"""Sensores do Vivo Easy.

O endpoint `clients/dashboard/v2` devolve `consumption` como um mapa
`{<EasyProduct>: Consumption}` (ex.: "INTERNET", "NATIONAL_VOICE", "GIGAS").
Criamos um sensor por produto presente (volume restante) com o resto dos
campos como atributos, mais carteira, cupons e dados do Easy Prime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass

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
    """Cria os sensores a partir do primeiro refresh do coordinator."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = [
        VivoEasyWalletSensor(coordinator),
        VivoEasyCouponsSensor(coordinator),
        VivoEasyPrimePlanSensor(coordinator),
        VivoEasyPrimeNextChargeSensor(coordinator),
        VivoEasyPrimeExpirationSensor(coordinator),
    ]
    consumption = (coordinator.data.get("dashboard") or {}).get("consumption") or {}
    entities.extend(
        VivoEasyConsumptionSensor(coordinator, product) for product in consumption
    )
    async_add_entities(entities)


class VivoEasyConsumptionSensor(VivoEasyEntity, SensorEntity):
    """Volume restante de um produto (internet, voz, gigas...)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: VivoEasyDataUpdateCoordinator, product: str
    ) -> None:
        """product = chave do mapa de consumo (ex: INTERNET)."""
        super().__init__(coordinator)
        self._product = product
        self._attr_unique_id = f"{coordinator.client.msisdn}_consumo_{product.lower()}"
        self._attr_translation_key = "consumption"
        self._attr_name = product.replace("_", " ").title()

    def _data(self) -> dict[str, Any]:
        consumption = (self.coordinator.data.get("dashboard") or {}).get(
            "consumption"
        ) or {}
        return consumption.get(self._product) or {}

    @property
    def native_value(self) -> float | None:
        """Volume restante; None quando ilimitado."""
        data = self._data()
        if data.get("unlimited"):
            return None
        return data.get("remainingVolume")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unidade reportada pela API (GB, DAY...)."""
        return self._data().get("unit")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Demais campos do consumo como atributos."""
        data = self._data()
        return {
            "titulo": data.get("title"),
            "descricao": data.get("description"),
            "volume_total": data.get("totalVolume"),
            "ilimitado": data.get("unlimited"),
            "renovacao_automatica": data.get("autoRenew"),
            "diario": data.get("daily"),
            "cashback": data.get("cash"),
        }


class VivoEasyWalletSensor(VivoEasyEntity, SensorEntity):
    """Soma dos créditos da carteira (bônus/cashback)."""

    _attr_translation_key = "wallet"
    _attr_native_unit_of_measurement = "BRL"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de carteira."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_carteira"

    def _credits(self) -> list[dict[str, Any]]:
        wallet = (self.coordinator.data.get("dashboard") or {}).get("wallet") or {}
        return wallet.get("credits") or []

    @property
    def native_value(self) -> float:
        """Total em reais dos créditos."""
        return round(sum(float(c.get("value") or 0) for c in self._credits()), 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Detalhe de cada crédito."""
        return {
            "creditos": [
                {
                    "nome": c.get("name"),
                    "valor": c.get("value"),
                    "expira_em": c.get("expirationDate"),
                }
                for c in self._credits()
            ]
        }


class VivoEasyCouponsSensor(VivoEasyEntity, SensorEntity):
    """Quantidade de cupons disponíveis."""

    _attr_translation_key = "coupons"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de cupons."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_cupons"

    @property
    def native_value(self) -> int:
        """Número de cupons."""
        coupons = (self.coordinator.data.get("dashboard") or {}).get("coupons") or []
        return len(coupons)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Flag de cupons não vistos."""
        dashboard = self.coordinator.data.get("dashboard") or {}
        return {"nao_vistos": dashboard.get("unseenCoupons")}


class _PrimeSensor(VivoEasyEntity, SensorEntity):
    """Base para sensores do Easy Prime."""

    def _prime(self) -> dict[str, Any]:
        return self.coordinator.data.get("prime") or {}


class VivoEasyPrimePlanSensor(_PrimeSensor):
    """Nome do plano Easy Prime atual."""

    _attr_translation_key = "prime_plan"

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de plano."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_prime_plano"

    @property
    def native_value(self) -> str | None:
        """Nome do plano."""
        plan = self._prime().get("plan") or {}
        return plan.get("name") or plan.get("title")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Flags da assinatura."""
        prime = self._prime()
        return {
            "cartao_ativo": prime.get("hasActiveCreditCard"),
            "erro_renovacao": prime.get("hasRenewalError"),
            "cancelamento_agendado": prime.get("hasScheduledCancellation"),
        }


class VivoEasyPrimeNextChargeSensor(_PrimeSensor):
    """Data da próxima cobrança do Easy Prime."""

    _attr_translation_key = "prime_next_charge"

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de próxima cobrança."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_prime_proxima_cobranca"

    @property
    def native_value(self) -> str | None:
        """Data da próxima cobrança (string como vem da API)."""
        return self._prime().get("nextChargeDate")


class VivoEasyPrimeExpirationSensor(_PrimeSensor):
    """Data de expiração da assinatura Easy Prime."""

    _attr_translation_key = "prime_expiration"

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de expiração."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_prime_expiracao"

    @property
    def native_value(self) -> str | None:
        """Data de expiração (string como vem da API)."""
        return self._prime().get("subscriptionExpirationDate")
