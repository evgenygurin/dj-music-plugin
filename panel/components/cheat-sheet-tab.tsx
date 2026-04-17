'use client'

import { useState } from 'react'
import { IconRefresh } from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import { getCheatSheet } from '@/actions/set-actions'
import { useToolAction } from '@/hooks/use-tool-action'

interface CheatSheetTabProps {
  setId: number
}

function extractCheatSheetText(
  structured: Record<string, unknown> | null,
  content: Array<{ type: string; text?: string }>
): string {
  if (structured && typeof structured.cheat_sheet === 'string') {
    return structured.cheat_sheet
  }
  return content
    .filter((c) => c.type === 'text' && c.text)
    .map((c) => c.text)
    .join('')
}

export function CheatSheetTab({ setId }: CheatSheetTabProps) {
  const [content, setContent] = useState<string | null>(null)

  const action = useToolAction({
    label: 'Cheat sheet',
    fn: () => getCheatSheet(setId),
    successMessage: 'Loaded.',
    onSuccess: (result) => {
      setContent(extractCheatSheetText(result.structured_content, result.content))
    },
  })

  if (!content) {
    return (
      <div className="flex flex-col items-center gap-4 py-8 text-center">
        <p className="text-sm text-muted-foreground">
          Load cheat sheet to see human-readable transition info.
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={action.run}
          disabled={action.loading}
          className="gap-1.5"
        >
          <IconRefresh className={`h-4 w-4 ${action.loading ? 'animate-spin' : ''}`} />
          {action.loading ? 'Loading…' : 'Load Cheat Sheet'}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={action.run}
          disabled={action.loading}
          className="gap-1.5"
        >
          <IconRefresh className={`h-3.5 w-3.5 ${action.loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>
      <pre className="overflow-auto rounded-md bg-muted p-4 text-xs font-mono leading-relaxed whitespace-pre-wrap break-words">
        {content}
      </pre>
    </div>
  )
}
