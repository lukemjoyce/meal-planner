# Spec & Plan: Ingredient Normalization & Substitution Graph

**Status:** Phase 1 in progress — alias resolution built (`src/lib/ingredient-graph.ts`, `src/data/ingredient-graph.json`), verified by `scripts/check-ingredient-graph.ts`, and wired into the grocery merge (`canonicalizeIngredients` in `generateGroceryList`, `src/lib/claude.ts`). Graph backfilled from the recipe library via `scripts/backfill-ingredient-graph.ts` — **248 nodes, 248/248 library ingredients resolve, no conflicts**. Substitute edges still seed-only (Phase 2); optimizer not yet built.
**Author:** generated 2026-06-12
**Feature owner:** Luke

---

## 1. Problem

Recipe combinability is limited by two kinds of friction in ingredient data:

1. **Naming inconsistency.** "chicken breast", "skinless chicken breast", and "boneless skinless chicken breast" are the same purchase, but the grocery aggregation step (`generateGroceryList` in `src/lib/claude.ts`) combines items by an LLM matching names. Inconsistent names → failed merges → two packages bought → waste, which directly undermines the app's overlap/budget value prop.

2. **No notion of substitutes.** "crème fraîche" and "sour cream" are *different* purchases, but one can stand in for the other. Without modeling that, a recipe calling for crème fraîche forces a separate single-use tub even when the week already buys sour cream. Users are more limited than they need to be in which recipes combine well.

The end goal: **let more recipes combine** by (a) reliably matching identical ingredients and (b) opportunistically substituting near-equivalent ingredients to consolidate purchases.

## 2. Goal

Build a single ingredient knowledge graph plus the logic that uses it, so that:

- **Normalization** (alias resolution) is **always applied** — clean, lossless name canonicalization so the merge step works.
- **Substitution** is **weighted and optional** — applied only when it pays for itself, never toward a target ratio.
- **Claude is kept out of the runtime.** The expensive contextual reasoning is precomputed and cached; planning-time decisions are pure graph lookup + arithmetic.

**Non-goals (for v1):**
- Dislike-driven and allergy-driven substitution. Designed-around but not built — see §8 (deferred). The graph and math are forward-compatible; only the optimizer's trigger/benefit term changes.
- Category/aisle grouping correctness (separate, lower-stakes concern — deferred by owner).
- Unit standardization across the whole library. The LLM grocery step tolerates mixed common units; this spec assumes ingredient *names* are the higher-priority lever.

## 3. Core model: one graph, two edge types

Nodes are **purchasable products** (the granularity of "what package do you buy"). Two relationship types:

- **Alias (zero distance).** Many input strings collapse to one node. "free range eggs", "large eggs", "eggs" → same node. This is normalization. Lossless, always applied.
- **Substitute (weighted, directed).** An edge between two *different* nodes with a culinary quality cost. `crème fraîche → sour cream`. Lossy, optional, context-gated.

The disambiguation test: **same purchase → alias; different purchases that can stand in → substitute edge.**

### 3.1 Node granularity & modifier taxonomy

Canonical identity is at purchasable-product granularity, not recipe-description granularity. The trap is that some modifiers are prep noise and some are product-defining:

- **Prep modifiers (strip for matching):** minced, diced, chopped, sliced, grated, etc. "minced garlic" ≡ "garlic".
- **Product-defining modifiers (keep as identity):** powder, dried, fresh, ground, smoked, roasted, etc. "garlic powder" ≠ "garlic"; "fresh oregano" ≠ "dried oregano".

So a node's identity is `(base, product-modifiers)`, with prep noise discarded. This taxonomy is finite and built once.

## 4. Directed substitute edge

An edge carries exactly three things; only one is the "weight":

```
{
  from,                // canonical node
  to,                  // canonical node
  base_quality_cost,   // Axis A weight, 0–1 (see §5)
  ratio                // amount conversion, e.g. 1 clove garlic = ~1/8 tsp garlic powder
}
```

Edges are **directed** — `sour cream → crème fraîche` need not equal the reverse. (Cost: roughly doubles edge-authoring effort. Accepted.)

**Authoring rule (critical for forward-compat):** author edges as *general culinary substitutability*, independent of whether they help consolidation. Do NOT create edges only for ingredients that appear in multiple recipes — that would leave no edge for a single-use allergen when §8 is built later. The graph is a standalone knowledge base; consolidation merely queries it.

