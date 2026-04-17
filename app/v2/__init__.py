"""Target architecture (parallel refactor).

Phase 1-7 implementation per
docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md

`app/v2/` MAY import from `app/` during transition.
`app/` MUST NOT import from `app/v2/`.
"""

__version__ = "0.0.0-v2"
