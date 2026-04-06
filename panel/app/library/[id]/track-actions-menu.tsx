'use client'

import { useState } from 'react'
import { toast } from 'sonner'
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

interface TrackActionsMenuProps {
  trackId: number
}

export function TrackActionsMenu({ trackId }: TrackActionsMenuProps) {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  const handleAnalyze = async () => {
    setLoading(true)
    const toastId = toast.loading('Analyzing track...')
    try {
      await analyzeTrack(trackId)
      toast.success('Analysis complete', { id: toastId })
      router.refresh()
    } catch (err) {
      toast.error(`Analysis failed: ${err instanceof Error ? err.message : 'Unknown error'}`, { id: toastId })
    } finally {
      setLoading(false)
    }
  }

  const handleClassify = async () => {
    setLoading(true)
    const toastId = toast.loading('Classifying mood...')
    try {
      await classifyTrackMood(trackId)
      toast.success('Mood classified', { id: toastId })
      router.refresh()
    } catch (err) {
      toast.error(`Classification failed: ${err instanceof Error ? err.message : 'Unknown error'}`, { id: toastId })
    } finally {
      setLoading(false)
    }
  }

  const handleArchive = async () => {
    setLoading(true)
    const toastId = toast.loading('Archiving track...')
    try {
      await archiveTrack(trackId)
      toast.success('Track archived', { id: toastId })
      router.push('/library')
    } catch (err) {
      toast.error(`Archive failed: ${err instanceof Error ? err.message : 'Unknown error'}`, { id: toastId })
    } finally {
      setLoading(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={buttonVariants({ variant: 'outline', size: 'sm' })}
        disabled={loading}
      >
        Actions
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={handleAnalyze}>
          Analyze Track
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleClassify}>
          Classify Mood
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={handleArchive}>
          Archive
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
