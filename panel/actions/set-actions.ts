'use server'

import { revalidateTag } from 'next/cache'
import { callTool, type ToolCallResult } from '@/lib/mcp-client'
import { createClient } from '@/lib/supabase/server'

/**
 * Build a new DJ set version from a playlist.
 *
 * v1.0 mapping: legacy compound `build_set(playlist_id, name, template,
 * algorithm)` is decomposed into:
 *   1. Read playlist tracks via Supabase (Panel pattern — direct read).
 *   2. `sequence_optimize(track_ids, algorithm, template)` — pure compute,
 *      returns ordering + quality_score.
 *   3. `entity_create(entity="set", data={name, source_playlist_id,
 *      template_name})` — creates the set shell. Skipped if `setId` is
 *      passed (rebuild path reuses the existing set).
 *   4. `entity_create(entity="set_version", data={set_id, track_order,
 *      version_label, generator_run_meta})` — set_version_build handler
 *      persists ordering + computes pairwise transitions.
 *
 * Returns the result of the final `entity_create(set_version)` call so the
 * UI can display version_id + quality_score directly.
 */
export async function buildSet(
  playlistId: number,
  name: string,
  template?: string,
  algorithm: 'greedy' | 'ga' = 'ga'
): Promise<ToolCallResult> {
  // 1. Get playlist track ids (Panel reads Supabase directly per architecture).
  const supabase = await createClient()
  const { data: items, error: itemsErr } = await supabase
    .from('dj_playlist_items')
    .select('track_id, sort_index')
    .eq('playlist_id', playlistId)
    .order('sort_index', { ascending: true })

  if (itemsErr || !items || items.length < 2) {
    return errorResult(
      'build_set',
      itemsErr?.message ?? `playlist ${playlistId} has fewer than 2 tracks`
    )
  }
  const trackIds = items.map((it: { track_id: number }) => it.track_id)

  // 2. Optimize ordering.
  const optimize = await callTool('sequence_optimize', {
    track_ids: trackIds,
    algorithm,
    template: template ?? null,
  })
  if (optimize.is_error || !optimize.structured_content) {
    revalidateTag('sets', 'default')
    return optimize
  }
  const optSc = optimize.structured_content as {
    track_order?: number[]
    quality_score?: number
  }
  const trackOrder = optSc.track_order ?? trackIds

  // 3. Create the set.
  const created = await callTool('entity_create', {
    entity: 'set',
    data: {
      name,
      source_playlist_id: playlistId,
      template_name: template ?? null,
    },
  })
  if (created.is_error || !created.structured_content) {
    revalidateTag('sets', 'default')
    return created
  }
  const createdSc = created.structured_content as { data?: { id?: number } }
  const setId = createdSc.data?.id
  if (typeof setId !== 'number') {
    return errorResult('build_set', 'entity_create(set) returned no id')
  }

  // 4. Build the version (handler computes transitions).
  const version = await callTool('entity_create', {
    entity: 'set_version',
    data: {
      set_id: setId,
      track_order: trackOrder,
      version_label: 'auto',
      generator_run_meta: {
        algorithm,
        template: template ?? null,
        optimizer_quality: optSc.quality_score ?? null,
      },
    },
  })
  revalidateTag('sets', 'default')
  return version
}

/**
 * Rebuild a set: re-run optimization on the same source playlist with
 * pinned/excluded tracks honoured.
 *
 * v1.0 mapping: legacy `rebuild_set(set_id, pin, unpin, exclude, ...)` →
 *   1. `entity_get(entity="set", id)` to recover source_playlist_id +
 *      template_name.
 *   2. Read playlist tracks (Supabase direct).
 *   3. `sequence_optimize(... pinned, excluded)`.
 *   4. `entity_create(entity="set_version", ...)`.
 *
 * Note: `unpin` is not modelled — pin/exclude are the optimizer inputs.
 * Anything not in `pin` simply isn't pinned.
 */
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
  const algorithm = options.algorithm ?? 'ga'

  // 1. Read the set to get its source playlist + template.
  const setResp = await callTool('entity_get', { entity: 'set', id: setId })
  if (setResp.is_error || !setResp.structured_content) {
    return setResp
  }
  const setSc = setResp.structured_content as {
    data?: { source_playlist_id?: number | null; template_name?: string | null }
  }
  const sourcePlaylistId = setSc.data?.source_playlist_id
  const templateName = setSc.data?.template_name ?? null
  if (!sourcePlaylistId) {
    return errorResult('rebuild_set', `set ${setId} has no source_playlist_id`)
  }

  // 2. Get playlist track ids.
  const supabase = await createClient()
  const { data: items, error: itemsErr } = await supabase
    .from('dj_playlist_items')
    .select('track_id, sort_index')
    .eq('playlist_id', sourcePlaylistId)
    .order('sort_index', { ascending: true })
  if (itemsErr || !items || items.length < 2) {
    return errorResult(
      'rebuild_set',
      itemsErr?.message ?? `source playlist has fewer than 2 tracks`
    )
  }
  const trackIds = items.map((it: { track_id: number }) => it.track_id)

  // 3. Optimize.
  const optimize = await callTool('sequence_optimize', {
    track_ids: trackIds,
    algorithm,
    template: templateName,
    pinned: options.pin ?? null,
    excluded: options.exclude ?? null,
  })
  if (optimize.is_error || !optimize.structured_content) {
    revalidateTag('sets', 'default')
    return optimize
  }
  const optSc = optimize.structured_content as {
    track_order?: number[]
    quality_score?: number
  }
  const trackOrder = optSc.track_order ?? trackIds

  // 4. Create new version.
  const version = await callTool('entity_create', {
    entity: 'set_version',
    data: {
      set_id: setId,
      track_order: trackOrder,
      version_label: options.version_label ?? 'rebuild',
      generator_run_meta: {
        algorithm,
        template: templateName,
        optimizer_quality: optSc.quality_score ?? null,
        pinned: options.pin ?? [],
        excluded: options.exclude ?? [],
      },
    },
  })
  revalidateTag('sets', 'default')
  return version
}

