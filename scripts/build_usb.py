#!/usr/bin/env python3
"""Build a complete 64GB DJ USB from the dj-music-plugin database.

One program, five stages. Curates the best techno from the genre-tagged
library into crates, downloads the audio, builds the WEAPONS + PANIC crates
with the real transition engine, and emits a Rekordbox-importable library
plus per-crate playlists, a manifest, a backup mirror and the empty scaffold.

    uv run python scripts/build_usb.py --stage all
    uv run python scripts/build_usb.py --stage export    # re-emit XML/M3U8 only

Stages: curate -> download -> special -> export (run individually or `all`).

DB access: the `curate` and `special` stages need the database. asyncpg works
on the VM / under `claude --teleport`; on a host where it's blocked, pre-bake
the manifest (`scripts/usb_manifest.py` on the VM) and run with
`--manifest <csv>`, and pass `--features-json <cache>` for the special crates.
Audio download (`download`) and `export` are pure-local and need no DB.

Output tree (USB_ROOT, default ~/DJ_USB_BUILD):
    01_WARMUP/ 02_DRIVING/ 03_PEAK/ 04_HYPNOTIC_ROLLERS/ 05_HARD_RAVE/
    06_MINIMAL_ROLLING/   <rank> [<camelot>] [<bpm>] <title>.mp3
    07_WEAPONS/           top heaters by quality
    00_NOW/PANIC_90min/   one optimizer-built bulletproof arc
    08_TOOLS/ 09_FRESH_UNPLAYED/ 10_TESTED_LIVE/ _DIGGING/   empty scaffold
    _META/  rekordbox_library.xml, usb_manifest.csv, crates/*.m3u8, README.txt
    _BACKUP/  mirror of WEAPONS + PANIC + the xml
"""

from __future__ import annotations

# ruff: noqa: E501 — embedded SQL / Rekordbox-XML / README string literals
import argparse
import asyncio
import contextlib
import csv
import json
import logging
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

# ── layout ─────────────────────────────────────────────────────────────
CRATE_BUDGET = {
    "01_WARMUP": 700,
    "02_DRIVING": 1750,
    "03_PEAK": 1000,
    "04_HYPNOTIC_ROLLERS": 600,
    "05_HARD_RAVE": 450,
    "06_MINIMAL_ROLLING": 500,
}
SCAFFOLD = [
    "08_TOOLS/intros_outros",
    "08_TOOLS/percussion_loops",
    "08_TOOLS/risers_downlifters",
    "08_TOOLS/acid_lines_303",
    "09_FRESH_UNPLAYED",
    "10_TESTED_LIVE",
    "_DIGGING/by_label",
    "_DIGGING/b2b_safe",
    "_DIGGING/resurface",
]
WEAPONS_N = 50
PANIC_POOL = 40  # candidate pool the optimizer chains
PANIC_LEN = 16  # ~90 min at ~6.5 min/track

# crate -> rough "energy" tag (1..5) for Rekordbox My Tag / comments
CRATE_ENERGY = {
    "01_WARMUP": 2,
    "02_DRIVING": 3,
    "03_PEAK": 4,
    "04_HYPNOTIC_ROLLERS": 3,
    "05_HARD_RAVE": 5,
    "06_MINIMAL_ROLLING": 2,
}

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
for _n in ("httpx", "httpcore"):
    logging.getLogger(_n).setLevel(logging.WARNING)
log = logging.getLogger("usb")

# ── curation SQL (genre-tagged -> crate -> ranked -> budget-capped) ─────
_CURATE_SQL = """
WITH base AS (
  SELECT f.track_id, f.beatport_genre AS g, f.bpm, f.energy_mean AS e,
    f.integrated_lufs AS lufs, f.key_code, f.analysis_level,
    (0.18*LEAST(COALESCE(f.danceability,0)/1.5,1.0)+0.18*COALESCE(f.kick_prominence,0)
     +0.15*COALESCE(f.pulse_clarity,0)+0.12*COALESCE(f.bpm_stability,0)
     +0.10*COALESCE(f.key_confidence,0)+0.17*COALESCE(f.energy_mean,0)
     +0.10*GREATEST(0,1-abs(COALESCE(f.integrated_lufs,-20)+9.5)/6)) AS q
  FROM track_audio_features_computed f
  WHERE f.beatport_genre IS NOT NULL AND f.bpm BETWEEN 118 AND 150
    AND NOT COALESCE(f.variable_tempo,false)
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
  SELECT crate, track_id, q, bpm, e, lufs, key_code, g, analysis_level,
    row_number() OVER (PARTITION BY crate ORDER BY q DESC) AS rn FROM crated WHERE crate IS NOT NULL
)
SELECT r.crate, r.rn, r.track_id, x.external_id AS yandex_id, k.camelot,
  round(r.bpm::numeric,1) AS bpm, round(r.e::numeric,2) AS energy,
  round(r.lufs::numeric,1) AS lufs, round(r.q::numeric,3) AS q,
  r.g AS genre, r.analysis_level, t.title, t.duration_ms
FROM ranked r
JOIN tracks t ON t.id=r.track_id
LEFT JOIN track_external_ids x ON x.track_id=r.track_id AND x.platform='yandex_music'
LEFT JOIN keys k ON k.key_code=r.key_code
WHERE x.external_id IS NOT NULL
"""


