'use client'

import { Button } from '@/components/ui/button'

interface PageErrorProps {
  error: Error & { digest?: string }
  reset: () => void
}

/**
 * Standard error boundary content. Used by every `error.tsx` so that
 * presentation stays consistent across the panel.
 */
export function PageError({ error, reset }: PageErrorProps) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
      <h2 className="display-heading text-lg">Something went wrong</h2>
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground/50">{error.message}</p>
      <Button onClick={reset} variant="outline">
        Try again
      </Button>
    </div>
  )
}
