'use server'

import { revalidateTag } from 'next/cache'
import { callTool, type ToolCallResult } from '@/lib/mcp-client'

export async function buildSet(
  playlistId: number,
  name: string,
  template?: string,
  algorithm: 'greedy' | 'ga' = 'ga'
): Promise<ToolCallResult> {
  const result = await callTool('build_set', {
    playlist_id: playlistId,
    name,
    template: template ?? undefined,
    algorithm,
  })
  revalidateTag('sets', 'default')
  return result
}

export async function rebuildSet(
  setId: number,
  options: {
    pin?: number[]
    unpin?: number[]
    exclude?: number[]
    algorithm?: 'greedy' | 'ga'
    version_label?: string
  } = {}
): Promise<ToolCallResult> {
  const result = await callTool('rebuild_set', { set_id: setId, ...options })
  revalidateTag('sets', 'default')
  return result
}

export async function deliverSet(
  setId: number,
  options: { version?: number; copy_files?: boolean; sync_to_ym?: boolean; dry_run?: boolean } = {}
): Promise<ToolCallResult> {
  const result = await callTool('deliver_set', { set_id: setId, ...options })
  revalidateTag('sets', 'default')
  return result
}

export async function scoreTransitions(setId: number): Promise<ToolCallResult> {
  const result = await callTool('score_transitions', { mode: 'set', set_id: setId })
  revalidateTag('sets', 'default')
  return result
}

export async function getCheatSheet(setId: number): Promise<ToolCallResult> {
  return callTool('get_set_cheat_sheet', { set_id: setId })
}

export async function exportSet(
  setId: number,
  format: 'json' | 'm3u8' | 'rekordbox' = 'json'
): Promise<ToolCallResult> {
  return callTool('export_set', { set_id: setId, format })
}
