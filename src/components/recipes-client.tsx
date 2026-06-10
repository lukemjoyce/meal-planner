'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { createRecipe, deleteRecipe } from '@/app/actions/recipes'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import type { RecipeData, Ingredient } from '@/lib/types'

interface Props {
  recipes: RecipeData[]
}

const MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack']

function RecipeCard({ recipe, onDelete }: { recipe: RecipeData; onDelete: (id: string) => void }) {
  const [isPending, startTransition] = useTransition()
  const [open, setOpen] = useState(false)

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2 pt-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base leading-tight">{recipe.name}</CardTitle>
          <div className="flex shrink-0 items-center gap-1">
            {recipe.isAiGenerated && <Badge variant="secondary" className="text-xs">AI</Badge>}
            <Badge variant="outline" className="text-xs capitalize">{recipe.mealType}</Badge>
          </div>
        </div>
        {recipe.description && (
          <p className="text-xs text-stone-500 leading-snug">{recipe.description}</p>
        )}
      </CardHeader>
      <CardContent className="pb-3">
        <p className="text-xs font-medium text-stone-600 mb-1">
          {recipe.servings} servings · {recipe.ingredients.length} ingredients
        </p>
        <div className="flex flex-wrap gap-1 mb-2">
          {recipe.ingredients.slice(0, 5).map((ing) => (
            <span key={ing.name} className="rounded bg-stone-100 px-1.5 py-0.5 text-xs text-stone-600">
              {ing.name}
            </span>
          ))}
          {recipe.ingredients.length > 5 && (
            <span className="text-xs text-stone-400">+{recipe.ingredients.length - 5} more</span>
          )}
        </div>
        <div className="flex gap-1 mt-2">
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger
              className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'h-7 text-xs px-2')}
            >
              View
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>{recipe.name}</DialogTitle>
              </DialogHeader>
              <div className="space-y-3 text-sm">
                {recipe.description && <p className="text-stone-600">{recipe.description}</p>}
                <div>
                  <p className="font-semibold mb-1">Ingredients ({recipe.servings} servings)</p>
                  <ul className="space-y-0.5">
                    {recipe.ingredients.map((ing, i) => (
                      <li key={i} className="text-stone-600">
                        {ing.amount} {ing.unit} {ing.name}
                        {ing.notes && <span className="text-stone-400"> ({ing.notes})</span>}
                      </li>
                    ))}
                  </ul>
                </div>
                {recipe.instructions && (
                  <div>
                    <p className="font-semibold mb-1">Instructions</p>
                    <p className="text-stone-600 whitespace-pre-line leading-relaxed">{recipe.instructions}</p>
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs px-2 text-red-500 hover:text-red-700 hover:bg-red-50"
            disabled={isPending}
            onClick={() => startTransition(() => onDelete(recipe.id))}
          >
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function AddRecipeDialog({ onSaved }: { onSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const [isPending, startTransition] = useTransition()
  const [ingredients, setIngredients] = useState<Ingredient[]>([{ name: '', amount: 1, unit: 'cup', category: '' }])
  const [mealType, setMealType] = useState('dinner')
  const [error, setError] = useState('')

  function addIngredient() {
    setIngredients((prev) => [...prev, { name: '', amount: 1, unit: 'cup', category: '' }])
  }

  function updateIngredient(index: number, field: keyof Ingredient, value: string | number) {
    setIngredients((prev) => prev.map((ing, i) => i === index ? { ...ing, [field]: value } : ing))
  }

  function removeIngredient(index: number) {
    setIngredients((prev) => prev.filter((_, i) => i !== index))
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    const fd = new FormData(e.currentTarget)
    const validIngredients = ingredients.filter((i) => i.name.trim())

    if (validIngredients.length === 0) {
      setError('Add at least one ingredient')
      return
    }

    startTransition(async () => {
      try {
        await createRecipe({
          name: fd.get('name') as string,
          description: fd.get('description') as string || undefined,
          servings: Number(fd.get('servings')),
          mealType,
          ingredients: validIngredients,
          instructions: fd.get('instructions') as string || undefined,
          tags: (fd.get('tags') as string).split(',').map((t) => t.trim()).filter(Boolean),
        })
        setOpen(false)
        onSaved()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to save recipe')
      }
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className={buttonVariants({ size: 'sm' })}>Add Recipe</DialogTrigger>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add Recipe</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2 space-y-1">
              <Label htmlFor="name">Recipe name *</Label>
              <Input id="name" name="name" required placeholder="e.g. Chicken Tacos" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="servings">Servings</Label>
              <Input id="servings" name="servings" type="number" min={1} defaultValue={4} />
            </div>
            <div className="space-y-1">
              <Label>Meal type</Label>
              <Select value={mealType} onValueChange={(v) => { if (v) setMealType(v) }}>
                <SelectTrigger>
                  <SelectValue className="capitalize">{mealType}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {MEAL_TYPES.map((t) => (
                    <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="col-span-2 space-y-1">
              <Label htmlFor="description">Description (optional)</Label>
              <Input id="description" name="description" placeholder="Brief description" />
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Ingredients</Label>
              <Button type="button" variant="ghost" size="sm" onClick={addIngredient}>+ Add</Button>
            </div>
            {ingredients.map((ing, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Input
                  placeholder="Amount"
                  type="number"
                  step="0.25"
                  value={ing.amount}
                  onChange={(e) => updateIngredient(i, 'amount', parseFloat(e.target.value))}
                  className="w-20 shrink-0"
                />
                <Input
                  placeholder="Unit"
                  value={ing.unit}
                  onChange={(e) => updateIngredient(i, 'unit', e.target.value)}
                  className="w-20 shrink-0"
                />
                <Input
                  placeholder="Ingredient name"
                  value={ing.name}
                  onChange={(e) => updateIngredient(i, 'name', e.target.value)}
                  className="flex-1"
                />
                {ingredients.length > 1 && (
                  <Button type="button" variant="ghost" size="sm" className="px-2 text-stone-400" onClick={() => removeIngredient(i)}>×</Button>
                )}
              </div>
            ))}
          </div>

          <div className="space-y-1">
            <Label htmlFor="instructions">Instructions (optional)</Label>
            <Textarea id="instructions" name="instructions" placeholder="Step by step cooking instructions..." rows={3} className="resize-none" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="tags">Tags (optional, comma-separated)</Label>
            <Input id="tags" name="tags" placeholder="e.g. quick, mexican, weeknight" />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={isPending}>{isPending ? 'Saving…' : 'Save Recipe'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function RecipesClient({ recipes: initialRecipes }: Props) {
  const router = useRouter()
  const [recipes, setRecipes] = useState(initialRecipes)
  const [, startTransition] = useTransition()

  function handleDelete(id: string) {
    startTransition(async () => {
      await deleteRecipe(id)
      setRecipes((prev) => prev.filter((r) => r.id !== id))
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900">My Recipes</h1>
          <p className="text-sm text-stone-500">
            {recipes.length} recipe{recipes.length !== 1 ? 's' : ''} · Claude uses these when generating your meal plan
          </p>
        </div>
        <AddRecipeDialog onSaved={() => router.refresh()} />
      </div>

      {recipes.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-stone-200 py-16 text-center">
          <p className="text-2xl">📖</p>
          <p className="mt-2 font-medium text-stone-600">No recipes saved yet</p>
          <p className="mt-1 text-sm text-stone-400">
            Add your favorites, or let Claude generate new ones when you create a meal plan
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {recipes.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
