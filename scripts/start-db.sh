#!/usr/bin/env bash
# Start Supabase MCP server for database access
# Reads credentials from .env (DJ_DB_ACCESS_TOKEN, DJ_DB_PROJECT_REF)
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env from project root
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  . "$PROJECT_ROOT/.env"
  set +a
fi

# The supabase MCP server expects SUPABASE_ACCESS_TOKEN env var
export SUPABASE_ACCESS_TOKEN="${SUPABASE_ACCESS_TOKEN:-${DJ_DB_ACCESS_TOKEN:-}}"

PROJECT_REF="${DJ_DB_PROJECT_REF:-bowosphlnghhgaulcyfm}"

exec npx -y @supabase/mcp-server-supabase@0.7.0 \
  --read-only \
  --project-ref="$PROJECT_REF" \
  --features=database,docs,debug
