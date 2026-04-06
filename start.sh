#!/bin/bash
# Setup script for Claude Code web environment.
# Runs BEFORE Claude Code launches (from /tmp or any directory).
# Only installs dependencies — does NOT start servers.
# Servers are started via SessionStart hook in .claude/settings.json.
set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/dj-music-plugin}"
cd "$PROJECT_DIR"

# ── Install Python dependencies ──
uv sync --extra http --extra dev

# ── Install panel dependencies ──
(cd panel && bun install)

# ── Ensure panel .env exists ──
if [ ! -f panel/.env ]; then
  cp panel/.env.example panel/.env
  echo "Created panel/.env from .env.example"
fi

echo "Dependencies installed"
