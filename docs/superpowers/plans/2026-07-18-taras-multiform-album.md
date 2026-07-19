# Taras Multiform Album — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сгенерировать 8-track Taras album в Suno с единым голосовым стержнем и разными жанровыми оболочками, сохранить локальные mp3 и собрать альбомный manifest.

**Architecture:** Один runtime generation pass через существующий Suno adapter. Локальный Python runner создаёт 8 треков на `chirp-fenix`, скачивает результаты, пишет `SUMMARY.json` и `LISTEN.md`, затем пытается собрать Suno playlist как album container.

**Tech Stack:** Python 3.12, uv, existing Suno session adapter, local JSON/Markdown artifacts.

## Global Constraints

- Все команды только через `uv`.
- Model: `chirp-fenix`.
- 8 tracks, one Taras voice core, distinct genre tails.
- No new dependencies.
- If Suno bearer expired, refresh first.
- If CAPTCHA appears, stop cleanly and report it.

---

### Task 1: Encode Taras album trackbook

**Files:**
- Create: `app/domain/suno_voice/taras_album.py`
- Create: `tests/domain/suno_voice/test_taras_album.py`

**Interfaces:**
- Produces: `TARAS_ALBUM_TITLE`, `TARAS_VOICE_CORE`, `TARAS_ALBUM_TRACKS`, `assemble_taras_album_prompt(slug)`

### Task 2: Build runtime album generator

**Files:**
- Create: `scripts/taras_multiform_album.py`
- Create: `suno_out/taras_album/README.md`

**Interfaces:**
- Produces: `suno_out/taras_album/SUMMARY.json`, `suno_out/taras_album/LISTEN.md`, downloaded mp3 files

### Task 3: Generate album and write album manifest

**Files:**
- Runtime outputs only

**Interfaces:**
- Produces: 8 titles × 2 variants, local downloads, optional Suno playlist id

### Task 4: Final verification

**Files:** none

**Interfaces:**
- Produces: delivered links + local paths + shortlist of strongest tracks
