# Concurrency Caps: Per-Profile vs Global

Answers the recurring "max number of running tasks — is that per profile or for
all of Hermes?" Verified on the live install (`hermes -p NAME config get K`,
`hermes <cmd> --help`), `hermes_cli/config_defaults.py`,
`hermes_cli/kanban.py`, `hermes_cli/kanban_db.py`, `tools/delegate_tool.py`.

## There is no single global "max running tasks"

Eight different caps, three scopes. Read the table, not the question — and note
that the newest one is a cap on live CHAT SESSIONS (not tasks), which is what a
user usually means by "max number of running sessions".

| Config key | Scope | Default | This box |
|---|---|---|---|
| `max_concurrent_sessions` (top-level) | **per profile** (`$HERMES_HOME`), shared across that profile's surfaces | `null` = unlimited | `null` — verified live 2026-09-18 |
| `max_live_sessions` | ONE gateway process (value from its launch profile); soft LRU, detached sessions only | 16 | 16 (default, unwritten) |
| `gateway.api_server.max_concurrent_runs` | per profile, API server | 10 (`0` = off) | not read |
| `delegation.max_concurrent_children` | **per profile**, and per PARENT | 3 | 3 |
| `delegation.max_spawn_depth` | per profile (depth, not count) | 1 | 1 |
| `cron.max_parallel_jobs` | per profile (its own cron table) | `null` = unbounded | `null` |
| `kanban.max_in_progress` | **GLOBAL** — board-wide, all profiles | unset = no cap | unset |
| `kanban.max_in_progress_per_profile` | per profile, inside the shared board | unset = no cap | unset |

## Delegation — per profile AND per parent

`delegation.max_concurrent_children` lives in that profile's `config.yaml`, so
each profile carries its own value. But it is a **per-parent cap, not a global
one**: two different parents can each spawn `max_children` concurrently
(confirmed by the bundled `hermes-agent` reference
`delegate-task-concurrency-diagnosis.md`). So three profiles each delegating in
their own session can run 3 children apiece — 9 total, not 3.

- Floor 1, **no ceiling**. Env fallback `DELEGATION_MAX_CONCURRENT_CHILDREN`.
- Covers batch `tasks=[...]` AND concurrent `background=true` units; new async
  dispatches beyond the cap fall back to synchronous execution.
- `> 10` logs a cost warning at WARNING once — a log line only, it caps nothing.
- `delegation.max_spawn_depth` is depth (1 = flat), also per profile; at 1 an
  `orchestrator` role is silently downgraded to leaf.

### Key names users reach for that do NOT exist

Users name these settings colloquially. Grep before repeating their wording back:

| Wording heard | Reality |
|---|---|
| `max_number_of_workers` | **Not a Hermes key.** v0.19.1: 0 hits in a recursive grep of `$HOME`, 0 in the `hermes-agent` source, 0 in the docs bundle (`llms-full.txt`). It is a paraphrase of `delegation.max_concurrent_children`. |
| `max_workers` | Only ever a derived `ThreadPoolExecutor(max_workers=…)` argument (`agent/tool_executor.py::_MAX_TOOL_WORKERS`, the delegate batch pool). Not settable. The docs sentence "ThreadPoolExecutor with the configured concurrency limit as max workers" describes that derivation, not a config key. |
| "max running tasks / workers per profile" | Ambiguous by design — resolve to the table above; there is no single key. |

Cheap falsification (do this before answering "yes that's per profile"):

```bash
grep -rIn "<key>" --exclude-dir=node_modules --exclude-dir=.git ~ | head
grep -rIn "<key>" ~/.hermes/hermes-agent --include=*.py | head
grep -n "<key>" /tmp/llms-full.txt   # curl the docs llms-full.txt once, ~5 MB
```

### `hermes config get` reports the EFFECTIVE value, not whether it is pinned

`hermes config get delegation.max_concurrent_children` → `3` on a profile whose
`config.yaml` delegation block contains only `max_iterations: 50`. That `3` is
the **code default** (`hermes_cli/config_defaults.py`), not a written key. So
"it's 3 here" ≠ "it's set here" — say which one you mean, and check the file:

```bash
grep -n -A10 '^delegation:' ~/.hermes/config.yaml ~/.hermes/profiles/*/config.yaml
```

Verified 2026-09-30: all 16 loaded profiles carry their own `config.yaml` with a
`delegation:` block, and every one pins only `max_iterations: 50` — both caps
are unwritten everywhere, so each profile sits on defaults (3 / 1) and would
drift independently the moment one profile sets a value.

### Proving per-profile resolution without touching a real profile

