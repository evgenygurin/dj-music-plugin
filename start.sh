#!/bin/bash
# Setup script for Claude Code web environment.
# Runs BEFORE Claude Code launches (from /tmp or any directory).
# Only installs dependencies — does NOT start servers.
# MCP server is launched by Claude Code via fastmcp stdio (see plugin.json).
set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/dj-music-plugin}"
cd "$PROJECT_DIR"

# ── Install Python dependencies ──
uv sync --extra dev

echo "Dependencies installed"
