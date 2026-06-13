/**
 * Ingredient normalization & substitution graph.
 *
 * Phase 1 (this file): alias resolution only — collapse messy raw ingredient
 * strings to a canonical node so the grocery merge step matches reliably.
 * Substitute edges are loaded and exposed but not yet used by the planner.
 *
 * See docs/ingredient-normalization-substitution-spec.md.
 *
 * The algorithm functions (`buildIndices`, `resolveWith`) are pure and take the
 * graph explicitly, so they can be exercised by a plain `tsx` script without the
 * Next bundler resolving the `@/` JSON import.
 */

import type { Ingredient } from './types'

export interface SubstituteEdge {
  to: string
  qualityCost: number // Axis-A base culinary cost, 0 (identical) .. 1 (ruins dish)
  ratio: number // amount of `to` per 1 unit of `from` (1.0 = same amount, same unit)
  fromUnit?: string
  toUnit?: string
}

export interface GraphNode {
  aliases: string[]
  substitutes: SubstituteEdge[]
}

export interface IngredientGraph {
  normalization: {
    prepModifiers: string[]
    productModifiers: string[]
    measureWords: string[]
  }
  ingredients: Record<string, GraphNode>
}

export interface GraphIndices {
  /** normalized alias/canonical text -> canonical key */
  aliasIndex: Map<string, string>
  /** canonical key -> its out-edges */
  edgeIndex: Map<string, SubstituteEdge[]>
  /** prep modifiers ∪ measure words — both are noise dropped before matching */
  stripWords: Set<string>
  productModifiers: Set<string>
}

export interface ResolutionResult {
  /** canonical node key, or a best-effort normalized form when unresolved */
  canonical: string
  /** true when the string matched a known alias/canonical node */
  resolved: boolean
}

/**
 * Canonicalize a raw ingredient string into comparable tokens-as-text:
 * lowercase, strip accents, drop parentheticals/quantities/punctuation.
 * Commas become spaces so "garlic, minced" tokenizes like "minced garlic".
 */
export function normalizeText(raw: string): string {
  return raw
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // strip diacritics: crème -> creme
    .replace(/\([^)]*\)/g, ' ') // drop parentheticals
    .replace(/[^a-z0-9\s,]/g, ' ') // drop punctuation, keep commas as separators
    .replace(/,/g, ' ')
    .replace(/\b\d+([./]\d+)?\b/g, ' ') // drop standalone quantities
    .replace(/\s+/g, ' ')
    .trim()
}

function stripPrep(normalized: string, prep: Set<string>): string {
  return normalized
    .split(' ')
    .filter((t) => t && !prep.has(t))
    .join(' ')
}

/** Conservative singularizer used only as a fallback lookup, never to mutate the key. */
function depluralize(text: string): string {
  const words = text.split(' ')
  if (words.length === 0) return text
  const last = words[words.length - 1]
  let singular = last
  if (/ies$/.test(last)) singular = last.replace(/ies$/, 'y')
  else if (/(ches|shes|ses|xes)$/.test(last)) singular = last.replace(/es$/, '')
  else if (/s$/.test(last) && !/ss$/.test(last)) singular = last.replace(/s$/, '')
  words[words.length - 1] = singular
  return words.join(' ')
}

/** Build the in-memory lookup indices from the raw graph. */
export function buildIndices(graph: IngredientGraph): GraphIndices {
  const aliasIndex = new Map<string, string>()
  const edgeIndex = new Map<string, SubstituteEdge[]>()

  for (const [canonical, node] of Object.entries(graph.ingredients)) {
    const canonKey = normalizeText(canonical)
    aliasIndex.set(canonKey, canonical) // a node resolves to itself
    for (const alias of node.aliases) {
      aliasIndex.set(normalizeText(alias), canonical)
    }
    edgeIndex.set(canonical, node.substitutes)
  }

  return {
    aliasIndex,
    edgeIndex,
    stripWords: new Set([
      ...graph.normalization.prepModifiers,
      ...graph.normalization.measureWords,
    ]),
    productModifiers: new Set(graph.normalization.productModifiers),
  }
}

/**
 * Resolve a raw ingredient string to its canonical node.
 *
 * Lookup order, most-specific first, so product-modified names (their own nodes)
 * win before prep-stripping: full normalized form → prep-stripped form →
 * depluralized fallback. A miss returns the best-effort normalized form with
 * resolved=false (the future runtime cache path handles these).
 */
export function resolveWith(indices: GraphIndices, raw: string): ResolutionResult {
  const norm = normalizeText(raw)
  const stripped = stripPrep(norm, indices.stripWords)

  const candidates = [norm, stripped, depluralize(stripped)]
  for (const c of candidates) {
    const hit = indices.aliasIndex.get(c)
    if (hit) return { canonical: hit, resolved: true }
  }
  return { canonical: stripped || norm, resolved: false }
}

// --- Convenience layer backed by the bundled JSON (used by Next app code) ---

let _indices: GraphIndices | null = null

function getIndices(): GraphIndices {
  if (_indices) return _indices
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const graph = require('@/data/ingredient-graph.json') as IngredientGraph
  _indices = buildIndices(graph)
  return _indices
}

/** Resolve a raw ingredient name to its canonical form using the bundled graph. */
export function resolveIngredient(raw: string): ResolutionResult {
  return resolveWith(getIndices(), raw)
}

/** Out-edges (possible substitutions) for a canonical node. Empty if unknown. */
export function getSubstitutes(canonical: string): SubstituteEdge[] {
  return getIndices().edgeIndex.get(canonical) ?? []
}

/**
 * Replace each ingredient's name with its canonical form so identical products
 * across recipes render identically (and merge reliably). Unresolved names are
 * left untouched — we never substitute a lossy best-effort form for the original.
 */
export function canonicalizeIngredients(ingredients: Ingredient[]): Ingredient[] {
  return ingredients.map((i) => {
    const { canonical, resolved } = resolveIngredient(i.name)
    return resolved ? { ...i, name: canonical } : i
  })
}
