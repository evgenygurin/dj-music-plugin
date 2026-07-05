"""SunoAdapter — Suno generation via the universal Provider protocol.

Two surfaces share one adapter:

* **session** (browser Suno web) — the default; exposes ``generation``
  (create/cancel/download) + ``account``. Unchanged legacy behaviour.
* **sunoapi** (api.sunoapi.org, ``api_key`` mode) — full sunoapi.org REST
  surface: every documented generate variant, lyrics, WAV, stem separation,
  MIDI, video, cover art, persona, style boost, custom voice, and file upload.
  Gated on ``payload_mode == "sunoapi"`` — these endpoints do not exist on the
  browser host, so calling them in session mode raises a typed error.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from app.providers.suno import endpoints, endpoints_web
from app.providers.suno.client import SunoClient
from app.providers.suno.client_errors import AuthFailedError, SunoError
from app.providers.suno.endpoints import Endpoint, pull_field
from app.providers.suno.endpoints_web import WebWrite, build_web_body
from app.shared.errors import ValidationError

_SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_SUNOAPI_MODELS = {"V4", "V4_5", "V4_5PLUS", "V4_5ALL", "V5", "V5_5"}


def _merge_ops(*sources: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Union of entity -> operations across surfaces (order-preserving)."""
    merged: dict[str, list[str]] = {}
    for src in sources:
        for entity, ops in src.items():
            bucket = merged.setdefault(entity, [])
            for op in ops:
                if op not in bucket:
                    bucket.append(op)
    return {k: tuple(v) for k, v in merged.items()}


