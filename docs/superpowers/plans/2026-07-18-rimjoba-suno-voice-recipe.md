# RimJoba Suno Voice Recipe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Операционализировать approved prompt-рецепт голоса RimJoba: pure-domain assembler + тесты + copy-paste артефакты в `suno_out/rimjoba/` + CLI для сборки style/negative/title.

**Architecture:** Один pure-Python модуль `app/domain/suno_voice/rimjoba.py` держит immutable VOICE BLOCK, GENRE TAIL catalog, NEGATIVE и `assemble_rimjoba_style(mode) -> RimJobaPrompt`. Без вызовов Suno API (create persona/voice out of scope). CLI `scripts/rimjoba_prompt.py` печатает готовые блоки. Copy-paste txt-файлы синхронизированы с константами модуля.

**Tech Stack:** Python 3.12, pytest, ruff, uv. Без новых зависимостей.

## Global Constraints

- Все команды только через `uv` (`uv run pytest`, `uv run ruff check`, `uv run python`)
- Идентификаторы на английском; user-facing строки рецепта — как в спеке (EN style tags + RU lyrics helpers)
- Тексты VOICE BLOCK / NEGATIVE / tails — **verbatim** из `docs/superpowers/specs/2026-07-18-rimjoba-suno-voice-recipe-design.md`
- **No** `provider_write` / persona create / voice generate в этом плане
- Коммит после каждой Task
- TDD: failing test → implement → pass → commit
- `make check` не обязателен на каждый микро-шаг; минимум: `uv run pytest` на затронутых тестах + `uv run ruff check` на новых файлах перед коммитом Task

**Spec:** `docs/superpowers/specs/2026-07-18-rimjoba-suno-voice-recipe-design.md`

---

## File map

| Path | Responsibility |
|------|----------------|
| `app/domain/suno_voice/__init__.py` | Public exports |
| `app/domain/suno_voice/rimjoba.py` | Constants + assemble + validate |
| `tests/domain/suno_voice/test_rimjoba.py` | Unit tests |
| `suno_out/rimjoba/VOICE_BLOCK.txt` | Copy-paste voice lock |
| `suno_out/rimjoba/NEGATIVE.txt` | Copy-paste negative |
| `suno_out/rimjoba/tails/<mode>.txt` | Per-mode genre tails |
| `suno_out/rimjoba/LYRICS_SKELETON.txt` | Lyrics performance skeleton |
| `suno_out/rimjoba/README.md` | How to use (RU, short) |
| `scripts/rimjoba_prompt.py` | CLI: print assembled prompt |

---

### Task 1: Domain module — constants + assemble

**Files:**
- Create: `app/domain/suno_voice/__init__.py`
- Create: `app/domain/suno_voice/rimjoba.py`
- Create: `tests/domain/suno_voice/test_rimjoba.py`

