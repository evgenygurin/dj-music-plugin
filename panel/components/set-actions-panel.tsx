'use client'

import { useState } from 'react'
import {
  IconRefresh,
  IconPlayerPlay,
  IconDownload,
  IconFileExport,
  IconBuildingFactory,
} from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import {
  buildSet,
  rebuildSet,
  scoreTransitions,
  deliverSet,
  exportSet,
} from '@/actions/set-actions'

interface SetActionsPanelProps {
  setId: number
  sourcePlaylistId: number | null
  setName: string
  templateName: string | null
}

export function SetActionsPanel({
  setId,
  sourcePlaylistId,
  setName,
  templateName,
}: SetActionsPanelProps) {
  const [loading, setLoading] = useState<string | null>(null)

  async function run(key: string, fn: () => Promise<unknown>, label: string) {
    setLoading(key)
    try {
      const result = await fn()
      if (result && typeof result === 'object' && 'is_error' in result && result.is_error) {
        toast.error(`${label} failed`, { description: 'Check MCP server connection.' })
      } else {
        toast.success(label, { description: 'Operation completed.' })
      }
    } catch {
      toast.error(`${label} failed`, { description: 'Unexpected error.' })
    } finally {
      setLoading(null)
    }
  }

  const actions: Array<{
    key: string
    label: string
    icon: React.ReactNode
    disabled?: boolean
    fn: () => Promise<unknown>
    description: string
  }> = [
    {
      key: 'build',
      label: 'Build Set',
      icon: <IconBuildingFactory className="h-4 w-4" />,
      disabled: sourcePlaylistId === null,
      fn: () =>
        sourcePlaylistId !== null
          ? buildSet(sourcePlaylistId, setName, templateName ?? undefined)
          : Promise.resolve(null),
      description: 'Run genetic algorithm optimizer to build a new version.',
    },
    {
      key: 'rebuild',
      label: 'Rebuild',
      icon: <IconRefresh className="h-4 w-4" />,
      fn: () => rebuildSet(setId),
      description: 'Re-run optimization keeping pinned tracks in place.',
    },
    {
      key: 'score',
      label: 'Score Transitions',
      icon: <IconPlayerPlay className="h-4 w-4" />,
      fn: () => scoreTransitions(setId),
      description: 'Evaluate all consecutive track transitions.',
    },
    {
      key: 'deliver',
      label: 'Deliver Set',
      icon: <IconDownload className="h-4 w-4" />,
      fn: () => deliverSet(setId),
      description: 'Copy MP3s, generate M3U8, JSON guide, and cheat sheet.',
    },
    {
      key: 'export',
      label: 'Export JSON',
      icon: <IconFileExport className="h-4 w-4" />,
      fn: () => exportSet(setId, 'json'),
      description: 'Export full set guide as JSON file.',
    },
  ]

  return (
    <div className="flex flex-col gap-3">
      {actions.map((action) => (
        <div key={action.key} className="flex items-center justify-between gap-4 py-2 border-b last:border-0">
          <div>
            <div className="text-sm font-medium">{action.label}</div>
            <div className="text-xs text-muted-foreground">{action.description}</div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => run(action.key, action.fn, action.label)}
            disabled={loading !== null || action.disabled}
            className="gap-1.5 flex-shrink-0"
          >
            {loading === action.key ? (
              <IconRefresh className="h-4 w-4 animate-spin" />
            ) : (
              action.icon
            )}
            {loading === action.key ? 'Running…' : action.label}
          </Button>
        </div>
      ))}
    </div>
  )
}
