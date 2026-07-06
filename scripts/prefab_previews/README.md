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
