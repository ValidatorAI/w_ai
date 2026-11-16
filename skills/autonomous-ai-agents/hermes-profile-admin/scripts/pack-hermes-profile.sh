#!/usr/bin/env bash
# pack-hermes-profile.sh — zip ONE Hermes profile for transfer to another machine,
# excluding all re-downloadable / machine-local bulk (skills .hub index ~48M,
# curator backups, caches, logs, sessions, state dbs, locks).
#
# Usage:
#   pack-hermes-profile.sh PROFILE [options]
#   PROFILE = a named profile (e.g. ai_settings) or "default".
#             "default" has no folder — its home IS $HERMES_HOME — so the
#             packer takes a portable allow-list from the root instead.
#
# Options:
#   -o, --out FILE       output zip (default: PROFILE-YYYYmmdd-HHMMSS.zip in the
#                        directory the command was run from)
#   -H, --hermes-home P  source HERMES_HOME (default: $HERMES_HOME or ~/.hermes)
#   --include-sessions   also pack sessions/ + state.db* (chat history; bigger)
#   --include-kanban     also pack kanban board workspaces (never _archived/)
#   --full               NO excludes at all (exact byte mirror of the folder)
#   -h, --help
set -euo pipefail

ORIG_PWD="$PWD"
PROFILE="" OUT="" HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
INCLUDE_SESSIONS=0 INCLUDE_KANBAN=0 FULL=0

die() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    -o|--out) OUT="$2"; shift 2;;
    -H|--hermes-home) HERMES_HOME="$2"; shift 2;;
    --include-sessions) INCLUDE_SESSIONS=1; shift;;
    --include-kanban) INCLUDE_KANBAN=1; shift;;
    --full) FULL=1; shift;;
    -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    -*) die "unknown option $1";;
    *) PROFILE="$1"; shift;;
  esac
done

[ -n "$PROFILE" ] || die "PROFILE is required (named profile or 'default')"
[ -d "$HERMES_HOME" ] || die "hermes home not found: $HERMES_HOME"
command -v zip >/dev/null || die "zip binary not found"

MODE="" SRC_PARENT=""
if [ "$PROFILE" = "default" ]; then
  MODE="default"
  SRC_PARENT="$HERMES_HOME"
  # portable allow-list for the root home; everything not listed (hermes-agent/,
  # node/, tools/, installs/, state.db, logs/, sessions/, caches …) stays behind
  ROOTS=(SOUL.md SOUL.MD config.yaml profile.yaml .env .envrc \
         skills plugins memories cron hooks platforms pairing plans skins \
         workspace kanban kanban.db)
else
  MODE="named"
  SRC_PARENT="$HERMES_HOME/profiles/$PROFILE"
  [ -d "$SRC_PARENT" ] || die "profile folder not found: $SRC_PARENT"
  # entries are stored RELATIVE to the profile dir — the unpacker decides the
  # folder name, which also makes --as renames work
  ROOTS=(.)
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---- manifest (carries the layout contract for the unpacker) ----
{
  echo "profile=$PROFILE"
  echo "mode=$MODE"
  echo "source_host=$(hostname)"
  echo "source_hermes_home=$HERMES_HOME"
  echo "packed_at=$(date -Is)"
  echo "excludes=$([ "$FULL" = 1 ] && echo none || echo minimal)"
  echo "include_sessions=$INCLUDE_SESSIONS"
} > "$TMP/.profile-manifest"

# ---- prune list (flat OR chain, applied before -type f) ----
PRUNE=()
if [ "$FULL" != 1 ]; then
  # depth-independent, safe name prunes: pure regenerable artifacts
  PRUNE+=( -name .hub -o -name .curator_backups -o -name __pycache__ \
           -o -name '.soul_backup_*' -o -name .deleted \
           -o -name '*.lock' -o -name '*.db-shm' -o -name '*.db-wal' \
           -o -name '*.bak' -o -name '*.bak-*' -o -name '*.tmp' \
           -o -name '.DS_Store' \
           -o -path '*kanban/boards/_archived' )
  [ "$INCLUDE_KANBAN" = 1 ] || PRUNE+=( -o -path '*kanban/boards/*/workspaces' )
  # prunes anchored at the profile dir itself (find runs with cwd = it)
  if [ "$MODE" = "named" ]; then
    PRUNE+=( -o -path './cache' -o -path './logs' -o -path './home' \
             -o -path './backups' -o -path './image_cache' \
             -o -path './audio_cache' -o -path './plugin-update-checks' \
             -o -path './node' -o -path './bin' -o -path './lsp' \
             -o -path './sandboxes' -o -path './telemetry' \
             -o -path './terminal-sessions' -o -path './.profile-manifest' \
             -o -path './.env.pre-import-*' \
             -o -path './cron/ticker_heartbeat' -o -path './cron/ticker_last_success' )
    [ "$INCLUDE_SESSIONS" = 1 ] || PRUNE+=( -o -path './sessions' \
             -o -path './state.db*' -o -path './runtime' )
  fi
fi

# ---- enumerate payload ----
EXISTING=()
for r in "${ROOTS[@]}"; do [ -e "$SRC_PARENT/$r" ] && EXISTING+=("$r"); done
[ ${#EXISTING[@]} -gt 0 ] || die "nothing portable found under $SRC_PARENT"

cd "$SRC_PARENT"
: > "$TMP/filelist"
for r in "${EXISTING[@]}"; do
  if [ ${#PRUNE[@]} -gt 0 ]; then
    find "$r" \( "${PRUNE[@]}" \) -prune -o -type f -print >> "$TMP/filelist"
  else
    find "$r" -type f ! -name .profile-manifest -print >> "$TMP/filelist"
  fi
done
sort -u "$TMP/filelist" -o "$TMP/filelist"

NFILES=$(wc -l < "$TMP/filelist")
[ "$NFILES" -gt 0 ] || die "exclude filters removed every file"

# ---- zip: manifest first, then payload ----
OUT="${OUT:-$PROFILE-$(date +%Y%m%d-%H%M%S).zip}"
case "$OUT" in /*) ;; *) OUT="$ORIG_PWD/$OUT";; esac
rm -f "$OUT"
( cd "$TMP" && zip -q "$OUT" .profile-manifest )
zip -q "$OUT" -@ < "$TMP/filelist"

SZ=$(du -h "$OUT" | cut -f1)
echo "packed: $OUT"
echo "profile: $PROFILE (mode: $MODE, files: $NFILES, size: $SZ)"
echo "restore with: unpack-hermes-profile.sh $(basename "$OUT")"
[ "$FULL" = 1 ] && warn "--full mode: machine-local state IS included; review before unpacking on a live install." \
  || warn "excluded: .hub index, caches, logs, locks, backups$([ "$INCLUDE_SESSIONS" = 0 ] && echo ', sessions/state.db') — .hub re-downloads itself on the target's first skills-hub browse."
