'use server'

import { callTool } from '@/lib/mcp-client'
import type { SetTemplate } from '@/lib/set-narrative/types'

interface RawSlot {
  position: number
  target_mood: string | null
  energy_lufs: number
  bpm_min: number
  bpm_max: number
  duration_ms: number
  flexibility: number
}

interface RawTemplate {
  name: string
  duration_min: number
  description: string
  slots: RawSlot[]
}

/**
 * Fetch set templates from the MCP backend.
 *
 * Returns an empty array on any failure (backend down, malformed response,
 * tool not registered) so the UI renders its empty state instead of
 * crashing the page with a 500.
 */
export async function fetchSetTemplates(): Promise<SetTemplate[]> {
  let response
  try {
    response = await callTool('get_set_templates', {})
  } catch {
    return []
  }

  if (response.is_error) return []

  const sc = response.structured_content as { templates?: RawTemplate[] } | null
  if (!sc?.templates || !Array.isArray(sc.templates)) return []

  return sc.templates.map((tpl) => ({
    name: tpl.name,
    durationMin: tpl.duration_min,
    description: tpl.description,
    slots: tpl.slots.map((slot) => ({
      position: slot.position,
      targetMood: slot.target_mood,
      energyLufs: slot.energy_lufs,
      bpmMin: slot.bpm_min,
      bpmMax: slot.bpm_max,
      durationMs: slot.duration_ms,
      flexibility: slot.flexibility,
    })),
  }))
}
