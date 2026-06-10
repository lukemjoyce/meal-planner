# Eval Feature Design — Meal-Plan & Grocery Quality

**Status:** Draft for review
**Author:** generated 2026-05-30 · revised 2026-05-31
**Feature owner:** Luke

---

## 1. Context

The app generates a week's meals and a grocery list via Claude, in **two separate calls**. This
document describes an **eval feature** layered on top — to measure and improve the quality of both
generated outputs, starting out-of-band and graduating to an optional live quality gate.

### Grounding in the actual codebase

This spec is written against what the app really does today (not a generic assumption):

| Aspect | Reality in this repo |
|---|---|
| Model | **Haiku** — `claude-haiku-4-5-20251001` (`RUNTIME_MODEL` in `src/lib/claude.ts`), not Sonnet |
| Meal-plan call | `generateMealPlan()` → `{ weekMeals, explanation, newRecipes[], libraryRecipeNames[] }` |
| Grocery call | `generateGroceryList()` → `GroceryListItem[]` |
| Grocery reference data | `GROCERY_DATA` in `src/lib/grocery-data.ts` — a TypeScript array (~38 items today), matched **by name** via `findGroceryItem()`; items have **no `id`** |
| Recipe library | `src/data/recipe-library.json` — **200** `LibraryRecipe` records (`id`, `tags`, `prepTime`, `estimatedCostTier`; no `cuisine`/`cookTime` fields) |
| Stack | TypeScript + Next.js (v16) server actions; Prisma + better-sqlite3. **No plain `.js` modules.** |
| Preferences | `UserPreferences` (`dietaryRestrictions`, `foodPreferences`, `groceryStore`, `weeklyBudget`, `servingsPerMeal`) — `src/lib/types.ts` |
| Orchestration | `generateAIMealPlan()` and `generateWeekGroceryList()` server actions in `src/app/actions/planner.ts` |

> **Scope decisions (2026-05-31):**
> 1. Eval covers **both** Claude calls — meal-plan generation **and** grocery-list generation.
> 2. Two tiers: **offline harness + passive live logging first**; an **inline quality gate**
>    (score → retry → fallback) lands later, **behind a feature flag**, default off.

---

## 2. Goal

Know, quantitatively, whether a change to either prompt or the model makes outputs better or worse —
before shipping it — keep a running record of how live outputs score, and (once trusted) optionally
enforce a quality floor at request time.

**Non-goals (v1):**
- No LLM-as-judge scoring in v1 — deterministic checks only (cheap, reproducible, no extra API
  spend). Subjective quality grading can come later.
- The inline gate ships **disabled by default**; turning it on is a deliberate, later step.

---

## 3. What "good" means

Two scorers, one per call. Each returns `{ score, passed, breakdown }` where `score` is the fraction
of *applicable* checks passed (checks that don't apply — e.g. budget when `weeklyBudget` is null —
are excluded from the denominator), and `passed = score >= THRESHOLD` (default `0.80`).

### 3a. Meal-plan scorer — `scoreMealPlan(plan, preferences, weekStructure)`

Scores the `generateMealPlan()` output against the request.

| Check | Definition |
|---|---|
| `coversStructure` | Every requested day×meal in `weekStructure` (minus `daysOff`) has a planned meal |
| `recipesResolvable` | Each `libraryRecipeNames` entry exists in `recipe-library.json`; each `newRecipes` entry has name + ≥1 ingredient + instructions |
| `respectsRestrictions` | No selected recipe violates `preferences.dietaryRestrictions` (reuse `filterLibraryByDiet` logic for library picks; tag/ingredient scan for new recipes) |
| `preferLibrary` | Share of picks drawn from the library vs newly invented (the prompt instructs "prefer library"; low reuse is a quality signal, not a hard fail) |
| `hasExplanation` | `explanation` is non-empty (the strategy summary the UI shows) |

### 3b. Grocery scorer — `scoreGroceryList(list, recipes, preferences)`

Scores the `generateGroceryList()` output (`GroceryListItem[]`).

