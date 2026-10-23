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
        VivoEasyClientSensor(coordinator),
        VivoEasyOverbalanceSensor(coordinator),
        VivoEasyRenewalsSensor(coordinator),
        VivoEasyMgmSensor(coordinator),
        VivoEasyNotificationsSensor(coordinator),
        VivoEasyPurchaseHistorySensor(coordinator),
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
        """Preço do plano e flags da assinatura."""
        prime = self._prime()
        plan = prime.get("plan") or {}
        return {
            "preco": plan.get("price"),
            "preco_total": plan.get("totalPrice"),
            "tipo": plan.get("type"),
            "parcelas": plan.get("numberInstallments"),
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


def _mask_cpf(cpf: str | None) -> str | None:
    """Mascara o CPF deixando só os 3 dígitos do meio visíveis."""
    if not cpf:
        return cpf
    digits = "".join(c for c in cpf if c.isdigit())
    if len(digits) != 11:
        return "***"
    return f"***.{digits[3:6]}.***-**"


class VivoEasyClientSensor(VivoEasyEntity, SensorEntity):
    """Nome do titular + dados do perfil (plano, email, cpf mascarado)."""

    _attr_translation_key = "client"

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de cliente."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_cliente"

    def _client(self) -> dict[str, Any]:
        return self.coordinator.data.get("client") or {}

    @property
    def native_value(self) -> str | None:
        """Nome do titular."""
        return self._client().get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Email, CPF mascarado, plano e flags do cliente."""
        client = self._client()
        plan = client.get("plan") or {}
        return {
            "email": client.get("email"),
            "cpf": _mask_cpf(client.get("cpf")),
            "plano": plan.get("name"),
            "customer_id": client.get("customerId"),
            "aguardando_renovacao": client.get("isAwaitingRenewal"),
            "erro_renovacao": client.get("isRenewalError"),
            "limite_compra": client.get("purchaseLimitValue"),
        }


class VivoEasyOverbalanceSensor(VivoEasyEntity, SensorEntity):
    """Saldo extra (overbalance) em reais."""

    _attr_translation_key = "overbalance"
    _attr_native_unit_of_measurement = "BRL"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de saldo extra."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_saldo_extra"

    @property
    def native_value(self) -> float | None:
        """Valor do saldo extra."""
        over = self.coordinator.data.get("overbalance") or {}
        return over.get("overbalance")


class VivoEasyRenewalsSensor(VivoEasyEntity, SensorEntity):
    """Quantidade de renovações automáticas ativas."""

    _attr_translation_key = "renewals"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de renovações."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_renovacoes"

    def _items(self) -> list[dict[str, Any]]:
        renewals = self.coordinator.data.get("renewals") or {}
        return renewals.get("items") or []

    @property
    def native_value(self) -> int:
        """Número de renovações."""
        return len(self._items())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Lista das renovações (componentId usado nos serviços)."""
        return {
            "tem_cartao": (self.coordinator.data.get("renewals") or {}).get(
                "hasCreditCard"
            ),
            "itens": [
                {
                    "component_id": r.get("componentId"),
                    "volume": r.get("volume"),
                    "preco": r.get("offerPrice"),
                    "ativo": r.get("active"),
                }
                for r in self._items()
            ],
        }


class VivoEasyMgmSensor(VivoEasyEntity, SensorEntity):
    """Indique e ganhe: código e usos."""

    _attr_translation_key = "mgm"

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor MGM."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_mgm"

    def _mgm(self) -> dict[str, Any]:
        return self.coordinator.data.get("mgm") or {}

    @property
    def native_value(self) -> str | None:
        """Código de indicação."""
        return self._mgm().get("code")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Usos e mensagem de compartilhamento."""
        mgm = self._mgm()
        return {
            "usos_atuais": mgm.get("currentUse"),
            "usos_maximos": mgm.get("maxUse"),
            "mensagem": mgm.get("message"),
            "valor_minimo_compra": mgm.get("minPurchaseValue"),
        }


class VivoEasyNotificationsSensor(VivoEasyEntity, SensorEntity):
    """Quantidade de notificações da conta."""

    _attr_translation_key = "notifications"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de notificações."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_notificacoes"

    @property
    def native_value(self) -> int | None:
        """Número de notificações (lista ou campo count)."""
        data = self.coordinator.data.get("notifications")
        if data is None:
            return None
        if isinstance(data, list):
            return len(data)
        items = data.get("notifications") or data.get("items")
        return len(items) if isinstance(items, list) else data.get("count")


class VivoEasyPurchaseHistorySensor(VivoEasyEntity, SensorEntity):
    """Total gasto em compras no mês corrente."""

    _attr_translation_key = "purchase_history"
    _attr_native_unit_of_measurement = "BRL"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: VivoEasyDataUpdateCoordinator) -> None:
        """Inicializa o sensor de histórico de compras."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.msisdn}_historico_compras"

    def _items(self) -> list[dict[str, Any]]:
        data = self.coordinator.data.get("purchase_history") or {}
        return data.get("items") or data.get("purchases") or []

    @property
    def native_value(self) -> float:
        """Soma dos valores das compras do mês."""
        total = 0.0
        for item in self._items():
            value = item.get("value") or item.get("price") or item.get("amount") or 0
            try:
                total += float(value)
            except (TypeError, ValueError):
                continue
        return round(total, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Quantidade de compras no mês."""
        return {"quantidade": len(self._items())}
