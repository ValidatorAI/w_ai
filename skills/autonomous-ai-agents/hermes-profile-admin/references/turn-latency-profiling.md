# Turn latency profiling — "send a message to <profile> and see what makes the
# whole time of response"

Trigger: "why is that profile slow", "what makes the whole time of response",
"send a message to the knowledge profile and time it", "where do the seconds go",
or any request to attribute wall-clock to a real turn instead of guessing from
config. Companion to `references/toolset-cost-and-quality-tradeoffs.md`: that file
answers "which tool costs me time/tokens" from config, THIS file measures one turn
end to end.

## The three instruments, in order

1. **A client-side probe** — POST one message to the profile through the
   multiplex API server and read curl's timing breakdown.
   Script: `scripts/probe-profile-latency.sh <profile> "<prompt>"`.
2. **The target profile's OWN log** — the request is logged by the profile that
   SERVED it, i.e. `~/.hermes/profiles/<name>/logs/agent.log` (the root
   `~/.hermes/logs/agent.log` does NOT carry it). This is the only place with
   per-phase timestamps.
   Script: `scripts/turn-phase-report.py <profile>` (prints the phase table for
   the recent turns).
3. **Langfuse spans (optional cross-check)** — the profile's own project keys
   give independent model-call durations. See "Langfuse cross-check" below.

## 1. The probe

```bash
bash scripts/probe-profile-latency.sh knowledge "Reply with exactly: OK"
```

It does the equivalent of:

```bash
curl -s -o /tmp/resp.json -w \
'connect: %{time_connect}s
starttransfer: %{time_starttransfer}s
total: %{time_total}s
http_code: %{http_code}
size_download: %{size_download} bytes
' -m 900 -X POST "http://127.0.0.1:8642/p/${PROFILE}/v1/chat/completions" \
  -H "Authorization: Bearer ${API_SERVER_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"model":"<model>","messages":[{"role":"user","content":"..."}],"stream":false}'
```

Read the response's `usage.prompt_tokens` — that is the token half of the answer
and it is stable across identical prompts, which makes it a good regression
signal.

Traps:

- `connect`/`appconnect` are ~0.0001s (loopback) even when the turn takes 5s —
  the seconds are all in the server-side phases, never in the socket.
- With `stream: false` (the default in most profiles here) `starttransfer ==
  total`: nothing is readable until the turn completes. Say so when the user
  asks about perceived speed; streaming changes perception, not total.
- `/p/<profile>/...` validates against the profile's OWN `API_SERVER_KEY`. It
  works with the root key only because profiles cloned from `default` share it —
  do not state "the root key is accepted" as a general rule (the older note that
  the root key returns `gateway_auth_failed` holds when the keys differ).

## 2. Phase decomposition from the profile log

Anchors, in the order they appear for a single turn (raw line shape:
`YYYY-mm-dd HH:MM:SS,mmm LEVEL logger: message`):

| Phase | Anchor line fragment |
|---|---|
| agent bootstrap | `run_agent: OpenAI client created (agent_init, shared=True)` |
| tool tiering | `tools.tool_search: tool_search activated (tier 1): N core/visible tools kept, M deferred (~T tokens), listing full (budget ~B tokens)` |
| memory provider | `agent.memory_manager: Memory provider 'openviking' registered (6 tools)` then `run_agent: Memory provider 'openviking' activated` |
| turn start | `[api-<hex>] agent.turn_context: conversation turn: session=... platform=api_server history=0 msg='...'` |
| model call issued | `run_agent: OpenAI client created (chat_completion_stream_request, shared=False)` |
| model call returned | `[api-<hex>] agent.conversation_loop: API call #1: model=... in=N out=M total=T latency=Xs cache=A/N (P%)` |
| turn finalised | `[api-<hex>] agent.conversation_loop: Turn ended: reason=text_response(finish_reason=stop) api_calls=1/150 ...` |
| response written | `aiohttp.access: 127.0.0.1 [...] "POST /p/<profile>/v1/chat/completions HTTP/1.1" 200 <bytes>` |

Four phases fall out:

```
intake+bootstrap   client send  -> turn_context   (agent_init, tiering, memory provider registration)
recall+assembly    turn_context -> model issued   (OpenViking recall + prompt build; UNSEGMENTED)
model call         model issued -> API call #1
finalize           API call #1  -> HTTP 200       (turn end, session/response persistence)
```

## 3. Worked numbers (2026-09-24, `knowledge`, deepseek-v4-flash, 3× "Reply with exactly: OK")

