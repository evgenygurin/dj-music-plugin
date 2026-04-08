'use client'

import { useEffect, useRef } from 'react'

import { useAudioPlayer } from '@/components/audio-player/audio-player-context'

type AudioPlayerApi = ReturnType<typeof useAudioPlayer>

/**
 * Global keyboard shortcuts for the audio player.
 *
 * Mounted once inside PlayerProvider so shortcuts are always
 * available as long as the provider tree is live. They are
 * **focus-scoped**: a shortcut only fires when `document.activeElement`
 * is inside a DOM subtree marked with `data-player-root="true"` —
 * currently the global `<Player>` bars and the `<DjPlayer>` root on
 * `/player`. This prevents Space from hijacking text inputs or
 * buttons elsewhere in the app.
 *
 * The listener reads the live engine through a ref so `useEffect`
 * depends only on mount lifecycle — the handler is attached once
 * and removed on unmount rather than re-wired on every state tick.
 *
 * Bindings (no modifier — Cmd/Ctrl/Alt combos pass through):
 *   Space / K   — play/pause toggle
 *   ArrowLeft   — seek −5s
 *   ArrowRight  — seek +5s
 *   J           — seek −10s
 *   L           — seek +10s
 */
export function PlayerKeyboardShortcuts() {
  const player = useAudioPlayer()
  const playerRef = useRef<AudioPlayerApi>(player)

  // Keep the ref pointed at the latest engine snapshot so the
  // stable `handler` below always acts on fresh state without
  // re-subscribing the document listener.
  useEffect(() => {
    playerRef.current = player
  }, [player])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Let OS/browser shortcuts pass through untouched.
      if (e.metaKey || e.ctrlKey || e.altKey) return

      // Focus gate: only fire when focus is inside a player region.
      const active = document.activeElement
      if (!(active instanceof Element)) return
      if (!active.closest('[data-player-root="true"]')) return

      // Don't hijack typing inside form fields that happen to live
      // inside the player region (e.g. library search on /player).
      if (
        active instanceof HTMLInputElement ||
        active instanceof HTMLTextAreaElement ||
        (active instanceof HTMLElement && active.isContentEditable)
      ) {
        return
      }

      const p = playerRef.current
      if (!p.current) return

      switch (e.key) {
        case ' ':
        case 'k':
        case 'K':
          e.preventDefault()
          p.toggle()
          break
        case 'ArrowLeft':
          e.preventDefault()
          p.seek(Math.max(0, p.position - 5))
          break
        case 'ArrowRight':
          e.preventDefault()
          p.seek(
            p.duration > 0 ? Math.min(p.duration, p.position + 5) : p.position + 5,
          )
          break
        case 'j':
        case 'J':
          e.preventDefault()
          p.seek(Math.max(0, p.position - 10))
          break
        case 'l':
        case 'L':
          e.preventDefault()
          p.seek(
            p.duration > 0 ? Math.min(p.duration, p.position + 10) : p.position + 10,
          )
          break
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  return null
}
