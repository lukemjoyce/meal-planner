'use client'

import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import {
  BUDGET_MOOD_OPTIONS,
  COMMON_ALLERGENS,
  CUISINE_OPTIONS,
  DIET_OPTIONS,
  EFFORT_OPTIONS,
  EMPTY_MEAL_PREFERENCES,
  type BudgetMood,
  type CookingEffort,
  type MealPreferences,
} from '@/lib/types'

interface Props {
  initial?: Partial<MealPreferences>
  onComplete: (prefs: MealPreferences, saveToProfile: boolean) => void
  onCancel?: () => void
  isSubmitting?: boolean
}

// Steps that make up the questionnaire. Step 0 (days/meals) stays in the planner;
// this wizard owns the taste & constraint questions plus a final review.
const STEP_TITLES = ['Allergies', 'Diet', 'Tastes', 'This week', 'Review'] as const
const LAST_STEP = STEP_TITLES.length - 1

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

// Merge fixed selections with parsed free-text, de-duplicated (case-insensitive).
function mergeUnique(...lists: string[][]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const list of lists) {
    for (const item of list) {
      const key = item.toLowerCase()
      if (!seen.has(key)) {
        seen.add(key)
        out.push(item)
      }
    }
  }
  return out
}

export function MealQuestionnaire({ initial, onComplete, onCancel, isSubmitting }: Props) {
  const seed = { ...EMPTY_MEAL_PREFERENCES, ...initial }

  const [step, setStep] = useState(0)

  // Allergies
  const [allergens, setAllergens] = useState<string[]>(
    seed.allergies.filter((a) => COMMON_ALLERGENS.some((o) => o.value === a))
  )
  const [otherAllergies, setOtherAllergies] = useState(
    seed.allergies.filter((a) => !COMMON_ALLERGENS.some((o) => o.value === a)).join(', ')
  )

  // Diet
  const knownDiet = DIET_OPTIONS.some((o) => o.value === seed.diet)
  const [diet, setDiet] = useState<string>(seed.diet && knownDiet ? seed.diet : seed.diet ? '__other' : 'none')
  const [otherDiet, setOtherDiet] = useState(seed.diet && !knownDiet ? seed.diet : '')

  // Tastes
  const [cuisines, setCuisines] = useState<string[]>(
    seed.cuisines.filter((c) => CUISINE_OPTIONS.some((o) => o.value === c))
  )
  const [otherCuisines, setOtherCuisines] = useState(
    seed.cuisines.filter((c) => !CUISINE_OPTIONS.some((o) => o.value === c)).join(', ')
  )
  const [dislikes, setDislikes] = useState(seed.dislikes.join(', '))

  // This week
  const [effort, setEffort] = useState<CookingEffort | null>(seed.effort)
  const [budgetMood, setBudgetMood] = useState<BudgetMood | null>(seed.budgetMood)
  const [notes, setNotes] = useState(seed.notes)

  const [saveToProfile, setSaveToProfile] = useState(false)

  const preferences = useMemo<MealPreferences>(
    () => ({
      allergies: mergeUnique(allergens, splitList(otherAllergies)),
      diet: diet === 'none' ? null : diet === '__other' ? otherDiet.trim() || null : diet,
      dislikes: splitList(dislikes),
      cuisines: mergeUnique(cuisines, splitList(otherCuisines)),
      effort,
      budgetMood,
      notes: notes.trim(),
    }),
    [allergens, otherAllergies, diet, otherDiet, dislikes, cuisines, otherCuisines, effort, budgetMood, notes]
  )

  function toggle(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value])
  }

  const back = () => (step === 0 ? onCancel?.() : setStep((s) => s - 1))
  const next = () => setStep((s) => Math.min(s + 1, LAST_STEP))

  return (
    <div className="space-y-5">
      {/* Progress */}
      <div>
        <div className="mb-1.5 flex items-center justify-between text-xs text-muted-foreground">
          <span aria-live="polite" className="font-medium">
            Step {step + 1} of {STEP_TITLES.length} &bull; {STEP_TITLES[step]}
          </span>
          <span>{Math.round(((step + 1) / STEP_TITLES.length) * 100)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="bg-gradient-brand h-full rounded-full transition-all duration-300"
            style={{ width: `${((step + 1) / STEP_TITLES.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Step body */}
      <div className="min-h-[15rem]">
        {step === 0 && (
          <fieldset className="space-y-4">
            <legend className="font-heading text-base font-semibold text-foreground">
              Any allergies or intolerances?
            </legend>
            <p className="text-sm text-muted-foreground">We&apos;ll keep these out of every recipe.</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {COMMON_ALLERGENS.map(({ value, label }) => (
                <label key={value} className="flex cursor-pointer items-center gap-2">
                  <Checkbox
                    checked={allergens.includes(value)}
                    onCheckedChange={() => toggle(allergens, setAllergens, value)}
                  />
                  <span className="text-sm">{label}</span>
                </label>
              ))}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="other-allergies">Other allergies (comma-separated)</Label>
              <Input
                id="other-allergies"
                value={otherAllergies}
                onChange={(e) => setOtherAllergies(e.target.value)}
                placeholder="e.g. mustard, kiwi"
              />
            </div>
          </fieldset>
        )}

        {step === 1 && (
          <fieldset className="space-y-4">
            <legend className="font-heading text-base font-semibold text-foreground">
              Do you follow a particular diet?
            </legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {DIET_OPTIONS.map(({ value, label }) => (
                <SegmentedOption
                  key={value}
                  selected={diet === value}
                  onSelect={() => setDiet(value)}
                  label={label}
                />
              ))}
              <SegmentedOption
                selected={diet === '__other'}
                onSelect={() => setDiet('__other')}
                label="Other…"
              />
            </div>
            {diet === '__other' && (
              <div className="space-y-1.5">
                <Label htmlFor="other-diet">Tell us about your diet</Label>
                <Input
                  id="other-diet"
                  value={otherDiet}
                  onChange={(e) => setOtherDiet(e.target.value)}
                  placeholder="e.g. FODMAP, Whole30"
                />
              </div>
            )}
          </fieldset>
        )}

        {step === 2 && (
          <fieldset className="space-y-4">
            <legend className="font-heading text-base font-semibold text-foreground">
              Tastes & dislikes
            </legend>
            <div className="space-y-2">
              <Label>Cuisines you enjoy</Label>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {CUISINE_OPTIONS.map(({ value, label }) => (
                  <label key={value} className="flex cursor-pointer items-center gap-2">
                    <Checkbox
                      checked={cuisines.includes(value)}
                      onCheckedChange={() => toggle(cuisines, setCuisines, value)}
                    />
                    <span className="text-sm">{label}</span>
                  </label>
                ))}
              </div>
              <Input
                value={otherCuisines}
                onChange={(e) => setOtherCuisines(e.target.value)}
                placeholder="Other cuisines (comma-separated)"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="dislikes">Foods you&apos;d rather avoid</Label>
              <Input
                id="dislikes"
                value={dislikes}
                onChange={(e) => setDislikes(e.target.value)}
                placeholder="e.g. mushrooms, very spicy food, olives"
              />
            </div>
          </fieldset>
        )}

        {step === 3 && (
          <fieldset className="space-y-5">
            <legend className="font-heading text-base font-semibold text-foreground">How about this week?</legend>
            <div className="space-y-2">
              <Label>How much effort for cooking?</Label>
              <div className="grid grid-cols-3 gap-2">
                {EFFORT_OPTIONS.map(({ value, label, hint }) => (
                  <SegmentedOption
                    key={value}
                    selected={effort === value}
                    onSelect={() => setEffort(effort === value ? null : value)}
                    label={label}
                    hint={hint}
                  />
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label>Budget mood</Label>
              <div className="grid grid-cols-3 gap-2">
                {BUDGET_MOOD_OPTIONS.map(({ value, label, hint }) => (
                  <SegmentedOption
                    key={value}
                    selected={budgetMood === value}
                    onSelect={() => setBudgetMood(budgetMood === value ? null : value)}
                    label={label}
                    hint={hint}
                  />
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="notes">Anything else we should know?</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. use up the spinach I have, cooking for a toddler too…"
                className="resize-none"
                rows={2}
              />
            </div>
          </fieldset>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <h3 className="font-heading text-base font-semibold text-foreground">Review your answers</h3>
            <dl className="space-y-3 text-sm">
              <ReviewRow label="Allergies" onEdit={() => setStep(0)}>
                {preferences.allergies.length ? (
                  <ChipList items={preferences.allergies} tone="destructive" />
                ) : (
                  <Muted>None</Muted>
                )}
              </ReviewRow>
              <ReviewRow label="Diet" onEdit={() => setStep(1)}>
                {preferences.diet ? <span className="capitalize">{preferences.diet}</span> : <Muted>No specific diet</Muted>}
              </ReviewRow>
              <ReviewRow label="Cuisines" onEdit={() => setStep(2)}>
                {preferences.cuisines.length ? <ChipList items={preferences.cuisines} /> : <Muted>No preference</Muted>}
              </ReviewRow>
              <ReviewRow label="Avoid" onEdit={() => setStep(2)}>
                {preferences.dislikes.length ? <ChipList items={preferences.dislikes} /> : <Muted>Nothing in particular</Muted>}
              </ReviewRow>
              <ReviewRow label="This week" onEdit={() => setStep(3)}>
                <span className="capitalize">
                  {[
                    preferences.effort && EFFORT_OPTIONS.find((o) => o.value === preferences.effort)?.label,
                    preferences.budgetMood && `${BUDGET_MOOD_OPTIONS.find((o) => o.value === preferences.budgetMood)?.label} budget`,
                  ]
                    .filter(Boolean)
                    .join(' · ') || <Muted>No preference</Muted>}
                </span>
              </ReviewRow>
              {preferences.notes && (
                <ReviewRow label="Notes" onEdit={() => setStep(3)}>
                  <span className="text-foreground/80">{preferences.notes}</span>
                </ReviewRow>
              )}
            </dl>
            <label className="flex cursor-pointer items-center gap-2 pt-1">
              <Checkbox checked={saveToProfile} onCheckedChange={() => setSaveToProfile((v) => !v)} />
              <span className="text-sm text-muted-foreground">Save these to my profile for next time</span>
            </label>
          </div>
        )}
      </div>

      {/* Footer nav */}
      <div className="flex items-center justify-between border-t border-border pt-4">
        <Button variant="ghost" onClick={back} disabled={isSubmitting}>
          {step === 0 ? 'Cancel' : 'Back'}
        </Button>
        <div className="flex items-center gap-2">
          {step !== LAST_STEP && step !== 0 && (
            <Button variant="ghost" onClick={next} disabled={isSubmitting}>
              Skip
            </Button>
          )}
          {step === LAST_STEP ? (
            <Button onClick={() => onComplete(preferences, saveToProfile)} disabled={isSubmitting}>
              {isSubmitting ? 'Generating with Claude…' : 'Generate my plan'}
            </Button>
          ) : (
            <Button onClick={next} disabled={isSubmitting}>
              Next
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

function SegmentedOption({
  selected,
  onSelect,
  label,
  hint,
}: {
  selected: boolean
  onSelect: () => void
  label: string
  hint?: string
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'flex flex-col items-start rounded-xl border px-3 py-2 text-left text-sm transition-all outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
        selected
          ? 'border-brand bg-brand/10 font-semibold text-foreground shadow-sm shadow-primary/10'
          : 'border-input text-muted-foreground hover:border-brand/40 hover:bg-muted'
      )}
    >
      <span>{label}</span>
      {hint && <span className={cn('text-xs', selected ? 'text-brand-foreground' : 'text-muted-foreground/70')}>{hint}</span>}
    </button>
  )
}

function ReviewRow({
  label,
  onEdit,
  children,
}: {
  label: string
  onEdit: () => void
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-2.5 last:border-0">
      <div className="flex-1">
        <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
        <dd className="mt-1">{children}</dd>
      </div>
      <Button variant="link" size="sm" onClick={onEdit} className="h-auto p-0 text-xs">
        Edit
      </Button>
    </div>
  )
}

function ChipList({ items, tone }: { items: string[]; tone?: 'destructive' }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Badge key={item} variant={tone === 'destructive' ? 'destructive' : 'secondary'} className="capitalize">
          {item}
        </Badge>
      ))}
    </div>
  )
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span className="text-muted-foreground/70">{children}</span>
}
