# Declarative Set Draft — FastMCP Full-Stack Design

> The AI builds a set iteratively, reviews it with narrative feedback, then
> confirms with the user — all through native FastMCP capabilities.

**Date:** 2026-04-16
**Status:** Approved

---

## Problem

The current declarative flow (`get_candidate_pool → preview_set_arc →
commit_set_version`) works, but is atomic: the AI must assemble the entire
`track_ids` list in its own context and submit it in one shot. Three gaps
remain:

1. **No iteration.** A wrong ordering requires rebuilding the full list from
   scratch. There is no "move track 8 to position 12" without recomputing
   everything.
2. **No narrative.** `quality_score: 0.72` is a number. The AI (and user)
   need to know *why* — which transitions drag, what the crowd experiences at
   each phase, where the energy sags.
3. **No human confirmation gate.** `commit_set_version` writes to the DB
   immediately. The user has no chance to review the summary before saving.

---

## Solution — FastMCP Native Capabilities

Five FastMCP features, none currently used in the set-building flow:

| Feature | Used for |
|---|---|
| `ctx.set_state()` / `ctx.get_state()` | Session-scoped draft: survives across tool calls |
| `ctx.sample(result_type=ArcCritique)` | Server-side narrative from the client LLM |
| `ctx.read_resource()` | Tools read `knowledge://` resources for sampling context |
| `ctx.elicit(response_type=None)` | User confirms before DB write |
| `ctx.report_progress()` | Progress updates in arc scoring and transition scoring |

---

## Architecture

### New files

```text
app/schemas/arc_critique.py                  ← ArcCritique Pydantic model
app/controllers/tools/draft.py               ← 4 new tools
app/controllers/resources/session_draft.py   ← session://set-draft resource
```

### Modified files

```text
app/controllers/tools/sets.py                ← add ctx.report_progress() to score_transitions
app/controllers/prompts/workflows/dj_expert_session.py  ← step 4 updated
```

`FileSystemProvider` auto-discovers new files — no changes to
`app/bootstrap/server_builder.py`. Sampling fallback via Anthropic is already
configured in `app/bootstrap/sampling.py`.

---

## Session State Schema

One key `"set_draft"` stored per MCP session:

```python
{
    "name": "Loft Party 1AM",       # str — used as set name on commit
    "template": "roller_90",         # str | None — arc scoring template
    "track_ids": [101, 207, 88, ...]  # list[int] — ordered, the full draft
}
```

Ephemeral: lives for the session lifetime, never written to the database
until `commit_draft` is called and confirmed.

State key constant defined once in `app/controllers/tools/draft.py`:

```python
_DRAFT_KEY = "set_draft"
```

---

## ArcCritique Model

Location: `app/schemas/arc_critique.py`

```python
class ArcCritique(BaseModel):
    crowd_journey: str
    # "Opens restrained and hypnotic → industrial build at tracks 5–8 →
    #  peak pressure at track 10 → atmospheric release at close"

    weak_transitions: list[str]
    # ["Track 8→9: same BPM and energy level, no dynamic shift",
    #  "Track 12→13: key clash (C minor → F# major, Camelot distance 6)"]

    strongest_moment: str
    # "Track 10 (industrial, 138 BPM) — expect peak crowd response here"

    recommendation: str
    # "Swap track 6 (minimal, low energy) earlier to create contrast
    #  before the industrial block"
```

Used as `result_type` in `ctx.sample()`. FastMCP handles auto-retry if the
LLM returns invalid JSON.

---

## Tools

All four tools live in `app/controllers/tools/draft.py`.

### `update_set_draft`

Writes or replaces the session-scoped draft. Called after every ordering
decision.

```text
Inputs:  track_ids: list[int], name?: str, template?: str
Context: ctx.set_state("set_draft", {...})
Output:  {track_count: int, name: str, template: str|None, updated: true}
```

Atomic replace — no partial update semantics needed.

### `preview_draft`

Computes arc fitness on the current draft. Optionally generates narrative
via `ctx.sample()`.

```bash
Inputs:  narrative: bool = False
Context: ctx.get_state("set_draft")
         ctx.report_progress(0..3, "Loading features" | "Computing arc" | "Generating narrative")
         if narrative:
             ctx.read_resource("knowledge://dancefloor-psychology")
             ctx.read_resource("knowledge://set-dynamics")
             ctx.sample(messages=..., system_prompt=resources, result_type=ArcCritique)
Output:  {score, energy_arc, bpm_arc, weak_spots, track_count, critique?: ArcCritique}
```

Fast mode (`narrative=False`): no LLM call, only arc math.
Full mode (`narrative=True`): adds `critique` field with `ArcCritique`.

Error path: if draft is empty → `ValidationError("No draft set. Call update_set_draft first.")`.

Sampling error path: if `ctx.sample()` fails (client doesn't support
sampling, no fallback key), `critique` is omitted and a `ctx.warning()` is
emitted. The arc scores are still returned.

### `commit_draft`

Confirms with the user via `ctx.elicit()`, then saves to the database.

