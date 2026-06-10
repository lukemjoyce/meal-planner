import Anthropic from '@anthropic-ai/sdk'
import type { GroceryStore } from './grocery-data'
import type { Ingredient, MealPreferences, RecipeData, UserPreferences, WeekMeals } from './types'
import { filterLibraryByDiet, compactLibraryForPrompt, getRecipeLibrary } from './recipe-library'

const client = new Anthropic()

// Haiku for all runtime calls — cheap enough for frequent testing and daily use
const RUNTIME_MODEL = 'claude-haiku-4-5-20251001'

export interface MealPlanRequest {
  preferences: UserPreferences
  savedRecipes: RecipeData[]
  weekStructure: {
    days: string[]
    meals: string[]
    daysOff: string[]
  }
  // Structured answers from the planner questionnaire (see meal-questionnaire-spec.md)
  mealPreferences?: MealPreferences
}

// Render questionnaire answers into clearly-labeled prompt sections. Allergies are
// emphasized as HARD exclusions, distinct from soft taste preferences.
function renderMealPreferences(prefs?: MealPreferences): string {
  if (!prefs) return ''

  const sections: string[] = []

  if (prefs.allergies.length > 0) {
    sections.push(
      `ALLERGIES — HARD CONSTRAINT. NEVER include these ingredients or their derivatives in any recipe: ${prefs.allergies.join(', ')}.`
    )
  }
  if (prefs.diet) sections.push(`Diet: ${prefs.diet}`)
  if (prefs.cuisines.length > 0) sections.push(`Preferred cuisines: ${prefs.cuisines.join(', ')}`)
  if (prefs.dislikes.length > 0) sections.push(`Avoid where possible (soft preference): ${prefs.dislikes.join(', ')}`)
  if (prefs.effort) {
    const effortText: Record<string, string> = {
      quick: 'Prefer quick recipes (under ~30 min).',
      balanced: 'A balanced mix of quick and involved recipes is fine.',
      cook: 'The user enjoys cooking and is happy with more involved recipes.',
    }
    sections.push(effortText[prefs.effort] ?? '')
  }
  if (prefs.budgetMood) {
    const budgetText: Record<string, string> = {
      tight: 'Budget is tight — favor inexpensive, cost-effective ingredients.',
      moderate: 'Moderate budget — balance cost and quality.',
      flexible: 'Budget is flexible — quality matters more than cost.',
    }
    sections.push(budgetText[prefs.budgetMood] ?? '')
  }
  if (prefs.notes) sections.push(`Additional notes from the user: ${prefs.notes}`)

  return sections.filter(Boolean).join('\n')
}

export interface GeneratedMealPlan {
  weekMeals: WeekMeals
  explanation: string
  newRecipes: Omit<RecipeData, 'id' | 'createdAt'>[]
  libraryRecipeNames: string[] // names Claude picked from the pre-generated library
}

export interface GroceryListItem {
  name: string
  totalAmountNeeded: number
  unit: string
  category: string
  packageLabel: string
  packageSize: number
  packageUnit: string
  packagesNeeded: number
  pricePerPackage: number
  totalCost: number
  usedInMeals: string[]
  wasteNote?: string
}

// Forced output tool for the meal plan. Claude must call this, so the SDK returns
// already-parsed JSON in `block.input` — no text scraping, no malformed-JSON repair.
const MEAL_PLAN_TOOL: Anthropic.Tool = {
  name: 'submit_meal_plan',
  description: 'Submit the planned week of meals as structured data.',
  input_schema: {
    type: 'object',
    properties: {
      explanation: { type: 'string', description: 'Brief strategy summary focusing on ingredient reuse' },
      libraryRecipeNames: {
        type: 'array',
        items: { type: 'string' },
        description: 'Exact names of recipes selected from the pre-built library',
      },
      weekMeals: {
        type: 'object',
        description:
          'Keyed by day (monday..sunday). Each day maps meal types (breakfast/lunch/dinner) to { recipeName, mealType, servings }.',
        additionalProperties: true,
      },
      newRecipes: {
        type: 'array',
        description: 'Only recipes NOT in the library that you had to invent.',
        items: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            description: { type: 'string' },
            mealType: { type: 'string' },
            servings: { type: 'number' },
            ingredients: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  name: { type: 'string' },
                  amount: { type: 'number' },
                  unit: { type: 'string' },
                  category: { type: 'string' },
                },
                required: ['name', 'amount', 'unit'],
              },
            },
            instructions: { type: 'string' },
            tags: { type: 'array', items: { type: 'string' } },
          },
          required: ['name', 'mealType', 'servings', 'ingredients'],
        },
      },
    },
    required: ['explanation', 'libraryRecipeNames', 'weekMeals', 'newRecipes'],
  },
}

