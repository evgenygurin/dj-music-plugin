"""Pure builder for the ffmpeg ``filter_complex`` graph.

Ported from render_pipeline.py ``render()`` — string assembly only, no IO.
Each segment i reads ffmpeg input ``[i:a]`` (the runner supplies ``-i`` per
segment, in order). Returns the list of graph statements; the runner joins
them with ';'.
"""

from __future__ import annotations

from app.domain.render.models import RenderPlan


def build_filtergraph(plan: RenderPlan) -> list[str]:
    n = plan.n
    xsplit = plan.xsplit_hz
    bar_s = 4.0 * (60.0 / plan.target_bpm)
    low_x = plan.low_swap_bars * bar_s
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

        parts.append(f"[s{i}]asplit=2[s{i}a][s{i}b]")
        parts.append(f"[s{i}a]lowpass=f={xsplit}[lo{i}]")
        parts.append(f"[s{i}b]highpass=f={xsplit}[hi{i}]")

        fd = min(plan.outro_fade_bars * bar_s, length)
        h: list[str] = []
        if i > 0:
            h.append(f"afade=t=in:curve=qsin:st=0:d={d_in:.3f}")
        if i < n - 1:
            h.append(f"afade=t=out:curve=qsin:st={length - d_out:.3f}:d={d_out:.3f}")
        else:
            h.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[hi{i}]{','.join(h) if h else 'acopy'}[H{i}]")

        lo: list[str] = []
        if i > 0:
            st = max(0.0, d_in / 2 - low_x / 2)
            lo.append(f"afade=t=in:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        if i < n - 1:
            st = length - d_out / 2 - low_x / 2
            lo.append(f"afade=t=out:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        else:
            lo.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[lo{i}]{','.join(lo) if lo else 'acopy'}[Lo{i}]")

        t_ms = int(running_t * 1000)
        parts.append(f"[H{i}][Lo{i}]amix=inputs=2:normalize=0,adelay={t_ms}|{t_ms}[m{i}]")
        mixlabels.append(f"[m{i}]")
        running_t += length - d_out

    parts.append(
        "".join(mixlabels) + f"amix=inputs={n}:normalize=0,"
        f"alimiter=level_in=1:level_out=1:limit={plan.limiter_ceiling}:"
        "attack=5:release=60:asc=1[mix]"
    )
    return parts
