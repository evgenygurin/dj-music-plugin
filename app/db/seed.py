"""Reference-data seed: 24 Camelot keys + 4 provider rows.

Idempotent — safe to call on every startup.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.key import Key
from app.models.provider_metadata import Provider

# (key_code, pitch_class, mode, name, camelot)
# Minor keys → mode=0 (A series), major → mode=1 (B series).
_KEYS: tuple[tuple[int, int, int, str, str], ...] = (
    (0, 9, 0, "A minor", "8A"),
    (1, 4, 0, "E minor", "9A"),
    (2, 11, 0, "B minor", "10A"),
    (3, 6, 0, "F# minor", "11A"),
    (4, 1, 0, "C# minor", "12A"),
    (5, 8, 0, "G# minor", "1A"),
    (6, 3, 0, "D# minor", "2A"),
    (7, 10, 0, "A# minor", "3A"),
    (8, 5, 0, "F minor", "4A"),
    (9, 0, 0, "C minor", "5A"),
    (10, 7, 0, "G minor", "6A"),
    (11, 2, 0, "D minor", "7A"),
    (12, 0, 1, "C major", "8B"),
    (13, 7, 1, "G major", "9B"),
    (14, 2, 1, "D major", "10B"),
    (15, 9, 1, "A major", "11B"),
    (16, 4, 1, "E major", "12B"),
    (17, 11, 1, "B major", "1B"),
    (18, 6, 1, "F# major", "2B"),
    (19, 1, 1, "C# major", "3B"),
    (20, 8, 1, "G# major", "4B"),
    (21, 3, 1, "D# major", "5B"),
    (22, 10, 1, "A# major", "6B"),
    (23, 5, 1, "F major", "7B"),
)

_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("yandex_music", "Yandex Music"),
    ("spotify", "Spotify"),
    ("beatport", "Beatport"),
    ("soundcloud", "SoundCloud"),
)


async def seed_reference(session: AsyncSession) -> None:
    """Ensure all 24 keys + 4 provider rows exist (idempotent)."""
    existing_keys = {k for (k,) in (await session.execute(select(Key.key_code))).all()}
    for key_code, pitch_class, mode, name, camelot in _KEYS:
        if key_code not in existing_keys:
            session.add(
                Key(
                    key_code=key_code,
                    pitch_class=pitch_class,
                    mode=mode,
                    name=name,
                    camelot=camelot,
                )
            )

    existing_provs = {c for (c,) in (await session.execute(select(Provider.code))).all()}
    for code, display in _PROVIDERS:
        if code not in existing_provs:
            session.add(Provider(code=code, display_name=display))

    await session.flush()
