// panel/components/player/player.tsx
'use client'

import { useState } from 'react'

import { ControlPanel } from './control-panel'
import { MediumPlayerBar } from './medium-player-bar'
import { MiniPlayerBar } from './mini-player-bar'
import { PlayerHero } from './player-hero'
import { SetIndicatorChip } from './set-indicator-chip'
import { SetPlannerDrawer } from './set-planner-drawer'
import { usePlayer } from './player-provider'

export function Player() {
  const player = usePlayer()
  const [controlPanelOpen, setControlPanelOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const openControlPanel = () => {
    if (player.layer < 3) player.jumpToLayer(3)
    setControlPanelOpen(true)
  }

  return (
    <>
      <PlayerHero />
      <MiniPlayerBar />
      <MediumPlayerBar onOpenControlPanel={openControlPanel} />
      {/* Layer 3 inline bits: show medium bar structure + set chip */}
      {player.layer >= 3 && player.audio.current && (
        <MediumPlayerBar onOpenControlPanel={openControlPanel} />
      )}
      {player.layer >= 3 && (
        <div className="pointer-events-none fixed bottom-24 left-1/2 z-40 -translate-x-1/2">
          <div className="pointer-events-auto">
            <SetIndicatorChip onOpen={() => setDrawerOpen(true)} />
          </div>
        </div>
      )}
      <ControlPanel open={controlPanelOpen} onClose={() => setControlPanelOpen(false)} />
      <SetPlannerDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </>
  )
}
