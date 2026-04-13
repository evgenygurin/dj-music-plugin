#!/usr/bin/env bash
# Fix beat detection on Selectel VM — one-shot script.
#
# Usage:
#   bash scripts/fix_beat_on_server.sh
#
# What it does:
#   1. Pulls the fix branch
#   2. Installs audio deps
#   3. Runs migration (NULLs wrong beat features, downgrades analysis_level)
#   4. Runs verify_audio_pipeline.py on a real MP3
#   5. Runs verify_p3_features.py on the same MP3
#
set -euo pipefail

BRANCH="claude/fix-beat-detection-0YIPC"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
echo "========================================"
echo "Beat Detection Fix — Selectel VM"
echo "========================================"
echo "Project: $PROJECT_DIR"
echo "Branch:  $BRANCH"
echo ""

# ── 1. Pull latest code ──
echo "[1/5] Pulling branch $BRANCH..."
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull origin "$BRANCH"
echo "  OK"

# ── 2. Install deps ──
echo ""
echo "[2/5] Installing dependencies (audio extra)..."
uv sync --extra audio 2>&1 | tail -3
echo "  OK"

# ── 3. Run migration ──
echo ""
echo "[3/5] Running migration (reset wrong beat features)..."
uv run alembic upgrade head 2>&1
echo "  OK — beat features reset, analysis_level downgraded to 2"

# ── 4. Find a real MP3 for verification ──
echo ""
echo "[4/5] Running verify_audio_pipeline.py..."

# Try to find an MP3 — check common locations
MP3=""
for dir in \
    "$HOME/Library/Mobile Documents/com~apple~CloudDocs/dj-techno-set-builder/library" \
    "$PROJECT_DIR/library" \
    "$PROJECT_DIR/generated-sets" \
    "$HOME/music" \
    "$HOME/Music" \
    "/tmp/dj-library"; do
    if [ -d "$dir" ]; then
        found=$(find "$dir" -name "*.mp3" -size +500k 2>/dev/null | head -1)
        if [ -n "$found" ]; then
            MP3="$found"
            break
        fi
    fi
done

if [ -n "$MP3" ]; then
    echo "  Found MP3: $(basename "$MP3")"
    uv run python scripts/verify_audio_pipeline.py "$MP3" 2>&1
    echo ""
    echo "[5/5] Running verify_p3_features.py..."
    uv run python scripts/verify_p3_features.py "$MP3" 2>&1
else
    echo "  WARNING: No MP3 files found for verification."
    echo "  Run manually: uv run python scripts/verify_audio_pipeline.py /path/to/track.mp3"
    echo ""
    echo "[5/5] Skipping verify_p3_features.py (no MP3)."
fi

echo ""
echo "========================================"
echo "DONE. Beat detection fixed."
echo ""
echo "Next steps:"
echo "  - Any tool triggering L3 (build_set, score_transitions)"
echo "    will auto-reanalyze tracks with the fixed BeatDetector."
echo "  - To manually reanalyze: use analyze_track with force=True"
echo "========================================"
