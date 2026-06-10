import { getCurrentWeekPlan } from '@/app/actions/planner'
import { getRecipes } from '@/app/actions/recipes'
import { getProfile } from '@/app/actions/profile'
import { PlannerClient } from '@/components/planner/planner-client'

export default async function PlannerPage() {
  const [plan, recipes, profile] = await Promise.all([
    getCurrentWeekPlan(),
    getRecipes(),
    getProfile(),
  ])

  return (
    <PlannerClient
      initialPlan={plan ? { weekMeals: plan.meals, hasGroceryList: !!plan.groceryList } : null}
      recipes={recipes}
      profile={{
        groceryStore: profile.groceryStore,
        weeklyBudget: profile.weeklyBudget,
        servingsPerMeal: profile.servingsPerMeal,
        dietaryRestrictions: profile.dietaryRestrictions,
        foodPreferences: profile.foodPreferences,
      }}
      storeChange={
        plan?.groceryList?.store && plan.groceryList.store !== profile.groceryStore
          ? { from: plan.groceryList.store, to: profile.groceryStore }
          : null
      }
    />
  )
}
