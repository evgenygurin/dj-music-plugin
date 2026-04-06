'use client'

import { useState } from 'react'
import { IconRefresh } from '@tabler/icons-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { getCheatSheet } from '@/actions/set-actions'

interface CheatSheetTabProps {
  setId: number
}

export function CheatSheetTab({ setId }: CheatSheetTabProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const result = await getCheatSheet(setId)
      if (result && typeof result === 'object' && 'is_error' in result && result.is_error) {
        toast.error('Failed to load cheat sheet')
        return
      }
      // Extract text from result
      let text = ''
      if (typeof result === 'string') {
        text = result
      } else if (result && typeof result === 'object') {
        const r = result as Record<string, unknown>
        if ('cheat_sheet' in r) {
          text = String(r.cheat_sheet)
        } else if ('content' in r) {
          const c = r.content
          if (Array.isArray(c)) {
            text = c.map((item) => (item as { text?: string }).text ?? '').join('')
          } else {
            text = String(c)
          }
        } else {
          text = JSON.stringify(result, null, 2)
        }
      }
      setContent(text)
    } catch {
      toast.error('Failed to load cheat sheet')
    } finally {
      setLoading(false)
    }
  }

  if (!content) {
    return (
      <div className="flex flex-col items-center gap-4 py-8 text-center">
        <p className="text-sm text-muted-foreground">
          Load cheat sheet to see human-readable transition info.
        </p>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} className="gap-1.5">
          <IconRefresh className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Loading…' : 'Load Cheat Sheet'}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" onClick={load} disabled={loading} className="gap-1.5">
          <IconRefresh className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>
      <pre className="overflow-auto rounded-md bg-muted p-4 text-xs font-mono leading-relaxed whitespace-pre-wrap break-words">
        {content}
      </pre>
    </div>
  )
}
