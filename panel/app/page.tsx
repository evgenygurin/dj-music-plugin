import { SiteHeader } from '@/components/site-header'

export default function DashboardPage() {
  return (
    <>
      <SiteHeader title="Dashboard" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <p className="text-muted-foreground">Dashboard coming soon...</p>
      </div>
    </>
  )
}
