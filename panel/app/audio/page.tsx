import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { SiteHeader } from "@/components/site-header"
import { IconWaveSquare } from "@tabler/icons-react"

export default function AudioPage() {
  return (
    <>
      <SiteHeader title="Audio Analysis" />
      <div className="flex flex-1 flex-col items-center justify-center py-20">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconWaveSquare />
            </EmptyMedia>
            <EmptyTitle>Audio Analysis</EmptyTitle>
            <EmptyDescription>
              Run BPM detection, key analysis, loudness measurement, and full audio pipeline on tracks.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    </>
  )
}
