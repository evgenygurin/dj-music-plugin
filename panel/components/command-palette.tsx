"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"

const NAV_ITEMS = [
  { name: "Dashboard", href: "/" },
  { name: "Library", href: "/library" },
  { name: "Playlists", href: "/playlists" },
  { name: "Sets", href: "/sets" },
  { name: "Discover", href: "/discover" },
  { name: "Curation", href: "/curation" },
  { name: "Audio Analysis", href: "/audio" },
  { name: "Delivery", href: "/delivery" },
  { name: "Tools", href: "/tools" },
  { name: "Admin", href: "/admin" },
]

export const OPEN_COMMAND_PALETTE_EVENT = "dj-panel:open-command-palette"

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  useEffect(() => {
    const openPalette = () => setOpen(true)
    window.addEventListener(OPEN_COMMAND_PALETTE_EVENT, openPalette)
    return () => window.removeEventListener(OPEN_COMMAND_PALETTE_EVENT, openPalette)
  }, [])

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search Pages, Tools…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Pages">
          {NAV_ITEMS.map((item) => (
            <CommandItem
              key={item.href}
              onSelect={() => {
                router.push(item.href)
                setOpen(false)
              }}
            >
              {item.name}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
