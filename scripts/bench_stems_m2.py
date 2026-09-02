#!/usr/bin/env python3
"""Bench RTF / peak RSS / SDR-proxy для 3-tier стем-рантаймов на M2 8GB.

Замеряет каждый рантайм (mlx → onnx → torch) на каждом треке из
``/tmp/dj_audio/*.mp3`` (по умолчанию) — печатает RTF (elapsed/duration),
пиковый RSS (psutil, опрос 0.1s), и SDR-proxy (10·log10 mixture/residual).

Констрейнты плана:
- ``segment=7.8`` (HTDemucs Transformer hard limit, см. app/config/stems.py)
- ``jobs=0`` на 8GB (см. demucs_runner.py)
- ``percussion`` 2000 Hz high-pass
- кэш ``sha256(path)[:12] / model / stem.flac`` — не меняет схему (раннеры сами кешируют)

Использование::

    uv run python scripts/bench_stems_m2.py
    uv run python scripts/bench_stems_m2.py --track "/tmp/dj_audio/05*.mp3" --runtimes mlx,onnx,torch
    uv run python scripts/bench_stems_m2.py --track /tmp/dj_audio/03*.mp3 --clip 30 --runtimes torch
    uv run python scripts/bench_stems_m2.py --runtimes torch --json-out /tmp/bench.json

Ожидаемо на M2 8GB (3-мин трек, см. plan Task 6):
    mlx  RTF ~0.03 (30× realtime), onnx ~0.10, torch ~0.20, RSS <5 GB, 5 flac/трек.

При отсутствии ``mlx`` / ``onnxruntime`` рантайм помечается ``SKIP`` (fallback
в ``get_runner`` не маскирует реальный RTF — бенч вызывает раннеры напрямую).
"""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import tempfile
import threading
import time
import warnings
from pathlib import Path

import numpy as np

# ── утилы ────────────────────────────────────────────────────────────────


def _get_duration(path: Path) -> float:
    """Длительность аудио в секундах (librosa → ffprobe → fallback 0)."""
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=ResourceWarning)
            import librosa

            y, sr = librosa.load(str(path), sr=44100, mono=False)
            y2 = np.atleast_2d(y)
            n = y2.shape[1] if y2.ndim == 2 else y2.shape[0]
            if sr and n:
                return float(n) / float(sr)
    except Exception:
        pass
    # ffprobe fallback
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0:
            return float(out.stdout.strip())
    except Exception:
        pass
    return 0.0


def _trim_clip(src: Path, seconds: float) -> Path:
    """Сделать временный clip первые ``seconds`` секунд через ffmpeg."""
    tmp = Path(tempfile.gettempdir()) / f"bench_clip_{seconds:.0f}_{src.stem}.mp3"
    # переписываем только если исходник новее
    if tmp.exists():
        try:
            if tmp.stat().st_mtime > src.stat().st_mtime:
                return tmp
        except Exception:
            pass
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-t",
            str(seconds),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(tmp),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
    )
    return tmp


def _rss_monitor(proc_psutil: object, stop: threading.Event, out: dict[str, float]) -> None:
    """Опрашивает RSS каждые 0.1s, пишет пик в ``out['peak']``."""
    try:
        import psutil as _psutil  # type: ignore
    except Exception:
        return
    peak = out.get("peak", 0.0)
    proc = _psutil.Process()
    # также следим за дочерними (demucs форк с jobs>0, хотя на 8GB jobs=0)
    while not stop.is_set():
        try:
            rss = float(proc.memory_info().rss)
            try:
                for child in proc.children(recursive=True):
                    try:
                        rss += float(child.memory_info().rss)
                    except Exception:
                        pass
            except Exception:
                pass
            if rss > peak:
                peak = rss
                out["peak"] = peak
        except Exception:
            pass
        stop.wait(0.1)


