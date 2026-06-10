# Guided Meal Questionnaire — Feature Spec

**Status:** Draft for review
**Author:** generated 2026-05-30
**Feature owner:** Luke

---

## 1. Overview

Replace the single free-text **"Any notes for Claude?"** textarea in the planner's "Configure Your
Week" card with a friendly, one-question-at-a-time questionnaire that walks the user through the
decisions that actually shape a good meal plan. Each step asks one focused question using the input
type best suited to it — checkboxes for common allergies, a dropdown for diet style, steppers for
counts — and always offers an **"Other"** free-text escape hatch so nothing is lost. The collected
answers are normalized into a structured object and woven into the meal-plan prompt, replacing the
lossy free-text `additionalNotes` field.

## 2. Problem

The planner already collects the *structured* parts of a week — days, meals, and days-off — as
checkboxes (`planner-client.tsx`). But everything about **taste and constraints** is either:

- buried in a single optional `notes` textarea ("e.g. Make it easy this week, prefer Asian
  flavors…"), which gets passed to Claude verbatim as `additionalNotes`, or
- set once on the **Profile** page and easy to forget about at planning time.

This has three problems:

- **Blank-page paralysis.** The notes box gives no hint about what matters (allergies, cooking
  time, cuisines, budget mood this week), so users either over- or under-specify.
- **Allergies aren't first-class.** The profile models *dietary restrictions* (`nut-free`,
  `dairy-free`, `gluten-free`, etc. — see `DIETARY_RESTRICTIONS` in `types.ts`) but has no
  dedicated, granular allergy capture (peanuts vs tree nuts, shellfish, eggs, soy, sesame). A
  user typing "allergic to shellfish" into the free-text notes is relying on the model not to
  miss it — that's a safety gap, not just a quality one.
- **Per-week intent is lost.** Profile preferences are permanent; the notes box is the only place
  to express "this week I want quick dinners on a tight budget," and it does so unstructured.

## 3. Goals

- Guide the user through the questions that matter **one at a time**, low-friction.
- Use the **right control per question**: checkboxes for multi-select (allergies, cuisines),
  dropdown/radio for single-select (diet style, budget mood), steppers for counts.
- Always pair fixed options with an **"Other" free-text field** for specifics.
- Treat **allergies as hard exclusions** in the prompt, visibly distinct from soft preferences.
- Produce a **structured `MealPreferences` object** that augments the existing
  `generateAIMealPlan` config and replaces the free-text `additionalNotes`.
- **Pre-fill** from the user's saved profile (`dietaryRestrictions`, `foodPreferences`) and offer
  to save new answers back, so returning users mostly confirm-and-continue.
- Let users **skip** non-essential questions and **go back** to change earlier answers.

## 4. Non-Goals

- A full conversational/chatbot interface — this is a fixed, finite wizard, not open dialogue.
- Replacing the Profile page — the questionnaire reads from and writes to the same fields.
- Changing the day/meal/days-off selectors, which already work well as checkboxes.
- Per-meal customization (e.g. "no fish on Fridays") — out of scope.
- Nutrition/calorie tracking beyond passing a stated preference to the model.

## 5. Questionnaire Flow