| Check | Definition |
|---|---|
| `coversAllIngredients` | Every ingredient across the planned recipes appears in the list (fuzzy match, `findGroceryItem` logic) |
| `pricingConsistent` | `totalCost ≈ packagesNeeded × pricePerPackage` per item (±1¢) |
| `withinBudget` | `Σ totalCost ≤ preferences.weeklyBudget` (skipped when null) |
| `knownItems` | Each item resolves via `findGroceryItem()` against `GROCERY_DATA` |
| `priceRealistic` | Each `pricePerPackage` within a tolerance band of the known `GROCERY_DATA` price for that item+store (when matchable) |
| `saneQuantities` | `packagesNeeded` a positive integer `≤ 20`; `totalAmountNeeded > 0` |
| `respectsRestrictions` | No item conflicts with `preferences.dietaryRestrictions` (e.g. no meat/seafood categories when vegetarian/vegan) |

A combined run score is the mean of the two scorers when both calls are evaluated together.

> **Note on allergens:** the original draft checked `constraints.allergens`, but the app has **no
> structured allergy field yet** — allergies live in free-text notes. `respectsRestrictions` uses
> the existing `dietaryRestrictions`. A true allergen check lands once the questionnaire's structured
> `allergies` field exists (`meal-questionnaire-spec.md`, open Q 10.1) — tracked as a follow-up.

---

## 4. Architecture

```
              ┌──────────────────── live user flow ────────────────────┐
generateAIMealPlan()      → generateMealPlan()      [Haiku] ─┐
generateWeekGroceryList() → generateGroceryList()   [Haiku] ─┤
                                                             ├─(fire-and-forget)─► scoreX() ─► EvalLog
                                                             │   (passive; never blocks the response)
                                                             │
                                  ┌── if FEATURE_EVAL_GATE on (later phase, default OFF) ──┐
                                  │  score < threshold → retry w/ constrained prompt        │
                                  │  still failing      → fall back (library recipe / safe   │
                                  │                        grocery rebuild) before returning │
                                  └──────────────────────────────────────────────────────────┘

              ┌──────────────────── offline harness (pre-ship) ────────────────────┐
npm run eval → for each scenario: generateMealPlan()+generateGroceryList()
             → scoreMealPlan()+scoreGroceryList() → per-check pass rates + avg score
```

One scoring function per call (`scoreMealPlan`, `scoreGroceryList`), shared by the offline harness,
the passive logger, and (later) the inline gate — so the three paths can never drift.

---

## 5. Files to create

All TypeScript, colocated with the app's conventions:

```
src/lib/eval/
  score.ts        ← scoreMealPlan(...) and scoreGroceryList(...) → EvalResult  (shared, pure)
  scenarios.ts    ← ~20–50 fixed scenarios (preferences + weekStructure, drawing on real library)
  log.ts          ← writeEvalLog(entry)  (see §7)
  gate.ts         ← inline gate orchestration (Phase 4); reads FEATURE_EVAL_GATE
scripts/
  run-evals.ts    ← offline harness; `tsx scripts/run-evals.ts`
```

Add npm script `"eval": "tsx scripts/run-evals.ts"` (repo already uses `tsx`, e.g.
`scripts/generate-recipes.ts`). Scorers are **pure** (no I/O/auth) → unit-testable and reusable
across all three paths.

---

## 6. Offline harness (`scripts/run-evals.ts`)

```ts
// pseudocode — real impl is TS against the actual generators
import { scenarios } from '@/lib/eval/scenarios'
import { generateMealPlan, generateGroceryList } from '@/lib/claude'
import { scoreMealPlan, scoreGroceryList } from '@/lib/eval/score'

const PROMPT_VERSION = 'v1'
for (const s of scenarios) {
  const plan = await generateMealPlan({ preferences: s.preferences, savedRecipes: [], weekStructure: s.weekStructure })
  const planScore = scoreMealPlan(plan, s.preferences, s.weekStructure)

  // resolve plan → recipes, then build the grocery list (mirrors the real action)
  const list = await generateGroceryList({ weekMeals: plan.weekMeals, recipes: s.resolvedRecipes, preferences: s.preferences, servingsPerMeal: s.preferences.servingsPerMeal })
  const listScore = scoreGroceryList(list, s.resolvedRecipes, s.preferences)
  // collect both scores + breakdowns
}
// print: avg meal-plan score, avg grocery score, and per-check pass rates across scenarios
```

Calls the **real** `generateMealPlan` / `generateGroceryList` (Haiku, real prompts) — no
`callSonnet` reimplementation, so we evaluate the code we actually ship. Run before any
prompt/model change and compare versions.

