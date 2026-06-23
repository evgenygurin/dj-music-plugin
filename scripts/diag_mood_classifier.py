"""One-off diagnostic: is the mood classifier degenerate on the live library?

Pulls a random sample of real feature rows, runs the actual MoodClassifier,
and compares the label distribution WITH the catch-all penalty (prod) vs
WITHOUT it. Also flags miscalibrated ("dead-weight") profile features whose
ideal/tolerance no real track can reach.

Run: uv run python scripts/diag_mood_classifier.py
"""

from __future__ import annotations

import asyncio
import math
from collections import Counter

from sqlalchemy import func, select

from app.audio.classification.classifier import MoodClassifier
from app.audio.classification.profiles import ALL_PROFILES, CATCH_ALL_SUBGENRES
from app.db.session import dispose, get_session_factory
from app.models.track_features import TrackAudioFeaturesComputed as TF

SAMPLE = 3000
clf = MoodClassifier()
COLS = [c.name for c in TF.__table__.columns]


def raw_scores(feats: dict) -> dict:
    return {p.subgenre: clf._score_profile(p, feats) for p in ALL_PROFILES}


def winner(scores: dict, penalty: float):
    s = dict(scores)
    for sg in CATCH_ALL_SUBGENRES:
        if sg in s:
            s[sg] *= penalty
    ranked = sorted(s.items(), key=lambda x: x[1], reverse=True)
    win, w = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    conf = (w - second) / (w + 1e-10)
    return win, max(0.0, min(1.0, conf))


async def main() -> None:
    factory = get_session_factory()
    async with factory() as s:
        rows = (await s.execute(select(TF).order_by(func.random()).limit(SAMPLE))).scalars().all()

    print(f"sampled rows: {len(rows)}")
    lvl = Counter(r.analysis_level for r in rows)
    print(f"analysis_level dist in sample: {dict(sorted(lvl.items()))}")

    dist_pen = Counter()
    dist_nopen = Counter()
    confs = []
    flipped_from_catchall = 0
    raw_catchall_winner = 0

    # feature calibration: best achievable Gaussian similarity per feature
    feat_targets: dict[str, list[tuple[float, float]]] = {}
    for p in ALL_PROFILES:
        for name, t in p.features.items():
            feat_targets.setdefault(name, []).append((t.ideal, t.tolerance))
    feat_best_sim: dict[str, list[float]] = {k: [] for k in feat_targets}
    feat_present: Counter = Counter()

    for r in rows:
        feats = {c: getattr(r, c) for c in COLS}
        sc = raw_scores(feats)
        win_p, conf_p = winner(sc, penalty=0.85)
        win_n, _ = winner(sc, penalty=1.0)
        dist_pen[win_p.value] += 1
        dist_nopen[win_n.value] += 1
        confs.append(conf_p)
        if win_n in CATCH_ALL_SUBGENRES:
            raw_catchall_winner += 1
            if win_p not in CATCH_ALL_SUBGENRES:
                flipped_from_catchall += 1
        for name, targets in feat_targets.items():
            v = feats.get(name)
            if v is None:
                continue
            feat_present[name] += 1
            best = max(math.exp(-((float(v) - i) ** 2) / (2.0 * tol**2)) for i, tol in targets)
            feat_best_sim[name].append(best)

    confs.sort()

    def pct(p: float) -> float:
        return confs[min(len(confs) - 1, int(p * len(confs)))]

    print("\n=== LABEL DIST — WITH catch-all penalty 0.85 (prod) ===")
    for k, v in dist_pen.most_common():
        print(f"  {k:14s} {v:5d}")
    print("\n=== LABEL DIST — WITHOUT penalty (1.0) ===")
    for k, v in dist_nopen.most_common():
        print(f"  {k:14s} {v:5d}")

    print(
        f"\nraw (no-penalty) winner is driving/hypnotic: {raw_catchall_winner} "
        f"({100 * raw_catchall_winner / len(rows):.1f}%)"
    )
    print(
        f"penalty flips those away from driving/hypnotic: {flipped_from_catchall} "
        f"({100 * flipped_from_catchall / len(rows):.1f}%)"
    )
    print(
        f"\nmood_confidence (with penalty) p50={pct(0.5):.3f} "
        f"p90={pct(0.9):.3f} p99={pct(0.99):.3f} max={confs[-1]:.3f}"
    )

    print("\n=== MISCALIBRATED FEATURES (present but best-case similarity ~0) ===")
    rep = []
    for name, sims in feat_best_sim.items():
        if not sims:
            continue
        mean_best = sum(sims) / len(sims)
        rep.append((mean_best, name, feat_present[name]))
    for mean_best, name, n in sorted(rep):
        flag = "  <-- DEAD" if mean_best < 0.15 else ""
        if mean_best < 0.35:
            print(f"  {name:28s} mean_best_sim={mean_best:.3f}  present={n}{flag}")

    await dispose()


if __name__ == "__main__":
    asyncio.run(main())
