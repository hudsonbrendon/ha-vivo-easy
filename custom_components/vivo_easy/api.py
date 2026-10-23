"""Cliente da API do Vivo Easy (engenharia reversa do app br.com.vivo.vivoeasy).

Reimplementa, em Python puro, o fluxo de autenticação e as chamadas de leitura
que o app faz contra o gateway `https://vivo.gateway.zup.me/easy/v3/`:

- `generate_auth_token` / `hash_msisdn` / `solve_hashcash`: portados de
  `br.com.zup.vivoeasy3.utils.Utils`.
- Token rotativo: cada resposta pode trazer um novo header `x-access-token`
  que vira o `authorization` da próxima requisição (ver interceptor `e4/d.java`).
- Hashcash é desafio-resposta: a requisição vai sem PoW; só se a resposta
  trouxer um header `x-hashcash` é que resolvemos e reenviamos.

Nenhuma lib nativa (libsigner/Topaz) é necessária para os endpoints de leitura.
O certificate pinning do app é client-side e não se aplica aqui.
"""

from __future__ import annotations

import base64
import hashlib
import socket
from typing import Any

import aiohttp
import async_timeout

BASE_URL = "https://vivo.gateway.zup.me/easy/v3"

# Headers fixos do interceptor e4/d.java
APPLICATION_KEY = "1ef259a08374013f98a712ff0c6c0a2a"
ORGANIZATION_SLUG = "vivo"

# Segredos portados de Utils.java / SecurityUtils.java (app v4.3.9)
_AUTH_TOKEN_SEP = "&@#!&"
_AUTH_TOKEN_SUFFIX = "&@#!&GG_IZI"
_MSISDN_HASH_SALT = ",s)S.X-p;SdwsA2&lR.dIy|SCg}bZ1{&7y^%kpk2u9V+{mEO%n3HccBYJIKhFujb"
# SecurityUtils.generateHash: PBKDF2WithHmacSHA1, 1000 iters, dkLen 64 bytes.
_PWD_SALT = "a,0,2,b,3,q,1,l,o,4,7,8,c,9,01,02"
_PWD_ITERATIONS = 1000
_PWD_DKLEN = 64

_TIMEOUT = 20
_MAX_HASHCASH_BITS = 6  # trava de segurança: n>6 estouraria tempo/CPU


class VivoEasyApiError(Exception):
    """Erro geral da API."""


class VivoEasyApiCommunicationError(VivoEasyApiError):
    """Falha de comunicação/timeout."""


class VivoEasyApiAuthenticationError(VivoEasyApiError):
    """Credenciais inválidas ou sessão expirada."""


def generate_auth_token(msisdn: str, password: str) -> str:
    """Utils.generateAuthToken: base64(msisdn&@#!&password&@#!&GG_IZI)."""
    raw = f"{msisdn}{_AUTH_TOKEN_SEP}{password}{_AUTH_TOKEN_SUFFIX}"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def hash_msisdn(msisdn: str) -> str:
    """Utils.hashMsisdn: sha256(msisdn + salt) hex."""
    return hashlib.sha256((msisdn + _MSISDN_HASH_SALT).encode("utf-8")).hexdigest()


def generate_hash(password: str) -> str:
    """SecurityUtils.generateHash: PBKDF2-HMAC-SHA1 hex (header x-auth-pwd)."""
    derived = hashlib.pbkdf2_hmac(
        "sha1",
        password.encode("utf-8"),
        _PWD_SALT.encode("utf-8"),
        _PWD_ITERATIONS,
        _PWD_DKLEN,
    )
    return derived.hex()


def solve_hashcash(challenge: str) -> str:
    """Utils.solveHashcash: acha i tal que sha256(challenge:i) comece com n zeros.

    `challenge` tem a forma "<n>:...". Retorna "<challenge>:<i>".
    """
    n = int(challenge.split(":")[0])
    if n > _MAX_HASHCASH_BITS:
        msg = f"hashcash difficulty {n} too high"
        raise VivoEasyApiError(msg)
    target = "0" * n
    i = 0
    while True:
        candidate = f"{challenge}:{i}"
        if hashlib.sha256(candidate.encode("utf-8")).hexdigest().startswith(target):
            return candidate
        i += 1


