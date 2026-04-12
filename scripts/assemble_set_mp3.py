"""Download tracks and assemble a DJ set into a single MP3 with crossfades.

Reads the optimized track order from Supabase, downloads MP3s from YM,
and merges them via ffmpeg with configurable crossfade.

Usage:
    python scripts/assemble_set_mp3.py --mood acid --limit 15 --bpm-min 128 --bpm-max 138
    python scripts/assemble_set_mp3.py --mood peak_time --limit 10 --crossfade 8
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("assemble")

import httpx

from app.camelot.wheel import key_code_to_camelot
from app.config import Settings
from app.entities.audio.features import TrackFeatures
from app.transition.scorer import TransitionScorer
from app.ym.client import YandexMusicClient
from app.ym.rate_limiter import RateLimiter


def _sb_get(path: str) -> httpx.Response:
    url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    key = os.environ["NEXT_PUBLIC_SUPABASE_ANON_KEY"]
    return httpx.get(
        f"{url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )


FEATURE_FIELDS = (
    "track_id,bpm,bpm_confidence,bpm_stability,variable_tempo,"
    "integrated_lufs,short_term_lufs_mean,loudness_range_lu,crest_factor_db,"
    "energy_mean,energy_max,energy_std,energy_slope,"
    "energy_sub,energy_low,energy_lowmid,energy_mid,energy_highmid,energy_high,"
    "spectral_centroid_hz,spectral_rolloff_85,spectral_rolloff_95,"
    "spectral_flatness,spectral_flux_mean,spectral_flux_std,"
    "spectral_slope,spectral_contrast,hnr_db,chroma_entropy,"
    "key_code,key_confidence,atonality,"
    "mfcc_vector,onset_rate,pulse_clarity,kick_prominence,hp_ratio,"
    "mood,mood_confidence,analysis_level,"
    "tonnetz_vector,tempogram_ratio_vector,"
    "beat_loudness_band_ratio,danceability,dissonance_mean,"
    "dynamic_complexity,pitch_salience_mean,spectral_complexity_mean"
)


def _parse_vector(val: object) -> list[float] | None:
    if val is None:
        return None
    if isinstance(val, list):
        return [float(x) for x in val]
    if isinstance(val, str):
        import json

        try:
            return [float(x) for x in json.loads(val)]
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _row_to_features(row: dict) -> TrackFeatures:
    bands = [
        row.get("energy_sub") or 0.0,
        row.get("energy_low") or 0.0,
        row.get("energy_lowmid") or 0.0,
        row.get("energy_mid") or 0.0,
        row.get("energy_highmid") or 0.0,
        row.get("energy_high") or 0.0,
    ]
    return TrackFeatures(
        bpm=row.get("bpm"),
        bpm_confidence=row.get("bpm_confidence"),
        bpm_stability=row.get("bpm_stability"),
        variable_tempo=row.get("variable_tempo"),
        integrated_lufs=row.get("integrated_lufs"),
        short_term_lufs_mean=row.get("short_term_lufs_mean"),
        loudness_range_lu=row.get("loudness_range_lu"),
        crest_factor_db=row.get("crest_factor_db"),
        energy_mean=row.get("energy_mean"),
        energy_slope=row.get("energy_slope"),
        energy_bands=bands if any(b != 0.0 for b in bands) else None,
        spectral_centroid_hz=row.get("spectral_centroid_hz"),
        spectral_rolloff_85=row.get("spectral_rolloff_85"),
        spectral_rolloff_95=row.get("spectral_rolloff_95"),
        spectral_flatness=row.get("spectral_flatness"),
        spectral_flux_std=row.get("spectral_flux_std"),
        spectral_slope=row.get("spectral_slope"),
        spectral_contrast=row.get("spectral_contrast"),
        hnr_db=row.get("hnr_db"),
        chroma_entropy=row.get("chroma_entropy"),
        key_code=row.get("key_code"),
        key_confidence=row.get("key_confidence"),
        atonality=row.get("atonality"),
        mfcc_vector=_parse_vector(row.get("mfcc_vector")),
        onset_rate=row.get("onset_rate"),
        pulse_clarity=row.get("pulse_clarity"),
        kick_prominence=row.get("kick_prominence"),
        hp_ratio=row.get("hp_ratio"),
        tonnetz_vector=_parse_vector(row.get("tonnetz_vector")),
        tempogram_ratio_vector=_parse_vector(row.get("tempogram_ratio_vector")),
        beat_loudness_band_ratio=_parse_vector(row.get("beat_loudness_band_ratio")),
        danceability=row.get("danceability"),
        dissonance_mean=row.get("dissonance_mean"),
        dynamic_complexity=row.get("dynamic_complexity"),
        pitch_salience_mean=row.get("pitch_salience_mean"),
        spectral_complexity_mean=row.get("spectral_complexity_mean"),
        mood=row.get("mood"),
    )


def _greedy_build(features: dict[int, TrackFeatures], scorer: TransitionScorer) -> list[int]:
    if len(features) <= 2:
        return list(features.keys())
    remaining = set(features.keys())
    start = min(remaining, key=lambda tid: features[tid].bpm or 0)
    chain = [start]
    remaining.remove(start)
    while remaining:
        current = chain[-1]
        best_id, best_score = None, -1.0
        for c in remaining:
            s = scorer.score(features[current], features[c])
            if s.overall > best_score:
                best_score = s.overall
                best_id = c
        if best_id is not None:
            chain.append(best_id)
            remaining.remove(best_id)
        else:
            break
    return chain


def _merge_with_crossfade(mp3_files: list[Path], output: Path, crossfade_s: int) -> bool:
    """Merge MP3 files with crossfade using iterative pairwise ffmpeg calls."""
    if len(mp3_files) == 0:
        return False
    if len(mp3_files) == 1:
        shutil.copy2(mp3_files[0], output)
        return True

    tmp_dir = output.parent / "_merge_tmp"
    tmp_dir.mkdir(exist_ok=True)

    try:
        current = mp3_files[0]
        for i in range(1, len(mp3_files)):
            next_file = mp3_files[i]
            is_last = i == len(mp3_files) - 1
            out_file = output if is_last else (tmp_dir / f"merge_{i:03d}.mp3")

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(current),
                "-i",
                str(next_file),
                "-filter_complex",
                f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a0];"
                f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a1];"
                f"[a0][a1]acrossfade=d={crossfade_s}:c1=tri:c2=tri[out]",
                "-map",
                "[out]",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "320k",
                str(out_file),
            ]

            log.info("  Merging track %d/%d...", i + 1, len(mp3_files))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                log.error(
                    "ffmpeg pair merge failed at track %d: %s",
                    i + 1,
                    result.stderr[-300:] if result.stderr else "",
                )
                return False
            current = out_file

        return output.exists()
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def main(args: argparse.Namespace) -> None:
    settings = Settings()
    t_total = time.time()

    # Step 1: Load features from Supabase
    log.info("=" * 60)
    log.info("STEP 1: Loading %s tracks from Supabase", args.mood)
    log.info("=" * 60)

    params = f"mood=eq.{args.mood}&bpm=not.is.null&integrated_lufs=not.is.null"
    if args.bpm_min:
        params += f"&bpm=gte.{args.bpm_min}"
    if args.bpm_max:
        params += f"&bpm=lte.{args.bpm_max}"
    r = _sb_get(
        f"track_audio_features_computed?select={FEATURE_FIELDS}&{params}&order=bpm.asc&limit={args.limit}"
    )
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        log.error("No tracks found")
        return
    log.info("Loaded %d tracks", len(rows))

    features = {row["track_id"]: _row_to_features(row) for row in rows}
    track_ids = list(features.keys())

    # Get titles
    titles: dict[int, str] = {}
    id_filter = ",".join(str(t) for t in track_ids)
    r = _sb_get(f"tracks?select=id,title&id=in.({id_filter})")
    if r.status_code == 200:
        titles = {t["id"]: t["title"] for t in r.json()}

    # Get YM IDs
    r = _sb_get(
        f"track_external_ids?select=track_id,external_id&platform=eq.yandex_music&track_id=in.({id_filter})"
    )
    ym_ids: dict[int, str] = {}
    if r.status_code == 200:
        ym_ids = {row["track_id"]: row["external_id"] for row in r.json()}

    # Filter to tracks that have YM IDs (downloadable)
    downloadable = {tid: f for tid, f in features.items() if tid in ym_ids}
    log.info("Downloadable: %d / %d (have YM IDs)", len(downloadable), len(features))
    if not downloadable:
        log.error("No tracks with YM IDs to download")
        return

    # Step 2: Build optimized order
    log.info("=" * 60)
    log.info("STEP 2: Building optimized chain")
    log.info("=" * 60)
    scorer = TransitionScorer()
    chain = _greedy_build(downloadable, scorer)
    log.info("Chain: %d tracks", len(chain))

    for i, tid in enumerate(chain):
        f = features[tid]
        cam = key_code_to_camelot(f.key_code) if f.key_code is not None else "?"
        log.info(
            "  %2d. [%5.1f BPM %4s %5.1f LUFS] %s",
            i + 1,
            f.bpm or 0,
            cam,
            f.integrated_lufs or 0,
            titles.get(tid, f"#{tid}"),
        )

    # Step 3: Download MP3s
    log.info("=" * 60)
    log.info("STEP 3: Downloading %d MP3s from Yandex Music", len(chain))
    log.info("=" * 60)

    out_dir = Path("generated-sets") / f"{args.mood}-set"
    out_dir.mkdir(parents=True, exist_ok=True)

    ym = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=RateLimiter(
            delay=settings.ym_rate_limit_delay,
            max_retries=settings.ym_retry_attempts,
            backoff_factor=settings.ym_retry_backoff_factor,
        ),
    )

    mp3_files: list[Path] = []
    try:
        for i, tid in enumerate(chain):
            ym_id = ym_ids[tid]
            title = titles.get(tid, f"Track_{tid}")
            safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[
                :60
            ].strip()
            filename = f"{i + 1:02d}. {safe_title}.mp3"
            dest = out_dir / filename

            if dest.exists() and dest.stat().st_size > 100_000:
                log.info("  [%d/%d] SKIP (exists): %s", i + 1, len(chain), filename)
                mp3_files.append(dest)
                continue

            log.info("  [%d/%d] Downloading ym:%s → %s", i + 1, len(chain), ym_id, filename)
            t0 = time.time()
            try:
                size = await ym.download_track(ym_id, str(dest))
                log.info("    OK %.1f MB in %.1fs", size / 1_048_576, time.time() - t0)
                mp3_files.append(dest)
            except Exception as e:
                log.error("    FAILED: %s", e)
    finally:
        await ym.close()

    if not mp3_files:
        log.error("No MP3s downloaded")
        return

    log.info("Downloaded %d / %d tracks", len(mp3_files), len(chain))

    # Step 4: Merge into single MP3
    log.info("=" * 60)
    log.info("STEP 4: Merging into single MP3 (%ds crossfade)", args.crossfade)
    log.info("=" * 60)

    output_file = out_dir / f"{args.mood}_set_mixed.mp3"
    ok = _merge_with_crossfade(mp3_files, output_file, args.crossfade)

    if ok and output_file.exists():
        size_mb = output_file.stat().st_size / 1_048_576
        log.info("=" * 60)
        log.info("DONE in %.1fs", time.time() - t_total)
        log.info("=" * 60)
        log.info("Output: %s (%.1f MB)", output_file, size_mb)
        log.info("Tracks: %d", len(mp3_files))
        [features[tid].bpm or 0 for tid in chain if tid in {t: None for t in chain}]
        log.info("Individual tracks in: %s", out_dir)
    else:
        log.error("Merge failed — individual tracks still available in %s", out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble DJ set as single MP3")
    parser.add_argument("--mood", default="acid", help="Subgenre mood")
    parser.add_argument("--limit", type=int, default=15, help="Max tracks")
    parser.add_argument("--bpm-min", type=float, help="Min BPM")
    parser.add_argument("--bpm-max", type=float, help="Max BPM")
    parser.add_argument("--crossfade", type=int, default=6, help="Crossfade duration in seconds")
    main_args = parser.parse_args()

    asyncio.run(main(main_args))
