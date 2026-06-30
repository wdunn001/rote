---
slug: pip-install-frozen
name: pip install with requirements.txt
family: package-mgmt
platform: cross-platform
equivalents: npm ci (node); cargo build (rust); bundle install (ruby)
references: https://pip.pypa.io/
---

# Command
```sh
pip install --no-cache-dir -r requirements.txt
```

# When to use
Install pinned Python dependencies in a venv from a requirements file.

# When NOT to use
Multi-package management with lockfile semantics — use `pip-compile` + `pip-sync`, Poetry, uv, or pdm. Reproducible installs across machines — use `requirements.txt` produced by `pip freeze` or `pip-compile` with HASH pinning.

# Gotchas
- `--no-cache-dir` is recommended inside Docker; otherwise the cache stays in the image layer wasting space.
- pip resolves the FIRST requirement and works downward; conflicting requirements may pick wrong versions silently. Use `pip check` after install.
- Don't `pip install` system-wide on managed systems (Debian PEP 668 marks them externally-managed — requires `--break-system-packages` or a venv).
- Use `python -m pip` instead of bare `pip` to avoid PATH ambiguity in scripts.

# Flags
- `--no-cache-dir`: don't write/read the cache (Dockerfile-friendly)
- `--upgrade`: upgrade already-installed packages
- `--user`: install to user site-packages (no root)
- `--no-deps`: skip dependency resolution
- `--target <dir>`: install to a specific directory
- `-c constraints.txt`: pin versions even if requirements.txt is loose

# Examples
- Dockerfile: `RUN pip install --no-cache-dir -r requirements.txt`
- Local: `python -m pip install --upgrade pip wheel && python -m pip install -r requirements.txt`
