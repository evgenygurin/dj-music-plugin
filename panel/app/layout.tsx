import type { Metadata, Viewport } from 'next'
import localFont from 'next/font/local'
import { Instrument_Serif } from 'next/font/google'
import { JetBrains_Mono } from 'next/font/google'
import { ThemeProvider } from 'next-themes'
import { Analytics } from '@vercel/analytics/react'
import { Toaster } from '@/components/ui/sonner'
import { AudioPlayerProvider } from '@/components/audio-player/audio-player-context'
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
  title: 'DJ Mix',
  description: 'Auto-mix techno player',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'DJ Mix',
  },
  other: {
    'apple-mobile-web-app-capable': 'yes',
    'mobile-web-app-capable': 'yes',
  },
}

export const viewport: Viewport = {
  themeColor: '#000000',
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
        className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable} min-h-dvh antialiased bg-black text-white`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <AudioPlayerProvider>
            {children}
          </AudioPlayerProvider>
          <Toaster />
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
