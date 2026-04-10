import { NextResponse } from 'next/server'

import { createClient } from '@/lib/supabase/server'

export const dynamic = 'force-dynamic'

const RAW = process.env.MCP_HTTP_URL ?? 'http://localhost:8001'
const REST_BASE = RAW.replace(/\/+mcp\/?$/, '').replace(/\/+$/, '')

// Total timeout for the entire request (connect + stream body).
// Backend read timeout is 15s per chunk; this covers the full transfer.
const TOTAL_TIMEOUT_MS = 45_000

export async function GET(
  request: Request,
  { params }: { params: Promise<{ trackId: string }> },
) {
  const { trackId } = await params
  const id = Number.parseInt(trackId, 10)
  if (!Number.isFinite(id)) {
    return NextResponse.json({ error: 'invalid track id' }, { status: 400 })
  }

  const supabase = await createClient()
  const { data, error } = await supabase
    .from('yandex_metadata')
    .select('yandex_track_id')
    .eq('track_id', id)
    .limit(1)
    .maybeSingle()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  if (!data?.yandex_track_id) {
    return NextResponse.json(
      { error: 'no yandex track id for this track' },
      { status: 404 },
    )
  }

  const range = request.headers.get('range')
  const upstreamHeaders: Record<string, string> = {}
  if (range) upstreamHeaders.range = range

  // Single AbortController governs connect + entire body stream.
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), TOTAL_TIMEOUT_MS)

  let upstream: Response
  try {
    upstream = await fetch(
      `${REST_BASE}/api/audio/stream/${data.yandex_track_id}`,
      {
        cache: 'no-store',
        headers: upstreamHeaders,
        signal: ac.signal,
      },
    )
  } catch (err) {
    clearTimeout(timer)
    const msg = err instanceof Error ? err.message : String(err)
    return NextResponse.json(
      { error: 'upstream timeout or connection failed', detail: msg },
      { status: 504 },
    )
  }

  if (!upstream.ok && upstream.status !== 206) {
    clearTimeout(timer)
    const text = await upstream.text().catch(() => '')
    return NextResponse.json(
      { error: 'upstream failed', status: upstream.status, body: text },
      { status: upstream.status || 502 },
    )
  }

  const headers = new Headers()
  headers.set('Cache-Control', 'no-store')
  for (const key of ['content-type', 'content-length', 'content-range', 'accept-ranges']) {
    const v = upstream.headers.get(key)
    if (v) headers.set(key, v)
  }
  if (!headers.has('content-type')) headers.set('content-type', 'audio/mpeg')
  if (!headers.has('accept-ranges')) headers.set('accept-ranges', 'bytes')

  // Wrap body in a stream that clears the timeout on completion.
  const body = upstream.body
    ? upstream.body.pipeThrough(
        new TransformStream({
          flush() {
            clearTimeout(timer)
          },
        }),
      )
    : null

  return new NextResponse(body, {
    status: upstream.status,
    headers,
  })
}
