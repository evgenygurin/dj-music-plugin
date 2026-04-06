'use server'

import { callTool as callToolServer, type ToolCallResult } from '@/lib/mcp-client'

export async function executeToolAction(
  name: string,
  args: Record<string, unknown>
): Promise<ToolCallResult> {
  return callToolServer(name, args)
}
