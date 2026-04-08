import type { NextConfig } from 'next'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// In an ESM next.config.ts, __dirname is undefined — derive it from import.meta.url
// so Turbopack's workspace root is pinned to /panel and not a parent directory
// (there's an unrelated /Users/laptop/package.json that otherwise hijacks resolution).
const panelDir = path.dirname(fileURLToPath(import.meta.url))

const nextConfig: NextConfig = {
  serverExternalPackages: ['@modelcontextprotocol/sdk'],
  turbopack: {
    root: panelDir,
  },
}

export default nextConfig
