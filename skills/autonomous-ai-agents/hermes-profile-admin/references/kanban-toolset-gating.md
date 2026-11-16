# Kanban Toolsets: Which Profiles Get `kanban_*`, and Does It Need the Terminal?

"Can a profile without terminal access create and assign kanban tasks to other
profiles?" — **Yes, the kanban toolset is on a separate axis from `terminal`**,
but on a default install it is OFF everywhere and the switch is not the one the
docs imply. Everything below is source- and live-verified (2026-09-29) on this
box: `tools/kanban_tools.py`, `tools/registry.py::get_definitions`,
`toolsets.py`, `hermes_cli/tools_config.py`, plus sandbox `HERMES_HOME` runs.

## The gate (read this before answering anything kanban-tool related)

All 12 kanban tools register with `toolset="kanban"` and
`check_fn=_check_kanban_mode`. `check_fn` is evaluated **per tool** inside
`registry.get_definitions()` (tools/registry.py ~L652-699) and a False result
drops the tool from the schema even when the toolset is otherwise enabled.

    _check_kanban_mode() -> True  IFF
      os.environ["HERMES_KANBAN_TASK"] is set      (dispatcher-spawned worker)
      OR "kanban" in load_config()["toolsets"]     (TOP-LEVEL key, exact match)

Consequences that are easy to get wrong:

- **It reads the TOP-LEVEL `toolsets:` list, not `platform_toolsets`.** A
  profile can list `kanban` under `platform_toolsets.cli` and still receive
  zero kanban tools. Verified live: `delegator`/`coder`/`testprofile` all have
  `kanban` in `platform_toolsets.cli`, and
  `_check_kanban_mode()` returns **False** for every one of them
  (`load_config()["toolsets"] == ['hermes-cli']`, the built-in default — none of
  the 17 profiles on this box has an explicit top-level `toolsets` key).
  Asking the live profiles to list their kanban tools answered `NONE`, i.e. the
  model genuinely cannot see them.
- **`hermes tools enable kanban --platform cli` refuses**: `✗ Unknown toolset
  'kanban'`. kanban is absent from `CONFIGURABLE_TOOLSETS`
  (hermes_cli/tools_config.py ~L96-124), so neither the picker nor the
  Desktop/`hermes tools` UI can turn it on. Its tool NAMES still ride along in
  `_HERMES_CORE_TOOLS` (toolsets.py ~L75-83) — which is exactly why the schema
  gate has to drop them again.
- The `kanban` toolset is a real key in the `TOOLSETS` dict (toolsets.py ~L287),
  so it can be named in the top-level `toolsets` list.

The 12 tools: `kanban_show`, `kanban_list`, `kanban_create`, `kanban_link`,
`kanban_unblock`, `kanban_comment`, `kanban_complete`, `kanban_block`,
`kanban_heartbeat`, `kanban_attach`, `kanban_attach_url`, `kanban_attachments`.

## What the handlers actually need

Nothing but the board. They open the shared SQLite board directly
(`kanban_tools._connect(board)`); no handler shells out, so the `terminal`
toolset is irrelevant to creating, assigning, linking, or commenting. The
`kanban` CLI (`hermes kanban create/assign/...`) works from ANY profile session
because it is plain CLI against the shared DB — no toolset at all is required
for that path.

## The fix that works

Add `kanban` to that profile's **top-level** `toolsets:` list in its
`config.yaml`:

```yaml
toolsets:
  - hermes-cli
  - kanban
```

Measured with the real config in a throwaway `HERMES_HOME`
(`hermes prompt-size --json`), so the numbers are what the runtime resolves:

| config | tools |
|---|---|
| this box's default profile | 32 |
| `toolsets: [hermes-cli, kanban]` | **44** (exactly +12 kanban) |
| same, `terminal` also removed from `platform_toolsets.cli` | **42**, all 12 `kanban_*` present, no terminal/process tool |

