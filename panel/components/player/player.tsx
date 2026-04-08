'use client'

import { useState } from 'react'

import { ControlPanel } from './control-panel'
import { PlayerBar } from './player-bar'
import { SetPlannerDrawer } from './set-planner-drawer'

/**
 * Top-level player composition.
 *
 * One persistent bar (PlayerBar) always rendered at the bottom of the
 * viewport on every page and in every state. Two overlays open from it
 * on demand:
 *   - ControlPanel popover (set mode picker + mix length)
 *   - SetPlannerDrawer (energy arc graph, slot timeline, upcoming picks)
 *
 * The old layered PlayerHero / MiniPlayerBar / MediumPlayerBar split
 * was replaced after it caused the bar to disappear in several states.
 */
export function Player() {
  const [controlPanelOpen, setControlPanelOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <>
      <PlayerBar
        onOpenControlPanel={() => setControlPanelOpen(true)}
        onOpenSetPlanner={() => setDrawerOpen(true)}
      />
      <ControlPanel open={controlPanelOpen} onClose={() => setControlPanelOpen(false)} />
      <SetPlannerDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </>
  )
}