## 5. The two cost axes

The crux of the weighting. There are **two independent axes**; the edge weight lives entirely on Axis A.

### Axis A — culinary quality cost (intrinsic, stable, cached)

`base_quality_cost` = how much worse the swap is *in the typical case*, ignoring any specific recipe. Pure taste/texture fidelity. `0` = indistinguishable, `1` = ruins the dish. No money in it. This is the stored edge weight (e.g. `garlic → garlic powder, 0.6`).

The **role multiplier** is also Axis A — it contextualizes the same culinary cost to *this* dish:

```
effective_quality_penalty = base_quality_cost × role_multiplier(recipe, ingredient)
```

- background aromatic (garlic in a 2-hour ragù) → multiplier < 1 → swap barely matters
- hero / raw (garlic in aioli) → `forbidden` flag (cleaner than a giant multiplier)

"Culinary quality only" and the formula are consistent: the formula operates *entirely within* Axis A. base = average culinary cost of the swap; role = this recipe's sensitivity; product = the culinary penalty here. Money never enters.

### Axis B — economic benefit (extrinsic, per-plan, computed live)

The consolidation payoff: does applying the sub remove a package / cut waste, given the current cart and package sizes? Measured in **dollars**, lives **nowhere on the edge** — recomputed each plan because the same swap is worth different amounts depending on what else is in the cart. Subbing onion→shallots may *create* waste (pricier, used once), so this must be computed from real package math, not assumed.

### Decision rule (consolidation mode)

```
apply sub  if   economic_benefit($)  >  λ × effective_quality_penalty
```

`λ` = the one tunable knob: how much taste the user will trade per dollar saved.

Why keep the axes separate: Axis A is stable → the static cached table (Claude builds once). Axis B is volatile but cheap arithmetic. Baking dollars onto the edge would force recomputation every plan and defeat the caching goal.

## 6. Per-recipe role annotations (the cost-structure key)

The hard part of substitution is **context** (garlic powder is fine in a braise, terrible in garlic bread), but the recipe library is static and grows slowly. So push the contextual reasoning to **import time**, batched, one-time-per-recipe: have Claude annotate each ingredient with its role in that specific dish.

```
garlic → { role: "background", importance: low }   // in a bolognese
garlic → { role: "hero", importance: high }        // in aioli
```

Store with the recipe. At planning time, substitution acceptability is pure lookup: `edge.base_quality_cost × role_multiplier(role)`. No live Claude call.

- Store role as a **category** (`hero` / `secondary` / `background`), not a raw number. Cheaper for Claude to emit, human-auditable, and category→multiplier mapping lives in config so it can be retuned globally without re-annotating recipes.
- `hero` carries a `forbidden` flag for substitution.

This is the architecture that delivers the "don't call Claude every time" goal: Claude becomes a **builder** of tables (alias map, substitution edges, role annotations), not a runtime calculator. Live planning is Claude-free graph math.

## 7. Substitution is a set-level optimization, not a recipe property

A substitution is only worth applying if it lets an ingredient merge with something already in the week's cart (or eliminates a single-use package). So subs are decided at the **set level over the chosen week**, driven by what consolidates — **never** toward a target ratio.

This dissolves the "70% of recipes end up substituted" worry: the objective is `consolidation_savings − λ × quality_penalty > 0`, so a sub is applied only when it pays for itself. If a recipe's ingredients are already optimal, zero subs. Still, add explicit guardrails as constraints:

- **Per-recipe fidelity floor:** max N subs per recipe, or total penalty per recipe under a threshold.
- **Forbidden when hero:** role = hero/raw disables the edge.
- **Drop-vs-substitute:** if making recipe X fit requires more than ~2 swaps, the optimizer should prefer *dropping X and picking a different candidate* over mangling it. Substitution competes with recipe-swapping in the same objective. (This is the "better off forgoing some recipes to keep the originals" intuition, encoded.)

The optimization is small (few candidate subs per week) → greedy or simple search, no LLM.

### 7.1 Use at selection time, not just shopping

The bigger payoff is at **recipe selection**. With the graph you can compute *effective overlap* between two recipes: they may share nothing literally, but if crème fraîche≈sour cream and shallot≈onion their effective overlap is high, making them a good pair to co-select. Feed effective overlap into candidate scoring so the planner naturally picks combinable weeks; the grocery step then realizes the subs selection already assumed.

