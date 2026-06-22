"""Manual prompt verification: render every prompt and validate that EVERY
referenced name (resource URI, tool, cross-prompt, template, aggregate op/field,
energy_direction) resolves against the live runtime.

Goes beyond tests/prompts/test_prompt_content_correctness.py (which only checks
entity / provider-entity / field-preset / filter / data / provider_write).

Run: uv run python scripts/verify_prompts_manual.py
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable

import app.prompts as _prompts_pkg
from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry

# ── ground truth from the live runtime ──────────────────────────────────────
EntityRegistry.clear()
register_default_entities()
ENTITIES = set(EntityRegistry.names())

TOOLS = {
    "entity_list",
    "entity_get",
    "entity_aggregate",
    "entity_create",
    "entity_update",
    "entity_delete",
    "provider_read",
    "provider_search",
    "provider_write",
    "transition_score_pool",
    "sequence_optimize",
    "playlist_sync",
    "tool_invoke",
    "unlock_namespace",
    "ui_set_view",
    "ui_transition_score",
    "ui_library_audit",
    "ui_score_pool_matrix",
    "ui_library_dashboard",
    "ui_camelot_wheel",
}

RESOURCE_TEMPLATES = [
    "local://playlists/{id}/audit",
    "local://playlists/{id}{?include_tracks}",
    "local://sets/{id}/cheatsheet{?version}",
    "local://sets/{id}/narrative",
    "local://sets/{id}/review",
    "local://sets/{id}/versions/compare/{a}/{b}",
    "local://sets/{id}/{view}",
    "local://tracks/{id}",
    "local://tracks/{id}/audit",
    "local://tracks/{id}/features",
    "local://tracks/{id}/suggest_next{?limit,energy_direction}",
    "local://tracks/{id}/suggest_replacement/{set_id}/{position}",
    "local://transition/{from_id}/{to_id}/explain",
    "local://transition/{from_id}/{to_id}/score",
    "local://transition_history/best_pairs{?track_id,limit}",
    "local://transition_history/history{?limit,track_id}",
    "reference://audit_rules",
    "reference://camelot",
    "reference://subgenres",
    "reference://templates",
    "schema://entities",
    "schema://entities/{entity}",
    "schema://providers",
    "schema://providers/{name}",
    "session://energy-trend{?limit}",
    "session://set-draft",
    "session://tool-history",
]

TEMPLATES = {
    "warm_up_30",
    "classic_60",
    "peak_hour_60",
    "roller_90",
    "progressive_120",
    "wave_120",
    "closing_60",
    "full_library",
}
AGG_OPS = {"count", "distinct", "histogram", "min_max", "sum", "avg"}
ENERGY_DIRS = {"up", "down", "flat"}
VIEWS = {"summary", "tracks", "transitions", "full"}  # local://sets/{id}/{view}
# real model columns PER entity — so a field valid on one entity is not
# accepted on another (e.g. bpm is on track_features, NOT on track).
ENTITY_COLUMNS: dict[str, set[str]] = {
    e: set(EntityRegistry.get(e).model.__table__.columns.keys()) for e in ENTITIES
}
AGG_FIELDS: set[str] = set().union(*ENTITY_COLUMNS.values())  # fallback (entity unknown)


# ── helpers ──────────────────────────────────────────────────────────────────
def _split(uri: str) -> tuple[list[str], set[str]]:
    """Return (path segments after scheme, query keys).

    Handles both template query markers ``{?a,b}`` and real ``?a=1&b=2``.
    """
    body = uri.split("://", 1)[1]
    qkeys: set[str] = set()
    # template marker {?a,b} — strip it out, record its keys
    tmpl_q = re.search(r"\{\?([^}]+)\}", body)
    if tmpl_q:
        qkeys |= set(tmpl_q.group(1).split(","))
    body = re.sub(r"\{\?[^}]+\}", "", body)
    # real query ?a=1&b=2
    path, _, query = body.partition("?")
    if query:
        for pair in query.split("&"):
            k = pair.split("=")[0].strip()
            if k:
                qkeys.add(k)
    segs = [s for s in path.split("/") if s != ""]
    return segs, qkeys


def _is_placeholder(seg: str) -> bool:
    return (
        (seg.startswith("{") and seg.endswith("}"))
        or (seg.startswith("<") and seg.endswith(">"))
        or seg.isdigit()
    )


def _template_qkeys(tmpl: str) -> set[str]:
    m = re.search(r"\{\?([^}]+)\}", tmpl)
    return set(m.group(1).split(",")) if m else set()


def uri_matches(cand: str, tmpl: str) -> bool:
    # scheme must match (local:// vs session:// vs reference:// vs schema://)
    if cand.split("://", 1)[0] != tmpl.split("://", 1)[0]:
        return False
    cs, _ = _split(cand)
    ts, _ = _split(tmpl)
    if len(cs) != len(ts):
        return False
    for c, t in zip(cs, ts, strict=True):
        t_ph = t.startswith("{") and t.endswith("}")
        if t_ph:
            continue  # template param matches anything
        if _is_placeholder(c):
            continue  # candidate placeholder matches a literal template seg
        if c != t:
            return False
    return True


def validate_uri(cand: str) -> str | None:
    for t in RESOURCE_TEMPLATES:
        if uri_matches(cand, t):
            # enum-segment check: the {view} param accepts a fixed set only
            if t == "local://sets/{id}/{view}":
                view_seg = _split(cand)[0][-1]
                if not _is_placeholder(view_seg) and view_seg not in VIEWS:
                    return f"set view '{view_seg}' not in {sorted(VIEWS)}"
            # query-key check: any query key must be declared on the template
            _, cq = _split(cand)
            bad_q = cq - _template_qkeys(t)
            if bad_q:
                return f"query keys {sorted(bad_q)} not in {t}"
            return None
    return f"no resource template matches '{cand}'"


# ── render all prompts ───────────────────────────────────────────────────────
def _render_all() -> dict[str, str]:
    pkg = _prompts_pkg

    bodies: dict[str, str] = {}
    args: dict[str, dict] = {
        "build_set_workflow": {"playlist_id": 1, "template": "classic_60"},
        "deliver_set_workflow": {"set_id": 1, "sync_to_ym": False},
        "expand_playlist_workflow": {"playlist_id": 1, "target_count": 10},
        "full_pipeline": {"playlist_id": 1, "template": "classic_60"},
        "quick_mix_check": {"from_track_id": 1, "to_track_id": 2},
        "dj_expert_session": {},
        "library_health_workflow": {"playlist_id": 1},
        "analyze_library_workflow": {"playlist_id": 1, "level": 3},
        "track_prep_workflow": {"track_id": 1},
        "harmonic_journey_workflow": {"playlist_id": 1},
        "subgenre_journey_workflow": {"playlist_id": 1, "arc": "build"},
        "tempo_journey_workflow": {"playlist_id": 1},
        "scenario_set_workflow": {"playlist_id": 1, "scenario": "warmup"},
        "dj_persona_workflow": {"playlist_id": 1, "persona": "klock"},
        "style_lock_set_workflow": {"playlist_id": 1, "style": "hypnotic"},
        "mix_cluster_workflow": {"playlist_id": 1},
        "lineup_handoff_workflow": {"playlist_id": 1, "role": "warmup"},
        "b2b_planning_workflow": {"playlist_a": 1, "playlist_b": 2},
        "extend_set_workflow": {"set_id": 1},
        "set_review_workflow": {"set_id": 1},
        "rescue_set_workflow": {"set_id": 1},
        "fix_transition_workflow": {"from_track_id": 1, "to_track_id": 2},
        "replace_track_workflow": {"set_id": 1, "position": 3},
        "set_cheatsheet_workflow": {"set_id": 1},
        "set_duration_fit_workflow": {"set_id": 1},
        "live_next_track_workflow": {"last_track_id": 1},
        "crate_digging_workflow": {"seed": "Amelie Lens", "target_count": 10},
        "taste_profile_workflow": {},
        "playlist_sync_workflow": {"playlist_id": 1, "direction": "diff"},
        "library_cleanup_workflow": {"playlist_id": 1},
    }
    for mod in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        if mod.name.endswith("._shared"):
            continue
        m = importlib.import_module(mod.name)
        fn_name = mod.name.rsplit(".", 1)[1]
        fn: Callable | None = getattr(m, fn_name, None)
        if fn is None or fn_name not in args:
            continue
        result = fn(**args[fn_name])
        parts = []
        for msg in result.messages:
            c = msg.content
            parts.append(getattr(c, "text", str(c)))
        bodies[fn_name] = "\n".join(parts)
    return bodies


# ── validation passes ────────────────────────────────────────────────────────
_URI_RE = re.compile(r"(?:local|session|reference|schema)://[^\s)\]`'\"]+")
_TOOL_RE = re.compile(
    r"\b(entity_[a-z]+|provider_[a-z]+|sequence_optimize|transition_score_pool"
    r"|playlist_sync|ui_[a-z_]+|unlock_namespace|tool_invoke)\("
)
_XPROMPT_RE = re.compile(r"\b([a-z_]+_workflow|dj_expert_session|quick_mix_check|full_pipeline)\b")
_SEQ_TMPL_RE = re.compile(r"sequence_optimize\([^)]*template=[\"']([a-z_0-9]+)[\"']", re.DOTALL)
_AGG_OP_RE = re.compile(r"entity_aggregate\([^)]*operation=[\"']([a-z_]+)[\"']", re.DOTALL)
# whole entity_aggregate(...) call window, so field= can be cross-checked
# against the call's own entity= (a field valid on another entity must fail).
_AGG_CALL_RE = re.compile(r"entity_aggregate\(([^)]*)\)", re.DOTALL)
_ENT_IN_CALL = re.compile(r"entity=[\"'](\w+)[\"']")
_FIELD_IN_CALL = re.compile(r"field=[\"'](\w+)[\"']")
# energy_direction in BOTH the quoted form ('up') and the URL-query form
# (&energy_direction=up); a leading '<' (the <up|down|flat> doc placeholder)
# is intentionally not matched.
_ENERGY_RE = re.compile(r"energy_direction\s*[=:]\s*[\"']?([a-z]+)")

ALL_PROMPTS = None  # filled after render


def check(name: str, body: str) -> list[str]:
    issues: list[str] = []

    for uri in _URI_RE.findall(body):
        uri = uri.rstrip(".,;")
        err = validate_uri(uri)
        if err:
            issues.append(f"URI: {err}")

    for tool in _TOOL_RE.findall(body):
        if tool not in TOOLS:
            issues.append(f"TOOL: '{tool}' is not a real tool")

    for xp in _XPROMPT_RE.findall(body):
        if xp not in ALL_PROMPTS:
            issues.append(f"XPROMPT: '{xp}' is not a registered prompt")

    for t in _SEQ_TMPL_RE.findall(body):
        if t not in TEMPLATES:
            issues.append(f"TEMPLATE: sequence_optimize template='{t}' unknown")

    for op in _AGG_OP_RE.findall(body):
        if op not in AGG_OPS:
            issues.append(f"AGG_OP: '{op}' not a valid aggregate operation")

    for blob in _AGG_CALL_RE.findall(body):
        fm = _FIELD_IN_CALL.search(blob)
        if not fm:
            continue
        field = fm.group(1)
        em = _ENT_IN_CALL.search(blob)
        ent = em.group(1) if em else None
        if ent and ent in ENTITY_COLUMNS:
            if field not in ENTITY_COLUMNS[ent]:
                issues.append(f"AGG_FIELD: '{field}' is not a column on entity '{ent}'")
        elif field not in AGG_FIELDS:
            issues.append(f"AGG_FIELD: '{field}' not a known model column")

    for ed in _ENERGY_RE.findall(body):
        if ed not in ENERGY_DIRS:
            issues.append(f"ENERGY_DIR: '{ed}' not in up/down/flat")

    return issues


def main() -> None:
    global ALL_PROMPTS
    bodies = _render_all()
    ALL_PROMPTS = set(bodies.keys())
    print(f"Rendered {len(bodies)} prompts.\n")
    total_issues = 0
    for name in sorted(bodies):
        issues = check(name, bodies[name])
        if issues:
            total_issues += len(issues)
            print(f"❌ {name}")
            for i in issues:
                print(f"     - {i}")
        else:
            print(f"✅ {name}")
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {len(bodies)} prompts, {total_issues} issues")
    if total_issues == 0:
        print("ALL REFERENCES RESOLVE AGAINST THE LIVE RUNTIME ✅")


if __name__ == "__main__":
    main()