def _cap(rows: list[dict]) -> list[dict]:
    return [r for r in rows if int(r["rank"]) <= CRATE_BUDGET.get(r["crate"], 0)]


# ── helpers ────────────────────────────────────────────────────────────
def fname(rank, cam, bpm, title) -> str:
    safe = re.sub(r"[^A-Za-z0-9 ()&_.,-]", "", str(title)).strip()[:80]
    return f"{int(rank):04d} [{cam or '--'}] [{bpm}] {safe}.mp3"


def split_artist(title: str) -> tuple[str, str]:
    return tuple(title.split(" - ", 1)) if " - " in title else ("", title)  # type: ignore[return-value]


def dest_of(root: Path, r: dict) -> Path:
    return root / r["crate"] / fname(r["rank"], r["camelot"], r["bpm"], r["title"])


# ── stage: curate ──────────────────────────────────────────────────────
async def curate(manifest: Path) -> None:
    from sqlalchemy import text

    from app.db.session import dispose, get_session_factory

    sf = get_session_factory()
    async with sf() as s:
        rows = (await s.execute(text(_CURATE_SQL))).mappings().all()
    capped = _cap([dict(rank=r["rn"], **{k: r[k] for k in r if k != "rn"}) for r in rows])
    capped.sort(key=lambda r: (r["crate"], int(r["rank"])))
    with manifest.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "crate",
                "rank",
                "track_id",
                "yandex_id",
                "camelot",
                "bpm",
                "energy",
                "lufs",
                "q",
                "genre",
                "analysis_level",
                "title",
                "duration_ms",
            ],
        )
        w.writeheader()
        w.writerows(capped)
    log.info("curate: %d tracks -> %s", len(capped), manifest)
    await dispose()


# ── stage: download ────────────────────────────────────────────────────
async def download(root: Path, rows: list[dict], workers: int) -> None:
    from app.config import get_settings
    from app.providers.yandex.client import YandexClient
    from app.providers.yandex.rate_limiter import TokenBucketRateLimiter

    s = get_settings()
    client = YandexClient(
        token=s.yandex.token,
        user_id=str(s.yandex.user_id),
        base_url=s.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(delay_s=1.0),
    )
    c = {"done": 0, "ok": 0, "skip": 0, "fail": 0}
    lock, sem, total = asyncio.Lock(), asyncio.Semaphore(workers), len(rows)

    async def one(r: dict) -> None:
        dest = dest_of(root, r)
        st = "FAIL"
        try:
            if dest.exists() and dest.stat().st_size > 500_000:
                st = "SKIP"
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                async with sem:
                    await client.download_track(r["yandex_id"], dest)
                st = "OK"
        except Exception as e:
            st = "FAIL"
            _ = e
        async with lock:
            c["done"] += 1
            c[{"OK": "ok", "SKIP": "skip", "FAIL": "fail"}[st]] += 1
            if c["done"] % 25 == 0 or st == "FAIL":
                log.info(
                    "[%d/%d] %s (ok=%d skip=%d fail=%d)",
                    c["done"],
                    total,
                    st,
                    c["ok"],
                    c["skip"],
                    c["fail"],
                )

    try:
        await asyncio.gather(*(one(r) for r in rows))
    finally:
        await client.close()
    log.info("download: ok=%d skip=%d fail=%d / %d", c["ok"], c["skip"], c["fail"], total)