def _sdr_proxy(mixture_path: Path, stems: dict[str, Path]) -> float | None:
    """SDR-proxy: 10·log10(||mix||² / ||mix - sum(stems)||²).

    ``sum(stems)`` должен ≈ ``mix`` при идеальном разделении, остаток мал →
    SDR высокий. Возвращает ``None`` если не удалось загрузить аудио.
    """
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            warnings.filterwarnings("ignore", category=FutureWarning)
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=ResourceWarning)
            warnings.filterwarnings("ignore", category=UserWarning, message="PySoundFile failed.*")
            warnings.filterwarnings(
                "ignore", category=FutureWarning, message=".*__audioread_load.*"
            )
            import librosa

            mix, sr = librosa.load(str(mixture_path), sr=44100, mono=False)
            mix2 = np.atleast_2d(mix).astype(np.float64)
            # стерео → моно для энергии (сумма каналов)
            if mix2.shape[0] == 2:
                mix_mono = mix2.mean(axis=0)
            else:
                mix_mono = mix2[0]

            # сумма стемов
            acc: np.ndarray | None = None
            for p in stems.values():
                if not p.exists():
                    continue
                y, _ = librosa.load(str(p), sr=sr, mono=False)
                y2 = np.atleast_2d(y).astype(np.float64)
                if y2.shape[0] == 2:
                    y_mono = y2.mean(axis=0)
                else:
                    y_mono = y2[0]
                # выравниваем длину к mix_mono
                if len(y_mono) > len(mix_mono):
                    y_mono = y_mono[: len(mix_mono)]
                elif len(y_mono) < len(mix_mono):
                    y_mono = np.pad(y_mono, (0, len(mix_mono) - len(y_mono)))
                if acc is None:
                    acc = y_mono
                else:
                    # выравниваем acc тоже
                    if len(acc) != len(y_mono):
                        m = min(len(acc), len(y_mono))
                        acc = acc[:m]
                        y_mono = y_mono[:m]
                        mix_mono = mix_mono[:m]
                    acc = acc + y_mono

            if acc is None:
                return None
            # выравниваем mix к acc
            m = min(len(mix_mono), len(acc))
            mix_mono = mix_mono[:m]
            acc = acc[:m]
            residual = mix_mono - acc
            sig_pow = float(np.mean(mix_mono**2))
            res_pow = float(np.mean(residual**2))
            if res_pow < 1e-12 or sig_pow < 1e-12:
                return None
            return float(10.0 * np.log10(sig_pow / res_pow))
    except Exception:
        return None


