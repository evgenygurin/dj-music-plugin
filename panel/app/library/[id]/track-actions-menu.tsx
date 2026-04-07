'use client'

import { useRouter } from 'next/navigation'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { buttonVariants } from '@/components/ui/button'
import { analyzeTrack, classifyTrackMood, archiveTrack } from '@/actions/track-actions'
import { useToolAction } from '@/hooks/use-tool-action'

interface TrackActionsMenuProps {
  trackId: number
}

export function TrackActionsMenu({ trackId }: TrackActionsMenuProps) {
  const router = useRouter()

  const analyze = useToolAction({
    label: 'Analyzing track',
    fn: () => analyzeTrack(trackId),
    successMessage: 'Analysis complete.',
    refresh: true,
  })

  const classify = useToolAction({
    label: 'Classifying mood',
    fn: () => classifyTrackMood(trackId),
    successMessage: 'Mood classified.',
    refresh: true,
  })

  const archive = useToolAction({
    label: 'Archiving track',
    fn: () => archiveTrack(trackId),
    successMessage: 'Track archived.',
    onSuccess: () => router.push('/library'),
  })

  const loading = analyze.loading || classify.loading || archive.loading

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={buttonVariants({ variant: 'outline', size: 'sm' })}
        disabled={loading}
      >
        Actions
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={analyze.run}>Analyze Track</DropdownMenuItem>
        <DropdownMenuItem onClick={classify.run}>Classify Mood</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={archive.run}>
          Archive
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
