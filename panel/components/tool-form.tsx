'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { IconChevronDown } from '@tabler/icons-react'

export interface JsonSchema {
  type?: string
  properties?: Record<string, JsonSchemaProperty>
  required?: string[]
  [key: string]: unknown
}

export interface JsonSchemaProperty {
  type?: string | string[]
  anyOf?: Array<{ type: string; [key: string]: unknown }>
  default?: unknown
  description?: string
  enum?: string[]
  title?: string
  [key: string]: unknown
}

function getEffectiveType(prop: JsonSchemaProperty): string {
  if (prop.type) return Array.isArray(prop.type) ? prop.type[0] : prop.type
  if (prop.anyOf) {
    const nonNull = prop.anyOf.find((a) => a.type !== 'null')
    return nonNull?.type || 'string'
  }
  return 'string'
}

function SchemaField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string
  prop: JsonSchemaProperty
  value: unknown
  onChange: (name: string, value: unknown) => void
}) {
  const type = getEffectiveType(prop)
  const label = prop.title || name.replace(/_/g, ' ')

  if (prop.enum) {
    return (
      <div className="grid gap-2">
        <Label htmlFor={name}>{label}</Label>
        <Select
          value={value != null ? String(value) : undefined}
          onValueChange={(v: string | null) => onChange(name, v ?? undefined)}
        >
          <SelectTrigger id={name}>
            <SelectValue placeholder="Select..." />
          </SelectTrigger>
          <SelectContent>
            {prop.enum.map((opt) => (
              <SelectItem key={opt} value={opt}>
                {opt}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {prop.description && (
          <p className="text-xs text-muted-foreground">{prop.description}</p>
        )}
      </div>
    )
  }

  if (type === 'boolean') {
    return (
      <div className="flex items-center gap-3">
        <Checkbox
          id={name}
          checked={!!value}
          onCheckedChange={(checked: boolean) => onChange(name, checked)}
        />
        <div>
          <Label htmlFor={name}>{label}</Label>
          {prop.description && (
            <p className="text-xs text-muted-foreground">{prop.description}</p>
          )}
        </div>
      </div>
    )
  }

  if (type === 'integer' || type === 'number') {
    return (
      <div className="grid gap-2">
        <Label htmlFor={name}>{label}</Label>
        <Input
          id={name}
          type="number"
          value={value !== undefined && value !== null ? String(value) : ''}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            onChange(name, e.target.value ? Number(e.target.value) : undefined)
          }
          placeholder={
            prop.default !== undefined ? `Default: ${prop.default}` : ''
          }
        />
        {prop.description && (
          <p className="text-xs text-muted-foreground">{prop.description}</p>
        )}
      </div>
    )
  }

  // Default: string input
  return (
    <div className="grid gap-2">
      <Label htmlFor={name}>{label}</Label>
      <Input
        id={name}
        type="text"
        value={String(value || '')}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
          onChange(name, e.target.value || undefined)
        }
        placeholder={
          prop.default !== undefined ? `Default: ${prop.default}` : ''
        }
      />
      {prop.description && (
        <p className="text-xs text-muted-foreground">{prop.description}</p>
      )}
    </div>
  )
}

export function ToolForm({
  schema,
  onSubmit,
  loading,
}: {
  schema: JsonSchema
  onSubmit: (args: Record<string, unknown>) => void
  loading?: boolean
}) {
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [showAdvanced, setShowAdvanced] = useState(false)

  const properties = schema.properties || {}
  const required = new Set(schema.required || [])

  const requiredFields = Object.entries(properties).filter(([k]) =>
    required.has(k)
  )
  const optionalFields = Object.entries(properties).filter(
    ([k]) => !required.has(k)
  )

  const handleChange = (name: string, value: unknown) => {
    setValues((prev) => {
      const next = { ...prev }
      if (value === undefined || value === '' || value === null) {
        delete next[name]
      } else {
        next[name] = value
      }
      return next
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const args: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(values)) {
      if (v !== undefined && v !== null && v !== '') args[k] = v
    }
    onSubmit(args)
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4">
      {requiredFields.map(([name, prop]) => (
        <SchemaField
          key={name}
          name={name}
          prop={prop}
          value={values[name]}
          onChange={handleChange}
        />
      ))}

      {optionalFields.length > 0 && (
        <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
          <CollapsibleTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="gap-1 text-muted-foreground"
              />
            }
          >
            <IconChevronDown
              className={`h-4 w-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
            />
            {optionalFields.length} optional parameters
          </CollapsibleTrigger>
          <CollapsibleContent className="grid gap-4 pt-2">
            {optionalFields.map(([name, prop]) => (
              <SchemaField
                key={name}
                name={name}
                prop={prop}
                value={values[name]}
                onChange={handleChange}
              />
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}

      <Button type="submit" disabled={loading} className="w-full">
        {loading ? <Spinner className="mr-2 h-4 w-4" /> : null}
        {loading ? 'Running...' : 'Execute'}
      </Button>
    </form>
  )
}
