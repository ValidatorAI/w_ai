# Enumerating a profile's toolsets — which surface answers what

Trigger: "list the toolsets I have", "how many toolsets does this profile have",
"which are active", "make me a CSV of them". These look like one question but
there are FOUR surfaces, they disagree, and the right answer is the one the user
is reading from — not the shortest one.

Measured on this box, `default` profile, 2026-09-21 (Hermes install at
`~/.hermes/hermes-agent`, live dashboard on `127.0.0.1:9119`):

| Surface | Rows | What it is |
|---|---|---|
| `_checklist_toolset_keys("cli")` | 24 | What the interactive `hermes tools` checklist offers: effective configurable toolsets minus config-only (`stt`) and other-platform-scoped (`discord`, `discord_admin`) |
| `hermes -p NAME tools list --platform cli` | 25 | That platform's resolved built-ins with `✓ enabled` / `✗ disabled`. Excludes config-only `stt`, plugin toolsets, and other-platform-scoped ones |
| `_get_effective_configurable_toolsets()` | 27 | The configurator universe: `CONFIGURABLE_TOOLSETS` (hardcoded 27-entry tuple list in `hermes_cli/tools_config.py` L94-123) + plugin toolsets, deduped by key |
| `GET /api/tools/toolsets?profile=NAME` (dashboard) | 28 | The Toolsets-page row set: label, description, platform, `enabled`, `available`, `configured`, `tools[]`. Adds plugin toolsets only the dashboard process discovers — `a2a` here |

25 is the count you get from the CLI; 28 is what a dashboard-reading user counts.
Both are correct answers to different questions, so a quoted number is a clue to
the surface, never a contradiction to correct.

## Live read (preferred when the dashboard is up)

```bash
ss -ltnp | grep hermes                      # find the dashboard (here 127.0.0.1:9119) and the gateway (8642)
TOK=$(curl -s http://127.0.0.1:9119/ | grep -o '__HERMES_SESSION_TOKEN__="[^"]*"' | cut -d'"' -f2)
curl -s -H "X-Hermes-Session-Token: $TOK" \
     "http://127.0.0.1:9119/api/tools/toolsets?profile=default"
```

- The token is embedded in the dashboard HTML as
  `window.__HERMES_SESSION_TOKEN__="..."`; with no/incorrect header the route
  answers `{"detail":"Unauthorized"}` (the SPA HTML is still served, which is
  how you find the token in the first place).
- `profile=` takes a profile name; `default` reads the root `~/.hermes` config.
- In the handler (`hermes_cli/web_routers/tools.py::get_toolsets` L53-112)
  `available` is simply set equal to `enabled`, so there is no separate
  "installed but off" state to report. `enabled` is the toggle the user sees.
- Config-only toolsets (`_CONFIG_ONLY_TOOLSETS` = `stt`) get their state from
  their own config section (`stt.enabled`, default true) instead of
  `platform_toolsets`, which is why `stt` shows active while never appearing in
  `hermes tools list`.
- MCP servers are NOT toolsets and are excluded here
  (`include_default_mcp_servers=False`); the CLI list prints them in a separate
  "MCP servers: … all tools enabled" block. Never add them to a toolset count.

## Offline read (no server needed)

`scripts/list-profile-toolsets.py` mirrors that handler with the real resolvers
(`_get_effective_configurable_toolsets` + `_get_platform_tools` +
`_toolset_configuration_platform`, with `HERMES_HOME` pinned per profile).
It prints the same `name,active` shape and can write the CSV directly:

```bash
python3 scripts/list-profile-toolsets.py --profile default
python3 scripts/list-profile-toolsets.py --profile default --csv ~/hermes_default_toolsets.csv
python3 scripts/list-profile-toolsets.py --url http://127.0.0.1:9119 --token "$TOK" --profile default
```

Expect the offline run to return one row FEWER than the live API when a plugin
toolset only materialises in the dashboard process (27 vs 28 here, the extra
being `a2a`). Confirm with `discover_plugins()` scope before treating the delta
as a bug.

## Why the CLI list is not the census

`hermes tools list --platform X` walks the platform's RESOLVED set, so it omits:
config-only capabilities (`stt`), toolsets scoped to another platform
(`discord`, `discord_admin` are `discord`-only per `_toolset_allowed_for_platform`),
plugin toolsets that aren't reachable from that platform, and any toolset parked
off via `agent.disabled_toolsets` (that switch is subtracted last — see the
Lock-Down section of SKILL.md; it explains why a "disabled" row there can still
be enabled on a profile after a UI re-enable).

## CLI gotchas hit while answering this

- `hermes tools` (interactive) and `hermes tools --summary` both refuse
  non-interactive use: `Error: 'hermes tools' requires an interactive terminal.
  It cannot be run through a pipe or non-interactive subprocess.` — and a pty
  does NOT bypass it. Script against `hermes tools list --platform NAME` or the
  dashboard API instead.
- Doc drift: `cli-config.yaml.example` (~L1025) still says "Run
  `hermes chat --list-toolsets` to see all toolsets"; this build rejects it
  (`unrecognized arguments: --list-toolsets`). Don't repeat that instruction.
- `grep -c "enabled"` over `hermes tools list` output is a trap: the MCP block
  also contains "all tools enabled" (3 lines here), which inflates any naive
  count by the number of MCP servers.

## Delivering the answer

When the user asks for a CSV, write the file (2 columns, `name,active`), then
print its contents inline and name the surface it came from plus the row count.
State explicitly that MCP servers were excluded so a later diff against a
different screen doesn't look like drift. If their count and yours differ, say
which surface produced yours and which one produces theirs.
