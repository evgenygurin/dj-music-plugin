'use client'

import { useState } from 'react'
import { IconRefresh, IconCloudUpload } from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { auditPlaylist, syncPlaylist } from '@/actions/playlist-actions'

interface PlaylistActionsBarProps {
  playlistId: number
}

export function PlaylistActionsBar({ playlistId }: PlaylistActionsBarProps) {
  const [auditLoading, setAuditLoading] = useState(false)
  const [syncLoading, setSyncLoading] = useState(false)

  async function handleAudit() {
    setAuditLoading(true)
    try {
      const result = await auditPlaylist(playlistId)
      if (result && typeof result === 'object' && 'is_error' in result && result.is_error) {
        toast.error('Audit failed', { description: 'Check MCP server connection.' })
      } else {
        toast.success('Audit complete', { description: 'Playlist audit finished.' })
      }
    } catch {
      toast.error('Audit failed', { description: 'Unexpected error.' })
    } finally {
      setAuditLoading(false)
    }
  }

  async function handleSync() {
    setSyncLoading(true)
    try {
      const result = await syncPlaylist(playlistId)
      if (result && typeof result === 'object' && 'is_error' in result && result.is_error) {
        toast.error('Sync failed', { description: 'Check MCP server connection.' })
      } else {
        toast.success('Synced', { description: 'Playlist pulled from Yandex Music.' })
      }
    } catch {
      toast.error('Sync failed', { description: 'Unexpected error.' })
    } finally {
      setSyncLoading(false)
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={handleAudit}
        disabled={auditLoading}
        className="gap-1.5"
      >
        <IconRefresh className={`h-4 w-4 ${auditLoading ? 'animate-spin' : ''}`} />
        {auditLoading ? 'Auditing…' : 'Audit Playlist'}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={handleSync}
        disabled={syncLoading}
        className="gap-1.5"
      >
        <IconCloudUpload className={`h-4 w-4 ${syncLoading ? 'animate-bounce' : ''}`} />
        {syncLoading ? 'Syncing…' : 'Sync to YM'}
      </Button>
    </div>
  )
}
