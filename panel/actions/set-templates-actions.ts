'use server'

import { callTool } from '@/lib/mcp-client'
import type { SetTemplate } from '@/lib/set-narrative/types'

export async function fetchSetTemplates(): Promise<SetTemplate[]> {
  const response = await callTool('get_set_templates', {})

  if (response.is_error) {
    throw new Error(`MCP error: ${response.content?.[0]?.text ?? 'unknown error'}`)
  }

  const result = response.structured_content as any

  if (!result.templates) {
    throw new Error('Invalid templates response from MCP server')
  }

  return result.templates.map((tpl: any) => ({
    name: tpl.name,
    durationMin: tpl.duration_min,
    description: tpl.description,
    slots: tpl.slots.map((slot: any) => ({
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
