#!/usr/bin/env bash
# unpack-hermes-profile.sh — install a profile zip (made by pack-hermes-profile.sh)
# into a target Hermes location on another machine.
#
# Usage:
#   unpack-hermes-profile.sh FILE.zip [options]
#
# Behavior by pack mode (read from the zip's .profile-manifest):
#   named   -> extracts to $TARGET_HOME/profiles/NAME/   (clean import; an
#              existing folder is MOVED ASIDE to NAME.pre-import-TIMESTAMP,
#              never deleted, unless --merge which overwrites in place)
#   default -> MERGES the root files (config.yaml, SOUL.md, skills/, ...) into
#              $TARGET_HOME; overwrites only same-named files and backs up the
#              existing config.yaml/.env/SOUL.md first when --force is used.
#
# Options:
#   -t, --target-home P   target HERMES_HOME (default: $HERMES_HOME or ~/.hermes)
#   -p, --as NAME         override profile name / rename (named mode only)
#   -f, --force           proceed even if the target already has content
#   -m, --merge           named mode: overwrite in place instead of clean import
#   --dry-run             show what would happen, touch nothing
#   -h, --help
set -euo pipefail

ZIP="" TARGET="${HERMES_HOME:-$HOME/.hermes}" AS="" FORCE=0 MERGE=0 DRY=0

die() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }
run() { if [ "$DRY" = 1 ]; then echo "DRY: $*"; else "$@"; fi; }

while [ $# -gt 0 ]; do
  case "$1" in
    -t|--target-home) TARGET="$2"; shift 2;;
    -p|--as) AS="$2"; shift 2;;
    -f|--force) FORCE=1; shift;;
    -m|--merge) MERGE=1; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    -*) die "unknown option $1";;
    *) ZIP="$1"; shift;;
  esac
done

[ -n "$ZIP" ] || die "FILE.zip is required"
[ -f "$ZIP" ] || die "zip not found: $ZIP"
command -v unzip >/dev/null || die "unzip binary not found"

# ---- read manifest ----
unzip -Z1 "$ZIP" .profile-manifest >/dev/null 2>&1 \
  || die "not a hermes profile zip (no .profile-manifest inside) — packed with pack-hermes-profile.sh?"
MANIFEST="$(unzip -p "$ZIP" .profile-manifest)"
NAME="$(sed -n 's/^profile=//p' <<<"$MANIFEST")"
MODE="$(sed -n 's/^mode=//p' <<<"$MANIFEST")"
[ -n "$NAME" ] && [ -n "$MODE" ] || die "unreadable manifest in $ZIP"
[ -n "$AS" ] || AS="$NAME"
[ "$AS" = "$NAME" ] || { [ "$MODE" = named ] || die "--as rename only works for named profiles"; }

STAMP="$(date +%Y%m%d-%H%M%S)"
NFILES=$(unzip -Z1 "$ZIP" | grep -cv '^\.profile-manifest$' || true)

if [ "$MODE" = named ]; then
  DEST="$TARGET/profiles/$AS"
else
  DEST="$TARGET"
fi

echo "zip:     $ZIP  ($NFILES files, mode=$MODE, profile=$NAME)"
echo "target:  $DEST"

[ -d "$TARGET" ] || { [ "$DRY" = 1 ] || die "target hermes home does not exist: $TARGET (install hermes there first, or create it)"; }

if [ "$MODE" = named ]; then
  if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    if [ "$MERGE" = 1 ]; then
      echo "merge mode: overwriting same-named files in place"
      [ "$FORCE" = 1 ] || true   # merge IS the explicit opt-in
    elif [ "$FORCE" = 1 ]; then
      run mv "$DEST" "${DEST}.pre-import-$STAMP"
      echo "existing folder moved aside to ${DEST}.pre-import-$STAMP"
    else
      die "$DEST already exists and is not empty. Use --force (move aside + clean import) or --merge (overwrite in place)."
    fi
  fi
  run mkdir -p "$DEST"
else
  # default merge: protect the target's own identity files first
  if [ -f "$TARGET/config.yaml" ] || [ -f "$TARGET/SOUL.md" ]; then
    if [ "$FORCE" != 1 ] && [ "$DRY" != 1 ]; then
      die "$TARGET already looks like a live hermes home. Re-run with --force to merge (config.yaml/.env/SOUL.md will be backed up first)."
    fi
    BK="$TARGET/backups/pre-import-$STAMP"
    run mkdir -p "$BK"
    for f in config.yaml .env SOUL.md profile.yaml; do
      [ -f "$TARGET/$f" ] && run cp -p "$TARGET/$f" "$BK/$f" && warn "backed up existing $f -> $BK/$f"
    done
  fi
fi

# ---- extract ----
run unzip -o -q "$ZIP" -d "$DEST"
if [ "$DRY" = 1 ]; then echo "DRY: extraction planned for $DEST"; exit 0; fi

# the manifest is a transfer artifact, not profile content
rm -f "$DEST/.profile-manifest"

# ---- post-fixups ----
[ -f "$DEST/.env" ] && chmod 600 "$DEST/.env"
if [ "$MODE" = named ] && [ "$AS" != "$NAME" ]; then
  # renamed import: profile.yaml (if any) may still describe the old name — harmless,
  # but stamp the new folder so `hermes -p NAME` resolution uses the directory anyway.
  :
fi

# recreate CLI alias if hermes is installed
if [ "$MODE" = named ] && command -v hermes >/dev/null; then
  if [ ! -e "$HOME/.local/bin/$AS" ]; then
    hermes profile alias "$AS" 2>/dev/null || warn "alias '$AS' not created (name may clash with a hermes subcommand; use 'hermes -p $AS')"
  fi
fi

# ---- verify (target registry, NOT the local one) ----
echo "---"
echo "installed: $DEST ($(du -sh "$DEST" 2>/dev/null | cut -f1), $(find "$DEST" -type f | wc -l) files)"
if command -v hermes >/dev/null; then
  echo "hermes sees (in $TARGET):"
  HERMES_HOME="$TARGET" hermes profile list 2>/dev/null | grep -iE "(▶|◆|●)?\s*$AS|Profile" | head -3 || true
else
  warn "hermes CLI not on PATH here — install it before first run"
fi
echo "next: chmod 600 on .env is done; smoke-test with:"
echo "  hermes -p $AS chat -Q -q \"reply with exactly: PROFILE-OK\""
