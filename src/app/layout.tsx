import type { Metadata } from 'next'
import { Inter, Plus_Jakarta_Sans, Geist_Mono } from 'next/font/google'
import './globals.css'

// Body: Inter — the most readable UI workhorse.
const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' })
// Headings: Plus Jakarta Sans — geometric, friendly, modern.
const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-heading',
  weight: ['500', '600', '700', '800'],
  display: 'swap',
})
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' })

export const metadata: Metadata = {
  title: 'Meal Planner — Smart Grocery Lists',
  description: 'Plan your week, minimize waste, stay on budget.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jakarta.variable} ${geistMono.variable} h-full`}
    >
      <body className="min-h-full bg-[oklch(0.99_0.01_155)] font-sans antialiased dark:bg-background">{children}</body>
    </html>
  )
}
