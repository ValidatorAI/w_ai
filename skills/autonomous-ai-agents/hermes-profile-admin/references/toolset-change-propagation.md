# Toolset Changes: Does the Gateway Need a Restart?

Answers the recurring question class: *"I enabled/disabled a tool — do I need to
restart the gateway?"*, plus its symptom twin *"my new tool/toolset isn't showing
up"*. Verified by reading the source on this install
(`~/.hermes/hermes-agent/`, 2026-09).

## Verdict table

| Change | Restart needed? |
|---|---|
| Built-in toolset toggle (`hermes tools enable/disable X`, any platform key) | **No.** Config edit is picked up per message; the cached agent is rebuilt when the toolset signature changes. |
| Toggling a tool on an already-configured MCP server | No (same path — it is just a config entry). |
| Adding / removing an **MCP server** | Gateway: `/reload-mcp` (live reconnect, no process restart). CLI: new session. |
| Hermes code or plugin changes; platform/channel wiring; boot-read knobs (`kanban.dispatch_interval_seconds`) | **Yes** — gateway process restart (`/restart` in chat, `hermes gateway restart` from a shell). |
| Any of the above, on the **CLI** surface | No gateway involved: the running agent keeps its toolsets; start a new session (`/reset`, `/new`) or relaunch `hermes`. |

Do not answer `/restart` for a tool toggle, and do not answer "nothing needed" for
a newly added MCP *server*.

## The propagation chain (what to cite)

Symbol names are stable; line numbers drift with upstream commits. Re-verify with
`grep -n "<symbol>" gateway/run.py hermes_cli/tools_config.py`.

1. **Write.** `hermes tools enable/disable` persists into
   `platform_toolsets.<platform>` — `hermes_cli/tools_config.py`
   (`config.setdefault("platform_toolsets", {})`, then
   `config["platform_toolsets"][platform] = sorted(enabled | preserved)`).
   The same file's `_get_platform_tools(config, platform)` is the single
   resolution point used everywhere.
2. **Per-message read.** `gateway/run.py` main turn path:
   `user_config = _load_gateway_config()` →
   `enabled_toolsets = sorted(_get_platform_tools(user_config, platform_key))` →
   `disabled_toolsets = (user_config.get("agent") or {}).get("disabled_toolsets")` →
   both passed to the `AIAgent(...)` constructor. `_load_gateway_config()` shares
   the **mtime-keyed** raw-yaml cache with `hermes_cli.config.read_raw_config`, so
   a config edit on disk is visible on the very next message — no reload command.
   The background-task path repeats the same resolution.
3. **Cache invalidation.** The gateway caches the `AIAgent` per session keyed by
   `_agent_config_signature(model, runtime, enabled_toolsets, ephemeral_prompt,
   cache_keys, user_id, ...)`. Its blob includes `sorted(enabled_toolsets)` and a
   sorted `cache_keys` dict from `_extract_cache_busting_config(user_config)`.
   `_CACHE_BUSTING_CONFIG_KEYS` explicitly lists `("agent", "disabled_toolsets")`
   alongside `model.context_length`, `compression.*`, `memory.provider`,
   `checkpoints.*`. The in-source rationale: those values are baked into the agent
   at construction, so without the signature they would be silently ignored until
   an unrelated eviction (`/reset`, model switch).
   Consequence: **edit toolset config → next message rebuilds the agent → new
   toolset live.** No restart.
4. **The deliberate cost.** The rebuild discards the frozen system prompt + tool
   schemas, so that session's prompt-cache prefix is lost. That is why toolsets
   never change mid-conversation; the change lands at the next message boundary.

## Re-enabling a toolset fleet-wide (the reverse of a lock-down)

A lock-down is a hand edit (no CLI writes lists) — but the REVERSE is a CLI
command, and it is the case where `hermes tools enable` is the *only* correct
tool. Re-enabling requires clearing the toolset out of
`agent.disabled_toolsets`, because that list is subtracted last and beats every
platform list:

```bash
HERMES_HOME="$HOME/.hermes/profiles/<name>" hermes tools enable terminal --platform cli
# ✓ Enabled: terminal
```

The write path in `hermes_cli/tools_config.py` (the function containing
`config["platform_toolsets"][platform] = sorted(...)`) reconciles explicitly: it
computes `newly_enabled` and rebuilds `agent.disabled_toolsets` without those
keys. Its in-source rationale is this page's subject exactly — "a toolset listed
there stays permanently OFF no matter what this function writes — the toggle
'saves' but silently can't ever take effect" (issue #49995). Consequences worth
telling the user:

- ONE enable call per profile clears the block for that toolset on **every**
  surface (cli, api_server, cron, messaging) — do not loop the platform keys.
- The Desktop Toolsets UI reaches this same code path, so a UI re-enable does
  land. (The SKILL.md pitfall about a toggle that "saves" but stays off applies
  to hand-written deny entries that the user never re-enables through a
  platform checklist.)
- `HERMES_HOME=~/.hermes/profiles/<name> hermes …` is a verified way to target a
  profile for one command without depending on which profile is sticky — use it
  in `for d in ~/.hermes/profiles/*/` loops.

### Procedure

1. **Audit first, then touch only what is off** —
   `python3 scripts/audit-toolset-effective.py terminal`. On this box 3 of 15
   profiles already resolved terminal (default, coder, delegator), so 12 calls
   ran instead of a per-platform sweep (minutes of process startups).