```bash
Inputs:  version_label?: str
Context: ctx.get_state("set_draft")
         preview_arc(track_ids) → quality_score, weak_spots count
         ctx.elicit(
             message=f"Save '{name}': {N} tracks, score {q:.2f}, "
                     f"{len(weak)} weak transitions. Confirm?",
             response_type=None    ← accept/decline only, no data field
         )
         if accept:
             svc.commit_version(name, track_ids, template, version_label)
             ctx.delete_state("set_draft")
Output:  {set_id, version_id, version_label, quality_score, track_count}
      or {cancelled: true}  on decline/cancel
```

Elicitation error path: if client doesn't support elicitation, skip the
gate and save directly (same behaviour as `commit_set_version`). Log a
`ctx.info()` warning.

### `clear_draft`

Resets the session draft.

```text
Inputs:  (none)
Context: ctx.delete_state("set_draft")
Output:  {cleared: true}
```

---

## Resource: `session://set-draft`

Location: `app/controllers/resources/session_draft.py`

```python
@resource("session://set-draft")
async def get_set_draft(ctx: Context = CurrentContext()) -> dict:
    """Read the current session-scoped set draft."""
    return await ctx.get_state("set_draft") or {}
```

The AI can inspect the draft as a read-only resource without calling a tool.
Returns `{}` if no draft exists.

---

## Change to `score_transitions`

Add progress reporting to `score_transitions(mode="set")` in
`app/controllers/tools/sets.py`:

```python
await ctx.report_progress(0, total, "Scoring transitions")
# ... for each pair:
await ctx.report_progress(i + 1, total, f"Pair {i+1}/{total}")
```

No logic change. The `ctx` parameter is already present via `Context | None`.

---

## Prompt Update: `dj_expert_session` Step 4

Replace current step 4 with:

```text
**Step 4 — Adopt these behavioral rules:**
- Translate human intent using knowledge://vocabulary. Never ask "what BPM range?"
- Make reasonable assumptions and state them briefly (one sentence max)
- Ask questions only when intent is genuinely ambiguous — at most one question
- Speak like a DJ, not a database interface
- Set building workflow — you own the track selection and ordering:
  1. get_candidate_pool → explore library by mood/subgenre/energy
  2. update_set_draft(track_ids=[...]) → save your working order
  3. preview_draft(narrative=False) → fast arc check; repeat steps 2–3 to refine
  4. preview_draft(narrative=True) → full narrative before committing
  5. commit_draft() → user confirms, version saved
- Use clear_draft() to start over at any point
- Never delegate ordering to an optimizer — curate the arc yourself
```

---

## Data Flow Example

```bash
User: "dark and driving, loft party, 1AM, 90 minutes"

dj_expert_session() boots AI with library + knowledge
    ↓
get_candidate_pool(subgenres=["detroit","industrial","peak_time"], bpm_min=130, limit=60)
    → 47 tracks

update_set_draft(track_ids=[101, 207, 88, 312, ...], name="Loft 1AM", template="roller_90")
    → {track_count: 14, updated: true}

preview_draft(narrative=False)
    → {score: 0.71, weak_spots: [8, 9], energy_arc: [...]}

# AI moves track at position 9 before position 8

update_set_draft(track_ids=[101, 207, 88, 312, ..., 312_new_pos, ...])
    → {track_count: 14, updated: true}

preview_draft(narrative=True)
    → {score: 0.81, critique: {
           crowd_journey: "Opens hypnotic 130 BPM → industrial build...",
           weak_transitions: [],
           strongest_moment: "Track 10",
           recommendation: "Swap track 5 earlier for contrast"
       }}

commit_draft("v1-loft")
    → ctx.elicit: "Save 'Loft 1AM': 14 tracks, score 0.81, 0 weak transitions. Confirm?"
    → user accepts
    → {set_id: 42, version_id: 7, quality_score: 0.81, track_count: 14}
```

---

## Testing Strategy

| File | What it tests |
|---|---|
| `tests/test_tools/test_draft_tools.py` | All 4 tools: state read/write, arc logic, mocked elicitation, mocked sampling |
| `tests/test_tools/test_draft_session_resource.py` | `session://set-draft` resource: empty state, state after update |
| `tests/test_services/test_arc_critique.py` | `ArcCritique` Pydantic validation and serialization |
| `tests/acceptance/test_draft_flow.py` | End-to-end: update → preview → commit → DB row exists with correct order |

Sampling (`ctx.sample`) is always mocked in tests.
Elicitation (`ctx.elicit`) is mocked via `client.set_elicitation_handler()`.

---

## What Does Not Change

- `commit_set_version` remains for programmatic / non-interactive use
- `preview_set_arc` remains as a standalone arc tool (no session state dependency)
- `get_candidate_pool` unchanged
- All existing tests pass without modification
- Database schema unchanged

---

## Files Summary

| File | Action |
|---|---|
| `app/schemas/arc_critique.py` | Create |
| `app/controllers/tools/draft.py` | Create |
| `app/controllers/resources/session_draft.py` | Create |
| `app/controllers/tools/sets.py` | Modify — add `ctx.report_progress()` |
| `app/controllers/prompts/workflows/dj_expert_session.py` | Modify — step 4 |
| `tests/test_tools/test_draft_tools.py` | Create |
| `tests/test_tools/test_draft_session_resource.py` | Create |
| `tests/test_services/test_arc_critique.py` | Create |
| `tests/acceptance/test_draft_flow.py` | Create |
