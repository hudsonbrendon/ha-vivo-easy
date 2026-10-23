# Engenharia reversa — app Vivo Easy

Alvo: `br.com.vivo.vivoeasy` v4.3.9 (versionCode 315), APK baixado da APKPure,
analisado estaticamente com `jadx` (nunca executado). App Android nativo
Kotlin/Java (2 dex), DTOs **não ofuscados** em `br.com.zup.vivoeasy3.data.model.*`.

## Backend

- Gateway de produção: `https://vivo.gateway.zup.me/easy/v3/`
- Outros bases vistos: `/easy-events/v2/`, `/easy-wallet/v1/`, `/aws-images/v1/`
- **Certificate pinning** (SHA-256) para `vivo.gateway.zup.me` em `e4/g.java`.
  É enforcement client-side do app; um cliente Python faz seu próprio TLS e não
  é afetado.

## Autenticação (interceptor `e4/d.java` + `e4/g.java`)

Headers fixos em toda requisição ao gateway:

| Header | Valor |
|---|---|
| `X-Organization-Slug` | `vivo` |
| `X-Application-Key` | `1ef259a08374013f98a712ff0c6c0a2a` |
| `User-Agent` / `x-app-os` | `ANDROID` |
| `x-app-device` | modelo do device |
| `x-app-version` | ex. `4.3.9` |
| `authorization` | token de acesso atual |
| `x-uid` | uid do cliente |

**Token rotativo**: cada resposta pode trazer `x-access-token` (e `x-uid`); o app
substitui o token atual e usa na próxima chamada (`Preferences "current_token"`).

**Hashcash = desafio-resposta** (não é PoW incondicional): a requisição vai sem
`x-hashcash`; se a **resposta** trouxer um header `x-hashcash: <n>:...`, o app
resolve `Utils.solveHashcash` e **reenvia** a mesma requisição com o header. Os
GETs de leitura (dashboard etc.) normalmente não são desafiados.

### Login — `POST authenticate?isAutoLogin=false`

Body `AuthCredentials`:

```json
{ "number": "<msisdn>", "hash": "<generateAuthToken(msisdn, senha)>",
  "deviceId": "<uuid>", "deviceToken": "<push token, pode vazio>" }
```

Mapa de headers de device (`DeviceUtils.generateDeviceHeaders`) acompanha o POST.
Resposta: `AuthResponse { number, customerId, clientId, mustMigrateSoon }` +
headers `x-access-token` / `x-uid`.

## Primitivos de crypto (`br.com.zup.vivoeasy3.utils.Utils`)

Portados em `custom_components/vivo_easy/api.py` e verificados em
`tests/test_crypto.py`:

- `generateAuthToken(msisdn, senha)` = `base64("{msisdn}&@#!&{senha}&@#!&GG_IZI")`
- `hashMsisdn(msisdn)` = `sha256(msisdn + ",s)S.X-p;SdwsA2&lR.dIy|SCg}bZ1{&7y^%kpk2u9V+{mEO%n3HccBYJIKhFujb")`
- `solveHashcash(ch)`: `n = int(ch.split(":")[0])`; acha `i` tal que
  `sha256("{ch}:{i}")` (hex) comece com `n` zeros; retorna `"{ch}:{i}"`.

As libs nativas `libsigner`/`libmcrypt`/`libdigest` são do SDK antifraude
**Topaz** (`br.com.topaz.heartbeat`, fingerprint/RASP) e **não** são exigidas
pelos endpoints de leitura do gateway — o interceptor `e4/d.java` não assina as
requisições do gateway.

## Endpoints de leitura usados pela integração (interface `f4/a.java`)

`@f`=GET `@o`=POST `@i`=Header `@s`=Path `@t`=Query `@dn.a`=Body.

| Endpoint | Retorno | Uso no HA |
|---|---|---|
| `GET clients/dashboard/v2` | `DashboardConsumption` | consumo por produto, carteira, cupons |
| `GET primes/current/status/v3` | `NPVMySubscription` | assinatura Easy Prime |
| `GET clients/{msisdn}/status/v2` | `LineStatus` | status da linha |

### `DashboardConsumption`

- `consumption: Map<EasyProduct, Consumption>` — chaves: `INTERNET`,
  `LIMITED_INTERNET`, `UNLIMITED_INTERNET`, `GIGAS`, `NATIONAL_VOICE`, apps
  (`NETFLIX`, `SPOTIFY`, `TIKTOK`...).
  - `Consumption`: `totalVolume`, `remainingVolume`, `unit` (OfferType: GB/DAY),
    `daily`, `cash`, `autoRenew`, `unlimited`, `title`, `description`,
    `balances[]`, `renewInfo`.
- `wallet.credits[]`: `{ name, value, expirationDate, details, components }`.
- `coupons[]`, `unseenCoupons`, `alertCards[]`, `giftModal`.

### `NPVMySubscription`

`plan`, `nextChargeDate`, `subscriptionExpirationDate`, `hasActiveCreditCard`,
`hasRenewalError`, `hasScheduledCancellation`, `overbalance`.

### `LineStatus`

`status` (enum), `foreign`, `fwa`, `migrationFlow`, `mustAuthenticate`, `paymentId`.

## Outros endpoints mapeados (não usados, apenas referência)

`catalogs/plans/clients/v3`, `catalogs/plans/v3`, `extracts/internet/period/{p}`,
`extracts/call/period/{p}/component/{c}`, `coupons/wallet`, `renewals/v2`,
`retention/*`, `purchases/*`, `migrations/*`, `mgm/*`, `roaming/*`. POSTs
sensíveis exigem `x-hashcash` e/ou `x-auth-pwd`.
