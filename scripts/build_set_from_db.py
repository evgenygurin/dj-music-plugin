"""Build an optimized DJ set from already-analyzed tracks in Supabase.

Reads audio features via Supabase REST API, runs greedy chain builder
with the real 6-component TransitionScorer, and outputs the result.

Usage:
    python scripts/build_set_from_db.py --mood peak_time --limit 20
    python scripts/build_set_from_db.py --mood acid --limit 15 --bpm-min 130 --bpm-max 140
    python scripts/build_set_from_db.py --playlist-id 14 --limit 20
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_set")

import httpx

from app.entities.audio.features import TrackFeatures
from app.transition.recommender import TransitionRecommender
from app.transition.scorer import TransitionScorer


def _load_supabase_creds() -> tuple[str, str]:
    """Load Supabase URL and anon key from env or panel/.env."""
    sb_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    sb_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
    if sb_url and sb_key:
        return sb_url, sb_key
    from pathlib import Path

    panel_env = Path(__file__).resolve().parent.parent / "panel" / ".env"
    if not panel_env.exists():
        panel_env = Path(__file__).resolve().parent.parent / "panel" / ".env.local"
    if panel_env.exists():
        for line in panel_env.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip().strip("\"'")
            if k.strip() == "NEXT_PUBLIC_SUPABASE_URL":
                sb_url = v
            elif k.strip() == "NEXT_PUBLIC_SUPABASE_ANON_KEY":
                sb_key = v
    if not sb_url or not sb_key:
        log.error(
            "Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, or create panel/.env"
        )
        sys.exit(1)
    return sb_url, sb_key


_SB_URL, _SB_KEY = "", ""


def _sb_headers() -> tuple[dict[str, str], str]:
    global _SB_URL, _SB_KEY
    if not _SB_URL:
        _SB_URL, _SB_KEY = _load_supabase_creds()
    return {
        "apikey": _SB_KEY,
        "Authorization": f"Bearer {_SB_KEY}",
    }, _SB_URL


def _fetch_tracks_by_mood(
    mood: str,
    limit: int,
    bpm_min: float | None,
    bpm_max: float | None,
) -> list[dict]:
    """Fetch tracks with features from Supabase by mood."""
    headers, url = _sb_headers()

    # Build filter
    params = f"mood=eq.{mood}&bpm=not.is.null&integrated_lufs=not.is.null"
    if bpm_min:
        params += f"&bpm=gte.{bpm_min}"
    if bpm_max:
        params += f"&bpm=lte.{bpm_max}"

    fields = (
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

    r = httpx.get(
        f"{url}/rest/v1/track_audio_features_computed?select={fields}&{params}"
        f"&order=bpm.asc&limit={limit}",
        headers=headers,
    )
    if r.status_code != 200:
        log.error("Supabase error: %s %s", r.status_code, r.text[:200])
        return []
    return r.json()


def _fetch_tracks_by_playlist(playlist_id: int, limit: int) -> list[dict]:
    """Fetch track features for tracks in a playlist."""
    headers, url = _sb_headers()

    # Get track IDs from playlist
    r = httpx.get(
        f"{url}/rest/v1/dj_playlist_items?select=track_id&playlist_id=eq.{playlist_id}"
        f"&order=sort_index.asc&limit={limit}",
        headers=headers,
    )
    if r.status_code != 200 or not r.json():
        return []
    track_ids = [str(item["track_id"]) for item in r.json()]

    # Get features
    fields = (
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
    id_filter = ",".join(track_ids)
    r = httpx.get(
        f"{url}/rest/v1/track_audio_features_computed?select={fields}"
        f"&track_id=in.({id_filter})&bpm=not.is.null",
        headers=headers,
    )
    if r.status_code != 200:
        return []
    return r.json()


def _fetch_track_titles(track_ids: list[int]) -> dict[int, str]:
    """Fetch track titles from DB."""
    headers, url = _sb_headers()
    titles: dict[int, str] = {}
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i : i + 50]
        id_filter = ",".join(str(tid) for tid in batch)
        r = httpx.get(
            f"{url}/rest/v1/tracks?select=id,title&id=in.({id_filter})",
            headers=headers,
        )
        if r.status_code == 200:
            for t in r.json():
                titles[t["id"]] = t["title"]
    return titles


def _row_to_features(row: dict) -> TrackFeatures:
    """Convert Supabase row to TrackFeatures dataclass."""

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

    # Build energy_bands list from individual band columns
    energy_bands = [
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
        energy_bands=energy_bands if any(b != 0.0 for b in energy_bands) else None,
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


def _greedy_build(
    features: dict[int, TrackFeatures],
    scorer: TransitionScorer,
) -> list[int]:
    """Greedy chain builder — at each step pick the best transition."""
    if not features:
        return []

    track_ids = list(features.keys())
    if len(track_ids) <= 2:
        return track_ids

    # Start with the track that has lowest BPM (warm-up feel)
    remaining = set(track_ids)
    start = min(remaining, key=lambda tid: features[tid].bpm)
    chain = [start]
    remaining.remove(start)

    while remaining:
        current = chain[-1]
        best_id = None
        best_score = -1.0

        for candidate in remaining:
            score = scorer.score(features[current], features[candidate])
            if score.overall > best_score:
                best_score = score.overall
                best_id = candidate

        if best_id is not None:
            chain.append(best_id)
            remaining.remove(best_id)
        else:
            break

    return chain


def main(args: argparse.Namespace) -> None:
    log.info("=" * 60)
    log.info("DJ Set Builder — Real Transition Scoring")
    log.info("=" * 60)

    # Step 1: Fetch tracks from Supabase
    if args.playlist_id:
        log.info("Fetching tracks from playlist id=%d...", args.playlist_id)
        rows = _fetch_tracks_by_playlist(args.playlist_id, args.limit)
    else:
        log.info(
            "Fetching %s tracks (BPM %s-%s, limit %d)...",
            args.mood,
            args.bpm_min or "any",
            args.bpm_max or "any",
            args.limit,
        )
        rows = _fetch_tracks_by_mood(args.mood, args.limit, args.bpm_min, args.bpm_max)

    if not rows:
        log.error("No tracks found")
        return

    log.info("Loaded %d tracks with features from Supabase", len(rows))

    # Step 2: Convert to TrackFeatures
    features: dict[int, TrackFeatures] = {}
    for row in rows:
        tid = row["track_id"]
        features[tid] = _row_to_features(row)

    # Fetch titles
    titles = _fetch_track_titles(list(features.keys()))

    # Step 3: Greedy chain build with TransitionScorer
    log.info("Building greedy chain with 6-component TransitionScorer...")
    scorer = TransitionScorer()
    recommender = TransitionRecommender()
    chain = _greedy_build(features, scorer)
    log.info("Chain built: %d tracks", len(chain))

    # Step 4: Score all transitions
    log.info("=" * 60)
    log.info("SET ORDER (optimized by transition quality)")
    log.info("=" * 60)

    total_score = 0.0
    hard_conflicts = 0
    min_score = 1.0
    transition_details = []

    for i, tid in enumerate(chain):
        f = features[tid]
        title = titles.get(tid, f"Track #{tid}")
        from app.camelot.wheel import key_code_to_camelot

        cam = key_code_to_camelot(f.key_code) if f.key_code is not None else "?"
        log.info(
            "  %2d. [%6.1f BPM | %4s | %6.1f LUFS | E=%.2f] %s",
            i + 1,
            f.bpm,
            cam,
            f.integrated_lufs or 0,
            f.energy_mean,
            title,
        )

        if i > 0:
            prev = features[chain[i - 1]]
            score = scorer.score(prev, f)
            rec = recommender.recommend(score, prev, f)

            if score.hard_reject:
                hard_conflicts += 1
                log.warning(
                    "       ^^^ HARD REJECT: %s (score=0.0)",
                    score.reject_reason,
                )
            else:
                total_score += score.overall
                min_score = min(min_score, score.overall)
                log.info(
                    "       ↑ %.3f [bpm=%.2f harm=%.2f ener=%.2f spec=%.2f grv=%.2f tmb=%.2f] "
                    "→ fx=%s",
                    score.overall,
                    score.bpm,
                    score.harmonic,
                    score.energy,
                    score.spectral,
                    score.groove,
                    score.timbral,
                    rec.fx_type.value,
                )

            transition_details.append(
                {
                    "from": titles.get(chain[i - 1], "?"),
                    "to": title,
                    "score": score,
                    "rec": rec,
                }
            )

    n_transitions = len(chain) - 1
    avg_score = total_score / max(n_transitions - hard_conflicts, 1)

    # Summary
    log.info("=" * 60)
    log.info("SET SUMMARY")
    log.info("=" * 60)
    bpms = [features[tid].bpm for tid in chain]
    lufs = [features[tid].integrated_lufs or 0 for tid in chain]
    log.info("  Tracks: %d", len(chain))
    log.info("  BPM range: %.1f - %.1f", min(bpms), max(bpms))
    log.info("  LUFS range: %.1f - %.1f", min(lufs), max(lufs))
    log.info("  Transitions: %d", n_transitions)
    log.info("  Hard conflicts: %d", hard_conflicts)
    log.info("  Average score: %.3f", avg_score)
    log.info("  Min score: %.3f", min_score if min_score < 1.0 else 0.0)

    # Best/worst transitions
    valid = [t for t in transition_details if not t["score"].hard_reject]
    if valid:
        best = max(valid, key=lambda t: t["score"].overall)
        worst = min(valid, key=lambda t: t["score"].overall)
        log.info("  Best:  %.3f  %s → %s", best["score"].overall, best["from"], best["to"])
        log.info("  Worst: %.3f  %s → %s", worst["score"].overall, worst["from"], worst["to"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build DJ set from Supabase data")
    parser.add_argument("--mood", default="peak_time", help="Subgenre mood filter")
    parser.add_argument("--playlist-id", type=int, help="Use playlist instead of mood filter")
    parser.add_argument("--limit", type=int, default=20, help="Max tracks in set")
    parser.add_argument("--bpm-min", type=float, help="Min BPM filter")
    parser.add_argument("--bpm-max", type=float, help="Max BPM filter")
    main(parser.parse_args())
