---
slug: fastapi-list-endpoint-with-stats
name: FastAPI list endpoint with optional stats join
language: python
applies_patterns: repository-pattern, service-layer
applies_technologies: sqlite, postgresql
references: 
---

# When to use
Adding a list endpoint to FastAPI where each entry should optionally
include aggregate stats joined from a sibling table.  The rote
uses this shape for /scripts, /design-patterns, /technologies, etc.

# When NOT to use
Pagination is cursor-based instead of offset-based (use the cursor variant).

The aggregate stats are heavy enough they warrant a separate endpoint.

# Placeholders
- RESOURCE_SINGULAR: lowercase_snake singular name of the resource (example: drone)
- RESOURCE_PLURAL: plural form for the response key (example: drones)
- ROUTE_PATH: URL path under root (example: /drones)
- PRIMARY_TABLE: main table name (example: drones)
- OPERATION_ID: stable operation id for OpenAPI (example: list_drones)

# Snippet
```python
@app.get("${ROUTE_PATH}", operation_id="${OPERATION_ID}")
def list_${RESOURCE_PLURAL}(include_stats: bool = True) -> dict[str, Any]:
    """List ${RESOURCE_PLURAL} with optional aggregate stats joined per row."""
    out = []
    with _conn() as c:
        for row in c.execute("SELECT * FROM ${PRIMARY_TABLE} ORDER BY name"):
            entry = _serialize_${RESOURCE_SINGULAR}(row)
            if include_stats:
                entry["stats"] = _${RESOURCE_SINGULAR}_stats(c, entry["id"])
            out.append(entry)
    return {"${RESOURCE_PLURAL}": out, "count": len(out)}
```

# Example expansion
See /scripts and /delegates in the live FastAPI server.
