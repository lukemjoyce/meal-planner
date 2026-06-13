/**
 * One-time backfill for the ingredient graph (Phase 1: nodes + aliases only).
 * Run with:           npx tsx scripts/backfill-ingredient-graph.ts
 * Preview without API: npx tsx scripts/backfill-ingredient-graph.ts --dry-run
 *
 * Reads the distinct ingredient names from the recipe library, asks Claude to
 * cluster them into canonical purchasable-product nodes with aliases, and merges
 * the result into src/data/ingredient-graph.json. Substitute edges are NOT
 * authored here (Phase 2) — new nodes get an empty `substitutes` array.
 *
 * Uses claude-sonnet-4-6 for quality (one-time cost). Safe to re-run: only
 * not-yet-resolvable names are sent, and merges union aliases without clobbering
 * the hand-authored seed. Saves after every chunk.
 *
 * NOTE: this makes billable Anthropic API calls. Review the diff before committing.
 */

import 'dotenv/config'
import Anthropic from '@anthropic-ai/sdk'
import fs from 'fs'
import path from 'path'
import { buildIndices, resolveWith, type IngredientGraph } from '../src/lib/ingredient-graph'

const client = new Anthropic()
const MODEL = 'claude-sonnet-4-6'
const CHUNK_SIZE = 40
const DRY_RUN = process.argv.includes('--dry-run')

const GRAPH_PATH = path.join(process.cwd(), 'src', 'data', 'ingredient-graph.json')
const LIBRARY_PATH = path.join(process.cwd(), 'src', 'data', 'recipe-library.json')

interface NodeResult {
  canonical: string
  aliases: string[]
}

function loadGraph(): IngredientGraph {
  return JSON.parse(fs.readFileSync(GRAPH_PATH, 'utf-8')) as IngredientGraph
}

function saveGraph(graph: IngredientGraph): void {
  fs.writeFileSync(GRAPH_PATH, JSON.stringify(graph, null, 2) + '\n')
}

function distinctLibraryNames(): string[] {
  const recipes = JSON.parse(fs.readFileSync(LIBRARY_PATH, 'utf-8')) as {
    ingredients: { name: string }[]
  }[]
  const names = new Set<string>()
  for (const r of recipes) for (const ing of r.ingredients) names.add(ing.name)
  return [...names].sort()
}

const NODE_TOOL: Anthropic.Tool = {
  name: 'submit_nodes',
  description: 'Submit canonical ingredient nodes with their aliases.',
  input_schema: {
    type: 'object',
    properties: {
      nodes: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            canonical: {
              type: 'string',
              description: 'lowercase canonical grocery-product name (the simple name on a shopping list)',
            },
            aliases: {
              type: 'array',
              items: { type: 'string' },
              description: 'other names/plurals/spellings recipes use for this exact product',
            },
          },
          required: ['canonical', 'aliases'],
        },
      },
    },
    required: ['nodes'],
  },
}

function buildPrompt(names: string[], existingCanonicals: string[]): string {
  return `Normalize these grocery ingredient names into canonical purchasable-product nodes.

INPUT NAMES:
${names.map((n) => `- ${n}`).join('\n')}

EXISTING CANONICAL NODES (reuse these when an input fits — map as an alias instead of making a new node):
${existingCanonicals.length ? existingCanonicals.map((c) => `- ${c}`).join('\n') : 'none'}

RULES:
- "canonical" = the simplest name you'd write on a shopping list, lowercase (e.g. "scallion", "yellow onion", "garlic").
- Group synonyms / regional names / plurals / format variants under ONE canonical: green onion = scallion = spring onion; cilantro = coriander; garbanzo beans = chickpeas.
- Product-defining modifiers make a DISTINCT node — never merge across them: "garlic powder" ≠ "garlic", "dried oregano" ≠ "oregano", "ground beef" is its own node. Different purchase = different node.
- Prep words (minced, diced, chopped) are noise — drop them from the canonical.
- "aliases" must include the original input name (unless identical to the canonical) plus other plausible names/plurals/spellings.
- EVERY input name must be recoverable: it must appear either as a "canonical" or inside some node's "aliases".
- Do NOT propose substitutes — that is handled separately.

Submit via the submit_nodes tool.`
}