export async function generateMealPlan(request: MealPlanRequest): Promise<GeneratedMealPlan> {
  const { preferences, savedRecipes, weekStructure, mealPreferences } = request

  // Filter library by dietary restrictions and build compact listing
  const library = getRecipeLibrary()
  const compatibleLibrary = filterLibraryByDiet(library, preferences.dietaryRestrictions)
  const libraryListing = compactLibraryForPrompt(compatibleLibrary)

  const savedRecipesSummary = savedRecipes.length > 0
    ? savedRecipes.map((r) => `- ${r.name} (${r.mealType}): ${r.ingredients.map((i) => i.name).join(', ')}`).join('\n')
    : 'None'

  // Stable prefix → cached. The instructions + recipe library are byte-identical
  // across requests with the same dietary restrictions, so they cache cleanly.
  // Volatile per-request data (preferences, week structure) goes in the user turn,
  // after the cache breakpoint.
  const systemBlocks: Anthropic.TextBlockParam[] = [
    {
      type: 'text',
      text: `You are a meal planner. Your goal is to select practical meals that minimize ingredient waste by reusing ingredients across the week.

You have access to a pre-built recipe library. ALWAYS prefer library recipes over creating new ones — only create a new recipe when the library has nothing suitable.

INGREDIENT OVERLAP STRATEGY:
- Pick meals that share ingredients (cilantro, sour cream, onions, chicken, etc.)
- If buying a rotisserie chicken, plan 2 meals that use it
- Think about package sizes: sour cream (8oz/16oz), cilantro (1 bunch)

Always submit your plan by calling the submit_meal_plan tool.`,
    },
    {
      type: 'text',
      text: `PRE-BUILT RECIPE LIBRARY (use these by name — they are fully defined):
${libraryListing || 'Library is empty — create new recipes.'}`,
      cache_control: { type: 'ephemeral' },
    },
  ]

  const mealPreferencesSection = renderMealPreferences(mealPreferences)

  const userPrompt = `Plan meals for the week.

USER PREFERENCES:
- Dietary restrictions: ${preferences.dietaryRestrictions.join(', ') || 'none'}
- Grocery store: ${preferences.groceryStore}
- Budget: ${preferences.weeklyBudget ? `$${preferences.weeklyBudget}/week` : 'flexible'}
- Servings per meal: ${preferences.servingsPerMeal}
${mealPreferencesSection ? `\nMEAL PREFERENCES (from questionnaire):\n${mealPreferencesSection}\n` : ''}
WEEK STRUCTURE:
- Days: ${weekStructure.days.join(', ')}
- Meals to plan: ${weekStructure.meals.join(', ')}
- Days off: ${weekStructure.daysOff.join(', ') || 'none'}

USER'S SAVED RECIPES (prefer these first):
${savedRecipesSummary}`

  const message = await client.messages.create({
    model: RUNTIME_MODEL,
    max_tokens: 4096,
    system: systemBlocks,
    tools: [MEAL_PLAN_TOOL],
    tool_choice: { type: 'tool', name: MEAL_PLAN_TOOL.name },
    messages: [{ role: 'user', content: userPrompt }],
  })

  const block = message.content.find((b) => b.type === 'tool_use')
  if (!block || block.type !== 'tool_use') {
    throw new Error('Claude did not return a meal plan')
  }
  const parsed = block.input as Partial<GeneratedMealPlan>

  return {
    weekMeals: parsed.weekMeals ?? {},
    explanation: parsed.explanation ?? '',
    newRecipes: parsed.newRecipes ?? [],
    libraryRecipeNames: parsed.libraryRecipeNames ?? [],
  }
}

