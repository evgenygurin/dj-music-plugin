import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format milliseconds as "M:SS" */
export function formatDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

const CAMELOT_MAP: Record<number, string> = {
  0: '5A', 1: '12A', 2: '7A', 3: '2A', 4: '9A', 5: '4A',
  6: '11A', 7: '6A', 8: '1A', 9: '8A', 10: '3A', 11: '10A',
  12: '5B', 13: '12B', 14: '7B', 15: '2B', 16: '9B', 17: '4B',
  18: '11B', 19: '6B', 20: '1B', 21: '8B', 22: '3B', 23: '10B',
}

export function camelotNotation(keyCode: number | null): string {
  if (keyCode === null || keyCode === undefined) return '—'
  return CAMELOT_MAP[keyCode] ?? '—'
}

export function formatLufs(lufs: number | null): string {
  if (lufs === null || lufs === undefined) return '—'
  return `${lufs.toFixed(1)} LUFS`
}

export function formatBpm(bpm: number | null): string {
  if (bpm === null || bpm === undefined) return '—'
  return bpm.toFixed(1)
}

export function scoreColor(score: number | null): string {
  if (score === null || score === undefined) return 'text-muted-foreground'
  if (score === 0) return 'text-red-500 font-bold'
  if (score < 0.4) return 'text-red-400'
  if (score < 0.7) return 'text-yellow-400'
  return 'text-green-400'
}
