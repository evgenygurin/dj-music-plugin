---
description: Configuration and constants patterns
globs: app/config/**/*.py, app/shared/constants.py
---

# Configuration

- Settings are split by concern under `app/config/` — 9 per-domain
  files: `audio.py`, `audit.py`, `database.py`, `delivery.py`,
  `discovery.py`, `mcp.py`, `optimization.py`, `transition.py`,
  `yandex.py`. `app/config/__init__.py` exposes the frozen
  `Settings` dataclass aggregator + `get_settings()` (lru_cached)
  and `reset_settings_cache()` for tests.
- Access via `from app.config import get_settings; settings = get_settings()`.
  Then `settings.transition.weight_bpm`, `settings.audio.sample_rate`,
  etc. **No module-level `settings = Settings()` singleton** — always
  go through `get_settings()`.
- Each per-domain class sets its own `env_prefix` via pydantic-settings
  `SettingsConfigDict`:
  - `AudioSettings` → `DJ_AUDIO_`
  - `YandexSettings` → `DJ_YM_`
  - `DatabaseSettings` → `DJ_` (plain, shared root)
  - `AuditSettings` → `DJ_` (plain)
  - `MCPSettings` → `DJ_MCP_`
  - `DeliverySettings` → `DJ_DELIVERY_`
  - `DiscoverySettings` → `DJ_DISCOVERY_`
  - `OptimizationSettings` → `DJ_GA_`
  - `TransitionSettings` → `DJ_TRANSITION_`
- Use pydantic-settings with `.env` file support.
- Document units in field comments: `# seconds`, `# Hz`, `# LUFS`, `# dB`.
- Group fields by section with `# ── Section ──` comments.
- Non-configurable domain values in `app/shared/constants.py` as
  enums and module-level constants.
- Never use bare numbers in code — reference `settings.*` or constants.
- Test overrides: instantiate the per-domain class directly
  (`AudioSettings(sample_rate=44100)`) or patch env vars +
  `reset_settings_cache()`.

## Gotchas

- Background tasks: `task=True` requires `pip install 'fastmcp[tasks]'`
- Error masking: `mask_error_details=not settings.debug` in production
