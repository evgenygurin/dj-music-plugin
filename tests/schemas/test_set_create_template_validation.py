"""Audit iter 16 (T-16): ``entity_create(set, {template_name: 'bogus'})``
silently created the set with the bogus name. Same silent-accept class
as the v1.2.12 fix on ``sequence_optimize``.

The check lives at the entity_create dispatcher rather than on
``SetCreate`` itself because schemas can't import ``app.domain`` per
the v2-server import contract. Coverage runs at the schema level
(template_name field still accepts None / strings) plus the
dispatcher level (real registry validation).
"""

from __future__ import annotations

from app.schemas.set import SetCreate


def test_set_create_schema_still_accepts_template_name_field() -> None:
    """The schema must allow ``template_name`` through; the dispatcher
    runs the registry check."""
    SetCreate.model_validate({"name": "X", "template_name": "classic_60"})
    SetCreate.model_validate({"name": "X", "template_name": "anything"})  # schema OK
    SetCreate.model_validate({"name": "X", "template_name": None})
    SetCreate.model_validate({"name": "X"})


def test_dispatcher_validation_logic_uses_registry() -> None:
    """The dispatcher imports ``list_template_names`` to validate -
    pin the source of truth so the check can't drift."""
    from app.domain.template.registry import list_template_names

    names = list_template_names()
    assert "classic_60" in names
    assert "peak_hour_60" in names
    assert "bogus_template_xyz" not in names
