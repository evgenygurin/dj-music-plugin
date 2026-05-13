# Plugin Settings (`.claude/dj-music.local.md`)

Per-project override file for DJ Music Plugin runtime configuration. Follows the Claude Code plugin-settings convention: YAML frontmatter + markdown body, gitignored, read by slash commands and skills.

## Location

```text
<repo-root>/.claude/dj-music.local.md
```

Gitignored. Never commit. Create it manually when you need to override defaults — there is no canonical template.

## Schema

```yaml
---
# Feature flags (consumed by build-set / deliver-set skills)
enable_echo_out_style: true
enable_filter_sweep_style: true

# Default set-building behaviour (consumed by build-set / deliver-set skills)
default_template: peak_hour_60
default_crossfade_bars: 32
default_analysis_level: 3
---

# Notes

Free-form markdown body. Use it for prompts the DJ wants persisted
across sessions, notes about the current library state, or pointers
for scheduled jobs.
```

## Field reference

| Field | Default | Consumer |
|---|---|---|
| `enable_echo_out_style` | `true` | `/build-set` / `/deliver-set` skills (future: prune from picker if false) |
| `enable_filter_sweep_style` | `true` | `/build-set` / `/deliver-set` skills (future: prune from picker if false) |
| `default_template` | `peak_hour_60` | `/build-set` skill |
| `default_crossfade_bars` | `32` | `/deliver-set` skill |
| `default_analysis_level` | `3` | `/build-set`, `/deliver-set` skills |

## Usage

### Bootstrap

```bash
$EDITOR .claude/dj-music.local.md
```

### Hot reload

Settings changes are read on every slash-command invocation — no Claude Code restart needed.

### Parsing reference

All consumers use the standard frontmatter extraction:

```bash
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' .claude/dj-music.local.md)
TEMPLATE=$(echo "$FRONTMATTER" | grep '^default_template:' | sed 's/default_template: *//' | sed 's/^"\(.*\)"$/\1/')
```
