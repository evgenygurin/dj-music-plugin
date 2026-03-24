---
description: Configuration and constants patterns
globs: app/config.py, app/core/constants.py
---

# Configuration

- All tunable values in `Settings` class (`app/config.py`) with `env_prefix="DJ_"`
- Use pydantic-settings with `.env` file support
- Document units in field comments: `# seconds`, `# Hz`, `# LUFS`, `# dB`
- Group fields by section with `# ── Section ──` comments
- `settings = Settings()` singleton at module level
- Non-configurable domain values in `app/core/constants.py` as enums and module-level constants
- Never use bare numbers in code — reference `settings.*` or constants
- Test overrides: use `Settings(field=value)` in test fixtures, or env var patching