| run | curl total | prompt tok | bootstrap | recall+assembly | model call | finalize |
|---|---|---|---|---|---|---|
| A | 4.500 s | 24,942 | 0.395 | 0.903 | 2.099 (cache 13%) | 1.157 |
| B | 5.327 s | 24,942 | 0.109 | 3.448 | 1.634 | 0.191 |
| C | 5.140 s | 24,942 | 0.158 | 3.452 | 1.420 (cache 99%) | 0.214 |

What to conclude from this shape, and what to say:

- **The recall+assembly phase is the dominant and the variable one** — 0.9 s once,
  3.45 s twice, i.e. up to ~67% of the total and more than the model call. 3.45 s
  sits just under `recall_timeout_seconds: 4.0`, which is why it is the first
  suspect.
- **Cache hit rate explains model-call variance**, not prompt size: run A's call
  was slowest (2.1 s) at `cache=3200/24942 (13%)`; B/C were 1.4–1.6 s at
  `24704/24942 (99%)`. Cold prefix = slower call.
- **Token inflation has its own log line**: `tool_search activated (tier 1): 24
  core/visible tools kept, 171 deferred (~34375 tokens), listing full (budget
  ~20000 tokens)`. 24,942 prompt tokens to emit 2 — the deferred MCP catalog is
  the bulk, and it was a turn that called zero tools. MCP servers are NOT gated by
  `platform_toolsets` (`references/mcp-vs-toolsets.md`), so the w-bridge catalog
  loads even when it is absent from the profile's toolset list.
- **The cheap win is the pre-model phase**, not the model: splitting recall from
  assembly, or trimming the deferred catalog.

## 4. Langfuse cross-check (and its limits)

Credentials are per profile: `HERMES_LANGFUSE_PUBLIC_KEY` / `HERMES_LANGFUSE_SECRET_KEY`
in `~/.hermes/profiles/<name>/.env`, HTTP basic auth against the base URL.

```bash
PK=$(grep -m1 '^HERMES_LANGFUSE_PUBLIC_KEY=' .env | cut -d= -f2-)
SK=$(grep -m1 '^HERMES_LANGFUSE_SECRET_KEY=' .env | cut -d= -f2-)
curl -s -u "$PK:$SK" "$BASE/api/public/traces?limit=6"
curl -s -u "$PK:$SK" "$BASE/api/public/observations?traceId=<trace_id>&limit=60"
```

Limits, all observed:

- **Do not filter by `environment=`.** `?environment=knowledge` returned
  `totalItems: 0` while traces tagged `env=knowledge` existed. Fetch unfiltered
  and filter client-side.
- **Only two span types exist**: a `Hermes turn` AGENT span and a `call-llm`
  GENERATION child. There is **no span for memory recall or prompt assembly**, so
  Langfuse cannot split the pre-model gap — the profile log is the only source for
  it.
- **The `latency` field on the traces list is not the turn duration** (a 4.5 s turn
  reported 35.292). Use the `observations` list and its per-span `latency`.
- Span durations differ slightly from the log's `latency=`: e.g. Langfuse
  GENERATION 2.653 s vs log `latency=2.1s` for the same call — different
  measurement windows. Quote the direction (they agree to ~0.2–0.5 s), not
  false precision.

## 5. Pitfalls when parsing the log

- **Anchor every marker to the run window and take the FIRST match after the run
  start.** A naive "last match wins" scan let a later run's `turn_context`
  overwrite an earlier run's mark and produced a bogus 7.547 s bootstrap phase
  that had to be recomputed. `scripts/turn-phase-report.py` resets its pending
  record at each `turn_context`, which is the fix.
- **Mind the prefix.** Lines read via the file tools carry `NNNN|` line-number
  prefixes; lines from `tail` do not. A regex anchored on `\d+\|` silently
  matches nothing on `tail` output (and vice versa).
- **Compare before attributing.** The OpenViking service answers a plain HTTP
  request on its port in ~3 ms, so a 3.45 s pre-model gap is NOT raw service
  latency — it is recall pipeline + MCP round trip + prompt assembly. If the user
  wants it split, the options are per-phase debug logging or adding a recall span;
  say that rather than inventing a split.
- **One cold run misleads.** Three identical prompts gave 4.50 / 5.33 / 5.14 s and
  very different phase mixes; a single sample is not a profile of the profile.
- Restated honesty rule from the companion reference: phase times are measured,
  "quality" never is.

## 6. Answer shape that worked

Lead with the measured total and the token count ("4.5–5.3 s and 24,942 prompt
tokens to emit 'OK'"), then the phase table, then name the dominant phase and the
variable one, then the token-inflation line and the one lever to pull. Keep the
method header (endpoint, script path, log path, Langfuse trace id) so every number
is re-runnable, and close with the explicit limits list — the user checks claims
against the live install and will ask which surface a number came from.
