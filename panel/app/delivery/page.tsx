import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { SiteHeader } from "@/components/site-header"
import { IconPackageExport } from "@tabler/icons-react"

export default function DeliveryPage() {
  return (
    <>
      <SiteHeader title="Delivery" />
      <div className="flex flex-1 flex-col items-center justify-center py-20">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconPackageExport />
            </EmptyMedia>
            <EmptyTitle>Delivery</EmptyTitle>
            <EmptyDescription>
              Export sets to MP3, M3U8, and Rekordbox XML. Push to Yandex Music playlists.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    </>
  )
}
