"""Smoke test de terminal do cliente Vivo Easy (sem Home Assistant).

Faz login real e despeja os JSONs de dashboard/prime/status da linha, pra você
validar os campos antes de instalar no HA. As credenciais ficam só na sua
máquina (variáveis de ambiente ou prompt) — nada é enviado além do gateway Vivo.

Uso:
    pip install aiohttp async_timeout
    VIVO_MSISDN=5531999999999 VIVO_PASSWORD='suasenha' python3 scripts/smoke.py
    # ou sem env vars: pergunta no terminal
"""

from __future__ import annotations

import asyncio
import getpass
import importlib.util
import json
import os
import pathlib

import aiohttp

_API = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "vivo_easy"
    / "api.py"
)
_spec = importlib.util.spec_from_file_location("vivo_easy_api", _API)
_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api)


async def main() -> None:
    """Loga e imprime os três endpoints de leitura."""
    msisdn = os.environ.get("VIVO_MSISDN") or input("Número (ex 5531999999999): ")
    password = os.environ.get("VIVO_PASSWORD") or getpass.getpass("Senha do app: ")

    async with aiohttp.ClientSession() as session:
        client = _api.VivoEasyApiClient(msisdn=msisdn, password=password, session=session)
        print("Logando...")
        await client.async_login()
        print(f"OK. customerId={client.customer_id} clientId={client.client_id}\n")

        for label, coro in (
            ("dashboard/v2", client.async_get_dashboard()),
            ("primes/current/status/v3", client.async_get_prime_status()),
            ("clients/{msisdn}/status/v2", client.async_get_line_status()),
        ):
            print(f"===== {label} =====")
            try:
                data = await coro
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except _api.VivoEasyApiError as err:
                print(f"(falhou: {err})")
            print()


if __name__ == "__main__":
    asyncio.run(main())
