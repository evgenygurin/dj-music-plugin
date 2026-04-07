'use client'

import { useRef } from 'react'
import { ToolForm } from '@/components/tool-form'
import { ToolResult } from '@/components/tool-result'
import { executeToolAction } from '@/actions/tool-actions'
import { useToolAction } from '@/hooks/use-tool-action'

export function ToolRunner({
  toolName,
  schema,
}: {
  toolName: string
  schema: Record<string, unknown>
}) {
  const argsRef = useRef<Record<string, unknown>>({})

  const action = useToolAction({
    label: toolName,
    fn: () => executeToolAction(toolName, argsRef.current),
  })

  const handleSubmit = async (args: Record<string, unknown>) => {
    argsRef.current = args
    await action.run()
  }

  return (
    <div className="grid gap-6">
      <ToolForm
        schema={schema as Parameters<typeof ToolForm>[0]['schema']}
        onSubmit={handleSubmit}
        loading={action.loading}
      />
      {action.result && <ToolResult result={action.result} />}
    </div>
  )
}
