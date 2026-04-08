'use client'

import {
  IconRefresh,
  IconPlayerPlay,
  IconDownload,
  IconFileExport,
  IconBuildingFactory,
} from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import {
  buildSet,
  rebuildSet,
  scoreTransitions,
  deliverSet,
  exportSet,
} from '@/actions/set-actions'
import { useToolAction } from '@/hooks/use-tool-action'
import type { ToolCallResult } from '@/lib/mcp-client'

interface SetActionsPanelProps {
  setId: number
  sourcePlaylistId: number | null
  setName: string
  templateName: string | null
}

interface SetAction {
  key: string
  label: string
  icon: React.ReactNode
  description: string
  disabled?: boolean
  hook: ReturnType<typeof useToolAction<ToolCallResult>>
}

export function SetActionsPanel({
  setId,
  sourcePlaylistId,
  setName,
  templateName,
}: SetActionsPanelProps) {
  const build = useToolAction({
    label: 'Build Set',
    fn: () =>
      sourcePlaylistId !== null
        ? buildSet(sourcePlaylistId, setName, templateName ?? undefined)
        : Promise.reject(new Error('No source playlist linked to this set.')),
    successMessage: 'New version generated.',
    refresh: true,
  })

  const rebuild = useToolAction({
    label: 'Rebuild',
    fn: () => rebuildSet(setId),
    successMessage: 'Set rebuilt.',
    refresh: true,
  })

  const score = useToolAction({
    label: 'Score Transitions',
    fn: () => scoreTransitions(setId),
    successMessage: 'Transitions scored.',
    refresh: true,
  })

  const deliver = useToolAction({
    label: 'Deliver Set',
    fn: () => deliverSet(setId),
    successMessage: 'Files written.',
  })

  const exportJson = useToolAction({
    label: 'Export JSON',
    fn: () => exportSet(setId, 'json'),
    successMessage: 'JSON exported.',
  })

  const actions: SetAction[] = [
    {
      key: 'build',
      label: 'Build Set',
      icon: <IconBuildingFactory className="h-4 w-4" />,
      description: 'Run genetic algorithm optimizer to build a new version.',
      disabled: sourcePlaylistId === null,
      hook: build,
    },
    {
      key: 'rebuild',
      label: 'Rebuild',
      icon: <IconRefresh className="h-4 w-4" />,
      description: 'Re-run optimization keeping pinned tracks in place.',
      hook: rebuild,
    },
    {
      key: 'score',
      label: 'Score Transitions',
      icon: <IconPlayerPlay className="h-4 w-4" />,
      description: 'Evaluate all consecutive track transitions.',
      hook: score,
    },
    {
      key: 'deliver',
      label: 'Deliver Set',
      icon: <IconDownload className="h-4 w-4" />,
      description: 'Copy MP3s, generate M3U8, JSON guide, and cheat sheet.',
      hook: deliver,
    },
    {
      key: 'export',
      label: 'Export JSON',
      icon: <IconFileExport className="h-4 w-4" />,
      description: 'Export full set guide as JSON file.',
      hook: exportJson,
    },
  ]

  const anyLoading = actions.some((a) => a.hook.loading)

  return (
    <div className="flex flex-col gap-3">
      {actions.map((action) => (
        <div
          key={action.key}
          className="flex items-center justify-between gap-4 py-2 border-b last:border-0"
        >
          <div>
            <div className="text-sm font-medium">{action.label}</div>
            <div className="text-xs text-muted-foreground">{action.description}</div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={action.hook.run}
            disabled={anyLoading || action.disabled}
            className="gap-1.5 flex-shrink-0"
          >
            {action.hook.loading ? (
              <IconRefresh className="h-4 w-4 animate-spin" />
            ) : (
              action.icon
            )}
            {action.hook.loading ? 'Running…' : action.label}
          </Button>
        </div>
      ))}
    </div>
  )
}
