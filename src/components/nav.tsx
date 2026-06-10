'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { logout } from '@/app/actions/auth'
import { Button } from '@/components/ui/button'
// Nav uses Button for actions (not links) so no buttonVariants needed
import { cn } from '@/lib/utils'

const NAV_LINKS = [
  { href: '/planner', label: 'Planner' },
  { href: '/grocery-list', label: 'Grocery List' },
  { href: '/recipes', label: 'My Recipes' },
  { href: '/profile', label: 'Profile' },
]

export function Nav({ userName }: { userName: string | null }) {
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 border-b border-border/70 bg-background/80 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link href="/planner" className="flex items-center gap-2 font-heading text-base font-bold text-foreground">
            <span className="bg-gradient-brand grid size-8 place-content-center rounded-xl text-base shadow-sm shadow-primary/20">
              🛒
            </span>
            <span className="hidden sm:inline">Hearth AI</span>
          </Link>
          <nav className="hidden gap-1 sm:flex">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                  pathname.startsWith(link.href)
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {userName && <span className="hidden text-sm text-muted-foreground sm:block">{userName}</span>}
          <form action={logout}>
            <Button variant="ghost" size="sm" type="submit">
              Sign out
            </Button>
          </form>
        </div>
      </div>
      {/* Mobile nav */}
      <nav className="flex gap-1 overflow-x-auto border-t border-border/60 px-4 pb-2 pt-1 sm:hidden">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              'rounded-lg px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors',
              pathname.startsWith(link.href)
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  )
}