// Forced output tool for the grocery list. The array is wrapped in an `items`
// object because tool input schemas must be an object at the top level.
const GROCERY_LIST_TOOL: Anthropic.Tool = {
  name: 'submit_grocery_list',
  description: 'Submit the optimized grocery list as structured data.',
  input_schema: {
    type: 'object',
    properties: {
      items: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            totalAmountNeeded: { type: 'number' },
            unit: { type: 'string' },
            category: { type: 'string' },
            packageLabel: { type: 'string' },
            packageSize: { type: 'number' },
            packageUnit: { type: 'string' },
            packagesNeeded: { type: 'number' },
            pricePerPackage: { type: 'number' },
            totalCost: { type: 'number' },
            usedInMeals: { type: 'array', items: { type: 'string' } },
            wasteNote: { type: 'string' },
          },
          required: [
            'name',
            'totalAmountNeeded',
            'unit',
            'category',
            'packageLabel',
            'packageSize',
            'packageUnit',
            'packagesNeeded',
            'pricePerPackage',
            'totalCost',
            'usedInMeals',
          ],
        },
      },
    },
    required: ['items'],
  },
}

export interface GroceryGenerationRequest {
  weekMeals: WeekMeals
  recipes: RecipeData[]
  preferences: UserPreferences
  servingsPerMeal: number
}

export async function generateGroceryList(
  request: GroceryGenerationRequest
): Promise<GroceryListItem[]> {
  const { weekMeals, recipes, preferences, servingsPerMeal } = request

  const recipeMap = new Map(recipes.map((r) => [r.id, r]))

  const mealsWithIngredients: { mealName: string; ingredients: Ingredient[]; servings: number }[] = []

  for (const [day, dayMeals] of Object.entries(weekMeals)) {
    if (!dayMeals) continue
    for (const [mealType, meal] of Object.entries(dayMeals)) {
      if (!meal) continue
      const recipe = meal.recipeId ? recipeMap.get(meal.recipeId) : undefined
      if (recipe) {
        mealsWithIngredients.push({
          mealName: `${day} ${mealType} (${meal.recipeName})`,
          ingredients: recipe.ingredients,
          servings: meal.servings ?? servingsPerMeal,
        })
      }
    }
  }

  const store = preferences.groceryStore as GroceryStore
  const budget = preferences.weeklyBudget

  // Stable instructions are cached; the store name (volatile) lives in the user
  // turn so it doesn't invalidate the cached prefix.
  const systemBlocks: Anthropic.TextBlockParam[] = [
    {
      type: 'text',
      text: `You are a grocery shopping expert. Create an optimized grocery list that:
1. Combines the same ingredient across all meals (cilantro used 3× = 1 bunch)
2. Uses real grocery store package sizes (sour cream: 8oz/16oz/24oz, chicken: sold by lb)
3. Minimizes waste — buy the smallest package that covers the need
4. Estimates realistic prices for the given store

Always submit your list by calling the submit_grocery_list tool.`,
      cache_control: { type: 'ephemeral' },
    },
  ]

  const userPrompt = `Build the grocery list for this week's meals.

MEALS:
${mealsWithIngredients.map((m) => `${m.mealName} (${m.servings} servings):\n${m.ingredients.map((i) => `  - ${i.amount} ${i.unit} ${i.name}`).join('\n')}`).join('\n\n')}

STORE: ${store}
${budget ? `BUDGET: $${budget}` : ''}`

  const message = await client.messages.create({
    model: RUNTIME_MODEL,
    max_tokens: 6000,
    system: systemBlocks,
    tools: [GROCERY_LIST_TOOL],
    tool_choice: { type: 'tool', name: GROCERY_LIST_TOOL.name },
    messages: [{ role: 'user', content: userPrompt }],
  })

  const block = message.content.find((b) => b.type === 'tool_use')
  if (!block || block.type !== 'tool_use') {
    throw new Error('Claude did not return a grocery list')
  }
  const parsed = block.input as { items?: GroceryListItem[] }
  return parsed.items ?? []
}
