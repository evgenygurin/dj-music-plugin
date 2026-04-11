'use client'

import * as React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  IconLayoutDashboard,
  IconVinyl,
  IconPlaylist,
  IconStack2,
  IconSearch,
  IconTags,
  IconWaveSquare,
  IconPackageExport,
  IconTerminal2,
  IconSettings,
  IconDisc,
} from '@tabler/icons-react'

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'

const mainItems = [
  { title: 'Dashboard', url: '/', icon: IconLayoutDashboard },
  { title: 'Library', url: '/library', icon: IconVinyl },
  { title: 'Playlists', url: '/playlists', icon: IconPlaylist },
  { title: 'Sets', url: '/sets', icon: IconStack2 },
  { title: 'DJ Player', url: '/player', icon: IconDisc },
]

const toolsItems = [
  { title: 'Discover', url: '/discover', icon: IconSearch },
  { title: 'Curation', url: '/curation', icon: IconTags },
  { title: 'Audio', url: '/audio', icon: IconWaveSquare },
  { title: 'Delivery', url: '/delivery', icon: IconPackageExport },
]

const systemItems = [
  { title: 'Tools', url: '/tools', icon: IconTerminal2 },
  { title: 'Admin', url: '/admin', icon: IconSettings },
]

function NavGroup({
  label,
  items,
  pathname,
}: {
  label: string
  items: { title: string; url: string; icon: React.ComponentType<{ className?: string }> }[]
  pathname: string
}) {
  return (
    <SidebarGroup>
      <SidebarGroupLabel className="dj-data text-[9px] uppercase tracking-[0.25em] text-muted-foreground/40">
        {label}
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                render={<Link href={item.url} />}
                isActive={
                  item.url === '/'
                    ? pathname === '/'
                    : pathname.startsWith(item.url)
                }
                tooltip={item.title}
              >
                <item.icon className="size-4" />
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              render={<Link href="/" />}
            >
              <div className="flex flex-1 items-center gap-2">
                <div className="grid size-7 place-items-center rounded-lg bg-foreground/5">
                  <IconDisc className="size-4 text-foreground/70" />
                </div>
                <span className="display-heading text-base text-foreground">DJ Music</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavGroup label="Main" items={mainItems} pathname={pathname} />
        <NavGroup label="Tools" items={toolsItems} pathname={pathname} />
        <NavGroup label="System" items={systemItems} pathname={pathname} />
      </SidebarContent>
      <SidebarFooter>
        <div className="px-3 py-2">
          <p className="dj-data text-[10px] text-muted-foreground/30">v0.7.0</p>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
