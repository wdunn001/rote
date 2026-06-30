---
slug: bm25-lexical-rank
name: BM25 lexical ranker — dependency-free keyword search fallback
language: python
applies_patterns: degraded-mode-source-of-truth-sidecar
applies_technologies:
references: rote server/app_lexical.py
---

# When to use
You need keyword search/ranking but cannot ship an embedding model (locked-down env, no GPU, no network) or want a fallback when the vector backend is down. Corpus is small (dozens-to-low-thousands of rows) so a full in-Python scan per query is trivially fast.

# When NOT to use
Large corpora (10k+ docs) where you need an inverted index — use a real engine (sqlite FTS5, Tantivy, Elasticsearch). Semantic/synonym matching matters more than keyword overlap — then you genuinely need embeddings.

# Placeholders
- QUERY: the search string
- DOCS: list[str], one concatenated text blob per candidate (e.g. name + purpose + when_to_use)
- LIMIT: max results to return
- K1 / B: BM25 tuning (defaults 1.5 / 0.75 are fine)

# Snippet
```python
import math, re
from collections import Counter

_TOK_RE = re.compile(r"[a-z0-9]+")
def _tok(s): return _TOK_RE.findall((s or "").lower())

def bm25(QUERY, DOCS, LIMIT, k1=1.5, b=0.75):
    """Return [(doc_index, distance)] best-first. distance in [0,1], 0 = best,
    1.0 = no term overlap — shaped like a cosine distance so callers that
    expect 'smaller = better' work unchanged."""
    q = _tok(QUERY)
    toks = [_tok(d) for d in DOCS]
    n = len(toks) or 1
    avgdl = (sum(len(t) for t in toks) / n) or 1.0
    df = {}
    for t in toks:
        for term in set(t):
            df[term] = df.get(term, 0) + 1
    scored = []
    for i, t in enumerate(toks):
        tf = Counter(t); dl = len(t) or 1; s = 0.0
        for term in q:
            f = tf.get(term, 0)
            if not f:
                continue
            idf = math.log(1 + (n - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scored.append((i, s))
    scored.sort(key=lambda x: -x[1])
    top = scored[:LIMIT]
    maxs = top[0][1] if top and top[0][1] > 0 else 0.0
    return [(i, (1.0 - s / maxs) if maxs > 0 else 1.0) for i, s in top]
```

# Notes
- Weight name/title into the blob (and split kebab/snake to words) so identifier matches rank — `f"{name} {name.replace('-',' ').replace('_',' ')} {purpose}"`.
- df is computed over the candidate set each call (no persistent index), which is what keeps it dependency-free.
