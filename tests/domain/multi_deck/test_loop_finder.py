from __future__ import annotations

from app.domain.multi_deck.loop_finder import find_loops

SECTIONS = [
    {
        "section_type": 2,
        "start_ms": 32000,
        "end_ms": 64000,
        "energy": 0.8,
        "stem_energy": {"vocals": 0.05, "drums": 0.9},
    },
    {
        "section_type": 3,
        "start_ms": 64000,
        "end_ms": 96000,
        "energy": 0.3,
        "stem_energy": {"vocals": 0.6, "drums": 0.1},
    },
]


def test_find_loops() -> None:
    result = find_loops(SECTIONS, 128.0, 1, min_bars=4)
    assert len(result["loops"]) == 1
    assert result["loops"][0]["section_type"] == 2


def test_find_loops_exclude_vocals() -> None:
    sections = [
        {
            "section_type": 2,
            "start_ms": 32000,
            "end_ms": 64000,
            "energy": 0.8,
            "stem_energy": {"vocals": 0.8, "drums": 0.5},
        }
    ]
    result = find_loops(sections, 120.0, 1, min_bars=4)
    assert result["loops"] == []


def test_find_loops_bar_range() -> None:
    sections = [
        {
            "section_type": 2,
            "start_ms": 0,
            "end_ms": 4000,
            "energy": 0.8,
            "stem_energy": {"vocals": 0.05},
        },
        {
            "section_type": 3,
            "start_ms": 4000,
            "end_ms": 32000,
            "energy": 0.9,
            "stem_energy": {"vocals": 0.1},
        },
    ]
    result = find_loops(sections, 128.0, 1, min_bars=4, max_bars=16)
    assert all(4 <= loop["bars"] <= 16 for loop in result["loops"])


def test_find_loops_default_bpm() -> None:
    result = find_loops(SECTIONS[:1], None, 1, min_bars=4)
    assert result["bpm"] == 120.0


def test_find_loops_energy_stability_threshold() -> None:
    sections = [
        {
            "section_type": 4,
            "start_ms": 32000,
            "end_ms": 64000,
            "energy": 0.3,
            "stem_energy": {"vocals": 0.1},
        }
    ]
    result = find_loops(sections, 128.0, 1, min_bars=4, min_energy_stability=0.5)
    assert result["loops"] == []
    result2 = find_loops(sections, 128.0, 1, min_bars=4, min_energy_stability=0.2)
    assert len(result2["loops"]) == 1