def _resolve_tracks(patterns: list[str]) -> list[Path]:
    tracks: list[Path] = []
    for pat in patterns:
        p = Path(pat)
        # glob с wildcard
        if "*" in pat or "?" in pat or "[" in pat:
            import glob as _glob

            for g in _glob.glob(pat):
                gp = Path(g)
                if gp.is_file() and gp.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a"):
                    tracks.append(gp)
        elif p.is_file():
            tracks.append(p)
        elif p.is_dir():
            for ext in (".mp3", ".wav", ".flac", ".m4a"):
                tracks.extend(p.glob(f"*{ext}"))
                tracks.extend(p.glob(f"*{ext.upper()}"))
    # дедуп по resolve, сортировка
    seen: set[str] = set()
    uniq: list[Path] = []
    for t in sorted(tracks):
        key = str(t.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(t)
    return uniq


def _get_runner_direct(runtime: str):  # type: ignore[no-untyped-def]
    """Вернуть раннер напрямую (без fallback) — для честного RTF."""
    if runtime == "mlx":
        try:
            from app.audio.deep.demucs_mlx_runner import mlx_separate

            return mlx_separate, "mlx_separate"
        except Exception as exc:
            return None, f"mlx not available: {exc}"
    if runtime == "onnx":
        try:
            from app.audio.deep.demucs_onnx_runner import onnx_separate

            # onnx_separate по умолчанию vocals-only — для бенча нужен full 5
            def _onnx_full(
                input_path: Path, cache_root: Path, *, model: str | None = None, flac: bool = True
            ):  # type: ignore[no-untyped-def]
                return onnx_separate(
                    input_path,
                    cache_root,
                    stems=("vocals", "drums", "bass", "harmonic", "percussion"),
                    model=model,
                    flac=flac,
                )

            _onnx_full.__name__ = "onnx_separate"
            return _onnx_full, "onnx_separate"
        except Exception as exc:
            return None, f"onnx not available: {exc}"
    if runtime in ("torch", "cpu"):
        try:
            from app.audio.deep.demucs_runner import run_demucs

            return run_demucs, "run_demucs"
        except Exception as exc:
            return None, f"torch runner not available: {exc}"
    return None, f"unknown runtime {runtime!r}"


# ── CLI ────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bench RTF/RSS/SDR-proxy для 3-tier стем-рантаймов (mlx/onnx/torch) на M2 8GB."
    )
    p.add_argument(
        "--track",
        action="append",
        dest="tracks",
        default=[],
        help="Путь или glob к треку (можно несколько --track). Default: /tmp/dj_audio/*.mp3",
    )
    p.add_argument(
        "--runtimes",
        default="mlx,onnx,torch",
        help="Список рантаймов через запятую (default: mlx,onnx,torch).",
    )
    p.add_argument(
        "--cache-root",
        default="generated-sets/bench",
        help="Корень кэша стемов (default: generated-sets/bench). Схема кэша не меняется: sha12/model/stem.flac",
    )
    p.add_argument(
        "--clip",
        type=float,
        default=None,
        help="Обрезать каждый трек до N секунд (ffmpeg) перед бенчем — для 30s vs 3min сравнения.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Имя модели для кэша (default: htdemucs / htdemucs_fp16 у onnx).",
    )
    p.add_argument(
        "--json-out",
        default=None,
        help="Записать результаты в JSON файл.",
    )
    p.add_argument(
        "--flac",
        action="store_true",
        default=True,
        help="Писать flac (default: yes).",
    )
    p.add_argument(
        "--no-flac",
        dest="flac",
        action="store_false",
        help="Писать wav вместо flac.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    runtimes = [r.strip().lower() for r in args.runtimes.split(",") if r.strip()]
    allowed = {"mlx", "onnx", "torch", "cpu"}
    runtimes = [r for r in runtimes if r in allowed]
    if not runtimes:
        print("No valid runtimes (choose from mlx,onnx,torch,cpu)", file=sys.stderr)
        return 2

    track_patterns: list[str] = args.tracks if args.tracks else ["/tmp/dj_audio/*.mp3"]
    tracks = _resolve_tracks(track_patterns)
    if not tracks:
        print(f"No tracks found for patterns {track_patterns}", file=sys.stderr)
        # всё равно печатаем заголовок чтобы CI не падал без аудио
        tracks = []

    # psutil опционален — без него RSS = n/a но бенч идёт
    try:
        import psutil  # type: ignore
    except Exception:
        psutil = None  # type: ignore[assignment]

    cache_root = Path(args.cache_root)

    print("=" * 84)
    print("BENCH STEMS M2 8GB — RTF / peak RSS / SDR-proxy")
    print("=" * 84)
    print(f"Runtimes : {', '.join(runtimes)}")
    print(
        f"Tracks   : {len(tracks)}  " + (", ".join(p.name for p in tracks) if tracks else "(none)")
    )
    print(f"Cache    : {cache_root}  (sha12/model/stem.flac, не менять схему)")
    print("Segment  : 7.8s  overlap 0.25  jobs 0 (M2 8GB constraint)")
    print("Percussion split: 2000 Hz high-pass")
    if args.clip:
        print(f"Clip     : {args.clip:.0f}s (ffmpeg -t)")
    print("-" * 84)

    # header
    hdr = f"{'track':30s} {'runtime':8s} {'dur':>7s} {'elapsed':>8s} {'RTF':>7s} {'RSS peak':>9s} {'RSS delta':>9s} {'SDRpx':>7s} {'stems':>6s} status"
    print(hdr)
    print("-" * 84)

    results: list[dict[str, object]] = []

    for orig_track in tracks:
        track = orig_track
        # clip если запрошен
        if args.clip and args.clip > 0:
            try:
                track = _trim_clip(orig_track, float(args.clip))
                print(f"# clip {orig_track.name} -> {track.name} ({args.clip:.0f}s)")
            except Exception as exc:
                print(f"# clip failed for {orig_track.name}: {exc} — bench full track")

        duration = _get_duration(track)
        # fallback если либроса не дала длительность — пробуем file_size heuristic
        if duration <= 0:
            try:
                duration = float(track.stat().st_size) / 200_000.0  # ~200KB/s mp3
            except Exception:
                duration = 180.0
        dur_str = f"{duration:.1f}s" if duration else "n/a"

        for runtime in runtimes:
            runner, runner_name = _get_runner_direct(runtime)
            if runner is None:
                status = f"SKIP ({runner_name})"
                print(
                    f"{track.name:30s} {runtime:8s} {dur_str:>7s} {'-':>8s} {'-':>7s} {'-':>9s} {'-':>9s} {'-':>7s} {'-':>6s} {status}"
                )
                results.append(
                    {
                        "track": str(orig_track),
                        "clip_track": str(track),
                        "runtime": runtime,
                        "duration": duration,
                        "elapsed": None,
                        "rtf": None,
                        "rss_peak_mb": None,
                        "rss_delta_mb": None,
                        "sdr_proxy_db": None,
                        "stems": 0,
                        "status": status,
                    }
                )
                continue

            # перитрековый кэш: generated-sets/bench/{runtime}/{hash}/...
            # но раннер сам делает sha12 — достаточно общего cache_root
            per_runtime_cache = cache_root / runtime
            # уникальный subdir чтобы разные рантаймы не делили кэш (честный замер)
            # сам раннер всё равно ключует по sha12, так что изоляции достаточно
            per_runtime_cache.mkdir(parents=True, exist_ok=True)

            # RSS монитор
            rss_before = 0.0
            rss_peak_holder: dict[str, float] = {}
            stop_evt = threading.Event()
            mon_thread: threading.Thread | None = None
            if psutil is not None:
                try:
                    import psutil as _psutil  # type: ignore

                    rss_before = float(_psutil.Process().memory_info().rss)
                    rss_peak_holder["peak"] = rss_before
                    mon_thread = threading.Thread(
                        target=_rss_monitor, args=(_psutil, stop_evt, rss_peak_holder), daemon=True
                    )
                    mon_thread.start()
                except Exception:
                    rss_before = 0.0

            t0 = time.perf_counter()
            stems: dict[str, Path] | None = None
            err: str | None = None
            try:
                # синхронный раннер — вызываем напрямую (resolver вызывает через to_thread)
                stems = runner(track, per_runtime_cache, model=args.model, flac=args.flac)  # type: ignore[call-arg]
            except Exception as exc:
                msg = str(exc)
                # mlx/onnx не установлены — показываем SKIP вместо FAIL (честный RTF)
                if "mlx not installed" in msg or "onnxruntime" in msg:
                    elapsed = time.perf_counter() - t0
                    if mon_thread is not None:
                        stop_evt.set()
                        mon_thread.join(timeout=1.0)
                    status = f"SKIP ({type(exc).__name__}: {msg})"
                    print(
                        f"{track.name:30s} {runtime:8s} {dur_str:>7s} {'-':>8s} {'-':>7s} {'-':>9s} {'-':>9s} {'-':>7s} {'-':>6s} {status}"
                    )
                    results.append(
                        {
                            "track": str(orig_track),
                            "clip_track": str(track),
                            "runtime": runtime,
                            "runner": runner_name,
                            "duration": duration,
                            "elapsed": None,
                            "rtf": None,
                            "rss_peak_mb": None,
                            "rss_delta_mb": None,
                            "sdr_proxy_db": None,
                            "stems": 0,
                            "flac_count": 0,
                            "status": status,
                        }
                    )
                    continue
                err = f"{type(exc).__name__}: {exc}"
                stems = None
            elapsed = time.perf_counter() - t0

            if mon_thread is not None:
                stop_evt.set()
                mon_thread.join(timeout=1.0)

            rss_peak = rss_peak_holder.get("peak", rss_before)
            rss_delta = rss_peak - rss_before if rss_before else 0.0
            rss_peak_mb = rss_peak / (1024 * 1024) if rss_peak else None
            rss_delta_mb = rss_delta / (1024 * 1024) if rss_delta else None

            rtf = (elapsed / duration) if duration > 0 else None

            # SDR-proxy — только если стемы создались
            sdr: float | None = None
            stem_count = 0
            flac_count = 0
            if stems:
                stem_count = len(stems)
                # считаем flac на диске (5 ожидаем)
                try:
                    flac_count = sum(1 for p in stems.values() if Path(p).exists())
                except Exception:
                    flac_count = stem_count
                sdr = _sdr_proxy(track, stems)

            status = (
                "OK" if err is None and stem_count else f"FAIL: {err}" if err else "FAIL: no stems"
            )

            # gc между прогонами (M2 8GB: free unified memory)
            try:
                gc.collect()
                try:
                    import torch  # type: ignore

                    if torch.backends.mps.is_available():
                        torch.mps.empty_cache()  # type: ignore[attr-defined]
                except Exception:
                    pass
            except Exception:
                pass

            rtf_s = f"{rtf:.3f}" if rtf is not None else "-"
            rss_s = f"{rss_peak_mb:.0f}MB" if rss_peak_mb else "-"
            delta_s = f"+{rss_delta_mb:.0f}MB" if rss_delta_mb else "-"
            sdr_s = f"{sdr:.1f}dB" if sdr is not None else "-"
            elapsed_s = f"{elapsed:.1f}s"
            stems_s = f"{flac_count}/5" if stems else "-"

            print(
                f"{track.name:30s} {runtime:8s} {dur_str:>7s} {elapsed_s:>8s} {rtf_s:>7s} {rss_s:>9s} {delta_s:>9s} {sdr_s:>7s} {stems_s:>6s} {status}"
            )

            results.append(
                {
                    "track": str(orig_track),
                    "clip_track": str(track),
                    "runtime": runtime,
                    "runner": runner_name,
                    "duration": duration,
                    "elapsed": elapsed,
                    "rtf": rtf,
                    "rss_peak_mb": rss_peak_mb,
                    "rss_delta_mb": rss_delta_mb,
                    "sdr_proxy_db": sdr,
                    "stems": stem_count,
                    "flac_count": flac_count,
                    "status": status,
                }
            )

    print("-" * 84)
    # сводка
    if results:
        ok = [
            r
            for r in results
            if isinstance(r.get("status"), str) and str(r["status"]).startswith("OK")
        ]
        print(
            f"Done: {len(ok)}/{len(results)} OK  |  RSS <5GB target, RTF mlx ~0.03 onnx ~0.10 torch ~0.20"
        )
        # подсказка по проверке 5 flac
        print(
            f"Verify: ls {cache_root}/*/stems/*/*/*.flac 2>/dev/null | wc -l  → 5 per track (или ls {cache_root}/{{mlx,onnx,torch}}/*/*/*/*.flac | wc -l)"
        )

    if args.json_out:
        out_p = Path(args.json_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"JSON written to {out_p}")

    # exit code: 0 если хоть один OK или все SKIP (нет моделей), 1 если все FAIL
    has_ok = any(str(r.get("status", "")).startswith("OK") for r in results)
    has_skip_only = all("SKIP" in str(r.get("status", "")) for r in results) if results else True
    if not tracks:
        return 0
    if has_ok or has_skip_only:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