2. **Back up ALL configs into one timestamped dir** before a fleet-wide edit —
   per-file `.bak`s are not enough to unwind a loop that touched N profiles:
   `mkdir -p ~/.hermes/config-backups/$(date +%Y%m%d-%H%M%S)`, copy
   `~/.hermes/config.yaml` plus every `profiles/*/config.yaml` in, and print the
   path in the reply so the user can revert.
3. **Run the enable per profile**, then **re-audit** and report the touched set.

### Side effects to expect (not corruption)

`hermes tools enable` rewrites `platform_toolsets.<platform>` as an EXPLICIT
allowlist mirroring the previously-effective set, records
`known_builtin_toolsets.<platform>` (how a later uncheck is told apart from a
newly-shipped toolset), and auto-adds recently shipped toolsets — here `kanban`
appeared in every cli list. Nothing enabled becomes disabled, but the config
SHAPE changes from a composite name to explicit keys; say so in the report
rather than letting the user find it in a diff.

### Say what the capability re-opens

Lock-downs arrive as a SET (terminal + file + code_execution together).
Re-enabling terminal alone leaves `file` and `code_execution` disabled in config
while handing the agent a shell that can do both — say that plainly in the reply
and offer the revert from the backup dir. Do not let "✗ disabled file" read as
if the block still holds.

## Auditing a toolset: resolve, never scan the list

`platform_toolsets` list membership is not the answer. In a cloned fleet the
messaging keys hold COMPOSITE names (`hermes-discord`, `hermes-google_chat`), so
`'terminal' in platform_toolsets['discord']` is False while the resolved set DOES
contain terminal. A literal scan during a fleet audit reported 11 surfaces
"missing terminal" that were in fact blocked only by `agent.disabled_toolsets` —
answering from that scan would have been wrong twice: it hides the real cause and
points the fix at the wrong key.

Resolve instead. `scripts/audit-toolset-effective.py [TOOLSET]` does it for every
profile × configured platform plus `cli` / `api_server` / `cron`, one fresh
interpreter per profile (the resolver is home-dependent: plugin toolsets and
credential-gated auto-enables like `x_search` / `homeassistant` read the
profile's own home). It exits 1 if anything is still off, so it can gate a
rollout; it also prints each profile's declared `agent.disabled_toolsets` so the
mechanism holding a toolset off is visible. Raw call for one-off checks:

```python
import os, sys, yaml
os.environ["HERMES_HOME"] = home          # the profile under test
sys.path.insert(0, "/home/user/.hermes/hermes-agent")
cfg = yaml.safe_load(open(f"{home}/config.yaml"))
from hermes_cli.tools_config import _get_platform_tools
"terminal" in _get_platform_tools(cfg, "api_server")
```

Two things to read correctly while auditing:

- `platform '<x>' has no valid toolsets configured (unknown name(s): ...)` on
  stderr is a PRE-EXISTING defect in that profile, not caused by your edit —
  seen here for `google_chat` / `teams` (`hermes-google_chat` / `hermes-teams`
  are not real composite names; issue #38798) across the cloned role profiles.
  Report it as a side finding, do not silently "fix" it, and do not let it abort
  the sweep.
- A toolset can be effective on a surface because the platform key is ABSENT
  (the resolver falls back to that platform's default toolset) — so "not in the
  list" is neither on nor off until you resolve it.

## Restart-scoped commands (for contrast)

- `/restart` — `gateway/slash_commands.py::_handle_restart_command`: drains
  active work ("gateway.draining"), records routing so the new process can notify
  the requester, then restarts the gateway **process**. Has redelivery-dedup logic
  for the PTB `get_updates` ACK race (a re-delivered `/restart` is ignored instead
  of looping). Use for code/plugin/platform changes.
- `/reload-mcp` — `gateway/run.py::_execute_mcp_reload` (reached via
  `_handle_reload_mcp_command`): reconnects MCP servers live and reports
  reconnected/added/removed names plus the available tool count; can also fail
  with a reported error. This is the "new MCP server" path, not `/restart`.

## Verification probes

```bash
# declared config vs. resolved set for one platform, per profile
hermes -p NAME tools list --platform cli
# live, through the running gateway (api_server surface = what bots get)
curl -s -H "Authorization: Bearer $API_SERVER_KEY" \
  http://127.0.0.1:8642/p/NAME/v1/toolsets
# re-locate the anchors instead of trusting line numbers
cd ~/.hermes/hermes-agent && grep -n "_CACHE_BUSTING_CONFIG_KEYS\|_agent_config_signature\|_execute_mcp_reload" gateway/run.py
```

## Answer shape (this user)

Verdict first with the negation spelled out — "No — not for a tool toggle" — then
the mechanism in one line (config re-read per message; agent rebuilt when the
toolset signature changes), then the boundary cases that *do* need a restart. Name
the file/command the claim came from. Keep it short; hold the exhaustive chain
behind an offer.

Note: the bundled `hermes-agent` skill's `references/troubleshooting.md` gives the
coarser line "Config changes: In gateway: /restart / Tools/skills: /reset". That
skill is protected — the verified finer-grained answer above supersedes it for
toolset questions, so answer from here rather than repeating the coarse line.

The reverse direction needs no scope question: **"enable X for all profiles" is
literal-all.** The exempt-set convention in SKILL.md governs
capability-STRIPPING, not enables — and a profile that already resolves X simply
needs no call. Answer an enable request with four things, in this order: the set
touched; the mechanism that was actually blocking it
(`agent.disabled_toolsets` — one list subtracted last — never the platform list);
what the capability re-opens; and the backup dir to revert from. Report the
surfaces verified, not the commands run.
