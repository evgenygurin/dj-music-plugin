from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.audio.render.diagnostics import diagnose_mix


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "generated-sets" / "render" / "v173"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEGMENTS = {
    "intro": ROOT / "generated-sets" / "suno-assets" / "buckshot-1114-v173-pack" / "1114-v173-intro-ritual [8a1a4a6d-82ee-4c92-aec9-0c60e12343f5].mp3",
    "pressure": ROOT / "generated-sets" / "suno-assets" / "buckshot-1114-v173-pack" / "1114-v173-pressure-bridge-surrounded-overdose [8d97a224-dfe4-47dd-bf14-0757c620dee4].mp3",
    "surrounded": Path("/tmp/dj_audio/09. Surrounded [bandcamp-1223419985].mp3"),
    "overdose": Path("/tmp/dj_audio/11. Overdose Casino [bandcamp-2606914609].mp3"),
    "general": Path("/tmp/dj_audio/02. General Release [146071230].mp3"),
    "before": Path("/tmp/dj_audio/03. Before Every Load [146071231].mp3"),
    "blank": Path("/tmp/dj_audio/01. Blank Shell [146071227].mp3"),
    "texture": ROOT / "generated-sets" / "suno-assets" / "buckshot-1114-v173-pack" / "1114-v173-blank-shell-texture-bed [7006a570-9ef9-4c44-bf01-23c06f6e783e].mp3",
    "bridge": ROOT / "generated-sets" / "suno-assets" / "buckshot-1114-v173-pack" / "1114-v173-bridge-blank-shell-socket-calibration [61206f20-40ec-45fd-bd2c-5f9bc02c62ed].mp3",
    "socket": Path("/tmp/dj_audio/04. Socket Calibration [146071233].mp3"),
    "outro": ROOT / "generated-sets" / "suno-assets" / "buckshot-1114-v173-pack" / "1114-v173-socket-outro-comedown [5ca99134-c771-4dc5-ab82-7d062bdc82cf].mp3",
}


def candidate_space() -> list[dict[str, object]]:
    out = []
    idx = 1
    for main_xfade in (4, 6, 8, 10):
        for bridge_xfade in (4, 6):
            for use_pressure in (False, True):
                for use_texture in (False, True):
                    if len(out) >= 20:
                        return out
                    out.append(
                        {
                            "id": idx,
                            "main_xfade": float(main_xfade),
                            "bridge_xfade": float(bridge_xfade),
                            "intro_vol": -6.0 if main_xfade <= 6 else -8.0,
                            "pressure_on": use_pressure,
                            "pressure_vol": -12.0 if use_pressure else None,
                            "texture_on": use_texture,
                            "texture_vol": -14.0 if use_texture else None,
                            "bridge_vol": -9.0 if bridge_xfade == 6 else -10.5,
                            "outro_vol": -10.0 if main_xfade <= 6 else -12.0,
                        }
                    )
                    idx += 1
    return out


