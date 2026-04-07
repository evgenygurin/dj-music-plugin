import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { JsonSchema } from '@/components/tool-form'
import { ToolDialogButton } from '@/components/tool-dialog-button'

interface ToolActionCardProps {
  title: string
  description: string
  toolName: string
  schema: JsonSchema
  buttonLabel?: string
}

/**
 * Card-wrapped MCP tool runner. Used on Audio / Curation / Delivery pages
 * to surface a single tool with title, description and a single CTA.
 */
export function ToolActionCard({
  title,
  description,
  toolName,
  schema,
  buttonLabel,
}: ToolActionCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <ToolDialogButton
          toolName={toolName}
          schema={schema}
          label={buttonLabel}
        />
      </CardContent>
    </Card>
  )
}