**Interfaces:**
- Produces:
  - `VOICE_BLOCK: str`
  - `NEGATIVE_TAGS: str`
  - `GENRE_TAILS: dict[str, str]` keys exactly: `street_trap`, `techno_rap`, `boom_bap`, `phonk`, `club`, `late_night`
  - `REFERENCE_CLIP_ID: str = "e4d68e9a-d35d-4e70-8af0-4205cf484d2f"`
  - `REFERENCE_URL: str = "https://suno.com/song/e4d68e9a-d35d-4e70-8af0-4205cf484d2f"`
  - `@dataclass(frozen=True, slots=True) class RimJobaPrompt` with fields: `style: str`, `negative_tags: str`, `mode: str`, `title_prefix: str` (always `"RimJoba"`)
  - `def assemble_rimjoba_style(mode: str, *, extra_negative: str = "") -> RimJobaPrompt`
  - `def list_modes() -> tuple[str, ...]`
  - `class UnknownRimJobaModeError(ValueError)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/suno_voice/test_rimjoba.py
from __future__ import annotations

import pytest

from app.domain.suno_voice.rimjoba import (
    GENRE_TAILS,
    NEGATIVE_TAGS,
    REFERENCE_CLIP_ID,
    VOICE_BLOCK,
    UnknownRimJobaModeError,
    assemble_rimjoba_style,
    list_modes,
)


def test_voice_block_is_immutable_taras_lock() -> None:
    assert "deadpan delivery" in VOICE_BLOCK
    assert "cold cocky" in VOICE_BLOCK
    assert "light autotune" in VOICE_BLOCK
    assert "wide stereo ad-libs" in VOICE_BLOCK
    assert "gang-chant hooks" in VOICE_BLOCK
    assert "no autotune" not in VOICE_BLOCK.lower()


def test_negative_bans_drift() -> None:
    low = NEGATIVE_TAGS.lower()
    for token in ("female vocals", "choir lead", "melodic crooner", "robotic extreme autotune"):
        assert token in low
    assert "no autotune" not in low
    assert "no singing" not in low


def test_all_spec_modes_present() -> None:
    expected = {
        "street_trap",
        "techno_rap",
        "boom_bap",
        "phonk",
        "club",
        "late_night",
    }
    assert set(GENRE_TAILS) == expected
    assert set(list_modes()) == expected


def test_assemble_puts_voice_block_first() -> None:
    prompt = assemble_rimjoba_style("street_trap")
    assert prompt.style.startswith(VOICE_BLOCK)
    assert GENRE_TAILS["street_trap"] in prompt.style
    assert prompt.style.index(VOICE_BLOCK) < prompt.style.index(GENRE_TAILS["street_trap"])
    assert prompt.negative_tags == NEGATIVE_TAGS
    assert prompt.mode == "street_trap"
    assert prompt.title_prefix == "RimJoba"


def test_assemble_extra_negative_appends() -> None:
    prompt = assemble_rimjoba_style("phonk", extra_negative="bright EDM festival drop")
    assert prompt.negative_tags.startswith(NEGATIVE_TAGS)
    assert "bright EDM festival drop" in prompt.negative_tags


def test_assemble_unknown_mode_raises() -> None:
    with pytest.raises(UnknownRimJobaModeError, match="unknown"):
        assemble_rimjoba_style("opera_ballad")


def test_genre_tail_has_no_vocal_identity_words() -> None:
    banned = (
        "deadpan",
        "autotune",
        "baritone",
        "female",
        "choir",
        "crooner",
        "ad-lib",
        "ad lib",
    )
    for mode, tail in GENRE_TAILS.items():
        low = tail.lower()
        for word in banned:
            assert word not in low, f"{mode} tail leaks vocal word: {word}"


def test_reference_clip_id() -> None:
    assert REFERENCE_CLIP_ID == "e4d68e9a-d35d-4e70-8af0-4205cf484d2f"
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
uv run pytest tests/domain/suno_voice/test_rimjoba.py -v
```

Expected: `ModuleNotFoundError` or collection error for `app.domain.suno_voice`.

- [ ] **Step 3: Implement domain module**

`app/domain/suno_voice/rimjoba.py`:

