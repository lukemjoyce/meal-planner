/**
 * One-time script to pre-generate the recipe library.
 * Run with: npx tsx scripts/generate-recipes.ts
 *
 * Uses claude-sonnet-4-6 for quality — this is a one-time cost.
 * Safe to re-run: skips batches already completed.
 */

import 'dotenv/config'
import Anthropic from '@anthropic-ai/sdk'
import fs from 'fs'
import path from 'path'

const client = new Anthropic()
const OUTPUT_PATH = path.join(process.cwd(), 'src', 'data', 'recipe-library.json')

interface LibraryRecipe {
  id: string
  name: string
  description: string
  mealType: string
  prepTime: number
  servings: number
  ingredients: Array<{ name: string; amount: number; unit: string; category: string }>
  instructions: string
  tags: string[]
  estimatedCostTier: 'budget' | 'moderate' | 'premium'
}

const BATCHES = [
  {
    label: 'Quick weeknight dinners — American/comfort',
    mealType: 'dinner',
    count: 25,
    focus: 'Classic American and comfort food weeknight dinners ready in 30 minutes or less. Examples: pasta dishes, burgers, quesadillas, chicken dishes, tacos, chili, stir fries. Variety of proteins. Include tags for specific protein used.',
  },
  {
    label: 'Quick weeknight dinners — Global cuisines',
    mealType: 'dinner',
    count: 25,
    focus: 'Fast international weeknight dinners: Asian (stir fry, fried rice, noodles), Mexican (enchiladas, fajitas, burritos), Mediterranean (shakshuka, kebabs, gyros), Indian (curry, dal). Ready in 30 minutes. Each recipe a distinct cuisine.',
  },
  {
    label: 'Weekend and slow-cook dinners',
    mealType: 'dinner',
    count: 20,
    focus: 'More involved weekend dinners: braised meats, roasts, slow cooker meals, homemade pizza, risotto, rack of lamb, pot roast, whole roasted chicken. Worth the extra time. Include "weekend" and "slow-cook" or "oven" tags.',
  },
  {
    label: 'Meal-prep batch dinners',
    mealType: 'dinner',
    count: 20,
    focus: 'Dinners that reheat well and batch-cook easily: grain bowls, soups, stews, casseroles, sheet pan meals, one-pot pasta, stuffed peppers. Good for making 6-8 servings at once. Include "meal-prep" tag.',
  },
  {
    label: 'Lunches — salads and grain bowls',
    mealType: 'lunch',
    count: 20,
    focus: 'Hearty salads and grain bowls for lunch: Caesar with chicken, Greek salad, quinoa bowls, farro salads, tuna niçoise, Thai beef salad, Mediterranean grain bowl, poke bowl. Filling and nutritious.',
  },
  {
    label: 'Lunches — soups, wraps, and sandwiches',
    mealType: 'lunch',
    count: 20,
    focus: 'Soups (tomato bisque, minestrone, French onion, chicken noodle, lentil), wraps (chicken Caesar, hummus veggie, turkey avocado), sandwiches (grilled cheese, BLT, club, Cuban). Diverse and satisfying.',
  },
  {
    label: 'Breakfasts',
    mealType: 'breakfast',
    count: 20,
    focus: 'Varied breakfasts: egg dishes (scrambles, frittatas, Benedict, omelets), pancakes and waffles, overnight oats, smoothie bowls, avocado toast variations, breakfast burritos, shakshuka. Both quick and leisurely options.',
  },
  {
    label: 'Budget meals and vegetarian/vegan',
    mealType: 'dinner',
    count: 25,
    focus: 'Mix of: (1) Budget-friendly dinners using cheap proteins — beans, lentils, eggs, rice, canned fish, tofu. Hearty and filling under $2/serving. (2) Vegetarian and vegan mains that are satisfying: veggie burgers, lentil stew, black bean tacos, tofu stir fry, mushroom risotto, eggplant parmigiana. Tag vegan recipes as "vegan" AND "vegetarian". Tag budget recipes as "budget".',
  },
]

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function loadExisting(): LibraryRecipe[] {
  try {
    const raw = fs.readFileSync(OUTPUT_PATH, 'utf-8')
    return JSON.parse(raw) as LibraryRecipe[]
  } catch {
    return []
  }
}

