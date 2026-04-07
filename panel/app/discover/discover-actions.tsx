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
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
        <CardDescription>
          Import tracks, download audio, find similar tracks, or expand a playlist.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          <ToolDialogButton toolName="import_tracks" schema={importSchema} label="Import Tracks" />
          <ToolDialogButton toolName="download_tracks" schema={downloadSchema} label="Download Tracks" />
          <ToolDialogButton toolName="find_similar_tracks" schema={similarSchema} label="Find Similar" />
          <ToolDialogButton toolName="expand_playlist_ym" schema={expandSchema} label="Expand Playlist" />
        </div>
      </CardContent>
    </Card>
  )
}
