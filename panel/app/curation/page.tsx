import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { SiteHeader } from "@/components/site-header"
import { IconTags } from "@tabler/icons-react"

export default function CurationPage() {
  return (
    <>
      <SiteHeader title="Curation" />
      <div className="flex flex-1 flex-col items-center justify-center py-20">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconTags />
            </EmptyMedia>
            <EmptyTitle>Curation</EmptyTitle>
            <EmptyDescription>
              Classify tracks by subgenre, distribute to playlists, and sync with Yandex Music.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    </>
  )
}
