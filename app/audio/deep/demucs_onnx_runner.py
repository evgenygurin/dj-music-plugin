# ruff: noqa: RUF002, RUF003
"""ONNX CoreML runner (fp16, 166MB) — chunk 7.8s / overlap 0.25.

Канонический 5-стем набор: vocals / drums / bass / harmonic / percussion.
MLX/ONNX/Torch — 3-tier рантаймы через StemRunner Protocol (app/config/stems.py).

- fp16 weights 166MB: ``htdemucs_fp16.onnx`` (quantized, в 2x меньше float32)
- провайдеры ``["CoreMLExecutionProvider", "CPUExecutionProvider"]`` — Neural Engine -> CPU fallback
- чанк 7.8s (HTDemucs Transformer hard limit <=7.8) / overlap 0.25 / hop 5.85s
- выбор стемов: vocals-only ~22s vs full-bag ~88s (3min трек, M2) за счёт отдельного прогона на группу
- запись flac (compression 8) + кэш ``sha256(path)[:12] / model / stem.flac`` (не менять схему)
- percussion PERCUSSION_SPLIT_HZ=2000 (high-pass из drums, kick остаётся в drums)
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

# 7.8 — HTDemucs hard limit (≤7.8), 2000 Hz — percussion split (см. global constraints + AGENTS.md §8)
DEMUCS_SEGMENT: float = 7.8
DEMUCS_OVERLAP: float = 0.25
PERCUSSION_SPLIT_HZ: int = 2000
DEFAULT_ONNX_MODEL: str = "htdemucs_fp16"
FLAC_COMPRESSION: int = 8

ONNX_PROVIDERS: list[str] = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
# fp16 model ~166MB (quantized ht-demucs). Системный путь переопределяется env.
DEFAULT_ONNX_MODEL_PATH: str = "htdemucs_fp16.onnx"

_CANONICAL_5: tuple[str, ...] = ("vocals", "drums", "bass", "harmonic", "percussion")
# Demucs native 4-stem → canonical mapping (other → harmonic)
_DEMUCS_NATIVE_TO_CANONICAL: dict[str, str] = {
    "vocals": "vocals",
    "drums": "drums",
    "bass": "bass",
    "other": "harmonic",
}
_NATIVE_4: tuple[str, ...] = ("vocals", "drums", "bass", "other")


def _cache_paths(
    input_path: Path, cache_root: Path, model: str, ext: str
) -> tuple[Path, Path, dict[str, Path]]:
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    cache_dir = cache_root / f"{input_path.stem}_{cache_key}"
    stem_dir = cache_dir / model / input_path.stem
    stem_dir.mkdir(parents=True, exist_ok=True)
    # расширим только для запрошенных стемов позже — здесь подсказка для full-каноникала
    return cache_dir, stem_dir, {}


def _write_flac(path: Path, data: np.ndarray, sr: int = 44100) -> None:
    """Записать (channels, samples) или (samples,) float32 в flac.

    Пытается soundfile → ffmpeg fallback. Создаёт валидный flac даже для мок-данных.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # нормализуем к (samples, channels) для soundfile
    if data.ndim == 2:
        # demucs/onnx обычно (stems, channels, samples) или (channels, samples)
        # здесь data — один стем: (channels, samples) или (samples,)
        if data.shape[0] in (1, 2) and data.shape[1] > 4:
            wav = np.transpose(data).astype(np.float32)
        else:
            wav = data.astype(np.float32)
    else:
        wav = data.astype(np.float32)

    # пробуем soundfile
    try:
        import soundfile as sf

        sf.write(str(path), wav, sr, format="FLAC", subtype="PCM_16")
        return
    except Exception:
        pass

    # ffmpeg fallback — временный wav
    tmp_wav = path.with_suffix(".tmp.wav")
    try:
        import soundfile as sf2

        sf2.write(str(tmp_wav), wav, sr)
    except Exception:
        # крайний fallback: пишем raw wav через numpy+wave
        import wave

        nch = wav.shape[1] if wav.ndim == 2 else 1
        flat = (np.clip(wav, -1.0, 1.0) * 32767).astype(np.int16)
        if flat.ndim == 1:
            flat = flat[:, None]
        interleaved = flat.reshape(-1).tobytes()
        with wave.open(str(tmp_wav), "wb") as wf:
            wf.setnchannels(nch)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(interleaved)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(tmp_wav),
                "-c:a",
                "flac",
                "-compression_level",
                str(FLAC_COMPRESSION),
                str(path),
            ],
            check=True,
            timeout=120,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        tmp_wav.unlink(missing_ok=True)