`$HERMES_HOME` IS the resolution root (`hermes_cli/config.py::get_config_path`
→ `get_hermes_home()/config.yaml`; profile dirs come from
`hermes_cli/profiles.py::get_profile_dir`, and `default` maps to `~/.hermes`).
Probe it on a throwaway home instead of editing the user's config:

```bash
mkdir -p /tmp/hermesprobe
printf 'delegation:\n  max_concurrent_children: 7\n  max_spawn_depth: 3\n' > /tmp/hermesprobe/config.yaml
HERMES_HOME=/tmp/hermesprobe hermes config get delegation.max_concurrent_children   # -> 7
hermes config get delegation.max_spawn_depth                                        # -> 1 (untouched)
```

This is the general-purpose proof for ANY "is this per profile?" question —
cheaper and safer than mutating a live profile, and it also separates
"per-profile file" from "global file read by every profile".

## Cron — per profile

`cron.max_parallel_jobs` (default `null`/unbounded) = how many due jobs run in
parallel per tick, for that profile's OWN job table. Env override
`HERMES_CRON_MAX_PARALLEL`. Each profile's gateway ticks its own table.

## Kanban — the only genuinely global cap

- `kanban.max_in_progress` — **global concurrency cap on the shared board**
  (`hermes_cli/kanban.py` ~2438, "#33488 global concurrency cap"). Counts every
  in-progress task on `kanban.db` regardless of assignee profile.
- `kanban.max_in_progress_per_profile` — optional **per-profile throttle**
  (`#21582`): when set to a positive int, no single profile may hold more than N
  workers even if the global cap would allow it. Tasks blocked this way defer to
  the next dispatcher tick. Purpose: stop one profile saturating its local model
  / API quota / browser pool while other profiles sit idle.

Both are read from the config of the profile whose gateway runs the dispatcher
(`kanban.dispatch_in_gateway: true` by default, so the running gateway's
profile). The BOARD itself is shared across all profiles — that is the point of
it (`hermes-multi-agent-collaboration`).

Note: `max_in_progress` is read via `_kanban_cfg.get("max_in_progress")` but is
**not** present in `config_defaults.py`, so `hermes config get kanban.max_in_progress`
reports "Config key not set" even though the dispatcher honours it. Set it with
`hermes config set kanban.max_in_progress N` (scalar int — `config set` handles
ints fine) or via the dashboard's kanban settings.

## Chat-session slots — `max_concurrent_sessions` (the cap users usually mean)

```yaml
max_concurrent_sessions: null   # null/0 = unlimited; positive int = cap on ACTIVE CHAT SESSIONS
```

Verified live 2026-09-18 against the running install (`hermes config get` → null;
dashboard `GET /api/config/schema`; source in `hermes_cli/active_sessions.py`,
`cli.py`, `gateway/run.py`, `tui_gateway/server.py`, `gateway/config.py`).

- Canonical key is **top-level**; `gateway.max_concurrent_sessions` is an accepted
  fallback and the top-level key wins when both are set — both resolvers do this
  (`hermes_cli/active_sessions.py::resolve_max_concurrent_sessions`,
  `gateway/config.py` ~L1167). Malformed values (bool, non-numeric string, ≤0)
  are ignored with a warning, so a typo never blocks startup.
- **Scope across profiles: per profile.** The registry is a lease file at
  `$HERMES_HOME/runtime/active_sessions.json` (+ `.lock`), so N profiles on one
  host get N separate budgets — it is NOT a machine-wide session ceiling.
- **Scope across surfaces: SHARED.** CLI (`cli.py::_claim_active_session`, called
  in the interactive `run()` loop ~L14908 AND in one-shot `chat -q` mode ~L18251),
  the TUI/dashboard/desktop gateway
  (`tui_gateway/server.py::_claim_active_session_slot`), and the messaging gateway
  (`gateway/run.py::_claim_active_session_slot`) all lease from the same file. That
  is why a rejection message names the SURFACES holding the slots, not the one that
  got blocked.
- A slot is claimed on a session's **first turn**, not when a chat window opens —
  idle desktop tabs and background websocket resumes cannot starve the gateway.
- Best-effort / fail-open: an unreadable or unlockable registry admits the session
  rather than stranding the user. Intended for one host sharing one `$HERMES_HOME`,
  not a shared home mounted across machines.
- `hermes status` prints slot usage and holders when the cap is set
  (`hermes_cli/status.py` ~L622); the dashboard status page shows the count.
- Adjacent knobs with the same "how many live sessions" flavour:
  `max_live_sessions` (default 16) caps live session objects in the TUI/dashboard
  gateway (`tui_gateway/server.py::_max_live_sessions`, re-read per call), and
  `gateway.api_server.max_concurrent_runs` (default 10, `0` disables) rejects
  over-cap runs with HTTP 429 `Too many concurrent runs (max N)`.

