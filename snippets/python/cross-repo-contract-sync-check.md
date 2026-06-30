---
slug: cross-repo-contract-sync-check
language: python
name: Cross-repo contract drift check
intent: Assert a versioned contract and its canonical tokens match every hand-copied mirror across sibling repos; exit 1 on drift
implements: cross-repo-contract-drift-guard
references: mz-halow-bridge/scripts/check_contract_sync.py
---

# Placeholders

| Token | Meaning | Example |
|---|---|---|
| `${VERSION_MACRO}` | the `#define` carrying the contract version | `MZ_HALOW_CONTRACT_VERSION` |
| `${CANONICAL_REL}` | path to the source-of-truth file, repo-relative | `include/mz_halow_link.h` |
| `${MIRRORS}` | list of (sibling_repo, rel_path, [required_tokens]) | see code |

# Snippet

```python
#!/usr/bin/env python3
"""Assert ${VERSION_MACRO} + canonical tokens match across sibling repos."""
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
SIBLINGS = os.path.dirname(HERE)

def read(p):
    try:
        with open(p, encoding="utf-8") as f: return f.read()
    except OSError: return None

def version(text):
    m = re.search(r"#define\s+${VERSION_MACRO}\s+(\d+)", text or "")
    return int(m.group(1)) if m else None

# (sibling_repo_dirname, rel_path, [tokens_that_must_be_present])
MIRRORS = [
    ("${SIBLING_A}", "${MIRROR_A_REL}", ['${TOKEN_1}', '${TOKEN_2}']),
    # ... add one row per mirror file ...
]

def main():
    canonical = read(os.path.join(HERE, "${CANONICAL_REL}"))
    if canonical is None:
        print("FATAL: canonical contract missing"); return 2
    cver = version(canonical)
    print(f"canonical ${VERSION_MACRO} = {cver}")
    errors, notes = [], []
    for repo, rel, tokens in MIRRORS:
        path = os.path.join(SIBLINGS, repo, rel)
        text = read(path)
        if text is None:
            notes.append(f"SKIP {repo}/{rel}: not found"); continue
        mver = version(text)
        if mver is not None and mver != cver:
            errors.append(f"{repo}/{rel}: version {mver} != {cver}")
        for tok in tokens:
            if tok not in text:
                errors.append(f"{repo}/{rel}: missing token {tok!r}")
    for n in notes: print(n)
    if errors:
        print("\nDRIFT:"); [print(" -", e) for e in errors]; return 1
    print("OK in sync"); return 0

if __name__ == "__main__":
    sys.exit(main())
```

# Notes
Absent siblings skip-with-note so the script still runs standalone in the source repo's CI. Wire into pre-commit / CI in each consumer. Bump `${VERSION_MACRO}` on any breaking change so the version assert has teeth.
