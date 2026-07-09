from __future__ import annotations

import logging
from pathlib import Path
from tempfile import mkdtemp

from app.audio.deep.beatgrid_builder import build_beatgrid
from app.audio.deep.demucs_runner import run_demucs
from app.audio.deep.drum_bands import analyze_drum_bands
from app.audio.deep.embedding_builder import build_embeddings
from app.audio.deep.stem_analyzer import analyze_stems
from app.audio.deep.structure_analyzer import analyze_structure
from app.audio.deep.timeseries_store import upload_timeseries
from app.audio.deep.waveform_store import build_waveform, upload_waveform
from app.domain.deep_analysis.models import L6AnalysisResult
from app.providers.supabase.storage_client import SupabaseStorageClient
from app.repositories.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class L6AnalysisOrchestrator:
    def __init__(self, storage_client: SupabaseStorageClient) -> None:
        self._storage = storage_client

    async def run(self, track_id: int, uow: UnitOfWork) -> L6AnalysisResult:
        result = L6AnalysisResult(track_id=track_id)

        lib_item = await uow.audio_files.get_for_track(track_id)
        if lib_item is None or not lib_item.file_path:
            result.errors.append("No library item with file_path")
            return result

        audio_path = Path(lib_item.file_path)
        if not audio_path.exists():
            result.errors.append(f"File not found: {audio_path}")
            return result

        work_dir = Path(mkdtemp(prefix=f"l6_{track_id}_"))
        try:
            # Step 1: Demucs
            stem_paths = run_demucs(audio_path, work_dir / "stems")
            result.stems = {k: str(v) for k, v in stem_paths.items()}

            # Step 2: Per-stem analysis
            all_features: dict[str, dict] = {}
            try:
                all_features = await analyze_stems(uow, track_id, stem_paths, audio_path)
                for stem_name, features in all_features.items():
                    if features:
                        await uow.stem_features.upsert(track_id, stem_name, features)
                        result.stem_features_count += 1
            except Exception as e:
                result.errors.append(f"Stem analysis: {e}")

            # Step 3: Beatgrid (use original audio)
            try:
                await build_beatgrid(uow, track_id, audio_path)
                result.beatgrid_registered = True
            except Exception as e:
                result.errors.append(f"Beatgrid: {e}")

            # Step 4: Structure
            try:
                await uow.track_features.clear_l6_sections(track_id)
                sections = analyze_structure(audio_path, stem_paths)
                for section in sections:
                    await uow.track_features.save_track_section(track_id, section)
                result.sections_count = len(sections)
            except Exception as e:
                result.errors.append(f"Structure: {e}")

            # Step 5: Embeddings (from original features)
            try:
                orig_features = all_features.get("original", {})
                if orig_features:
                    embeddings = build_embeddings(orig_features)
                    for etype, emb in embeddings.items():
                        await uow.track_embeddings.upsert(track_id, "original", etype, emb)
                        result.embeddings_count += 1
            except Exception as e:
                result.errors.append(f"Embeddings: {e}")

            # Step 5b: Drum band analysis (per-band energy + onset rate)
            try:
                drums_path = stem_paths.get("drums")
                if drums_path:
                    bands_data = analyze_drum_bands(drums_path)
                    await uow.stem_features.upsert(
                        track_id, "drums", {"drum_bands": bands_data}
                    )
                    result.drum_bands = bands_data.get("bands", {})
            except Exception as e:
                result.errors.append(f"DrumBands: {e}")

            # Step 6: CrossSimilarity — skipped without candidates

            # Step 7: Timeseries upload (skip if Supabase unavailable)
            if self._storage.available:
                try:
                    await upload_timeseries(self._storage, track_id, "original", {})
                    result.timeseries_uploaded = True
                except Exception as e:
                    result.errors.append(f"Timeseries upload: {e}")
            else:
                result.errors.append("Timeseries upload: Supabase not configured")

            # Step 8: Waveform (skip if Supabase unavailable)
            if self._storage.available:
                try:
                    peaks = build_waveform(audio_path)
                    await upload_waveform(self._storage, track_id, "original", peaks)
                    result.waveform_uploaded = True
                except Exception as e:
                    result.errors.append(f"Waveform upload: {e}")
            else:
                result.errors.append("Waveform upload: Supabase not configured")

        finally:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)

        return result
