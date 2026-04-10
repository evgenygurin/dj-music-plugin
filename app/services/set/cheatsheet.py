"""Set cheat sheet sub-service — generate human-readable transition guides."""

from __future__ import annotations

from app.core.errors import NotFoundError
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.transition.recipe import TransitionRecipe


def _format_recipe_box(recipe: TransitionRecipe, score: float | None = None) -> str:
    """Format a transition recipe as a text box for cheat sheet."""
    type_label = recipe.transition_type.value.upper().replace("_", " ")
    header = f"{type_label} · {recipe.bars} bars"
    if recipe.djay_transition.value != "none":
        header += f" ─── djay: {recipe.djay_transition.value.replace('_', ' ').title()}"
    else:
        header += " ─── djay: Manual EQ"

    lines = [f"     ┌── {header} ──┐"]
    lines.append("     │")
    for step in recipe.steps:
        deck_label = step.deck.upper()
        lines.append(f"     │  bar {step.bar:<3}  {deck_label}: {step.action}")
    lines.append("     │")
    eq = recipe.eq_plan
    lines.append(f"     │  EQ: low={eq.low} · mid={eq.mid} · high={eq.high}")
    for w in recipe.warnings:
        lines.append(f"     │  ⚠ {w}")
    lines.append(f"     │  Rescue: {recipe.rescue_move}")
    if score is not None:
        lines.append(f"     │  Score: {score:.2f} · Confidence: {recipe.confidence:.2f}")
    lines.append("     └" + "─" * 50 + "┘")
    return "\n".join(lines)


class SetCheatSheetService:
    """Generate human-readable cheat sheets for DJ sets."""

    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
        feature_repo: FeatureRepository,
    ) -> None:
        self._sets = set_repo
        self._tracks = track_repo
        self._features = feature_repo

    async def get_cheat_sheet(self, set_id: int, version: str | None = None) -> str:
        """Generate human-readable cheat sheet with BPM, key, energy, transitions."""
        from app.camelot.wheel import key_code_to_camelot

        dj_set = await self._sets.get_by_id(set_id)
        if dj_set is None:
            raise NotFoundError("Set", set_id)

        result = await self._sets.load_version_with_items(set_id)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        latest, items = result

        # Batch-load features for all tracks
        track_ids = [item.track_id for item in items]
        features_map = await self._features.get_scoring_features_batch(track_ids)

        lines = [
            f"=== {dj_set.name} ===",
            f"Version: {latest.label or latest.id}",
            f"Tracks: {len(items)}",
            f"Score: {latest.quality_score or 'N/A'}",
            "",
        ]

        prev_feat = None
        for i, item in enumerate(items, 1):
            track = await self._tracks.get_by_id(item.track_id)
            if not track:
                continue

            feat = features_map.get(item.track_id)

            # Track line with BPM, key, energy
            bpm_str = f"{feat.bpm:.1f}" if feat and feat.bpm else "?"
            key_str = (
                key_code_to_camelot(feat.key_code) if feat and feat.key_code is not None else "?"
            )
            lufs_str = (
                f"{feat.integrated_lufs:.1f}" if feat and feat.integrated_lufs is not None else "?"
            )
            pinned = " [PINNED]" if item.pinned else ""

            line = f"{i:2d}. {track.title}{pinned}  [{bpm_str} BPM | {key_str} | {lufs_str} LUFS]"
            lines.append(line)

            # Transition info from previous track
            if prev_feat and feat and i > 1:
                bpm_delta = (feat.bpm - prev_feat.bpm) if feat.bpm and prev_feat.bpm else None
                prev_key = (
                    key_code_to_camelot(prev_feat.key_code)
                    if prev_feat.key_code is not None
                    else "?"
                )
                cur_key = key_code_to_camelot(feat.key_code) if feat.key_code is not None else "?"
                energy_dir = ""
                if feat.integrated_lufs is not None and prev_feat.integrated_lufs is not None:
                    delta_lufs = feat.integrated_lufs - prev_feat.integrated_lufs
                    energy_dir = (
                        "up" if delta_lufs > 0.5 else ("down" if delta_lufs < -0.5 else "~")
                    )

                bpm_delta_str = f"{bpm_delta:+.1f}" if bpm_delta is not None else "?"
                lines.append(
                    f"    -> {bpm_delta_str} BPM | key: {prev_key}->{cur_key} | energy: {energy_dir}"
                )

                # Generate recipe box
                synthetic = TransitionScore(
                    bpm=0.5,
                    harmonic=0.5,
                    energy=0.5,
                    spectral=0.5,
                    groove=0.5,
                    timbral=0.5,
                    overall=0.5,
                )
                recipe = recommend_recipe(
                    synthetic,
                    prev_feat,
                    feat,
                    mood_a=prev_feat.mood if prev_feat else None,
                    mood_b=feat.mood if feat else None,
                )
                lines.append(_format_recipe_box(recipe))

            prev_feat = feat

        return "\n".join(lines)
