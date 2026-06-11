'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { LoaderCircle } from 'lucide-react'
import { generateWeekGroceryList } from '@/app/actions/planner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import { STORE_NAMES, type GroceryStore } from '@/lib/grocery-data'
import { ProfileUpdateBanner } from '@/components/profile-update-banner'
import type { GroceryListItem } from '@/lib/claude'
import type { WeekMeals } from '@/lib/types'

interface GroceryList {
  items: GroceryListItem[]
  totalCost: number
}

interface Props {
  plan: {
    meals: WeekMeals
    groceryList: GroceryList | null
  } | null
  profile: { groceryStore: string; weeklyBudget: number | null }
  storeChange?: { from: string; to: string } | null
}

const CATEGORY_ORDER = [
  'Produce',
  'Meat & Seafood',
  'Dairy & Eggs',
  'Bakery & Bread',
  'Pantry',
  'Spices',
  'Frozen',
  'Other',
]

export function GroceryListClient({ plan, profile, storeChange }: Props) {
  const router = useRouter()
  const [isPending, startTransition] = useTransition()
  const [groceryList, setGroceryList] = useState<GroceryList | null>(plan?.groceryList ?? null)
  const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set())
  const [error, setError] = useState('')

  const storeName = STORE_NAMES[profile.groceryStore as GroceryStore] ?? profile.groceryStore

  function handleGenerate() {
    setError('')
    startTransition(async () => {
      try {
        const result = await generateWeekGroceryList()
        setGroceryList({ items: result.items as GroceryListItem[], totalCost: result.totalCost })
        setCheckedItems(new Set())
        router.refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to generate grocery list')
      }
    })
  }

  function toggleItem(name: string) {
    setCheckedItems((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const groupedItems =
    groceryList?.items.reduce(
      (acc, item) => {
        const cat = item.category ?? 'Other'
        if (!acc[cat]) acc[cat] = []
        acc[cat].push(item)
        return acc
      },
      {} as Record<string, GroceryListItem[]>
    ) ?? {}

  const sortedCategories = Object.keys(groupedItems).sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a)
    const bi = CATEGORY_ORDER.indexOf(b)
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi)
  })

  const uncheckedTotal = groceryList?.items
    .filter((item) => !checkedItems.has(item.name))
    .reduce((sum, item) => sum + item.totalCost, 0) ?? 0

  if (!plan || Object.keys(plan.meals).length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-stone-900">Grocery List</h1>
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-stone-200 py-16 text-center">
          <p className="text-2xl">🛒</p>
          <p className="mt-2 font-medium text-stone-600">No meal plan yet</p>
          <p className="mt-1 mb-4 text-sm text-stone-400">Create a week plan first, then generate your grocery list</p>
          <Button onClick={() => router.push('/planner')}>Go to Planner</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {isPending && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm">
          <LoaderCircle className="size-12 animate-spin text-primary" />
        </div>
      )}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900">Grocery List</h1>
          <p className="text-sm text-stone-500">{storeName}{profile.weeklyBudget ? ` · $${profile.weeklyBudget} budget` : ''}</p>
        </div>
        <Button onClick={handleGenerate} disabled={isPending}>
          {isPending ? 'Generating…' : groceryList ? 'Regenerate' : 'Generate List'}
        </Button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {storeChange && groceryList && (
        <ProfileUpdateBanner
          oldStore={storeChange.from}
          newStore={storeChange.to}
          onUpdate={handleGenerate}
          pending={isPending}
        />
      )}

      {groceryList && (
        <>
          <div className="flex items-center gap-4 rounded-xl border border-stone-200 bg-white p-4">
            <div>
              <p className="text-sm text-stone-500">Estimated total</p>
              <p className="text-2xl font-bold text-stone-900">${groceryList.totalCost.toFixed(2)}</p>
            </div>
            {checkedItems.size > 0 && (
              <>
                <Separator orientation="vertical" className="h-10" />
                <div>
                  <p className="text-sm text-stone-500">Remaining</p>
                  <p className="text-2xl font-bold text-stone-700">${uncheckedTotal.toFixed(2)}</p>
                </div>
                <Separator orientation="vertical" className="h-10" />
                <div>
                  <p className="text-sm text-stone-500">Checked off</p>
                  <p className="text-lg font-semibold text-green-600">{checkedItems.size} items</p>
                </div>
              </>
            )}
            {profile.weeklyBudget && (
              <>
                <Separator orientation="vertical" className="h-10" />
                <div>
                  <p className="text-sm text-stone-500">vs. budget</p>
                  <p className={`text-lg font-semibold ${groceryList.totalCost <= profile.weeklyBudget ? 'text-green-600' : 'text-red-600'}`}>
                    {groceryList.totalCost <= profile.weeklyBudget
                      ? `$${(profile.weeklyBudget - groceryList.totalCost).toFixed(2)} under`
                      : `$${(groceryList.totalCost - profile.weeklyBudget).toFixed(2)} over`}
                  </p>
                </div>
              </>
            )}
          </div>

          <div className="space-y-4">
            {sortedCategories.map((category) => (
              <Card key={category}>
                <CardHeader className="pb-2 pt-3">
                  <CardTitle className="text-sm font-semibold text-stone-600 uppercase tracking-wide">
                    {category}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pb-3">
                  <div className="space-y-2">
                    {groupedItems[category].map((item) => (
                      <div
                        key={item.name}
                        className={`flex items-start gap-3 rounded-lg p-2 transition-colors ${checkedItems.has(item.name) ? 'opacity-40' : ''}`}
                      >
                        <Checkbox
                          checked={checkedItems.has(item.name)}
                          onCheckedChange={() => toggleItem(item.name)}
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <p className={`text-sm font-medium text-stone-800 ${checkedItems.has(item.name) ? 'line-through' : ''}`}>
                              {item.name}
                            </p>
                            <p className="shrink-0 text-sm font-semibold text-stone-900">
                              ${item.totalCost.toFixed(2)}
                            </p>
                          </div>
                          <p className="text-xs text-stone-500">
                            {item.packageLabel}
                            {item.packagesNeeded > 1 ? ` × ${item.packagesNeeded}` : ''}
                            {' · '}
                            need {item.totalAmountNeeded} {item.unit}
                          </p>
                          {item.usedInMeals.length > 0 && (
                            <p className="mt-0.5 text-xs text-stone-400">
                              Used in: {item.usedInMeals.join(', ')}
                            </p>
                          )}
                          {item.wasteNote && (
                            <p className="mt-0.5 text-xs text-amber-600">
                              💡 {item.wasteNote}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              onClick={() => {
                const text = sortedCategories
                  .flatMap((cat) => [
                    `\n${cat.toUpperCase()}`,
                    ...groupedItems[cat].map(
                      (i) => `• ${i.packageLabel}${i.packagesNeeded > 1 ? ` ×${i.packagesNeeded}` : ''} ${i.name} — $${i.totalCost.toFixed(2)}`
                    ),
                  ])
                  .join('\n')
                navigator.clipboard.writeText(`GROCERY LIST\nTotal: $${groceryList.totalCost.toFixed(2)}\n${text}`)
              }}
            >
              Copy to Clipboard
            </Button>
          </div>
        </>
      )}

      {!groceryList && !isPending && (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-stone-200 py-16 text-center">
          <p className="text-2xl">📋</p>
          <p className="mt-2 font-medium text-stone-600">Ready to generate</p>
          <p className="mt-1 text-sm text-stone-400">
            We&apos;ll analyze your week&apos;s meals and build an optimized grocery list
          </p>
        </div>
      )}
    </div>
  )
}
