"""Reclassify mood for every track from STORED features (no audio, no download).

Mood is a pure function of already-computed audio features, so this is a fast
in-DB recompute. Re-runs the current MoodClassifier (with the fixed catch-all
penalty) over every track_audio_features_computed row and updates
mood + mood_confidence. Also syncs the stale labels (which were produced by an
older classifier version) to the current code.

Dry-run by default (prints the projected distribution + change count, NO write).
Pass --apply to write.

Run: set -a; . ./.env; set +a; uv run python scripts/reclassify_moods.py [--apply]
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter

from sqlalchemy import select, update

from app.audio.classification.classifier import MoodClassifier
from app.config import get_settings
from app.db.session import dispose, get_session_factory
from app.models.track_features import TrackAudioFeaturesComputed as TF

COLS = [c.name for c in TF.__table__.columns]
BATCH = 2000
clf = MoodClassifier()


async def main(apply: bool) -> None:
    pen = get_settings().audio.mood_catch_all_penalty
    print(f"catch-all penalty in effect: {pen}")
    print(f"mode: {'APPLY (writing)' if apply else 'DRY RUN (no writes)'}\n")

    factory = get_session_factory()
    async with factory() as s:
        rows = (await s.execute(select(TF))).scalars().all()
        print(f"loaded {len(rows)} feature rows")

        old_dist: Counter = Counter()
        new_dist: Counter = Counter()
        changed = 0
        updates: list[dict] = []
        for r in rows:
            feats = {c: getattr(r, c) for c in COLS}
            res = clf.classify(feats)
            new_mood = res.mood.value
            old_dist[r.mood] += 1
            new_dist[new_mood] += 1
            if new_mood != r.mood:
                changed += 1
            updates.append(
                {
                    "track_id": r.track_id,
                    "mood": new_mood,
                    "mood_confidence": round(float(res.confidence), 4),
                }
            )

        def fmt(d: Counter) -> str:
            return "  ".join(f"{k}:{v}" for k, v in d.most_common())

        print(f"\nOLD (stored): {fmt(old_dist)}")
        print(f"\nNEW (recompute): {fmt(new_dist)}")
        print(f"\nlabels changed: {changed}/{len(rows)} ({100 * changed / len(rows):.1f}%)")
        print(
            f"driving: {old_dist.get('driving', 0)} -> {new_dist.get('driving', 0)}   "
            f"hypnotic: {old_dist.get('hypnotic', 0)} -> {new_dist.get('hypnotic', 0)}"
        )

        if not apply:
            print("\nDRY RUN — no writes. Re-run with --apply to persist.")
            await dispose()
            return

        print(f"\napplying {len(updates)} updates in batches of {BATCH} ...")
        for i in range(0, len(updates), BATCH):
            await s.execute(update(TF), updates[i : i + BATCH])
            await s.flush()
            print(f"  wrote {min(i + BATCH, len(updates))}/{len(updates)}")
        await s.commit()
        print("committed.")

    await dispose()


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