## 8. Deferred: dislike- & allergy-driven substitution

**Not built in v1, but the design is forward-compatible — near-zero rework if two rules (below) are honored.**

The graph, ratios, role annotations, and penalty math are 100% shared. What differs is only the optimizer's **trigger and benefit term**:

| | Consolidation (v1) | Mandatory: allergy/dislike (deferred) |
|---|---|---|
| "from" ingredient | fine as-is | blocked — must move off it |
| Sub applied when | net benefit > 0 (opportunistic) | always; pick least-bad reachable node |
| Benefit term | consolidation savings ($) | + large bonus for escaping a blocked ingredient |

Two structural rules to keep the later addition purely additive:

1. **Author the graph as general culinary substitutability**, not "things that help consolidation" (so single-use allergens still have edges). — already in §4.
2. **Keep candidate-generation separate from benefit-scoring** in the optimizer. Candidates = all out-edges of an ingredient. Benefit = a pluggable term. Don't hardcode "only consider subs whose target is already in the cart" — true for consolidation, false for allergies.

The TODO then lives entirely in the optimizer's objective function (a "blocked ingredients" input + a second benefit source), never in the schema. Allergies are a *hard constraint* (questionnaire already captures `allergies`/`dislikes`), so they'd traverse the same edges but with a different, mandatory weighting.

## 9. Storage

**The graph is global reference data and does NOT touch the existing `Recipe` table.** `Recipe` (`prisma/schema.prisma:32`) is *per-user* — it's `userId`-scoped denormalized copies that `saveAiRecipe` writes when a user's plan picks a recipe (`planner.ts:107-124`). The canonical recipe library is the static `src/data/recipe-library.json`, not that table. Global data ("crème fraîche → sour cream" is true for everyone) must not live on a per-user table.

The graph's profile — global, read-heavy, write-rare, small enough to hold in memory (alias = hashmap, substitutes = adjacency list) — matches the existing static-data pattern (`grocery-data.ts`, `recipe-library.json`) more than the user-scoped Postgres tables. The hinge is **how it grows**:

- **Authored in batches** (Claude generates edges offline, like `generate-recipes.ts` builds the library) → a committed JSON/TS module loaded in memory. Simpler, faster, no per-ingredient DB round-trip at plan time.
- **Learns at runtime** (planner hits an unknown ingredient → one Claude call → persist so the cost is never paid again) → needs the DB for durable writes. Aligns with the "don't recompute with Claude every time" goal.

**Recommendation:** seed the bulk as committed JSON; add one small **global** DB cache table (no `userId`) for runtime-resolved entries later — e.g. `IngredientAlias`, `IngredientSubstitute`. Both independent of `Recipe`. Can start JSON-only and defer Postgres entirely.

### 9.1 Role annotations need no schema change

Role annotations (§6) attach to *ingredients*, and ingredients are already a JSON blob (`Recipe.ingredients` is a `String`; library JSON stores `{name, amount, unit, category}`). Adding a `role` key per ingredient is a content change, not a migration: seed it in the library JSON at import time, and it rides along for free into per-user `Recipe` copies inside the existing ingredients blob.

## 10. Open questions / not yet decided

- **JSON-only vs. JSON + runtime cache table** — decided by whether v1 wants runtime learning (§9). Leaning JSON-first.
- **λ default and tuning surface** — is it global, or exposed via the questionnaire's budget mood?
- **Edge authoring pipeline** — how Claude proposes edges (with base_quality_cost, ratio, direction) and how they're reviewed/seeded.
- **Build order:** ship **normalization (alias resolution) alone first** — it improves overlap matching immediately without touching substitution.

## 11. Decisions locked so far

- One graph, two edge types (alias + directed substitute). ✅
- Directed edges. ✅
- Weight = Axis A culinary quality only; economic benefit is Axis B, per-plan, off-edge. ✅
- Role annotations precomputed at import time, stored as categories. ✅
- Substitution applied only when it pays for itself (set-level optimization), with per-recipe and drop-vs-substitute guardrails. ✅
- Consolidation-only for v1; allergy/dislike deferred but designed-around. ✅
- Graph is **global** storage, separate from the per-user `Recipe` table; seed as committed JSON, optional global DB cache table later. Role annotations need no schema change. ✅
