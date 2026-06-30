---
slug: optimistic-ui
name: Optimistic UI
category: offline
intent: Apply the user's change locally immediately; reconcile with the server result later
references: TanStack Query docs; React Query patterns
---

# When to use
The user is doing a confident action (typing, dragging, clicking a confirmed button) and they expect immediate feedback.

The change usually succeeds; server-side rejection is rare.

You can roll back gracefully on rejection (no destructive side effects already triggered).

# When NOT to use
The action has irreversible side effects from the user's perspective (sending money, sending a message visible to others).

The conflict rate is high — users see flickering reverts.

# Structure
Mutation fires; UI updates immediately.  Server call happens in the background.  On server success: confirm.  On server failure: roll back + surface the error.  Often paired with TanStack Query's onMutate.

# Example
```typescript
const issue = useMutation({
  mutationFn: (cmd: DroneCommand) => api.issue(droneId, cmd),
  onMutate: async (cmd) => {
    await queryClient.cancelQueries(['drone', droneId]);
    const prev = queryClient.getQueryData(['drone', droneId]);
    queryClient.setQueryData(['drone', droneId], applyOptimistically(prev, cmd));
    return { prev };
  },
  onError: (err, cmd, ctx) => queryClient.setQueryData(['drone', droneId], ctx?.prev),
  onSettled: () => queryClient.invalidateQueries(['drone', droneId]),
});
```

# Relationships
Pairs with local-first-architecture (offline = always optimistic).  Pairs with retry / outbox (if the call fails for transient reasons).
