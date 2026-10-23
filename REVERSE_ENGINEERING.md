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

## Primitivos de crypto (`Utils.java` / `SecurityUtils.java`)

Portados em `custom_components/vivo_easy/api.py` e verificados em
`tests/test_crypto.py`:

- `generateAuthToken(msisdn, senha)` = `base64("{msisdn}&@#!&{senha}&@#!&GG_IZI")`
  (campo `hash` do `AuthCredentials` no login).
- `hashMsisdn(msisdn)` = `sha256(msisdn + ",s)S.X-p;SdwsA2&lR.dIy|SCg}bZ1{&7y^%kpk2u9V+{mEO%n3HccBYJIKhFujb")`
- `solveHashcash(ch)`: `n = int(ch.split(":")[0])`; acha `i` tal que
  `sha256("{ch}:{i}")` (hex) comece com `n` zeros; retorna `"{ch}:{i}"`.
- `SecurityUtils.generateHash(senha)` = **PBKDF2-HMAC-SHA1**(senha,
  salt `a,0,2,b,3,q,1,l,o,4,7,8,c,9,01,02`, 1000 iterações, dkLen 64 bytes) em
  hex (128 chars). É o valor do header **`x-auth-pwd`** exigido nas ações
  sensíveis (compra, renovação, cancelamento, troca de cartão). Confirmado em
  `CheckoutFragment`/`DashboardFragment`: `generateHash(AuthPreferences.restore().getPassword())`.

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

## Leituras complementares usadas (coordinator, best-effort)

| Endpoint | Retorno | Sensor |
|---|---|---|
| `GET clients` | `Client` | Titular (nome, cpf mascarado, plano, email) |
| `GET renewals` | `Renewals` | Renovações automáticas (+ componentId) |
| `GET adherence/{msisdn}/overbalance` | `OverBalance` | Saldo extra |
| `GET mgm/client/v2` | `InfoMgm` | Indique e ganhe (código, usos) |
| `GET catalogs/clients/addons/internet/v2` | `CatalogInternet` | catálogo p/ compra |
| `GET catalogs/clients/addons/daily/v2` | `CatalogApps` | catálogo p/ compra |
| `GET notifications/q` | `NotificationResponse` | Notificações |
| `GET purchase-history/{ano}/{mes}/v3` | `Shopping` | Compras do mês |

## Ações expostas como serviços HA (escrita)

Enviam `x-auth-pwd` (= `generateHash(senha)`) e resolvem hashcash sob desafio.

| Serviço | Endpoint | Headers |
|---|---|---|
| `comprar_pacote` | `POST purchases` | x-auth-pwd |
| `ativar_renovacao` | `POST renewals/v2` | x-auth-pwd, x-hashcash |
| `cancelar_renovacao` | `DELETE renewals/{componentId}` | x-auth-pwd |
| `renovar_prime` | `POST purchases/renew-prime` | x-auth-pwd, x-hashcash |
| `reativar_prime` | `PUT primes/client/reactivation` | x-auth-pwd, x-hashcash |
| `avaliar_app` | `POST clients/rating-app` | — |
| `agendar_cancelamento_linha` | `POST retention/schedule-line-cancellation` | x-auth-pwd (exige `confirmar`) |
| `cancelar_linha` | `POST retention/v2/cancel-line` | x-auth-pwd (irreversível, exige `confirmar`) |

Corpos de `purchases`/`renewals/v2` inferidos dos DTOs (`PurchaseRequest`:
`offerId`, `offers[]`, `couponCode`, `paymentMethod`; `Renewal`: `componentId`).
Podem precisar de ajuste fino com captura real.

## Outros endpoints mapeados (referência, não expostos)

`catalogs/plans/clients/v3`, `catalogs/plans/v3`, `extracts/internet/period/{p}`,
`extracts/daily|call/period/{p}/component/{c}`, `coupons/*`, `credit_cards/*`
(f4/b.java — cadastro/troca de cartão), `pix/purchase/{id}/status`,
`adherence/purchase/pix`, `migrations/*`, `roaming/*`, `shopping-cart`,
`purchase-limit`. A lista completa (~110 endpoints, verbo + path + retorno +
headers) foi extraída de `f4/a.java` e `f4/b.java`.
