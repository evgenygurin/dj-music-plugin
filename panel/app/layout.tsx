import type { Metadata, Viewport } from 'next'
import localFont from 'next/font/local'
import { Instrument_Serif } from 'next/font/google'
import { JetBrains_Mono } from 'next/font/google'
import { ThemeProvider } from 'next-themes'
import { Analytics } from '@vercel/analytics/react'
import { Toaster } from '@/components/ui/sonner'
import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar'
import { AppSidebar } from '@/components/app-sidebar'
import { CommandPalette } from '@/components/command-palette'
import { PlayerProvider } from '@/components/player/player-provider'
import { Player } from '@/components/player/player'
import { BottomNav } from '@/components/bottom-nav'
import './globals.css'

const geistSans = localFont({
  src: [{ path: './fonts/GeistVF.woff2', style: 'normal' }],
  variable: '--font-geist-sans',
  display: 'swap',
  fallback: ['-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
})

const geistMono = localFont({
  src: [{ path: './fonts/GeistMonoVF.woff2', style: 'normal' }],
  variable: '--font-geist-mono',
  display: 'swap',
  fallback: ['ui-monospace', 'SFMono-Regular', 'monospace'],
})

const instrumentSerif = Instrument_Serif({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-instrument-serif',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'DJ Music Panel',
  description: 'Techno library management dashboard',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'DJ Music',
  },
  other: {
    'apple-mobile-web-app-capable': 'yes',
    'mobile-web-app-capable': 'yes',
  },
}

export const viewport: Viewport = {
  themeColor: '#111111',
  viewportFit: 'cover',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning className="dark">
      <head>
        <link rel="apple-touch-icon" href="/icon-192.png" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable} min-h-dvh antialiased`}
      >
        <a
          href="#main-content"
          className="sr-only fixed left-4 top-4 z-[100] rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-lg focus:not-sr-only"
        >
          Skip to Main Content
        </a>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <PlayerProvider>
            <SidebarProvider
              style={{
                '--sidebar-width': 'calc(var(--spacing) * 64)',
                '--header-height': '3.25rem',
              } as React.CSSProperties}
            >
              {/* Sidebar hidden on mobile via CSS, but Provider wraps everything */}
              <div className="hidden md:contents">
                <AppSidebar variant="inset" />
              </div>
              <SidebarInset className="pb-[calc(8.5rem+env(safe-area-inset-bottom,0px))] md:pb-24">{children}</SidebarInset>
              <CommandPalette />
            </SidebarProvider>
            {/* Mobile bottom nav */}
            <BottomNav />
            <Player />
          </PlayerProvider>
          <Toaster />
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
