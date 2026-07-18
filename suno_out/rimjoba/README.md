# RimJoba — Suno voice recipe (copy-paste)

Референс: https://suno.com/song/e4d68e9a-d35d-4e70-8af0-4205cf484d2f

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