# ── feature loading for special crates ─────────────────────────────────
async def load_features(ids: list[int], cache: Path | None) -> dict:
    if cache and cache.exists():
        raw = json.loads(cache.read_text())
        return {int(k): v for k, v in raw.items()}
    from app.db.session import dispose, get_session_factory
    from app.repositories.unit_of_work import UnitOfWork

    sf = get_session_factory()
    out: dict = {}
    async with sf() as s:
        feats = await UnitOfWork(s).track_features.get_scoring_features_batch(ids)
        out = {tid: f for tid, f in feats.items()}
    await dispose()
    return out


# ── stage: special crates (WEAPONS + PANIC) ────────────────────────────
async def special(root: Path, rows: list[dict], cache: Path | None) -> None:
    by_id = {int(r["track_id"]): r for r in rows}
    # WEAPONS: top quality across the punchy crates (peak/driving/hard/hypnotic)
    punchy = [
        r
        for r in rows
        if r["crate"] in {"02_DRIVING", "03_PEAK", "05_HARD_RAVE", "04_HYPNOTIC_ROLLERS"}
    ]
    weapons = sorted(punchy, key=lambda r: float(r["q"]), reverse=True)[:WEAPONS_N]
    wdir = root / "07_WEAPONS"
    wdir.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(weapons, 1):
        src = dest_of(root, r)
        if src.exists():
            shutil.copy2(
                src,
                wdir
                / f"{i:02d} [{r['camelot']}] [{r['bpm']}] {split_artist(r['title'])[0] or r['title']}.mp3"[
                    :120
                ],
            )
    log.info("WEAPONS: %d tracks", len(weapons))

    # PANIC: optimizer-built arc from a strong L5 pool
    from app.domain.optimization.greedy import GreedyChainBuilder
    from app.domain.transition.scorer import TransitionScorer
    from app.shared.features import TrackFeatures

    pool = [
        r
        for r in sorted(punchy, key=lambda r: float(r["q"]), reverse=True)
        if int(r.get("analysis_level") or 0) >= 5
    ][:PANIC_POOL]
    feats = await load_features([int(r["track_id"]) for r in pool], cache)
    ids = [int(r["track_id"]) for r in pool if int(r["track_id"]) in feats]
    tr = [
        feats[i] if isinstance(feats[i], TrackFeatures) else TrackFeatures(**feats[i]) for i in ids
    ]
    if len(ids) >= 4:
        order = GreedyChainBuilder(TransitionScorer()).optimize(tr, ids).track_order[:PANIC_LEN]
        pdir = root / "00_NOW" / "PANIC_90min"
        pdir.mkdir(parents=True, exist_ok=True)
        m3u = ["#EXTM3U", "#PLAYLIST:PANIC 90min"]
        for pos, tid in enumerate(order, 1):
            r = by_id[tid]
            src = dest_of(root, r)
            nm = f"{pos:02d} [{r['camelot']}] [{r['bpm']}] {r['title']}.mp3"[:120]
            if src.exists():
                shutil.copy2(src, pdir / nm)
            m3u += [f"#EXTINF:-1,{r['title']}  [{r['camelot']} {r['bpm']}]", nm]
        (pdir / "PANIC.m3u8").write_text("\n".join(m3u) + "\n")
        log.info("PANIC_90min: %d tracks (optimizer order)", len(order))


