"""SunoAdapter — generated set assets via the universal Provider protocol."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from app.providers.suno.client import SunoClient
from app.providers.suno.client_errors import AuthFailedError, SunoError
from app.shared.errors import ValidationError

_SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def _require(params: dict[str, Any], *keys: str, op: str) -> tuple[Any, ...]:
    missing = [k for k in keys if params.get(k) in (None, "")]
    if missing:
        raise ValidationError(
            f"suno {op!r} requires param(s) {missing!r}; got keys {sorted(params.keys()) or 'none'}"
        )
    return tuple(params[k] for k in keys)


def _safe_filename(name: str, max_len: int = 120) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", name).strip()
    return re.sub(r"\s+", " ", cleaned)[:max_len] or "suno-generation"


class SunoAdapter:
    name: str = "suno"

    entities_supported: ClassVar[tuple[str, ...]] = ("generation", "account")
    operations_supported: ClassVar[dict[str, tuple[str, ...]]] = {
        "generation": ("create", "cancel", "download"),
    }

    _ID_KEYS: ClassVar[tuple[str, ...]] = (
        "id",
        "generation_id",
        "generationId",
        "task_id",
        "taskId",
        "clip_id",
        "clipId",
    )

    def __init__(
        self,
        *,
        client: SunoClient,
        default_model: str = "",
        payload_mode: str = "suno_web",
        download_dir: Path | None = None,
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._payload_mode = payload_mode
        self._download_dir = download_dir or Path("/tmp/dj_suno")

    async def read(self, entity: str, id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        match entity:
            case "generation":
                if id is None:
                    raise ValidationError("suno generation read requires id")
                raw = await self._client.get_generation(id)
                return self._normalize_generation(raw)
            case "account":
                return await self._read_account()
            case _:
                raise ValidationError(f"unknown suno read entity: {entity}")

    async def write(self, entity: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        if entity != "generation":
            raise ValidationError(f"unknown suno write entity: {entity}")
        match operation:
            case "create":
                return await self._create_generation(params)
            case "cancel":
                (generation_id,) = _require(params, "generation_id", op="generation.cancel")
                raw = await self._client.cancel_generation(str(generation_id))
                return self._normalize_generation(raw)
            case "download":
                return await self._download_generation(params)
            case _:
                raise ValidationError(f"unknown suno generation operation: {operation}")

    def _capabilities(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "entities_supported": list(self.entities_supported),
            "operations_supported": {
                key: list(value) for key, value in self.operations_supported.items()
            },
        }

    async def _read_account(self) -> dict[str, Any]:
        """Capabilities + live balance/plan. Auth errors propagate; a provider
        without a billing endpoint (404 etc.) degrades to capabilities-only."""
        account = self._capabilities()
        try:
            info = await self._client.get_account()
        except AuthFailedError:
            raise
        except SunoError:
            info = {}
        for src, dst in (
            ("total_credits_left", "credits_left"),
            ("monthly_limit", "monthly_limit"),
            ("monthly_usage", "monthly_usage"),
            ("subscription_type", "subscription_type"),
            ("is_active", "is_active"),
        ):
            if src in info:
                account[dst] = info[src]
        models = info.get("models")
        if isinstance(models, list):
            account["usable_models"] = [
                m.get("external_key")
                for m in models
                if isinstance(m, dict) and m.get("can_use") and m.get("external_key")
            ]
        return account

    async def _create_generation(self, params: dict[str, Any]) -> dict[str, Any]:
        (prompt,) = _require(params, "prompt", op="generation.create")
        payload = self._build_generation_payload(prompt=str(prompt), params=params)
        raw = await self._client.create_generation(payload)
        normalized = self._normalize_generation(raw)
        normalized["request"] = {
            "title": params.get("title"),
            "tags": params.get("tags"),
            "duration_s": params.get("duration_s"),
            "bpm": params.get("bpm"),
            "key": params.get("key"),
        }
        return normalized

    def _build_generation_payload(self, *, prompt: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._payload_mode == "generic":
            payload = dict(params.get("extra") or {})
            for key in (
                "prompt",
                "title",
                "tags",
                "negative_tags",
                "instrumental",
                "duration_s",
                "bpm",
                "key",
                "lyrics",
                "style",
                "callback_url",
            ):
                if key in params and params[key] is not None:
                    payload[key] = params[key]
            if self._default_model and "model" not in payload:
                payload["model"] = self._default_model
            payload["prompt"] = prompt
            return payload

        payload = dict(params.get("extra") or {})
        lyrics = params.get("lyrics")
        tags = self._stringify_tags(params.get("tags") or params.get("style"))
        if lyrics:
            payload.setdefault("prompt", str(lyrics))
            payload.setdefault("tags", tags or prompt)
            if params.get("title"):
                payload.setdefault("title", str(params["title"]))
            metadata = dict(payload.get("metadata") or {})
            metadata.setdefault("create_mode", "CUSTOM")
            payload["metadata"] = metadata
        else:
            # Description mode. Suno's v2-web requires a NON-EMPTY params.prompt
            # (an empty string is reported as a missing field), so the free-form
            # description goes into prompt; gpt_description_prompt is kept for
            # builds that read it. make_instrumental keeps it wordless.
            payload.setdefault("gpt_description_prompt", prompt)
            payload.setdefault("prompt", prompt)
            if tags:
                payload.setdefault("tags", tags)
            if params.get("title"):
                payload.setdefault("title", str(params["title"]))
            metadata = dict(payload.get("metadata") or {})
            metadata.setdefault("create_mode", "SIMPLE")
            metadata.setdefault("lyrics_model", "default")
            payload["metadata"] = metadata

        if params.get("negative_tags"):
            payload.setdefault("negative_tags", self._stringify_tags(params["negative_tags"]))
        if "instrumental" in params:
            payload.setdefault("make_instrumental", bool(params["instrumental"]))
        else:
            payload.setdefault("make_instrumental", False)
        model = params.get("model") or self._default_model
        if model:
            payload.setdefault("mv", str(model))
        payload.setdefault("generation_type", "TEXT")
        for key in (
            "weirdness",
            "style_weight",
            "continue_clip_id",
            "continue_at",
            "infill_start_s",
            "infill_end_s",
            "persona_id",
            "audio_id",
            "callback_url",
        ):
            if key in params and params[key] is not None:
                payload.setdefault(key, params[key])
        return payload

    @staticmethod
    def _stringify_tags(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list | tuple | set):
            return ", ".join(str(item) for item in value if item is not None)
        return str(value)

    async def _download_generation(self, params: dict[str, Any]) -> dict[str, Any]:
        (generation_id,) = _require(params, "generation_id", op="generation.download")
        target_dir = Path(params.get("target_dir") or self._download_dir).expanduser()
        title = params.get("title") or f"suno-{generation_id}"
        suffix = str(params.get("suffix") or ".mp3")
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        filename = (
            params.get("filename") or f"{_safe_filename(str(title))} [{generation_id}]{suffix}"
        )
        dest = target_dir / _safe_filename(str(filename), max_len=180)
        path = await self._client.download_generation(
            str(generation_id),
            dest=dest,
            audio_url=params.get("audio_url"),
        )
        return {
            "generation_id": str(generation_id),
            "file_path": str(path),
            "file_size": path.stat().st_size,
        }

    async def search(self, query: str, type: str = "tracks", limit: int = 20) -> dict[str, Any]:
        raise ValidationError("suno provider does not support catalog search")

    async def download_audio(self, track_id: str, dest: Path | None = None) -> Path:
        target = dest if dest is not None else self._download_dir / f"{track_id}.mp3"
        return await self._client.download_generation(track_id, target)

    async def close(self) -> None:
        await self._client.close()

    @classmethod
    def _extract_id(cls, payload: dict[str, Any]) -> str | None:
        for key in cls._ID_KEYS:
            value = payload.get(key)
            if value is not None:
                return str(value)
        for container_key in ("generation", "data", "clip", "task"):
            value = payload.get(container_key)
            if isinstance(value, dict):
                found = cls._extract_id(value)
                if found:
                    return found
        return None

    _CLIP_CONTAINER_KEYS: ClassVar[tuple[str, ...]] = (
        "clips",
        "tracks",
        "generations",
        "data",
        "items",
        "results",
    )

    @classmethod
    def _extract_clip_ids(cls, payload: dict[str, Any]) -> list[str]:
        """Collect the per-clip ids from a create/status response.

        Suno's create returns a BATCH id plus a ``clips`` array whose members
        carry the real, pollable ids — ``/api/feed/v2/?ids=<batch>`` returns
        nothing, only ``ids=<clip>`` works. Callers must poll clip ids.
        """
        for container in cls._CLIP_CONTAINER_KEYS:
            value = payload.get(container)
            if isinstance(value, list):
                ids = [
                    str(cls._extract_id(i))
                    for i in value
                    if isinstance(i, dict) and cls._extract_id(i)
                ]
                if ids:
                    return ids
        return []

    @classmethod
    def _normalize_generation(cls, payload: dict[str, Any]) -> dict[str, Any]:
        batch_id = cls._extract_id(payload)
        clip_ids = cls._extract_clip_ids(payload)
        # generation_id must be pollable: prefer the first clip id, since the
        # batch id is not queryable via /api/feed/v2/.
        generation_id = clip_ids[0] if clip_ids else batch_id
        status = payload.get("status")
        for container_key in ("generation", "data", "clip", "task"):
            value = payload.get(container_key)
            if status is None and isinstance(value, dict):
                status = value.get("status")
        if status is None:
            clips = payload.get("clips")
            if isinstance(clips, list) and clips and isinstance(clips[0], dict):
                status = clips[0].get("status")
        audio_url = SunoClient.find_audio_url(payload)
        return {
            "generation_id": generation_id,
            "batch_id": batch_id,
            "clip_ids": clip_ids,
            "status": status,
            "audio_url": audio_url,
            "ready": bool(audio_url)
            or str(status).lower() in {"complete", "completed", "succeeded"},
            "raw": payload,
        }
