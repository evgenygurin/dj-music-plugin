import type { NextConfig } from 'next'
import path from 'node:path'

const nextConfig: NextConfig = {
  turbopack: {
    // Pin Turbopack's workspace root to the panel directory so it doesn't
    // pick up an unrelated lockfile higher up the tree.
    root: path.resolve(__dirname),
  },
}

export default nextConfig
