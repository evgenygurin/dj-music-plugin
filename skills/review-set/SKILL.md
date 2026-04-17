---
name: review-set
description: "Use when the user asks to review a set, analyze set quality, score transitions, find weak transitions, explain why a transition is weak, compare set versions, or check for hard conflicts. Covers fast and deep set review, transition explanation, replacement suggestion."
version: 0.8.2
---

# Review DJ Set Workflow

Guide the user through analyzing the quality of a built DJ set, identifying weak transitions, and proposing fixes — without rebuilding the whole set.

## Steps

1. **Identify the set**
   - If the user references it by name, resolve via `get_set(query="...")`
   - Otherwise list candidates with `list_sets(limit=20)`
   - Note the latest version: `get_set(id=..., view="summary")` → `latest_version_id`

2. **Fast quality overview**
   - `quick_set_review(set_id=...)` — total quality score, hard conflicts, weak transitions, energy arc match, subgenre variety
   - Report the headline numbers in plain language. Stop here if nothing is broken.

3. **Score every transition**
   - `score_transitions(mode="set", set_id=...)` — full per-pair breakdown
   - Sort by `overall` ascending; surface the 3 worst.
   - For each weak pair, identify the limiting component (`bpm` / `harmonic` / `energy` / `spectral` / `groove` / `timbral`).

4. **Explain a single weak transition**
   - `explain_transition(from_track_id=..., to_track_id=...)` — narrative breakdown of all 6 components
   - Show `hard_reject` flag and `reject_reason` if present
   - Mention `used_section_context`: when `false`, drum-only relaxation didn't kick in — suggesting the user re-`deliver_set` after adding mix points may improve scoring

5. **Propose replacements**
   - `find_replacement(set_id=..., position=N, count=5)` — top candidates that fit the slot
   - For each candidate, present BPM, key, energy, mood, plus the projected new transition score

6. **Iterate (delegated to /build-set)**
   - When the user picks replacements, hand off: `/build-set` workflow knows `rebuild_set(set_id=..., pin_tracks=[...], exclude_tracks=[...])`
   - Or call directly: `rebuild_set(...)` then `compare_set_versions(set_id=...)` to confirm improvement

7. **Narrative review (optional)**
   - `analyze_set_narrative(set_id=...)` — story arc, tension/release pattern, subgenre journey
   - Use this for deeper aesthetic review beyond raw scores

## Score Interpretation

| Range | Verdict |
|-------|---------|
| `overall >= 0.75` | Strong transition |
| `0.55 - 0.74` | Acceptable, could be smoother |
| `0.40 - 0.54` | Weak — consider replacement |
| `< 0.40` | Soft conflict — likely audible problem |
| `0.0 + hard_reject=true` | Hard reject (BPM > 10, Camelot ≥ 5, or energy gap > 6 LUFS) — must fix |

## Component Cheat Sheet

When a single component drags the score down:

- **BPM low** → tracks > 10 BPM apart, or low `bpm_stability`/`bpm_confidence`
- **Harmonic low** → Camelot distance ≥ 3 OR atonal pair without drum-only relaxation
- **Energy low** → > 3 LUFS step (especially downward without a breakdown section)
- **Spectral low** → MFCC distance high → very different timbre / mix character
- **Groove low** → onset_rate or kick_prominence mismatch — different feel
- **Timbral low** → HNR / chroma_entropy / dynamic_complexity gap

## Tips

- Always run `quick_set_review` first — it's <1s and tells you whether deeper analysis is needed.
- Hard rejects (`overall=0.0`) block delivery via the elicitation gate in `deliver_set`. Surface them prominently.
- For a single transition, prefer `explain_transition` over `score_transitions(mode="pair")` — same data plus narrative reasoning.
- Tool reference: @docs/tool-catalog.md (quick_set_review, score_transitions, explain_transition, find_replacement, compare_set_versions, analyze_set_narrative, rebuild_set)
- Scoring formula: @docs/transition-scoring.md
