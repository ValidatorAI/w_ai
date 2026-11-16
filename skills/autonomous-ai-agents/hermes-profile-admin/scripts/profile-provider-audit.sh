#!/usr/bin/env bash
# Audit the model/provider setup of every Hermes profile.
#
# Prints, per profile: main provider + default model, fallback-chain length,
# and which provider API keys are present in that profile's .env.
#
# SAFETY: prints key NAMES only, never values. Safe to run in a session and
# to quote in a reply.
#
# Usage:  bash scripts/profile-provider-audit.sh [HERMES_ROOT]
#         HERMES_ROOT defaults to $HERMES_HOME or ~/.hermes

set -uo pipefail

ROOT="${1:-${HERMES_HOME:-$HOME/.hermes}}"

if [ ! -d "$ROOT" ]; then
  echo "no hermes root at $ROOT" >&2
  exit 1
fi

# Provider keys worth reporting. Extend as needed.
KEY_RE='^(DEEPSEEK_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY|OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|XAI_API_KEY|GLM_API_KEY|ZAI_API_KEY|MINIMAX_API_KEY|KIMI_API_KEY|DASHSCOPE_API_KEY|MISTRAL_API_KEY|GROQ_API_KEY|HF_TOKEN)='

audit_one() {
  local label="$1" cfg="$2" envf="$3"
  local provider default fallbacks keys

  provider=$(awk '/^model:/{m=1} m&&/^[[:space:]]+provider:/{print $2; exit}' "$cfg" 2>/dev/null)
  default=$(awk '/^model:/{m=1} m&&/^[[:space:]]+default:/{print $2; exit}' "$cfg" 2>/dev/null)

  if [ -f "$cfg" ]; then
    # Count list entries under fallback_providers (lines starting with "- ")
    fallbacks=$(awk '/^fallback_providers:/{f=1;next} f&&/^[^[:space:]]/{f=0} f&&/^[[:space:]]*-/{c++} END{print c+0}' "$cfg")
  else
    fallbacks="?"
  fi

  keys=$(grep -oE "$KEY_RE" "$envf" 2>/dev/null | tr -d '=' | sort -u | tr '\n' ' ')

  printf '%-14s provider=%-12s model=%-24s fallbacks=%-3s keys=[%s]\n' \
    "$label" "${provider:-?}" "${default:-?}" "$fallbacks" "${keys:-none}"
}

echo "hermes root: $ROOT"
echo
audit_one "default" "$ROOT/config.yaml" "$ROOT/.env"

if [ -d "$ROOT/profiles" ]; then
  for d in "$ROOT"/profiles/*/; do
    [ -d "$d" ] || continue
    audit_one "$(basename "$d")" "$d/config.yaml" "$d/.env"
  done
else
  echo "(no profiles/ directory)"
fi
