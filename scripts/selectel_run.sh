#!/usr/bin/env bash
# Run a command on Selectel VM via SSH.
#
# Usage:
#   bash scripts/selectel_run.sh "cd /root/dj-music-plugin && uv run pytest"
#   bash scripts/selectel_run.sh                  # interactive SSH session
#
# Requires .env with:
#   SELECTEL_SSH_HOST=<ip>
#   SELECTEL_SSH_USER=root
#   SELECTEL_SSH_KEY_PATH=~/.ssh/selectel_ed25519
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.env"
    set +a
fi

HOST="${SELECTEL_SSH_HOST:?Set SELECTEL_SSH_HOST in .env}"
USER="${SELECTEL_SSH_USER:-root}"
KEY="${SELECTEL_SSH_KEY_PATH:-$HOME/.ssh/selectel_ed25519}"
REMOTE_DIR="${SELECTEL_PROJECT_PATH:-/root/dj-music-plugin}"

SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"

if [ $# -eq 0 ]; then
    echo "Connecting to $USER@$HOST..."
    # shellcheck disable=SC2086
    ssh $SSH_OPTS -i "$KEY" "$USER@$HOST"
else
    CMD="$*"
    echo "Running on $USER@$HOST:"
    echo "  $CMD"
    echo "---"
    # shellcheck disable=SC2086
    ssh $SSH_OPTS -i "$KEY" "$USER@$HOST" "cd $REMOTE_DIR && $CMD"
fi
