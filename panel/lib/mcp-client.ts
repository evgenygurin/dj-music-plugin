import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'

const MCP_URL = process.env.MCP_HTTP_URL ?? 'http://localhost:8000/mcp'
const MCP_HTTP_URL = process.env.MCP_HTTP_URL ?? 'http://localhost:8000'

export async function mcpCall(
  tool: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const client = new Client({ name: 'dj-panel', version: '1.0.0' })
  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL))
  await client.connect(transport)
  try {
    const result = await client.callTool({ name: tool, arguments: args })
    if (result.isError) {
      throw new Error(
        `MCP tool ${tool} failed: ${JSON.stringify(result.content)}`
      )
    }
    const structured = result.structuredContent
    if (structured) return structured
    const textParts = (result.content as Array<{ type: string; text?: string }>)
      ?.filter((c) => c.type === 'text')
      .map((c) => c.text)
      .join('')
    return textParts ? JSON.parse(textParts) : result.content
  } finally {
    await client.close()
  }
}

// ── Tool UI types ──

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

// ── Tool UI functions (REST API) ──

export async function fetchTools(tag?: string): Promise<ToolInfo[]> {
  const url = tag
    ? `${MCP_HTTP_URL}/api/tools?tag=${tag}`
    : `${MCP_HTTP_URL}/api/tools`
  const res = await fetch(url, { next: { revalidate: 60 } })
  if (!res.ok) return []
  const data = await res.json()
  return data.tools || []
}

export async function fetchToolSchema(
  name: string
): Promise<Record<string, unknown> | null> {
  const res = await fetch(`${MCP_HTTP_URL}/api/tools/${name}/schema`, {
    next: { revalidate: 60 },
  })
  if (!res.ok) return null
  return res.json()
}

export async function callTool(
  name: string,
  args: Record<string, unknown>
): Promise<ToolCallResult> {
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
}
