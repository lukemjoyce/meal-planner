# Meal Planner — Roadmap & Status

**Updated:** 2026-06-04

Running status of features and the agreed build order. Detailed designs live in the per-feature
specs in this folder; this file is the index + outstanding work.

---

## Shipped

### Guided meal questionnaire — Phase 1 (`meal-questionnaire-spec.md`)
Replaced the planner's free-text "notes" box with a one-question-at-a-time stepper.
- `MealPreferences` type + option lists in `src/lib/types.ts`.
- `src/components/planner/meal-questionnaire.tsx` — 5-step wizard (allergies → diet → tastes →
  effort/budget → review), checkboxes/segmented controls + "Other" fields, progress bar, review step,
  "save to profile" checkbox.
- Wired into `planner-client.tsx` (week structure → questionnaire); structured answers threaded
  through `generateAIMealPlan` → `generateMealPlan`, allergies rendered as HARD prompt exclusions.

### UI refresh (green theme + fonts)
- Three-green palette (vivid `#00e855` brand / deep emerald primary / mint neutrals) as oklch tokens
  in `globals.css`, applied 60-30-10. Custom `text-gradient-brand` / `bg-gradient-brand` utilities.
- Fonts wired via `next/font`: Plus Jakarta Sans (headings) + Inter (body) + Geist Mono.
- Refreshed nav, landing, questionnaire, planner surfaces to semantic tokens (dark-mode safe).

### Claude structured output (`src/lib/claude.ts`)
- Both calls use **forced tool use** (`tool_choice`) → SDK returns parsed JSON; eliminated the
  malformed-JSON parse errors. Deleted the old `parseJsonSafely` text-scraping.
- Prompt caching (`cache_control: ephemeral`) on stable prefixes (recipe library; grocery
  instructions); volatile data (store, prefs, week) kept after the breakpoint.

### Profile → grocery-store sync banner
- `GroceryList.store` snapshots the store at generation; compared to the current profile store.
- Shared `src/components/profile-update-banner.tsx` on planner + grocery pages: "store changed —
  update?" Updating from either page regenerates the one shared grocery list (both tabs revalidated),
  so they stay in sync.
- `updateProfile` revalidates `/grocery-list` too (fixes the old header/price mismatch).

---

## Outstanding / next up

Agreed sequencing: **questionnaire defines the `MealPreferences` contract the eval scores against**,
so questionnaire work precedes the eval, then remaining phases run eval-guarded.

1. **Questionnaire Phase 2 — profile sync.** Pre-fill steps from saved `dietaryRestrictions` /
   `foodPreferences`; add a dedicated `allergies` field (vs. folding into dietary restrictions —
   open Q in the spec); migrate legacy comma-separated profile strings to structured arrays.

2. **Diet/allergy staleness prompt (follow-up to the store banner).** Changing diet/allergies in
   Profile can leave a stale plan with an allergen — a real safety gap. Unlike the store change, this
   needs a **full meal-plan regen**, not the cheap grocery refresh. The retained `User.prefsUpdatedAt`
   column already exists to drive this; build a "your meal plan may not match your new dietary
   settings — regenerate?" prompt that re-runs `generateAIMealPlan`.

3. **Servings-per-meal change handling.** Deferred: servings are baked into each planned meal, so a
   change needs a full plan regen (currently manual via "New Plan"). Decide whether to surface a
   prompt or leave manual.

4. **Eval feature (`eval-feature-design.md`).** Phase 1 (scoring core + offline harness) → Phase 2
   (passive logging) → Phase 3 (admin view) → Phase 4 (inline gate behind `FEATURE_EVAL_GATE`) →
   Phase 5 (allergen check — unblocked once questionnaire Phase 2 lands the structured `allergies`).

5. **Questionnaire Phase 3 — polish.** Animations, partial-progress persistence, etc.

6. **Pantry carryover (`pantry-carryover-spec.md`).** Leftover-aware grocery planning. Most isolated;
   nothing else depends on it.

7. **"My Recipes" default servings (separate spec, TBD).** Recipes default to 4 servings, adjustable
   per-recipe. User explicitly deferred to its own spec.

---

## Known gotcha (for whoever implements next)

The app runs against the **root `dev.db`** (`src/lib/db.ts` → `process.cwd()/dev.db`), but
`prisma.config.ts` resolves `file:./dev.db` relative to `prisma/` (the empty `prisma/dev.db`). A
normal `prisma migrate` edits the wrong file and the app then 500s with "no such column." To add a
column: edit `schema.prisma`, `ALTER TABLE` the root `dev.db` directly (one-off `better-sqlite3`
script), then `prisma generate` (schema-only) for types. After regenerating, **restart the dev
server** (it caches the client on `globalThis.prisma` + Turbopack caches `.next/dev`) — clear
`.next` if a stale-client error persists.