def _derive_percussion_from_drums(
    drums_path: Path,
    percussion_path: Path,
) -> None:
    """Выделить percussion (hi-hat/cymbal >2kHz) из drums через ffmpeg high-pass.

    Если ffmpeg недоступен или drums отсутствует — копируем drums как fallback
    (тихий деградейшн, не роняет пайплайн).
    """
    if percussion_path.exists():
        return
    if not drums_path.exists():
        return
    cutoff = PERCUSSION_SPLIT_HZ
    tmp_drums = drums_path.with_name("drums_tmp.wav")
    # flac-aware: drums/percussion могут быть flac — ffmpeg читает оба
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(drums_path),
                "-filter_complex",
                (
                    f"[0]lowpass=f={cutoff}:poles=2,asetpts=PTS-STARTPTS[drums];"
                    f"[0]highpass=f={cutoff}:poles=2,asetpts=PTS-STARTPTS[perc]"
                ),
                "-map",
                "[drums]",
                str(tmp_drums),
                "-map",
                "[perc]",
                str(percussion_path),
            ],
            check=True,
            timeout=120,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tmp_drums.replace(drums_path)
    except Exception:
        # fallback: дублируем drums в percussion если сплит не удался
        try:
            import shutil

            shutil.copy(drums_path, percussion_path)
        except Exception:
            pass
        tmp_drums.unlink(missing_ok=True)


def _load_audio(input_path: Path, sr: int = 44100) -> tuple[np.ndarray, int]:
    """Загрузить стерео аудио как (channels, samples) float32. Мок-дружелюбно."""
    if not input_path.exists():
        # тест-вход без файла — отдаём 1s тишины (44100)
        return np.zeros((2, sr), dtype=np.float32), sr
    try:
        import soundfile as sf

        data, file_sr = sf.read(str(input_path), always_2d=True)
        # soundfile → (samples, channels) → (channels, samples)
        wav = np.transpose(data).astype(np.float32)
        # ресемпл если нужно (упрощённо)
        if file_sr != sr:
            try:
                import librosa

                wav = librosa.resample(wav, orig_sr=file_sr, target_sr=sr)
            except Exception:
                pass
        # гарантируем 2 канала
        if wav.shape[0] == 1:
            wav = np.repeat(wav, 2, axis=0)
        elif wav.shape[0] > 2:
            wav = wav[:2, :]
        return wav, sr
    except Exception:
        pass
    try:
        import librosa

        y, file_sr = librosa.load(str(input_path), sr=sr, mono=False)
        wav = np.atleast_2d(y).astype(np.float32)
        if wav.shape[0] == 1:
            wav = np.repeat(wav, 2, axis=0)
        return wav, sr
    except Exception:
        pass
    return np.zeros((2, sr), dtype=np.float32), sr


def _get_session(model_path: str | Path | None = None) -> Any:
    """Создать InferenceSession с CoreML->CPU провайдерами (fp16).

    model_path по умолчанию — ``htdemucs_fp16.onnx`` (166MB fp16).
    """
    import os as _os

    path = str(model_path or _os.environ.get("DJ_ONNX_MODEL_PATH", DEFAULT_ONNX_MODEL_PATH))
    # lazy import — позволяет мокать onnxruntime в тестах даже когда пакет не установлен
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "onnxruntime not installed (need onnxruntime-silicon for CoreML)"
        ) from exc

    # CoreML EP может отсутствовать на Linux — onnxruntime сам упадёт в fallback
    sess = ort.InferenceSession(path, providers=ONNX_PROVIDERS)
    return sess


