"""Camelot Wheel logic for harmonic mixing compatibility.

Provides conversion between key codes (0-23) and Camelot notation (1A-12B),
distance calculation on the Camelot wheel, and compatibility checks.

Key code layout:
    Even codes (0,2,...,22) = A mode (minor keys)
    Odd codes  (1,3,...,23) = B mode (major keys)
    Wheel position = (code // 2) + 1  (range 1-12)
"""

from app.v2.shared.constants import CAMELOT_KEYS, KEY_CODE_MAX, KEY_CODE_MIN

# Reverse mapping: notation -> key_code (built once at import time)
_NOTATION_TO_CODE: dict[str, int] = {
    notation: code for code, (notation, _name) in CAMELOT_KEYS.items()
}

_WHEEL_SIZE = 12


def _validate_key_code(code: int) -> None:
    """Raise ValueError if code is outside 0-23."""
    if code < KEY_CODE_MIN or code > KEY_CODE_MAX:
        msg = f"key_code must be {KEY_CODE_MIN}-{KEY_CODE_MAX}, got {code}"
        raise ValueError(msg)


def key_code_to_camelot(code: int) -> str:
    """Convert a key code (0-23) to Camelot notation (e.g. '8A', '12B').

    Args:
        code: Integer key code in range 0-23.

    Returns:
        Camelot notation string.

    Raises:
        ValueError: If code is not in 0-23.
    """
    _validate_key_code(code)
    notation, _name = CAMELOT_KEYS[code]
    return notation


def camelot_to_key_code(notation: str) -> int:
    """Convert Camelot notation (e.g. '8A', '12B') to a key code (0-23).

    Args:
        notation: Camelot notation string like '1A' through '12B'.

    Returns:
        Integer key code in range 0-23.

    Raises:
        ValueError: If notation is not a valid Camelot string.
    """
    try:
        return _NOTATION_TO_CODE[notation]
    except KeyError:
        msg = f"Invalid Camelot notation: {notation!r}"
        raise ValueError(msg) from None


def camelot_distance(code_a: int, code_b: int) -> int:
    """Calculate distance between two keys on the Camelot wheel.

    Distance = minimum wheel steps (clockwise or counterclockwise)
               + 1 if modes differ (A vs B).

    Range: 0 (same key) to 7 (opposite side + mode switch).

    Args:
        code_a: First key code (0-23).
        code_b: Second key code (0-23).

    Returns:
        Integer distance (0-7).

    Raises:
        ValueError: If either code is not in 0-23.
    """
    _validate_key_code(code_a)
    _validate_key_code(code_b)

    pos_a = (code_a // 2) + 1
    pos_b = (code_b // 2) + 1
    mode_a = code_a % 2  # 0 = A, 1 = B
    mode_b = code_b % 2

    # Shortest path around the 12-position wheel
    raw_diff = abs(pos_a - pos_b)
    wheel_dist = min(raw_diff, _WHEEL_SIZE - raw_diff)

    # Mode penalty: +1 if switching between A and B
    mode_penalty = 0 if mode_a == mode_b else 1

    return wheel_dist + mode_penalty


def is_compatible(code_a: int, code_b: int) -> bool:
    """Check if two keys are harmonically compatible (distance <= 1).

    Compatible transitions:
        - Same key (distance 0)
        - Adjacent on wheel, same mode (distance 1)
        - Same position, different mode (distance 1)

    Args:
        code_a: First key code (0-23).
        code_b: Second key code (0-23).

    Returns:
        True if the keys are compatible for harmonic mixing.
    """
    return camelot_distance(code_a, code_b) <= 1
