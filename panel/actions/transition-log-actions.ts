'use server'

import { callTool } from '@/lib/mcp-client'
import type { TransitionLog } from '@/components/audio-player/audio-player-types'

export async function logTransition(log: TransitionLog): Promise<{ id: number } | null> {
  const result = await callTool('log_transition', {
    from_track_id: log.from.id,
    to_track_id: log.to.id,
    overall_score: log.overallScore,
    bpm_score: null,
    harmonic_score: null,
    energy_score: null,
    spectral_score: null,
    groove_score: null,
    timbral_score: null,
    style: log.resolvedStyle,
    duration_sec: log.durationSec,
    tempo_match_ratio: log.tempoMatchRatio,
    user_reaction: null,
    session_id: null,
  })
  if (result.is_error) return null
  if (result.structured_content) return { id: (result.structured_content as { id: number }).id }
  return null
}

export async function updateTransitionReaction(
  entryId: number,
  reaction: 'like' | 'ban' | 'skip' | 'listened',
): Promise<boolean> {
  const result = await callTool('update_reaction', {
    entry_id: entryId,
    reaction,
  })
  return !result.is_error
}
