# Prefab UI previews

Standalone reproductions of the 7 Prefab UI tools (`app/tools/ui/`) with
seeded fake data. Lets us:

1. Render each tool to static HTML (`artifacts/previews/*.html`) via
   `prefab export`.
2. Screenshot the rendered page with headless Chromium
   (`artifacts/screenshots/*.png`).

No Supabase, no MCP server, no real audio needed — the preview script
hand-rolls a minimal `UnitOfWork` mock + `TransitionScorer` stub for
each tool.

## Regenerate

```bash
# One-time: make sure fastmcp[apps] is installed
uv sync --all-extras

# 1. Build PrefabApp objects + export to HTML (~6.5 MB each, bundled)
mkdir -p artifacts/previews artifacts/screenshots
for app in set_view_app transition_score_app library_audit_app \
           score_pool_matrix_app library_dashboard_app camelot_wheel_app \
           render_studio_app; do
  uv run prefab export "scripts/prefab_previews/apps.py:${app}" \
    --bundled -o "artifacts/previews/${app%_app}.html"
done

# 2. Screenshot each HTML with Playwright + headless Chromium
uv pip install playwright
uv run python scripts/prefab_previews/shoot.py
```

Only the screenshots end up in git (`artifacts/screenshots/`). HTML
bundles are ignored — regenerate as needed.

## Files

- `apps.py` — 7 `PrefabApp` module-level globals, one per UI tool
- `shoot.py` — Playwright runner, writes PNG per preview
- `artifacts/screenshots/*.png` — tracked in git for docs/PR comments

## Live host (interactive buttons)

Static exports have **no MCP host** — the embedded MCP-Apps client posts
`ui/initialize` to `window.parent` and, with nobody answering, every
button (`CallTool` action) fails with **"Not connected"**. To actually
drive the pipeline from the browser, run the live host:

```bash
# from repo root; .env must point at the live DB
uv run python scripts/prefab_previews/serve_live.py --version-id 149
open http://127.0.0.1:8300/
```

`serve_live.py`:

1. builds the real `ui_control_center` PrefabApp for the given
   `version_id` (live DB) and serves it at `/app`;
2. serves a wrapper page at `/` that iframes `/app` and implements the
   MCP-Apps host protocol over postMessage (`ui/initialize`,
   `tools/call`);
3. proxies `tools/call` into the real FastMCP server via an in-memory
   `fastmcp.Client` — full middleware/DI stack, hidden app-only tools
   (`control_center_panel`, `act_build`, `act_l5_set`) included, and
   `RENDER_JOBS` state shared in-process.

Also wired into `.claude/launch.json` as the `control-center-live`
dev-server (env: `DJ_PREVIEW_VERSION_ID`, `PORT`).
