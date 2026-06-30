#!/usr/bin/env bash
# =============================================================================
# script: monorepo-symbol-rename.sh
# purpose: Safely rename identifiers AND their file/dir paths across a repo in
#          one pass: git-mv path moves first, then a scoped content rewrite of
#          disjoint substring pairs, with include globs + exclude regexes (to
#          spare e.g. dated historical docs) and a --dry-run. This is the
#          recipe behind a clean "IDroneLink -> IDeviceTransport + drone-link/
#          -> device-transport/" style monorepo rename across many surfaces.
# inputs:
#   --map OLD=NEW    substring rewrite pair (repeatable; applied left-to-right)
#   --mv  OLD=NEW    git mv a dir or file BEFORE the content rewrite (repeatable)
#   --include GLOB   filename glob for content rewrite (repeatable; default:
#                    common code + config + md extensions)
#   --exclude REGEX  path regex to SKIP in content rewrite (repeatable; e.g.
#                    'docs/(ops|releases|audits)/' to leave history untouched)
#   --root DIR       repo root to operate in (default: cwd)
#   --dry-run        print planned moves + candidate count, write nothing
# outputs: stdout summary (moves, files rewritten, residual-OLD count);
#          exit 0 success, 1 git-mv failure, 2 bad args
# touches-secrets: false
# when-to-use:
#   - renaming a type/interface/const AND moving its dir or file in one shot
#   - generalizing an abstraction across multiple app surfaces that must stay
#     in lockstep (web + companion + worker), keeping git rename history
#   - any rename where pure find/replace is not enough because paths move too
# when-NOT-to-use:
#   - content-only replace, no path moves  -> use find-replace-tree.sh
#   - overlapping substrings (Foo and FooBar): order longest-first or this
#     double-rewrites; always verify the plan with --dry-run first
# added: 2026-06-04
# family: monorepo-symbol-rename
# environment: posix-bash
# =============================================================================
# NOTE: deliberately NOT using `set -u`. When a Claude Code Bash tool call
# sources its shell snapshot, an unguarded `$ZSH_VERSION` reference trips
# `set -u` and silently corrupts mapfile/process-substitution arrays. See
# anti-pattern `set-u-breaks-on-shell-snapshot`.
set -o pipefail

ROOT="."; DRY=0
declare -a MAPS MVS INCLUDES EXCLUDES
while [ $# -gt 0 ]; do
  case "$1" in
    --map) MAPS+=("$2"); shift 2;;
    --mv) MVS+=("$2"); shift 2;;
    --include) INCLUDES+=("$2"); shift 2;;
    --exclude) EXCLUDES+=("$2"); shift 2;;
    --root) ROOT="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    -h|--help) sed -n '2,40p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
[ "${#MAPS[@]}" -gt 0 ] || { echo "need at least one --map OLD=NEW" >&2; exit 2; }
cd "$ROOT" || { echo "bad --root: $ROOT" >&2; exit 2; }

if [ "${#INCLUDES[@]}" -eq 0 ]; then
  INCLUDES=( '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.cjs' '*.json' '*.yml' '*.yaml' '*.md' '*.py' '*.go' '*.rs' '*.cs' '*.java' '*.cpp' '*.h' )
fi

# 1) git mv path moves (dirs/files) first so rename history is preserved
for pair in "${MVS[@]}"; do
  old="${pair%%=*}"; new="${pair#*=}"
  if [ ! -e "$old" ]; then echo "skip mv (missing): $old" >&2; continue; fi
  if [ "$DRY" = 1 ]; then echo "DRY  git mv $old -> $new"; continue; fi
  mkdir -p "$(dirname "$new")"
  git mv "$old" "$new" || { echo "git mv failed: $old -> $new" >&2; exit 1; }
  echo "moved  $old -> $new"
done

# 2) candidate files: include-glob matches containing any OLD substring, minus excludes
pat=""
for m in "${MAPS[@]}"; do
  o="${m%%=*}"
  esc=$(printf '%s' "$o" | sed 's/[.[\*^$()+?{}|/]/\\&/g')
  pat+="${pat:+|}$esc"
done
# Prefer `git ls-files`: tracked-only, gitignore-aware (skips node_modules,
# nested worktrees, build dirs) and fast. Falls back to a PRUNED find off-git.
CANDID=()
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  while IFS= read -r f; do CANDID+=("$f"); done < <(git ls-files -- "${INCLUDES[@]}" 2>/dev/null)
else
  incl=()
  for g in "${INCLUDES[@]}"; do incl+=( -o -name "$g" ); done
  incl=( "${incl[@]:1}" )   # drop leading -o
  while IFS= read -r f; do CANDID+=("$f"); done < <(
    find . \( -path '*/node_modules/*' -o -path '*/.git/*' \) -prune -o \
         -type f \( "${incl[@]}" \) -print 2>/dev/null )
fi

FILES=()
for f in "${CANDID[@]}"; do
  skip=0
  for ex in "${EXCLUDES[@]}"; do printf '%s' "$f" | grep -qE "$ex" && { skip=1; break; }; done
  [ "$skip" = 1 ] && continue
  grep -qE "$pat" "$f" 2>/dev/null && FILES+=("$f")
done

echo "content-rewrite candidates: ${#FILES[@]}"
if [ "$DRY" = 1 ]; then
  printf '  %s\n' "${FILES[@]}" | head -60
  echo "(dry-run: no writes)"; exit 0
fi

# 3) apply all map pairs per file
sed_args=()
for m in "${MAPS[@]}"; do
  o="${m%%=*}"; n="${m#*=}"
  oe=$(printf '%s' "$o" | sed 's/[\/&]/\\&/g')
  ne=$(printf '%s' "$n" | sed 's/[\/&]/\\&/g')
  sed_args+=( -e "s/$oe/$ne/g" )
done
for f in "${FILES[@]}"; do sed -i "${sed_args[@]}" "$f"; done

# 4) residual report (false-positive if any NEW contains an OLD substring)
res=0
for f in "${FILES[@]}"; do grep -qE "$pat" "$f" 2>/dev/null && res=$((res+1)); done
echo "rewritten: ${#FILES[@]} files; residual-OLD files: $res"
if [ "$res" = 0 ]; then echo "clean"; else
  echo "WARN: residual OLD matches remain — overlapping substrings or NEW⊃OLD; inspect"; fi
