---
description: Configuration and constants patterns
globs: app/config/**/*.py, app/shared/constants.py
---

# Configuration

- Settings are split by concern under `app/config/` (`audio.py`,
  `yandex.py`, `database.py`, `mcp.py`, `audit.py`, `delivery.py`,
  `discovery.py`, `optimization.py`, `transition.py`). Top-level
  `Settings` class composes them.
- All tunable values use `env_prefix="DJ_"` via pydantic-settings
- Use pydantic-settings with `.env` file support
- Document units in field comments: `# seconds`, `# Hz`, `# LUFS`, `# dB`
- Group fields by section with `# ── Section ──` comments
- `settings = Settings()` singleton at module level
- Non-configurable domain values in `app/shared/constants.py` as enums and module-level constants
- Never use bare numbers in code — reference `settings.*` or constants
- Test overrides: use `Settings(field=value)` in test fixtures, or env var patching

## Gotchas

- Background tasks: `task=True` requires `pip install 'fastmcp[tasks]'`
- Error masking: `mask_error_details=not settings.debug` in production
