import pytest

from app.core.entity_resolver import parse_entity_ref


def test_parse_int() -> None:
    ref = parse_entity_ref(42)
    assert ref.type == "id" and ref.value == 42


def test_parse_numeric_string() -> None:
    ref = parse_entity_ref("42")
    assert ref.type == "id" and ref.value == 42


def test_parse_ym_prefix() -> None:
    ref = parse_entity_ref("ym:12345")
    assert ref.type == "ym_id" and ref.value == "12345"


def test_parse_text_query() -> None:
    ref = parse_entity_ref("Aphex Twin - Xtal")
    assert ref.type == "query" and ref.value == "Aphex Twin - Xtal"


def test_parse_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_entity_ref("")


def test_parse_whitespace_raises() -> None:
    with pytest.raises(ValueError):
        parse_entity_ref("   ")
