import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'

const MCP_URL = process.env.MCP_HTTP_URL ?? 'http://localhost:8000/mcp'

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
