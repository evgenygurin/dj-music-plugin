'use client'

import { useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ToolForm } from '@/components/tool-form'
import type { JsonSchema } from '@/components/tool-form'
import { ToolResult } from '@/components/tool-result'
import { executeToolAction } from '@/actions/tool-actions'
import { toast } from 'sonner'
import type { ToolCallResult } from '@/lib/mcp-client'

interface ActionButtonProps {
  toolName: string
  label: string
  schema: JsonSchema
}

function ActionButton({ toolName, label, schema }: ActionButtonProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ToolCallResult | null>(null)

  const handleSubmit = async (args: Record<string, unknown>) => {
    setLoading(true)
    try {
      const res = await executeToolAction(toolName, args)
      setResult(res)
      if (res.is_error) {
        toast.error(`${toolName} failed`)
      } else {
        toast.success(`${toolName} completed`)
        setOpen(false)
      }
    } catch {
      toast.error(`Failed to call ${toolName}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm">{label}</Button>} />
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">{toolName}</DialogTitle>
        </DialogHeader>
        <ToolForm
          schema={schema}
          onSubmit={handleSubmit}
          loading={loading}
        />
        {result && <ToolResult result={result} />}
      </DialogContent>
    </Dialog>
  )
}

interface DiscoverActionsProps {
  importSchema: JsonSchema
  downloadSchema: JsonSchema
  similarSchema: JsonSchema
  expandSchema: JsonSchema
}

export function DiscoverActions({
  importSchema,
  downloadSchema,
  similarSchema,
  expandSchema,
}: DiscoverActionsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
        <CardDescription>
          Import tracks, download audio, find similar tracks, or expand a playlist.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          <ActionButton
            toolName="import_tracks"
            label="Import Tracks"
            schema={importSchema}
          />
          <ActionButton
            toolName="download_tracks"
            label="Download Tracks"
            schema={downloadSchema}
          />
          <ActionButton
            toolName="find_similar_tracks"
            label="Find Similar"
            schema={similarSchema}
          />
          <ActionButton
            toolName="expand_playlist_ym"
            label="Expand Playlist"
            schema={expandSchema}
          />
        </div>
      </CardContent>
    </Card>
  )
}
