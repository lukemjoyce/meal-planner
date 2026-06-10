'use server'

import { revalidatePath } from 'next/cache'
import { db } from '@/lib/db'
import { getSession } from '@/lib/session'

async function requireAuth() {
  const session = await getSession()
  if (!session) throw new Error('Unauthorized')
  return session
}

export async function getProfile() {
  const session = await requireAuth()
  const user = await db.user.findUniqueOrThrow({
    where: { id: session.userId },
    select: {
      id: true,
      email: true,
      name: true,
      dietaryRestrictions: true,
      foodPreferences: true,
      groceryStore: true,
      weeklyBudget: true,
      servingsPerMeal: true,
      prefsUpdatedAt: true,
    },
  })
  return {
    ...user,
    dietaryRestrictions: JSON.parse(user.dietaryRestrictions) as string[],
    foodPreferences: JSON.parse(user.foodPreferences) as Record<string, string[]>,
  }
}

export async function updateProfile(data: {
  name?: string
  dietaryRestrictions?: string[]
  foodPreferences?: Record<string, string[]>
  groceryStore?: string
  weeklyBudget?: number | null
  servingsPerMeal?: number
}) {
  const session = await requireAuth()
  await db.user.update({
    where: { id: session.userId },
    data: {
      ...(data.name !== undefined && { name: data.name }),
      ...(data.dietaryRestrictions !== undefined && {
        dietaryRestrictions: JSON.stringify(data.dietaryRestrictions),
      }),
      ...(data.foodPreferences !== undefined && {
        foodPreferences: JSON.stringify(data.foodPreferences),
      }),
      ...(data.groceryStore !== undefined && { groceryStore: data.groceryStore }),
      ...(data.weeklyBudget !== undefined && { weeklyBudget: data.weeklyBudget }),
      ...(data.servingsPerMeal !== undefined && { servingsPerMeal: data.servingsPerMeal }),
      // Mark preferences as freshly changed so an existing meal plan / grocery list
      // can be flagged stale until regenerated.
      prefsUpdatedAt: new Date(),
    },
  })
  revalidatePath('/profile')
  revalidatePath('/planner')
  revalidatePath('/grocery-list')
}
