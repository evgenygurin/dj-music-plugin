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


# ── resolve_track_refs tests ─────────────────────────


async def test_resolve_small_ids(seeded_db) -> None:  # type: ignore[no-untyped-def]
    """Small IDs (< 1M) pass through as local DB IDs."""
    from app.core.entity_resolver import resolve_track_refs

    result = await resolve_track_refs([1, 2, 3], seeded_db)
    assert result == [1, 2, 3]


async def test_resolve_ym_ids(seeded_db) -> None:  # type: ignore[no-untyped-def]
    """Large IDs (> 1M) are looked up as YM external IDs."""

    from app.core.entity_resolver import resolve_track_refs
    from app.models.track import Track, TrackExternalId

    # Create track with YM external ID
    track = Track(title="Test Track", status=0, duration_ms=300000)
    seeded_db.add(track)
    await seeded_db.flush()

    ext_id = TrackExternalId(track_id=track.id, platform="yandex_music", external_id="129142659")
    seeded_db.add(ext_id)
    await seeded_db.flush()

    # Resolve — large int should map to local DB track ID
    result = await resolve_track_refs([129142659], seeded_db)
    assert result == [track.id]


async def test_resolve_ym_prefix(seeded_db) -> None:  # type: ignore[no-untyped-def]
    """'ym:12345' prefix resolves via TrackExternalId."""
    from app.core.entity_resolver import resolve_track_refs
    from app.models.track import Track, TrackExternalId

    track = Track(title="Prefixed Track", status=0, duration_ms=200000)
    seeded_db.add(track)
    await seeded_db.flush()

    ext_id = TrackExternalId(track_id=track.id, platform="yandex_music", external_id="99999")
    seeded_db.add(ext_id)
    await seeded_db.flush()

    result = await resolve_track_refs(["ym:99999"], seeded_db)
    assert result == [track.id]


async def test_resolve_missing_ym_id_skipped(seeded_db) -> None:  # type: ignore[no-untyped-def]
    """Unresolvable YM IDs are skipped (not raised)."""
    from app.core.entity_resolver import resolve_track_refs

    result = await resolve_track_refs([999999999], seeded_db)
    assert result == []


async def test_resolve_mixed_refs(seeded_db) -> None:  # type: ignore[no-untyped-def]
    """Mix of local IDs and YM IDs resolves correctly."""
    from app.core.entity_resolver import resolve_track_refs
    from app.models.track import Track, TrackExternalId

    track = Track(title="Mixed Test", status=0, duration_ms=300000)
    seeded_db.add(track)
    await seeded_db.flush()

    ext_id = TrackExternalId(track_id=track.id, platform="yandex_music", external_id="5555555")
    seeded_db.add(ext_id)
    await seeded_db.flush()

    result = await resolve_track_refs([1, 5555555, 2], seeded_db)
    assert result == [1, track.id, 2]
