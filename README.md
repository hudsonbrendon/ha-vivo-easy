# Vivo Easy — Home Assistant

Integração não-oficial que traz os dados da sua linha **Vivo Easy** para o Home
Assistant: consumo de internet/voz, gigas, carteira (bônus/cashback), cupons,
assinatura Easy Prime e status da linha.

Baseada em engenharia reversa do app oficial (`br.com.vivo.vivoeasy`). Detalhes
do protocolo em [`REVERSE_ENGINEERING.md`](REVERSE_ENGINEERING.md).

> Projeto pessoal, sem vínculo com a Vivo/Telefônica. Use com a sua própria conta.

## Instalação (HACS)

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
- **Cupons** — quantidade disponível + flag de não vistos.
- **Easy Prime** — plano, próxima cobrança, expiração da assinatura.
- **Linha ativa** (binary sensor) — status/estrangeiro/FWA nos atributos.

Atualização a cada 30 min (cloud polling).

## Desenvolvimento

```bash
python3 -I tests/test_crypto.py   # valida os primitivos de login/hashcash
```

## Aviso

A API é privada e pode mudar sem aviso — uma atualização do app pode exigir
reajuste. A integração só faz leituras.
