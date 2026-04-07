const MCP_HTTP_URL = process.env.MCP_HTTP_URL ?? 'http://localhost:8000'

export interface ToolInfo {
  name: string
  description: string | null
  tags: string[]
  annotations: Record<string, unknown> | null
  input_schema: Record<string, unknown>
  timeout: number | null
}

export interface ToolCallResult {
  tool_name: string
  content: Array<{ type: string; text?: string }>
  structured_content: Record<string, unknown> | null
  is_error: boolean
}

export async function fetchTools(tag?: string): Promise<ToolInfo[]> {
  const url = tag
    ? `${MCP_HTTP_URL}/api/tools?tag=${tag}`
    : `${MCP_HTTP_URL}/api/tools`
  try {
    const res = await fetch(url, { next: { revalidate: 60 } })
    if (!res.ok) return []
    const data = await res.json()
    return data.tools || []
  } catch {
    // Backend unavailable (e.g. during `next build` with MCP server down).
    // Pages render in their empty state instead of crashing the build.
    return []
  }
}

export async function fetchToolSchema(
  name: string
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${MCP_HTTP_URL}/api/tools/${name}/schema`, {
      next: { revalidate: 60 },
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function callTool(
  name: string,
  args: Record<string, unknown>
): Promise<ToolCallResult> {
  try {
    const res = await fetch(`${MCP_HTTP_URL}/api/tools/${name}/call`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ arguments: args }),
    })
    if (!res.ok) {
      const error = await res.text()
      return {
        tool_name: name,
        content: [{ type: 'text', text: error }],
        structured_content: null,
        is_error: true,
      }
    }
    return res.json()
  } catch (err) {
    return {
      tool_name: name,
      content: [
        {
          type: 'text',
          text: err instanceof Error ? err.message : 'MCP backend unreachable',
        },
      ],
      structured_content: null,
      is_error: true,
    }
  }
}
