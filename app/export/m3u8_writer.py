"""M3U8 playlist writer with custom #EXTDJ-* tags."""

from __future__ import annotations

from pathlib import Path

from app.export.models import SetExportData


def write_m3u8(data: SetExportData, output_path: Path) -> Path:
    """Write extended M3U8 with custom #EXTDJ-* tags."""
    lines = ["#EXTM3U", f"#PLAYLIST:{data.name}"]

    for track in data.tracks:
        duration_sec = (track.duration_ms or 0) // 1000
        lines.append(f"#EXTINF:{duration_sec},{track.artist} - {track.title}")

        if track.bpm:
            lines.append(f"#EXTDJ-BPM:{track.bpm:.1f}")
        if track.key_camelot:
            lines.append(f"#EXTDJ-KEY:{track.key_camelot}")
        if track.energy_lufs is not None:
            lines.append(f"#EXTDJ-ENERGY:{track.energy_lufs:.1f}")

        for cue in track.cue_points:
            lines.append(
                f"#EXTDJ-CUE:{cue.get('position_ms', 0)},"
                f"{cue.get('kind', 0)},{cue.get('label', '')},{cue.get('color', '')}"
            )

        for loop in track.saved_loops:
            lines.append(
                f"#EXTDJ-LOOP:{loop.get('in_ms', 0)},"
                f"{loop.get('out_ms', 0)},{loop.get('label', '')}"
            )

        for section in track.sections:
            lines.append(
                f"#EXTDJ-SECTION:{section.get('type', '')},"
                f"{section.get('start_ms', 0)},{section.get('end_ms', 0)},"
                f"{section.get('energy', '')}"
            )

        # Transition to next track
        trans = next(
            (t for t in data.transitions if t.from_position == track.position),
            None,
        )
        if trans:
            lines.append(
                f"#EXTDJ-TRANSITION:{trans.transition_type or 'mix'},"
                f"{trans.score or 0:.2f},{trans.bpm_delta or 0:.1f},"
                f"{trans.key_distance or 0},{trans.energy_delta or 0:.1f}"
            )

        if track.mood_confidence is not None:
            lines.append(f"#EXTDJ-MOOD-CONFIDENCE:{track.mood_confidence:.2f}")
        if track.rms_dbfs is not None:
            lines.append(f"#EXTDJ-RMS:{track.rms_dbfs:.1f}")
        if track.true_peak_db is not None:
            lines.append(f"#EXTDJ-PEAK:{track.true_peak_db:.1f}")
        if track.crest_factor_db is not None:
            lines.append(f"#EXTDJ-CREST:{track.crest_factor_db:.1f}")
        if track.danceability is not None:
            lines.append(f"#EXTDJ-DANCEABILITY:{track.danceability:.2f}")
        if track.hp_ratio is not None:
            lines.append(f"#EXTDJ-HP-RATIO:{track.hp_ratio:.2f}")
        if track.dominant_phrase_bars is not None:
            lines.append(f"#EXTDJ-PHRASE:{track.dominant_phrase_bars} bars")

        if track.eq_settings:
            eq_parts = ",".join(f"{k}={v}" for k, v in track.eq_settings.items())
            lines.append(f"#EXTDJ-EQ:{eq_parts}")

        if track.notes:
            lines.append(f"#EXTDJ-NOTE:{track.notes}")

        lines.append(track.file_path)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
