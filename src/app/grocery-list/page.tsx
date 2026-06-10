import { getCurrentWeekPlan } from '@/app/actions/planner'
import { getProfile } from '@/app/actions/profile'
import { GroceryListClient } from '@/components/grocery-list-client'

export default async function GroceryListPage() {
  const [plan, profile] = await Promise.all([getCurrentWeekPlan(), getProfile()])

  const oldStore = plan?.groceryList?.store ?? null
  const storeChanged = !!oldStore && oldStore !== profile.groceryStore

  return (
    <GroceryListClient
      plan={plan}
      profile={profile}
      storeChange={storeChanged ? { from: oldStore, to: profile.groceryStore } : null}
    />
  )
}