Row 3 is the direct answer to "without terminal access": yes.

**Pitfall — `hermes config set` cannot write this list.** It stores scalars
only, so `hermes config set toolsets "[hermes-cli, kanban]"` writes the STRING
`'["hermes-cli", "kanban"]'` (verified by back-reading the file). It then works
only by accident, because `"kanban" in <string>` is a substring match — do not
rely on it. Back up `config.yaml`, then hand-edit the list (or
`hermes config edit`). Same scalar-only rule as
`platform_toolsets.<platform>` and `agent.disabled_toolsets`.

## Verification recipe (offline, no API calls)

Two layers, both cheap — never answer this class of question from docs alone.

1. **Gate + schema, per profile, fresh process** (set `HERMES_HOME` per
   invocation so nothing is cached across profiles):

```python
import os, sys; os.environ["HERMES_HOME"] = home
sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent"))
from tools.kanban_tools import _check_kanban_mode
from tools.registry import registry
from hermes_cli.config import load_config
print(load_config().get("toolsets"), _check_kanban_mode())
names = {"kanban_create", "kanban_list", "terminal", "web_search"}
print(sorted(d["function"]["name"]
             for d in registry.get_definitions(names, quiet=True)))
```

Run it with the install's own interpreter:
`~/.hermes/hermes-agent/venv/bin/python` (the launcher script names the venv).

2. **Whole-session tool count, end to end** — copy `config.yaml` + `.env` into a
   sandbox home, edit the sandbox copy, and count:

```bash
mkdir -p /tmp/kbtest && cp ~/.hermes/config.yaml ~/.hermes/.env /tmp/kbtest/
# edit /tmp/kbtest/config.yaml (yaml.safe_load -> set toolsets -> yaml.safe_dump)
HERMES_HOME=/tmp/kbtest hermes prompt-size --json   # -> "tools": {"count": 44}
```

`hermes prompt-size --json` is the reusable probe here: it builds the real
tool schema offline and reporting `count` before/after an edit is a stronger
signal than asking a model which tools it has (a model asked to list tools
without calling them can answer `NONE` for the wrong reason — cross-check with
layer 1 before believing it).

## Assignment and dispatch (don't conflate with the gate)

- `kanban_create` REQUIRES `assignee` (profile name) — "tasks without an
  assignee are never dispatched". A profile with no kanban toolset can still be
  ASSIGNED work (assignment is a DB field); it just can't create/assign itself.
- The board is passive: an assigned task starts only when a dispatcher pass
  runs. Check the holder before promising anything will execute —
  `pgrep -af "hermes_cli.main gateway run"` plus `kanban.dispatch_in_gateway`
  (default true) and `kanban.dispatch_interval_seconds`. On this box the
  gateway is normally up and the interval is 10s, so an assign flips
  ready→running within seconds.
- `hermes kanban boards` lists boards and marks the current one (`default`,
  `company`, `new-room` here); `hermes kanban assignees` shows which profiles
  have task history and their counts.
- **Subagents cannot do this.** `_reject_delegated_child_mutation()` hard-blocks
  `kanban_create` / `complete` / `block` / `comment` / `heartbeat` / `link` /
  `unblock` when `is_delegated_child_context()` is true — a `delegate_task`
  child cannot even be trusted about env vars, since it shares the parent
  process. Only the profile's own (main) session may create or assign.

## Answer shape for this question

Verdict first and unprompted: "Yes — kanban is a separate axis from terminal."
Then the four facts that change the user's decision: the gate reads the
top-level `toolsets` key (so `platform_toolsets.cli` entries are inert here);
`hermes tools enable kanban` refuses; the working fix with its measured
before/after; and that assignment still needs a live dispatcher. Close with the
offer to flip it on for one profile and demo a create+assign round-trip rather
than editing the user's fleet unasked — this user caps capability answers and
reads the verdict first, and turning a profile's kanban tools on is a live
capability change, not a read-only answer.
