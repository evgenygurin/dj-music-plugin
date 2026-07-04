"""Rank 07_WEAPONS candidates for the USB build.

Scores in-crate pairwise transitions (top-300 by manifest rank in the three
combat crates), weapon_score = mean of the top-2 outgoing overall scores.
Writes ~/DJ_USB_BUILD/_META/weapons.csv (all candidates, sorted desc).

Run locally with the project env sourced (a stale harness DJ_DATABASE_URL
otherwise gives "tenant not found"):

    set -a && . ./.env && set +a && uv run python scripts/usb_weapons.py

Requires /tmp/usb_manifest.csv (see scripts/usb_manifest.py).
"""

from __future__ import annotations

import asyncio
import csv
from collections import defaultdict
from pathlib import Path

from app.db.session import dispose, get_session_factory
from app.domain.transition.scorer import TransitionScorer
from app.repositories.track_features import TrackFeaturesRepository

MANIFEST = Path("/tmp/usb_manifest.csv")
OUT = Path.home() / "DJ_USB_BUILD" / "_META" / "weapons.csv"
CRATES = {"02_DRIVING", "03_PEAK", "05_HARD_RAVE"}
TOP_RANK = 300
TOP_K = 2


async def main() -> None:
    rows = list(csv.DictReader(MANIFEST.open()))
    cand = [r for r in rows if r["crate"] in CRATES and int(r["rank"]) <= TOP_RANK]
    by_crate: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in cand:
        by_crate[r["crate"]].append(r)
    meta = {int(r["track_id"]): r for r in cand}

    scorer = TransitionScorer()
    factory = get_session_factory()
    results: list[tuple[float, int]] = []
    try:
        async with factory() as session:
            repo = TrackFeaturesRepository(session)
            for crate, crate_rows in sorted(by_crate.items()):
                ids = [int(r["track_id"]) for r in crate_rows]
                feats = await repo.get_scoring_features_batch(ids)
                print(f"{crate}: {len(ids)} ids, {len(feats)} with features")
                for a in ids:
                    fa = feats.get(a)
                    if fa is None:
                        continue
                    top: list[float] = []
                    for b in ids:
                        if a == b:
                            continue
                        fb = feats.get(b)
                        if fb is None:
                            continue
                        s = scorer.score(fa, fb)
                        if not s.hard_reject:
                            top.append(float(s.overall))
                    top.sort(reverse=True)
                    if len(top) >= TOP_K:
                        results.append((sum(top[:TOP_K]) / TOP_K, a))
    finally:
        await dispose()

    results.sort(reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "weapon_rank",
                "weapon_score",
                "track_id",
                "crate",
                "rank",
                "camelot",
                "bpm",
                "lufs",
                "title",
            ]
        )
        for i, (score, tid) in enumerate(results, start=1):
            r = meta[tid]
            w.writerow(
                [
                    i,
                    f"{score:.4f}",
                    tid,
                    r["crate"],
                    r["rank"],
                    r["camelot"],
                    r["bpm"],
                    r["lufs"],
                    r["title"],
                ]
            )
    print(f"wrote {len(results)} candidates -> {OUT}")
    print("--- TOP 20 ---")
    for i, (score, tid) in enumerate(results[:20], start=1):
        r = meta[tid]
        print(
            f"{i:2d}. {score:.3f} [{r['camelot']:>3}] [{r['bpm']:>5}] "
            f"{r['crate'][:10]:<10} {r['title']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