```python
"""RimJoba Suno voice prompt recipe (Taras lock).

Spec: docs/superpowers/specs/2026-07-18-rimjoba-suno-voice-recipe-design.md
Prompt-only — no Persona/Voice create.
"""

from __future__ import annotations

from dataclasses import dataclass

REFERENCE_CLIP_ID = "e4d68e9a-d35d-4e70-8af0-4205cf484d2f"
REFERENCE_URL = f"https://suno.com/song/{REFERENCE_CLIP_ID}"

VOICE_BLOCK = (
    "RimJoba signature male voice: mid-baritone Russian rap MC, deadpan delivery, "
    "cold cocky swagger, close-mic dry presence, light autotune (subtle, not melodic robot), "
    "wide stereo ad-libs, gang-chant hooks, short delay throws on key lines, punchy consonants, "
    "relaxed jaw, half-time pocket feel even at double-time bursts, clean raw mix, "
    "intimate and arrogant at once"
)

NEGATIVE_TAGS = (
    "female vocals, choir lead, ethereal singer, opera, melodic crooner, heavy melisma, "
    "robotic extreme autotune, chipmunk, kids voice, whisper-only ASMR, folk, accordion, "
    "balalaika, orchestral lead vocal"
)

GENRE_TAILS: dict[str, str] = {
    "street_trap": (
        "Russian trap, drill-tinged hip-hop, 140 BPM, half-time bounce, booming distorted 808, "
        "punchy trap kick, triplet hi-hats, sparse dark bells, detuned synth melody, trap risers"
    ),
    "techno_rap": (
        "techno-rap, 140 BPM four-on-the-floor warehouse rave, cold synth pulse, "
        "syncopated kick-bass, sparse drums in verses, club delay throws"
    ),
    "boom_bap": (
        "boom-bap hip-hop, dusty breakbeats, swung drums, vinyl scratches, "
        "head-nod groove, sparse bass-kick-snare pocket"
    ),
    "phonk": (
        "phonk, dusty Memphis bounce, chopped cowbell groove, hard sub pulses, "
        "tape wobble, smoky half-time pocket"
    ),
    "club": (
        "Russian club-pop anthem, four-on-the-floor kick, buoyant synth stabs, "
        "chantable crowd hooks, filtered build, handclap outro"
    ),
    "late_night": (
        "jazz-hop, laid-back swung pocket, dusty brushes, upright bass, muted keys, "
        "soft sax answers, warm Rhodes"
    ),
}

LYRICS_SKELETON = """[Intro]
[deadpan, low, close mic]
Римджо́ба (эй)

[Verse 1]
[deadpan, low, close mic]
...short lines...
...end ad-libs (е) (а)

[Hook]
[cold cocky, gang doubles]
<MEM 3-6 words> (ха)
<MEM 3-6 words> (бра)
Римджо́ба — ... (эй)

[Verse 2]
...

[Hook]
...

[Outro]
...fade ad-libs (скр) (е)
"""


class UnknownRimJobaModeError(ValueError):
    """Raised when assemble_rimjoba_style gets an unknown genre mode."""


@dataclass(frozen=True, slots=True)
class RimJobaPrompt:
    style: str
    negative_tags: str
    mode: str
    title_prefix: str = "RimJoba"


def list_modes() -> tuple[str, ...]:
    return tuple(sorted(GENRE_TAILS))


def assemble_rimjoba_style(mode: str, *, extra_negative: str = "") -> RimJobaPrompt:
    key = mode.strip().lower().replace("-", "_").replace(" ", "_")
    tail = GENRE_TAILS.get(key)
    if tail is None:
        known = ", ".join(list_modes())
        raise UnknownRimJobaModeError(
            f"unknown RimJoba mode {mode!r}; known: {known}"
        )
    style = f"{VOICE_BLOCK}. {tail}."
    negative = NEGATIVE_TAGS
    extra = extra_negative.strip()
    if extra:
        negative = f"{NEGATIVE_TAGS}, {extra}"
    return RimJobaPrompt(style=style, negative_tags=negative, mode=key)
```

`app/domain/suno_voice/__init__.py`:

```python
"""Suno voice / persona prompt recipes (pure domain)."""

from app.domain.suno_voice.rimjoba import (
    GENRE_TAILS,
    LYRICS_SKELETON,
    NEGATIVE_TAGS,
    REFERENCE_CLIP_ID,
    REFERENCE_URL,
    VOICE_BLOCK,
    RimJobaPrompt,
    UnknownRimJobaModeError,
    assemble_rimjoba_style,
    list_modes,
)

__all__ = [
    "GENRE_TAILS",
    "LYRICS_SKELETON",
    "NEGATIVE_TAGS",
    "REFERENCE_CLIP_ID",
    "REFERENCE_URL",
    "VOICE_BLOCK",
    "RimJobaPrompt",
    "UnknownRimJobaModeError",
    "assemble_rimjoba_style",
    "list_modes",
]
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run pytest tests/domain/suno_voice/test_rimjoba.py -v
```

Expected: all passed.

- [ ] **Step 5: Lint**

```bash
uv run ruff check app/domain/suno_voice tests/domain/suno_voice
```

Expected: clean (fix if needed).

- [ ] **Step 6: Commit**

```bash
git add app/domain/suno_voice tests/domain/suno_voice
git commit -m "feat(suno): RimJoba voice recipe domain assembler (Taras lock)"
```

---

### Task 2: Copy-paste artifacts in `suno_out/rimjoba/`

