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

interface RawTemplatesPayload {
  templates?: RawTemplate[]
  total?: number
}

/**
 * Fetch set templates from the MCP backend.
 *
 * v1.0 mapping: legacy `get_set_templates` → `read_resource(uri="reference://
 * templates")`. The resource returns a JSON payload with shape
 * `{total, templates: [{name, duration_min, description, slots: [...]}]}`.
 *
 * `read_resource` is a FastMCP synthetic tool — depending on transport, the
 * payload shows up either in `structured_content` directly, or as the JSON
 * text of the first content item. We probe both.
 *
 * Returns an empty array on any failure (backend down, malformed response,
 * resource missing) so the UI renders its empty state instead of crashing
 * the page with a 500.
 */
export async function fetchSetTemplates(): Promise<SetTemplate[]> {
  let response
  try {
    response = await callTool('read_resource', { uri: 'reference://templates' })
  } catch {
    return []
  }

  if (response.is_error) return []

  let payload: RawTemplatesPayload | null = null

  // 1. Direct structured shape: { templates: [...] }.
  const sc = response.structured_content as RawTemplatesPayload | null
  if (sc?.templates && Array.isArray(sc.templates)) {
    payload = sc
  }

  // 2. Nested under FastMCP `read_resource` envelope:
  //    { contents: [{ text: "<json>", uri, mimeType }] }
  //    OR { result: <decoded payload> } depending on transport.
  if (!payload && sc) {
    const wrapped = sc as Record<string, unknown>
    const nested =
      (wrapped.result as RawTemplatesPayload | undefined) ??
      (wrapped.payload as RawTemplatesPayload | undefined)
    if (nested?.templates && Array.isArray(nested.templates)) {
      payload = nested
    }
    const contents = wrapped.contents as
      | Array<{ text?: string }>
      | undefined
    if (!payload && Array.isArray(contents) && contents[0]?.text) {
      try {
        const parsed = JSON.parse(contents[0].text) as RawTemplatesPayload
        if (parsed?.templates && Array.isArray(parsed.templates)) {
          payload = parsed
        }
      } catch {
        // ignore — fall through
      }
    }
  }

  // 3. Fallback: walk content items, parse the first text payload as JSON.
  if (!payload) {
    for (const item of response.content) {
      if (item.type !== 'text' || !item.text) continue
      try {
        const parsed = JSON.parse(item.text) as RawTemplatesPayload
        if (parsed?.templates && Array.isArray(parsed.templates)) {
          payload = parsed
          break
        }
      } catch {
        // not JSON — try next item
      }
    }
  }

  if (!payload?.templates) return []

  return payload.templates.map((tpl) => ({
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
