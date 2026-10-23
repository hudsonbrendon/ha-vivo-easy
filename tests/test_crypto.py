"""Checagem dos primitivos de crypto portados do app (Utils.java).

Roda sem Home Assistant: `python3 -I tests/test_crypto.py`.
Protege contra regressão nos algoritmos de login/hashcash.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import pathlib
import sys
import types

# aiohttp/async_timeout só são usados em runtime pela classe de cliente; para a
# checagem de crypto, stubamos para rodar sem dependências do Home Assistant.
for _name in ("aiohttp", "async_timeout"):
    sys.modules.setdefault(_name, types.ModuleType(_name))

# Carrega só api.py (sem o __init__ do pacote, que depende do Home Assistant).
_API = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "vivo_easy" / "api.py"
_spec = importlib.util.spec_from_file_location("vivo_easy_api", _API)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
generate_auth_token = _mod.generate_auth_token
hash_msisdn = _mod.hash_msisdn
solve_hashcash = _mod.solve_hashcash


def test_generate_auth_token() -> None:
    """base64(msisdn&@#!&password&@#!&GG_IZI)."""
    got = generate_auth_token("5531999999999", "minhasenha")
    expected = base64.b64encode(b"5531999999999&@#!&minhasenha&@#!&GG_IZI").decode()
    assert got == expected


def test_hash_msisdn_is_sha256_hex() -> None:
    """sha256 hex de 64 chars, determinístico."""
    got = hash_msisdn("5531999999999")
    assert len(got) == 64
    assert got == hash_msisdn("5531999999999")


def test_solve_hashcash() -> None:
    """Solução deve bater n zeros no sha256 e preservar o desafio."""
    for challenge in ("1:abc", "2:xyz", "3:deadbeef"):
        n = int(challenge.split(":")[0])
        sol = solve_hashcash(challenge)
        assert sol.startswith(challenge + ":")
        assert hashlib.sha256(sol.encode()).hexdigest().startswith("0" * n)


if __name__ == "__main__":
    test_generate_auth_token()
    test_hash_msisdn_is_sha256_hex()
    test_solve_hashcash()
    print("todos os checks de crypto passaram")
