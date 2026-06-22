"""Guard tests: every entity / provider name referenced in a prompt body
must resolve to something the runtime actually exposes.

Audit (2026-04-27) found four content bugs in workflow prompts:

* ``deliver_set_workflow`` told the LLM to ``entity_create(entity='app_export', ...)``
  even though ``app_export`` has been drop-pending since Blueprint §13.2
  and is not registered in ``EntityRegistry``.
* ``expand_playlist_workflow`` referenced
  ``provider_read(entity='similar_tracks', ...)`` — the real adapter
  surface is ``track_similar``.
* ``build_set_workflow`` told the LLM to use ``entity_list(entity="track",
  fields="scoring")``; the ``scoring`` preset only exists on
  ``track_features`` (track has ``id|ref|summary|full``).
* ``full_pipeline`` inherited the lot via cross-prompt invocation.

Bug class D is the same shape as v1.0.13 (declared but not enforced):
docs lied about contracts. This module pins the contract.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from app.prompts.analyze_library_workflow import analyze_library_workflow
from app.prompts.b2b_planning_workflow import b2b_planning_workflow
from app.prompts.build_set_workflow import build_set_workflow
from app.prompts.crate_digging_workflow import crate_digging_workflow
from app.prompts.deliver_set_workflow import deliver_set_workflow
from app.prompts.dj_expert_session import dj_expert_session
from app.prompts.expand_playlist_workflow import expand_playlist_workflow
from app.prompts.extend_set_workflow import extend_set_workflow
from app.prompts.fix_transition_workflow import fix_transition_workflow
from app.prompts.full_pipeline import full_pipeline
from app.prompts.harmonic_journey_workflow import harmonic_journey_workflow
from app.prompts.library_health_workflow import library_health_workflow
from app.prompts.playlist_sync_workflow import playlist_sync_workflow
from app.prompts.quick_mix_check import quick_mix_check
from app.prompts.replace_track_workflow import replace_track_workflow
from app.prompts.scenario_set_workflow import scenario_set_workflow
from app.prompts.set_review_workflow import set_review_workflow
from app.prompts.subgenre_journey_workflow import subgenre_journey_workflow
from app.prompts.taste_profile_workflow import taste_profile_workflow
from app.providers.yandex.adapter import YandexAdapter
from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry


@pytest.fixture(autouse=True)
def _registered() -> None:
    EntityRegistry.clear()
    register_default_entities()
    yield
    EntityRegistry.clear()


def _render(p: Callable[..., object]) -> str:
    """Render any prompt with throwaway args; concatenate every message body."""
    name = p.__name__
    if name == "build_set_workflow":
        result = p(playlist_id=1, template="classic_60")
    elif name == "deliver_set_workflow":
        result = p(set_id=1, sync_to_ym=False)
    elif name == "expand_playlist_workflow":
        result = p(playlist_id=1, target_count=10)
    elif name == "full_pipeline":
        result = p(playlist_id=1, template="classic_60", sync_to_ym=False)
    elif name == "quick_mix_check":
        result = p(from_track_id=1, to_track_id=2)
    elif name == "dj_expert_session":
        result = p()
    elif name == "library_health_workflow":
        result = p(playlist_id=1)
    elif name == "analyze_library_workflow":
        result = p(playlist_id=1, level=3)
    elif name == "harmonic_journey_workflow":
        result = p(playlist_id=1)
    elif name == "subgenre_journey_workflow":
        result = p(playlist_id=1, arc="build")
    elif name == "scenario_set_workflow":
        result = p(playlist_id=1, scenario="warmup")
    elif name == "b2b_planning_workflow":
        result = p(playlist_a=1, playlist_b=2)
    elif name == "extend_set_workflow" or name == "set_review_workflow":
        result = p(set_id=1)
    elif name == "fix_transition_workflow":
        result = p(from_track_id=1, to_track_id=2)
    elif name == "replace_track_workflow":
        result = p(set_id=1, position=3)
    elif name == "crate_digging_workflow":
        result = p(seed="Amelie Lens", target_count=10, playlist_id=1)
    elif name == "taste_profile_workflow":
        result = p()
    elif name == "playlist_sync_workflow":
        result = p(playlist_id=1, direction="diff")
    else:
        raise AssertionError(f"unknown prompt: {name}")
    parts: list[str] = []
    for m in result.messages:  # type: ignore[attr-defined]
        content = m.content
        parts.append(getattr(content, "text", str(content)))
    return "\n".join(parts)


_ENTITY_RE = re.compile(r"""\bentity\s*=\s*['"]([a-z_]+)['"]""")
_PROVIDER_READ_RE = re.compile(
    r"""provider_read\s*\([^)]*?\bentity\s*=\s*['"]([a-z_]+)['"]""",
    re.DOTALL,
)
_FIELDS_PRESET_RE = re.compile(
    r"""\bentity\s*=\s*['"]([a-z_]+)['"][^)]*?\bfields\s*=\s*['"]([a-z_]+)['"]""",
    re.DOTALL,
)

PROMPTS = (
    build_set_workflow,
    deliver_set_workflow,
    dj_expert_session,
    expand_playlist_workflow,
    full_pipeline,
    quick_mix_check,
    library_health_workflow,
    analyze_library_workflow,
    harmonic_journey_workflow,
    subgenre_journey_workflow,
    scenario_set_workflow,
    b2b_planning_workflow,
    extend_set_workflow,
    set_review_workflow,
    fix_transition_workflow,
    replace_track_workflow,
    crate_digging_workflow,
    taste_profile_workflow,
    playlist_sync_workflow,
)


@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.__name__)
def test_entity_names_are_registered(prompt: Callable[..., object]) -> None:
    body = _render(prompt)
    referenced = set(_ENTITY_RE.findall(body))
    registered = set(EntityRegistry.names())
    # Provider entities are validated separately; drop them from this check.
    provider_entities = set(_PROVIDER_READ_RE.findall(body))
    referenced -= provider_entities
    unknown = referenced - registered
    assert not unknown, (
        f"{prompt.__name__} references unregistered entities {sorted(unknown)} — "
        "registered entities are: " + ", ".join(sorted(registered))
    )


@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.__name__)
def test_provider_entities_match_adapter_surface(
    prompt: Callable[..., object],
) -> None:
    body = _render(prompt)
    referenced = set(_PROVIDER_READ_RE.findall(body))
    supported = set(YandexAdapter.entities_supported)
    unknown = referenced - supported
    assert not unknown, (
        f"{prompt.__name__} uses provider_read(entity={sorted(unknown)!r}) — "
        f"YandexAdapter only handles {sorted(supported)}"
    )


@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.__name__)
def test_field_presets_exist_on_entity(prompt: Callable[..., object]) -> None:
    """`fields="<preset>"` must reference a preset declared on that entity.

    Audit found ``fields="scoring"`` on ``entity="track"`` — ``scoring`` is
    only declared on ``track_features``. The result is a hard ValueError
    inside ``resolve_field_projection`` when the LLM follows the recipe.
    """
    body = _render(prompt)
    bad: list[tuple[str, str]] = []
    for entity, preset in _FIELDS_PRESET_RE.findall(body):
        if entity not in EntityRegistry.names():
            continue  # entity-name correctness is covered by another test
        cfg = EntityRegistry.get(entity)
        if preset not in cfg.field_presets:
            bad.append((entity, preset))
    assert not bad, (
        f"{prompt.__name__} references undeclared field presets: {bad}. "
        "Each ``fields=<name>`` must exist in that entity's field_presets."
    )
