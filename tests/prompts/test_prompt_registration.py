"""Prompt metadata constants + registration tests."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

from app.prompts._shared import PROMPT_META

EXPECTED_PROMPTS: frozenset[str] = frozenset(
    {
        "dj_expert_session",
        "build_set_workflow",
        "deliver_set_workflow",
        "expand_playlist_workflow",
        "full_pipeline",
        "quick_mix_check",
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
    # Sanity: at least 6 prompt files
    assert len(imported) >= 6
    for name in EXPECTED_PROMPTS:
        assert any(m.endswith(f".{name}") for m in imported), (
            f"Prompt module for '{name}' not found in {imported}"
        )


def test_all_prompts_return_prompt_result() -> None:
    """Calling each prompt function (with minimal args) yields PromptResult."""
    from fastmcp.prompts import PromptResult

    from app.prompts.build_set_workflow import build_set_workflow
    from app.prompts.deliver_set_workflow import deliver_set_workflow
    from app.prompts.dj_expert_session import dj_expert_session
    from app.prompts.expand_playlist_workflow import expand_playlist_workflow
    from app.prompts.full_pipeline import full_pipeline
    from app.prompts.quick_mix_check import quick_mix_check

    results = [
        dj_expert_session(),
        build_set_workflow(playlist_id=1),
        deliver_set_workflow(set_id=1),
        expand_playlist_workflow(playlist_id=1),
        full_pipeline(playlist_id=1),
        quick_mix_check(from_track_id=1, to_track_id=2),
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
