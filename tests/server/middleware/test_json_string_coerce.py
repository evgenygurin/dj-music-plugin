"""Unit tests for ``_coerce_args_against_schema`` (the helper inside
``JsonStringCoerceMiddleware``).

Closes the v1.0.10-v1.0.13 transport-asymmetry bug class at the
architecture level: any tool whose ``inputSchema`` declares an arg as
``type: array`` or ``type: object`` will have a stringified payload
parsed back to a native dict/list before Pydantic validation runs.
"""

from __future__ import annotations

from app.server.middleware.json_string_coerce import _coerce_args_against_schema


def test_coerces_array_string_to_list() -> None:
    schema = {"type": "object", "properties": {"track_ids": {"type": "array"}}}
    args = {"track_ids": "[1, 2, 3]"}
    assert _coerce_args_against_schema(args, schema) == {"track_ids": [1, 2, 3]}


def test_coerces_object_string_to_dict() -> None:
    schema = {"type": "object", "properties": {"filters": {"type": "object"}}}
    args = {"filters": '{"bpm__gte": 120}'}
    assert _coerce_args_against_schema(args, schema) == {"filters": {"bpm__gte": 120}}


def test_native_types_pass_through() -> None:
    schema = {"type": "object", "properties": {"track_ids": {"type": "array"}}}
    args = {"track_ids": [1, 2, 3]}
    assert _coerce_args_against_schema(args, schema) == {"track_ids": [1, 2, 3]}


def test_invalid_json_left_untouched() -> None:
    """Pydantic should produce a clean error downstream, not the middleware."""
    schema = {"type": "object", "properties": {"track_ids": {"type": "array"}}}
    args = {"track_ids": "not json"}
    assert _coerce_args_against_schema(args, schema) == {"track_ids": "not json"}


def test_string_typed_arg_not_coerced() -> None:
    """type=string args must be left alone even if they look like JSON."""
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    args = {"name": '{"a":1}'}
    assert _coerce_args_against_schema(args, schema) == {"name": '{"a":1}'}


def test_anyof_with_array_branch() -> None:
    """Common in fastmcp tools: ``Annotated[list[int] | None, ...]``."""
    schema = {
        "type": "object",
        "properties": {"track_ids": {"anyOf": [{"type": "array"}, {"type": "null"}]}},
    }
    args = {"track_ids": "[1, 2]"}
    assert _coerce_args_against_schema(args, schema) == {"track_ids": [1, 2]}


def test_no_schema_returns_args_unchanged() -> None:
    args = {"x": "[1, 2]"}
    assert _coerce_args_against_schema(args, None) == args


def test_arg_not_in_schema_left_alone() -> None:
    schema = {"type": "object", "properties": {"a": {"type": "array"}}}
    args = {"b": "[1, 2]"}
    assert _coerce_args_against_schema(args, schema) == {"b": "[1, 2]"}


def test_empty_string_not_coerced() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "array"}}}
    args = {"x": ""}
    assert _coerce_args_against_schema(args, schema) == {"x": ""}


def test_string_starting_with_brace_but_invalid_json_left_alone() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "object"}}}
    args = {"x": "{not json"}
    assert _coerce_args_against_schema(args, schema) == {"x": "{not json"}
