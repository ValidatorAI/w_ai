# MCP vs Toolsets: Two Independent Axes (Per Profile)

Answers the recurring class of question: "does a profile need tool/toolset X
(usually **terminal**) to use MCP?" Short answer: **no**. MCP is its own axis,
configured per profile, and is not gated by any builtin toolset.

Verified live on this install (default + 14 profiles):
`hermes profile list`, every profile's `config.yaml` parsed with `yaml.safe_load`.

## Evidence that MCP is not gated by the terminal tool

- The `delegator` profile has **terminal removed** from its CLI toolsets
  (`platform_toolsets.cli` = 8 entries vs 17 in the other 13 profiles) yet still
  configures `mcp_servers: {w-bridge, memory}`. Terminal-off does not disable MCP.
- `hermes_cli/tools_config.py` folds every ENABLED MCP server NAME into the
  enabled-toolset set (`enabled_mcp_server_names(config)`,
  `include_default_mcp_servers=True`). Each server contributes a *runtime
  toolset named after the server* (e.g. `w-bridge`) once it registers ≥1 tool.
  The only opt-out is the literal sentinel **`no_mcp`** in a platform's toolset
  list — and the picker has no checkbox for it, so re-saving from
  `hermes tools` clears it (`preserved_entries.discard("no_mcp")`).
- `toolsets.py` contains no MCP reference at all — nothing to enable or disable
  there; `mcp_servers` is a top-level config key, siblings with `plugins`.
- **stdio servers are spawned by Hermes itself**, not by the model-facing
  terminal tool: `tools/mcp_tool.py` uses its own asyncio subprocess path with
  filtered env (secret-source vars passed through deliberately) and shared
  stderr redirection. HTTP servers need nothing local at all.

## What a profile actually needs for MCP

1. `mcp_servers:` in THAT profile's own `config.yaml` — there is no fleet-wide
   list and no inheritance from `default`. Observed shape here: all 14 profiles
   carry `w-bridge` (`http://0.0.0.0:8031/mcp`) + `memory`
   (`http://127.0.0.1:1933/mcp`); only `default` adds `obisidian`, which needs
   `headers: {Authorization: 'Bearer ${MCP_OBISIDIAN_API_KEY}'}`.
2. A **restart** of the session/agent — tools are discovered at agent startup
   (`hermes_cli/mcp_startup.py` background discovery thread, gated on
   `mcp_servers` being non-empty), so a newly added server is invisible until
   the next session. **In a gateway** there is a live path that avoids the
   session restart: the `/reload-mcp` slash command
   (`gateway/run.py::_execute_mcp_reload`) reconnects servers and reports
   reconnected/added/removed names + tool count. Neither path needs a gateway
   process restart — see `references/toolset-change-propagation.md`.
3. Reachability of the endpoint/command, plus whatever credentials the entry
   carries (`headers`/`env`).
4. Optional per-server keys: `enabled: false` to park it, `connect_timeout`,
   `idle_timeout_seconds` / `max_lifetime_seconds` (stdio lifecycle recycle).

Terminal is only needed to talk to the server **by hand** — curl JSON-RPC,
launch a stdio server, debug it.

## Tool-count effect: direct tools vs the deferred catalog

A server with a big surface does not dump all its tools into context. Here
`w-bridge` contributes 155 tools and they arrive as the **deferred** catalog
(`tool_search` / `tool_describe` / `tool_call`) rather than as directly-listed
tools; `memory` and `obisidian` tools load directly. Practical consequence: a
large MCP server's tool names are NOT in the system prompt index — `tool_search`
("create github issue"-style keyword query) is how you reach them, and
`tool_describe` is required before `tool_call`.

## Cheap verification recipe (no session restart needed)

```bash
hermes profile list                       # which profiles exist, gateway state, alias
hermes -p NAME mcp list                   # servers + ✓ enabled for that profile
hermes -p NAME tools list --platform cli  # toolsets actually enabled (terminal here or not)
```

Fleet audit in one pass — parse every profile's config instead of asking one at
a time (also catches a profile whose `config.yaml` is broken YAML):

```python
import yaml, glob, os
base = os.path.expanduser("~/.hermes")
paths = sorted(glob.glob(base + "/profiles/*/config.yaml")) + [base + "/config.yaml"]
for p in paths:
    name = p.split("/profiles/")[-1].split("/")[0] if "/profiles/" in p else "default"
    d = yaml.safe_load(open(p)) or {}
    mcp = list((d.get("mcp_servers") or {}).keys())
    ts  = (d.get("platform_toolsets") or {}).get("cli") or []
    print(name, mcp, "terminal" in ts, len(ts))
```

This one-liner produced the profile table above and is the fastest way to prove
or disprove "does MCP need the terminal tool?" for any profile.

## Answer shape

Lead with the verdict ("No") and the single strongest piece of live evidence (a
profile that has terminal off and MCP on), then the four requirements, and name
the files the claim came from (`hermes_cli/tools_config.py`,
`tools/mcp_tool.py`, `toolsets.py`). Keep it tight — this user caps length.
Flag the restart requirement early, because it explains "the tools don't exist"
far more often than a broken config does.
