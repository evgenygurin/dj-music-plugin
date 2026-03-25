# Configuration Reference

All configuration is via environment variables with the `DJ_` prefix. Settings are defined in `app/config.py` using Pydantic Settings.

## Quick Setup

```bash
cp .env.example .env
# Edit .env with your values
```

## Configuration File

Settings are loaded from:
1. Environment variables (highest priority)
2. `.env` file in the project root
3. Default values (lowest priority)

---

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_DATABASE_URL` | `sqlite+aiosqlite:///dj_music.db` | Database connection URL |

### Supported Backends

| Backend | URL Format | Required Extra |
|---------|-----------|----------------|
| SQLite (dev) | `sqlite+aiosqlite:///dj_music.db` | None (bundled) |
| PostgreSQL (prod) | `postgresql+asyncpg://user:pass@host:5432/db` | `postgres` |

---

## Yandex Music

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DJ_YM_TOKEN` | `""` | Yes* | OAuth token |
| `DJ_YM_USER_ID` | `""` | Yes* | User ID |
| `DJ_YM_BASE_URL` | `https://api.music.yandex.net` | No | API base URL |
| `DJ_YM_LIBRARY_PATH` | `""` | Yes* | Local music library path |
| `DJ_YM_RATE_LIMIT_DELAY` | `1.5` | No | Seconds between API calls |

\* Required for YM features. The server starts without them but YM tools will fail.

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_YM_RATE_LIMIT_DELAY` | `1.5` | Minimum seconds between requests |
| `DJ_YM_RETRY_ATTEMPTS` | `3` | Max retries on transient errors |
| `DJ_YM_RETRY_BACKOFF_FACTOR` | `2.0` | Exponential backoff multiplier |

---

## MCP Server

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_SERVER_NAME` | `"DJ Music"` | Server name in MCP |
| `DJ_PAGINATION_SIZE` | `100` | Page size for list operations |
| `DJ_PAGINATION_MAX` | `100` | Maximum page size |
| `DJ_CACHE_DIR` | `"cache/"` | Cache directory |
| `DJ_MCP_RETRY_ATTEMPTS` | `3` | Tool call retry attempts |
| `DJ_MCP_RETRY_DELAY` | `1.0` | Retry delay in seconds |
| `DJ_PAYLOAD_LOGGING` | `false` | Log tool call payloads |
| `DJ_DEBUG` | `false` | Enable debug mode (verbose logging, show error details) |

> **Note:** `DJ_PAGINATION_SIZE` must be >= total tools (100) because Claude Code doesn't follow `nextCursor` pagination.

---

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_LOG_LEVEL` | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `DJ_LOG_FORMAT` | `"json"` | Log format: `json` or `text` |
| `DJ_LOG_TO_CLIENT_DEBUG` | `false` | Forward logs to MCP client |

---

## Transition Scoring

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_TRANSITION_CACHE_TTL` | `3600` | Cache TTL in seconds |
| `DJ_TRANSITION_CACHE_MAX_SIZE` | `10000` | Max cached scores |
| `DJ_TRANSITION_HARD_REJECT_BPM_DIFF` | `10.0` | BPM difference threshold for hard reject |
| `DJ_TRANSITION_HARD_REJECT_CAMELOT_DIST` | `5` | Camelot distance threshold |
| `DJ_TRANSITION_HARD_REJECT_ENERGY_GAP` | `6.0` | LUFS gap threshold |

---

## Storage Backends

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_STORAGE_BACKEND` | `"memory"` | Backend: `memory`, `file`, `redis` |
| `DJ_STORAGE_FILE_DIR` | `"cache/storage"` | File storage directory |
| `DJ_STORAGE_REDIS_HOST` | `"localhost"` | Redis host |
| `DJ_STORAGE_REDIS_PORT` | `6379` | Redis port |
| `DJ_STORAGE_REDIS_PASSWORD` | `""` | Redis password |
| `DJ_STORAGE_REDIS_DB` | `0` | Redis database number |
| `DJ_RESPONSE_CACHE_ENABLED` | `true` | Enable response caching |
| `DJ_RESPONSE_CACHE_TTL` | `300` | Response cache TTL (seconds) |

---

## Discovery & Expansion

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_DISCOVERY_MIN_DURATION_MS` | `180000` | Min track duration (3 min) |
| `DJ_DISCOVERY_MAX_DURATION_MS` | `600000` | Max track duration (10 min) |
| `DJ_DISCOVERY_BATCH_SIZE` | `20` | Tracks per YM add_tracks batch |
| `DJ_DISCOVERY_MAX_SEEDS` | `30` | Max seed tracks for expansion |
| `DJ_DISCOVERY_BAD_GENRES` | `"pop,ruspop,dance,..."` | Genres to filter out |
| `DJ_DISCOVERY_BAD_VERSION_WORDS` | `"radio,edit,acoustic,..."` | Version words to filter |

---

