'use client'

import { IconRefresh, IconCloudUpload } from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import { auditPlaylist, syncPlaylist } from '@/actions/playlist-actions'
import { useToolAction } from '@/hooks/use-tool-action'

interface PlaylistActionsBarProps {
  playlistId: number
}

export function PlaylistActionsBar({ playlistId }: PlaylistActionsBarProps) {
  const audit = useToolAction({
    label: 'Audit',
    fn: () => auditPlaylist(playlistId),
    successMessage: 'Playlist audit finished.',
  })

  const sync = useToolAction({
    label: 'Sync',
    fn: () => syncPlaylist(playlistId),
    successMessage: 'Playlist pulled from Yandex Music.',
    refresh: true,
  })

  return (
    <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap">
      <Button
        variant="outline"
        size="sm"
        onClick={audit.run}
        disabled={audit.loading}
        className="w-full gap-1.5 sm:w-auto"
      >
        <IconRefresh className={`h-4 w-4 ${audit.loading ? 'animate-spin' : ''}`} />
        {audit.loading ? 'Auditing…' : 'Audit Playlist'}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={sync.run}
        disabled={sync.loading}
        className="w-full gap-1.5 sm:w-auto"
      >
        <IconCloudUpload className={`h-4 w-4 ${sync.loading ? 'animate-bounce' : ''}`} />
        {sync.loading ? 'Syncing…' : 'Sync to YM'}
      </Button>
    </div>
  )
}
