'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import { IconAlertTriangle, IconRefresh, IconX } from '@tabler/icons-react'

import { useAudioPlayer } from '@/components/audio-player/audio-player-context'
import { ControlPanel } from './control-panel'
import { MediumPlayerBar } from './medium-player-bar'
import { MiniPlayerBar } from './mini-player-bar'
import { PlayerHero } from './player-hero'
import { SetIndicatorChip } from './set-indicator-chip'
import { SetPlannerDrawer } from './set-planner-drawer'
import { TransitionVisualizer } from './transition-visualizer'
import { usePlayer } from './player-provider'

export function Player() {
  const pathname = usePathname()
  const player = usePlayer()
  const [controlPanelOpen, setControlPanelOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Hide the global player on /player — that route renders its own
  // <DjPlayer> as the primary transport and doesn't need the fixed
  // mini/medium bars stacking on top.
  if (pathname === '/player') return null

  const error = player.audio.error

  return (
    <div data-player-root="true">
      <PlayerHero />
      <MiniPlayerBar />
      <MediumPlayerBar
        onCollapse={() => player.jumpToLayer(1)}
        onOpenControlPanel={() => setControlPanelOpen(true)}
      />
      {player.set.active && (
        <div className="pointer-events-none fixed bottom-[88px] left-1/2 z-40 -translate-x-1/2">
          <div className="pointer-events-auto">
            <SetIndicatorChip onOpen={() => setDrawerOpen(true)} />
          </div>
        </div>
      )}
      <TransitionVisualizer />
      <ControlPanel open={controlPanelOpen} onClose={() => setControlPanelOpen(false)} />
      <SetPlannerDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {error && <PlayerErrorBanner key={error} message={error} />}
    </div>
  )
}

/**
 * Blocking error banner shown above the mini/medium bars when the
 * audio engine reports a failure. "Blocking" in the sense that it
 * surfaces the error in a way the user cannot ignore — it sits over
 * the transport bars and offers a one-click Retry that re-plays the
 * current track (a successful `play()` clears `error` inside the
 * engine) plus a Dismiss that hides the banner locally via a
 * `dismissed` flag. The parent keys this component on `message`, so
 * a distinct subsequent failure remounts a fresh banner and the
 * dismiss state resets automatically.
 */
function PlayerErrorBanner({ message }: { message: string }) {
  const player = useAudioPlayer()
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div
      role="alert"
      className="fixed inset-x-0 bottom-[72px] z-50 mx-auto max-w-2xl px-4"
    >
      <div className="flex items-center gap-3 rounded-lg border border-red-500/40 bg-red-950/90 px-4 py-2.5 shadow-lg backdrop-blur-sm">
        <IconAlertTriangle className="size-4 shrink-0 text-red-400" />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-red-200">Playback error</div>
          <div className="truncate text-xs text-red-300/80">{message}</div>
        </div>
        <button
          type="button"
          onClick={() => {
            if (player.current) player.play(player.current)
          }}
          disabled={!player.current}
          aria-label="Retry playback"
          className="flex items-center gap-1 rounded border border-red-400/40 bg-red-500/10 px-2 py-1 text-xs font-medium text-red-200 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <IconRefresh className="size-3" />
          Retry
        </button>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss error"
          className="rounded p-1 text-red-300/70 transition-colors hover:bg-red-500/10 hover:text-red-200"
        >
          <IconX className="size-3.5" />
        </button>
      </div>
    </div>
  )
}

