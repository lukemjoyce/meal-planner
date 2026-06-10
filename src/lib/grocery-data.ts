// TODO: Instacart API integration
// Replace static GROCERY_DATA pricing with live Instacart Connect API calls.
// Instacart Connect API: https://developer.instacart.com
// Key capabilities needed:
//   - GET /v2/products/search — find products by name, returns real prices + package sizes per retailer
//   - POST /v2/orders — let users place delivery orders directly from the grocery list UI
//   - GET /v2/retailers — list available stores in user's area (replaces our static STORE_NAMES)
// Integration points in this file: replace `prices` fields in GROCERY_DATA with live lookups,
// cache results per store per zip code (TTL ~4 hours) to avoid hammering the API.
// User flow: user connects Instacart account in /profile, we store their zip + preferred retailer,
// grocery list page gets a "Order via Instacart" button that POSTs their checked items.

export type GroceryStore = 'king-soopers' | 'whole-foods' | 'safeway' | 'walmart' | 'trader-joes'

export interface PackageOption {
  size: number
  unit: string
  label: string
  prices: Partial<Record<GroceryStore, number>>
}

export interface GroceryItem {
  name: string
  category: string
  packages: PackageOption[]
  defaultUnit: string
}

export const STORE_NAMES: Record<GroceryStore, string> = {
  'king-soopers': 'King Soopers',
  'whole-foods': 'Whole Foods',
  safeway: 'Safeway',
  walmart: 'Walmart',
  'trader-joes': "Trader Joe's",
}