---

## 7. Logging

Reuse the app's Prisma/SQLite stack (not an ad-hoc JSON file). New model:

```prisma
model EvalLog {
  id            String   @id @default(cuid())
  createdAt     DateTime @default(now())
  source        String                 // "live" | "offline"
  target        String                 // "mealplan" | "grocery"
  promptVersion String
  model         String                 // RUNTIME_MODEL at run time
  userId        String?                // live runs
  scenarioId    String?                // offline runs
  score         Float
  passed        Boolean
  breakdown     String                 // JSON: per-check booleans
  latencyMs     Int?
  wasRetry      Boolean  @default(false)  // set by the inline gate (Phase 4)
  wasFallback   Boolean  @default(false)
  notes         String?
}
```

(SQLite has no JSON/array type — `breakdown` is a JSON string, matching the existing
`meals`/`ingredients`/`foodPreferences` convention.)

- **Live (passive):** after each generator returns in `generateAIMealPlan()` /
  `generateWeekGroceryList()`, score and write an `EvalLog` **without awaiting** on the user's
  response path — eval failures must never affect the user. `source = "live"`.
- **Offline:** the harness writes one `EvalLog` per scenario per target with `source = "offline"`.

Optional later: a gated `/eval` admin page charting score-over-time and per-check pass rates.

---

## 8. Inline quality gate (later phase, feature-flagged)

Behind `FEATURE_EVAL_GATE` (env flag, **default off**). When enabled, the live actions score the
output before returning and, on failure, try to repair it:

- **Meal plan:** on low score, retry once with a constrained prompt (emphasize library-only
  selection + restriction adherence); if still failing, substitute the weakest picks with
  diet-compatible library recipes (`filterLibraryByDiet`).
- **Grocery list:** on low score, retry once instructing Claude to use only `GROCERY_DATA` item
  names; if still failing, deterministically rebuild from `GROCERY_DATA` + `getStorePrice()` for the
  unmatched items.

Every gate action logs `wasRetry` / `wasFallback`. This adds latency and possibly a second Claude
call **only when the flag is on** — which is why it ships dark and is enabled deliberately after the
passive logs show the gate would help more than it hurts.

---

## 9. Phased plan

- **Phase 1 — Scoring core + offline harness.** `score.ts` (both scorers), `scenarios.ts`,
  `run-evals.ts`, `npm run eval`. Baseline avg scores for `v1`. No app-flow changes.
- **Phase 2 — Passive live logging.** `EvalLog` model + migration; fire-and-forget scoring in both
  server actions. Accumulate real-world scores.
- **Phase 3 — Visibility.** Minimal gated admin view of score trends / per-check pass rates.
- **Phase 4 — Inline gate (flagged).** `gate.ts` + `FEATURE_EVAL_GATE`; retry/fallback for both
  calls, default off; enable once logs justify it.
- **Phase 5 — Follow-ups.** Allergen check once structured `allergies` exists
  (`meal-questionnaire-spec.md`); optional LLM-as-judge for subjective quality.

---

## 10. Resolved decisions (2026-05-31)

1. **Scope:** ✅ Both Claude calls — meal-plan **and** grocery-list eval.
2. **Runtime:** ✅ Both tiers — offline harness + passive logging now; inline gate later **behind a
   feature flag** (`FEATURE_EVAL_GATE`, default off). Live path unchanged until the flag is on.
3. **Scoring method:** ✅ Deterministic checks only for v1; LLM-as-judge a later option.
4. **Implementation:** ✅ TypeScript against the real generators (Haiku), not a standalone JS
   reimplementation. Logging via existing Prisma/SQLite.

## 11. Open questions

1. **Price tolerance band** for `priceRealistic` — what ± range counts as "realistic" given static
   `GROCERY_DATA`? (Suggest ±25% to start.)
2. **`knownItems` strictness** — hard fail vs warn? Today's small `GROCERY_DATA` (~38 items) will
   false-flag until it grows; may warrant a softer weight initially.
3. **Pass threshold / hard fails** — keep `0.80`, or make safety checks (`respectsRestrictions`) a
   hard fail regardless of overall score?
4. **Gate aggressiveness** — one retry then fallback (as drafted), or more retries before giving up?
