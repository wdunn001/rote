#!/usr/bin/env python3
"""
script: import-scripts.py
purpose: Bulk-import existing scripts from a directory tree into the Script
         Library.  Discovers candidates, dedups by file-hash, infers
         frontmatter via the local-llm delegate (Ollama on
         edge-host), categorizes by purpose, copies into scripts/ with
         family + environment + tags, writes an audit report.
family: import-scripts
environment: cross-python
inputs:
    --root <path>           tree to scan (repeat for multiple trees)
    --library <path>        target rote root (default /path/to/rote)
    --dry-run               report what would be imported; do not write
    --skip-llm              use naive frontmatter (no Ollama dispatch)
    --auto-accept           import every match without prompting
    --max-files <n>         safety cap on imports per run (default 200)
    --max-bytes <n>         per-file size limit in bytes (default 50000)
    --since-mtime <unix>    only import files modified after this unix-ts
    --tag-prefix <text>     prepend this string to every generated tag
    --report <path>         write JSON audit report (default ./import-report.json)
outputs:
    stdout: per-script accept/skip line + summary
    file: ./import-report.json  (or --report <path>)
    exit 0 success, 3 max-files exceeded, 4 ollama unreachable, 5 bad args
touches-secrets: no — refuses to ingest files that look like they contain
                 secret values (heuristic: lines matching PASSWORD=/SECRET=/
                 API_KEY=/PRIVATE.*KEY surrounded by data); reports them
                 to the audit instead of importing
when-to-use:    fresh-library setup with a body of existing scripts; periodic
                sweep of a development tree for new ad-hoc scripts that
                deserve promotion
when-NOT-to-use: incremental promotion of one script — use `rote new`
                 + paste the body directly; this script is for BULK.
added: 2026-06-03
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


# Extensions the rote indexer understands.
SUPPORTED_EXTS: dict[str, str] = {
    ".sh":   "posix-bash",
    ".bash": "posix-bash",
    ".zsh":  "posix-zsh",
    ".fish": "posix-fish",
    ".ps1":  "windows-pwsh",
    ".cmd":  "windows-cmd",
    ".bat":  "windows-cmd",
    ".py":   "cross-python",
    ".js":   "cross-node",
    ".mjs":  "cross-node",
    ".ts":   "cross-node",
    ".rb":   "cross-ruby",
}

# Directory names we never descend into.  Aggressive: training-data Python
# stdlib, vendored libraries, build artifacts, SDK toolchains, package
# managers, container runtimes — none of these contain user-authored
# utility scripts worth indexing.
DIR_BLOCKLIST: set[str] = {
    # VCS
    ".git", ".svn", ".hg",
    # Node ecosystem
    "node_modules", "bower_components", ".next", ".nuxt", ".turbo",
    # Python venvs + caches + stdlib + package internals
    ".venv", "venv", "env", "envs", "__pycache__",
    ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    "site-packages", "dist-packages", "lib2to3",
    "pip-tmp", "pip-temp",
    # Generic build / dist
    "dist", "build", "out", "target", "bin/Debug", "bin/Release",
    "obj/Debug", "obj/Release",
    # Java / JVM
    ".gradle", ".mvn",
    # iOS / Android SDK
    "Pods", "DerivedData",
    "sdks", "android-sdk", "android-ndk", "ndk", "toolchains", "prebuilt",
    "platform-tools", "build-tools", "system-images", "emulator",
    # Container / VM
    "containers", "Docker", ".docker",
    # OS / Microsoft junk
    "windows", "Windows", "Program Files", "Program Files (x86)",
    "ProgramData", "$Recycle.Bin", "AppData", "WindowsApps",
    "MicrosoftEdgeBackups", "Microsoft", "Mozilla",
    # Cloud sync / backup
    "OneDrive", "Dropbox", "Google Drive", "iCloudDrive",
    # Editor / IDE state
    ".idea", ".vscode", ".vs", ".vscode-server",
    # Archives / cache trees
    "_archive", "archive", "_old", "old", "backup", "backups",
    # Library compile outputs
    "Release", "Debug",  # cmake / msbuild output
}

# File patterns we skip even with a supported extension.
FILE_BLOCKLIST_PATTERNS: list[re.Pattern] = [
    re.compile(r"\.bak\.\d+"),
    re.compile(r"\.bak$"),
    re.compile(r"\.orig$"),
    re.compile(r"\.lock$"),
    re.compile(r"^tests?/"),  # don't slurp test fixtures; too project-specific
    re.compile(r"_test\."),
    # venv / pip internals — these get installed system-wide and aren't
    # user-authored scripts worth indexing.
    re.compile(r"/(?:activate|deactivate)(?:\.\w+)?$"),
    re.compile(r"/activate_this\.py$"),
    re.compile(r"/(?:pip|pip3|pip3\.\d+)$"),
    re.compile(r"/(?:python|python3|python3\.\d+)$"),
    re.compile(r"/(?:pydoc|pydoc3)\.bat$"),
    re.compile(r"/(?:f2py|wheel|easy_install|normalizer|isympy|tqdm|dotenv|proton)(?:\.\w+)?$"),
    re.compile(r"/(?:idle|idle3|smtpd|venv|virtualenv).*"),
    # Compiled / generated files
    re.compile(r"\.min\.js$"),
    re.compile(r"\.bundle\.js$"),
    re.compile(r"\.d\.ts$"),
    re.compile(r"\.generated\."),
    re.compile(r"\.pb\.(?:py|js|ts)$"),  # protobuf-generated
]

# If any of these files appear NEXT TO a candidate, treat the containing
# directory as 'not a place for user scripts' (it's a venv / SDK / package
# install).  We bail on the entire subtree, not just the file.
VENV_SENTINELS: set[str] = {
    "pyvenv.cfg",          # python venv
    "pip-selfcheck.json",  # pip's marker
    "INSTALLER",           # site-packages distinfo marker
    ".package.json",       # node package
    "AndroidManifest.xml", # android module
    "source.properties",   # android sdk component
    "NOTICE",              # often inside vendored libs (heuristic)
}


def looks_like_venv_or_sdk(dirpath: str) -> bool:
    """Heuristic: a directory containing pyvenv.cfg / source.properties /
    Pods etc. is a managed install tree — don't recurse."""
    try:
        entries = set(os.listdir(dirpath))
    except OSError:
        return False
    return bool(entries & VENV_SENTINELS)

