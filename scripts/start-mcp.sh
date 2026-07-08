#!/bin/bash
# Start DJ MCP server with correct environment
set -eo pipefail

cd /Users/laptop/dev/dj-music-plugin
export PATH="/Users/laptop/.local/bin:$PATH"
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

export DJ_MCP_DISABLE_PROMPTS="${DJ_MCP_DISABLE_PROMPTS:-1}"

exec /Users/laptop/dev/dj-music-plugin/.venv/bin/fastmcp run fastmcp.json --no-banner
