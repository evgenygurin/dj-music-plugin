'use client'

import { useState, useRef } from 'react'
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
import { Spinner } from '@/components/ui/spinner'
import { useToolAction } from '@/hooks/use-tool-action'

interface ToolDialogButtonProps {
  toolName: string
  schema: JsonSchema
  /** Trigger button label. Defaults to "Run {toolName}". */
  label?: string
  /** Trigger button variant. */
  variant?: React.ComponentProps<typeof Button>['variant']
  /** Trigger button size. */
  size?: React.ComponentProps<typeof Button>['size']
  /** Show ToolResult inline below the form (default: true). */
  showResult?: boolean
  /** Close dialog on success (default: true). */
  closeOnSuccess?: boolean
}

/**
 * Self-contained "Run a tool" button. Opens a Dialog containing the
 * auto-generated ToolForm, executes the tool through `executeToolAction`,
 * displays the result inline, and routes errors/successes through
 * `useToolAction` for unified toast handling.
 *
 * Use this anywhere you want to expose a single MCP tool as a button.
 */
export function ToolDialogButton({
  toolName,
  schema,
  label,
  variant = 'outline',
  size = 'sm',
  showResult = true,
  closeOnSuccess = true,
}: ToolDialogButtonProps) {
  const [open, setOpen] = useState(false)
  // Args ref so the run() closure always sees the latest values without
  // depending on a render cycle.
  const argsRef = useRef<Record<string, unknown>>({})

  const action = useToolAction({
    label: toolName,
    fn: () => executeToolAction(toolName, argsRef.current),
    onSuccess: () => {
      if (closeOnSuccess) setOpen(false)
    },
  })

  const handleSubmit = async (args: Record<string, unknown>) => {
    argsRef.current = args
    await action.run()
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant={variant} size={size}>
            {action.loading ? <Spinner className="mr-2 h-4 w-4" /> : null}
            {label || `Run ${toolName}`}
          </Button>
        }
      />
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">{toolName}</DialogTitle>
        </DialogHeader>
        <ToolForm schema={schema} onSubmit={handleSubmit} loading={action.loading} />
        {showResult && action.result && <ToolResult result={action.result} />}
      </DialogContent>
    </Dialog>
  )
}
