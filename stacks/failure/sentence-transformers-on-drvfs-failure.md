---
slug: sentence-transformers-on-drvfs-failure
name: sentence-transformers + torch on Windows drvfs (FAILURE)
technologies: sentence-transformers, sqlite-vec
patterns: semantic-search-with-embeddings
context: rote initial bootstrap on ~/dev/
outcome: failure
references: scripts/seed-design-patterns-and-technologies.py - see Ollama tech entry
---

# What worked
- The libraries themselves work fine when installed on a native Linux filesystem.

# What didn't
- pip install of torch + sentence-transformers on drvfs (Windows-mounted /mnt/h/) produced zero-byte __init__.py files in 30% of attempts
- A killed install left site-packages in inconsistent state; even `rm -rf .venv` was slow enough to fail under shell timeouts
- venv resolution kept claiming success while the package was partially installed

# When to reuse
- Never reuse this combo on drvfs.  Use Ollama nomic-embed-text as the embedding backend instead — sheds the 80MB torch dep entirely.

# When to avoid
- Any pip install of large packages on drvfs filesystems.
- Move venvs to ~/.cache/ on WSL native FS; symlink under the repo so callers see the expected .venv path.
