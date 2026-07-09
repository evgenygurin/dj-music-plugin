"""Pure builder for the ffmpeg ``filter_complex`` graph.

Ported from render_pipeline.py ``render()`` — string assembly only, no IO.
Each segment i reads ffmpeg input ``[i:a]`` (the runner supplies ``-i`` per
segment, in order). Returns the list of graph statements; the runner joins
them with ';'.

3-band phased EQ ritual: highs phase 1 (p1 of transition), mids phase 2
(p1→p2 of transition), bass pinpoint swap at phase 3 (p2 of transition).
"""

from __future__ import annotations

from app.domain.render.eq import build_master_eq
from app.domain.render.models import RenderPlan


def build_filtergraph(plan: RenderPlan) -> list[str]:
    n = plan.n
    xlo = plan.xsplit_low_hz
    xhi = plan.xsplit_high_hz
    bar_s = 4.0 * (60.0 / plan.target_bpm)
    beat_s = 60.0 / plan.target_bpm
    low_x = plan.low_swap_beats * beat_s
    p1 = plan.eq_phase_1_ratio
    p2 = plan.eq_phase_2_ratio
    parts: list[str] = []
    mixlabels: list[str] = []
    running_t = 0.0

    for seg in plan.segments:
        i = seg.index
        d_in = seg.d_in_s
        d_out = seg.d_out_s
        length = seg.length_s

        base = (
            f"[{i}:a]atrim=start={seg.trim_start_s:.4f}:"
            f"duration={length / seg.tempo_ratio + 1.0:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={seg.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={length:.3f},asetpts=PTS-STARTPTS,volume={seg.gain_db:.2f}dB,"
            f"aformat=sample_rates=44100:channel_layouts=stereo"
        )
        parts.append(f"{base}[s{i}]")

        # 3-band split
        parts.append(f"[s{i}]asplit=3[s{i}a][s{i}b][s{i}c]")
        parts.append(f"[s{i}a]lowpass=f={xlo}[lo{i}]")
        parts.append(f"[s{i}b]highpass=f={xlo},lowpass=f={xhi}[mid{i}]")
        parts.append(f"[s{i}c]highpass=f={xhi}[hi{i}]")

        fd = min(plan.outro_fade_bars * bar_s, length)

        # ── HIGH band: Phase 1 only ──
        # Incoming HIGH: fade in during first p1 of transition
        # Outgoing HIGH: fade out during last p1 of transition
        hi: list[str] = []
        if i > 0:
            d_hi = d_in * p1
            hi.append(f"afade=t=in:curve=qsin:st=0:d={d_hi:.3f}")
        if i < n - 1:
            d_hi_out = d_out * p1
            hi.append(f"afade=t=out:curve=qsin:st={length - d_out:.3f}:d={d_hi_out:.3f}")
        else:
            hi.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[hi{i}]{','.join(hi) if hi else 'acopy'}[H{i}]")

        # ── MID band: Phase 2 ──
        # Incoming MID: silent until p1*d_in, then fade in over (p2-p1)*d_in
        # Outgoing MID: fade out over (p2-p1)*d_out starting at (1-p2)*d_out before end
        mid: list[str] = []
        if i > 0:
            mid_delay = d_in * p1
            mid_dur = d_in * (p2 - p1)
            mid.append(f"afade=t=in:curve=qsin:st={mid_delay:.3f}:d={mid_dur:.3f}")
        if i < n - 1:
            mid_st = length - d_out * (1.0 - p1)
            mid_dur_out = d_out * (p2 - p1)
            mid.append(f"afade=t=out:curve=qsin:st={mid_st:.3f}:d={mid_dur_out:.3f}")
        else:
            mid.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[mid{i}]{','.join(mid) if mid else 'acopy'}[MID{i}]")

        # ── LOW band: Pinpoint swap (Phase 3) ──
        # Incoming LOW: 1-beat fade in at d_in * p2
        # Outgoing LOW: 1-beat fade out at length - d_out * (1 - p2)
        lo: list[str] = []
        if i > 0:
            st = d_in * p2 - low_x / 2
            lo.append(f"afade=t=in:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        if i < n - 1:
            st = length - d_out * (1.0 - p2) - low_x / 2
            lo.append(f"afade=t=out:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        else:
            lo.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[lo{i}]{','.join(lo) if lo else 'acopy'}[Lo{i}]")

        # Mix 3 bands back
        t_ms = int(running_t * 1000)
        parts.append(
            f"[H{i}][MID{i}][Lo{i}]amix=inputs=3:normalize=0,adelay={t_ms}|{t_ms}|{t_ms}[m{i}]"
        )
        mixlabels.append(f"[m{i}]")
        running_t += length - d_out

    master_eq = build_master_eq(
        plan.master_eq_mud_cut_db, plan.master_eq_air_boost_db, plan.master_eq_sub_boost_db
    )
    parts.append(
        "".join(mixlabels) + f"amix=inputs={n}:normalize=0,"
        f"acompressor=threshold={plan.glue_comp_threshold_db}dB:"
        f"ratio={plan.glue_comp_ratio}:attack={plan.glue_comp_attack_ms}:"
        f"release={plan.glue_comp_release_ms}:knee=8:detection=rms:"
        f"link=average:makeup=3,"
        f"firequalizer=gain_entry='{master_eq}',"
        f"alimiter=level_in=1:level_out=1:limit={plan.limiter_ceiling}:"
        f"attack={plan.limiter_attack_ms}:release={plan.limiter_release_ms}:asc=0,"
        f"dynaudnorm=framelen=500:peak=0.95:maxgain={plan.dynaudnorm_maxgain}[mix]"
    )
    return parts
