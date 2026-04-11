import { SiteHeader } from '@/components/site-header'
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

interface PageShellProps {
  title: string
  parent?: { label: string; href: string }
  children: ReactNode
  /** Optional additional classes for the inner content container. */
  className?: string
}

/**
 * Canonical page wrapper. Provides:
 *  - SiteHeader with optional breadcrumb
 *  - @container/main for container queries
 *  - Standard padding/gap that matches the design system
 *
 * Use this on every page instead of hand-rolled `<div>` wrappers.
 */
export function PageShell({ title, parent, children, className }: PageShellProps) {
  return (
    <>
      <SiteHeader title={title} parent={parent} />
      <div className="flex flex-1 flex-col">
        <main id="main-content" className="@container/main flex flex-1 flex-col gap-2 pb-2">
          <h1 className="sr-only">{title}</h1>
          <div
            className={cn(
              'mx-auto flex w-full max-w-[1300px] flex-col gap-3 px-3 py-3 sm:px-4 sm:py-4 md:gap-6 md:py-6 lg:px-6',
              className
            )}
          >
            {children}
          </div>
        </main>
      </div>
    </>
  )
}

interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  badge?: ReactNode
  /** Optional class for the H1 element (e.g. `font-mono` for tool names). */
  titleClassName?: string
}

/**
 * In-page hero / heading row. Use inside <PageShell> for pages that want a
 * visible H1 with description and optional right-aligned actions.
 *
 * The SiteHeader already shows the page title in the breadcrumb, so this is
 * the *content* heading, not the navigation header.
 */
export function PageHeader({
  title,
  description,
  actions,
  badge,
  titleClassName,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className={cn('display-heading text-2xl tracking-tight text-balance', titleClassName)}>
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground/60 md:text-[10px] md:uppercase md:tracking-wider md:text-muted-foreground/50">{description}</p>
        )}
      </div>
      {actions && <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:flex-shrink-0 sm:justify-end">{actions}</div>}
    </div>
  )
}