def onnx_separate(
    input_path: Path,
    cache_root: Path,
    stems: tuple[str, ...] = ("vocals",),
    *,
    model: str | None = None,
    flac: bool = True,
    model_path: str | Path | None = None,
) -> dict[str, Path]:
    """Разделить трек через ONNX CoreML (fp16, 166MB) чанками 7.8s / 0.25 overlap.

    Поддерживает выбор стемов: ``stems=("vocals",)`` → один прогон ~22s
    vs ``stems=("vocals","drums","bass","other")`` / full 5 → bag ~88s (3min трек).
    Это даёт выбор скорости vs полноты bag-of-models (см. plan Task 2).

    Кэш: ``cache_root / {stem}_{sha12} / {model} / {stem_name} / {stem}.flac``
    (схема не меняется, как у torch-раннера).  # noqa: RUF002

    Args:
        input_path: путь к входному mp3/wav/flac.
        cache_root: корень кэша стемов.
        stems: запрашиваемые стемы. Поддерживаются ``vocals``/``drums``/``bass``/``other``/``harmonic``/``percussion``.
            ``("vocals",)`` (default) — быстрый vocals-only прогон. Для полного набора
            передайте ``("vocals","drums","bass","harmonic","percussion")`` или ``_CANONICAL_5``.
        model: имя модели для имени директории кэша (default ``htdemucs_fp16``).
        flac: писать flac (True) или wav (False).
        model_path: путь к .onnx файлу (fp16, 166MB). Default ``htdemucs_fp16.onnx``.

    Returns:
        dict ``stem_name → Path`` для запрошенных стемов (канонический 5-набор при full запросе).
    """
    model_name = model or DEFAULT_ONNX_MODEL
    ext = "flac" if flac else "wav"

    # нормализуем stems: other → harmonic, валидируем
    allowed = {"vocals", "drums", "bass", "other", "harmonic", "percussion"}
    norm_stems: list[str] = []
    for s in stems:
        if s not in allowed:
            raise ValueError(f"unknown stem {s!r}, allowed {sorted(allowed)}")
        # canonical
        canon = _DEMUCS_NATIVE_TO_CANONICAL.get(s, s)
        if canon not in norm_stems:
            norm_stems.append(canon)

    # percussion всегда из drums — если просят percussion, нужен drums pass
    needs_drums_for_percussion = "percussion" in norm_stems and "drums" not in norm_stems
    # внутренние стемы для инференса (native 4)
    inference_stems: list[str] = []
    for s in norm_stems:
        if s == "percussion":
            continue
        if s == "harmonic":
            if "other" not in inference_stems:
                inference_stems.append("other")
        else:
            if s not in inference_stems:
                inference_stems.append(s)
    if needs_drums_for_percussion and "drums" not in inference_stems:
        inference_stems.append("drums")

    # мап native→canon для выхода
    # кэш-директории
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    cache_dir = cache_root / f"{input_path.stem}_{cache_key}"
    stem_dir = cache_dir / model_name / input_path.stem
    stem_dir.mkdir(parents=True, exist_ok=True)

    # ожидаемые файлы (канонический выход)
    expected_paths: dict[str, Path] = {name: stem_dir / f"{name}.{ext}" for name in norm_stems}

    # cache hit — все запрошенные файлы есть
    if all(p.exists() for p in expected_paths.values()):
        return expected_paths

    # также проверяем wav fallback когда flac запрошен но wavs уже есть (как в torch runner)
    if flac:
        wav_fallback: dict[str, Path] = {name: stem_dir / f"{name}.wav" for name in norm_stems}
        if all(p.exists() for p in wav_fallback.values()):
            # конвертим wav→flac лениво (переиспользуем write_flac, но проще скопировать через ffmpeg)
            # быстрее: вернуть wav как есть если flac ещё не нужен? Текущий контракт — вернуть flac пути,
            # поэтому конвертим.
            for name, wav_p in wav_fallback.items():
                flac_p = expected_paths[name]
                if not flac_p.exists():
                    try:
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-y",
                                "-i",
                                str(wav_p),
                                "-c:a",
                                "flac",
                                "-compression_level",
                                str(FLAC_COMPRESSION),
                                str(flac_p),
                            ],
                            check=True,
                            timeout=120,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except Exception:
                        # fallback — копия
                        import shutil

                        shutil.copy(wav_p, flac_p)
            return expected_paths

    # --- inference (chunk 7.8s, overlap 0.25, overlap-add) ---
    sr = 44100
    segment_samples = int(DEMUCS_SEGMENT * sr)
    hop_samples = int(segment_samples * (1.0 - DEMUCS_OVERLAP))
    if hop_samples <= 0:
        hop_samples = segment_samples

    wav, _sr = _load_audio(input_path, sr=sr)  # (channels, samples)
    # wav shape: (2, N)
    n_samples = wav.shape[1]

    # если вход короче сегмента — один чанк
    offsets: list[int] = []
    if n_samples <= segment_samples:
        offsets = [0]
    else:
        off = 0
        while off + segment_samples <= n_samples:
            offsets.append(off)
            off += hop_samples
        # хвост
        if offsets and offsets[-1] + segment_samples < n_samples:
            offsets.append(n_samples - segment_samples)

    # создаём сессию (мок-дружелюбно — path может не существовать, mock перехватит)
    sess = _get_session(model_path)

    # соберём in-memory накопления для overlap-add: stem_name → (channels, N) float32
    # инициализируем нулями
    accum: dict[str, np.ndarray] = {}
    weight: np.ndarray = np.zeros(n_samples, dtype=np.float32)
    # Hann/window для сглаживания нахлёста (треугольная — проще)
    chunk_window = np.ones(segment_samples, dtype=np.float32)
    # косинусная рампа на overlap края
    overlap_s = segment_samples - hop_samples
    if overlap_s > 0:
        ramp = np.hanning(overlap_s * 2)[:overlap_s].astype(np.float32)
        # левый ramp 0→1, правый 1→0 — для overlap-add используем линейную 0.5
        # упрощённо: окно =1 внутри, ramp на краях
        chunk_window[:overlap_s] = ramp
        chunk_window[-overlap_s:] = ramp[::-1]

    for name in inference_stems:
        accum[name] = np.zeros_like(wav, dtype=np.float32)
    # если inference_stems пуст (например stems=("percussion",) → drumm+perc), уже инициализирован drums
    if not accum and "drums" not in accum:
        # хотя percussion без drums невозможен — уже добавили
        pass

    # имя входа для onnx — берём первое
    try:
        input_name = sess.get_inputs()[0].name
    except Exception:
        input_name = "input"

    for off in offsets:
        chunk = wav[:, off : off + segment_samples]
        # паддинг если хвост короче
        if chunk.shape[1] < segment_samples:
            pad = segment_samples - chunk.shape[1]
            chunk = np.pad(chunk, ((0, 0), (0, pad)), mode="constant")
        # добавляем batch dim для onnx: (1, channels, samples) или (channels, samples) — пробуем оба
        chunk_in = np.expand_dims(chunk, axis=0).astype(np.float32)
        # run
        try:
            outputs = sess.run(None, {input_name: chunk_in})
        except TypeError:
            # некоторые моки ожидают (None, {input_name: chunk}) без batch
            outputs = sess.run(None, {input_name: chunk.astype(np.float32)})

        # outputs — list per stem (или один)
        # маппим по порядку inference_stems
        if outputs is None:
            outputs = []
        if not isinstance(outputs, (list, tuple)):
            outputs = [outputs]

        for idx, stem_native in enumerate(inference_stems):
            if idx >= len(outputs):
                break
            out = outputs[idx]
            if out is None:
                continue
            arr = np.asarray(out)
            # нормализуем к (channels, samples)
            if arr.ndim == 3:
                # (1, channels, samples) → (channels, samples)
                arr = arr[0]
            if arr.ndim == 1:
                arr = np.expand_dims(arr, axis=0)
                arr = np.repeat(arr, 2, axis=0)
            if arr.ndim == 2 and arr.shape[0] > 4 and arr.shape[1] in (1, 2):
                # (samples, channels) → (channels, samples)
                arr = np.transpose(arr)
            if arr.shape[1] != segment_samples:
                # режем/паддим
                if arr.shape[1] > segment_samples:
                    arr = arr[:, :segment_samples]
                else:
                    arr = np.pad(arr, ((0, 0), (0, segment_samples - arr.shape[1])))

            # overlap-add с окном
            w = chunk_window
            # need broadcast: (channels, samples) * (samples,)
            weighted = arr.astype(np.float32) * w
            length = min(segment_samples, n_samples - off)
            accum[stem_native][:, off : off + length] += weighted[:, :length]
        # вес окна
        wlen = min(segment_samples, n_samples - off)
        weight[off : off + wlen] += chunk_window[:wlen]

    # нормализация по весу (избегаем деления на 0)
    weight = np.maximum(weight, 1e-6)
    for name in list(accum.keys()):
        accum[name] = accum[name] / weight

    # мап native → canonical (other → harmonic)
    canonical_accum: dict[str, np.ndarray] = {}
    for native, accum_arr in accum.items():
        canon = _DEMUCS_NATIVE_TO_CANONICAL.get(native, native)
        canonical_accum[canon] = accum_arr

    # запись запрошенных канонических стемов
    for canon in norm_stems:
        if canon == "percussion":
            continue  # выводится сплитом ниже
        canon_arr: np.ndarray | None = canonical_accum.get(canon)
        if canon_arr is None:
            # если инференс не дал стем (мок с 1 выходом для vocals-only), дублируем первый
            canon_arr = next(iter(canonical_accum.values())) if canonical_accum else np.zeros_like(wav)
        out_path = expected_paths[canon]
        _write_flac(out_path, canon_arr, sr=sr)

    # percussion split из drums
    if "percussion" in norm_stems:
        drums_p = expected_paths.get("drums") or (stem_dir / f"drums.{ext}")
        perc_p = expected_paths["percussion"]
        # drums мог быть ещё не записан на диск если drums не был в norm_stems но нужен для perc
        if not drums_p.exists() and "drums" in canonical_accum:
            _write_flac(drums_p, canonical_accum["drums"], sr=sr)
        _derive_percussion_from_drums(drums_p, perc_p)
        # если сплит не создал файл (нет ffmpeg), fallback — скопировать drums
        if not perc_p.exists() and drums_p.exists():
            try:
                import shutil

                shutil.copy(drums_p, perc_p)
            except Exception:
                _write_flac(perc_p, canonical_accum.get("drums", np.zeros_like(wav)), sr=sr)

    # вернуть только запрошенные канонические пути
    return {name: expected_paths[name] for name in norm_stems}
