#!/usr/bin/env bash
# Sync a directory tree of SOUL.md definitions into Hermes profiles.
#
#   sync-soul-profiles.sh SOURCE_DIR [--clone-from PROFILE] [--dry-run]
#                        [--desc-file FILE] [--skip NAME]
#
# Expected layout:  SOURCE_DIR/<group>/<soul-name>/SOUL.md
#   - SOUL.MD (uppercase extension) is accepted too.
#   - Grouping depth is arbitrary; the SOUL's parent dir name becomes the
#     profile id (lowercased, spaces -> underscores).
#   - `example` and any --skip NAME group/soul dirs are ignored.
#
# For each soul this script, idempotently:
#   1. creates the profile if missing  (hermes profile create NAME --clone-from ...)
#   2. writes SOUL.md from the source  (previous SOUL backed up if it differed)
#   3. inherits the default profile's .env  (byte-copy, mode 600)
#   4. sets a role description only when the profile has no profile.yaml yet
#
# Optional description override file: tab-separated "profile_id<TAB>description",
# one per line, '#' comments allowed. Without it the first non-empty line of the
# SOUL is used, which is usually good enough for kanban routing.
set -uo pipefail

SRC=""
CLONE_FROM="default"
DRY_RUN=0
DESC_FILE=""
SKIP_NAMES=(example)

while [ $# -gt 0 ]; do
  case "$1" in
    --clone-from) CLONE_FROM="$2"; shift 2 ;;
    --desc-file)  DESC_FILE="$2"; shift 2 ;;
    --skip)       SKIP_NAMES+=("$2"); shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    -h|--help)    sed -n '2,22p' "$0"; exit 0 ;;
    -*)           echo "unknown option: $1" >&2; exit 2 ;;
    *)            SRC="$1"; shift ;;
  esac
done

[ -n "$SRC" ] || { echo "usage: $0 SOURCE_DIR [--clone-from PROFILE] [--dry-run]" >&2; exit 2; }
[ -d "$SRC" ] || { echo "no such source dir: $SRC" >&2; exit 2; }

# The default profile IS $HERMES_HOME itself; named profiles live under it.
DEFAULT_HOME="${HERMES_HOME:-$HOME/.hermes}"
PDIR="$DEFAULT_HOME/profiles"
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="$PDIR/.soul_backup_$STAMP"

to_id() { echo "$1" | tr '[:upper:]' '[:lower:]' | tr ' ' '_'; }

is_skipped() {
  local name="$1" s
  for s in "${SKIP_NAMES[@]}"; do
    [ "$(echo "$name" | tr '[:upper:]' '[:lower:]')" = "$(echo "$s" | tr '[:upper:]' '[:lower:]')" ] && return 0
  done
  # also skip if any parent path component matches
  case "/$name/" in */example/*) return 0 ;; esac
  return 1
}

desc_for() {  # $1 = profile id, $2 = soul file
  local id="$1" file="$2" d=""
  if [ -n "$DESC_FILE" ] && [ -f "$DESC_FILE" ]; then
    d=$(grep -P "^$id\t" "$DESC_FILE" 2>/dev/null | head -1 | cut -f2-)
  fi
  if [ -z "$d" ]; then
    d=$(grep -m1 -v '^[[:space:]]*$' "$file" | tr -s ' \t' ' ' | cut -c1-220)
  fi
  printf '%s' "$d"
}

echo "source     : $SRC"
echo "clone from : $CLONE_FROM   (profiles dir: $PDIR)"
echo "dry run    : $([ $DRY_RUN -eq 1 ] && echo yes || echo no)"
echo

created=0; updated=0; skipped=0

# --- pass 1: create missing profiles -------------------------------------
while IFS= read -r soul; do
  dir=$(dirname "$soul"); base=$(basename "$dir")
  is_skipped "$base" && { echo "  skip     $base"; skipped=$((skipped+1)); continue; }
  id=$(to_id "$base")
  if ! printf '%s' "$id" | grep -qE '^[a-z0-9][a-z0-9_-]{0,63}$'; then
    echo "  INVALID  '$base' -> '$id' (must match [a-z0-9][a-z0-9_-]{0,63})"; skipped=$((skipped+1)); continue
  fi
  if [ -d "$PDIR/$id" ]; then
    echo "  exists   $id"
    continue
  fi
  desc=$(desc_for "$id" "$soul")
  if [ $DRY_RUN -eq 1 ]; then
    echo "  CREATE   $id  -- description: ${desc:0:60}..."
    created=$((created+1)); continue
  fi
  if hermes profile create "$id" --clone-from "$CLONE_FROM" --description "$desc" > "/tmp/pc_$id.log" 2>&1; then
    echo "  created  $id"; created=$((created+1))
  else
    echo "  FAILED   $id (see /tmp/pc_$id.log)"; sed 's/^/           /' "/tmp/pc_$id.log"; skipped=$((skipped+1))
  fi
done < <(find "$SRC" -type f -iname 'SOUL.md' | sort)

echo
# --- pass 2: SOUL.md + .env sync -----------------------------------------
while IFS= read -r soul; do
  dir=$(dirname "$soul"); base=$(basename "$dir")
  is_skipped "$base" && continue
  id=$(to_id "$base")
  [ -d "$PDIR/$id" ] || continue
  if [ $DRY_RUN -eq 1 ]; then
    echo "  would sync  $id"; continue
  fi
  # back up only when the on-disk SOUL actually differs (keeps backups meaningful)
  if [ -f "$PDIR/$id/SOUL.md" ] && ! cmp -s "$soul" "$PDIR/$id/SOUL.md"; then
    mkdir -p "$BACKUP/$id"; cp -p "$PDIR/$id/SOUL.md" "$BACKUP/$id/SOUL.md"
    echo "  backup   $id/SOUL.md"
  fi
  cp "$soul" "$PDIR/$id/SOUL.md"
  cp -p "$DEFAULT_HOME/.env" "$PDIR/$id/.env"; chmod 600 "$PDIR/$id/.env"
  envstate=$(cmp -s "$DEFAULT_HOME/.env" "$PDIR/$id/.env" && echo inherited || echo MISMATCH)
  printf "  %-18s SOUL=%-6s .env=%s\n" "$id" "$(wc -c < "$PDIR/$id/SOUL.md")b" "$envstate"
  updated=$((updated+1))

  # role description only when the profile has none yet — never clobber a curated one
  if [ ! -f "$PDIR/$id/profile.yaml" ]; then
    hermes profile describe "$id" --text "$(desc_for "$id" "$soul")" >/dev/null 2>&1 \
      && echo "  describe $id" || echo "  describe FAILED $id"
  fi
done < <(find "$SRC" -type f -iname 'SOUL.md' | sort)

echo
echo "created=$created synced=$updated skipped=$skipped"
[ $DRY_RUN -eq 0 ] && [ -d "$BACKUP" ] && echo "soul backups: $BACKUP"
echo "verify with: hermes profile list"
exit 0
