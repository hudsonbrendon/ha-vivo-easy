# Changelog

## Unreleased

## 0.1.1 - 2026-10-30

Modernization for Home Assistant 2026.10 (Python 3.14).

- `api.py`: use `asyncio.timeout` (the `async_timeout` package is no longer
  shipped with Home Assistant).
- `entity.py`: import `DeviceInfo` from `homeassistant.helpers.device_registry`
  (the old `helpers.device_info` path does not exist, platforms failed to load).
- Services are registered in `async_setup` (`CONFIG_SCHEMA` config-entry only)
  instead of on every entry setup.
- Platforms use `AddConfigEntryEntitiesCallback` and declare `PARALLEL_UPDATES`.
- New `diagnostics.py` (password, line number, CPF, e-mail and ids redacted).
- Added `quality_scale.yaml`, `pyproject.toml` (ruff), `requirements_test.txt`,
  GitHub workflows (tests on Python 3.14, hassfest, HACS, release) and Home
  Assistant tests (setup/unload, config flow, diagnostics, services).
- `hacs.json`: minimum Home Assistant 2026.10.0 (Python 3.14 syntax).

## 0.1.0

First release.
