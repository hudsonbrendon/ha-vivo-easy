<p align="center">
  <img src="custom_components/vivo_easy/brand/logo@2x.png" alt="Vivo Easy" height="128">
</p>

# Vivo Easy — Home Assistant

[![Tests](https://github.com/hudsonbrendon/ha-vivo-easy/actions/workflows/tests.yml/badge.svg)](https://github.com/hudsonbrendon/ha-vivo-easy/actions/workflows/tests.yml)
[![Hassfest](https://github.com/hudsonbrendon/ha-vivo-easy/actions/workflows/hassfest.yml/badge.svg)](https://github.com/hudsonbrendon/ha-vivo-easy/actions/workflows/hassfest.yml)
[![HACS](https://github.com/hudsonbrendon/ha-vivo-easy/actions/workflows/validate.yml/badge.svg)](https://github.com/hudsonbrendon/ha-vivo-easy/actions/workflows/validate.yml)
[![Release](https://img.shields.io/github/v/release/hudsonbrendon/ha-vivo-easy?sort=semver)](https://github.com/hudsonbrendon/ha-vivo-easy/releases)
[![Downloads](https://img.shields.io/github/downloads/hudsonbrendon/ha-vivo-easy/total)](https://github.com/hudsonbrendon/ha-vivo-easy/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6.0%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![License](https://img.shields.io/github/license/hudsonbrendon/ha-vivo-easy)](LICENSE)

Integração não-oficial que traz os dados da sua linha **Vivo Easy** para o Home
Assistant: consumo de internet/voz, gigas, carteira (bônus/cashback), cupons,
assinatura Easy Prime e status da linha.

Baseada em engenharia reversa do app oficial (`br.com.vivo.vivoeasy`). Detalhes
do protocolo em [`REVERSE_ENGINEERING.md`](REVERSE_ENGINEERING.md).

> Projeto pessoal, sem vínculo com a Vivo/Telefônica. Use com a sua própria conta.

## Instalação (HACS)

[![Abrir no HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hudsonbrendon&repository=ha-vivo-easy&category=integration)
[![Adicionar integração](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vivo_easy)

1. HACS → repositórios customizados → adicione `hudsonbrendon/ha-vivo-easy`
   (categoria *Integration*).
2. Instale "Vivo Easy" e reinicie o Home Assistant.
3. Ajustes → Dispositivos e Serviços → Adicionar Integração → **Vivo Easy**.
4. Informe o **número da linha** (com DDD, só dígitos — ex. `5531999999999`) e a
   **senha do app**.

Instalação manual: copie `custom_components/vivo_easy` para o seu
`config/custom_components/` e reinicie.

## Entidades

- **Consumo** — um sensor por produto do dashboard (Internet, Voz e SMS, Gigas…),
  com volume restante como estado e volume total / renovação / cashback nos
  atributos. Ilimitado reporta estado vazio.
- **Carteira** — soma dos créditos (BRL), com detalhe de cada crédito.
- **Saldo extra** — overbalance em reais.
- **Cupons** — quantidade disponível + flag de não vistos.
- **Easy Prime** — plano (com preço), próxima cobrança, expiração.
- **Titular** — nome, email, CPF mascarado, plano.
- **Renovações automáticas** — quantidade + lista (componentId para os serviços).
- **Indique e ganhe** — código e usos.
- **Notificações** e **Compras do mês** (total gasto).
- **Linha ativa** (binary sensor) — status/estrangeiro/FWA nos atributos.

Atualização a cada 30 min (cloud polling); os reads complementares são
best-effort (se um falhar, o resto continua).

## Ações (serviços)

Expostos em Ferramentas do desenvolvedor → Serviços. As sensíveis mandam o
`x-auth-pwd` automaticamente; as irreversíveis exigem `confirmar: true`.

| Serviço | O que faz |
|---|---|
| `vivo_easy.comprar_pacote` | Compra um pacote (`offer_id` do catálogo, `coupon_code` opcional) |
| `vivo_easy.ativar_renovacao` / `cancelar_renovacao` | Liga/desliga renovação automática (`component_id`) |
| `vivo_easy.renovar_prime` / `reativar_prime` | Renova/reativa o Easy Prime |
| `vivo_easy.avaliar_app` | Avalia o app (1–5) |
| `vivo_easy.agendar_cancelamento_linha` | Agenda cancelamento (requer `confirmar`) |
| `vivo_easy.cancelar_linha` | Cancela a linha — **irreversível** (requer `confirmar`) |

> ⚠️ Compras/renovações gastam créditos ou cobram no cartão. Cancelamentos
> mexem na sua linha. Use com cuidado.

## Desenvolvimento

```bash
python3 -I tests/test_crypto.py   # valida os primitivos de login/hashcash
```

## Aviso

A API é privada e pode mudar sem aviso — uma atualização do app pode exigir
reajuste. A integração só faz leituras.
