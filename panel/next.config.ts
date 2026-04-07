import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  serverExternalPackages: ['@modelcontextprotocol/sdk'],
  turbopack: {
    root: __dirname,
  },
}

export default nextConfig
