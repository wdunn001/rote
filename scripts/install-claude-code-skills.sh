#!/usr/bin/env bash
# =============================================================================
# script: install-claude-code-skills.sh
# purpose: Install the four Claude Code skills + memory entry from this repo
#          into the per-user Claude Code config directory.  Idempotent;
#          re-runs replace prior copies (or refresh symlinks).
# inputs:
#   --mode <copy|symlink>   default copy.  Use symlink if you want edits in
#                           ~/.claude/skills/ to flow back to the repo for
#                           commit (maintainer workflow).
#   --skills <name,name>    comma-separated subset; default: all four
#                           (chronicle, rote, secret-handling,
#                            local-delegate)
#   --memory-project-dir <slug>
#                           Project memory dir name in
#                           ~/.claude/projects/<slug>/memory/.  Default:
#                           "-home-user-dev" (matches the user's working dir
#                           encoding Claude Code uses).
#   --no-memory             skip installing the memory entry
#   --no-backup             skip the .bak.<timestamp> copy on existing files
#   --dry-run               show what would be installed without writing
# outputs:
#   stdout: per-skill INSTALLED / SYMLINKED / SKIPPED / FAILED + summary
#   exit 0 success, 4 source file(s) missing, 5 bad args, 6 partial install
# touches-secrets: no
# when-to-use:    fresh machine setup; after pulling new SKILL.md changes;
#                 first time configuring Claude Code on this user's account
# when-NOT-to-use: if you have heavily customized your skills out-of-band —
#                  use --dry-run first to see what would be replaced
# added: 2026-06-03
# family: install-claude-code-skills
# environment: posix-bash
# =============================================================================
set -uo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
SRC_SKILLS_DIR="$REPO/claude-code-skills"
TARGET_SKILLS_DIR="$HOME/.claude/skills"
MEMORY_PROJECT_DIR="-home-user-dev"
MODE="copy"
SKILLS_CSV="chronicle,rote,secret-handling,local-delegate,design-patterns"
DO_MEMORY=1
DO_BACKUP=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)                MODE="$2"; shift 2 ;;
        --skills)              SKILLS_CSV="$2"; shift 2 ;;
        --memory-project-dir)  MEMORY_PROJECT_DIR="$2"; shift 2 ;;
        --no-memory)           DO_MEMORY=0; shift ;;
        --no-backup)           DO_BACKUP=0; shift ;;
        --dry-run)             DRY_RUN=1; shift ;;
        -h|--help)             sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ "$MODE" == "copy" || "$MODE" == "symlink" ]] \
    || { echo "--mode must be copy or symlink" >&2; exit 5; }

[[ -d "$SRC_SKILLS_DIR" ]] \
    || { echo "source skills dir missing: $SRC_SKILLS_DIR" >&2; exit 4; }

IFS=',' read -ra SKILLS <<< "$SKILLS_CSV"

INSTALLED=0
FAILED=0

install_one() {
    local skill="$1"
    local src="$SRC_SKILLS_DIR/$skill/SKILL.md"
    local dst_dir="$TARGET_SKILLS_DIR/$skill"
    local dst="$dst_dir/SKILL.md"

    if [[ ! -f "$src" ]]; then
        echo "[$skill] SOURCE MISSING: $src"
        FAILED=$((FAILED + 1))
        return
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[$skill] dry-run: would $MODE $src → $dst"
        return
    fi

    mkdir -p "$dst_dir"

    if [[ -e "$dst" || -L "$dst" ]]; then
        if [[ "$DO_BACKUP" -eq 1 && -f "$dst" && ! -L "$dst" ]]; then
            cp "$dst" "${dst}.bak.$(date +%Y%m%d-%H%M%S)"
        fi
        rm -f "$dst"
    fi

    if [[ "$MODE" == "symlink" ]]; then
        ln -s "$src" "$dst"
        echo "[$skill] SYMLINKED $dst → $src"
    else
        cp "$src" "$dst"
        echo "[$skill] INSTALLED $dst"
    fi
    INSTALLED=$((INSTALLED + 1))
}

for s in "${SKILLS[@]}"; do
    install_one "$s"
done

# Memory entry + index line
if [[ "$DO_MEMORY" -eq 1 ]]; then
    MEM_SRC="$SRC_SKILLS_DIR/memory/arch-rote-context-system.md"
    MEM_DIR="$HOME/.claude/projects/$MEMORY_PROJECT_DIR/memory"
    MEM_DST="$MEM_DIR/arch-rote-context-system.md"
    MEM_IDX="$MEM_DIR/MEMORY.md"

    if [[ ! -f "$MEM_SRC" ]]; then
        echo "[memory] SOURCE MISSING: $MEM_SRC"
        FAILED=$((FAILED + 1))
    elif [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[memory] dry-run: would $MODE $MEM_SRC → $MEM_DST"
        echo "[memory] dry-run: would ensure index line in $MEM_IDX"
    else
        mkdir -p "$MEM_DIR"
        if [[ -e "$MEM_DST" || -L "$MEM_DST" ]]; then
            [[ "$DO_BACKUP" -eq 1 && -f "$MEM_DST" && ! -L "$MEM_DST" ]] && \
                cp "$MEM_DST" "${MEM_DST}.bak.$(date +%Y%m%d-%H%M%S)"
            rm -f "$MEM_DST"
        fi
        if [[ "$MODE" == "symlink" ]]; then
            ln -s "$MEM_SRC" "$MEM_DST"
            echo "[memory] SYMLINKED $MEM_DST"
        else
            cp "$MEM_SRC" "$MEM_DST"
            echo "[memory] INSTALLED $MEM_DST"
        fi
        # MEMORY.md index — add the one-line entry if not present
        INDEX_LINE='- [Rote context system](arch-rote-context-system.md) — /path/to/rote/ at github.com/wdunn001/rote; FastAPI on :5572 + sqlite-vec + vault + delegates (Ollama/sglang/MetaMCP on edge-host) + MCP server + 4 Claude skills. Use BEFORE writing shell or deferring bulk work.'
        if [[ ! -f "$MEM_IDX" ]]; then
            printf '# Memory Index\n\n%s\n' "$INDEX_LINE" > "$MEM_IDX"
            echo "[memory] CREATED $MEM_IDX (with index line)"
        elif ! grep -qF "arch-rote-context-system.md" "$MEM_IDX"; then
            # Insert after the "# Memory Index" header line
            python3 - "$MEM_IDX" "$INDEX_LINE" << 'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); line = sys.argv[2]
text = p.read_text()
# Insert right after the first blank line following the header
lines = text.splitlines()
out, inserted = [], False
for i, l in enumerate(lines):
    out.append(l)
    if not inserted and l.startswith("# Memory Index"):
        # find the first blank line after it
        if i + 1 < len(lines) and lines[i+1].strip() == "":
            out.append("")
            out.append(line)
            inserted = True
        else:
            out.append("")
            out.append(line)
            out.append("")
            inserted = True
if not inserted:
    # No header — prepend
    out = ["# Memory Index", "", line, ""] + lines
p.write_text("\n".join(out) + "\n")
PY
            echo "[memory] APPENDED index line to $MEM_IDX"
        else
            echo "[memory] index line already present in $MEM_IDX"
        fi
        INSTALLED=$((INSTALLED + 1))
    fi
fi

echo
echo "=== install-claude-code-skills: installed=$INSTALLED failed=$FAILED mode=$MODE ==="
[[ "$FAILED" -gt 0 ]] && exit 6
exit 0
