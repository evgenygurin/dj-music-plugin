'use client'

import { useState } from 'react'

import { ControlPanel } from './control-panel'
import { MediumPlayerBar } from './medium-player-bar'
import { MiniPlayerBar } from './mini-player-bar'
import { PlayerHero } from './player-hero'
import { SetIndicatorChip } from './set-indicator-chip'
import { SetPlannerDrawer } from './set-planner-drawer'
import { TransitionVisualizer } from './transition-visualizer'
import { usePlayer } from './player-provider'

export function Player() {
  const player = usePlayer()
  const [controlPanelOpen, setControlPanelOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <>
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
    </>
  )
}
