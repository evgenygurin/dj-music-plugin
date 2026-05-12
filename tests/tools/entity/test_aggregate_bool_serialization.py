"""Regression: ``entity_aggregate(distinct, field=<bool>)`` must surface
booleans as Python booleans, not coerce them to integers.

Round-10 manual probe: ``distinct(variable_tempo)`` returned ``[0]`` while
the same column queried via ``group_by`` returned ``{group: False, …}``.
Root cause was the ``AggregateResult.value`` Pydantic union — it listed
``list[int | float | str | None]`` but no ``bool``, and Pydantic v2
picks the first compatible type (bool is an int subclass) so ``False``
got coerced to ``0`` on the way out. Fix: ``bool`` added to the union
before ``int``.
"""

from __future__ import annotations

from app.schemas.tool_responses import AggregateResult


def test_bool_list_value_preserves_bool() -> None:
    """``[False, True]`` must round-trip as booleans, not as ``[0, 1]``."""
    result = AggregateResult(
        entity="track_features",
        operation="distinct",
        field="variable_tempo",
        value=[False, True],
    )
    assert result.value == [False, True]
    # Serialization shape matters too — JSON booleans, not ints.
    dumped = result.model_dump()
    assert dumped["value"] == [False, True]
    for v in dumped["value"]:
        assert isinstance(v, bool)


def test_int_list_value_still_works() -> None:
    """Sanity: distinct over int column still serialises as ints."""
    result = AggregateResult(
        entity="track_features",
        operation="distinct",
        field="key_code",
        value=[0, 1, 2, 3],
    )
    assert result.value == [0, 1, 2, 3]


def test_mixed_bool_int_list() -> None:
    """When the column is bool the result list contains only booleans; the
    union still admits int-only lists from other columns. Sanity check
    that both orderings serialise as expected."""
    bool_result = AggregateResult(entity="t", operation="distinct", field="b", value=[True])
    int_result = AggregateResult(entity="t", operation="distinct", field="i", value=[42])
    assert isinstance(bool_result.value, list)
    assert isinstance(bool_result.value[0], bool)
    assert int_result.value == [42]


def test_scalar_int_value_unchanged() -> None:
    """``count`` returns a scalar int — the bool union slot must not
    swallow it."""
    result = AggregateResult(entity="track", operation="count", value=5)
    assert result.value == 5
