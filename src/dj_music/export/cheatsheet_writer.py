"""Human-readable text cheat sheet writer."""

from __future__ import annotations

from pathlib import Path

from dj_music.export.models import SetExportData


def write_cheat_sheet(data: SetExportData, output_path: Path) -> Path:
    """Write human-readable text cheat sheet."""
    lines = [
        f"{'=' * 60}",
        f"  {data.name}",
        f"  Version: {data.version_label or 'N/A'}",
        f"  Score: {data.quality_score or 'N/A'}",
        f"  Tracks: {len(data.tracks)}",
        f"{'=' * 60}",
        "",
    ]

    for _i, track in enumerate(data.tracks):
        bpm_str = f"{track.bpm:.0f}" if track.bpm else "?"
        key_str = track.key_camelot or "?"
        energy_str = f"{track.energy_lufs:.1f}" if track.energy_lufs is not None else "?"

        flags = []
        if track.variable_tempo:
            flags.append("VarTempo")
        if track.true_peak_db is not None and track.true_peak_db > -0.5:
            flags.append(f"Peak>{track.true_peak_db:.1f}")
        if track.mood_confidence is not None and track.mood_confidence < 0.5:
            flags.append("LowConf")

        lines.append(f"{track.position + 1:2d}. {track.artist} - {track.title}")
        lines.append(
            f"    BPM: {bpm_str}  Key: {key_str}  Energy: {energy_str} LUFS"
            f"  Mood: {track.mood or '?'}" + (f"  [{', '.join(flags)}]" if flags else "")
        )
        if track.dominant_phrase_bars is not None:
            lines.append(f"    Phrase: {track.dominant_phrase_bars} bars")

        # Section summary
        if track.sections:
            section_parts = [
                f"{s.get('type', '?')}@{s.get('start_ms', 0) // 1000}s" for s in track.sections
            ]
            lines.append(f"    Sections: {' | '.join(section_parts)}")

        # Transition info
        trans = next(
            (t for t in data.transitions if t.from_position == track.position),
            None,
        )
        if trans:
            score_str = f"{trans.score:.2f}" if trans.score is not None else "?"
            problems = []
            if trans.score is not None and trans.score == 0.0:
                problems.append("HARD CONFLICT")
            elif trans.score is not None and trans.score < 0.5:
                problems.append("WEAK")

            lines.append(
                f"    → Next: score={score_str}"
                f"  BPM Δ{trans.bpm_delta or 0:+.0f}"
                f"  Key dist={trans.key_distance or '?'}"
                f"  Energy Δ{trans.energy_delta or 0:+.1f}"
                + (f"  ⚠ {', '.join(problems)}" if problems else "")
            )
            # Recipe details
            if trans and trans.recipe_steps:
                type_label = (trans.transition_type or "blend").upper().replace("_", " ")
                bars_str = f"{trans.transition_bars} bars" if trans.transition_bars else ""
                djay_str = ""
                if trans.djay_transition and trans.djay_transition != "none":
                    djay_str = f" ─── djay: {trans.djay_transition.replace('_', ' ').title()}"
                else:
                    djay_str = " ─── djay: Manual EQ"
                lines.append(f"    ┌── {type_label} · {bars_str}{djay_str} ──┐")
                for step in trans.recipe_steps:
                    bar = step.get("bar", 0)
                    deck = step.get("deck", "?").upper()
                    action = step.get("action", "")
                    lines.append(f"    │  bar {bar:<3}  {deck}: {action}")
                if trans.eq_plan:
                    eq = trans.eq_plan
                    lines.append(
                        f"    │  EQ: low={eq.get('low', '?')} · "
                        f"mid={eq.get('mid', '?')} · high={eq.get('high', '?')}"
                    )
                if trans.rescue_move:
                    lines.append(f"    │  Rescue: {trans.rescue_move}")
                lines.append("    └" + "─" * 50 + "┘")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
