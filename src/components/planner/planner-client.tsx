'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { generateAIMealPlan, generateWeekGroceryList, saveWeekPlan } from '@/app/actions/planner'
import { updateProfile } from '@/app/actions/profile'
import { ProfileUpdateBanner } from '@/components/profile-update-banner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { DAYS_OF_WEEK, DIET_OPTIONS, type DayOfWeek, type MealPreferences, type WeekMeals } from '@/lib/types'
import type { RecipeData } from '@/lib/types'
import { MealQuestionnaire } from './meal-questionnaire'

const MEAL_TYPES = ['breakfast', 'lunch', 'dinner'] as const

interface Props {
  initialPlan: { weekMeals: WeekMeals; hasGroceryList: boolean } | null
  recipes: RecipeData[]
  profile: {
    groceryStore: string
    weeklyBudget: number | null
    servingsPerMeal: number
    dietaryRestrictions?: string[]
    foodPreferences?: Record<string, string[]>
  }
  storeChange?: { from: string; to: string } | null
}

export function PlannerClient({ initialPlan, recipes, profile, storeChange }: Props) {
  const router = useRouter()
  const [isPending, startTransition] = useTransition()

  const [weekMeals, setWeekMeals] = useState<WeekMeals>(initialPlan?.weekMeals ?? {})
  const [selectedDays, setSelectedDays] = useState<DayOfWeek[]>(
    initialPlan ? (Object.keys(initialPlan.weekMeals) as DayOfWeek[]) : ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
  )
  const [selectedMeals, setSelectedMeals] = useState<string[]>(
    initialPlan
      ? [...new Set(Object.values(initialPlan.weekMeals).flatMap((d) => Object.keys(d ?? {})))]
      : ['dinner']
  )
  const [explanation, setExplanation] = useState('')
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'view' | 'configure'>(!initialPlan ? 'configure' : 'view')
  // Within "configure": pick the week structure first, then answer the questionnaire.
  const [configStep, setConfigStep] = useState<'structure' | 'questions'>('structure')

  // Seed questionnaire from saved profile (Phase 1: diet + cuisines + dislikes).
  const questionnaireDefaults: Partial<MealPreferences> = {
    diet: (profile.dietaryRestrictions ?? []).find((r) => DIET_OPTIONS.some((o) => o.value === r)) ?? null,
    cuisines: profile.foodPreferences?.likes ?? [],
    dislikes: profile.foodPreferences?.dislikes ?? [],
  }

  function toggleDay(day: DayOfWeek) {
    setSelectedDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    )
  }

  function toggleMeal(meal: string) {
    setSelectedMeals((prev) =>
      prev.includes(meal) ? prev.filter((m) => m !== meal) : [...prev, meal]
    )
  }

  function handleGenerate(prefs: MealPreferences, saveToProfile: boolean) {
    setError('')
    startTransition(async () => {
      try {
        if (saveToProfile) {
          await updateProfile({
            dietaryRestrictions: [
              ...(profile.dietaryRestrictions ?? []).filter((r) => !DIET_OPTIONS.some((o) => o.value === r)),
              ...(prefs.diet && DIET_OPTIONS.some((o) => o.value === prefs.diet) ? [prefs.diet] : []),
            ],
            foodPreferences: { likes: prefs.cuisines, dislikes: prefs.dislikes },
          })
        }
        const result = await generateAIMealPlan({
          days: selectedDays,
          meals: selectedMeals,
          daysOff: [],
          preferences: prefs,
        })
        setWeekMeals(result.weekMeals)
        setExplanation(result.explanation)
        setMode('view')
        setConfigStep('structure')
        router.refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to generate meal plan')
      }
    })
  }

  function handleSaveManual() {
    startTransition(async () => {
      await saveWeekPlan(weekMeals)
      router.refresh()
    })
  }

  // Store changed in profile — regenerate the shared grocery list (recipes are
  // unaffected by store, so no meal-plan regen needed). Clears the banner on both tabs.
  function handleUpdateForStore() {
    setError('')
    startTransition(async () => {
      try {
        await generateWeekGroceryList()
        router.refresh()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to update grocery list')
      }
    })
  }

  const recipeById = new Map(recipes.map((r) => [r.id, r]))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Week Planner</h1>
          <p className="text-sm text-muted-foreground">
            Current week &bull; {profile.servingsPerMeal} servings/meal &bull; {profile.groceryStore.replace('-', ' ')}
            {profile.weeklyBudget ? ` &bull; $${profile.weeklyBudget} budget` : ''}
          </p>
        </div>
        <div className="flex gap-2">
          {weekMeals && Object.keys(weekMeals).length > 0 && (
            <Button variant="outline" size="sm" onClick={() => router.push('/grocery-list')}>
              View Grocery List
            </Button>
          )}
          <Button
            size="sm"
            variant={mode === 'configure' ? 'default' : 'outline'}
            onClick={() => setMode(mode === 'configure' ? 'view' : 'configure')}
          >
            {mode === 'configure' ? 'Cancel' : 'New Plan'}
          </Button>
        </div>
      </div>

      {storeChange && mode === 'view' && Object.keys(weekMeals).length > 0 && (
        <ProfileUpdateBanner
          oldStore={storeChange.from}
          newStore={storeChange.to}
          onUpdate={handleUpdateForStore}
          pending={isPending}
        />
      )}

      {mode === 'configure' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {configStep === 'structure' ? 'Configure Your Week' : 'Tell us your preferences'}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {configStep === 'structure' ? (
              <>
                <div>
                  <Label className="mb-2 block text-sm font-medium">Which days?</Label>
                  <div className="flex flex-wrap gap-2">
                    {DAYS_OF_WEEK.map((day) => (
                      <label key={day} className="flex cursor-pointer items-center gap-1.5">
                        <Checkbox
                          checked={selectedDays.includes(day)}
                          onCheckedChange={() => toggleDay(day)}
                        />
                        <span className="text-sm capitalize">{day.slice(0, 3)}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block text-sm font-medium">Which meals?</Label>
                  <div className="flex gap-4">
                    {MEAL_TYPES.map((meal) => (
                      <label key={meal} className="flex cursor-pointer items-center gap-1.5">
                        <Checkbox
                          checked={selectedMeals.includes(meal)}
                          onCheckedChange={() => toggleMeal(meal)}
                        />
                        <span className="text-sm capitalize">{meal}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button
                    onClick={() => setConfigStep('questions')}
                    disabled={selectedDays.length === 0 || selectedMeals.length === 0}
                  >
                    Continue
                  </Button>
                  {recipes.length > 0 && (
                    <Button variant="outline" onClick={() => setMode('view')}>
                      Plan manually
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <>
                <MealQuestionnaire
                  initial={questionnaireDefaults}
                  onComplete={handleGenerate}
                  onCancel={() => setConfigStep('structure')}
                  isSubmitting={isPending}
                />
                {error && (
                  <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                    {error}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {explanation && (
        <Card className="border-brand/30 bg-brand-muted">
          <CardContent className="pt-4">
            <p className="text-sm text-brand-foreground">
              <span className="font-semibold">Claude&apos;s strategy: </span>
              {explanation}
            </p>
          </CardContent>
        </Card>
      )}

      {mode === 'view' && Object.keys(weekMeals).length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {DAYS_OF_WEEK.filter((day) => weekMeals[day]).map((day) => {
            const dayMeals = weekMeals[day] ?? {}
            return (
              <Card key={day} className="overflow-hidden transition-shadow hover:shadow-md hover:shadow-primary/5">
                <CardHeader className="pb-2 pt-3">
                  <CardTitle className="font-heading text-sm font-semibold capitalize text-foreground">{day}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 pb-3">
                  {Object.entries(dayMeals).map(([mealType, meal]) => {
                    if (!meal) return null
                    const recipe = meal.recipeId ? recipeById.get(meal.recipeId) : null
                    return (
                      <div key={mealType} className="rounded-lg bg-muted/60 p-2">
                        <div className="flex items-center justify-between gap-1">
                          <Badge variant="secondary" className="shrink-0 text-xs capitalize">
                            {mealType}
                          </Badge>
                          {recipe?.isAiGenerated && (
                            <span className="text-xs font-medium text-brand-foreground">AI</span>
                          )}
                        </div>
                        <p className="mt-1 text-sm font-medium leading-tight text-foreground">
                          {meal.recipeName}
                        </p>
                        {recipe && (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {recipe.ingredients.slice(0, 3).map((i) => i.name).join(', ')}
                            {recipe.ingredients.length > 3 ? '…' : ''}
                          </p>
                        )}
                      </div>
                    )
                  })}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {mode === 'view' && Object.keys(weekMeals).length > 0 && (
        <div className="flex gap-2">
          <Button onClick={() => router.push('/grocery-list')} disabled={isPending}>
            Generate Grocery List
          </Button>
        </div>
      )}

      {mode === 'view' && Object.keys(weekMeals).length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border py-16 text-center">
          <div className="grid size-12 place-content-center rounded-2xl bg-brand-muted text-2xl">📅</div>
          <p className="mt-3 font-heading font-medium text-foreground">No meal plan for this week</p>
          <p className="mt-1 text-sm text-muted-foreground">Click &quot;New Plan&quot; to get started</p>
        </div>
      )}
    </div>
  )
}
