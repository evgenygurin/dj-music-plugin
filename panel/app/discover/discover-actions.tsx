import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { JsonSchema } from '@/components/tool-form'
import { ToolDialogButton } from '@/components/tool-dialog-button'

interface DiscoverActionsProps {
  importSchema: JsonSchema
  downloadSchema: JsonSchema
  similarSchema: JsonSchema
  expandSchema: JsonSchema
}

export function DiscoverActions({
  importSchema,
  downloadSchema,
  similarSchema,
  expandSchema,
}: DiscoverActionsProps) {
  return (
    <Card className="shadow-none border-border/20 bg-card/50">
      <CardHeader>
        <CardTitle className="display-heading text-lg">Quick Actions</CardTitle>
        <CardDescription>
          Import tracks, download audio, find similar tracks, or expand a playlist.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2 sm:grid-cols-2 [&_button]:w-full">
          <ToolDialogButton toolName="import_tracks" schema={importSchema} label="Import Tracks" />
          <ToolDialogButton toolName="download_tracks" schema={downloadSchema} label="Download Tracks" />
          <ToolDialogButton toolName="find_similar_tracks" schema={similarSchema} label="Find Similar" />
          <ToolDialogButton toolName="expand_platform_playlist" schema={expandSchema} label="Expand Playlist" />
        </div>
      </CardContent>
    </Card>
  )
}
