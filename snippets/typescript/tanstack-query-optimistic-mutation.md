---
slug: tanstack-query-optimistic-mutation
name: TanStack Query mutation with optimistic UI
language: typescript
applies_patterns: optimistic-ui
applies_technologies: 
references: 
---

# When to use
Confident user actions (drag, click confirmed button) where immediate
feedback matters.  Rollback on server failure.

# When NOT to use
Irreversible side effects (sending money, posting public content).

The query is so cheap that just letting it round-trip is fine.

# Placeholders
- HOOK_NAME: name of the React hook (example: useIssueCommand)
- QUERY_KEY: the query-key tuple (example: ['drone', droneId])
- API_CALL: the API call expression (example: api.issueCommand(droneId, cmd))
- ARG_TYPE: the mutation arg type (example: DroneCommand)
- LOCAL_APPLY: function that mutates the cached value (example: applyOptimistically)

# Snippet
```typescript
export function ${HOOK_NAME}(droneId: DroneId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (cmd: ${ARG_TYPE}) => ${API_CALL},
        onMutate: async (cmd) => {
            await qc.cancelQueries({ queryKey: ${QUERY_KEY} });
            const prev = qc.getQueryData(${QUERY_KEY});
            qc.setQueryData(${QUERY_KEY}, (old: any) => ${LOCAL_APPLY}(old, cmd));
            return { prev };
        },
        onError: (_err, _cmd, ctx) => {
            if (ctx?.prev !== undefined) qc.setQueryData(${QUERY_KEY}, ctx.prev);
        },
        onSettled: () => qc.invalidateQueries({ queryKey: ${QUERY_KEY} }),
    });
}
```

# Example expansion
See useDroneCommandHub.ts and useFleetCommands.ts in apps/web.
