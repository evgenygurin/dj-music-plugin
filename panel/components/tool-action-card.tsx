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
import { Spinner } from '@/components/ui/spinner'
import type { ToolCallResult } from '@/lib/mcp-client'

interface ToolActionCardProps {
  title: string
  description: string
  toolName: string
  schema: JsonSchema
  buttonLabel?: string
}

export function ToolActionCard({
  title,
  description,
  toolName,
  schema,
  buttonLabel,
}: ToolActionCardProps) {
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
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger
            render={
              <Button variant="outline" size="sm">
                {loading ? (
                  <Spinner className="mr-2 h-4 w-4" />
                ) : null}
                {buttonLabel || `Run ${toolName}`}
              </Button>
            }
          />
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-mono text-sm">{toolName}</DialogTitle>
            </DialogHeader>
            <ToolForm
              schema={schema}
              onSubmit={handleSubmit}
              loading={loading}
            />
          </DialogContent>
        </Dialog>
        {result && <ToolResult result={result} />}
      </CardContent>
    </Card>
  )
}
