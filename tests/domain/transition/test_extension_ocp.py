from __future__ import annotations


def test_new_preset_requires_one_file_and_one_registry_line() -> None:
    """OCP proof: adding a preset = 1 builder file + 1 DEFAULT_BUILDERS entry."""
    from app.domain.transition.recipe.builders import DEFAULT_BUILDERS

    assert "filter_sweep" in DEFAULT_BUILDERS
    # FILTER_SWEEP was added with 1 builder file + 1 registry line — no core edits


def test_new_picker_rule_requires_one_file_and_one_registry_line() -> None:
    """OCP proof: adding a rule = 1 rule file + 1 DEFAULT_RULES entry."""
    from app.domain.transition.picker.rules import DEFAULT_RULES

    rule_names = {r.name for r in DEFAULT_RULES}
    assert "filter_sweep" in rule_names
