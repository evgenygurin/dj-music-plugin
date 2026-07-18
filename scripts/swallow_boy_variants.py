#!/usr/bin/env python3
"""Generate 10 short Swallow Boy voice variants on Suno v5.5 Pro.

The script stops cleanly when session auth is expired and prints the exact
refresh command instead of throwing a long traceback.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.domain.suno_voice.swallow_boy import (
    SWALLOW_BOY_REFERENCE_URL,
    SWALLOW_BOY_VARIANTS,
    assemble_swallow_boy_prompt,
)
from app.providers.suno.client_errors import AuthFailedError, RateLimitedError
from app.server.lifespan import build_suno_adapter

OUT_DIR = Path("suno_out/rimjoba/swallow_boy")
MODEL = "chirp-fenix"


async def _preflight(adapter: object) -> dict:
    return await adapter.read(entity="account", id=None, params={})


async def _with_retry(
    call: Callable[[], Awaitable[Any]], *, attempts: int = 6, delay_s: float = 6.0
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except RateLimitedError as exc:
            last_error = exc
            if attempt == attempts:
                raise
            await asyncio.sleep(delay_s * attempt)
    assert last_error is not None
    raise last_error


async def _read_generation_ready(adapter: object, clip_id: str, *, attempts: int = 10) -> dict:
    for attempt in range(1, attempts + 1):
        clip = await _with_retry(lambda: adapter.read(entity="generation", id=clip_id, params={}))
        if clip.get("audio_url"):
            return clip
        await asyncio.sleep(min(3 * attempt, 12))
    return await _with_retry(lambda: adapter.read(entity="generation", id=clip_id, params={}))


def _write_outputs(results: list[dict]) -> None:
    summary_path = OUT_DIR / "SUMMARY.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Swallow Boy — 10 short variants",
        "",
        f"Reference: {SWALLOW_BOY_REFERENCE_URL}",
        f"Model: `{MODEL}`",
        "",
        "| # | Variant | Suno | Local | Duration |",
        "|---|---------|------|-------|----------|",
    ]
    for idx, result in enumerate(results, start=1):
        first = result["clips"][0] if result["clips"] else {}
        lines.append(
            "| {idx} | `{variant}` | {suno} | {local} | {dur} |".format(
                idx=idx,
                variant=result["variant_id"],
                suno=f"[clip]({first.get('suno_url')})" if first.get("suno_url") else "-",
                local=Path(first["local_path"]).name if first.get("local_path") else "-",
                dur=first.get("duration") or "-",
            )
        )
    (OUT_DIR / "LISTEN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _download_clip(adapter: object, clip_id: str, title: str) -> str | None:
    clip = await _read_generation_ready(adapter, clip_id)
    audio_url = clip.get("audio_url")
    if not audio_url:
        return None
    downloaded = await _with_retry(
        lambda: adapter.write(
            entity="generation",
            operation="download",
            params={
                "generation_id": clip_id,
                "target_dir": str(OUT_DIR),
                "title": title,
                "audio_url": audio_url,
            },
        )
    )
    return downloaded.get("file_path") or downloaded.get("path") or downloaded.get("local_path")


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    adapter = build_suno_adapter()
    if adapter is None:
        print("Suno adapter is disabled. Check DJ_SUNO_* credentials.")
        return 2

    try:
        account = await _preflight(adapter)
    except AuthFailedError:
        print("Suno session auth expired.")
        print("Refresh with: uv run python scripts/suno_refresh_token.py")
        return 3

    usable_models = account.get("usable_models") or []
    if MODEL not in usable_models:
        print(f"Model {MODEL!r} is not available. Usable models: {usable_models}")
        return 4

    results = []
    for idx, variant in enumerate(SWALLOW_BOY_VARIANTS, start=1):
        prompt = assemble_swallow_boy_prompt(variant.variant_id)
        title = f"Swallow Boy V{idx:02d} {variant.title_hint}"
        try:
            created = await _with_retry(
                lambda params={
                    "prompt": variant.lyrics,
                    "lyrics": variant.lyrics,
                    "title": title,
                    "tags": prompt.style,
                    "style": prompt.style,
                    "negative_tags": prompt.negative_tags,
                    "instrumental": False,
                    "model": MODEL,
                }: adapter.write(
                    entity="generation",
                    operation="create",
                    params=params,
                )
            )
        except AuthFailedError:
            print("Suno requires CAPTCHA/challenge for this account or IP.")
            print("Open Suno in the browser, complete the challenge, then rerun:")
            print("uv run python scripts/swallow_boy_variants.py")
            _write_outputs(results)
            return 5
        clip_ids = list(created.get("clip_ids") or [])
        if not clip_ids and created.get("generation_id"):
            clip_ids = [created["generation_id"]]

        clips = []
        for clip_id in clip_ids[:2]:
            clip_id = str(clip_id)
            downloaded = await _download_clip(
                adapter,
                clip_id,
                f"{variant.variant_id}_{clip_id[:8]}",
            )
            clip = await _read_generation_ready(adapter, clip_id)
            clips.append(
                {
                    "clip_id": clip_id,
                    "suno_url": f"https://suno.com/song/{clip_id}",
                    "audio_url": clip.get("audio_url"),
                    "duration": clip.get("raw", {}).get("metadata", {}).get("duration")
                    if isinstance(clip.get("raw"), dict)
                    else None,
                    "local_path": downloaded,
                }
            )

        results.append(
            {
                "variant_id": variant.variant_id,
                "title_hint": variant.title_hint,
                "model": MODEL,
                "reference_url": SWALLOW_BOY_REFERENCE_URL,
                "style": prompt.style,
                "negative_tags": prompt.negative_tags,
                "clips": clips,
            }
        )
        _write_outputs(results)

    summary_path = OUT_DIR / "SUMMARY.json"
    _write_outputs(results)
    print(f"Generated {len(results)} variants -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
