---
slug: pydantic-model-with-frontmatter-meta
name: Pydantic model paired with operation_id-pinned endpoint
language: python
applies_patterns: service-layer
applies_technologies: 
references: 
---

# When to use
Adding a request/response model + a typed FastAPI endpoint that takes it
as the body and has a stable operation_id for OpenAPI tool-name stability.

# When NOT to use
The endpoint takes only path/query params — use Query/Path types directly.

# Placeholders
- MODEL_NAME: Pydantic model class name (example: DelegationLogCreate)
- ROUTE_PATH: URL path (example: /delegations)
- HTTP_METHOD: fastapi decorator method (example: post)
- OPERATION_ID: stable op id (example: log_delegation)
- FIELDS: field block — one per line indented (example: delegate: str = Field(...)\n    capability: str = Field(..., min_length=1))

# Snippet
```python
class ${MODEL_NAME}(BaseModel):
    ${FIELDS}


@app.${HTTP_METHOD}("${ROUTE_PATH}", operation_id="${OPERATION_ID}")
def ${OPERATION_ID}(req: ${MODEL_NAME}) -> dict[str, Any]:
    # TODO: implement
    return {"action": "logged"}
```

# Example expansion
See log_delegation, upsert_anti_pattern in server/app.py.
