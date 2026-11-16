# Tool cost vs quality — "which of my active tools costs me time and tokens?"

Trigger: "which of your active tools increases quality of response and at the same
time increases response time / token usage", "what's expensive in my toolset",
"what should I turn off to make you faster/cheaper", or any per-tool
quality/latency/token question about the LIVE tool surface.

## 1. Scope the question BEFORE answering (the correction that started this file)

The user asked this once and rejected the first answer as off-axis: *"i mean tools
not mcps."* One config renders BOTH axes, so answer with the right one:

- **Built-in toolset tools** (`terminal`, `browser`, `file`, `web`, `session_search`,
  `delegation`, `code_execution`, `todo`, `memory`, `skills`, `cronjob`, …) — what
  a user means by "your tools".
- **MCP-provided tools** (`mcp__w_bridge__*`, `mcp__neurostack__*`, the OpenViking
  `viking_*` set) — a SEPARATE axis: top-level per-profile `mcp_servers`, each
  enabled server becoming its own runtime toolset. Their cost is a prompt-catalog
  cost (w-bridge 171 deferred tools here, neurostack 34), plus startup handshake.
  Never count them as toolsets and never answer a "which tools" question with them.

Lead with the built-in verdict; name MCP cost only as a separate headlined
paragraph, or when the user asks about MCPs. Grey area worth flagging explicitly:
in a profile with `memory.provider: openviking`, the `memory` TOOL is built-in but
the recall machinery behind it is the OpenViking MCP — say which half you mean.

## 2. The honest framing (state it, don't skip it)

No built-in tool adds latency on EVERY turn. Tool cost is **on-use**, plus a small
always-on cost (each enabled toolset's schemas, the deferred-tool catalog, the
skill index in the system prompt). The only per-turn latency+token tax in this
fleet is the **memory recall path** (`memory.provider: openviking`, an MCP):
`recall_timeout_seconds: 4.0`, `recall_max_injected_chars: 4000`,
`profile_token_budget: 6000`, `recall_limit: 6`, `recall_score_threshold: 0.15`,
plus the always-injected `memory_char_limit: 2200` + `user_char_limit: 1375`.
So "increases response time AND tokens" is strictly true only of the recall path;
for built-in tools it holds at use-time.

Second honesty rule for this user: **"quality up" is designed intent, not
measured.** Nothing in the config or session DB scores output quality. Say so in
one line rather than implying measurement.

## 3. Per-toolset profile (measured shape, not guesses)

FITS "quality up + time up + tokens up":

| Toolset | Why quality goes up | Time cost | Token cost |
|---|---|---|---|
| `terminal` | real command output = the only real proof | command duration; `terminal.timeout: 180`, foreground ceiling 600s | stdout enters context verbatim; unbounded unless piped/filtered |
| `browser` | JS-rendered / interactive pages where curl or `web_extract` fails | worst in the set — browser boot, navigation, waits, `browser.inactivity_timeout: 120` | accessibility snapshots, full-content snapshots, `browser_vision` screenshots |
| `delegation` | isolates reasoning-heavy, parallel, or context-flooding work | largest total (child model turns + tool loops); `delegation.max_iterations: 50`, `max_concurrent_children: 3`, `max_spawn_depth: 1` | paid twice: context in + every child turn + consolidated summary back |
| `session_search` | recall of prior work for "where did we leave X" | LOW — FTS5 over local SQLite, zero LLM calls | moderate-high: bookends + ±5-message windows per hit, up to 10 hits |

DOESN'T FIT:

- `code_execution` — **inverted on tokens.** `execute_code` exists to filter, loop
  and prune BEFORE results reach context (50KB stdout cap, `max_tool_calls: 50`,
  `timeout: 300`). Quality up, time up, tokens usually DOWN. It is a cost reducer.
- `file` — quality up (`patch` fuzzy matches; `write_file` verifies the on-disk
  hash), but reads are capped at 2000 lines / ~100K chars with `next_offset`
  pagination and everything is local I/O. Tokens moderate, latency negligible.
- `todo` — quality up only for 3+ step tasks (step-drift guard); tokens near zero.
- `memory` — quality up long-term (fewer repeated corrections); the cost is
  DEFERRED into every future turn (the two injected char budgets above), negligible
  latency. Fits "tokens up" on a horizon, not per call.
- `cronjob` — no effect on the current answer at all; it creates work that runs
  later in a fresh session with its own bill. On a CLI origin the job is
  LOCAL-ONLY (output saved, not delivered) — say that rather than implying a ping.

Also worth naming when it comes up: `skills` / `skill_view` is the cleanest
built-in fit for the trade in the strict sense — synchronous blocking read, whole
SKILL.md lands in context and stays for the turn, and the skill index is in the
system prompt every turn even when nothing is loaded.

## 4. The amplifier: compression turns fat tool output into a model call

`compression.enabled: true`, `threshold: 0.5`, `target_ratio: 0.2`,
`protect_last_n: 20`, `max_attempts: 3`, `proactive_prune_tokens: 0` (idle),
`proactive_prune_min_result_chars: 8000`, `proactive_prune_min_reclaim_tokens: 4096`.

So a context-flooding tool does not cost tokens once — it can trip compaction,
which is an extra LLM call (more time AND more tokens). That is the mechanism
behind `execute_code` and `read_file` pagination existing at all; lead with it when
the user asks "why is it slow" rather than listing tools.

## 5. Reading the live active set (and its traps)

```bash
ss -ltnp | grep hermes        # 9119 = dashboard (serves HTML), 8642 = API server (serves JSON)
K=$(python3 -c "import yaml;print(yaml.safe_load(open('$HOME/.hermes/config.yaml'))['API_SERVER_KEY'])")
curl -s -H "Authorization: Bearer $K" http://127.0.0.1:8642/p/<profile>/v1/toolsets
```

Traps, all hit live:

- **Port 9119 answers with the SPA HTML, not JSON.** A request to the wrong port
  looks like a broken endpoint; it is the dashboard. Find both with `ss -ltnp`.
- **The `/p/<profile>/v1/toolsets` view is `platform: "api_server"` and is NOT the
  CLI session's toolset set.** Observed this session: the endpoint reported
  `clarify` OFF while the live CLI session has the `clarify` tool. Quote the
  endpoint as "the api_server resolution" and say which platform you read.
- `agent.disabled_toolsets` is subtracted last, so a row can read enabled on a
  platform list while being dead everywhere — check that block before concluding.
- `hermes tools` / `hermes tools --summary` refuse non-interactive use (a pty does
  not help); use `hermes -p NAME tools list --platform NAME` or the API.
- MCP servers never appear here (`include_default_mcp_servers=False`); a blank is
  not evidence of a disable.

## 6. Answer shape that worked

Verdict first (name the tool), then the three costs each on its own line, then the
runner-ups grouped as FITS / DOESN'T FIT, then the amplifier note, then the
one-line intent-vs-measured caveat. Keep the live-evidence header (endpoint URL +
the config keys you read) so the user can re-run it; this user checks claims
against the live install and asks for the surface when a number looks off.
