import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { SiteHeader } from "@/components/site-header"
import { IconSettings } from "@tabler/icons-react"

export default function AdminPage() {
  return (
    <>
      <SiteHeader title="Admin" />
      <div className="flex flex-1 flex-col items-center justify-center py-20">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconSettings />
            </EmptyMedia>
            <EmptyTitle>Admin</EmptyTitle>
            <EmptyDescription>
              Manage visibility of MCP tool categories, platform connections, and system settings.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    </>
  )
}