export const GROCERY_DATA: GroceryItem[] = [
  // Produce
  {
    name: 'cilantro',
    category: 'Produce',
    defaultUnit: 'bunch',
    packages: [{ size: 1, unit: 'bunch', label: '1 bunch (~1 oz)', prices: { 'king-soopers': 0.79, 'whole-foods': 0.99, safeway: 0.89, walmart: 0.68, 'trader-joes': 0.99 } }],
  },
  {
    name: 'parsley',
    category: 'Produce',
    defaultUnit: 'bunch',
    packages: [{ size: 1, unit: 'bunch', label: '1 bunch (~1 oz)', prices: { 'king-soopers': 0.79, 'whole-foods': 0.99, safeway: 0.89, walmart: 0.68, 'trader-joes': 0.99 } }],
  },
  {
    name: 'green onions',
    category: 'Produce',
    defaultUnit: 'bunch',
    packages: [{ size: 1, unit: 'bunch', label: '1 bunch (6-8 stalks)', prices: { 'king-soopers': 0.99, 'whole-foods': 1.29, safeway: 1.09, walmart: 0.78, 'trader-joes': 0.99 } }],
  },
  {
    name: 'yellow onion',
    category: 'Produce',
    defaultUnit: 'lb',
    packages: [
      { size: 3, unit: 'lb', label: '3 lb bag', prices: { 'king-soopers': 2.49, 'whole-foods': 3.99, safeway: 2.99, walmart: 1.98, 'trader-joes': 2.99 } },
      { size: 5, unit: 'lb', label: '5 lb bag', prices: { 'king-soopers': 3.49, 'whole-foods': 5.99, safeway: 3.99, walmart: 2.98, 'trader-joes': 3.99 } },
    ],
  },
  {
    name: 'garlic',
    category: 'Produce',
    defaultUnit: 'head',
    packages: [
      { size: 1, unit: 'head', label: '1 head', prices: { 'king-soopers': 0.79, 'whole-foods': 0.99, safeway: 0.89, walmart: 0.58, 'trader-joes': 0.79 } },
      { size: 3, unit: 'head', label: '3-pack', prices: { 'king-soopers': 1.99, 'whole-foods': 2.49, safeway: 2.19, walmart: 1.78, 'trader-joes': 1.99 } },
    ],
  },
  {
    name: 'lemon',
    category: 'Produce',
    defaultUnit: 'each',
    packages: [
      { size: 1, unit: 'each', label: '1 lemon', prices: { 'king-soopers': 0.69, 'whole-foods': 0.99, safeway: 0.79, walmart: 0.58, 'trader-joes': 0.79 } },
      { size: 4, unit: 'each', label: '4-pack', prices: { 'king-soopers': 2.49, 'whole-foods': 3.49, safeway: 2.79, walmart: 1.98, 'trader-joes': 2.49 } },
    ],
  },
  {
    name: 'lime',
    category: 'Produce',
    defaultUnit: 'each',
    packages: [
      { size: 1, unit: 'each', label: '1 lime', prices: { 'king-soopers': 0.59, 'whole-foods': 0.79, safeway: 0.69, walmart: 0.48, 'trader-joes': 0.69 } },
      { size: 5, unit: 'each', label: '5-pack bag', prices: { 'king-soopers': 1.99, 'whole-foods': 2.99, safeway: 2.29, walmart: 1.78, 'trader-joes': 1.99 } },
    ],
  },
  {
    name: 'avocado',
    category: 'Produce',
    defaultUnit: 'each',
    packages: [
      { size: 1, unit: 'each', label: '1 avocado', prices: { 'king-soopers': 1.29, 'whole-foods': 1.79, safeway: 1.49, walmart: 0.98, 'trader-joes': 1.29 } },
      { size: 4, unit: 'each', label: '4-pack bag', prices: { 'king-soopers': 3.99, 'whole-foods': 5.99, safeway: 4.49, walmart: 3.48, 'trader-joes': 3.99 } },
    ],
  },
  {
    name: 'roma tomatoes',
    category: 'Produce',
    defaultUnit: 'lb',
    packages: [{ size: 1, unit: 'lb', label: 'per lb', prices: { 'king-soopers': 1.29, 'whole-foods': 1.99, safeway: 1.49, walmart: 0.98, 'trader-joes': 1.49 } }],
  },
  {
    name: 'bell pepper',
    category: 'Produce',
    defaultUnit: 'each',
    packages: [
      { size: 1, unit: 'each', label: '1 bell pepper', prices: { 'king-soopers': 1.49, 'whole-foods': 1.99, safeway: 1.69, walmart: 1.18, 'trader-joes': 1.49 } },
      { size: 3, unit: 'each', label: '3-pack', prices: { 'king-soopers': 3.49, 'whole-foods': 4.99, safeway: 3.99, walmart: 2.98, 'trader-joes': 3.49 } },
    ],
  },
  {
    name: 'jalapeño',
    category: 'Produce',
    defaultUnit: 'each',
    packages: [
      { size: 1, unit: 'each', label: '1 jalapeño', prices: { 'king-soopers': 0.25, 'whole-foods': 0.39, safeway: 0.29, walmart: 0.19, 'trader-joes': 0.29 } },
    ],
  },
  {
    name: 'broccoli',
    category: 'Produce',
    defaultUnit: 'head',
    packages: [
      { size: 1, unit: 'head', label: '1 head (~1 lb)', prices: { 'king-soopers': 1.99, 'whole-foods': 2.99, safeway: 2.29, walmart: 1.48, 'trader-joes': 1.99 } },
    ],
  },
  {
    name: 'spinach',
    category: 'Produce',
    defaultUnit: 'oz',
    packages: [
      { size: 5, unit: 'oz', label: '5 oz bag', prices: { 'king-soopers': 2.99, 'whole-foods': 3.99, safeway: 3.29, walmart: 2.48, 'trader-joes': 2.99 } },
      { size: 16, unit: 'oz', label: '1 lb bag', prices: { 'king-soopers': 4.99, 'whole-foods': 6.99, safeway: 5.49, walmart: 3.98, 'trader-joes': 4.99 } },
    ],
  },
  // Proteins
  {
    name: 'chicken breast',
    category: 'Meat & Seafood',
    defaultUnit: 'lb',
    packages: [
      { size: 1, unit: 'lb', label: 'per lb', prices: { 'king-soopers': 4.0, 'whole-foods': 6.0, safeway: 4.5, walmart: 3.48, 'trader-joes': 5.0 } },
    ],
  },
  {
    name: 'ground beef (80/20)',
    category: 'Meat & Seafood',
    defaultUnit: 'lb',
    packages: [
      { size: 1, unit: 'lb', label: 'per lb', prices: { 'king-soopers': 4.99, 'whole-foods': 7.99, safeway: 5.49, walmart: 4.48, 'trader-joes': 5.99 } },
    ],
  },
  {
    name: 'ground turkey',
    category: 'Meat & Seafood',
    defaultUnit: 'lb',
    packages: [
      { size: 1, unit: 'lb', label: 'per lb', prices: { 'king-soopers': 4.49, 'whole-foods': 6.99, safeway: 4.99, walmart: 3.98, 'trader-joes': 4.99 } },
    ],
  },
  {
    name: 'salmon fillet',
    category: 'Meat & Seafood',
    defaultUnit: 'lb',
    packages: [
      { size: 1, unit: 'lb', label: 'per lb', prices: { 'king-soopers': 9.99, 'whole-foods': 14.99, safeway: 11.99, walmart: 8.98, 'trader-joes': 11.99 } },
    ],
  },
  {
    name: 'shrimp (large, peeled)',
    category: 'Meat & Seafood',
    defaultUnit: 'lb',
    packages: [
      { size: 1, unit: 'lb', label: 'per lb', prices: { 'king-soopers': 8.99, 'whole-foods': 12.99, safeway: 9.99, walmart: 7.98, 'trader-joes': 9.99 } },
    ],
  },
  {
    name: 'eggs',
    category: 'Dairy & Eggs',
    defaultUnit: 'dozen',
    packages: [
      { size: 1, unit: 'dozen', label: '1 dozen', prices: { 'king-soopers': 3.49, 'whole-foods': 5.99, safeway: 3.99, walmart: 2.78, 'trader-joes': 3.99 } },
      { size: 18, unit: 'count', label: '18-count', prices: { 'king-soopers': 4.99, 'whole-foods': 7.99, safeway: 5.49, walmart: 3.98, 'trader-joes': 5.49 } },
    ],
  },
  // Dairy
  {
    name: 'sour cream',
    category: 'Dairy & Eggs',
    defaultUnit: 'oz',
    packages: [
      { size: 8, unit: 'oz', label: '8 oz (Daisy)', prices: { 'king-soopers': 1.79, 'whole-foods': 2.49, safeway: 1.99, walmart: 1.48, 'trader-joes': 1.99 } },
      { size: 16, unit: 'oz', label: '16 oz (Daisy)', prices: { 'king-soopers': 2.99, 'whole-foods': 3.99, safeway: 3.29, walmart: 2.48, 'trader-joes': 3.29 } },
      { size: 24, unit: 'oz', label: '24 oz (Daisy)', prices: { 'king-soopers': 3.99, 'whole-foods': 5.49, safeway: 4.29, walmart: 3.28, 'trader-joes': 4.49 } },
    ],
  },
  {
    name: 'shredded cheese',
    category: 'Dairy & Eggs',
    defaultUnit: 'oz',
    packages: [
      { size: 8, unit: 'oz', label: '8 oz bag', prices: { 'king-soopers': 2.99, 'whole-foods': 4.49, safeway: 3.29, walmart: 2.48, 'trader-joes': 3.49 } },
      { size: 16, unit: 'oz', label: '16 oz bag', prices: { 'king-soopers': 4.99, 'whole-foods': 7.99, safeway: 5.49, walmart: 3.98, 'trader-joes': 5.49 } },
    ],
  },
  {
    name: 'butter',
    category: 'Dairy & Eggs',
    defaultUnit: 'stick',
    packages: [
      { size: 4, unit: 'stick', label: '1 lb (4 sticks)', prices: { 'king-soopers': 4.49, 'whole-foods': 6.99, safeway: 4.99, walmart: 3.48, 'trader-joes': 4.99 } },
    ],
  },
  {
    name: 'heavy cream',
    category: 'Dairy & Eggs',
    defaultUnit: 'cup',
    packages: [
      { size: 1, unit: 'pint', label: '1 pint (2 cups)', prices: { 'king-soopers': 2.99, 'whole-foods': 4.49, safeway: 3.29, walmart: 2.48, 'trader-joes': 3.49 } },
    ],
  },
  {
    name: 'milk',
    category: 'Dairy & Eggs',
    defaultUnit: 'cup',
    packages: [
      { size: 1, unit: 'gallon', label: '1 gallon', prices: { 'king-soopers': 3.99, 'whole-foods': 5.99, safeway: 4.29, walmart: 2.98, 'trader-joes': 4.49 } },
    ],
  },
  // Pantry
  {
    name: 'olive oil',
    category: 'Pantry',
    defaultUnit: 'tbsp',
    packages: [
      { size: 16.9, unit: 'fl oz', label: '500ml bottle', prices: { 'king-soopers': 5.99, 'whole-foods': 9.99, safeway: 6.99, walmart: 4.98, 'trader-joes': 5.99 } },
    ],
  },
  {
    name: 'chicken broth',
    category: 'Pantry',
    defaultUnit: 'cup',
    packages: [
      { size: 32, unit: 'oz', label: '32 oz carton', prices: { 'king-soopers': 2.49, 'whole-foods': 3.99, safeway: 2.79, walmart: 1.98, 'trader-joes': 2.49 } },
    ],
  },
  {
    name: 'canned diced tomatoes',
    category: 'Pantry',
    defaultUnit: 'can',
    packages: [
      { size: 14.5, unit: 'oz', label: '14.5 oz can', prices: { 'king-soopers': 1.19, 'whole-foods': 1.99, safeway: 1.29, walmart: 0.88, 'trader-joes': 1.29 } },
    ],
  },
  {
    name: 'canned black beans',
    category: 'Pantry',
    defaultUnit: 'can',
    packages: [
      { size: 15, unit: 'oz', label: '15 oz can', prices: { 'king-soopers': 0.99, 'whole-foods': 1.49, safeway: 1.09, walmart: 0.78, 'trader-joes': 0.99 } },
    ],
  },
  {
    name: 'rice (white, long grain)',
    category: 'Pantry',
    defaultUnit: 'cup',
    packages: [
      { size: 2, unit: 'lb', label: '2 lb bag', prices: { 'king-soopers': 2.49, 'whole-foods': 3.99, safeway: 2.79, walmart: 1.88, 'trader-joes': 2.49 } },
      { size: 5, unit: 'lb', label: '5 lb bag', prices: { 'king-soopers': 4.99, 'whole-foods': 7.99, safeway: 5.49, walmart: 3.98, 'trader-joes': 5.49 } },
    ],
  },
  {
    name: 'pasta',
    category: 'Pantry',
    defaultUnit: 'oz',
    packages: [
      { size: 16, unit: 'oz', label: '1 lb box', prices: { 'king-soopers': 1.99, 'whole-foods': 2.99, safeway: 2.19, walmart: 1.28, 'trader-joes': 1.99 } },
    ],
  },
  {
    name: 'flour tortillas',
    category: 'Bakery & Bread',
    defaultUnit: 'count',
    packages: [
      { size: 10, unit: 'count', label: '10-count package', prices: { 'king-soopers': 2.99, 'whole-foods': 3.99, safeway: 3.29, walmart: 2.48, 'trader-joes': 2.99 } },
    ],
  },
  {
    name: 'soy sauce',
    category: 'Pantry',
    defaultUnit: 'tbsp',
    packages: [
      { size: 10, unit: 'fl oz', label: '10 fl oz bottle', prices: { 'king-soopers': 2.99, 'whole-foods': 3.99, safeway: 3.19, walmart: 2.18, 'trader-joes': 2.49 } },
    ],
  },
  {
    name: 'salsa',
    category: 'Pantry',
    defaultUnit: 'oz',
    packages: [
      { size: 16, unit: 'oz', label: '16 oz jar', prices: { 'king-soopers': 2.99, 'whole-foods': 4.49, safeway: 3.29, walmart: 2.18, 'trader-joes': 2.99 } },
    ],
  },
  {
    name: 'cumin (ground)',
    category: 'Spices',
    defaultUnit: 'tsp',
    packages: [
      { size: 2.5, unit: 'oz', label: '2.5 oz jar', prices: { 'king-soopers': 2.29, 'whole-foods': 3.49, safeway: 2.49, walmart: 1.78, 'trader-joes': 2.49 } },
    ],
  },
  {
    name: 'chili powder',
    category: 'Spices',
    defaultUnit: 'tsp',
    packages: [
      { size: 2.5, unit: 'oz', label: '2.5 oz jar', prices: { 'king-soopers': 2.29, 'whole-foods': 3.49, safeway: 2.49, walmart: 1.78, 'trader-joes': 2.49 } },
    ],
  },
  {
    name: 'smoked paprika',
    category: 'Spices',
    defaultUnit: 'tsp',
    packages: [
      { size: 2, unit: 'oz', label: '2 oz jar', prices: { 'king-soopers': 2.49, 'whole-foods': 3.99, safeway: 2.69, walmart: 1.98, 'trader-joes': 2.49 } },
    ],
  },
  {
    name: 'garlic powder',
    category: 'Spices',
    defaultUnit: 'tsp',
    packages: [
      { size: 3.5, unit: 'oz', label: '3.5 oz jar', prices: { 'king-soopers': 2.29, 'whole-foods': 3.49, safeway: 2.49, walmart: 1.68, 'trader-joes': 2.29 } },
    ],
  },
]

export function findGroceryItem(name: string): GroceryItem | undefined {
  const lower = name.toLowerCase()
  return GROCERY_DATA.find(
    (item) =>
      item.name.toLowerCase() === lower ||
      lower.includes(item.name.toLowerCase()) ||
      item.name.toLowerCase().includes(lower)
  )
}

export function getStorePrice(item: GroceryItem, store: GroceryStore, packageIndex = 0): number {
  const pkg = item.packages[packageIndex]
  return pkg.prices[store] ?? pkg.prices['king-soopers'] ?? 0
}
