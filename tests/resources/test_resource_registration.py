"""Resource metadata constants + registration tests."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

from app.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)

# Complete inventory of resource URIs expected to be registered by FSP.
# Separated into static (no {}) and templates for distinct list_resources()
# vs list_resource_templates() checks.
EXPECTED_STATIC_URIS: frozenset[str] = frozenset(
    {
        "schema://entities",
        "schema://providers",
        "session://set-draft",
        "session://tool-history",
        "reference://camelot",
        "reference://subgenres",
        "reference://templates",
        "reference://audit_rules",
        "reference://render/defaults",
    }
)

EXPECTED_TEMPLATE_URIS: frozenset[str] = frozenset(
    {
        "schema://entities/{entity}",
        "schema://providers/{name}",
        "session://energy-trend{?limit}",
        "local://tracks/{id}",
        "local://tracks/{id}/features",
        "local://tracks/{id}/audit",
        "local://tracks/{id}/suggest_next{?limit,energy_direction}",
        "local://tracks/{id}/suggest_replacement/{set_id}/{position}",
        "local://playlists/{id}{?include_tracks}",
        "local://playlists/{id}/audit",
        "local://sets/{id}/{view}",
        "local://sets/{id}/cheatsheet{?version}",
        "local://sets/{id}/design/data{?version}",
        "local://sets/{id}/narrative",
        "local://sets/{id}/review{?version}",
        "local://sets/{id}/versions/compare/{a}/{b}",
        "local://transition/{from_id}/{to_id}/score",
        "local://transition/{from_id}/{to_id}/explain",
        "local://transition_history/best_pairs{?track_id,limit}",
        "local://transition_history/history{?limit,track_id}",
        "local://render/jobs/{job_id}/status",
        "local://render/jobs/{job_id}/diagnostics",
        "local://render/{version_id}/beatgrid",
        "local://render/{version_id}/timeline",
        "local://tracks/{id}/deep_features{?stem}",
        "local://tracks/{id}/structure",
        "local://tracks/{id}/waveform{?stem}",
    }
)

ALL_EXPECTED_URIS: frozenset[str] = EXPECTED_STATIC_URIS | EXPECTED_TEMPLATE_URIS


def test_annotations_read_only_is_dict() -> None:
    assert isinstance(ANNOTATIONS_READ_ONLY, dict)
    assert ANNOTATIONS_READ_ONLY["readOnlyHint"] is True
    assert ANNOTATIONS_READ_ONLY["idempotentHint"] is True


def test_resource_meta_has_version() -> None:
    assert "version" in RESOURCE_META
    assert isinstance(RESOURCE_META["version"], str)


def test_json_dump_returns_string() -> None:
    out = json_dump({"a": 1, "b": [2, 3]})
    assert isinstance(out, str)
    assert '"a":1' in out.replace(" ", "")


def test_json_dump_handles_nested() -> None:
    out = json_dump({"nested": {"list": [1, 2, {"k": "v"}]}})
    assert "nested" in out and "list" in out and "v" in out


def test_json_dump_preserves_unicode() -> None:
    out = json_dump({"name": "Детройт"})
    assert "Детройт" in out


def _import_all_resource_modules() -> list[str]:
    """Recursively import every submodule under ``app.resources`` so that
    ``@resource`` decorators execute. Returns the list of imported dotted names.
    """
    import app.resources as pkg

    imported: list[str] = []
    for mod in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        if mod.name.endswith("._shared"):
            continue
        importlib.import_module(mod.name)
        imported.append(mod.name)
    return imported


def test_all_resource_modules_importable() -> None:
    """Every resource module must import cleanly (no syntax / dep errors)."""
    imported = _import_all_resource_modules()
    # Sanity: at least the 8 expected files
    assert len(imported) >= 8
    # The reference package members must be present
    assert any(m.endswith(".reference.camelot") for m in imported)
    assert any(m.endswith(".reference.subgenres") for m in imported)
    assert any(m.endswith(".reference.templates") for m in imported)
    assert any(m.endswith(".reference.audit_rules") for m in imported)


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Phase 5 server wiring: build_mcp_app_for_tests not yet implemented",
    strict=False,
)
async def test_all_expected_uris_registered() -> None:
    """Every expected resource URI is registered on the FastMCP app.

    Implementation body is complete so flipping xfail -> pass in Phase 5 is
    trivial: once ``build_mcp_app_for_tests`` exists and composes the
    FileSystemProvider pointed at ``app/v2/resources/``, this test will
    verify both static URIs (``list_resources``) and parametric templates
    (``list_resource_templates``).
    """
    from app.server.app import build_mcp_app_for_tests  # type: ignore[import-not-found]

    mcp = await build_mcp_app_for_tests()

    static = {r.uri for r in await mcp.list_resources()}
    templates = {t.uri_template for t in await mcp.list_resource_templates()}

    missing_static = EXPECTED_STATIC_URIS - static
    missing_templates = EXPECTED_TEMPLATE_URIS - templates
    assert not missing_static, f"Missing static resources: {missing_static}"
    assert not missing_templates, f"Missing templates: {missing_templates}"

    # Sanity: tags contain 'core' and annotations are read-only for every
    # registered resource. This catches drift in shared constants.
    for r in await mcp.list_resources():
        assert "core" in (r.tags or set())
        annotations = getattr(r, "annotations", None) or {}
        assert annotations.get("readOnlyHint", False) is True


def test_expected_uri_inventory_is_consistent() -> None:
    """The EXPECTED_*_URIS constants must cover every @resource URI literal
    actually declared in the source tree. Prevents silent drift — if someone
    adds a new resource, they must extend the inventory here.
    """
    import re
    from pathlib import Path

    resources_root = Path(__file__).resolve().parents[2] / "app" / "resources"
    pattern = re.compile(r'@resource\(\s*"([^"]+)"')
    found: set[str] = set()
    for py in resources_root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            found.add(match.group(1))

    missing = found - ALL_EXPECTED_URIS
    extra = ALL_EXPECTED_URIS - found
    assert not missing, f"Registered but not in expected inventory: {missing}"
    assert not extra, f"In expected inventory but not registered: {extra}"