The questionnaire is a stepper that opens when the user starts a new plan. One question per screen,
with progress ("Step 3 of 6"), a **Back** button, a **Skip** link on optional steps, and **Next**
(or **Generate my plan** on the last step). The existing day / meal / days-off selectors become the
first steps (reusing today's checkboxes); the taste/constraint questions follow.

| # | Question | Control | Options (examples) | Other field |
|---|----------|---------|--------------------|-------------|
| 1 | Which days are you planning, and which meals? | Checkboxes (existing) | Mon–Sun · breakfast/lunch/dinner · days off | — |
| 2 | Any allergies or intolerances? | Checkboxes | Peanuts, Tree nuts, Dairy, Eggs, Gluten, Soy, Shellfish, Fish, Sesame | "Other allergies" text |
| 3 | Do you follow a particular diet? | Dropdown / radio | None, Vegetarian, Vegan, Pescatarian, Keto, Paleo, Low-carb, Halal, Kosher | "Other diet" text |
| 4 | Foods you'd rather avoid, and cuisines you love? | Tag chips + checkboxes | Avoid: free chips · Cuisines: Italian, Mexican, Indian, Thai, Japanese, Mediterranean, American, Chinese | inline / "Other cuisines" |
| 5 | How much effort this week? | Radio | Quick (<30 min), Balanced, I want to cook · Budget: Tight / Moderate / Flexible | — |
| 6 | Anything else we should know? | Textarea | — | (final catch-all — replaces today's notes box) |

Steps 2–5 are skippable; step 1 is required (same validation as today: at least one active day and
one meal). The allergy step gets a brief reassurance line ("We'll keep these out of every recipe")
to signal it's a hard constraint, not a preference.

### Behavior

1. On open, each step pre-fills from the saved profile: `dietaryRestrictions` maps onto the diet
   and allergy steps; `foodPreferences.likes` seeds cuisines, `foodPreferences.dislikes` seeds
   "avoid." Returning users mostly confirm and hit Next.
2. Selecting checkboxes/radios does **not** auto-advance — the user reviews and clicks Next, so
   multi-select works naturally.
3. "Other" text fields only enable when relevant; their contents are split and merged into the
   matching list on submit.
4. A final review (or a summary rail) shows all answers with "Edit" links that jump back to any
   step, then **Generate my plan**.
5. On finish, answers normalize into `MealPreferences`; a **"Save these to my profile"** checkbox
   (on the final step) writes the durable parts back via the existing `updateProfile` action.

## 6. Data Model

### `MealPreferences` (new shared type — `src/lib/types.ts`)

```ts
export interface MealPreferences {
  allergies: string[];        // fixed options + parsed "Other" — HARD exclusions
  diet: string | null;        // single choice, or custom from "Other"
  dislikes: string[];         // soft "avoid" list
  cuisines: string[];         // soft preference
  effort: "quick" | "balanced" | "cook" | null;
  budgetMood: "tight" | "moderate" | "flexible" | null;
  notes: string;              // step 6 catch-all (replaces additionalNotes)
}
```

### Storage — reuse existing fields, no migration required

The app already persists preferences on `User` as JSON strings (`schema.prisma`):

- `dietaryRestrictions: String` — JSON array; today driven by the `DIETARY_RESTRICTIONS` list.
- `foodPreferences: String` — JSON of `{ likes: string[], dislikes: string[] }`.
- `groceryStore`, `weeklyBudget`, `servingsPerMeal` — already structured.

Mapping the questionnaire onto these:

- **Allergies** → extend `dietaryRestrictions` with explicit allergen entries (e.g. `peanut`,
  `shellfish`, `egg`, `soy`, `sesame`) **or** introduce a dedicated `allergies` JSON field. A
  dedicated field is cleaner (allergies are exclusions, not diet styles) and is the recommended
  path — it's a one-line additive Prisma column (`allergies String @default("[]")`), backward
  compatible with existing rows. *(Open question 10.1.)*
- **Diet** → maps to a `dietaryRestrictions` value (Vegetarian/Vegan/Keto/etc. already exist).
- **Cuisines / dislikes** → `foodPreferences.likes` / `foodPreferences.dislikes` (today's
  comma-separated profile inputs become structured chips).
- **effort / budgetMood / notes** → per-week, **not** persisted to the profile; they ride along
  in the generate request only (notes replaces `additionalNotes`).

This keeps the questionnaire and the Profile page reading/writing the same data — fill it in
either place. Legacy comma-separated profile strings parse cleanly into the chip lists on read.

## 7. Claude Integration

`generateAIMealPlan` (`actions/planner.ts`) gains the `MealPreferences` object alongside the
existing `{ days, meals, daysOff }` config. `generateMealPlan` (`lib/claude.ts`) renders each field
into a clearly labeled prompt section:

- **Allergies** become emphatic hard exclusions: *"NEVER include these ingredients or their
  derivatives: …"* — distinct from the existing soft "Dietary restrictions" line.
- Diet, cuisines, dislikes, effort, and budget mood become soft guidance.
- `notes` is appended verbatim where `additionalNotes` is today (claude.ts line ~83).

The JSON output contract (`GeneratedMealPlan`) is unchanged — only the prompt input grows. Runtime
model stays Haiku (`RUNTIME_MODEL`).

## 8. UI Changes

- New `MealQuestionnaire` stepper component replaces the `notes` textarea block in
  `planner-client.tsx` (lines ~170–182) and absorbs the existing day/meal/days-off selectors as
  step 1.
- Reuses primitives already in `src/components/ui`: `checkbox`, `select`, `label`, `button`,
  `card`, `textarea`, `separator`, `badge` (selected chips). A small progress indicator can be
  built from existing styles (or `tabs`).
- Mobile-first: one question fills the card; **Back / Next** pinned at the bottom; matches the
  existing stone-palette styling.
- Final review step with per-step "Edit" jumps and the "Save to my profile" checkbox.
- Per **AGENTS.md**, this Next.js is customized — check `node_modules/next/dist/docs/` before
  writing component/route code rather than assuming familiar APIs.

## 9. Accessibility

- Each step is a labeled `fieldset`/`legend`; checkboxes and radios are keyboard-navigable.
- Progress announced via `aria-live`; focus moves to the question heading on each step change.
- The allergy step is always reachable and clearly labeled — never hidden behind "advanced."

## 10. Open Questions

1. **Allergies storage:** dedicated `allergies` Prisma column (recommended) vs. folding allergens
   into `dietaryRestrictions`?
2. **Entry point:** is the questionnaire the only path, or do power users get a "skip to free text"
   shortcut straight to step 6?
3. **Partial progress:** persist answers if the user navigates away mid-questionnaire?
4. **Conflict reconciliation:** when questionnaire answers differ from the saved profile —
   overwrite, merge, or ask?
5. **Diet ⇒ allergy implication:** should choosing Vegan auto-exclude dairy/eggs, or stay
   independent?

## 11. Rollout

- **Phase — UI foundation & component toolkit (do alongside Phase 1).** Settle the component
  toolkit and stand up the stepper's visual shell *before* wiring data into it. **Recommendation:
  stay on shadcn/ui** — it's already the app's toolkit (`shadcn` dep + ~16 components in
  `src/components/ui/*`, Tailwind v4, stone palette), so new questionnaire screens inherit the
  existing look for free and "refactoring in" means *adding* components, not migrating a design
  system. The stepper needs two primitives not yet in the repo — add them with
  `npx shadcn@latest add radio-group progress` (Q3/Q5 use radio groups; progress shows "Step 3 of
  6"). Everything else it needs (`checkbox`, `select`, `label`, `button`, `card`, `textarea`,
  `separator`, `badge`) is already present — see §8. **Avoid adding DaisyUI here:** it's a Tailwind
  plugin with its own class-based components, so it would run as a *second* design system beside
  shadcn — more to learn, visual drift between old and new pages, and possible class/theme clashes
  with the Tailwind v4 setup. Deliverable: a clickable empty stepper (Back / Next / progress, no
  data yet) you can eyeball before Phase 1 fills it in. Per **AGENTS.md**, check
  `node_modules/next/dist/docs/` before writing route/component code — this Next.js is customized.
- **Phase 1 — Structured replacement.** Add `MealPreferences` type; build the stepper wrapping the
  existing selectors + allergy/diet/cuisine/effort/notes steps; map answers into the existing
  prompt (allergies as hard exclusions). Replaces the free-text notes box.
- **Phase 2 — Profile sync.** Pre-fill from `dietaryRestrictions` / `foodPreferences`; add the
  dedicated `allergies` field + "Save to my profile"; migrate legacy comma-separated strings.
- **Phase 3 — Polish.** Final review step, budget/effort questions, progress animation, and
  partial-progress persistence.
