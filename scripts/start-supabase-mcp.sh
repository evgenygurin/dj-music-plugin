#!/usr/bin/env bash
# Launch Supabase MCP server with credentials sourced from the nearest .env.
#
# Walks up from $CLAUDE_PLUGIN_ROOT looking for a .env file so that git
# worktrees (which don't have their own .env) inherit credentials from the
# main repo checkout above them.
#
# Required env (read from .env): DJ_DB_ACCESS_TOKEN

set -euo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DIR="$ROOT"
ENV_FILE=""

while [ "$DIR" != "/" ]; do
  if [ -f "$DIR/.env" ]; then
    ENV_FILE="$DIR/.env"
    break
  fi
  DIR="$(dirname "$DIR")"
done

if [ -n "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

: "${DJ_DB_ACCESS_TOKEN:?DJ_DB_ACCESS_TOKEN not set; create .env with DJ_DB_ACCESS_TOKEN=sbp_... in $ROOT or any parent dir}"

exec env SUPABASE_ACCESS_TOKEN="$DJ_DB_ACCESS_TOKEN" \
  npx -y @supabase/mcp-server-supabase@0.7.0 \
  --read-only \
  --project-ref=bowosphlnghhgaulcyfm \
  --features=database,docs,debug
