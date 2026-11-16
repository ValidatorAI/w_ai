#!/usr/bin/env bash
# probe-profile-latency.sh — send ONE message to a Hermes profile through the
# multiplex API server and report a client-side timing breakdown of the round trip.
#
#   bash probe-profile-latency.sh <profile> "<prompt>" [--port 8642]
#
# Then decompose the server-side phases from that profile's own log:
#   python3 turn-phase-report.py <profile>
# See references/turn-latency-profiling.md for the anchor table and worked numbers.
#
# Notes:
#   * 8642 is the JSON API server; 9119 is the dashboard (answers SPA HTML).
#     Resolve both with: ss -ltnp | grep hermes
#   * /p/<profile>/... validates against that profile's OWN API_SERVER_KEY; the
#     root key works here only because the profiles were cloned from default.
set -u

PROFILE="${1:?usage: probe-profile-latency.sh <profile> \"<prompt>\" [--port N]}"
PROMPT="${2:-Reply with exactly: OK}"
PORT=8642
while [ $# -gt 2 ]; do
  case "$1" in --port) PORT="$2"; shift 2 ;; *) shift ;; esac
done

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

# Key: prefer the target profile's own .env, fall back to the root config.
KEY=""
if [ -f "$HERMES_HOME/profiles/$PROFILE/.env" ]; then
  KEY=$(grep -m1 '^API_SERVER_KEY=' "$HERMES_HOME/profiles/$PROFILE/.env" 2>/dev/null | cut -d= -f2-)
fi
if [ -z "$KEY" ] && [ -f "$HERMES_HOME/config.yaml" ]; then
  KEY=$(python3 -c "import yaml;print(yaml.safe_load(open('$HERMES_HOME/config.yaml')).get('API_SERVER_KEY',''))" 2>/dev/null)
fi
[ -n "$KEY" ] || { echo "no API_SERVER_KEY found for profile '$PROFILE'" >&2; exit 1; }

MODEL=$(python3 -c "import yaml;print(yaml.safe_load(open('$HERMES_HOME/profiles/$PROFILE/config.yaml'))['model']['default'])" 2>/dev/null || echo "")
MODEL=${MODEL:-unknown}

BODY=$(python3 - "$MODEL" "$PROMPT" <<'PY'
import json, sys
print(json.dumps({"model": sys.argv[1],
                  "messages": [{"role": "user", "content": sys.argv[2]}],
                  "stream": False}))
PY
)

echo "profile : $PROFILE"
echo "model   : $MODEL"
echo "prompt  : $PROMPT"
echo "start   : $(date +%Y-%m-%dT%H:%M:%S.%3N)   <- paste this into turn-phase-report.py if you want t0"
echo "curl    :"
curl -s -o /tmp/probe-profile-latency.json -w \
'  connect       : %{time_connect}s
  appconnect    : %{time_appconnect}s
  starttransfer : %{time_starttransfer}s
  total         : %{time_total}s
  http_code     : %{http_code}
  size_download : %{size_download} bytes
' -m 900 \
  -X POST "http://127.0.0.1:${PORT}/p/${PROFILE}/v1/chat/completions" \
  -H "Authorization: Bearer ${KEY}" \
  -H 'Content-Type: application/json' \
  -d "$BODY"
echo "end     : $(date +%Y-%m-%dT%H:%M:%S.%3N)"
python3 - <<'PY'
import json
try:
    d = json.load(open("/tmp/probe-profile-latency.json"))
    u = d.get("usage", {})
    print("content :", (d.get("choices") or [{}])[0].get("message", {}).get("content", "")[:120])
    print("tokens  : prompt=%s completion=%s total=%s" % (
        u.get("prompt_tokens"), u.get("completion_tokens"), u.get("total_tokens")))
except Exception as e:
    print("response not JSON (%s): %s" % (e, open("/tmp/probe-profile-latency.json").read()[:200]))
PY
echo
echo "next    : python3 turn-phase-report.py $PROFILE"
