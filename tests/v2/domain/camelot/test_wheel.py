"""Tests for Camelot wheel logic (v2)."""

import pytest

from app.v2.domain.camelot.wheel import (
    camelot_distance,
    camelot_to_key_code,
    is_compatible,
    key_code_to_camelot,
)


class TestKeyCodeToCamelot:
    """key_code_to_camelot: convert key code (0-23) to Camelot notation."""

    def test_first_key(self) -> None:
        assert key_code_to_camelot(0) == "1A"

    def test_last_key(self) -> None:
        assert key_code_to_camelot(23) == "12B"

    def test_all_a_mode_keys(self) -> None:
        for code in range(0, 24, 2):
            result = key_code_to_camelot(code)
            assert result.endswith("A"), f"code {code} -> {result}, expected A mode"

    def test_all_b_mode_keys(self) -> None:
        for code in range(1, 24, 2):
            result = key_code_to_camelot(code)
            assert result.endswith("B"), f"code {code} -> {result}, expected B mode"

    def test_known_mappings(self) -> None:
        assert key_code_to_camelot(8) == "5A"
        assert key_code_to_camelot(9) == "5B"
        assert key_code_to_camelot(14) == "8A"
        assert key_code_to_camelot(15) == "8B"
        assert key_code_to_camelot(18) == "10A"
        assert key_code_to_camelot(19) == "10B"

    def test_invalid_code_negative(self) -> None:
        with pytest.raises(ValueError, match="key_code"):
            key_code_to_camelot(-1)

    def test_invalid_code_too_high(self) -> None:
        with pytest.raises(ValueError, match="key_code"):
            key_code_to_camelot(24)


class TestCamelotToKeyCode:
    def test_roundtrip_all_codes(self) -> None:
        for code in range(24):
            notation = key_code_to_camelot(code)
            assert camelot_to_key_code(notation) == code

    def test_known_notations(self) -> None:
        assert camelot_to_key_code("1A") == 0
        assert camelot_to_key_code("1B") == 1
        assert camelot_to_key_code("8A") == 14
        assert camelot_to_key_code("12B") == 23

    def test_invalid_notation_garbage(self) -> None:
        with pytest.raises(ValueError):
            camelot_to_key_code("XYZ")

    def test_invalid_notation_wrong_number(self) -> None:
        with pytest.raises(ValueError):
            camelot_to_key_code("13A")

    def test_invalid_notation_wrong_mode(self) -> None:
        with pytest.raises(ValueError):
            camelot_to_key_code("5C")

    def test_invalid_notation_zero(self) -> None:
        with pytest.raises(ValueError):
            camelot_to_key_code("0A")

    def test_invalid_notation_lowercase(self) -> None:
        with pytest.raises(ValueError):
            camelot_to_key_code("5a")

    def test_invalid_notation_empty(self) -> None:
        with pytest.raises(ValueError):
            camelot_to_key_code("")


class TestCamelotDistance:
    def test_same_key_distance_zero(self) -> None:
        assert camelot_distance(14, 14) == 0

    def test_adjacent_same_mode(self) -> None:
        assert camelot_distance(14, 16) == 1

    def test_adjacent_other_direction(self) -> None:
        assert camelot_distance(14, 12) == 1

    def test_mode_switch_same_position(self) -> None:
        assert camelot_distance(14, 15) == 1

    def test_wrap_around_12_to_1(self) -> None:
        assert camelot_distance(22, 0) == 1

    def test_wrap_around_b_mode(self) -> None:
        assert camelot_distance(23, 1) == 1

    def test_opposite_side_distance_6(self) -> None:
        assert camelot_distance(0, 12) == 6

    def test_two_steps_same_mode(self) -> None:
        assert camelot_distance(14, 18) == 2

    def test_one_step_plus_mode_switch(self) -> None:
        assert camelot_distance(14, 17) == 2

    def test_symmetry(self) -> None:
        for a in range(0, 24, 3):
            for b in range(0, 24, 5):
                assert camelot_distance(a, b) == camelot_distance(b, a)

    def test_max_distance_is_6(self) -> None:
        assert camelot_distance(0, 12) == 6

    def test_max_distance_with_mode_switch(self) -> None:
        dist = camelot_distance(0, 13)
        assert dist == 7

    def test_invalid_code_raises(self) -> None:
        with pytest.raises(ValueError):
            camelot_distance(-1, 0)
        with pytest.raises(ValueError):
            camelot_distance(0, 24)


class TestIsCompatible:
    def test_same_key_compatible(self) -> None:
        assert is_compatible(14, 14) is True

    def test_adjacent_compatible(self) -> None:
        assert is_compatible(14, 16) is True

    def test_mode_switch_compatible(self) -> None:
        assert is_compatible(14, 15) is True

    def test_two_steps_incompatible(self) -> None:
        assert is_compatible(14, 18) is False

    def test_wrap_around_compatible(self) -> None:
        assert is_compatible(22, 0) is True

    def test_far_apart_incompatible(self) -> None:
        assert is_compatible(0, 12) is False
