'use client'

import { useState, useTransition } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ymSearch, importTracks } from '@/actions/discovery-actions'

interface YmTrack {
  id: string | number
  title: string
  artists?: Array<{ name: string }>
  durationMs?: number
  albums?: Array<{ title?: string }>
}

function formatMs(ms: number): string {
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function extractTracks(structured: Record<string, unknown> | null): YmTrack[] {
  if (!structured) return []

  const result = structured.result as Record<string, unknown> | undefined
  if (result) {
    const tracks = result.tracks as { results?: YmTrack[] } | undefined
    if (tracks?.results) return tracks.results
    if (Array.isArray(result)) return result as YmTrack[]
  }

  if (Array.isArray(structured.tracks)) return structured.tracks as YmTrack[]

  return []
}

export function YmSearch() {
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState('tracks')
  const [results, setResults] = useState<YmTrack[]>([])
  const [error, setError] = useState<string | null>(null)
  const [importing, setImporting] = useState<Set<string>>(new Set())
  const [imported, setImported] = useState<Set<string>>(new Set())
  const [isSearching, startSearch] = useTransition()

  const handleSearch = () => {
    if (!query.trim()) return
    setError(null)
    startSearch(async () => {
      try {
        const result = await ymSearch(query.trim(), searchType)
        if (result.is_error) {
          setError(result.content[0]?.text ?? 'Search failed')
          setResults([])
          return
        }
        setResults(extractTracks(result.structured_content))
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Search failed')
        setResults([])
      }
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch()
  }

  const handleImport = async (track: YmTrack) => {
    const id = String(track.id)
    setImporting((prev) => new Set([...prev, id]))
    try {
      await importTracks([id])
      setImported((prev) => new Set([...prev, id]))
    } catch (e) {
      console.error('Import failed', e)
    } finally {
      setImporting((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Search Yandex Music</CardTitle>
        <CardDescription>Search for tracks, albums, artists, and playlists on Yandex Music.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search Yandex Music..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1"
          />
          <Select value={searchType} onValueChange={(v) => v !== null && setSearchType(v)}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="tracks">Tracks</SelectItem>
              <SelectItem value="albums">Albums</SelectItem>
              <SelectItem value="artists">Artists</SelectItem>
              <SelectItem value="playlists">Playlists</SelectItem>
              <SelectItem value="all">All</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleSearch} disabled={isSearching || !query.trim()}>
            {isSearching ? 'Searching...' : 'Search'}
          </Button>
        </div>

        {error && (
          <div className="text-sm text-destructive">{error}</div>
        )}

        {results.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">{results.length} results</p>
            {results.map((track) => {
              const id = String(track.id)
              const artistNames = track.artists?.map((a) => a.name).join(', ') ?? ''
              const albumTitle = track.albums?.[0]?.title ?? ''
              const isImporting = importing.has(id)
              const isImported = imported.has(id)

              return (
                <div
                  key={id}
                  className="flex items-center justify-between rounded-lg border px-3 py-2"
                >
                  <div className="flex-1 min-w-0 mr-4">
                    <div className="font-medium text-sm truncate">{track.title}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {[artistNames, albumTitle].filter(Boolean).join(' · ')}
                      {track.durationMs ? (
                        <span className="ml-2 font-mono">{formatMs(track.durationMs)}</span>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <Badge variant="outline" className="text-xs font-mono">{id}</Badge>
                    {isImported ? (
                      <Badge variant="secondary" className="text-xs">Imported</Badge>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleImport(track)}
                        disabled={isImporting}
                      >
                        {isImporting ? 'Importing...' : 'Import'}
                      </Button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {!isSearching && results.length === 0 && query && !error && (
          <p className="text-sm text-muted-foreground">No results found.</p>
        )}
      </CardContent>
    </Card>
  )
}
