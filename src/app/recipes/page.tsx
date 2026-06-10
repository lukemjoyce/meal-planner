import { getRecipes } from '@/app/actions/recipes'
import { RecipesClient } from '@/components/recipes-client'

export default async function RecipesPage() {
  const recipes = await getRecipes()
  return <RecipesClient recipes={recipes} />
}