/**
 * Score every consecutive transition in a set (latest version).
 *
 * v1.0 mapping: legacy `score_transitions(mode="set", set_id)` →
 *   1. Read set version + items via Supabase.
 *   2. `transition_score_pool(track_ids)` — returns N*(N-1) pair scores.
 *
 * Note: `transition_score_pool` returns ALL directed pairs, not only
 * consecutive ones. Consumers can filter where `pairs[i].a == track_order[k]
 * && pairs[i].b == track_order[k+1]`.
 *
 * TODO(v1.0-actions-rewrite): if a "consecutive only" output is needed,
 * filter to consecutive pairs here before returning, or expose a dedicated
 * helper that walks `track_order` and looks each pair up in `pairs`.
 */
export async function scoreTransitions(setId: number): Promise<ToolCallResult> {
  const supabase = await createClient()

  // Latest version + ordering.
  const { data: versions } = await supabase
    .from('dj_set_versions')
    .select('id')
    .eq('set_id', setId)
    .order('created_at', { ascending: false })
    .limit(1)
  const versionId = versions?.[0]?.id
  if (!versionId) {
    return errorResult('score_transitions', `set ${setId} has no versions`)
  }

  const { data: items } = await supabase
    .from('dj_set_items')
    .select('track_id, sort_index')
    .eq('version_id', versionId)
    .order('sort_index', { ascending: true })
  const trackIds = (items ?? []).map((it: { track_id: number }) => it.track_id)
  if (trackIds.length < 2) {
    return errorResult(
      'score_transitions',
      `version ${versionId} has fewer than 2 tracks`
    )
  }

  const result = await callTool('transition_score_pool', { track_ids: trackIds })
  revalidateTag('sets', 'default')
  return result
}

/**
 * Load the cheat sheet for a set.
 *
 * v1.0 mapping: legacy `get_set_cheat_sheet(set_id)` → `read_resource(
 * uri="local://sets/{id}/cheatsheet")`. The resource returns JSON with a
 * pre-formatted cheat sheet (the consumer pulls `structured_content.cheat_sheet`
 * or falls back to raw text content).
 */
export async function getCheatSheet(setId: number): Promise<ToolCallResult> {
  return callTool('read_resource', {
    uri: `local://sets/${setId}/cheatsheet`,
  })
}

/**
 * Deliver a set: copy MP3 files, write M3U8/JSON guide.
 *
 * v1.0 status: NOT YET WIRED. The legacy `deliver_set` was a high-level
 * compound that ran scoring → conflict gate (elicitation) → file copy →
 * optional YM sync. In v1.0 this is a workflow recipe (`deliver_set_workflow`
 * prompt) — but Panel is a tool client, not an LLM client, so it cannot
 * execute prompt recipes directly.
 *
 * Until a server-side composer exists (e.g. `delivery_pipeline` handler on
 * `entity_create(entity="delivery", ...)` or a dedicated tool), this returns
 * an explicit error so the UI surfaces a clear status.
 *
 * TODO(v1.0-actions-rewrite): build a delivery handler — likely as
 * `entity_create(entity="set_version", data={set_id, deliver: true})` with
 * an extended set_version_build_handler that invokes the delivery pipeline.
 */
export async function deliverSet(
  _setId: number,
  _options: { version?: number; copy_files?: boolean; sync_to_ym?: boolean; dry_run?: boolean } = {}
): Promise<ToolCallResult> {
  return errorResult(
    'deliver_set',
    'deliver_set is not yet wired in v1.0 — see panel/actions/set-actions.ts ' +
      'TODO(v1.0-actions-rewrite). Workflow needs a delivery handler.'
  )
}

/**
 * Export a set as JSON / M3U8 / Rekordbox XML.
 *
 * v1.0 status: NOT YET WIRED. There is no v1 `export_set` tool — the
 * legacy serializer code was removed. M3U8 / Rekordbox export should
 * become either a dedicated tool (`set_export(set_id, format)`) or be
 * folded into the delivery pipeline above. JSON export is partially
 * available via `read_resource(uri="local://sets/{id}/full")` (returns
 * the structured set view) — callers needing JSON can read that directly.
 *
 * TODO(v1.0-actions-rewrite): wire a real export tool, or migrate the
 * UI button to call `read_resource(local://sets/{id}/full)` and let the
 * client save the JSON.
 */
export async function exportSet(
  _setId: number,
  _format: 'json' | 'm3u8' | 'rekordbox' = 'json'
): Promise<ToolCallResult> {
  return errorResult(
    'export_set',
    'export_set is not yet wired in v1.0 — see panel/actions/set-actions.ts ' +
      'TODO(v1.0-actions-rewrite). For JSON, read local://sets/{id}/full.'
  )
}

function errorResult(toolName: string, message: string): ToolCallResult {
  return {
    tool_name: toolName,
    content: [{ type: 'text', text: message }],
    structured_content: null,
    is_error: true,
  }
}
