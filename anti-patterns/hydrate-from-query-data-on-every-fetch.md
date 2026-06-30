---
slug: hydrate-from-query-data-on-every-fetch
title: useEffect hydration from React-Query data clobbers in-flight user input
category: react
cost: ~30 min to diagnose; user-input-loss bug visible to operators as "form keeps resetting itself"
---

# Symptom

An edit form / drawer / modal pulls its initial values from a React Query (or SWR / TanStack) cache.  A "hydrate from server" `useEffect` watches the query data and copies fields into `useState` for local editing.  Periodically the form fields snap back to server values, wiping in-progress user input.  Often shows up as "every N seconds my input resets."

# Root cause

The hydrate effect's dep array includes the query data reference.  React Query returns a fresh object reference on every fetch (JSON-deserialized responses are by definition new objects), so any background refetch — even a same-content one — triggers the effect.

Common amplifier: a sibling mutation that runs on a debounce, invalidates the same query on success, refetches, hydrates, **changes some derived dep** (e.g. a stringified waypoints signature), restarts the debounce.  Infinite loop with no user input.

# Remedy

Hydrate ONCE per identifying key (e.g. `planId`), not on every data change.  Use a ref to track which key has already been hydrated:

```tsx
const hydratedIdRef = useRef<string | null>(null);

useEffect(() => {
  const row = query.data;
  if (!row) return;
  if (hydratedIdRef.current === row.id) return;  // <-- key guard
  hydratedIdRef.current = row.id;
  setName(row.name);
  setDescription(row.description);
  // ...
}, [query.data, /* setters */]);

// Reset the guard when the form closes so reopening reloads fresh state.
useEffect(() => {
  if (!open) hydratedIdRef.current = null;
}, [open]);
```

The form's local state becomes the source of truth during the edit session; explicit "discard and refetch" or "save" actions are the only state-mutation pathways.

# Trade-off you accept

A concurrent edit from another operator no longer reflects live in this drawer.  Usually fine — most edit drawers aren't multi-user-realtime.  Close + reopen the drawer to pull a fresh snapshot.  If you genuinely need collaborative edit, use yjs / Liveblocks; don't simulate it with refetch hydration.

# Diagnosis hints

- Check if a mutation onSuccess invalidates the same query that hydrates the form.
- Check if the hydrate effect's deps include the query data reference (vs an id).
- Strip the mutation's `invalidateQueries` and see if the loop stops — if yes, the loop runs through the mutation; if no, something else is shifting deps.

# Related

- React Query docs: "Important Defaults" — `staleTime: 0` + auto-refetch-on-window-focus is a common amplifier.
- [[react-derived-state-anti-pattern]] — broader version.

# Real-world hit

Shipped fix on `example-app` 2026-06-04 commit `4b27daa0`, `apps/web/src/pages/flight-plans/FlightPlanDetailPanel.tsx`.  Preflight mutation invalidated `["flight-plans"]` → query refetched → hydrate effect overwrote all form fields → `setWaypoints` reshape made `waypointsSig` (JSON stringified) a fresh string → debounced preflight effect's deps changed → another preflight → loop.  Reset every 2.6 s, killed operator input.
