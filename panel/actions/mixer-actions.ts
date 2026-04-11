'use server'

import { callTool } from '@/lib/mcp-client'

export interface MixerState {
  crossfader: number
  channel_gain: Record<number, number>
  eq: Record<number, { low: number; mid: number; high: number }>
  filter: Record<number, number>
}

async function parseMixer(result: Awaited<ReturnType<typeof callTool>>): Promise<MixerState | null> {
  if (result.is_error) return null
  if (result.structured_content) return result.structured_content as unknown as MixerState
  const text = result.content.find(c => c.type === 'text')?.text
  if (text) try { return JSON.parse(text) } catch { /* ignore */ }
  return null
}

export async function setEq(deckId: number, band: string, gain: number): Promise<MixerState | null> {
  return parseMixer(await callTool('set_eq', { deck_id: deckId, band, gain }))
}

export async function killEq(deckId: number, band: string): Promise<MixerState | null> {
  return parseMixer(await callTool('kill_eq', { deck_id: deckId, band }))
}

export async function resetEq(deckId: number): Promise<MixerState | null> {
  return parseMixer(await callTool('reset_eq', { deck_id: deckId }))
}

export async function setFilter(deckId: number, cutoffHz: number): Promise<MixerState | null> {
  return parseMixer(await callTool('set_filter', { deck_id: deckId, cutoff_hz: cutoffHz }))
}

export async function getMixerState(): Promise<MixerState | null> {
  return parseMixer(await callTool('mixer_state', {}))
}

export async function setCrossfader(target: number): Promise<MixerState | null> {
  return parseMixer(await callTool('mixer_crossfader', { target }))
}
