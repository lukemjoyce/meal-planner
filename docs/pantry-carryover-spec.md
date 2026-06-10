# Spec & Plan: Pantry Carryover (Leftover-Aware Grocery Planning)

**Status:** Draft for review
**Author:** generated 2026-05-30
**Feature owner:** Luke

---

## 1. Problem

Today the app plans each week in isolation. The grocery list already *computes* waste — it knows that buying a 16 oz sour cream to cover a 12 oz need leaves 4 oz behind — but that 4 oz vanishes the moment the week ends. Next week the planner buys another full container, ignoring what's already in the fridge.

This defeats the app's core promise (minimize waste). A user who runs the app two weeks in a row should see the second week's list *shrink* because it accounts for what's still good.

## 2. Goal

Before generating week N+1's grocery list, subtract the ingredients the user still has from previous weeks, so they only buy the shortfall. Show them clearly what they're reusing and what it saved.

**Non-goals (for v1):**
- Barcode scanning / receipt import.
- Tracking exact quantities of every spice grain. Staples are tracked as "have it / don't," not by amount.
- Real-time fridge sensors or expiry photo recognition.

## 3. Core concepts

### 3.1 Pantry inventory
A per-user list of ingredients currently on hand. Each item has a quantity, a unit, an acquisition date, and a computed expiry date. Items have a lifecycle: `active → consumed | discarded | expired`.

Two ways items enter the pantry:
1. **Automatically** — when a grocery list is generated, leftover from package rounding (`packageSize × packagesNeeded − amountNeeded`) becomes a pantry item.
2. **Manually** — the user tells the app "I already have a dozen eggs and a bag of rice" so the planner doesn't double-buy.

### 3.2 Shelf life
Each ingredient has an estimated fridge/pantry/freezer life. Acquisition date + shelf life = expiry date. On carryover we only count items whose expiry is on or after the new shopping day. This is the safety mechanism: we never suggest reusing 3-week-old cilantro.

A new static table (`src/lib/shelf-life.ts`), parallel to the existing `grocery-data.ts`, holds this. Examples:

| Ingredient | Storage | Days fresh | Staple? |
|---|---|---|---|
| cilantro | fridge | 7 | no |
| sour cream (opened) | fridge | 14 | no |
| chicken breast | fridge | 2 | no |
| shredded cheese (opened) | fridge | 21 | no |
| eggs | fridge | 28 | no |
| canned beans | pantry | 730 | yes |
| rice | pantry | 730 | yes |
| olive oil | pantry | 365 | yes |
| ground cumin / chili powder | pantry | 365 | yes (spice) |

Items not in the table get a conservative default (7 days, perishable) so we err toward *not* assuming the user still has them.

### 3.3 Staples vs perishables
**Staples** (oil, soy sauce, spices, flour, rice) are bought once and used in tiny amounts over months. Tracking exact remaining quantity is hopeless and not worth it. Instead we track them as a boolean: once bought, they're "in the pantry" with a long expiry, and the planner simply skips them on future lists until they'd realistically run out. The app already assumes the user has basic salt/pepper; this extends that to the specific staples they've actually purchased.

**Perishables** (produce, dairy, meat) are tracked by quantity + expiry, because that's where the real waste-avoidance lives.

## 4. How it changes the flow

```
Week N:
  generate meal plan
  generate grocery list ──► compute leftovers ──► write PantryItems (expiry = today + shelfLife)

Week N+1:
  generate meal plan        (optionally biased toward expiring items — see §8)
  load active pantry items
  filter to "still good on shopping day"
  generate grocery list WITH pantry context:
     Claude subtracts pantry amounts, lists only the shortfall
  ──► recompute leftovers ──► update PantryItems (decrement consumed, add new)
```

## 5. Data model

New Prisma model (SQLite — JSON-as-string convention matches the rest of the schema):

```prisma
model PantryItem {
  id           String   @id @default(cuid())
  userId       String
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  name         String                       // normalized ingredient name
  quantity     Float
  unit         String
  category     String
  isStaple     Boolean  @default(false)
  source       String                       // "leftover:2026-06-01" | "manual" | "staple"
  acquiredDate String                       // ISO date
  expiryDate   String?                      // ISO date; null = effectively non-perishable
  status       String   @default("active")  // active | consumed | discarded | expired
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt

  @@index([userId, status])
}
```

Add `pantryItems PantryItem[]` to `User`, plus a `trackPantry Boolean @default(true)` preference so users can opt out.

## 6. Claude integration changes

`generateGroceryList()` gains a `pantryInventory` argument. The prompt instructs Claude to:
- treat the inventory as already-owned,
- subtract available amounts from each recipe need,
- output only the shortfall (or mark an item fully covered),
- reason about fuzzy unit matches (e.g. pantry has "4 oz sour cream", recipe needs "0.5 cup") — Claude handles common conversions well; a small helper covers the obvious ones (oz↔cup, tbsp↔cup) as a backstop.

Each grocery item gains two fields:

```jsonc
{
  "name": "sour cream",
  "totalAmountNeeded": 12,
  "fromPantry": 4,            // drawn from existing inventory
  "toBuy": 8,                 // shortfall actually purchased
  "pantryCovered": false,     // true when fromPantry >= totalAmountNeeded (skip purchase)
  ...
}
```

