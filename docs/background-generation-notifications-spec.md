# Spec: Non-blocking background generation + nav notifications

**Status:** Proposed (not started) · **Drafted:** 2026-06-11 · **Effort:** Medium (~8–12 files)

## Summary
Make AI meal-plan and grocery-list generation **non-blocking**. Instead of a full-screen
overlay that traps the user on the page, generation runs in the background (indicated by a
thin loading bar under the navbar). The user can navigate freely while it runs. When a job
finishes and the user is **not** on that job's page, show a **green notification dot** next to
that page's nav item and play a short **notification sound**.

### Target UX (the scenario)
1. User clicks **Generate** on the Grocery List page → a loading bar appears under the navbar (page stays interactive).
2. User navigates to **My Recipes** to browse while groceries generate.
3. Generation finishes → a **green dot** appears next to **"Grocery List"** in the nav + a notification sound plays.
4. User clicks **Grocery List** → the new list is shown and the dot clears.

## Why this is non-trivial (the core constraint)
Today, generation runs in the **page component** via `useTransition` (`planner-client.tsx`,
`grocery-list-client.tsx`). The pending/result state is local to that component. **When the user
navigates away, the component unmounts and the in-flight result is lost** — the server action may
finish server-side, but there's no mounted client component to receive it.

Also, each authed route has its **own** `layout.tsx` (`planner/`, `grocery-list/`, `recipes/`,
`profile/`), each rendering `<Nav>`. So the nav **remounts on every navigation** and there is no
persistent place to hold cross-page state.

➡️ The fix requires lifting generation state into something that **persists across navigation**.

## Design

### 1. Consolidate authed routes into an `(app)` route group
Create `src/app/(app)/layout.tsx` and move `planner/`, `grocery-list/`, `recipes/`, `profile/`
under `src/app/(app)/`. Route groups don't change URLs. A **shared layout stays mounted across
navigation between its pages** (App Router behavior) — this is what makes persistence possible.
The 4 existing per-route layouts are near-identical (auth check + `<Nav>`); merge into one and
delete the others. (Mirror of the existing `(public)` route group.)

### 2. `GenerationProvider` (React context) — `src/components/generation-provider.tsx`
Mounted in `(app)/layout.tsx` so it persists. Responsibilities:
- Track per-job state: `{ planner: Status, grocery: Status }` where `Status = 'idle' | 'running' | 'done-unseen'`.
- Expose `start(job, action)` — **the provider invokes the server action itself** (so its promise
  resolves regardless of which page is mounted), sets `running`, then on resolve:
  - if the user is currently on that job's page → mark `idle` + `router.refresh()`.
  - else → mark `done-unseen` (drives the nav dot) + play the sound.
- Expose `markSeen(job)` — called when the user lands on a job's page, clears the dot + refreshes.
- Expose status for the nav + loading bar to read.

Hook: `useGeneration()`.

### 3. Refactor the trigger sites
- `planner-client.tsx`: replace local `useTransition`/`isPending` + blocking overlay with
  `useGeneration().start('planner', generateAIMealPlan(...))`. Remove the `LoaderCircle` full-screen overlay added earlier.
- `grocery-list-client.tsx`: same with `'grocery'` + `generateWeekGroceryList`.
- On completion the provider triggers `router.refresh()`; pages read fresh data via their server components as today.

### 4. Under-nav loading bar
A thin, full-width progress/indeterminate strip rendered in `(app)/layout.tsx` (or top of `<Nav>`),
visible when any job is `running`. Non-modal (does not block clicks). Solid `bg-primary`.

### 5. Nav green dots — `src/components/nav.tsx`
Read `useGeneration()`. Show a small green dot next to **Planner** / **Grocery List** when that job
is `done-unseen`. Clicking the link (or arriving on the page) calls `markSeen(job)` to clear it.

### 6. Notification sound
Add a short sound to `public/` (e.g. `public/notify.mp3`). Provider plays it via `new Audio()` on a
background completion. Note: browser autoplay policies require a prior user gesture — the "Generate"
click satisfies this in practice, but test across browsers.

## Implementation order (checkpoint-able)
1. `(app)` route group + shared layout + `GenerationProvider` scaffolding → verify nothing breaks.
2. Under-nav loading bar + move triggers into the provider (non-blocking) → verify generation still works.
3. Nav green dots + `markSeen` clearing.
4. Notification sound.

Doing it in this order means a working non-blocking version exists after step 2, before the polish.

## Caveats / non-goals
- **Survives in-app (client-side) navigation only — NOT a hard refresh or closed tab.** The provider
  state is in memory. True refresh-proof durability needs **server-side job tracking + polling** (a
  job row + status endpoint), which is a much larger effort and explicitly out of scope for v1.
- Async/notification UX is **fiddly to verify** (timing, navigation, sound can't be checked headlessly) — budget extra iteration.
- Audio autoplay may be blocked in some browsers without a recent gesture.

## Future enhancement: refresh-proof durability
Persist jobs server-side (a `GenerationJob` table: id, userId, type, status, result ref, timestamps).
Provider polls (or uses SSE) for in-flight jobs on mount, so a refresh/tab-reopen still shows progress
and completion. Enables multi-device and resilience. Significantly larger; revisit if the in-memory
v1 proves valuable.