class VivoEasyApiClient:
    """Cliente autenticado do Vivo Easy."""

    def __init__(
        self,
        msisdn: str,
        password: str,
        session: aiohttp.ClientSession,
        device_id: str = "home-assistant",
    ) -> None:
        """msisdn = número da linha só com dígitos (ex: 5531999999999)."""
        self._msisdn = "".join(c for c in msisdn if c.isdigit())
        self._password = password
        self._session = session
        self._device_id = device_id
        self._access_token: str | None = None
        self._uid: str | None = None
        self.customer_id: str | None = None
        self.client_id: str | None = None

    @property
    def msisdn(self) -> str:
        """Número da linha (somente dígitos)."""
        return self._msisdn

    def _base_headers(self) -> dict[str, str]:
        headers = {
            "X-Organization-Slug": ORGANIZATION_SLUG,
            "X-Application-Key": APPLICATION_KEY,
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "ANDROID",
            "x-app-os": "ANDROID",
            "x-app-device": "HomeAssistant",
            "x-app-version": "4.3.9",
            "x-device-uuid": self._device_id,
        }
        if self._access_token:
            headers["authorization"] = self._access_token
        if self._uid:
            headers["x-uid"] = self._uid
        return headers

    def _capture_rotating_token(self, response: aiohttp.ClientResponse) -> None:
        # Interceptor e4/g.java: guarda x-access-token/x-uid de toda resposta.
        token = response.headers.get("x-access-token")
        if token:
            self._access_token = token
        uid = response.headers.get("x-uid")
        if uid:
            self._uid = uid

    async def async_login(self) -> None:
        """POST authenticate; captura o token rotativo inicial.

        O login por senha (AuthHelper.startAuthCredentials) manda
        `password` = generate_hash(senha) (PBKDF2); NAO o campo `hash`
        (esse e do fluxo de auto-login por parceiro).
        """
        credentials = {
            "number": self._msisdn,
            "password": generate_hash(self._password),
            "deviceId": self._device_id,
            "deviceToken": "",
        }
        response = await self._request(
            "POST",
            "authenticate",
            params={"isAutoLogin": "false"},
            json=credentials,
            authed=False,
        )
        if self._access_token is None:
            msg = "login did not return x-access-token"
            raise VivoEasyApiAuthenticationError(msg)
        self.customer_id = response.get("customerId")
        self.client_id = response.get("clientId")

    def _auth_pwd(self) -> str:
        """Valor do header x-auth-pwd (PBKDF2 da senha)."""
        return generate_hash(self._password)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        authed: bool = True,
        auth_pwd: bool = False,
    ) -> Any:
        """Faz a chamada, trata hashcash (desafio-resposta) e o token rotativo.

        auth_pwd=True adiciona o header x-auth-pwd (necessário para ações
        sensíveis: compra, renovação, cancelamento).
        """
        url = f"{BASE_URL}/{path}"
        hashcash: str | None = None
        for _attempt in range(2):
            headers = self._base_headers()
            if auth_pwd:
                headers["x-auth-pwd"] = self._auth_pwd()
            if hashcash:
                headers["x-hashcash"] = hashcash
            try:
                async with async_timeout.timeout(_TIMEOUT):
                    resp = await self._session.request(
                        method, url, headers=headers, params=params, json=json
                    )
            except (TimeoutError, aiohttp.ClientError, socket.gaierror) as err:
                msg = f"erro de comunicação com o Vivo Easy: {err}"
                raise VivoEasyApiCommunicationError(msg) from err

            self._capture_rotating_token(resp)

            # Desafio hashcash: resolve e tenta de novo uma vez.
            challenge = resp.headers.get("x-hashcash")
            if challenge and hashcash is None:
                resp.close()
                hashcash = solve_hashcash(challenge)
                continue

            if resp.status in (401, 403):
                detail = ""
                try:
                    body = await resp.json()
                    detail = body.get("text") or body.get("code") or ""
                except (aiohttp.ClientError, ValueError):
                    pass
                resp.close()
                msg = f"Vivo Easy recusou o login: {detail}".strip() if detail else (
                    "autenticação do Vivo Easy falhou (401/403)"
                )
                raise VivoEasyApiAuthenticationError(msg)
            if resp.status >= 400:
                text = await resp.text()
                msg = f"Vivo Easy respondeu {resp.status}: {text[:200]}"
                raise VivoEasyApiError(msg)
            if resp.content_type == "application/json":
                return await resp.json()
            return await resp.text()
        # ponytail: só chega aqui se os 2 attempts caírem no continue (desafio
        # repetido). Tratamos como falha de auth em vez de loop infinito.
        msg = "hashcash desafiado repetidamente"
        raise VivoEasyApiAuthenticationError(msg)

    # --- endpoints de leitura (bearer; hashcash resolvido sob desafio) ---

    async def async_get_dashboard(self) -> dict[str, Any]:
        """clients/dashboard/v2 -> consumo, carteira, cupons."""
        return await self._request("GET", "clients/dashboard/v2")

    async def async_get_prime_status(self) -> dict[str, Any]:
        """primes/current/status/v3 -> assinatura Easy Prime."""
        return await self._request("GET", "primes/current/status/v3")

    async def async_get_line_status(self) -> dict[str, Any]:
        """clients/{msisdn}/status/v2 -> status da linha."""
        return await self._request("GET", f"clients/{self._msisdn}/status/v2")

    async def async_get_client(self) -> dict[str, Any]:
        """clients -> perfil do cliente (nome, cpf, plano, email...)."""
        return await self._request("GET", "clients")

    async def async_get_renewals(self) -> dict[str, Any]:
        """renewals -> renovações automáticas agendadas."""
        return await self._request("GET", "renewals")

    async def async_get_overbalance(self) -> dict[str, Any]:
        """adherence/{msisdn}/overbalance -> saldo extra (over)."""
        return await self._request("GET", f"adherence/{self._msisdn}/overbalance")

    async def async_get_mgm(self) -> dict[str, Any]:
        """mgm/client/v2 -> indique e ganhe (código, usos, bônus)."""
        return await self._request("GET", "mgm/client/v2")

    async def async_get_internet_catalog(self) -> dict[str, Any]:
        """catalogs/clients/addons/internet/v2 -> pacotes de internet à venda."""
        return await self._request("GET", "catalogs/clients/addons/internet/v2")

    async def async_get_daily_catalog(self) -> dict[str, Any]:
        """catalogs/clients/addons/daily/v2 -> pacotes diários/apps à venda."""
        return await self._request("GET", "catalogs/clients/addons/daily/v2")

    async def async_get_plans_catalog(self) -> dict[str, Any]:
        """catalogs/plans/clients/v3 -> planos disponíveis para troca."""
        return await self._request("GET", "catalogs/plans/clients/v3")

    async def async_get_included_apps(self) -> dict[str, Any]:
        """primes/current/status/included-apps -> apps ilimitados inclusos."""
        return await self._request("GET", "primes/current/status/included-apps")

    async def async_get_notifications(self) -> dict[str, Any]:
        """notifications/q -> notificações da conta."""
        return await self._request("GET", "notifications/q")

    async def async_get_purchase_history(self, year: int, month: int) -> dict[str, Any]:
        """purchase-history/{year}/{month}/v3 -> histórico de compras do mês."""
        return await self._request("GET", f"purchase-history/{year}/{month}/v3")

    # --- ações (escrita; exigem x-auth-pwd / hashcash) ---

    async def async_purchase(
        self, offer_id: str, coupon_code: str | None = None
    ) -> dict[str, Any]:
        """POST purchases -> compra um pacote/oferta (offerId do catálogo)."""
        body: dict[str, Any] = {"offerId": offer_id, "offers": [{"offerId": offer_id}]}
        if coupon_code:
            body["couponCode"] = coupon_code
        return await self._request("POST", "purchases", json=body, auth_pwd=True)

    async def async_renew(self, body: dict[str, Any]) -> Any:
        """POST renewals/v2 -> ativa renovação automática de um componente."""
        return await self._request("POST", "renewals/v2", json=body, auth_pwd=True)

    async def async_delete_renewal(self, component_id: str) -> Any:
        """DELETE renewals/{componentId} -> desativa a renovação automática."""
        return await self._request(
            "DELETE", f"renewals/{component_id}", auth_pwd=True
        )

    async def async_renew_prime(self) -> dict[str, Any]:
        """POST purchases/renew-prime -> renova a assinatura Easy Prime."""
        return await self._request(
            "POST", "purchases/renew-prime", json={}, auth_pwd=True
        )

    async def async_reactivate_prime(self) -> Any:
        """PUT primes/client/reactivation -> reativa assinatura cancelada."""
        return await self._request(
            "PUT", "primes/client/reactivation", json={}, auth_pwd=True
        )

    async def async_rate_app(self, stars: int) -> Any:
        """POST clients/rating-app -> envia avaliação (1-5)."""
        return await self._request("POST", "clients/rating-app", json={"rate": stars})

    async def async_schedule_line_cancellation(self) -> dict[str, Any]:
        """POST retention/schedule-line-cancellation -> AGENDA cancelamento da linha."""
        return await self._request(
            "POST", "retention/schedule-line-cancellation", json={}, auth_pwd=True
        )

    async def async_cancel_line(self) -> Any:
        """POST retention/v2/cancel-line -> CANCELA a linha (irreversível)."""
        return await self._request(
            "POST", "retention/v2/cancel-line", json={}, auth_pwd=True
        )
