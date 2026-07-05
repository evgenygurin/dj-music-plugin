"""Declarative registry of Suno **web** (browser-session) endpoints.

Source of truth: the live suno.com JS bundle (studio-api-prod.suno.com call
sites) cross-checked with gcui-art/suno-api and validated live against the
authenticated session (2026-07-06). These are the private endpoints the web
app itself calls — available only in the browser-session path
(``payload_mode == "suno_web"``); the adapter gates them on that mode.

Wire keys are the documented **snake_case** names the web app sends. The
adapter's ``pull_field`` accepts them directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.providers.suno.endpoints import pull_field


@dataclass(frozen=True)
class WebWrite:
    """A POST endpoint on the Suno web API."""

    path: str
    method: str = "POST"
    # {name} path params pulled from params (snake or camel).
    path_params: tuple[str, ...] = ()
    # Optional body fields pulled from params by wire key.
    body_fields: tuple[str, ...] = ()
    # Required body fields (validated after build).
    required: tuple[str, ...] = ()
    # Constant body fields always sent (e.g. ui_surface).
    const_body: dict[str, Any] = field(default_factory=dict)
    # Body fields kept as JSON arrays (not stringified).
    array_fields: tuple[str, ...] = ()
    # Response key holding the pollable clip id (edit actions -> action_clip_id).
    poll_key: str | None = None
    # True when the endpoint returns 204/empty on success (wav convert).
    empty_ok: bool = False


@dataclass(frozen=True)
class WebRead:
    """A GET endpoint keyed by a single id path param."""

    path: str  # contains a single {id}


def build_web_body(params: dict[str, Any], ep: WebWrite) -> dict[str, Any]:
    """Build the request body for a web endpoint from caller params."""
    from app.shared.errors import ValidationError

    body: dict[str, Any] = dict(ep.const_body)
    body.update(params.get("extra") or {})
    for f in ep.body_fields:
        val = pull_field(params, f)
        if val is None:
            continue
        if f in ep.array_fields:
            body[f] = list(val) if isinstance(val, list | tuple | set) else [val]
        else:
            body[f] = val
    missing = [f for f in ep.required if body.get(f) in (None, "")]
    if missing:
        raise ValidationError(
            f"suno web endpoint {ep.path!r} requires field(s) {missing!r}; "
            f"got keys {sorted(params.keys()) or 'none'}"
        )
    return body


# ── Write endpoints (entity, operation) -> WebWrite ──────────────────────────
WEB_WRITE: dict[tuple[str, str], WebWrite] = {
    # generation.create / generation.extend are handled specially in the adapter
    # (they reuse the suno_web generation-payload builder + continue params).
    ("generation", "concat"): WebWrite(
        path="/api/generate/concat/v2/",
        body_fields=("clip_id",),
        required=("clip_id",),
    ),
    # Stem separation: empty body, returns {clips:[...]} of stem clips.
    ("stem", "create"): WebWrite(path="/api/edit/stems/{clip_id}/", path_params=("clip_id",)),
    ("stem", "sample_pack"): WebWrite(
        path="/api/generate/{clip_id}/generate_sample_pack", path_params=("clip_id",)
    ),
    # WAV conversion: 204 accepted; read the file later via clip read kind=wav.
    ("wav", "create"): WebWrite(
        path="/api/gen/{clip_id}/convert_wav/", path_params=("clip_id",), empty_ok=True
    ),
    # Editor actions: each returns {action_clip_id} (or {id}) to poll.
    ("edit", "crop"): WebWrite(
        path="/api/edit/crop/{clip_id}/",
        path_params=("clip_id",),
        body_fields=("crop_start_s", "crop_end_s", "title"),
        required=("crop_start_s", "crop_end_s"),
        const_body={"is_crop_remove": False, "ui_surface": "song_actions"},
        poll_key="action_clip_id",
    ),
    ("edit", "fade"): WebWrite(
        path="/api/edit/fade/{clip_id}/",
        path_params=("clip_id",),
        body_fields=("fade_in_time", "fade_out_time", "title"),
        required=("fade_in_time", "fade_out_time"),
        poll_key="action_clip_id",
    ),
    ("edit", "reverse"): WebWrite(
        path="/api/clips/reverse-clip/",
        body_fields=("clip_id", "title"),
        required=("clip_id",),
        poll_key="id",
    ),
    # Remaster / upsample: base clip + optional enhancement controls.
    ("remaster", "create"): WebWrite(
        path="/api/generate/upsample",
        body_fields=(
            "clip_id",
            "model_name",
            "tags",
            "freedom",
            "tone",
            "strength",
            "stereo_width",
            "clarity",
            "variation_category",
        ),
        required=("clip_id",),
    ),
    # Persona (style/voice reuse) from a source clip.
    ("persona", "create"): WebWrite(
        path="/api/persona/create/",
        body_fields=(
            "name",
            "description",
            "root_clip_id",
            "singer_skill_level",
            "clips",
            "is_voice_recording",
            "voice_recording_id",
            "verification_id",
        ),
        required=("name", "description"),
    ),
    ("lyrics", "create"): WebWrite(
        path="/api/generate/lyrics/", body_fields=("prompt",), required=("prompt",)
    ),
    # Playlist CRUD.
    ("playlist", "create"): WebWrite(
        path="/api/playlist/create/", body_fields=("name",), required=("name",)
    ),
    ("playlist", "add_tracks"): WebWrite(
        path="/api/playlist/v2/{playlist_id}/tracks/add",
        path_params=("playlist_id",),
        body_fields=("clip_ids",),
        required=("clip_ids",),
        array_fields=("clip_ids",),
    ),
    ("playlist", "remove_tracks"): WebWrite(
        path="/api/playlist/v2/{playlist_id}/tracks/remove",
        path_params=("playlist_id",),
        body_fields=("clip_ids",),
        required=("clip_ids",),
        array_fields=("clip_ids",),
    ),
}

# ── Read endpoints ───────────────────────────────────────────────────────────
# entity "clip" read is multiplexed by a ``kind`` param onto these sub-paths.
CLIP_READ_KINDS: dict[str, WebRead] = {
    "info": WebRead("/api/clip/{id}"),
    "stems": WebRead("/api/clip/{id}/stems"),
    "wav": WebRead("/api/gen/{id}/wav_file/"),
    "downbeats": WebRead("/api/gen/{id}/downbeats"),
    "sections": WebRead("/api/gen/{id}/novelty-sections"),
    "waveform": WebRead("/api/gen/{id}/waveform-aggregates"),
    "aligned_lyrics": WebRead("/api/gen/{id}/aligned_lyrics/v2"),
}

# Standalone read entities (id in path).
WEB_READ: dict[str, WebRead] = {
    "lyrics": WebRead("/api/generate/lyrics/{id}"),
    "persona": WebRead("/api/persona/get-persona/{id}/"),
    "playlist": WebRead("/api/playlist/{id}/"),
}


def suno_web_entities() -> tuple[str, ...]:
    return (
        "generation",
        "clip",
        "stem",
        "wav",
        "edit",
        "remaster",
        "persona",
        "lyrics",
        "playlist",
        "account",
    )


def suno_web_operations() -> dict[str, tuple[str, ...]]:
    """entity -> supported write operations for the suno_web surface."""
    ops: dict[str, list[str]] = {
        "generation": ["create", "extend", "concat", "cancel", "download"],
    }
    for entity, operation in WEB_WRITE:
        if operation not in ops.setdefault(entity, []):
            ops[entity].append(operation)
    return {k: tuple(v) for k, v in ops.items()}
