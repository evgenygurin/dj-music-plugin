# Liebing N-Deck Toolkit — Plan (Task 1 details)

Plan file: docs/superpowers/plans/2026-09-03-liebing-n-deck-toolkit.md
Task 1: app/schemas/curate.py (83 fields) + tests

**Current evidence:**
- Design spec: docs/superpowers/specs/2026-09-03-liebing-n-deck-toolkit-design.md (204 lines, approved)
- Plan: docs/superpowers/plans/2026-09-03-liebing-n-deck-toolkit.md (6 tasks, tasks 1-2 complete)
- DB 83 cols verified (supabase_execute_sql), code: tests/tools/curate/test_curate_by_role.py (4 passed), app/schemas/curate.py (398 fields, 603 lines), app/config/stems.py (StemsConfig 7.8/5/0/2000), app/audio/deep/demucs_runner.py (STEMS_SEMAPHORE 1 shared with app/audio/deep/__init__.py)
- FastMCP v3.2.4 docs verified (context7 /prefecthq/fastmcp): structuredContent + outputSchema + version + task=True + Field(ge/le) all confirmed

Task 1 scope (independent, self-contained):
- Create/modify: `app/schemas/curate.py` (83 fields — int: 6 lookups each + bool: 2 + float: 7 ratios + float: spectral + str: BPM/key sources + phrase — covered 398)
- Test: `tests/tools/curate/test_curate_by_role.py` (add 83-field access, preset defaults, `filter` non-None override)
- TDD: failing test → minimal schema → pass → commit
- Verification: `pytest` + `ruff check` + `mypy --strict`
- Commit: `feat(curate): 83-field filters + Preset`