**Files:**
- Create: `suno_out/rimjoba/VOICE_BLOCK.txt`
- Create: `suno_out/rimjoba/NEGATIVE.txt`
- Create: `suno_out/rimjoba/LYRICS_SKELETON.txt`
- Create: `suno_out/rimjoba/tails/street_trap.txt`
- Create: `suno_out/rimjoba/tails/techno_rap.txt`
- Create: `suno_out/rimjoba/tails/boom_bap.txt`
- Create: `suno_out/rimjoba/tails/phonk.txt`
- Create: `suno_out/rimjoba/tails/club.txt`
- Create: `suno_out/rimjoba/tails/late_night.txt`
- Create: `suno_out/rimjoba/README.md`
- Modify: `tests/domain/suno_voice/test_rimjoba.py` (sync test)

**Interfaces:**
- Consumes: constants from Task 1
- Produces: on-disk copy-paste files **byte-equal** to domain constants (stripped trailing newline policy: single trailing `\n`)

- [ ] **Step 1: Add sync test**

Append to `tests/domain/suno_voice/test_rimjoba.py`:

```python
from pathlib import Path

import app.domain.suno_voice.rimjoba as rimjoba_mod


ROOT = Path(__file__).resolve().parents[3]
RIM_DIR = ROOT / "suno_out" / "rimjoba"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def test_suno_out_artifacts_match_domain_constants() -> None:
    assert _read(RIM_DIR / "VOICE_BLOCK.txt") == VOICE_BLOCK
    assert _read(RIM_DIR / "NEGATIVE.txt") == NEGATIVE_TAGS
    assert _read(RIM_DIR / "LYRICS_SKELETON.txt") == rimjoba_mod.LYRICS_SKELETON.strip()
    for mode, tail in GENRE_TAILS.items():
        assert _read(RIM_DIR / "tails" / f"{mode}.txt") == tail
```

- [ ] **Step 2: Run sync test — expect FAIL (missing files)**

```bash
uv run pytest tests/domain/suno_voice/test_rimjoba.py::test_suno_out_artifacts_match_domain_constants -v
```

Expected: FAIL `FileNotFoundError` or assertion.

- [ ] **Step 3: Write artifacts from constants**

```bash
uv run python - <<'PY'
from pathlib import Path
from app.domain.suno_voice.rimjoba import (
    GENRE_TAILS,
    LYRICS_SKELETON,
    NEGATIVE_TAGS,
    REFERENCE_URL,
    VOICE_BLOCK,
)

root = Path("suno_out/rimjoba")
(root / "tails").mkdir(parents=True, exist_ok=True)
(root / "VOICE_BLOCK.txt").write_text(VOICE_BLOCK + "\n", encoding="utf-8")
(root / "NEGATIVE.txt").write_text(NEGATIVE_TAGS + "\n", encoding="utf-8")
(root / "LYRICS_SKELETON.txt").write_text(LYRICS_SKELETON.strip() + "\n", encoding="utf-8")
for mode, tail in GENRE_TAILS.items():
    (root / "tails" / f"{mode}.txt").write_text(tail + "\n", encoding="utf-8")

readme = f"""# RimJoba — Suno voice recipe (copy-paste)

Референс: {REFERENCE_URL}

## Быстрый старт (Custom Mode)

1. **Style** = содержимое `VOICE_BLOCK.txt` + `. ` + один файл из `tails/` + `.`
2. **Negative** = `NEGATIVE.txt` (+ опциональный genre-neg)
3. **Lyrics** = по `LYRICS_SKELETON.txt` (deadpan tags + ad-libs)
4. **Title** = `RimJoba — <имя>`
5. Model: v5 / v5.5. Не ставь `no autotune` / `no singing`.

## Режимы tails

- `street_trap` — default signature
- `techno_rap`, `boom_bap`, `phonk`, `club`, `late_night`

## CLI

```bash
uv run python scripts/rimjoba_prompt.py street_trap
uv run python scripts/rimjoba_prompt.py phonk --extra-negative "bright EDM festival drop"
uv run python scripts/rimjoba_prompt.py --list
```

Спека: `docs/superpowers/specs/2026-07-18-rimjoba-suno-voice-recipe-design.md`
"""
(root / "README.md").write_text(readme, encoding="utf-8")
print("wrote", root)
PY
```

- [ ] **Step 4: Run full rimjoba tests — expect PASS**

```bash
uv run pytest tests/domain/suno_voice/test_rimjoba.py -v
```

- [ ] **Step 5: Commit**

```bash
git add suno_out/rimjoba tests/domain/suno_voice/test_rimjoba.py
git commit -m "docs(suno): RimJoba copy-paste voice recipe artifacts"
```

