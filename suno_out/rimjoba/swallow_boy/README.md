# Swallow Boy short variants

Reference: `https://suno.com/song/ed011c66-bd94-4bb2-bfd8-ec96a78ddc93`

Generation goal:

- `chirp-fenix`
- short-form `15-35 s`
- one fixed `swallow boy` voice core
- 10 controlled twists

Run:

```bash
uv run python scripts/swallow_boy_variants.py
```

If auth is expired:

```bash
uv run python scripts/suno_refresh_token.py
```

Artifacts:

- `SUMMARY.json`
- `LISTEN.md`
- downloaded mp3 files
