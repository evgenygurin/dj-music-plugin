'use client'

import { useState, useTransition } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
  InputGroupText,
} from '@/components/ui/input-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Search } from 'lucide-react'
import { importTracks, searchPlatform } from '@/actions/discovery-actions'

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
        const result = await searchPlatform(query.trim(), searchType)
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
    <Card className="shadow-none border-border/20 bg-card/50">
      <CardHeader>
        <CardTitle className="display-heading text-lg">Search Platform</CardTitle>
        <CardDescription>Search for tracks, albums, artists, and playlists on the active platform.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_140px_auto]">
          <InputGroup className="h-10 rounded-xl border-border/30 bg-muted/20">
            <InputGroupAddon>
              <InputGroupText>
                <Search />
              </InputGroupText>
            </InputGroupAddon>
            <InputGroupInput
              placeholder="Search platform catalog..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </InputGroup>

          <Select value={searchType} onValueChange={(v) => v !== null && setSearchType(v)}>
            <SelectTrigger className="h-10 w-full rounded-xl border-border/30 bg-muted/20 text-sm sm:w-[140px]">
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
          <Button onClick={handleSearch} disabled={isSearching || !query.trim()} className="h-10 w-full sm:w-auto">
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
                  className="flex flex-col gap-2 rounded-xl border border-border/20 bg-muted/10 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1 sm:mr-4">
                    <div className="font-medium text-sm text-foreground truncate">{track.title}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {[artistNames, albumTitle].filter(Boolean).join(' · ')}
                      {track.durationMs ? (
                        <span className="ml-2 font-mono">{formatMs(track.durationMs)}</span>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:flex-shrink-0 sm:justify-end">
                    <Badge variant="outline" className="text-xs font-mono">{id}</Badge>
                    {isImported ? (
                      <Badge variant="secondary" className="text-xs">Imported</Badge>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleImport(track)}
                        disabled={isImporting}
                        className="min-w-24"
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
