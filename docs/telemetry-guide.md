# OpenTelemetry Integration Guide

FastMCP v3 includes native OpenTelemetry instrumentation for distributed tracing. This guide covers how to enable and use telemetry in the DJ Music Plugin.

## Quick Start

### 1. Install OTEL Dependencies

```bash
uv sync --extra otel
```

This installs:
- `opentelemetry-distro` — Auto-instrumentation
- `opentelemetry-exporter-otlp` — OTLP exporter for traces

### 2. Run with Telemetry

Use `opentelemetry-instrument` wrapper to enable tracing:

```bash
# With command-line args
opentelemetry-instrument \
  --service_name dj-music \
  --exporter_otlp_endpoint http://localhost:4317 \
  fastmcp run app/server.py

# Or via environment variables
export OTEL_SERVICE_NAME=dj-music
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
opentelemetry-instrument fastmcp run app/server.py
```

### 3. Set Up an OTEL Backend

Choose one:
- **Jaeger** (local dev): `docker run -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one`
- **Grafana Tempo** (production)
- **Datadog** (SaaS)
- **New Relic** (SaaS)

## What Gets Traced

### Automatic (FastMCP)

FastMCP automatically creates spans for:
- `tools/call {name}` — Tool execution (e.g., `tools/call build_set`)
- `resources/read {uri}` — Resource reads
- `prompts/get {name}` — Prompt rendering

### Custom (DJ Music Plugin)

We add custom instrumentation for:

#### 1. Heavy Operations

Tools decorated with `@instrument_heavy_operation` get detailed spans:

```python
from app.telemetry import instrument_heavy_operation

@instrument_heavy_operation("build_set")
async def build_set_service(...):
    ...
```

**Automatically instrumented:**
- `build_set` (genetic algorithm optimization)
- `analyze_batch` (audio analysis pipeline)
- `deliver_set` (multi-stage delivery)

#### 2. Middleware

Two middleware layers add observability:

**DetailedTimingMiddleware** (innermost):
- Measures execution time for every MCP operation
- Adds `dj.timing.duration_ms` to span attributes
- Logs timing in debug mode

**StructuredLoggingMiddleware** (outermost):
- Logs all requests/responses with structured data
- Includes method, source, type, status
- Captures params when `DJ_PAYLOAD_LOGGING=true`

## Span Attributes

All custom spans include:

| Attribute | Example | Description |
|-----------|---------|-------------|
| `dj.operation` | `"build_set"` | Operation name |
| `dj.debug_mode` | `true` | Debug flag |
| `dj.arg.0`, `dj.arg.1` | `42`, `"playlist"` | First 3 positional args (if primitive) |
| `dj.param.{name}` | `dj.param.count=50` | Keyword arguments (if primitive) |
| `dj.param.{name}.count` | `dj.param.tracks.count=100` | List argument counts |
| `dj.timing.duration_ms` | `1234.56` | Execution time (from middleware) |
| `dj.timing.success` | `true` | Success/failure flag |
| `dj.timing.method` | `"tools/call"` | MCP method |

## Adding Custom Spans

### In Service Layer

```python
from app.telemetry import instrument_heavy_operation

@instrument_heavy_operation("optimize_transitions")
async def optimize_transitions(tracks: list[Track]) -> list[Transition]:
    # This function now gets a span with:
    # - Name: "dj.optimize_transitions"
    # - Attribute: dj.operation="optimize_transitions"
    # - Attribute: dj.param.tracks.count=len(tracks)
    ...
```

### Adding Events

```python
from app.telemetry import add_span_event

# In a GA optimization loop
for generation in range(max_generations):
    population = evolve(population)
    add_span_event("ga_generation", {
        "generation": generation,
        "best_score": max(population).score,
    })
```

### Setting Attributes

```python
from app.telemetry import set_span_attributes

# After set generation
set_span_attributes(
    track_count=len(set_version.items),
    total_duration_min=set_version.duration_ms / 60000,
    template=set_version.template_name,
)
```

### Recording Errors

```python
from app.telemetry import record_error

try:
    analyze_track(track_id)
except AnalyzerUnavailableError as e:
    record_error(e, "Librosa not installed, skipping beat detection")
    # Span is marked ERROR but execution continues
```

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_SERVICE_NAME` | `dj-music` | Service name in traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP endpoint (e.g., `http://localhost:4317`) |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` | Transport protocol (`grpc` or `http/protobuf`) |
| `OTEL_TRACES_SAMPLER` | `always_on` | Sampling strategy |
| `OTEL_TRACES_SAMPLER_ARG` | `1.0` | Sample rate (0.0-1.0 for `traceidratio`) |
| `DJ_DEBUG` | `false` | Enable debug logging (includes timing logs) |
| `DJ_PAYLOAD_LOGGING` | `false` | Log request params (can be verbose) |

### Sampling Strategies

For production, reduce trace volume:

```bash
# Sample 10% of traces
export OTEL_TRACES_SAMPLER=traceidratio
export OTEL_TRACES_SAMPLER_ARG=0.1
```

## Sentry Integration

Optional Sentry error tracking (requires `uv sync --extra sentry`):

```bash
export SENTRY_DSN=https://your-dsn@sentry.io/project-id
fastmcp run app/server.py
```

**Sentry features:**
- Exception tracking (all errors)
- Performance monitoring (10% of traces in prod, 100% in dev)
- Breadcrumbs from OTEL spans (if Sentry OTEL integration enabled)

## Example Trace Hierarchy

```
tools/call build_set (CLIENT)
  └── tools/call build_set (SERVER, provider=FileSystemProvider)
        ├── dj.build_set (INTERNAL, DetailedTimingMiddleware)
        │     ├── dj.optimize_set (INTERNAL, GeneticAlgorithm)
        │     │     ├── event: ga_generation (gen=0, best_score=0.65)
        │     │     ├── event: ga_generation (gen=1, best_score=0.72)
        │     │     └── ... (200 generations)
        │     └── dj.score_transitions (INTERNAL)
        │           └── (1,500 transition pairs scored)
        └── attributes:
              - dj.timing.duration_ms: 42,356
              - dj.timing.success: true
              - dj.param.playlist_id: 123
              - dj.param.template: "classic_60"
```

## Troubleshooting

### No Spans Appear

1. Check OTLP endpoint is reachable:
   ```bash
   curl -v http://localhost:4317
   ```

2. Verify SDK is installed:
   ```bash
   uv pip list | grep opentelemetry
   ```

3. Enable debug logging:
   ```bash
   export OTEL_LOG_LEVEL=debug
   opentelemetry-instrument fastmcp run app/server.py
   ```

### High Cardinality Warnings

If you see warnings about high-cardinality attributes (e.g., track IDs):
- We intentionally exclude IDs from span attributes
- Only primitive first 3 args are included
- List/dict params show count, not contents

### Performance Impact

OpenTelemetry overhead:
- **Without SDK**: ~0% (all operations are no-ops)
- **With SDK + sampling off**: ~1-2% CPU
- **With SDK + full tracing**: ~5-10% CPU (acceptable for dev, use sampling in prod)

## References

- [FastMCP Telemetry Docs](https://gofastmcp.com/servers/telemetry)
- [OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