def build_filter(cfg: dict[str, object]) -> str:
    parts: list[str] = []
    pressure_idx = 9 if cfg["pressure_on"] else None
    texture_idx = 9 + (1 if cfg["pressure_on"] else 0) if cfg["texture_on"] else None
    # ordered inputs
    parts.append("[0:a]atrim=start=0:duration=45,asetpts=PTS-STARTPTS,volume=-6dB[s0]")
    parts.append("[1:a]atrim=start=0:duration=95,asetpts=PTS-STARTPTS,volume=-1.2dB[s1]")
    parts.append("[2:a]atrim=start=0:duration=85,asetpts=PTS-STARTPTS,volume=-1.0dB[s2]")
    parts.append("[3:a]atrim=start=0:duration=75,asetpts=PTS-STARTPTS,volume=-1.8dB[s3]")
    parts.append("[4:a]atrim=start=0:duration=95,asetpts=PTS-STARTPTS,volume=-1.0dB[s4]")
    parts.append("[5:a]atrim=start=0:duration=60,asetpts=PTS-STARTPTS,volume=-2.0dB[s5]")
    parts.append("[6:a]atrim=start=20:duration=52,asetpts=PTS-STARTPTS,volume=-1.5dB[s6]")
    parts.append("[7:a]atrim=start=8:duration=105,asetpts=PTS-STARTPTS,volume=-1.5dB[s7]")
    parts.append("[8:a]atrim=start=18:duration=58,asetpts=PTS-STARTPTS,volume=-8dB[s8]")

    mx = float(cfg["main_xfade"])
    bx = float(cfg["bridge_xfade"])
    parts.append(f"[s0][s1]acrossfade=d={mx}:c1=tri:c2=tri[x1]")
    if cfg["pressure_on"]:
        parts.append(f"[{pressure_idx}:a]atrim=start=0:duration=36,asetpts=PTS-STARTPTS,volume=-12dB[p]")
        parts.append(f"[x1][p]acrossfade=d=4:c1=tri:c2=tri[x1p]")
        prev = "x1p"
    else:
        prev = "x1"
    parts.append(f"[{prev}][s2]acrossfade=d={mx}:c1=tri:c2=tri[x2]")
    parts.append(f"[x2][s3]acrossfade=d={mx}:c1=tri:c2=tri[x3]")
    parts.append(f"[x3][s4]acrossfade=d={mx}:c1=tri:c2=tri[x4]")
    if cfg["texture_on"]:
        parts.append(f"[{texture_idx}:a]atrim=start=30:duration=40,asetpts=PTS-STARTPTS,volume=-14dB[t]")
        parts.append("[s5][t]amix=inputs=2:normalize=0[s5m]")
        blank = "s5m"
    else:
        blank = "s5"
    parts.append(f"[x4][{blank}]acrossfade=d={mx}:c1=tri:c2=tri[x5]")
    parts.append(f"[x5][s6]acrossfade=d={bx}:c1=tri:c2=tri[x6]")
    parts.append(f"[x6][s7]acrossfade=d={bx}:c1=tri:c2=tri[x7]")
    parts.append(f"[x7][s8]acrossfade=d={mx}:c1=tri:c2=tri,acompressor=threshold=-18dB:ratio=2:attack=10:release=120:knee=6:detection=rms:link=average:makeup=1,alimiter=level_in=1:level_out=1:limit=0.85:attack=10:release=30:asc=0[mix]")
    return ";".join(parts)


def render_candidate(cfg: dict[str, object]) -> Path:
    out = OUT_DIR / f"MIX-cycle-{int(cfg['id']):02d}.mp3"
    inputs = [
        str(SEGMENTS["intro"]),
        str(SEGMENTS["surrounded"]),
        str(SEGMENTS["overdose"]),
        str(SEGMENTS["general"]),
        str(SEGMENTS["before"]),
        str(SEGMENTS["blank"]),
        str(SEGMENTS["bridge"]),
        str(SEGMENTS["socket"]),
        str(SEGMENTS["outro"]),
    ]
    if cfg["pressure_on"]:
        inputs.append(str(SEGMENTS["pressure"]))
    if cfg["texture_on"]:
        inputs.append(str(SEGMENTS["texture"]))
    cmd = ["ffmpeg", "-y"]
    for p in inputs:
        cmd += ["-i", p]
    cmd += [
        "-filter_complex",
        build_filter(cfg),
        "-map",
        "[mix]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-q:a",
        "0",
        str(out),
    ]
    subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
    return out


def score_report(rep) -> tuple[float, dict[str, int]]:
    counts = {"dropout": 0, "phase": 0, "entry": 0, "collapse": 0, "bass": 0, "jump": 0}
    for w in rep.windows:
        for t in w.tags:
            if "DROPOUT" in t:
                counts["dropout"] += 1
            if "PHASE" in t:
                counts["phase"] += 1
            if "ENTRY-SHOCK" in t:
                counts["entry"] += 1
            if "LOW-END-COLLAPSE" in t:
                counts["collapse"] += 1
            if "bass-thin" in t:
                counts["bass"] += 1
            if "LEVEL-JUMP" in t:
                counts["jump"] += 1
    score = (
        counts["dropout"] * 8
        + counts["phase"] * 6
        + counts["entry"] * 7
        + counts["collapse"] * 7
        + counts["bass"] * 3
        + counts["jump"] * 2
        + max(0.0, rep.flagged - 6) * 1.5
    )
    return score, counts


def main() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg missing")
    from app.audio.render.diagnostics import diagnose_mix

    results = []
    for cfg in candidate_space():
        out = render_candidate(cfg)
        rep = diagnose_mix(str(out))
        score, counts = score_report(rep)
        results.append(
            {
                "config": cfg,
                "file": str(out),
                "score": round(score, 2),
                "flagged": rep.flagged,
                "overall_rms_db": round(rep.overall_rms_db, 2),
                "counts": counts,
            }
        )
        print(f"cycle {cfg['id']:02d}: score={score:.2f} flagged={rep.flagged} counts={counts}")

    results.sort(key=lambda x: (x["score"], x["flagged"]))
    best = results[0]
    (OUT_DIR / "search-20-report.json").write_text(json.dumps({"best": best, "results": results}, indent=2))
    print("BEST", json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
