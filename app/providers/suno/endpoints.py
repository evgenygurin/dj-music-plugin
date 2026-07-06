"""Declarative registry of sunoapi.org REST endpoints.

Source of truth: the sunoapi.org OpenAPI specs (``suno-api.json``,
``suno-voice-api.json``, ``file-upload-api.json``). These endpoints are
sunoapi.org-specific (``api_key`` / ``sunoapi`` payload mode) and are NOT
available in the browser web-session path — the adapter gates them on mode.

Fields are the documented **camelCase** names; the adapter's field puller
also accepts snake_case aliases (``audio_id`` -> ``audioId``) plus a small
set of explicit aliases (``callback_url`` -> ``callBackUrl``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Model enums per endpoint group (documented allowed values).
MODELS_FULL = ("V4", "V4_5", "V4_5PLUS", "V4_5ALL", "V5", "V5_5")
MODELS_MASHUP = ("V4", "V4_5", "V4_5PLUS", "V4_5ALL", "V5")
MODELS_ADDON = ("V4_5PLUS", "V5", "V5_5")

# Fields whose snake_case form does not follow the naive camel->snake rule.
_EXTRA_ALIASES: dict[str, tuple[str, ...]] = {
    "callBackUrl": ("callback_url", "call_back_url"),
    "calBackUrl": ("callback_url", "callBackUrl", "cal_back_url"),
    "uploadUrlList": ("upload_urls", "upload_url_list"),
}


@dataclass(frozen=True)
class Endpoint:
    """A single sunoapi.org write (task-creating or sync) endpoint."""

    path: str
    method: str = "POST"
    # Documented body fields (camelCase). ``bool``/``number`` pass through.
    fields: tuple[str, ...] = ()
    # Required body fields to validate (excludes injected model/callBackUrl).
    required: tuple[str, ...] = ()
    # Inject the configured default model when the caller omits ``model``.
    inject_model: bool = False
    default_models: tuple[str, ...] = ()
    # Inject the configured default callBackUrl when absent.
    inject_callback: bool = True
    # Multipart/stream upload to the file-upload host (different base URL).
    upload: bool = False
    # array-typed body fields (kept as lists, not stringified).
    array_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TaskRead:
    """A GET record-info / details endpoint keyed by a query id param."""

    path: str
    query: str = "taskId"


_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(name: str) -> str:
    """``audioId`` -> ``audio_id``; ``infillStartS`` -> ``infill_start_s``."""
    return _CAMEL_RE.sub("_", name).lower()


def pull_field(params: dict[str, Any], camel: str) -> Any:
    """Return ``params[camel]`` honoring snake_case + explicit aliases."""
    if camel in params:
        return params[camel]
    snake = camel_to_snake(camel)
    if snake in params:
        return params[snake]
    for alt in _EXTRA_ALIASES.get(camel, ()):
        if alt in params:
            return params[alt]
    return None


# ── Music generation family (poll via /api/v1/generate/record-info) ──────────
_GEN_TAIL = (
    "personaId",
    "personaModel",
    "negativeTags",
    "vocalGender",
    "styleWeight",
    "weirdnessConstraint",
    "audioWeight",
    "callBackUrl",
)

WRITE: dict[tuple[str, str], Endpoint] = {
    ("generation", "sounds"): Endpoint(
        path="/api/v1/generate/sounds",
        fields=(
            "prompt",
            "model",
            "soundLoop",
            "soundTempo",
            "soundKey",
            "grabLyrics",
            "callBackUrl",
        ),
        required=("prompt",),
        inject_model=True,
        default_models=("V5",),
    ),
    ("generation", "extend"): Endpoint(
        path="/api/v1/generate/extend",
        fields=(
            "defaultParamFlag",
            "audioId",
            "prompt",
            "style",
            "title",
            "continueAt",
            "model",
            *_GEN_TAIL,
        ),
        required=("defaultParamFlag", "audioId"),
        inject_model=True,
        default_models=MODELS_FULL,
    ),
    ("generation", "upload_cover"): Endpoint(
        path="/api/v1/generate/upload-cover",
        fields=(
            "uploadUrl",
            "prompt",
            "style",
            "title",
            "customMode",
            "instrumental",
            "model",
            *_GEN_TAIL,
        ),
        required=("uploadUrl", "customMode", "instrumental"),
        inject_model=True,
        default_models=MODELS_FULL,
    ),
    ("generation", "upload_extend"): Endpoint(
        path="/api/v1/generate/upload-extend",
        fields=(
            "uploadUrl",
            "defaultParamFlag",
            "instrumental",
            "prompt",
            "style",
            "title",
            "continueAt",
            "model",
            *_GEN_TAIL,
        ),
        required=("uploadUrl", "defaultParamFlag"),
        inject_model=True,
        default_models=MODELS_FULL,
    ),
    ("generation", "add_instrumental"): Endpoint(
        path="/api/v1/generate/add-instrumental",
        fields=(
            "uploadUrl",
            "title",
            "negativeTags",
            "tags",
            "vocalGender",
            "styleWeight",
            "weirdnessConstraint",
            "audioWeight",
            "model",
            "callBackUrl",
        ),
        required=("uploadUrl", "title", "negativeTags", "tags"),
        inject_model=True,
        default_models=MODELS_ADDON,
    ),
    ("generation", "add_vocals"): Endpoint(
        path="/api/v1/generate/add-vocals",
        fields=(
            "prompt",
            "title",
            "negativeTags",
            "style",
            "vocalGender",
            "styleWeight",
            "weirdnessConstraint",
            "audioWeight",
            "uploadUrl",
            "model",
            "callBackUrl",
        ),
        required=("prompt", "title", "negativeTags", "style", "uploadUrl"),
        inject_model=True,
        default_models=MODELS_ADDON,
    ),
    ("generation", "mashup"): Endpoint(
        path="/api/v1/generate/mashup",
        fields=(
            "uploadUrlList",
            "customMode",
            "prompt",
            "style",
            "title",
            "instrumental",
            "model",
            "vocalGender",
            "styleWeight",
            "weirdnessConstraint",
            "audioWeight",
            "callBackUrl",
        ),
        required=("uploadUrlList", "customMode"),
        inject_model=True,
        default_models=MODELS_MASHUP,
        array_fields=("uploadUrlList",),
    ),
    ("generation", "replace_section"): Endpoint(
        path="/api/v1/generate/replace-section",
        fields=(
            "taskId",
            "audioId",
            "prompt",
            "tags",
            "title",
            "negativeTags",
            "fullLyrics",
            "infillStartS",
            "infillEndS",
            "callBackUrl",
        ),
        required=(
            "taskId",
            "audioId",
            "prompt",
            "tags",
            "title",
            "fullLyrics",
            "infillStartS",
            "infillEndS",
        ),
    ),
    # ── Sync / task endpoints with their own read (or no read) ──────────────
    ("lyrics", "create"): Endpoint(
        path="/api/v1/lyrics",
        fields=("prompt", "callBackUrl"),
        required=("prompt",),
    ),
    ("lyrics", "timestamped"): Endpoint(
        path="/api/v1/generate/get-timestamped-lyrics",
        fields=("taskId", "audioId"),
        required=("taskId", "audioId"),
        inject_callback=False,
    ),
    ("wav", "create"): Endpoint(
        path="/api/v1/wav/generate",
        fields=("taskId", "audioId", "callBackUrl"),
        required=("taskId", "audioId"),
    ),
    ("vocal_removal", "create"): Endpoint(
        path="/api/v1/vocal-removal/generate",
        fields=("taskId", "audioId", "type", "callBackUrl"),
        required=("taskId", "audioId"),
    ),
    ("midi", "create"): Endpoint(
        path="/api/v1/midi/generate",
        fields=("taskId", "audioId", "callBackUrl"),
        required=("taskId",),
    ),
    ("video", "create"): Endpoint(
        path="/api/v1/mp4/generate",
        fields=("taskId", "audioId", "author", "domainName", "callBackUrl"),
        required=("taskId", "audioId"),
    ),
    ("cover", "create"): Endpoint(
        path="/api/v1/suno/cover/generate",
        fields=("taskId", "callBackUrl"),
        required=("taskId",),
    ),
    ("persona", "create"): Endpoint(
        path="/api/v1/generate/generate-persona",
        fields=("taskId", "audioId", "name", "description", "vocalStart", "vocalEnd", "style"),
        required=("taskId", "audioId", "name", "description"),
        inject_callback=False,
    ),
    ("style", "boost"): Endpoint(
        path="/api/v1/style/generate",
        fields=("content",),
        required=("content",),
        inject_callback=False,
    ),
    # ── Custom voice (suno-voice-api) ───────────────────────────────────────
    ("voice", "validate"): Endpoint(
        path="/api/v1/voice/validate",
        fields=("voiceUrl", "vocalStartS", "vocalEndS", "language", "callBackUrl"),
        required=("voiceUrl", "vocalStartS", "vocalEndS"),
    ),
    ("voice", "generate"): Endpoint(
        path="/api/v1/voice/generate",
        fields=(
            "taskId",
            "verifyUrl",
            "voiceName",
            "description",
            "style",
            "singerSkillLevel",
            "callBackUrl",
        ),
        required=("taskId", "verifyUrl"),
    ),
    ("voice", "regenerate"): Endpoint(
        path="/api/v1/voice/regenerate",
        fields=("taskId", "calBackUrl"),
        required=("taskId",),
    ),
    ("voice", "check"): Endpoint(
        path="/api/v1/voice/check-voice",
        fields=("task_id",),
        required=("task_id",),
        inject_callback=False,
    ),
    # ── File upload (different host: file-upload-api) ────────────────────────
    ("file", "upload_base64"): Endpoint(
        path="/api/file-base64-upload",
        fields=("base64Data", "uploadPath", "fileName"),
        required=("base64Data", "uploadPath"),
        inject_callback=False,
        upload=True,
    ),
    ("file", "upload_url"): Endpoint(
        path="/api/file-url-upload",
        fields=("fileUrl", "uploadPath", "fileName"),
        required=("fileUrl", "uploadPath"),
        inject_callback=False,
        upload=True,
    ),
    ("file", "upload_stream"): Endpoint(
        path="/api/file-stream-upload",
        fields=("uploadPath", "fileName"),  # ``file`` supplied via local_path
        required=("uploadPath",),
        inject_callback=False,
        upload=True,
    ),
}

# GET record-info / details endpoints, keyed by read entity.
READ: dict[str, TaskRead] = {
    "lyrics": TaskRead("/api/v1/lyrics/record-info"),
    "wav": TaskRead("/api/v1/wav/record-info"),
    "vocal_removal": TaskRead("/api/v1/vocal-removal/record-info"),
    "midi": TaskRead("/api/v1/midi/record-info"),
    "video": TaskRead("/api/v1/mp4/record-info"),
    "cover": TaskRead("/api/v1/suno/cover/record-info"),
    "voice": TaskRead("/api/v1/voice/record-info"),
}

# ``provider_read(entity="voice", params={"kind": "validate"})`` polls the
# verification-phrase endpoint instead of the custom-voice record.
VOICE_VALIDATE_READ = TaskRead("/api/v1/voice/validate-info")


def sunoapi_entities() -> tuple[str, ...]:
    """All entities the sunoapi.org surface exposes (write + read + core)."""
    return (
        "generation",
        "lyrics",
        "wav",
        "vocal_removal",
        "midi",
        "video",
        "cover",
        "persona",
        "style",
        "voice",
        "file",
        "account",
    )


def sunoapi_operations() -> dict[str, tuple[str, ...]]:
    """entity -> supported write operations for the sunoapi.org surface."""
    ops: dict[str, list[str]] = {"generation": ["create", "cancel", "download"]}
    for entity, operation in WRITE:
        ops.setdefault(entity, []).append(operation)
    return {k: tuple(v) for k, v in ops.items()}
