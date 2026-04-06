'use client'

import { useState } from 'react'
import { ToolForm } from '@/components/tool-form'
import { ToolResult } from '@/components/tool-result'
import { executeToolAction } from '@/actions/tool-actions'
import type { ToolCallResult } from '@/lib/mcp-client'
import { toast } from 'sonner'

export function ToolRunner({
  toolName,
  schema,
}: {
  toolName: string
  schema: Record<string, unknown>
}) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ToolCallResult | null>(null)

  const handleSubmit = async (args: Record<string, unknown>) => {
    setLoading(true)
    setResult(null)
    try {
      const res = await executeToolAction(toolName, args)
      setResult(res)
      if (res.is_error) {
        toast.error(`${toolName} failed`)
      } else {
        toast.success(`${toolName} completed`)
      }
    } catch (e) {
      toast.error(`Failed to call ${toolName}`)
      setResult({
        tool_name: toolName,
        content: [{ type: 'text', text: String(e) }],
        structured_content: null,
        is_error: true,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid gap-6">
      <ToolForm
        schema={schema as Parameters<typeof ToolForm>[0]['schema']}
        onSubmit={handleSubmit}
        loading={loading}
      />
      {result && <ToolResult result={result} />}
    </div>
  )
}