# Heuristic: if a file's body contains any of these patterns AND a long
# value next to it, refuse to import it — likely contains a secret.
SECRET_BODY_RE = re.compile(
    r"(?im)^\s*(?:export\s+)?[A-Z][A-Z0-9_]*(PASSWORD|SECRET|TOKEN|API_KEY|"
    r"PRIVATE_KEY|CLIENT_SECRET|BEARER|ACCESS_KEY)\s*=\s*['\"]?[^'\"\s]{8,}"
)

OLLAMA_DEFAULT_URL = "http://edge-host:11434"
OLLAMA_MODEL = "qwen2.5:latest"

# Categorization candidates we suggest the LLM pick from.  These become
# `tags:` in the imported frontmatter so the GUI's tag filter works.
CATEGORY_HINTS = [
    "disk-cleanup", "git-ops", "docker-ops", "deploy", "build", "test-runner",
    "network-probe", "ssh-helper", "backup", "secrets-helper", "dev-env",
    "data-processing", "log-skim", "container-ops", "system-admin",
    "ci-cd", "release", "misc",
]


def fingerprint(text: str) -> str:
    """Stable content fingerprint for dedup.  SHA-256 of normalized text."""
    norm = text.encode("utf-8", "ignore")
    return hashlib.sha256(norm).hexdigest()[:16]


