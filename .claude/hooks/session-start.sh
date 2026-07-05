#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# Installs Python dependencies so linters (ruff), typechecker (mypy),
# import-linter, and the pytest suite work in remote sessions.
#
# Scope: base deps + the `dev` dependency-group only. Audio extras
# (librosa / essentia / numba / torch) are intentionally NOT installed —
# they are slow and fragile to build, and the audio tests `importorskip`
# so they skip cleanly without them. Run `uv sync --extra audio` by hand
# if you need to exercise the analyzer pipeline.
set -euo pipefail

# Only run in Claude Code remote (web) environments.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-"$(dirname "$0")/../.."}"

# uv is installed under ~/.local/bin in remote envs — make sure it's found.
export PATH="$HOME/.local/bin:$PATH"

# Idempotent: re-running reuses the cached venv. NOTE: `dev` is a
# dependency-group (synced by default), NOT an extra — `uv sync --extra dev`
# errors with "Extra `dev` is not defined". Plain `uv sync` is correct.
uv sync

echo "dj-music-plugin: dependencies installed (base + dev group)"
