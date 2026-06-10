'use client'

import { Button } from '@/components/ui/button'
import { STORE_NAMES, type GroceryStore } from '@/lib/grocery-data'

interface Props {
  oldStore: string
  newStore: string
  onUpdate: () => void
  pending?: boolean
}

const storeName = (s: string) => STORE_NAMES[s as GroceryStore] ?? s

// Shown on the planner and grocery-list pages when the user changed their grocery
// store in Profile after the current grocery list was generated. Updating from
// either page regenerates the one shared grocery list, so both pages stay in sync.
export function ProfileUpdateBanner({ oldStore, newStore, onUpdate, pending }: Props) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-brand/30 bg-brand-muted px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-brand-foreground">
        <span className="font-semibold">You&apos;ve updated your profile settings.</span> Grocery
        store changed{' '}
        <span className="font-medium">
          {storeName(oldStore)} → {storeName(newStore)}
        </span>
        . Update your grocery list?
      </p>
      <Button size="sm" onClick={onUpdate} disabled={pending} className="shrink-0">
        {pending ? 'Updating…' : 'Update grocery list'}
      </Button>
    </div>
  )
}
