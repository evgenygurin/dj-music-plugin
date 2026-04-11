'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  IconLayoutDashboard,
  IconMusicBolt,
  IconVinyl,
  IconPlaylist,
  IconStack2,
  IconSearch,
} from '@tabler/icons-react'
import { useAudioPlayer } from '@/components/audio-player/audio-player-context'

const tabs = [
  { title: 'Library', url: '/library', icon: IconVinyl },
  { title: 'Discover', url: '/discover', icon: IconSearch },
  { title: 'Home', url: '/', icon: IconLayoutDashboard, center: true },
  { title: 'Playlists', url: '/playlists', icon: IconPlaylist },
  { title: 'Sets', url: '/sets', icon: IconStack2 },
]

export function BottomNav() {
  const pathname = usePathname()
  const audio = useAudioPlayer()

  if (pathname === '/player') return null
  if (audio.current) return null

  return (
    <nav className="fixed inset-x-0 bottom-0 z-50 md:hidden" style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}>
      <div className="glass border-t border-foreground/5">
        <div className="flex items-end justify-around px-1 pb-1 pt-1.5">
          {tabs.map((tab) => {
            const isActive =
              tab.url === '/'
                ? pathname === '/'
                : pathname.startsWith(tab.url)
            const isCenter = tab.center === true
            return (
              <Link
                key={tab.url}
                href={tab.url}
                className={`flex flex-col items-center justify-center gap-0.5 min-w-[56px] py-1 rounded-lg transition-colors ${
                  isCenter ? 'px-1' : ''
                } ${
                  isActive
                    ? 'text-foreground'
                    : 'text-muted-foreground/60 active:text-foreground/80'
                }`}
              >
                {isCenter ? (
                  <span className={`grid size-9 place-items-center rounded-full border ${isActive ? 'border-foreground/30 bg-foreground/10' : 'border-border/60 bg-card/70'}`}>
                    <IconMusicBolt className="size-5" strokeWidth={isActive ? 2 : 1.7} />
                  </span>
                ) : (
                  <tab.icon className="size-[22px]" strokeWidth={isActive ? 2 : 1.5} />
                )}
                <span className="text-[10px] leading-tight font-medium">
                  {tab.title}
                </span>
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