### `max_live_sessions=16` is NOT 16 × ~200 MB (answered 2026-09-30)

The follow-up question after the scope answer, and the arithmetic is wrong for a
specific reason: the ~180–300 MB figure is a **per-PROCESS** number, while this
key caps session **records inside one already-running gateway process**.

- A session is a dict holding an `AIAgent` in that process's heap (`_sessions`,
  `tui_gateway/server.py:143`) — threads/objects, not interpreters. Marginal cost
  per session: agent skeleton ~0.2 MB + prompt/tool schemas ~0.04 MB + transcript
  ~1 KB RSS per 1 KB text (typical 0.2–2 MB, heavy file reader 5–10 MB). So 16
  live gateway sessions ≈ tens of MB over one baseline, not 3.2 GB.
- Measured on this host 2026-09-30: `hermes chat` 300.4 MB and 292.8 MB (separate
  processes), `hermes gateway run` 188.4 MB after 3 days uptime (RssAnon 156 MB /
  RssFile 31 MB) + one 17 MB `mcp_stdio_watchdog` MCP child. That baseline is paid
  once per process and shared by every session and worker inside it.
- 16 × ~200 MB only describes **16 separate CLI/TUI processes** — and this key does
  not govern those. To bound process count, use `max_concurrent_sessions` above.
- Real per-session hogs are subprocesses (browser daemons 100–300 MB each), while
  MCP servers are module-global per process (`tools/mcp_tool.py` `_servers`) and
  shared across sessions.
- Enforcement shape: soft LRU (`0`/`null` disables), evicts DETACHED sessions only
  (never running / pending / mid-build / holding active delegations), TTL 6 h
  (`_SESSION_TTL_S`), reaper every 300 s (`_REAPER_SCAN_S`) and `trim_memory` on
  each scan — hence a 3-day-old gateway sits at baseline instead of accumulating.

Full measured table and the "where the RSS really goes" detail: skill
`hermes-multi-agent-collaboration`, references/concurrency-and-session-caps.md +
references/delegation-memory-footprint.md.

### Restart semantics — varies by surface (this is the part to state explicitly)

| Surface | Needs a restart to honour a new cap? | Why |
|---|---|---|
| messaging gateway | **YES** — `hermes gateway restart` (or dashboard `POST /api/gateway/restart`) | `GatewayRunner.__init__` assigns `self.config` once (`gateway/run.py` ~L5744) and both the local pre-check (`_get_max_concurrent_sessions`) and the lease claim read that startup snapshot; nothing reassigns it later |
| TUI / dashboard / desktop chat | no | `tui_gateway/server.py::_load_cfg` re-reads config.yaml behind an mtime-keyed cache, so the next session claim sees the new value |
| CLI (interactive and one-shot), kanban workers | no | each session is a fresh process reading config.yaml at start |

The gateway is usually the systemd user unit `hermes-gateway.service` here, so
`hermes gateway status` names the pid to confirm the restart landed.

### Kanban interaction (the trap — this is why the answer is not just "set it to 3")

The dispatcher does NOT read `max_concurrent_sessions`; it has its own caps
(`max_spawn`, `max_in_progress`, `max_in_progress_per_profile`). But every worker
it spawns is `hermes -p <assignee> chat -q "work kanban task <id>"`
(`hermes_cli/kanban_db.py` ~L8990), i.e. one-shot CLI mode, which claims an
active-session slot and `sys.exit(1)`s when the cap is full (`cli.py` ~L18251).
So the cap DOES apply to dispatch, indirectly and destructively:

- It is counted against the **assignee profile's** own config — the spawn injects
  `HERMES_HOME` for that profile, so each worker reads that profile's cap.
- Over-cap workers die immediately. `nonzero_exit` is a REAL failure in the reap
  classifier (`kanban_db.py` ~L6920), so it counts toward `kanban.failure_limit`
  and can push the card to `blocked`. Only exit **75**
  (`KANBAN_RATE_LIMIT_EXIT_CODE`) is released back to `ready` without a failure
  count. Nothing queues for a slot.
- Therefore: keep the session cap comfortably ABOVE the worker concurrency you
  actually want (e.g. sessions 8 with `kanban.max_spawn: 3`), or throttle dispatch
  with `kanban.max_in_progress` instead of using the session cap as a kanban brake.

### Setting it (CLI and dashboard)

- `hermes config set max_concurrent_sessions 6` — a scalar int, so the "config set
  writes scalars only" limit does not bite; the comment-stripping caveat in
  SKILL.md Pitfalls does (back the file up first on a comment-rich config).
