'use server'

import { revalidatePath } from 'next/cache'
import { db } from '@/lib/db'
import { getSession } from '@/lib/session'
import type { Ingredient } from '@/lib/types'

async function requireAuth() {
  const session = await getSession()
  if (!session) throw new Error('Unauthorized')
  return session
}

export async function getRecipes() {
  const session = await requireAuth()
  const recipes = await db.recipe.findMany({
    where: { userId: session.userId },
    orderBy: { createdAt: 'desc' },
  })
  return recipes.map((r: typeof recipes[number]) => ({
    ...r,
    ingredients: JSON.parse(r.ingredients) as Ingredient[],
    tags: JSON.parse(r.tags) as string[],
  }))
}

export async function createRecipe(data: {
  name: string
  description?: string
  servings: number
  mealType: string
  ingredients: Ingredient[]
  instructions?: string
  tags: string[]
}) {
  const session = await requireAuth()
  await db.recipe.create({
    data: {
      userId: session.userId,
      name: data.name,
      description: data.description ?? null,
      servings: data.servings,
      mealType: data.mealType,
      ingredients: JSON.stringify(data.ingredients),
      instructions: data.instructions ?? null,
      tags: JSON.stringify(data.tags),
      isAiGenerated: false,
    },
  })
  revalidatePath('/recipes')
  revalidatePath('/planner')
}

export async function saveAiRecipe(data: {
  name: string
  description?: string | null
  servings: number
  mealType: string
  ingredients: Ingredient[]
  instructions?: string | null
  tags: string[]
}) {
  const session = await requireAuth()
  const recipe = await db.recipe.create({
    data: {
      userId: session.userId,
      name: data.name,
      description: data.description ?? null,
      servings: data.servings,
      mealType: data.mealType,
      ingredients: JSON.stringify(data.ingredients),
      instructions: data.instructions ?? null,
      tags: JSON.stringify(data.tags),
      isAiGenerated: true,
    },
  })
  revalidatePath('/recipes')
  return recipe.id
}

export async function deleteRecipe(id: string) {
  const session = await requireAuth()
  await db.recipe.deleteMany({ where: { id, userId: session.userId } })
  revalidatePath('/recipes')
  revalidatePath('/planner')
}

export async function updateRecipe(
  id: string,
  data: {
    name?: string
    description?: string | null
    servings?: number
    mealType?: string
    ingredients?: Ingredient[]
    instructions?: string | null
    tags?: string[]
  }
) {
  const session = await requireAuth()
  await db.recipe.updateMany({
    where: { id, userId: session.userId },
    data: {
      ...(data.name !== undefined && { name: data.name }),
      ...(data.description !== undefined && { description: data.description }),
      ...(data.servings !== undefined && { servings: data.servings }),
      ...(data.mealType !== undefined && { mealType: data.mealType }),
      ...(data.ingredients !== undefined && { ingredients: JSON.stringify(data.ingredients) }),
      ...(data.instructions !== undefined && { instructions: data.instructions }),
      ...(data.tags !== undefined && { tags: JSON.stringify(data.tags) }),
    },
  })
  revalidatePath('/recipes')
}
