/**
 * Verification for the ingredient normalization graph (Phase 1: alias resolution).
 * Run with: npx tsx scripts/check-ingredient-graph.ts
 *
 * Loads the graph JSON via fs (no `@/` alias needed under tsx) and asserts the
 * worked-trace cases from the spec. Exits non-zero on any failure.
 */

import fs from 'fs'
import path from 'path'
import { buildIndices, resolveWith, type IngredientGraph } from '../src/lib/ingredient-graph'

const graph = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), 'src', 'data', 'ingredient-graph.json'), 'utf-8')
) as IngredientGraph
const indices = buildIndices(graph)

// [input, expected canonical, expected resolved]
const cases: [string, string, boolean][] = [
  // prep stripping
  ['2 cloves garlic, minced', 'garlic', true],
  ['minced garlic', 'garlic', true],
  ['finely chopped garlic', 'garlic', true],
  // product modifier preserved -> distinct node, NOT collapsed to garlic
  ['garlic powder', 'garlic powder', true],
  ['granulated garlic', 'garlic powder', true],
  // accents + rootless synonym
  ['crème fraîche', 'creme fraiche', true],
  ['crema', 'creme fraiche', true],
  // synonyms / plurals
  ['green onions', 'scallion', true],
  ['green onion, sliced', 'scallion', true],
  ['onions', 'yellow onion', true],
  ['Yellow Onion', 'yellow onion', true],
  ['eggs', 'eggs', true],
  ['free range eggs', 'eggs', true],
  ['fresh coriander', 'cilantro', true],
  ['boneless skinless chicken breast', 'chicken breast', true],
  ['chicken breasts', 'chicken breast', true],
  ['ground beef', 'ground beef', true],
  // product modifier kept -> distinct node, NOT collapsed into plain mozzarella
  // (now a real node post-backfill; the point is canonical !== "mozzarella")
  ['fresh mozzarella', 'fresh mozzarella', true],
  // unknown -> best-effort normalized, unresolved
  ['dragon fruit', 'dragon fruit', false],
]

let failed = 0
for (const [input, expectedCanonical, expectedResolved] of cases) {
  const res = resolveWith(indices, input)
  const ok = res.canonical === expectedCanonical && res.resolved === expectedResolved
  if (!ok) {
    failed++
    console.error(
      `FAIL  "${input}"\n      got    { canonical: "${res.canonical}", resolved: ${res.resolved} }` +
        `\n      expect { canonical: "${expectedCanonical}", resolved: ${expectedResolved} }`
    )
  } else {
    console.log(`ok    "${input}" -> "${res.canonical}"${res.resolved ? '' : ' (unresolved)'}`)
  }
}

console.log(`\n${cases.length - failed}/${cases.length} passed`)
if (failed > 0) process.exit(1)
