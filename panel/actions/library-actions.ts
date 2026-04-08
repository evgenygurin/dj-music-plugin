'use server'

import { getTrackList, type TrackListParams, type TrackRow } from '@/lib/queries/tracks'

export interface LoadMoreResult {
  tracks: TrackRow[]
  total: number
  hasMore: boolean
  nextPage: number
}

export async function loadMoreTracks(params: TrackListParams): Promise<LoadMoreResult> {
  const result = await getTrackList(params)
  const page = params.page ?? 1
  const pageSize = params.pageSize ?? 50
  return {
    tracks: result.tracks,
    total: result.total,
    hasMore: page * pageSize < result.total,
    nextPage: page + 1,
  }
}