## GA Optimizer

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_GA_POPULATION_SIZE` | `100` | Individuals per generation |
| `DJ_GA_MAX_GENERATIONS` | `200` | Max generations |
| `DJ_GA_MUTATION_RATE` | `0.15` | Mutation probability |
| `DJ_GA_ELITISM_RATE` | `0.05` | Top individuals preserved |
| `DJ_GA_TOURNAMENT_SIZE` | `3` | Tournament selection pressure |
| `DJ_GA_CONVERGENCE_THRESHOLD` | `20` | Generations without improvement before stopping |

---

## Audio Analysis

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_AUDIO_ANALYSIS_TIMEOUT` | `120.0` | Per-track timeout (seconds) |
| `DJ_AUDIO_BATCH_TIMEOUT` | `600.0` | Batch analysis timeout |
| `DJ_AUDIO_STEM_TIMEOUT` | `300.0` | Stem separation timeout |
| `DJ_AUDIO_HOP_LENGTH` | `512` | FFT hop length |
| `DJ_AUDIO_SAMPLE_RATE` | `22050` | Audio sample rate (Hz) |
| `DJ_AUDIO_MFCC_N_COEFFS` | `13` | Number of MFCC coefficients |

---

## Techno Quality Criteria

These settings define the "techno quality gate" for `audit_playlist` and `gate_one_track`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_TECHNO_BPM_MIN` | `120.0` | Minimum BPM |
| `DJ_TECHNO_BPM_MAX` | `155.0` | Maximum BPM |
| `DJ_TECHNO_LUFS_MIN` | `-20.0` | Minimum LUFS |
| `DJ_TECHNO_LUFS_MAX` | `-4.0` | Maximum LUFS |
| `DJ_TECHNO_ENERGY_MIN` | `0.05` | Minimum energy mean |
| `DJ_TECHNO_ONSET_RATE_MIN` | `1.0` | Minimum onset rate |
| `DJ_TECHNO_KICK_PROMINENCE_MIN` | `0.05` | Minimum kick prominence |
| `DJ_TECHNO_PULSE_CLARITY_MIN` | `0.02` | Minimum pulse clarity |
| `DJ_TECHNO_HP_RATIO_MAX` | `8.0` | Maximum harmonic-to-percussive ratio |
| `DJ_TECHNO_CENTROID_MIN` | `300.0` | Minimum spectral centroid (Hz) |
| `DJ_TECHNO_CENTROID_MAX` | `10000.0` | Maximum spectral centroid (Hz) |
| `DJ_TECHNO_FLATNESS_MAX` | `0.5` | Maximum spectral flatness |
| `DJ_TECHNO_TEMPO_CONFIDENCE_MIN` | `0.3` | Minimum tempo detection confidence |
| `DJ_TECHNO_BPM_STABILITY_MIN` | `0.3` | Minimum BPM stability |
| `DJ_TECHNO_CREST_FACTOR_MAX` | `30.0` | Maximum crest factor (dB) |
| `DJ_TECHNO_LRA_MAX` | `25.0` | Maximum loudness range (LU) |
| `DJ_TECHNO_HNR_MIN` | `-30.0` | Minimum harmonic-to-noise ratio (dB) |

---

## Mood Classifier

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_MOOD_CATCH_ALL_PENALTY` | `0.85` | Penalty for catch-all subgenres (driving, hypnotic) |
| `DJ_MOOD_CONFIDENCE_THRESHOLD` | `0.3` | Minimum confidence for classification |

---

## Delivery

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_DELIVERY_OUTPUT_DIR` | `"generated-sets/"` | Output directory for set delivery |
| `DJ_DELIVERY_ICLOUD_STUB_THRESHOLD` | `0.9` | blocks/size ratio for iCloud stub detection |

---

## LLM Sampling

For server-side LLM sampling (not needed for Claude Code MAX users):

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_ANTHROPIC_API_KEY` | `""` | Anthropic API key (optional) |
| `DJ_SAMPLING_MODEL` | `"claude-sonnet-4-5"` | LLM model for sampling |
| `DJ_SAMPLING_MAX_TOKENS` | `512` | Max tokens per sampling call |
| `DJ_SAMPLING_TEMPERATURE` | `0.8` | Sampling temperature |

---

## Background Tasks

| Variable | Default | Description |
|----------|---------|-------------|
| `DJ_DOCKET_URL` | `"memory://"` | FastMCP Docket URL |
| `DJ_DOCKET_CONCURRENCY` | `4` | Max concurrent background tasks |
| `DJ_TASK_POLL_INTERVAL_SECONDS` | `5` | Task polling interval |

---

## Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRY_DSN` | `""` | Sentry error tracking DSN |
| `DJ_OTEL_ENABLED` | `false` | Enable OpenTelemetry |
| `DJ_OTEL_SERVICE_NAME` | `"dj-music"` | OTEL service name |
| `DJ_OTEL_ENDPOINT` | `""` | OTEL collector endpoint |

---

## Example `.env` File

```bash
# Required
DJ_YM_TOKEN=your_oauth_token
DJ_YM_USER_ID=your_user_id
DJ_YM_LIBRARY_PATH=/Users/you/Music/Music/Media.localized/

# Recommended
DJ_DATABASE_URL=sqlite+aiosqlite:///dj_music.db
DJ_DEBUG=false
DJ_LOG_LEVEL=INFO

# Optional: Server-side sampling
# DJ_ANTHROPIC_API_KEY=sk-ant-...

# Optional: Observability
# SENTRY_DSN=https://...@sentry.io/...
```

## Related Pages

- **[Getting Started](Getting-Started)** -- Initial setup guide
- **[Architecture](Architecture)** -- How configuration is used
- **[Transition Scoring](Transition-Scoring)** -- Scoring thresholds
- **[Audio Analysis Pipeline](Audio-Analysis-Pipeline)** -- Audio settings
- **[Performance](Performance)** -- Performance-related settings
