---
paths: app/controllers/dependencies/**/*.py
---

# DI Factories (Depends)

- Split by concern: `db.py`, `uow.py`, `repos.py`, `services.py`, `audio.py`, `external.py`
- `__init__.py` re-exports all factories for backward compat — keep it updated when adding new factories
- All factories use `Depends()` from FastMCP — `param=Depends(factory)` syntax (NOT `Annotated`)
- `get_db_session()` in `db.py` owns the transaction lifecycle: commit on success, rollback on error
- One DB session shared across all repos within a single tool call (via `Depends` caching)
- Workflow factories go in `services.py` alongside service factories
- `audio.py` provides `get_audio_service`, `get_tiered_pipeline`
- `external.py` provides `get_ym_client`
- `uow.py` provides `get_unit_of_work` (aggregates all repos)
- NEVER create repo/service instances inside tool functions — always inject via `Depends`
