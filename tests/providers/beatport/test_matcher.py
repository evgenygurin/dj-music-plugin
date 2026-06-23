"""Beatport matcher unit tests — pure, no network."""

from __future__ import annotations

from app.providers.beatport.matcher import normalize_text, pick_best


def _cand(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "beatport_id": 1,
        "title": "Structure",
        "artists": ["Patrick Siech"],
        "bpm": 126,
        "length_ms": 508066,
        "isrc": None,
        "genre": "Techno (Peak Time / Driving)",
        "camelot": "5A",
    }
    base.update(kw)
    return base


def test_normalize_strips_mix_feat_accents() -> None:
    assert normalize_text("Strücture (Original Mix)") == "structure"
    assert normalize_text("Track feat. Someone") == "track"
    assert normalize_text("A & B - Title [Extended Mix]") == "a b title"


def test_high_confidence_needs_audio_confirmation() -> None:
    r = pick_best(
        candidates=[_cand()],
        title="Structure",
        artist="Patrick Siech",
        bpm=126.0,
        duration_ms=508000,
    )
    assert r.matched
    assert r.confidence == "high"
    assert r.beatport_id == 1
    assert r.track is not None and r.track["genre"].startswith("Techno")


def test_medium_when_text_only_no_audio() -> None:
    r = pick_best(candidates=[_cand()], title="Structure", artist="Patrick Siech")
    assert r.matched
    assert r.confidence == "medium"


def test_bpm_mismatch_drops_to_medium_not_high() -> None:
    r = pick_best(
        candidates=[_cand(bpm=140, length_ms=200000)],
        title="Structure",
        artist="Patrick Siech",
        bpm=126.0,
        duration_ms=508000,
    )
    # text is strong but no audio signal agrees → not high
    assert r.confidence == "medium"


def test_isrc_exact_is_high_even_with_weak_text() -> None:
    r = pick_best(
        candidates=[_cand(title="totally different", artists=["Nobody"], isrc="GB1234567890")],
        title="Structure",
        artist="Patrick Siech",
        isrc="gb1234567890",
    )
    assert r.confidence == "high"
    assert "isrc-exact" in r.reasons


def test_octave_bpm_still_confirms() -> None:
    r = pick_best(
        candidates=[_cand(bpm=126)],
        title="Structure",
        artist="Patrick Siech",
        bpm=63.0,  # half-time audio detection error
        duration_ms=508066,
    )
    assert r.confidence == "high"


def test_no_credible_match_returns_none() -> None:
    r = pick_best(
        candidates=[_cand(title="Something Unrelated", artists=["Other Person"])],
        title="Structure",
        artist="Patrick Siech",
    )
    assert not r.matched
    assert r.confidence in ("low", "none")


def test_empty_candidates() -> None:
    r = pick_best(candidates=[], title="X", artist="Y")
    assert not r.matched
    assert r.confidence == "none"
    assert r.beatport_id is None
