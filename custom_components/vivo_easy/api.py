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

# Segredos portados de Utils.java (app v4.3.9)
_AUTH_TOKEN_SEP = "&@#!&"
_AUTH_TOKEN_SUFFIX = "&@#!&GG_IZI"
_MSISDN_HASH_SALT = ",s)S.X-p;SdwsA2&lR.dIy|SCg}bZ1{&7y^%kpk2u9V+{mEO%n3HccBYJIKhFujb"

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
        """POST authenticate; captura o token rotativo inicial."""
        credentials = {
            "number": self._msisdn,
            "hash": generate_auth_token(self._msisdn, self._password),
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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        authed: bool = True,
    ) -> Any:
        """Faz a chamada, trata hashcash (desafio-resposta) e o token rotativo."""
        url = f"{BASE_URL}/{path}"
        hashcash: str | None = None
        for _attempt in range(2):
            headers = self._base_headers()
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
                resp.close()
                msg = "autenticação do Vivo Easy falhou (401/403)"
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

    # --- endpoints de leitura (bearer apenas) ---

    async def async_get_dashboard(self) -> dict[str, Any]:
        """clients/dashboard/v2 -> consumo, carteira, cupons."""
        return await self._request("GET", "clients/dashboard/v2")

    async def async_get_prime_status(self) -> dict[str, Any]:
        """primes/current/status/v3 -> assinatura Easy Prime."""
        return await self._request("GET", "primes/current/status/v3")

    async def async_get_line_status(self) -> dict[str, Any]:
        """clients/{msisdn}/status/v2 -> status da linha."""
        return await self._request("GET", f"clients/{self._msisdn}/status/v2")
