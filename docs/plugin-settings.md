# Plugin Settings (`.claude/dj-music.local.md`)

Per-project override file for DJ Music Plugin runtime configuration. Follows the Claude Code plugin-settings convention: YAML frontmatter + markdown body, gitignored, read by slash commands and hooks.

## Location

```text
<repo-root>/.claude/dj-music.local.md
```

Gitignored. Never commit. Template: [`.claude/dj-music.local.md.example`](../.claude/dj-music.local.md.example) at the repo root.

## Schema

```yaml
---
# Panel dev overrides (consumed by /panel-setup → writes panel/.env.local)
supabase_url: https://your-project.supabase.co
supabase_anon_key: eyJhbGciOi...
mcp_http_url: http://localhost:8000/mcp

# Feature flags (consumed by panel actions + audio-player dispatcher)
enable_echo_out_style: true
enable_filter_sweep_style: true

# Default set-building behaviour (consumed by build-set / deliver-set skills)
default_template: peak_hour_60
default_crossfade_bars: 32
default_analysis_level: 3

# VM background jobs (consumed by vm_import_and_analyze.py via env export)
vm_host: root@155.212.128.27
vm_workers: 12
vm_sleep_sec: 600
---

# Notes

Free-form markdown body. Use it for prompts the DJ wants persisted
across sessions, notes about the current library state, or pointers
for scheduled jobs.
```

## Field reference

| Field | Default | Consumer |
|---|---|---|
| `supabase_url` | `NEXT_PUBLIC_SUPABASE_URL` env | `/panel-setup` → `panel/.env.local` |
| `supabase_anon_key` | `NEXT_PUBLIC_SUPABASE_ANON_KEY` env | `/panel-setup` → `panel/.env.local` |
| `mcp_http_url` | `http://localhost:8000/mcp` | `/panel-setup` → `panel/.env.local` |
| `enable_echo_out_style` | `true` | Audio player dispatcher (future: hide chip if false) |
| `enable_filter_sweep_style` | `true` | Audio player dispatcher (future: hide chip if false) |
| `default_template` | `peak_hour_60` | `/build-set` skill |
| `default_crossfade_bars` | `32` | Audio player initial state |
| `default_analysis_level` | `3` | `/build-set`, `/deliver-set`, VM sweeps |
| `vm_host` | — | `scripts/vm_import_and_analyze.py` deploy |
| `vm_workers` | `12` | `scripts/vm_import_and_analyze.py` |
| `vm_sleep_sec` | `600` | `scripts/vm_import_and_analyze.py` |

## Usage

### Bootstrap

```bash
cp .claude/dj-music.local.md.example .claude/dj-music.local.md
$EDITOR .claude/dj-music.local.md
```

Then run `/panel-setup` to materialize `panel/.env.local` from the file.

### Hot reload

Settings changes are read on every slash-command invocation — no Claude Code restart needed for command-based consumers. Hooks cache settings per session; edit `.claude/dj-music.local.md` and restart Claude Code if you rely on a hook consumer (currently none).

### Parsing reference

All consumers use the standard frontmatter extraction:

```bash
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' .claude/dj-music.local.md)
MCP_URL=$(echo "$FRONTMATTER" | grep '^mcp_http_url:' | sed 's/mcp_http_url: *//' | sed 's/^"\(.*\)"$/\1/')
```

See `commands/panel-setup.md` for the canonical parser.