**Prompt caching note:** the system prompt, shelf-life table, and store-pricing data are stable across requests and should sit in the cached prefix; the per-request pantry inventory is volatile and goes *after* the last cache breakpoint. This keeps the cache hot while still injecting fresh inventory each week. (Relevant once we add caching — see the model/cost notes; Haiku stays the runtime model.)

## 7. Reconciliation — the hard part

The app *predicts* leftovers, but real life differs (they ate the leftovers as a snack, or the cilantro wilted early). Three options:

| Approach | Friction | Accuracy | Verdict |
|---|---|---|---|
| **Optimistic auto-track** — assume predicted leftovers are real; let users correct in a Pantry view | low | good | **Recommended** |
| **End-of-week confirmation** — prompt "what's left?" every week | high | high | too much friction for this app's vibe |
| **No tracking, manual only** — user maintains pantry by hand | medium | depends | fallback / opt-out |

**Recommendation: optimistic hybrid.** Auto-create predicted leftovers, surface them in a one-tap-editable Pantry view, and lean on conservative expiry windows so stale guesses self-correct (an item nobody touched simply expires and drops out). This matches the low-friction ethos of the rest of the app.

## 8. Synergy: bias meal planning toward expiring items (Phase 3)

Because the meal planner *also* runs through Claude, we can feed the "expiring soon" list into `generateMealPlan()` and ask it to prefer recipes that use those items up. This closes the loop: instead of just *subtracting* leftover cilantro from the list, the app actively plans a meal that finishes it. This is the highest-value follow-on and is called out as its own phase.

## 9. UI changes

- **New "Pantry" tab.** Three groups: *Expiring soon* (≤3 days), *Fresh*, *Staples*. Each item: name, qty, expiry, and one-tap **Used it** / **Threw it out**. A **+ Add item** button for manual entry ("I already have…").
- **Grocery list page.** New "From your pantry" callout showing reused items, dollars saved, and waste avoided. Items fully covered by pantry render struck-through with a "have it" badge instead of a price.
- **Profile.** A "Track pantry & leftovers" toggle (the `trackPantry` preference).
- **First-run nudge.** "Add what you already have so we don't double-buy it."

## 10. Edge cases & decisions

1. **Unit mismatch** — lean on Claude for fuzzy reconciliation; small deterministic helper for oz/cup/tbsp as backstop. Log mismatches Claude couldn't resolve.
2. **Duplicate leftovers of the same ingredient** — merge into one pantry row, keep the *earliest* expiry (FIFO; consume oldest first).
3. **Lapsed users** — if someone skips 3 weeks, perishables auto-expire (a lightweight check on load flips `active → expired` when `expiryDate < today`). We never suggest reusing expired food.
4. **Conservative bias** — unknown ingredients default to a short 7-day perishable window so we under-claim rather than over-claim what's on hand.
5. **Opt-out** — `trackPantry = false` skips all of this and preserves today's behavior exactly.

## 11. Phased plan

**Phase 1 — Carryover MVP (the core value)**
- `PantryItem` model + migration; `trackPantry` preference.
- `shelf-life.ts` static table.
- Capture package-waste leftovers automatically after grocery generation; write PantryItems with computed expiry.
- Auto-expire stale items on load.
- `generateGroceryList()` accepts pantry inventory; prompt + output schema updated (`fromPantry` / `toBuy` / `pantryCovered`).
- Grocery list UI shows "from your pantry" + adjusted totals.
- Staples tracked as boolean.

**Phase 2 — Pantry management UI**
- Pantry tab (view / edit qty / mark used / discard / manual add).
- Profile toggle.

**Phase 3 — Use-it-up meal planning**
- Feed expiring items into `generateMealPlan()`; bias recipe selection to consume them.
- Expiring-soon nudges.

**Phase 4 — Accuracy polish**
- Better unit conversion.
- Optional: learn from user corrections (if they consistently discard cilantro, shorten its assumed life).

## 12. Resolved decisions (2026-05-30)

1. **Reconciliation:** ✅ Optimistic auto-track + one-tap-editable Pantry view (§7). No recurring end-of-week survey.
2. **Tracking scope:** ✅ Phase 1 tracks **both** perishables (by quantity + expiry) and a boolean staples pantry.
3. **Meal-planning bias (§8):** ✅ In scope soon — pull "use-it-up" forward. Phase 1 ships the grocery-list subtraction; meal-plan biasing follows immediately as Phase 2 (promoted ahead of the standalone Pantry UI).
4. **Instacart tie-in:** Assumed yes — when Instacart lands, "to buy" quantities feed the cart and "from pantry" items are excluded. Tracked as a dependency on the existing Instacart TODO in `grocery-data.ts`.

### Revised phase order (reflecting decision 3)

- **Phase 1 — Carryover MVP:** `PantryItem` model + migration, `trackPantry` preference, `shelf-life.ts` (with staple flags), auto-capture package-waste leftovers, auto-expire on load, staples-as-boolean, `generateGroceryList()` pantry-aware (`fromPantry`/`toBuy`/`pantryCovered`), grocery UI "from your pantry".
- **Phase 2 — Use-it-up meal planning:** feed expiring items into `generateMealPlan()`; bias recipe selection to consume them; expiring-soon surfacing.
- **Phase 3 — Pantry management UI:** dedicated Pantry tab (edit qty / used / discard / manual add), profile toggle.
- **Phase 4 — Accuracy polish:** unit conversion, learn-from-corrections.