---

### Task 3: CLI `scripts/rimjoba_prompt.py`

**Files:**
- Create: `scripts/rimjoba_prompt.py`
- Create: `tests/scripts/test_rimjoba_prompt_cli.py` (subprocess smoke)

**Interfaces:**
- Consumes: `assemble_rimjoba_style`, `list_modes` from Task 1
- Produces: CLI exit 0 with sections `TITLE_PREFIX`, `MODE`, `STYLE`, `NEGATIVE`; exit 2 on unknown mode

- [ ] **Step 1: Write failing CLI smoke test**

```python
# tests/scripts/test_rimjoba_prompt_cli.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rimjoba_prompt.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_list_modes() -> None:
    proc = _run("--list")
    assert proc.returncode == 0
    assert "street_trap" in proc.stdout
    assert "late_night" in proc.stdout


def test_cli_assemble_street_trap() -> None:
    proc = _run("street_trap")
    assert proc.returncode == 0
    assert "STYLE:" in proc.stdout
    assert "NEGATIVE:" in proc.stdout
    assert "deadpan delivery" in proc.stdout
    assert "Russian trap" in proc.stdout


def test_cli_unknown_mode_exits_2() -> None:
    proc = _run("not_a_mode")
    assert proc.returncode == 2
    assert "unknown" in proc.stderr.lower() or "unknown" in proc.stdout.lower()
```

- [ ] **Step 2: Run CLI tests — expect FAIL**

```bash
uv run pytest tests/scripts/test_rimjoba_prompt_cli.py -v
```

Expected: FAIL (script missing or wrong exit).

- [ ] **Step 3: Implement CLI**

`scripts/rimjoba_prompt.py`:

```python
#!/usr/bin/env python3
"""Print RimJoba Suno Custom Mode prompt blocks.

Usage:
  uv run python scripts/rimjoba_prompt.py street_trap
  uv run python scripts/rimjoba_prompt.py phonk --extra-negative "bright EDM festival drop"
  uv run python scripts/rimjoba_prompt.py --list
"""

from __future__ import annotations

import argparse
import sys

from app.domain.suno_voice.rimjoba import (
    REFERENCE_URL,
    UnknownRimJobaModeError,
    assemble_rimjoba_style,
    list_modes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble RimJoba Suno voice prompt")
    parser.add_argument(
        "mode",
        nargs="?",
        help="Genre mode (street_trap, techno_rap, boom_bap, phonk, club, late_night)",
    )
    parser.add_argument("--list", action="store_true", help="List modes and exit")
    parser.add_argument(
        "--extra-negative",
        default="",
        help="Optional genre-neg append",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Track name without prefix; prints full title RimJoba — <name>",
    )
    args = parser.parse_args(argv)

    if args.list:
        for mode in list_modes():
            print(mode)
        return 0

    if not args.mode:
        parser.error("mode required (or pass --list)")

    try:
        prompt = assemble_rimjoba_style(args.mode, extra_negative=args.extra_negative)
    except UnknownRimJobaModeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    title = f"{prompt.title_prefix} — {args.title}" if args.title.strip() else f"{prompt.title_prefix} — <name>"
    print(f"REFERENCE: {REFERENCE_URL}")
    print(f"MODE: {prompt.mode}")
    print(f"TITLE: {title}")
    print("STYLE:")
    print(prompt.style)
    print("NEGATIVE:")
    print(prompt.negative_tags)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests — expect PASS**

```bash
uv run pytest tests/scripts/test_rimjoba_prompt_cli.py tests/domain/suno_voice/test_rimjoba.py -v
uv run ruff check scripts/rimjoba_prompt.py tests/scripts/test_rimjoba_prompt_cli.py
```

- [ ] **Step 5: Manual smoke**

```bash
uv run python scripts/rimjoba_prompt.py street_trap --title "Все дороги"
uv run python scripts/rimjoba_prompt.py --list
```

Expected: STYLE starts with VOICE BLOCK; TITLE `RimJoba — Все дороги`.

- [ ] **Step 6: Commit**

```bash
git add scripts/rimjoba_prompt.py tests/scripts/test_rimjoba_prompt_cli.py
git commit -m "feat(suno): CLI to assemble RimJoba voice prompts"
```

---

### Task 4: Wire recipe into Suno agent docs (discoverability)

**Files:**
- Modify: `.claude/rules/suno.md` — add short «RimJoba voice recipe» section at end (before or after Gotchas)
- Modify: `docs/tool-catalog.md` only if there is an existing Suno recipes subsection; otherwise skip (YAGNI)

**Interfaces:**
- Consumes: paths from Tasks 1–3
- Produces: agent-visible pointer so DJ/Suno workflows find the recipe

- [ ] **Step 1: Append section to `.claude/rules/suno.md`**

Add at end of file:

```markdown
## RimJoba vocal identity (prompt recipe)

