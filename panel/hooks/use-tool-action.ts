'use client'

import { useState, useCallback } from 'react'
import { toast } from 'sonner'
import { useRouter } from 'next/navigation'
import type { ToolCallResult } from '@/lib/mcp-client'

interface ToolLike {
  is_error: boolean
}

interface UseToolActionOptions<T extends ToolLike> {
  /** Label shown in toasts (defaults to tool name). */
  label: string
  /** The async server action / call that runs the tool. */
  fn: () => Promise<T>
  /** Override the success message body. */
  successMessage?: string
  /** Override the error message body. Receives the failed result if available. */
  errorMessage?: string
  /** If true, calls `router.refresh()` on success. */
  refresh?: boolean
  /** Optional callback after a successful run, receives the tool result. */
  onSuccess?: (result: T) => void
  /** Optional callback after an error, receives the tool result if any. */
  onError?: (result: T | null, error: unknown) => void
}

export interface ToolActionState<T extends ToolLike> {
  loading: boolean
  result: T | null
  /** Run the action. Resolves to the result, or null if it threw. */
  run: () => Promise<T | null>
  /** Reset state to initial. */
  reset: () => void
}

/**
 * Standard hook for invoking an MCP tool from a client component.
 *
 * Encapsulates the loading flag, error/success toasts, optional router refresh
 * and result storage. Use this in every action button / dropdown / dialog so
 * panel-wide UX stays consistent.
 *
 * Generic over T so you can use it both with `ToolCallResult` and with custom
 * server-action return types that include `is_error`.
 */
export function useToolAction<T extends ToolLike = ToolCallResult>(
  options: UseToolActionOptions<T>
): ToolActionState<T> {
  const { label, fn, successMessage, errorMessage, refresh, onSuccess, onError } = options
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<T | null>(null)

  const run = useCallback(async (): Promise<T | null> => {
    setLoading(true)
    const toastId = toast.loading(`${label}…`)
    try {
      const res = await fn()
      setResult(res)
      if (res.is_error) {
        toast.error(`${label} failed`, {
          id: toastId,
          description: errorMessage ?? 'Check MCP server connection.',
        })
        onError?.(res, null)
        return res
      }
      toast.success(label, {
        id: toastId,
        description: successMessage,
      })
      if (refresh) router.refresh()
      onSuccess?.(res)
      return res
    } catch (err) {
      toast.error(`${label} failed`, {
        id: toastId,
        description: err instanceof Error ? err.message : 'Unexpected error.',
      })
      onError?.(null, err)
      return null
    } finally {
      setLoading(false)
    }
  }, [fn, label, successMessage, errorMessage, refresh, onSuccess, onError, router])

  const reset = useCallback(() => setResult(null), [])

  return { loading, result, run, reset }
}
