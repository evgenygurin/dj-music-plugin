from __future__ import annotations

from pathlib import Path

import librosa

from app.audio.render.kick_phase import compute_kick_phase
from app.audio.render.phase_refine import refine_phase
from app.repositories.unit_of_work import UnitOfWork


class BeatgridEntry:
    def __init__(self, bpm: float, trim_start_s: float, refined_trim_s: float, phase_ms: float) -> None:
        self.bpm = bpm
        self.trim_start_s = trim_start_s
        self.refined_trim_s = refined_trim_s
        self.phase_ms = phase_ms


def _get_bpm_from_path(audio_path: Path) -> float:
    y, sr = librosa.load(str(audio_path), sr=None, duration=60)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo)


async def build_beatgrid(uow: UnitOfWork, track_id: int, audio_path: Path) -> BeatgridEntry:
    bpm = _get_bpm_from_path(audio_path)
    trim_start, phase_ms = compute_kick_phase(str(audio_path), bpm)
    refined = refine_phase(str(audio_path), bpm, trim_start)

    lib_item = await uow.audio_files.get_for_track(track_id)
    if lib_item is not None:
        await uow.audio_files.register_beatgrid(
            library_item_id=lib_item.id,
            bpm=bpm,
            first_downbeat_ms=refined * 1000,
            canonical=True,
        )

    return BeatgridEntry(bpm=bpm, trim_start_s=trim_start, refined_trim_s=refined, phase_ms=phase_ms)
