import type { Ingredient } from './types'

export interface LibraryRecipe {
  id: string
  name: string
  description: string
  mealType: string
  prepTime: number
  servings: number
  ingredients: Ingredient[]
  instructions: string
  tags: string[]
  estimatedCostTier: 'budget' | 'moderate' | 'premium'
}

let _cache: LibraryRecipe[] | null = null

export function getRecipeLibrary(): LibraryRecipe[] {
  if (_cache) return _cache
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  _cache = require('@/data/recipe-library.json') as LibraryRecipe[]
  return _cache
}

export function filterLibraryByDiet(
  library: LibraryRecipe[],
  restrictions: string[]
): LibraryRecipe[] {
  if (restrictions.length === 0) return library
  return library.filter((recipe) => {
    for (const restriction of restrictions) {
      if (restriction === 'vegetarian' && !recipe.tags.includes('vegetarian') && !recipe.tags.includes('vegan')) {
        if (recipe.tags.some((t) => ['beef', 'chicken', 'pork', 'seafood', 'meat'].includes(t))) return false
      }
      if (restriction === 'vegan' && !recipe.tags.includes('vegan')) {
        if (recipe.tags.some((t) => ['dairy', 'eggs', 'meat', 'seafood', 'beef', 'chicken', 'pork'].includes(t))) return false
      }
      if (restriction === 'gluten-free' && !recipe.tags.includes('gluten-free')) {
        if (recipe.tags.includes('gluten')) return false
      }
      if (restriction === 'dairy-free' && recipe.tags.includes('dairy')) return false
    }
    return true
  })
}

export function compactLibraryForPrompt(library: LibraryRecipe[]): string {
  return library
    .map((r) => `- ${r.name} [${r.mealType}, ${r.tags.join(', ')}]`)
    .join('\n')
}
