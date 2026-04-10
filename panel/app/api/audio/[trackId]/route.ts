import { NextResponse } from 'next/server'

import { createClient } from '@/lib/supabase/server'

export const dynamic = 'force-dynamic'

// MCP_HTTP_URL points at the native MCP transport (often `.../mcp`); strip
// the trailing /mcp segment so we hit the FastAPI REST root.
const RAW = process.env.MCP_HTTP_URL ?? 'http://localhost:8000'
const REST_BASE = RAW.replace(/\/+mcp\/?$/, '').replace(/\/+$/, '')

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

  // Forward Range so the browser can request partial bytes for seek/duration.
  const range = request.headers.get('range')
  const upstreamHeaders: Record<string, string> = {}
  if (range) upstreamHeaders.range = range

  let upstream: Response
  try {
    upstream = await fetch(
      `${REST_BASE}/api/audio/stream/${data.yandex_track_id}`,
      {
        cache: 'no-store',
        headers: upstreamHeaders,
        signal: AbortSignal.timeout(15_000),
      },
    )
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    return NextResponse.json(
      { error: 'upstream timeout or connection failed', detail: msg },
      { status: 504 },
    )
  }

  if (!upstream.ok && upstream.status !== 206) {
    const text = await upstream.text().catch(() => '')
    return NextResponse.json(
      { error: 'upstream failed', status: upstream.status, body: text },
      { status: upstream.status || 502 },
    )
  }

  // Forward media headers so <audio> can determine duration and seek.
  const headers = new Headers()
  headers.set('Cache-Control', 'no-store')
  for (const key of ['content-type', 'content-length', 'content-range', 'accept-ranges']) {
    const v = upstream.headers.get(key)
    if (v) headers.set(key, v)
  }
  if (!headers.has('content-type')) headers.set('content-type', 'audio/mpeg')
  if (!headers.has('accept-ranges')) headers.set('accept-ranges', 'bytes')

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers,
  })
}