# ── stage: export (rekordbox xml + m3u8 + manifest + scaffold + backup) ─
def export(root: Path, rows: list[dict], manifest: Path) -> None:
    meta = root / "_META"
    (meta / "crates").mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, meta / "usb_manifest.csv")

    # per-crate M3U8
    crates: dict[str, list[dict]] = {}
    for r in rows:
        crates.setdefault(r["crate"], []).append(r)
    for crate, items in crates.items():
        items.sort(key=lambda r: int(r["rank"]))
        lines = ["#EXTM3U", f"#PLAYLIST:{crate}"]
        for r in items:
            f = fname(r["rank"], r["camelot"], r["bpm"], r["title"])
            lines += [
                f"#EXTINF:-1,{r['title']}  [{r['camelot']} {r['bpm']}BPM]",
                f"#EXTDJ-KEY:{r['camelot']}",
                f"#EXTDJ-BPM:{r['bpm']}",
                f"../{crate}/{f}",
            ]
        (meta / "crates" / f"{crate}.m3u8").write_text("\n".join(lines) + "\n")

    # Rekordbox XML (import: rekordbox -> File -> Import Collection)
    tracks_xml, pls_xml = [], []
    for r in rows:
        artist, name = split_artist(r["title"])
        loc = "file://localhost" + quote(str(dest_of(root, r)))
        dur = (
            int(int(r.get("duration_ms") or 0) / 1000)
            if str(r.get("duration_ms") or "").strip()
            else 0
        )
        tracks_xml.append(
            f'    <TRACK TrackID="{r["track_id"]}" Name="{escape(name)}" Artist="{escape(artist)}" '
            f'Genre="{escape(r.get("genre") or "Techno")}" Kind="MP3 File" TotalTime="{dur}" '
            f'AverageBpm="{float(r["bpm"]):.2f}" Tonality="{r["camelot"]}" '
            f'Comments="energy={CRATE_ENERGY.get(r["crate"], 3)} crate={r["crate"]}" Location="{loc}"/>'
        )
    for crate, items in sorted(crates.items()):
        keys = "".join(f'        <TRACK Key="{r["track_id"]}"/>\n' for r in items)
        pls_xml.append(
            f'      <NODE Name="{crate}" Type="1" KeyType="0" Entries="{len(items)}">\n{keys}      </NODE>'
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<DJ_PLAYLISTS Version="1.0.0">\n'
        '  <PRODUCT Name="rekordbox" Version="6.0.0" Company="AlphaTheta"/>\n'
        f'  <COLLECTION Entries="{len(rows)}">\n' + "\n".join(tracks_xml) + "\n  </COLLECTION>\n"
        '  <PLAYLISTS>\n    <NODE Type="0" Name="ROOT" Count="'
        + str(len(crates))
        + '">\n'
        + "\n".join(pls_xml)
        + "\n    </NODE>\n  </PLAYLISTS>\n</DJ_PLAYLISTS>\n"
    )
    (meta / "rekordbox_library.xml").write_text(xml)

    # scaffold + backup + readme
    for d in SCAFFOLD:
        (root / d).mkdir(parents=True, exist_ok=True)
    bak = root / "_BACKUP"
    bak.mkdir(exist_ok=True)
    shutil.copy2(meta / "rekordbox_library.xml", bak / "rekordbox_library.xml")
    for crate in ("07_WEAPONS", "00_NOW/PANIC_90min"):
        src = root / crate
        if src.exists():
            shutil.copytree(src, bak / (crate.replace("/", "_") + "_mirror"), dirs_exist_ok=True)
    (meta / "README.txt").write_text(
        "DJ USB — filename = `<rank> [<camelot>] [<bpm>] <artist - title>.mp3`.\n"
        "Crates: 01_WARMUP 02_DRIVING 03_PEAK 04_HYPNOTIC_ROLLERS 05_HARD_RAVE 06_MINIMAL_ROLLING\n"
        "07_WEAPONS = heaters, 00_NOW/PANIC_90min = bulletproof arc.\n"
        "Rekordbox: File -> Import Collection -> _META/rekordbox_library.xml, then Export to device\n"
        "(that creates PIONEER/). 08_TOOLS/09_FRESH/10_TESTED/_DIGGING are empty scaffolds.\n"
    )
    log.info("export: %d crate playlists + rekordbox xml + backup + scaffold", len(crates))


# ── orchestration ──────────────────────────────────────────────────────
async def run(args: argparse.Namespace) -> None:
    root = Path(args.usb_root).expanduser()
    manifest = Path(args.manifest).expanduser()
    cache = Path(args.features_json).expanduser() if args.features_json else None
    stages = ["curate", "download", "special", "export"] if args.stage == "all" else [args.stage]

    if "curate" in stages and not (args.manifest and manifest.exists() and args.stage != "curate"):
        await curate(manifest)
    rows = list(csv.DictReader(manifest.open())) if manifest.exists() else []
    if not rows and stages != ["curate"]:
        raise SystemExit(f"no manifest at {manifest} — run --stage curate first (needs DB)")
    if "download" in stages:
        await download(root, rows, args.workers)
    if "special" in stages:
        await special(root, rows, cache)
    if "export" in stages:
        export(root, rows, manifest)
    t = sum(1 for _ in root.rglob("*.mp3")) if root.exists() else 0
    log.info("USB at %s — %d mp3 files on disk", root, t)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a DJ USB from the dj-music-plugin DB")
    ap.add_argument(
        "--stage", choices=["all", "curate", "download", "special", "export"], default="all"
    )
    ap.add_argument("--usb-root", default="~/DJ_USB_BUILD")
    ap.add_argument("--manifest", default="/tmp/usb_manifest.csv")
    ap.add_argument(
        "--features-json", default=None, help="offline TrackFeatures cache for special crates"
    )
    ap.add_argument("--workers", type=int, default=4)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
