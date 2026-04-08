'use server'

import { getTrackMixMeta, type TrackMixMeta } from '@/lib/queries/mix-meta'

export async function fetchTrackMixMeta(trackId: number): Promise<TrackMixMeta | null> {
  return getTrackMixMeta(trackId)
}
