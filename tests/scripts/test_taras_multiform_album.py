from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class _Track:
    slug: str
    title: str
    lyrics: str = "lyrics"


@pytest.mark.asyncio
async def test_taras_album_uses_provider_default_model(tmp_path, monkeypatch) -> None:
    from scripts import taras_multiform_album as script

    captured: list[dict] = []

    class _Adapter:
        async def read(self, *, entity, id=None, params=None):
            return {"usable_models": ["chirp-auk-turbo"]}

        async def write(self, *, entity, operation, params):
            if entity == "generation" and operation == "create":
                captured.append(params)
                return {"clip_ids": []}
            if entity == "playlist":
                return {"playlist_id": "playlist-1"}
            return {}

    monkeypatch.setattr(script, "OUT", tmp_path)
    monkeypatch.setattr(script, "build_suno_adapter", lambda: _Adapter())
    monkeypatch.setattr(script, "TARAS_ALBUM_TRACKS", [_Track(slug="one", title="One")])
    monkeypatch.setattr(
        script,
        "assemble_taras_album_prompt",
        lambda slug: (_Track(slug=slug, title="One"), "style", "negative"),
    )

    assert await script.main() == 0
    assert captured
    assert "model" not in captured[0]
