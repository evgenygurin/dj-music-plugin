#!/bin/bash
set -a
source "$(dirname "$0")/../.env"
set +a
: "${DJ_DB_ACCESS_TOKEN:?}"
DJ_DB_PROJECT_REF="${DJ_DB_PROJECT_REF:-$(echo "$DJ_DATABASE_URL" | sed -n 's/.*postgres\.\([^:]*\):.*/\1/p')}"
: "${DJ_DB_PROJECT_REF:?}"
export SUPABASE_ACCESS_TOKEN="$DJ_DB_ACCESS_TOKEN"
exec npx -y @supabase/mcp-server-supabase@0.8.2 --read-only --project-ref="$DJ_DB_PROJECT_REF" --features=database,docs,debug
