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
    <Card className="shadow-none border-border/20 bg-card/50">
      <CardHeader>
        <CardTitle className="display-heading text-lg">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="[&_button]:w-full sm:[&_button]:w-auto">
        <ToolDialogButton
          toolName={toolName}
          schema={schema}
          label={buttonLabel}
        />
      </CardContent>
    </Card>
  )
}