# Full advertised surface = union of the sunoapi.org + browser-web surfaces.
_ALL_ENTITIES: tuple[str, ...] = tuple(
    dict.fromkeys((*endpoints.sunoapi_entities(), *endpoints_web.suno_web_entities()))
)
_ALL_OPERATIONS: dict[str, tuple[str, ...]] = _merge_ops(
    endpoints.sunoapi_operations(), endpoints_web.suno_web_operations()
)


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

    # Class-level defaults advertise the FULL capability surface (union of the
    # sunoapi.org + browser-web surfaces) for schema introspection + prompt
    # content-correctness tests. Each instance narrows these in __init__ to
    # match its runtime payload_mode.
    entities_supported: tuple[str, ...] = _ALL_ENTITIES
    operations_supported: dict[str, tuple[str, ...]] = _ALL_OPERATIONS

    _ID_KEYS: ClassVar[tuple[str, ...]] = (
        "id",
        "generation_id",
        "generationId",
        "task_id",
        "taskId",
        "audioId",
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
        callback_url: str = "",
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._payload_mode = payload_mode
        self._download_dir = download_dir or Path("/tmp/dj_suno")
        self._callback_url = callback_url
        if payload_mode == "sunoapi":
            self.entities_supported = endpoints.sunoapi_entities()
            self.operations_supported = endpoints.sunoapi_operations()
        elif payload_mode == "suno_web":
            self.entities_supported = endpoints_web.suno_web_entities()
            self.operations_supported = endpoints_web.suno_web_operations()
        else:
            self.entities_supported = ("generation", "account")
            self.operations_supported = {"generation": ("create", "cancel", "download")}

    # ── Provider protocol ────────────────────────────────────────────────────

    async def read(self, entity: str, id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        if entity == "generation":
            if id is None:
                raise ValidationError("suno generation read requires id")
            raw = await self._client.get_generation(id)
            return self._normalize_generation(raw)
        if entity == "account":
            return await self._read_account()

        if self._payload_mode == "suno_web":
            return await self._web_read(entity, id, params)

        self._require_sunoapi(f"read {entity!r}")
        rec: endpoints.TaskRead | None
        if entity == "voice" and str(params.get("kind") or "") == "validate":
            rec = endpoints.VOICE_VALIDATE_READ
        else:
            rec = endpoints.READ.get(entity)
        if rec is None:
            raise ValidationError(
                f"unknown suno read entity: {entity!r}; supported: "
                f"{sorted(('generation', 'account', *endpoints.READ))}"
            )
        if id is None:
            raise ValidationError(f"suno {entity!r} read requires id (taskId)")
        raw = await self._client.api_call("GET", rec.path, params={rec.query: str(id)})
        return self._normalize_task(raw, entity, "read")

    async def write(self, entity: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        if entity == "generation" and operation in ("create", "cancel", "download"):
            match operation:
                case "create":
                    return await self._create_generation(params)
                case "cancel":
                    (generation_id,) = _require(params, "generation_id", op="generation.cancel")
                    raw = await self._client.cancel_generation(str(generation_id))
                    return self._normalize_generation(raw)
                case _:  # download
                    return await self._download_generation(params)

        if self._payload_mode == "suno_web":
            return await self._web_write(entity, operation, params)

        self._require_sunoapi(f"{entity}.{operation}")
        ep = endpoints.WRITE.get((entity, operation))
        if ep is None:
            raise ValidationError(
                f"unknown suno operation {entity}.{operation}; supported: "
                f"{self.operations_supported.get(entity, ())}"
            )
        if ep.upload:
            return await self._file_upload(entity, operation, ep, params)
        body = self._build_body(params, ep, op=f"{entity}.{operation}")
        raw = await self._client.api_call(ep.method, ep.path, json=body)
        return self._normalize_task(raw, entity, operation)

    async def search(self, query: str, type: str = "tracks", limit: int = 20) -> dict[str, Any]:
        raise ValidationError("suno provider does not support catalog search")

    async def download_audio(self, track_id: str, dest: Path | None = None) -> Path:
        target = dest if dest is not None else self._download_dir / f"{track_id}.mp3"
        return await self._client.download_generation(track_id, target)

    async def close(self) -> None:
        await self._client.close()

    # ── sunoapi.org generic dispatch ─────────────────────────────────────────

    def _require_sunoapi(self, what: str) -> None:
        if self._payload_mode != "sunoapi":
            raise ValidationError(
                f"suno {what} requires api_key/sunoapi mode "
                "(set DJ_SUNO_AUTH_MODE=api_key + DJ_SUNO_API_KEY, "
                "DJ_SUNO_PAYLOAD_MODE defaults to sunoapi); "
                f"current payload_mode={self._payload_mode!r}"
            )

    # ── Suno web (browser-session) generic dispatch ──────────────────────────

    async def _web_write(
        self, entity: str, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if entity == "generation" and operation == "extend":
            return await self._web_extend(params)
        ep = endpoints_web.WEB_WRITE.get((entity, operation))
        if ep is None:
            raise ValidationError(
                f"unknown suno web operation {entity}.{operation}; supported: "
                f"{self.operations_supported.get(entity, ())}"
            )
        path = ep.path
        for pp in ep.path_params:
            val = pull_field(params, pp)
            if val in (None, ""):
                raise ValidationError(f"suno {entity}.{operation} requires path param {pp!r}")
            path = path.replace("{" + pp + "}", str(val))
        body = build_web_body(params, ep)
        raw = await self._client.api_call(ep.method, path, json=body)
        return self._normalize_web(raw, entity, operation, ep)

    async def _web_extend(self, params: dict[str, Any]) -> dict[str, Any]:
        continue_clip_id, continue_at = _require(
            params, "continue_clip_id", "continue_at", op="generation.extend"
        )
        instrumental = bool(params.get("instrumental", True))
        payload: dict[str, Any] = {
            "make_instrumental": instrumental,
            "mv": str(params.get("model") or self._default_model or "chirp-auk-turbo"),
            "prompt": str(params.get("lyrics") or ""),
            "gpt_description_prompt": str(params.get("prompt") or params.get("description") or ""),
            "tags": self._stringify_tags(params.get("tags") or params.get("style")),
            "title": str(params.get("title") or ""),
            "continue_clip_id": str(continue_clip_id),
            "continue_at": continue_at,
            "task": "extend",
            "generation_type": "TEXT",
            "metadata": {"create_mode": "SIMPLE", "lyrics_model": "default"},
        }
        if params.get("negative_tags"):
            payload["negative_tags"] = self._stringify_tags(params["negative_tags"])
        payload.update(params.get("extra") or {})
        raw = await self._client.create_generation(payload)
        return self._normalize_generation(raw)

    async def _web_read(
        self, entity: str, id: str | None, params: dict[str, Any]
    ) -> dict[str, Any]:
        if entity == "clip":
            kind = str(params.get("kind") or "info")
            rd = endpoints_web.CLIP_READ_KINDS.get(kind)
            if rd is None:
                raise ValidationError(
                    f"unknown suno clip read kind {kind!r}; supported: "
                    f"{sorted(endpoints_web.CLIP_READ_KINDS)}"
                )
            if id is None:
                raise ValidationError("suno clip read requires id")
            raw = await self._client.api_call("GET", rd.path.replace("{id}", str(id)))
            return {"entity": "clip", "kind": kind, "clip_id": str(id), "data": raw, "raw": raw}
        if entity == "persona" and id is None:
            raw = await self._client.api_call("GET", "/api/persona/get-personas/")
            return {"entity": "persona", "kind": "list", "data": raw, "raw": raw}
        rd = endpoints_web.WEB_READ.get(entity)
        if rd is None:
            raise ValidationError(
                f"unknown suno web read entity {entity!r}; supported: "
                f"{sorted(('generation', 'account', 'clip', *endpoints_web.WEB_READ))}"
            )
        if id is None:
            raise ValidationError(f"suno {entity!r} read requires id")
        raw = await self._client.api_call("GET", rd.path.replace("{id}", str(id)))
        return self._normalize_task(raw, entity, "read")

    def _normalize_web(
        self, raw: Any, entity: str, operation: str, ep: WebWrite
    ) -> dict[str, Any]:
        if ep.empty_ok and (not raw or raw == {}):
            return {"entity": entity, "operation": operation, "status": "accepted"}
        if not isinstance(raw, dict):
            return {"entity": entity, "operation": operation, "data": raw, "raw": raw}
        result: dict[str, Any] = {"entity": entity, "operation": operation, "raw": raw}
        if ep.poll_key and raw.get(ep.poll_key):
            result["generation_id"] = str(raw[ep.poll_key])
            result[ep.poll_key] = raw[ep.poll_key]
        else:
            clip_ids = SunoAdapter._extract_clip_ids(raw)
            gid = clip_ids[0] if clip_ids else SunoAdapter._extract_id(raw)
            if gid:
                result["generation_id"] = str(gid)
            if clip_ids:
                result["clip_ids"] = clip_ids
        result["status"] = raw.get("status")
        return result

    def _build_body(self, params: dict[str, Any], ep: Endpoint, *, op: str) -> dict[str, Any]:
        body: dict[str, Any] = dict(params.get("extra") or {})
        for f in ep.fields:
            val = pull_field(params, f)
            if val is None:
                continue
            if f in ep.array_fields:
                body[f] = list(val) if isinstance(val, list | tuple | set) else [val]
            elif f in ("negativeTags", "tags", "style") and not isinstance(val, str):
                body[f] = self._stringify_tags(val)
            else:
                body[f] = val
        if ep.inject_model:
            model = body.get("model") or self._default_model
            allowed = ep.default_models
            if allowed and (not model or model not in allowed):
                model = allowed[0]
            if model:
                body["model"] = model
        if ep.inject_callback and "callBackUrl" in ep.fields and not body.get("callBackUrl"):
            body["callBackUrl"] = self._callback_url
        missing = [f for f in ep.required if body.get(f) in (None, "")]
        if missing:
            raise ValidationError(
                f"suno {op!r} requires field(s) {missing!r}; "
                f"got keys {sorted(params.keys()) or 'none'}"
            )
        return body

    async def _file_upload(
        self, entity: str, operation: str, ep: Endpoint, params: dict[str, Any]
    ) -> dict[str, Any]:
        if operation == "upload_stream":
            (local_path,) = _require(params, "local_path", op="file.upload_stream")
            src = Path(str(local_path)).expanduser()
            if not src.exists():
                raise ValidationError(f"suno file.upload_stream: local file not found: {src}")
            data = self._build_body(params, ep, op=f"{entity}.{operation}")
            filename = str(data.get("fileName") or src.name)
            with src.open("rb") as fh:
                files = {"file": (filename, fh, "application/octet-stream")}
                raw = await self._client.upload_file(ep.path, data=data, files=files)
        else:
            body = self._build_body(params, ep, op=f"{entity}.{operation}")
            raw = await self._client.upload_file(ep.path, json=body)
        result: dict[str, Any] = {"entity": entity, "operation": operation, "raw": raw}
        if isinstance(raw, dict):
            for key in ("downloadUrl", "download_url", "fileUrl", "file_url", "url"):
                if isinstance(raw.get(key), str) and raw[key]:
                    result["upload_url"] = raw[key]
                    break
        return result

    @staticmethod
    def _normalize_task(raw: Any, entity: str, operation: str) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {"entity": entity, "operation": operation, "data": raw, "raw": raw}
        task_id = SunoAdapter._extract_id(raw)
        status = raw.get("status")
        for container in ("response", "data", "task"):
            value = raw.get(container)
            if status is None and isinstance(value, dict):
                status = value.get("status")
        status_text = str(status).lower() if status is not None else ""
        audio_url = SunoClient.find_audio_url(raw)
        ready = bool(audio_url) or status_text in {
            "complete",
            "completed",
            "success",
            "succeeded",
            "first_success",
        }
        return {
            "entity": entity,
            "operation": operation,
            "task_id": task_id,
            "status": status,
            "ready": ready,
            "audio_url": audio_url,
            "raw": raw,
        }

    # ── account ──────────────────────────────────────────────────────────────

    def _capabilities(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "payload_mode": self._payload_mode,
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
            ("credits_left", "credits_left"),
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

    # ── core generation (both modes) ─────────────────────────────────────────

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
        if self._payload_mode == "sunoapi":
            return self._build_sunoapi_payload(prompt=prompt, params=params)

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

    def _build_sunoapi_payload(self, *, prompt: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = dict(params.get("extra") or {})
        lyrics = params.get("lyrics")
        style = self._stringify_tags(params.get("style") or params.get("tags"))
        title = str(params.get("title") or "DJ Set Asset")
        instrumental = bool(params.get("instrumental", lyrics is None))

        custom_mode = bool(params.get("custom_mode", params.get("customMode", True)))
        payload.setdefault("customMode", custom_mode)
        payload.setdefault("instrumental", instrumental)
        payload.setdefault(
            "callBackUrl",
            str(params.get("callback_url") or params.get("callBackUrl") or self._callback_url),
        )
        model = str(params.get("model") or self._default_model or "V4_5")
        if model not in _SUNOAPI_MODELS:
            model = "V4_5"
        payload.setdefault("model", model)

        if custom_mode:
            payload.setdefault("style", style or prompt)
            payload.setdefault("title", title)
            if not instrumental:
                payload.setdefault("prompt", str(lyrics or prompt))
        else:
            payload.setdefault("prompt", str(lyrics or prompt))

        if params.get("negative_tags"):
            payload.setdefault("negativeTags", self._stringify_tags(params["negative_tags"]))
        for src, dst in (
            ("persona_id", "personaId"),
            ("persona_model", "personaModel"),
            ("vocal_gender", "vocalGender"),
            ("style_weight", "styleWeight"),
            ("weirdness", "weirdnessConstraint"),
            ("weirdness_constraint", "weirdnessConstraint"),
            ("audio_weight", "audioWeight"),
        ):
            if src in params and params[src] is not None:
                payload.setdefault(dst, params[src])
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

    # ── normalization helpers ────────────────────────────────────────────────

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
        "sunoData",
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
        response = payload.get("response")
        if isinstance(response, dict):
            if status is None:
                status = response.get("status")
            if not clip_ids:
                clip_ids = cls._extract_clip_ids(response)
        if status is None:
            clips = payload.get("clips")
            if isinstance(clips, list) and clips and isinstance(clips[0], dict):
                status = clips[0].get("status")
        status_text = str(status).lower()
        audio_url = SunoClient.find_audio_url(payload)
        return {
            "generation_id": generation_id,
            "batch_id": batch_id,
            "clip_ids": clip_ids,
            "status": status,
            "audio_url": audio_url,
            "ready": bool(audio_url)
            or status_text in {"complete", "completed", "succeeded", "success", "first_success"},
            "raw": payload,
        }
