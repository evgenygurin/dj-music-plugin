// Pure (non-client) helper for shaping data into EnergyArcChart input.
// Lives outside the 'use client' file so it can be imported from server
// components without tripping Next.js 16's stricter boundary checks.

export interface EnergyArcData {
  position: number
  title: string
  lufs: number
  fill: string
}

const LUFS_MIN = -20
const LUFS_MAX = -4

function energyColor(lufs: number): string {
  const normalized = Math.max(0, Math.min(1, (lufs - LUFS_MIN) / (LUFS_MAX - LUFS_MIN)))
  if (normalized < 0.4) return '#22c55e'
  if (normalized < 0.7) return '#eab308'
  return '#ef4444'
}

export function prepareEnergyArcData(
  data: Array<{ position: number; title: string; lufs: number }>,
): EnergyArcData[] {
  return data.map((d) => ({ ...d, fill: energyColor(d.lufs) }))
}
