"""Regression: `_session_id` must not raise on stateless context.

FastMCP v3 Context exposes `session_id` as a property that raises
RuntimeError outside an active MCP session. `getattr(ctx, "session_id",
default)` does NOT shield against this — getattr propagates property
exceptions instead of using the default. Without the wrapper, every
`session://*` resource read via REST/in-process returns 500.
"""

from __future__ import annotations

from app.resources.session import _session_id


class _StatefulFCtx:
    @property
    def session_id(self) -> str:
        return "real-session-abc"


class _StatelessFCtx:
    @property
    def session_id(self) -> str:
        raise RuntimeError("session_id is not available because no session exists")


class _NoAttrFCtx:
    pass  # no session_id attribute at all


def test_session_id_returns_real_id_when_stateful() -> None:
    assert _session_id(_StatefulFCtx()) == "real-session-abc"  # type: ignore[arg-type]


def test_session_id_returns_anonymous_when_property_raises() -> None:
    assert _session_id(_StatelessFCtx()) == "anonymous"  # type: ignore[arg-type]


def test_session_id_returns_anonymous_when_attr_missing() -> None:
    assert _session_id(_NoAttrFCtx()) == "anonymous"  # type: ignore[arg-type]
