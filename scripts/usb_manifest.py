#!/usr/bin/env python3
"""Generate the USB build manifest — runs on the VM (asyncpg works there).

Curates ~4.4k best techno tracks from the genre-tagged library into 6 crates
by composite DJ-quality, ranked, budget-capped, and writes a compact CSV
manifest (crate, rank, track_id, yandex_id, camelot, bpm, energy, lufs,
artist, title). The laptop then downloads audio from the manifest.
"""

from __future__ import annotations

import asyncio
import csv

from sqlalchemy import text

from app.db.session import dispose, get_session_factory

SQL = text("""
WITH base AS (
  SELECT f.track_id, f.beatport_genre AS g, f.bpm, f.energy_mean AS e, f.integrated_lufs AS lufs,
    f.key_code,
    (0.18*LEAST(COALESCE(f.danceability,0)/1.5,1.0)+0.18*COALESCE(f.kick_prominence,0)
     +0.15*COALESCE(f.pulse_clarity,0)+0.12*COALESCE(f.bpm_stability,0)+0.10*COALESCE(f.key_confidence,0)
     +0.17*COALESCE(f.energy_mean,0)+0.10*GREATEST(0,1-abs(COALESCE(f.integrated_lufs,-20)+9.5)/6)) AS q
  FROM track_audio_features_computed f
  WHERE f.beatport_genre IS NOT NULL AND f.bpm BETWEEN 118 AND 150 AND NOT COALESCE(f.variable_tempo,false)
),
crated AS (
  SELECT *, CASE
    WHEN g='Hard Techno' OR (g='Techno (Peak Time / Driving)' AND bpm>=134) THEN '05_HARD_RAVE'
    WHEN g='Techno (Raw / Deep / Hypnotic)' THEN '04_HYPNOTIC_ROLLERS'
    WHEN g='Techno (Peak Time / Driving)' AND (bpm>=130 OR e>=0.55) THEN '03_PEAK'
    WHEN g='Techno (Peak Time / Driving)' AND bpm>=126 THEN '02_DRIVING'
    WHEN g='Techno (Peak Time / Driving)' THEN '01_WARMUP'
    WHEN g='Minimal / Deep Tech' AND e>=0.46 THEN '06_MINIMAL_ROLLING'
    ELSE NULL END AS crate
  FROM base
),
ranked AS (
  SELECT crate, track_id, q, bpm, e, lufs, key_code,
    row_number() OVER (PARTITION BY crate ORDER BY q DESC) AS rn
  FROM crated WHERE crate IS NOT NULL
),
budget AS (
  SELECT *, CASE crate
    WHEN '01_WARMUP' THEN 700 WHEN '02_DRIVING' THEN 1750 WHEN '03_PEAK' THEN 1000
    WHEN '04_HYPNOTIC_ROLLERS' THEN 600 WHEN '05_HARD_RAVE' THEN 450 WHEN '06_MINIMAL_ROLLING' THEN 500 END AS cap
  FROM ranked
)
SELECT b.crate, b.rn, b.track_id, e.external_id AS yandex_id, k.camelot,
       round(b.bpm::numeric,1) AS bpm, round(b.e::numeric,2) AS energy, round(b.lufs::numeric,1) AS lufs,
       round(b.q::numeric,3) AS q, t.title
FROM budget b
JOIN tracks t ON t.id=b.track_id
LEFT JOIN track_external_ids e ON e.track_id=b.track_id AND e.platform='yandex_music'
LEFT JOIN keys k ON k.key_code=b.key_code
WHERE b.rn<=b.cap AND e.external_id IS NOT NULL
ORDER BY b.crate, b.rn;
""")


async def main() -> None:
    sf = get_session_factory()
    async with sf() as s:
        rows = (await s.execute(SQL)).mappings().all()
    with open("/root/usb_manifest.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "crate",
                "rank",
                "track_id",
                "yandex_id",
                "camelot",
                "bpm",
                "energy",
                "lufs",
                "q",
                "title",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r["crate"],
                    r["rn"],
                    r["track_id"],
                    r["yandex_id"],
                    r["camelot"] or "",
                    r["bpm"],
                    r["energy"],
                    r["lufs"],
                    r["q"],
                    r["title"],
                ]
            )
    print(f"manifest: {len(rows)} tracks -> /root/usb_manifest.csv")
    await dispose()


if __name__ == "__main__":
    asyncio.run(main())
