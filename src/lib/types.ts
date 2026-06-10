export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'

export type DayOfWeek = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday'

export const DAYS_OF_WEEK: DayOfWeek[] = [
  'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
]

export interface Ingredient {
  name: string
  amount: number
  unit: string
  category?: string
  notes?: string
}

export interface RecipeData {
  id: string
  name: string
  description: string | null
  servings: number
  mealType: string
  ingredients: Ingredient[]
  instructions: string | null
  tags: string[]
  isAiGenerated: boolean
  createdAt: Date
}

export interface PlannedMeal {
  recipeId?: string
  recipeName: string
  mealType: MealType
  servings?: number
  isCustom?: boolean
  notes?: string
}

export interface DayMeals {
  breakfast?: PlannedMeal
  lunch?: PlannedMeal
  dinner?: PlannedMeal
}

export type WeekMeals = Partial<Record<DayOfWeek, DayMeals>>

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
  store: string
  usedInMeals: string[]
  notes?: string
}

export interface UserPreferences {
  dietaryRestrictions: string[]
  foodPreferences: Record<string, string[]>
  groceryStore: string
  weeklyBudget: number | null
  servingsPerMeal: number
}

export type DietaryRestriction =
  | 'vegetarian'
  | 'vegan'
  | 'gluten-free'
  | 'dairy-free'
  | 'nut-free'
  | 'halal'
  | 'kosher'
  | 'low-carb'
  | 'keto'
  | 'paleo'

export const DIETARY_RESTRICTIONS: { value: DietaryRestriction; label: string }[] = [
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'gluten-free', label: 'Gluten-Free' },
  { value: 'dairy-free', label: 'Dairy-Free' },
  { value: 'nut-free', label: 'Nut-Free' },
  { value: 'halal', label: 'Halal' },
  { value: 'kosher', label: 'Kosher' },
  { value: 'low-carb', label: 'Low-Carb' },
  { value: 'keto', label: 'Keto' },
  { value: 'paleo', label: 'Paleo' },
]

// --- Guided meal questionnaire (see docs/meal-questionnaire-spec.md) ---

export type CookingEffort = 'quick' | 'balanced' | 'cook'
export type BudgetMood = 'tight' | 'moderate' | 'flexible'

// Structured answers from the planner questionnaire. Replaces the old free-text
// "notes" box; allergies are treated as HARD exclusions in the prompt.
export interface MealPreferences {
  allergies: string[] // fixed options + parsed "Other" — hard exclusions
  diet: string | null // single choice, or custom from "Other"
  dislikes: string[] // soft "avoid" list
  cuisines: string[] // soft preference
  effort: CookingEffort | null
  budgetMood: BudgetMood | null
  notes: string // final catch-all
}

export const EMPTY_MEAL_PREFERENCES: MealPreferences = {
  allergies: [],
  diet: null,
  dislikes: [],
  cuisines: [],
  effort: null,
  budgetMood: null,
  notes: '',
}

// Common allergens (value is what gets sent to Claude as an exclusion)
export const COMMON_ALLERGENS: { value: string; label: string }[] = [
  { value: 'peanuts', label: 'Peanuts' },
  { value: 'tree nuts', label: 'Tree nuts' },
  { value: 'dairy', label: 'Dairy' },
  { value: 'eggs', label: 'Eggs' },
  { value: 'gluten', label: 'Gluten' },
  { value: 'soy', label: 'Soy' },
  { value: 'shellfish', label: 'Shellfish' },
  { value: 'fish', label: 'Fish' },
  { value: 'sesame', label: 'Sesame' },
]

export const DIET_OPTIONS: { value: string; label: string }[] = [
  { value: 'none', label: 'No specific diet' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'pescatarian', label: 'Pescatarian' },
  { value: 'keto', label: 'Keto' },
  { value: 'paleo', label: 'Paleo' },
  { value: 'low-carb', label: 'Low-carb' },
  { value: 'halal', label: 'Halal' },
  { value: 'kosher', label: 'Kosher' },
]

export const CUISINE_OPTIONS: { value: string; label: string }[] = [
  { value: 'italian', label: 'Italian' },
  { value: 'mexican', label: 'Mexican' },
  { value: 'indian', label: 'Indian' },
  { value: 'thai', label: 'Thai' },
  { value: 'japanese', label: 'Japanese' },
  { value: 'mediterranean', label: 'Mediterranean' },
  { value: 'american', label: 'American' },
  { value: 'chinese', label: 'Chinese' },
]

export const EFFORT_OPTIONS: { value: CookingEffort; label: string; hint: string }[] = [
  { value: 'quick', label: 'Quick', hint: 'Under 30 min' },
  { value: 'balanced', label: 'Balanced', hint: 'A bit of both' },
  { value: 'cook', label: 'I want to cook', hint: 'Time to spare' },
]

export const BUDGET_MOOD_OPTIONS: { value: BudgetMood; label: string; hint: string }[] = [
  { value: 'tight', label: 'Tight', hint: 'Keep it cheap' },
  { value: 'moderate', label: 'Moderate', hint: 'Reasonable' },
  { value: 'flexible', label: 'Flexible', hint: 'Quality first' },
]
