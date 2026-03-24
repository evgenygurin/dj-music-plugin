"""Tests for Camelot wheel logic."""

import pytest

from app.core.camelot import (
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
        """Even codes map to A mode."""
        for code in range(0, 24, 2):
            result = key_code_to_camelot(code)
            assert result.endswith("A"), f"code {code} -> {result}, expected A mode"

    def test_all_b_mode_keys(self) -> None:
        """Odd codes map to B mode."""
        for code in range(1, 24, 2):
            result = key_code_to_camelot(code)
            assert result.endswith("B"), f"code {code} -> {result}, expected B mode"

    def test_known_mappings(self) -> None:
        """Spot-check several known mappings from CAMELOT_KEYS."""
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
    """camelot_to_key_code: reverse mapping from notation to code."""

    def test_roundtrip_all_codes(self) -> None:
        """Every code survives a roundtrip through notation and back."""
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
    """camelot_distance: distance on Camelot wheel (0-6)."""

    def test_same_key_distance_zero(self) -> None:
        """Same key code -> distance 0."""
        assert camelot_distance(14, 14) == 0

    def test_adjacent_same_mode(self) -> None:
        """8A (14) -> 9A (16): one step on wheel, same mode -> distance 1."""
        assert camelot_distance(14, 16) == 1

    def test_adjacent_other_direction(self) -> None:
        """8A (14) -> 7A (12): one step on wheel, same mode -> distance 1."""
        assert camelot_distance(14, 12) == 1

    def test_mode_switch_same_position(self) -> None:
        """8A (14) -> 8B (15): same position, mode switch -> distance 1."""
        assert camelot_distance(14, 15) == 1

    def test_wrap_around_12_to_1(self) -> None:
        """12A (22) -> 1A (0): adjacent on wheel (wraps) -> distance 1."""
        assert camelot_distance(22, 0) == 1

    def test_wrap_around_b_mode(self) -> None:
        """12B (23) -> 1B (1): adjacent on wheel (wraps) -> distance 1."""
        assert camelot_distance(23, 1) == 1

    def test_opposite_side_distance_6(self) -> None:
        """1A (0) -> 7A (12): 6 steps on wheel, same mode -> distance 6."""
        assert camelot_distance(0, 12) == 6

    def test_two_steps_same_mode(self) -> None:
        """8A (14) -> 10A (18): 2 steps on wheel -> distance 2."""
        assert camelot_distance(14, 18) == 2

    def test_one_step_plus_mode_switch(self) -> None:
        """8A (14) -> 9B (17): 1 step + mode switch -> distance 2."""
        assert camelot_distance(14, 17) == 2

    def test_symmetry(self) -> None:
        """Distance is symmetric: d(a,b) == d(b,a)."""
        for a in range(0, 24, 3):
            for b in range(0, 24, 5):
                assert camelot_distance(a, b) == camelot_distance(b, a)

    def test_max_distance_is_6(self) -> None:
        """Maximum distance on wheel is 6 (half of 12) for same mode."""
        # 1A (0) -> 7A (12): distance 6
        assert camelot_distance(0, 12) == 6

    def test_max_distance_with_mode_switch(self) -> None:
        """6 steps + mode switch -> 7, but max on wheel is 6 so distance = 6+1=7?
        Actually distance is capped by min(steps, 12-steps), so max wheel = 6.
        With mode switch: 6 + 1 = 7. Let's verify the actual max."""
        # 1A (0) -> 7B (13): 6 steps + mode switch
        dist = camelot_distance(0, 13)
        assert dist == 7

    def test_invalid_code_raises(self) -> None:
        with pytest.raises(ValueError):
            camelot_distance(-1, 0)
        with pytest.raises(ValueError):
            camelot_distance(0, 24)


class TestIsCompatible:
    """is_compatible: True if camelot_distance <= 1."""

    def test_same_key_compatible(self) -> None:
        assert is_compatible(14, 14) is True

    def test_adjacent_compatible(self) -> None:
        assert is_compatible(14, 16) is True  # 8A -> 9A

    def test_mode_switch_compatible(self) -> None:
        assert is_compatible(14, 15) is True  # 8A -> 8B

    def test_two_steps_incompatible(self) -> None:
        assert is_compatible(14, 18) is False  # 8A -> 10A, distance 2

    def test_wrap_around_compatible(self) -> None:
        assert is_compatible(22, 0) is True  # 12A -> 1A

    def test_far_apart_incompatible(self) -> None:
        assert is_compatible(0, 12) is False  # 1A -> 7A, distance 6
