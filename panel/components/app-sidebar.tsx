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
  IconCommand,
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
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
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
              <div className="flex flex-1 items-center justify-between">
                <span className="font-semibold text-sm">DJ Music</span>
                <IconCommand className="size-4 text-muted-foreground" />
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavGroup label="MAIN" items={mainItems} pathname={pathname} />
        <NavGroup label="TOOLS" items={toolsItems} pathname={pathname} />
        <NavGroup label="SYSTEM" items={systemItems} pathname={pathname} />
      </SidebarContent>
      <SidebarFooter>
        <div className="px-3 py-2">
          <p className="text-xs text-muted-foreground">v0.5.0</p>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
