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

exec npx -y @supabase/mcp-server-supabase@0.7.0 \
  --read-only \
  --project-ref="${DJ_DB_PROJECT_REF:?DJ_DB_PROJECT_REF not set in .env}" \
  --features=database,docs,debug