def already_indexed_fingerprints(library: Path) -> set[str]:
    """Hash every script already in library/scripts/ so we don't re-import
    something we already have under a different name."""
    out: set[str] = set()
    scripts_dir = library / "scripts"
    if not scripts_dir.is_dir():
        return out
    for p in scripts_dir.iterdir():
        if not p.is_file() or p.suffix not in SUPPORTED_EXTS:
            continue
        try:
            out.add(fingerprint(p.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    return out


def discover(roots: list[Path], max_bytes: int, since_mtime: int | None) -> list[Path]:
    """Walk roots, return candidate paths.  Caller filters further."""
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            print(f"[discover] skip missing root: {root}", file=sys.stderr)
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            # Don't descend into venvs / SDK trees / package installs
            if looks_like_venv_or_sdk(dirpath):
                dirnames.clear()
                continue
            # Prune blocklisted dirs in-place (faster than per-file rejection)
            dirnames[:] = [
                d for d in dirnames
                if d not in DIR_BLOCKLIST and not d.startswith(".")
            ]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix not in SUPPORTED_EXTS:
                    continue
                relative = str(p)
                if any(pat.search(relative) for pat in FILE_BLOCKLIST_PATTERNS):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size > max_bytes:
                    continue
                if st.st_size < 50:  # too tiny to be meaningful
                    continue
                if since_mtime is not None and st.st_mtime < since_mtime:
                    continue
                out.append(p)
    return out


def has_frontmatter(body: str) -> bool:
    """Cheap check: existing library-style frontmatter."""
    head = body[:2000]
    return any(
        marker in head
        for marker in ("# purpose:", "# script:", "family:", "environment:", "@purpose:")
    )


def looks_like_secret_file(body: str) -> bool:
    return bool(SECRET_BODY_RE.search(body))


def naive_frontmatter(path: Path, body: str) -> dict[str, str]:
    """Frontmatter we can infer without an LLM."""
    ext = path.suffix
    stem = path.stem
    name = path.name
    head = body[:1000]
    purpose = ""
    # Best-effort one-line summary from a leading comment block.
    for line in head.splitlines()[:20]:
        line = line.strip().lstrip("#").lstrip("//").strip()
        if 10 <= len(line) <= 200 and not line.startswith(("=", "-", "*", "!")):
            purpose = line
            break
    return {
        "purpose": purpose or f"Imported {name}",
        "family": stem.lower().replace("_", "-"),
        "environment": SUPPORTED_EXTS[ext],
        "tags": "imported, misc",
        "touches_secrets": "false",
        "when_to_use": "see source comments",
        "when_not_to_use": "unknown — review before relying",
    }


def ollama_infer(body: str, path: Path, url: str) -> dict[str, str]:
    """Ask local-llm to infer rich frontmatter for one script.
    Returns a dict matching the keys naive_frontmatter produces.  On any
    failure (ollama down, parse error), falls back to naive."""
    prompt = (
        "You are categorizing a shell script for a library.  Given the "
        "script body below, output a JSON object with these keys:\n"
        "  - purpose: a single sentence under 120 chars describing what "
        "the script does\n"
        "  - family: a kebab-case slug 2-5 words representing the logical "
        "operation (e.g. 'docker-prune', 'git-branch-sweep', "
        "'disk-cache-clear')\n"
        "  - tags: comma-separated list of 1-3 tags from this list: "
        + ", ".join(CATEGORY_HINTS) + "\n"
        "  - when_to_use: under 200 chars, when this is the right tool\n"
        "  - when_not_to_use: under 200 chars, when reaching for it is "
        "the wrong call\n"
        "  - touches_secrets: 'true' if the script reads/writes secret "
        "values; otherwise 'false'\n"
        "Output ONLY the JSON object — no preamble, no markdown fence.\n"
        "\nFILENAME: " + path.name + "\n"
        "BODY (truncated to 4 KB):\n"
        + body[:4096]
    )
    req_body = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 400},
    }).encode()
    try:
        req = urllib.request.Request(
            f"{url}/api/chat",
            data=req_body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.load(r)
        text = resp.get("message", {}).get("content", "").strip()
        # Trim code-fence wrappers if Ollama added them despite instructions.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to grab the first {...} block
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
            else:
                raise
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as exc:
        print(f"  [ollama-fallback] {path.name}: {exc}", file=sys.stderr)
        return naive_frontmatter(path, body)

    fm = naive_frontmatter(path, body)
    # Overwrite the fields the LLM gave us if they look reasonable.
    for key in ("purpose", "family", "tags", "when_to_use", "when_not_to_use", "touches_secrets"):
        if key in data and isinstance(data[key], str) and data[key].strip():
            fm[key] = data[key].strip()
    return fm


def build_frontmatter_block(meta: dict[str, str], comment: str, src_path: Path) -> str:
    """Render the parsed metadata into a rote frontmatter block
    appropriate for the script's comment syntax."""
    today = time.strftime("%Y-%m-%d")
    lines = [
        f"{comment} =============================================================================",
        f"{comment} script: {src_path.name}",
        f"{comment} purpose: {meta['purpose']}",
        f"{comment} family: {meta['family']}",
        f"{comment} environment: {meta['environment']}",
        f"{comment} tags: {meta['tags']}",
        f"{comment} when-to-use: {meta['when_to_use']}",
        f"{comment} when-NOT-to-use: {meta['when_not_to_use']}",
        f"{comment} touches-secrets: {meta['touches_secrets']}",
        f"{comment} imported-from: {src_path}",
        f"{comment} added: {today}",
        f"{comment} =============================================================================",
        "",
    ]
    return "\n".join(lines)


def comment_token(language: str) -> str:
    """Return the comment-line prefix to use when building the frontmatter
    for this language."""
    if language.startswith("cross-node"):
        return "//"
    return "#"


def insert_frontmatter(body: str, frontmatter: str) -> str:
    """Insert frontmatter into the script.  Preserve shebang if present."""
    lines = body.splitlines(keepends=True)
    if lines and lines[0].startswith("#!"):
        return lines[0] + frontmatter + "".join(lines[1:])
    return frontmatter + body


def write_imported(library: Path, src: Path, fm: dict[str, str], body: str, dry_run: bool) -> Path:
    """Compute target path + write (or pretend to)."""
    target_name = src.name
    target_path = library / "scripts" / target_name
    # If target exists, suffix with a short hash.
    if target_path.exists():
        h = fingerprint(body)[:6]
        target_path = library / "scripts" / f"{src.stem}-{h}{src.suffix}"
    if dry_run:
        return target_path
    comment = comment_token(fm["environment"])
    if not has_frontmatter(body):
        body = insert_frontmatter(body, build_frontmatter_block(fm, comment, src))
    target_path.write_text(body, encoding="utf-8")
    target_path.chmod(0o755)
    return target_path


def confirm(prompt: str) -> bool:
    try:
        answer = input(f"{prompt} [y/N/q] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if answer == "q":
        sys.exit(0)
    return answer == "y"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=[], help="repeat for multiple trees")
    ap.add_argument("--library", default="/path/to/rote")
    ap.add_argument("--ollama", default=OLLAMA_DEFAULT_URL)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-llm", action="store_true")
    ap.add_argument("--auto-accept", action="store_true")
    ap.add_argument("--max-files", type=int, default=200)
    ap.add_argument("--max-bytes", type=int, default=50_000)
    ap.add_argument("--since-mtime", type=int, default=None)
    ap.add_argument("--tag-prefix", default="")
    ap.add_argument("--report", default="import-report.json")
    args = ap.parse_args()

    if not args.root:
        print("ERROR: --root required (repeat for multiple trees)", file=sys.stderr)
        return 5

    library = Path(args.library)
    roots = [Path(r) for r in args.root]
    print(f"[import] roots: {roots}", file=sys.stderr)
    print(f"[import] library: {library}", file=sys.stderr)

    if not args.skip_llm:
        try:
            urllib.request.urlopen(f"{args.ollama}/api/tags", timeout=5).read()
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"[import] ollama not reachable at {args.ollama}: {exc}", file=sys.stderr)
            print("[import] use --skip-llm to proceed with naive frontmatter only", file=sys.stderr)
            return 4

    existing = already_indexed_fingerprints(library)
    print(f"[import] {len(existing)} scripts already in library — dedup baseline ready", file=sys.stderr)

    candidates = discover(roots, args.max_bytes, args.since_mtime)
    print(f"[import] {len(candidates)} candidates after extension/size filter", file=sys.stderr)
    if len(candidates) > args.max_files * 3:
        print(f"[import] {len(candidates)} > 3*max-files = {args.max_files * 3}; "
              "narrow your --root or raise --max-files", file=sys.stderr)
        return 3

    imported: list[dict] = []
    skipped: list[dict] = []
    rejected_secret: list[dict] = []
    rejected_dup: list[dict] = []
    bail_at = args.max_files

    for path in candidates:
        if len(imported) >= bail_at:
            print(f"[import] hit --max-files={bail_at}; stopping", file=sys.stderr)
            break
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            skipped.append({"path": str(path), "reason": f"read failed: {exc}"})
            continue

        fp = fingerprint(body)
        if fp in existing:
            rejected_dup.append({"path": str(path), "fingerprint": fp})
            continue
        if looks_like_secret_file(body):
            rejected_secret.append({"path": str(path)})
            continue

        if args.skip_llm:
            fm = naive_frontmatter(path, body)
        else:
            fm = ollama_infer(body, path, args.ollama)
        if args.tag_prefix:
            fm["tags"] = f"{args.tag_prefix}, " + fm["tags"]

        summary = f"  {path}  →  family={fm['family']}  tags=[{fm['tags']}]  purpose={fm['purpose'][:60]}"
        print(summary)

        if not args.auto_accept and not args.dry_run:
            if not confirm(f"  accept {path.name}?"):
                skipped.append({"path": str(path), "reason": "user declined"})
                continue

        target = write_imported(library, path, fm, body, args.dry_run)
        imported.append({
            "source": str(path), "target": str(target),
            "family": fm["family"], "environment": fm["environment"],
            "tags": fm["tags"], "purpose": fm["purpose"],
            "fingerprint": fp,
        })
        existing.add(fp)

    report = {
        "ts_unix": int(time.time()),
        "library": str(library),
        "roots": [str(r) for r in roots],
        "imported": imported,
        "skipped": skipped,
        "rejected_secret": rejected_secret,
        "rejected_duplicate": rejected_dup,
        "category_distribution": dict(Counter(
            tag.strip()
            for e in imported
            for tag in e["tags"].split(",")
        )),
        "dry_run": args.dry_run,
    }
    Path(args.report).write_text(json.dumps(report, indent=2))

    print(f"\n=== Import summary ===")
    print(f"  imported:  {len(imported)}")
    print(f"  duplicate: {len(rejected_dup)}")
    print(f"  secret-rejected: {len(rejected_secret)}")
    print(f"  user-skipped: {len(skipped)}")
    print(f"  report: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