async function processChunk(names: string[], existingCanonicals: string[]): Promise<NodeResult[]> {
  const message = await client.messages.create({
    model: MODEL,
    max_tokens: 8000,
    tools: [NODE_TOOL],
    tool_choice: { type: 'tool', name: NODE_TOOL.name },
    messages: [{ role: 'user', content: buildPrompt(names, existingCanonicals) }],
  })

  if (message.stop_reason === 'max_tokens') {
    throw new Error('submit_nodes truncated (hit max_tokens) — lower CHUNK_SIZE.')
  }
  const block = message.content.find((b) => b.type === 'tool_use')
  if (!block || block.type !== 'tool_use') throw new Error('No tool_use block returned.')
  const nodes = (block.input as { nodes?: NodeResult[] }).nodes ?? []
  return nodes
}

/** Union new aliases into the graph, creating nodes as needed. Returns conflicts for review. */
function mergeNodes(graph: IngredientGraph, nodes: NodeResult[]): string[] {
  const conflicts: string[] = []
  for (const { canonical, aliases } of nodes) {
    const key = canonical.trim().toLowerCase()
    if (!key) continue
    if (!graph.ingredients[key]) graph.ingredients[key] = { aliases: [], substitutes: [] }
    const set = new Set(graph.ingredients[key].aliases)
    for (const raw of aliases) {
      const alias = raw.trim()
      if (!alias || alias.toLowerCase() === key) continue
      // Flag if this alias is already a different node's canonical — needs a human call.
      if (graph.ingredients[alias.toLowerCase()] && alias.toLowerCase() !== key) {
        conflicts.push(`alias "${alias}" (under "${key}") is also a canonical node`)
        continue
      }
      set.add(alias)
    }
    graph.ingredients[key].aliases = [...set].sort()
  }
  return conflicts
}

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = []
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size))
  return out
}

async function main() {
  const graph = loadGraph()
  const allNames = distinctLibraryNames()
  let indices = buildIndices(graph)
  const uncovered = allNames.filter((n) => !resolveWith(indices, n).resolved)

  console.log(`Library distinct ingredient names: ${allNames.length}`)
  console.log(`Already resolved by graph:         ${allNames.length - uncovered.length}`)
  console.log(`To process:                        ${uncovered.length}`)
  console.log(`Existing canonical nodes:          ${Object.keys(graph.ingredients).length}\n`)

  if (uncovered.length === 0) {
    console.log('Nothing to backfill. Graph already covers every library ingredient.')
    return
  }

  const chunks = chunk(uncovered, CHUNK_SIZE)

  if (DRY_RUN) {
    console.log(`[dry-run] ${chunks.length} chunk(s) of up to ${CHUNK_SIZE}. No API calls, no writes.\n`)
    console.log('--- sample prompt (chunk 1) ---')
    console.log(buildPrompt(chunks[0].slice(0, 8), Object.keys(graph.ingredients).slice(0, 8)))
    // Exercise the merge logic on a clone with a synthetic response, prove it without writing.
    const clone = JSON.parse(JSON.stringify(graph)) as IngredientGraph
    const conflicts = mergeNodes(clone, [{ canonical: 'scallion', aliases: ['green onion', 'spring onion'] }])
    console.log('\n--- merge self-check (not saved) ---')
    console.log('scallion node after merge:', JSON.stringify(clone.ingredients['scallion']))
    console.log('conflicts:', conflicts.length ? conflicts : 'none')
    return
  }

  let processed = 0
  for (const [i, names] of chunks.entries()) {
    console.log(`Chunk ${i + 1}/${chunks.length} (${names.length} names)...`)
    try {
      const nodes = await processChunk(names, Object.keys(graph.ingredients))
      const conflicts = mergeNodes(graph, nodes)
      saveGraph(graph)
      indices = buildIndices(graph) // so later chunks see new coverage
      processed += names.length
      console.log(`  ✓ merged ${nodes.length} nodes. Graph total: ${Object.keys(graph.ingredients).length}`)
      if (conflicts.length) conflicts.forEach((c) => console.warn(`  ⚠ ${c}`))
    } catch (err) {
      console.error(`  ✗ chunk failed: ${err instanceof Error ? err.message : String(err)}`)
      console.log('  Continuing with next chunk...')
    }
    await new Promise((r) => setTimeout(r, 1000))
  }

  // Report any library names still unresolved for manual review.
  indices = buildIndices(graph)
  const stillUncovered = allNames.filter((n) => !resolveWith(indices, n).resolved)
  console.log(`\nDone. Processed ${processed} names. Graph nodes: ${Object.keys(graph.ingredients).length}`)
  if (stillUncovered.length) {
    console.log(`\n${stillUncovered.length} name(s) still unresolved — review manually:`)
    stillUncovered.forEach((n) => console.log(`  - ${n}`))
  }
}

main().catch((e) => {
  console.error('Fatal error:', e)
  process.exit(1)
})
