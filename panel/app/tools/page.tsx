import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { SiteHeader } from "@/components/site-header"
import { IconTerminal2 } from "@tabler/icons-react"

export default function ToolsPage() {
  return (
    <>
      <SiteHeader title="Tools" />
      <div className="flex flex-1 flex-col items-center justify-center py-20">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconTerminal2 />
            </EmptyMedia>
            <EmptyTitle>Tools</EmptyTitle>
            <EmptyDescription>
              Browse and invoke all 50 MCP tools. Unlock extended and hidden tool categories.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    </>
  )
}