- **Dashboard → Config page** works, with two quirks worth naming up front:
  - The form is generated from `DEFAULT_CONFIG`, and the key IS in the live schema:
    `GET /api/config/schema` → `{"type": "string", "description": "Max Concurrent
    Sessions", "category": "general"}`. Because the shipped default is `null`, the
    inferred type is `string`, so it renders as a plain TEXT input (not a number
    spinner) and saves a quoted string. Both loaders coerce numeric strings, so it
    still behaves as that integer.
  - The same page's YAML toggle (`GET/PUT /api/config/raw`) replaces the whole
    document through the YAML dumper (`save_config(parsed, merge_existing=False)`),
    so comments are lost on both the form and the YAML path — same failure class as
    `hermes config set`.
  - Auth: `/api/config/schema` answers without a token, `/api/config` (GET/PUT)
    needs one; the schema endpoint is the cheap way to prove a field exists in the
    running version before telling the user to go click it.

## Kanban dispatch CADENCE — same global scope as the caps

"How often does the dispatcher tick — 30s, 60s?" → **60s** default, and it is
**global, not per-profile**, for the same reason the caps are: one dispatcher
serves every profile and board. `kanban.dispatch_interval_seconds` (default 60,
floor **1.0s**, junk value → 60 + warning) is read ONCE from
`load_config()` of the gateway that HOLDS the lock — writing it into a
`profiles/<name>/config.yaml` is inert unless that gateway wins the lock race,
and losers log "another gateway already holds the dispatcher lock … this gateway
will NOT dispatch". Two differences from the caps above:

- It is read **once at gateway boot** (`gateway/kanban_watchers.py` ~971, "Read
  config once at boot"), so tuning it requires `hermes gateway restart` — NOT
  live like toolset config.
- The machine-global lock is `kanban_home()/kanban/.dispatcher.lock`, and
  `kanban_home()` resolves through `get_default_hermes_root()` → the ROOT even
  when `HERMES_HOME` is a profile dir ("shared across profiles by design").

Don't confuse it with the notifier watcher's 5s poll (task completion/block
notifications). Full detail, tuning risk (`max_spawn`, `max_in_progress`), live
log evidence, and a read-only verification recipe: skill
`hermes-multi-agent-collaboration`, `references/kanban-dispatch-cadence.md`.

## The cap that usually isn't a cap

A batch running fewer subagents than requested is most often the **model
trimming its own plan**, not Hermes. Reasoning models collapse a 13-15 task
batch to a "rounder" 5/8/9/10 and then narrate it as "the runtime caps at N" —
post-hoc rationalisation. Before accepting that, check:

```bash
hermes config get delegation.max_concurrent_children
grep -E "Truncated.*delegate_task|Too many tasks" ~/.hermes/logs/agent.log | tail
```

If the config value is what you intended and neither log line appears, no Hermes
cap fired. Full diagnosis (three real cap paths, the "force N parallel" prompt
wording): bundled `hermes-agent` reference
`references/delegate-task-concurrency-diagnosis.md`.

Do NOT recommend lowering `max_concurrent_children` to "fix" a short batch —
the value was chosen deliberately; push back on the model instead.

## Answer shape

Lead with "depends which running tasks — there are N caps with two scopes", then
the scope per cap, then which one is actually in force on this box. Do not give a
single-number answer; the scope IS the answer.

When the user names a key that does not exist (for example
`max_number_of_workers`): say so **first and flatly** ("that name isn't a Hermes
setting — grep found zero hits"), then name the real keys, then the scope verdict
they actually wanted. Never answer the scope question as if the invented key were
real, and never say "yes" to a premise only half of which is true — split the
answer per key (this user checks premises and calls out padding, so lead with the
verdict, then keep the evidence tight and offer the follow-up rather than
volunteering a config change).

"Is there a max number of running SESSIONS (a global setting)?" — the cap that
literally matches that wording is `max_concurrent_sessions`: canonical top-level
key, **per profile** rather than machine-wide, shared across that profile's CLI /
TUI / dashboard / gateway surfaces, unset (unlimited) by default. Give that
verdict first, then the surface-by-surface restart table (only the messaging
gateway needs a restart), then the kanban trap if the user runs a dispatcher.
Apply a value only when asked — an over-tight cap does not throttle dispatch, it
fails workers with exit 1 and burns their failure budget.

The next question is usually a MEMORY one ("does 16 live sessions mean
16 × 200 MB?"). Answer it from the memory-semantics subsection above: the cap
counts in-process session OBJECTS, the ~200 MB is a per-PROCESS baseline, and the
only thing that multiplies RAM is process/worker count — which is a different key
(`max_concurrent_sessions` for chat processes, `kanban.max_in_progress*` for
dispatcher workers). Lead with the one-word falsification ("No — that
multiplication doesn't hold"), then the per-session marginal figure, then the
measured per-process RSS rows.