function save(recipes: LibraryRecipe[]) {
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(recipes, null, 2))
}

async function generateBatch(batch: typeof BATCHES[number], existingNames: Set<string>): Promise<LibraryRecipe[]> {
  const prompt = `Generate ${batch.count} diverse, practical recipes for the following category:

CATEGORY: ${batch.label}
MEAL TYPE: ${batch.mealType}
FOCUS: ${batch.focus}

RULES:
- Each recipe must be distinct — different main protein/base ingredient, different cuisine or technique
- Realistic ingredient amounts (e.g., "1 lb ground beef", "2 cups rice", "3 cloves garlic")
- Instructions should be clear, 3-6 sentences
- servings: always 4 (standard family size)
- prepTime: total time in minutes
- estimatedCostTier: "budget" (under $2/serving), "moderate" ($2-5/serving), "premium" (over $5/serving)
- tags: array including relevant items from: [quick, meal-prep, weekend, comfort, healthy, budget, high-protein, low-carb, vegetarian, vegan, gluten-free, dairy-free, dairy, gluten, eggs, beef, chicken, pork, seafood, meat, mexican, asian, mediterranean, indian, italian, american, breakfast, one-pot, slow-cook, oven, 30min]
- DO NOT generate any recipe with these names (already in library): ${existingNames.size > 0 ? [...existingNames].slice(0, 30).join(', ') : 'none yet'}

Respond ONLY with a valid JSON array. No markdown, no explanation.

[
  {
    "id": "kebab-style-slug",
    "name": "Recipe Name",
    "description": "One sentence description",
    "mealType": "${batch.mealType}",
    "prepTime": 25,
    "servings": 4,
    "ingredients": [
      { "name": "ingredient", "amount": 1, "unit": "lb", "category": "Meat & Seafood" }
    ],
    "instructions": "Step by step...",
    "tags": ["tag1", "tag2"],
    "estimatedCostTier": "moderate"
  }
]`

  const message = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 8000,
    messages: [{ role: 'user', content: prompt }],
  })

  const content = message.content[0]
  if (content.type !== 'text') throw new Error('Unexpected response type')

  const text = content.text.trim()
  const start = text.indexOf('[')
  const end = text.lastIndexOf(']') + 1
  if (start === -1) throw new Error('No JSON array found in response')

  const parsed = JSON.parse(text.slice(start, end)) as LibraryRecipe[]

  // Ensure IDs are proper slugs and deduplicate
  return parsed
    .filter((r) => r.name && !existingNames.has(r.name.toLowerCase()))
    .map((r) => ({ ...r, id: r.id || slugify(r.name) }))
}

async function main() {
  console.log('Loading existing recipes...')
  let recipes = loadExisting()
  console.log(`Found ${recipes.length} existing recipes.\n`)

  for (const batch of BATCHES) {
    const existingNames = new Set(recipes.map((r) => r.name.toLowerCase()))
    console.log(`Generating batch: "${batch.label}" (target: ${batch.count})...`)

    try {
      const newRecipes = await generateBatch(batch, existingNames)
      recipes = [...recipes, ...newRecipes]
      save(recipes)
      console.log(`  ✓ Added ${newRecipes.length} recipes. Library total: ${recipes.length}\n`)
    } catch (err) {
      console.error(`  ✗ Batch failed: ${err instanceof Error ? err.message : String(err)}`)
      console.log('  Continuing with next batch...\n')
    }

    // Brief pause between batches to be kind to rate limits
    await new Promise((r) => setTimeout(r, 1000))
  }

  console.log(`\nDone! Recipe library saved to ${OUTPUT_PATH}`)
  console.log(`Total recipes: ${recipes.length}`)

  // Summary by meal type
  const byType = recipes.reduce((acc, r) => {
    acc[r.mealType] = (acc[r.mealType] ?? 0) + 1
    return acc
  }, {} as Record<string, number>)
  console.log('Breakdown:', byType)
}

main().catch((e) => {
  console.error('Fatal error:', e)
  process.exit(1)
})
