'use server'

import { callTool } from '@/lib/mcp-client'

/**
 * Subset of `TransitionLog` (audio-player-types.ts) actually consumed by
 * the persistence call. Narrowed here so callers can pass a partial
 * console-log object without satisfying every field of the full
 * `TransitionLog` interface (which is the strict shape used for DevTools
 * structured logging — missing fields default to null on persist).
 *
 * Field name aliases accepted for backward compat with the audio player's
 * structured-log object: `style` ≡ `resolvedStyle`, `tempoRatio` ≡
 * `tempoMatchRatio`.
 */
export interface LogTransitionInput {
  from: { id: number | undefined }
  to: { id: number | undefined }
  overallScore?: number | null
  resolvedStyle?: string
  style?: string
  durationSec: number
  tempoMatchRatio?: number
  tempoRatio?: number
}

/**
 * Persist a transition event to the `transition_history` table.
 *
 * v1.0 mapping: legacy `log_transition(...)` → `entity_create(entity=
 * "transition_history", data={...})`. The TransitionHistoryCreate schema
 * accepts the same fields plus an optional `user_reaction` (positive |
 * neutral | negative — different vocabulary from the legacy "like|ban|
 * skip|listened"; updateTransitionReaction below maps the legacy values).
 */
export async function logTransition(log: LogTransitionInput): Promise<{ id: number } | null> {
  if (log.from.id === undefined || log.to.id === undefined) return null
  const result = await callTool('entity_create', {
    entity: 'transition_history',
    data: {
      from_track_id: log.from.id,
      to_track_id: log.to.id,
      overall_score: log.overallScore ?? null,
      bpm_score: null,
      harmonic_score: null,
      energy_score: null,
      spectral_score: null,
      groove_score: null,
      timbral_score: null,
      style: log.resolvedStyle ?? log.style ?? null,
      duration_sec: log.durationSec,
      tempo_match_ratio: log.tempoMatchRatio ?? log.tempoRatio ?? null,
      user_reaction: null,
      session_id: null,
    },
  })
  if (result.is_error) return null
  if (result.structured_content) {
    const sc = result.structured_content as { data?: { id?: number }; id?: number }
    const id = sc.data?.id ?? sc.id
    if (typeof id === 'number') return { id }
  }
  return null
}

/**
 * Update the user_reaction on a logged transition.
 *
 * v1.0 mapping: legacy `update_reaction(entry_id, reaction)` → `entity_update(
 * entity="transition_history", id, data={user_reaction})`.
 *
 * The legacy reaction vocabulary was {like, ban, skip, listened}; the v1
 * TransitionHistoryUpdate schema accepts {positive, neutral, negative}.
 * Mapping (best-effort):
 *   like     → positive
 *   ban      → negative
 *   skip     → negative
 *   listened → neutral
 *
 * `entity_update` lives in the `crud:destructive` namespace which starts
 * locked — caller may need to first invoke `unlock_namespace(namespace=
 * "crud:destructive", action="unlock")`.
 */
export async function updateTransitionReaction(
  entryId: number,
  reaction: 'like' | 'ban' | 'skip' | 'listened',
): Promise<boolean> {
  const userReaction =
    reaction === 'like'
      ? 'positive'
      : reaction === 'listened'
        ? 'neutral'
        : 'negative'
  const result = await callTool('entity_update', {
    entity: 'transition_history',
    id: entryId,
    data: { user_reaction: userReaction },
  })
  return !result.is_error
}
