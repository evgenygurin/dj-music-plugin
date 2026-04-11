'use server'

import { createClient } from '@/lib/supabase/server'

/** Record positive/negative feedback for a track. Persists to DB for future scoring. */
export async function recordTrackFeedback(
  trackId: number,
  rating: 'like' | 'ban',
): Promise<{ success: boolean }> {
  const supabase = await createClient()

  // Upsert into a feedback table — create if not exists, update if exists
  const { error } = await supabase
    .from('dj_set_feedback')
    .upsert(
      {
        track_id: trackId,
        rating: rating === 'like' ? 5 : 1,
        feedback_type: 'manual',
        notes: rating,
      },
      { onConflict: 'track_id,feedback_type' },
    )

  if (error) {
    // Table may not have unique constraint on (track_id, feedback_type)
    // Fall back to insert
    await supabase.from('dj_set_feedback').insert({
      track_id: trackId,
      rating: rating === 'like' ? 5 : 1,
      feedback_type: 'manual',
      notes: rating,
    })
  }

  return { success: true }
}
