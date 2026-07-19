"""Prompt metadata constants + registration tests."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

from app.prompts._shared import PROMPT_META

EXPECTED_PROMPTS: frozenset[str] = frozenset(
    {
        # core (6)
        "dj_expert_session",
        "build_set_workflow",
        "deliver_set_workflow",
        "expand_playlist_workflow",
        "full_pipeline",
        "quick_mix_check",
        # library & analysis (3)
        "library_health_workflow",
        "analyze_library_workflow",
        "track_prep_workflow",
        # set design (10)
        "harmonic_journey_workflow",
        "subgenre_journey_workflow",
        "tempo_journey_workflow",
        "scenario_set_workflow",
        "dj_persona_workflow",
        "style_lock_set_workflow",
        "mix_cluster_workflow",
        "lineup_handoff_workflow",
        "b2b_planning_workflow",
        "extend_set_workflow",
        # set repair (4)
        "set_review_workflow",
        "rescue_set_workflow",
        "fix_transition_workflow",
        "replace_track_workflow",
        # delivery & performance (3)
        "set_cheatsheet_workflow",
        "set_duration_fit_workflow",
        "live_next_track_workflow",
        # discovery & ops (3)
        "crate_digging_workflow",
        "taste_profile_workflow",
        "playlist_sync_workflow",
        # library maintenance (1)
        "library_cleanup_workflow",
        # generation (2)
        "suno_set_asset_workflow",
        "suno_track_production_workflow",
        # render (1)
        "render_set_workflow",
    }
)


def test_prompt_meta_has_version() -> None:
    assert "version" in PROMPT_META
    assert "layer" in PROMPT_META
    assert PROMPT_META["layer"] == "prompt"


def _import_all_prompt_modules() -> list[str]:
    import app.prompts as pkg

    imported: list[str] = []
    for mod in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        if mod.name.endswith("._shared"):
            continue
        importlib.import_module(mod.name)
        imported.append(mod.name)
    return imported


def test_all_prompt_modules_importable() -> None:
    """Every prompt module imports cleanly (decorators execute)."""
    imported = _import_all_prompt_modules()
    # Sanity: at least 30 prompt files (the live catalog)
    assert len(imported) >= 30
    for name in EXPECTED_PROMPTS:
        assert any(m.endswith(f".{name}") for m in imported), (
            f"Prompt module for '{name}' not found in {imported}"
        )


def test_all_prompts_return_prompt_result() -> None:
    """Calling each prompt function (with minimal args) yields PromptResult."""
    from fastmcp.prompts import PromptResult

    from app.prompts.analyze_library_workflow import analyze_library_workflow
    from app.prompts.b2b_planning_workflow import b2b_planning_workflow
    from app.prompts.build_set_workflow import build_set_workflow
    from app.prompts.crate_digging_workflow import crate_digging_workflow
    from app.prompts.deliver_set_workflow import deliver_set_workflow
    from app.prompts.dj_expert_session import dj_expert_session
    from app.prompts.dj_persona_workflow import dj_persona_workflow
    from app.prompts.expand_playlist_workflow import expand_playlist_workflow
    from app.prompts.extend_set_workflow import extend_set_workflow
    from app.prompts.fix_transition_workflow import fix_transition_workflow
    from app.prompts.full_pipeline import full_pipeline
    from app.prompts.harmonic_journey_workflow import harmonic_journey_workflow
    from app.prompts.library_cleanup_workflow import library_cleanup_workflow
    from app.prompts.library_health_workflow import library_health_workflow
    from app.prompts.lineup_handoff_workflow import lineup_handoff_workflow
    from app.prompts.live_next_track_workflow import live_next_track_workflow
    from app.prompts.mix_cluster_workflow import mix_cluster_workflow
    from app.prompts.playlist_sync_workflow import playlist_sync_workflow
    from app.prompts.quick_mix_check import quick_mix_check
    from app.prompts.replace_track_workflow import replace_track_workflow
    from app.prompts.rescue_set_workflow import rescue_set_workflow
    from app.prompts.scenario_set_workflow import scenario_set_workflow
    from app.prompts.set_cheatsheet_workflow import set_cheatsheet_workflow
    from app.prompts.set_duration_fit_workflow import set_duration_fit_workflow
    from app.prompts.set_review_workflow import set_review_workflow
    from app.prompts.style_lock_set_workflow import style_lock_set_workflow
    from app.prompts.subgenre_journey_workflow import subgenre_journey_workflow
    from app.prompts.suno_set_asset_workflow import suno_set_asset_workflow
    from app.prompts.suno_track_production_workflow import (
        suno_track_production_workflow,
    )
    from app.prompts.taste_profile_workflow import taste_profile_workflow
    from app.prompts.tempo_journey_workflow import tempo_journey_workflow
    from app.prompts.track_prep_workflow import track_prep_workflow

    results = [
        dj_expert_session(),
        build_set_workflow(playlist_id=1),
        deliver_set_workflow(set_id=1),
        expand_playlist_workflow(playlist_id=1),
        full_pipeline(playlist_id=1),
        quick_mix_check(from_track_id=1, to_track_id=2),
        library_health_workflow(),
        library_health_workflow(playlist_id=1),
        analyze_library_workflow(),
        analyze_library_workflow(playlist_id=1, level=3),
        track_prep_workflow(track_id=1),
        harmonic_journey_workflow(playlist_id=1),
        subgenre_journey_workflow(playlist_id=1, arc="build"),
        tempo_journey_workflow(playlist_id=1),
        scenario_set_workflow(playlist_id=1, scenario="warmup"),
        dj_persona_workflow(playlist_id=1, persona="klock"),
        style_lock_set_workflow(playlist_id=1, style="hypnotic"),
        mix_cluster_workflow(playlist_id=1),
        lineup_handoff_workflow(playlist_id=1, role="warmup"),
        b2b_planning_workflow(playlist_a=1, playlist_b=2),
        extend_set_workflow(set_id=1),
        set_review_workflow(set_id=1),
        rescue_set_workflow(set_id=1),
        fix_transition_workflow(from_track_id=1, to_track_id=2),
        replace_track_workflow(set_id=1, position=3),
        set_cheatsheet_workflow(set_id=1),
        set_duration_fit_workflow(set_id=1),
        live_next_track_workflow(last_track_id=1),
        crate_digging_workflow(seed="Amelie Lens"),
        taste_profile_workflow(),
        playlist_sync_workflow(playlist_id=1, direction="diff"),
        library_cleanup_workflow(),
        library_cleanup_workflow(playlist_id=1),
        suno_set_asset_workflow(set_id=1),
        suno_track_production_workflow(title="Test Suno", brief="hypnotic techno"),
    ]
    for r in results:
        assert isinstance(r, PromptResult)
        assert r.description
        assert len(r.messages) >= 1


@pytest.mark.asyncio
async def test_all_expected_prompts_registered(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    names = {p.name for p in prompts}
    missing = EXPECTED_PROMPTS - names
    assert not missing, f"Missing prompts: {sorted(missing)}"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Phase 5 server wiring", strict=False)
async def test_all_prompts_have_tags(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    for p in prompts:
        if p.name not in EXPECTED_PROMPTS:
            continue
        assert p.tags, f"prompt {p.name} has no tags"


@pytest.mark.asyncio
async def test_all_prompts_have_description(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    for p in prompts:
        if p.name not in EXPECTED_PROMPTS:
            continue
        assert p.description, f"prompt {p.name} has no description"


@pytest.mark.asyncio
async def test_all_prompts_carry_meta_version(client: object) -> None:
    prompts = await client.list_prompts()  # type: ignore[attr-defined]
    for p in prompts:
        if p.name not in EXPECTED_PROMPTS:
            continue
        meta = getattr(p, "meta", {}) or {}
        assert "version" in meta, f"prompt {p.name} meta has no 'version'"
