# Suno Operations Reference

## Session / Suno Web Mode

- `provider_read(provider="suno", entity="account")` — credits, plan, payload mode, models.
- `provider_write(provider="suno", entity="generation", operation="create")` — create clips; poll `clip_ids`.
- `provider_read(provider="suno", entity="generation", id="<clip_id>")` — poll a clip.
- `provider_write(provider="suno", entity="generation", operation="extend")` — create continuation clips.
- `provider_write(provider="suno", entity="generation", operation="concat")` — merge extension chain.
- `provider_write(provider="suno", entity="generation", operation="download")` — download ready audio.
- `provider_write(provider="suno", entity="stem", operation="create")` — web stems.
- `provider_write(provider="suno", entity="wav", operation="create")` + `provider_read(provider="suno", entity="clip", params={"kind":"wav"})` — WAV.
- `provider_write(provider="suno", entity="edit", operation="crop|fade|reverse")` — exact edits.
- `provider_write(provider="suno", entity="remaster", operation="create")` — upsample/remaster.
- `provider_write(provider="suno", entity="persona", operation="create")` — web Persona.
- `provider_write(provider="suno", entity="lyrics", operation="create")` — lyrics.

## SunoAPI Mode

- `generation.create|extend|upload_cover|upload_extend|add_instrumental|add_vocals|mashup|replace_section|sounds`.
- `lyrics.create|timestamped` plus lyrics read.
- `wav.create` plus WAV read.
- `vocal_removal.create` plus vocal-removal read.
- `midi.create`, `video.create`, `cover.create` plus matching reads.
- `persona.create`, `style.boost`.
- `voice.validate|generate|regenerate|check` plus voice reads.
- `file.upload_base64|upload_url|upload_stream` for temporary upload URLs.

## ID Rules

- Web create returns `clip_ids` and `batch_id`; poll `clip_ids`.
- SunoAPI create returns task id; poll task id.
- Download only ready clip/task audio URLs.
