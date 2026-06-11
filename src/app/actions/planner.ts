'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { db } from '@/lib/db'
import { getSession } from '@/lib/session'
import { generateMealPlan, generateGroceryList } from '@/lib/claude'
import { saveAiRecipe } from './recipes'
import { getRecipeLibrary } from '@/lib/recipe-library'
import type { WeekMeals, UserPreferences, MealPreferences } from '@/lib/types'
import type { RecipeData } from '@/lib/types'
import type { Ingredient } from '@/lib/types'

async function requireAuth() {
  const session = await getSession()
  if (!session) throw new Error('Unauthorized')
  return session
}

export async function getCurrentWeekPlan() {
  const session = await requireAuth()
  const weekStart = getMonday(new Date())
  const plan = await db.weekPlan.findFirst({
    where: { userId: session.userId, weekStart },
    include: { groceryList: true },
  })
  return plan
    ? {
        ...plan,
        meals: JSON.parse(plan.meals) as WeekMeals,
        groceryList: plan.groceryList
          ? { ...plan.groceryList, items: JSON.parse(plan.groceryList.items) }
          : null,
      }
    : null
}

export async function saveWeekPlan(meals: WeekMeals, weekStart?: string) {
  const session = await requireAuth()
  const week = weekStart ?? getMonday(new Date())

  await db.weekPlan.upsert({
    where: { userId_weekStart: { userId: session.userId, weekStart: week } },
    create: { userId: session.userId, weekStart: week, meals: JSON.stringify(meals) },
    update: { meals: JSON.stringify(meals) },
  })
  revalidatePath('/planner')
  revalidatePath('/grocery-list')
}

export async function generateAIMealPlan(config: {
  days: string[]
  meals: string[]
  daysOff: string[]
  preferences?: MealPreferences
}) {
  const session = await requireAuth()

  const user = await db.user.findUnique({ where: { id: session.userId } })
  if (!user) redirect('/api/auth/logout')
  const savedRecipeRows = await db.recipe.findMany({ where: { userId: session.userId } })

  const preferences: UserPreferences = {
    dietaryRestrictions: JSON.parse(user.dietaryRestrictions) as string[],
    foodPreferences: JSON.parse(user.foodPreferences) as Record<string, string[]>,
    groceryStore: user.groceryStore,
    weeklyBudget: user.weeklyBudget,
    servingsPerMeal: user.servingsPerMeal,
  }

  const savedRecipes: RecipeData[] = savedRecipeRows.map((r: typeof savedRecipeRows[number]) => ({
    id: r.id,
    name: r.name,
    description: r.description,
    servings: r.servings,
    mealType: r.mealType,
    ingredients: JSON.parse(r.ingredients) as Ingredient[],
    instructions: r.instructions,
    tags: JSON.parse(r.tags) as string[],
    isAiGenerated: r.isAiGenerated,
    createdAt: r.createdAt,
  }))

  const result = await generateMealPlan({
    preferences,
    savedRecipes,
    weekStructure: config,
    mealPreferences: config.preferences,
  })

  // Save new AI-generated recipes to the user's library
  const recipeIdMap = new Map<string, string>()
  for (const newRecipe of result.newRecipes) {
    const id = await saveAiRecipe(newRecipe)
    recipeIdMap.set(newRecipe.name.toLowerCase(), id)
  }

  // Save library recipes that Claude selected — look up full details from JSON library
  const library = getRecipeLibrary()
  const libraryByName = new Map(library.map((r) => [r.name.toLowerCase(), r]))

  for (const libraryName of result.libraryRecipeNames ?? []) {
    const libraryRecipe = libraryByName.get(libraryName.toLowerCase())
    if (!libraryRecipe || recipeIdMap.has(libraryName.toLowerCase())) continue

    // Check if user already has this recipe saved
    const existing = await db.recipe.findFirst({
      where: { userId: session.userId, name: libraryRecipe.name },
    })

    if (existing) {
      recipeIdMap.set(libraryName.toLowerCase(), existing.id)
    } else {
      const id = await saveAiRecipe({
        name: libraryRecipe.name,
        description: libraryRecipe.description,
        servings: libraryRecipe.servings,
        mealType: libraryRecipe.mealType,
        ingredients: libraryRecipe.ingredients,
        instructions: libraryRecipe.instructions,
        tags: libraryRecipe.tags,
      })
      recipeIdMap.set(libraryName.toLowerCase(), id)
    }
  }

  // Resolve recipe IDs in week meals
  const resolvedMeals: WeekMeals = {}
  for (const [day, dayMeals] of Object.entries(result.weekMeals)) {
    if (!dayMeals) continue
    resolvedMeals[day as keyof WeekMeals] = {}
    for (const [mealType, meal] of Object.entries(dayMeals)) {
      if (!meal) continue
      const resolvedId =
        meal.recipeId ??
        recipeIdMap.get(meal.recipeName.toLowerCase()) ??
        undefined
      resolvedMeals[day as keyof WeekMeals]![mealType as keyof typeof dayMeals] = {
        ...meal,
        recipeId: resolvedId,
      }
    }
  }

  await saveWeekPlan(resolvedMeals)

  return { weekMeals: resolvedMeals, explanation: result.explanation }
}

export async function generateWeekGroceryList() {
  const session = await requireAuth()

  const user = await db.user.findUnique({ where: { id: session.userId } })
  if (!user) redirect('/api/auth/logout')
  const weekStart = getMonday(new Date())

  const plan = await db.weekPlan.findFirst({
    where: { userId: session.userId, weekStart },
  })
  if (!plan) throw new Error('No week plan found. Create a meal plan first.')

  const weekMeals = JSON.parse(plan.meals) as WeekMeals
  const recipeIds = Object.values(weekMeals)
    .flatMap((day) => Object.values(day ?? {}))
    .map((m) => m?.recipeId)
    .filter(Boolean) as string[]

  const recipeRows = await db.recipe.findMany({
    where: { id: { in: recipeIds } },
  })

  const recipes: RecipeData[] = recipeRows.map((r: typeof recipeRows[number]) => ({
    id: r.id,
    name: r.name,
    description: r.description,
    servings: r.servings,
    mealType: r.mealType,
    ingredients: JSON.parse(r.ingredients) as Ingredient[],
    instructions: r.instructions,
    tags: JSON.parse(r.tags) as string[],
    isAiGenerated: r.isAiGenerated,
    createdAt: r.createdAt,
  }))

  const preferences: UserPreferences = {
    dietaryRestrictions: JSON.parse(user.dietaryRestrictions) as string[],
    foodPreferences: JSON.parse(user.foodPreferences) as Record<string, string[]>,
    groceryStore: user.groceryStore,
    weeklyBudget: user.weeklyBudget,
    servingsPerMeal: user.servingsPerMeal,
  }

  const items = await generateGroceryList({
    weekMeals,
    recipes,
    preferences,
    servingsPerMeal: user.servingsPerMeal,
  })

  const totalCost = items.reduce((sum, item) => sum + item.totalCost, 0)

  await db.groceryList.upsert({
    where: { weekPlanId: plan.id },
    create: {
      weekPlanId: plan.id,
      items: JSON.stringify(items),
      totalCost,
      store: user.groceryStore,
    },
    update: {
      items: JSON.stringify(items),
      totalCost,
      store: user.groceryStore,
    },
  })

  revalidatePath('/grocery-list')
  revalidatePath('/planner')
  return { items, totalCost }
}

function getMonday(date: Date): string {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  d.setDate(diff)
  return d.toISOString().split('T')[0]
}
