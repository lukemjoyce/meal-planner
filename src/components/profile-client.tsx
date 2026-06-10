'use client'

import { useState, useTransition } from 'react'
import { updateProfile } from '@/app/actions/profile'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DIETARY_RESTRICTIONS, type DietaryRestriction } from '@/lib/types'
import { STORE_NAMES, type GroceryStore } from '@/lib/grocery-data'

interface Profile {
  id: string
  email: string
  name: string | null
  dietaryRestrictions: string[]
  foodPreferences: Record<string, string[]>
  groceryStore: string
  weeklyBudget: number | null
  servingsPerMeal: number
}

export function ProfileClient({ profile }: { profile: Profile }) {
  const [isPending, startTransition] = useTransition()
  const [saved, setSaved] = useState(false)
  const [name, setName] = useState(profile.name ?? '')
  const [restrictions, setRestrictions] = useState<string[]>(profile.dietaryRestrictions)
  const [store, setStore] = useState(profile.groceryStore)
  const [budget, setBudget] = useState(profile.weeklyBudget?.toString() ?? '')
  const [servings, setServings] = useState(profile.servingsPerMeal.toString())
  const [likes, setLikes] = useState(((profile.foodPreferences.likes as string[] | undefined) ?? []).join(', '))
  const [dislikes, setDislikes] = useState(((profile.foodPreferences.dislikes as string[] | undefined) ?? []).join(', '))

  function toggleRestriction(value: string) {
    setRestrictions((prev) =>
      prev.includes(value) ? prev.filter((r) => r !== value) : [...prev, value]
    )
  }

  function handleSave() {
    startTransition(async () => {
      await updateProfile({
        name: name || undefined,
        dietaryRestrictions: restrictions,
        foodPreferences: {
          likes: likes.split(',').map((s) => s.trim()).filter(Boolean),
          dislikes: dislikes.split(',').map((s) => s.trim()).filter(Boolean),
        },
        groceryStore: store,
        weeklyBudget: budget ? parseFloat(budget) : null,
        servingsPerMeal: parseInt(servings) || 4,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    })
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-bold text-stone-900">Profile & Preferences</h1>
      <p className="text-sm text-stone-500">
        These preferences guide Claude when generating your meal plans and grocery lists.
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label>Email</Label>
            <p className="text-sm text-stone-600">{profile.email}</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Dietary Restrictions</CardTitle>
          <CardDescription>Claude will avoid these in all generated meal plans</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            {DIETARY_RESTRICTIONS.map(({ value, label }) => (
              <label key={value} className="flex cursor-pointer items-center gap-2">
                <Checkbox
                  checked={restrictions.includes(value)}
                  onCheckedChange={() => toggleRestriction(value)}
                />
                <span className="text-sm">{label}</span>
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Food Preferences</CardTitle>
          <CardDescription>Help Claude understand your taste</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="likes">Foods / cuisines I love (comma-separated)</Label>
            <Input
              id="likes"
              value={likes}
              onChange={(e) => setLikes(e.target.value)}
              placeholder="e.g. Mexican, pasta, grilled chicken, Asian food"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="dislikes">Foods I dislike or want to avoid</Label>
            <Input
              id="dislikes"
              value={dislikes}
              onChange={(e) => setDislikes(e.target.value)}
              placeholder="e.g. seafood, mushrooms, very spicy food"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Shopping & Budget</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label>Preferred grocery store</Label>
            <Select value={store} onValueChange={(v) => { if (v) setStore(v) }}>
              <SelectTrigger>
                <SelectValue>{STORE_NAMES[store as GroceryStore] ?? store}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {Object.entries(STORE_NAMES).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="budget">Weekly grocery budget ($)</Label>
              <Input
                id="budget"
                type="number"
                min={0}
                step={10}
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="e.g. 150"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="servings">Servings per meal</Label>
              <Input
                id="servings"
                type="number"
                min={1}
                max={12}
                value={servings}
                onChange={(e) => setServings(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Button onClick={handleSave} disabled={isPending} className="w-full">
        {isPending ? 'Saving…' : saved ? 'Saved!' : 'Save Preferences'}
      </Button>
    </div>
  )
}