Hard vocal-lock for MC **RimJoba** (Taras / «Графский Самовар» reference).
Prompt-only — do **not** create Persona/Voice unless the user explicitly asks.

- Spec: `docs/superpowers/specs/2026-07-18-rimjoba-suno-voice-recipe-design.md`
- Domain: `app/domain/suno_voice/rimjoba.py` → `assemble_rimjoba_style(mode)`
- Copy-paste: `suno_out/rimjoba/` (`VOICE_BLOCK.txt` + `tails/` + `NEGATIVE.txt`)
- CLI: `uv run python scripts/rimjoba_prompt.py street_trap --title "…"`

Rules when generating RimJoba tracks:
1. Style **must** start with full VOICE BLOCK (never rewrite per mood).
2. Genre only via GENRE TAIL / `tails/<mode>.txt`.
3. Never add `no autotune` or `no singing` — breaks the Taras lock (light AT required).
4. Lyrics: deadpan tags + ad-libs `(е)(а)(ха)(скр)(бра)`; name once in intro + hook.
```

- [ ] **Step 2: No automated test** (docs-only). Manually confirm section renders / file ends cleanly.

- [ ] **Step 3: Commit**

```bash
git add .claude/rules/suno.md
git commit -m "docs(suno): point agents at RimJoba voice recipe"
```

---

### Task 5: Final verification

**Files:** none (verify only)

- [ ] **Step 1: Run focused suite**

```bash
uv run pytest tests/domain/suno_voice tests/scripts/test_rimjoba_prompt_cli.py -v
uv run ruff check app/domain/suno_voice tests/domain/suno_voice scripts/rimjoba_prompt.py tests/scripts/test_rimjoba_prompt_cli.py
```

Expected: all green.

- [ ] **Step 2: Three-genre dry print (no Suno create)**

```bash
uv run python scripts/rimjoba_prompt.py street_trap --title "Все дороги"
uv run python scripts/rimjoba_prompt.py techno_rap --title "Пульт и микрофон"
uv run python scripts/rimjoba_prompt.py boom_bap --title "Высшая проба"
```

Expected: each STYLE starts with identical VOICE BLOCK; tails differ; NEGATIVE identical.

- [ ] **Step 3: Optional live gen (manual, user-driven only)**

Only if user says «сгенерируй»: use assembled blocks via existing `dj_provider_write` session flow. **Not part of automated gate.** Do not run in CI/agent unless explicitly requested.

- [ ] **Step 4: No extra commit unless Step 1 found fixes** — if fixes needed, commit:

```bash
git commit -m "test(suno): harden RimJoba recipe verification"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Immutable VOICE BLOCK (Taras lock) | Task 1 constants + tests |
| GENRE TAIL catalog (6 modes) | Task 1 `GENRE_TAILS` |
| Fixed NEGATIVE anti-drift | Task 1 `NEGATIVE_TAGS` |
| Lyrics skeleton / performance rules | Task 1 `LYRICS_SKELETON` + Task 2 file |
| Workflow Custom Mode no-create | Task 2 README + Task 3 CLI + Task 4 rules |
| Reference clip URL/id | Task 1 `REFERENCE_*` |
| Copy-paste deliverable | Task 2 `suno_out/rimjoba/` |
| No persona/voice create | Global constraint; no write tasks |
| Three-genre consistency check | Task 5 dry print |
| Agent discoverability | Task 4 `.claude/rules/suno.md` |

## Out of scope (do not implement in this plan)

- `provider_write` persona/voice create
- MCP tool / prompt workflow registration
- Regenerating existing RimJoba library tracks
- Import generated MP3 as `audio_file`
