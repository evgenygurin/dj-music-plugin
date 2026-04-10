---
paths: app/services/workflows/**/*.py
---

# Workflows (Orchestration Layer)

- Workflows coordinate multiple services for a single MCP tool call
- Each workflow is a class with explicit `run_*` entrypoints
- Injected via DI from `controllers/dependencies/services.py`
- Workflows CAN import services and repositories — they sit at Band 2A
- Workflows CANNOT import MCP/FastMCP — framework-agnostic like services
- MCP tools should only: parse inputs → delegate to workflow → report progress → map errors
- Shared helpers go in `_helpers.py`, not duplicated across workflows
- Progress reporting: workflow accepts a callback, tool passes `ctx.info` as the callback

## Current Workflows

| Workflow | Tool(s) | Orchestrates |
|----------|---------|-------------|
| `ImportTracksWorkflow` | `import_tracks`, `download_tracks` | YM API → Track creation → metadata → playlist linking → optional analysis |
| `AnalyzeTrackWorkflow` | `analyze_track`, `analyze_batch` | TieredPipeline → AudioService → feature persistence |
| `BuildSetWorkflow` | `build_set`, `rebuild_set` | Pre-analysis (L3) → GA/greedy optimization → scoring |
| `DeliverSetWorkflow` | `deliver_set`, `export_set` | L4 ensure → scoring → conflict gate → export writers → file copy |
| `SyncPlaylistWorkflow` | `sync_playlist`, `push_set_to_ym` | Reconciliation → diff → apply changes → re-fetch |
