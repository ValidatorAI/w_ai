# The Per-Profile Automation Surface: Cron, Hooks, /plan

Answers the recurring "explain X in more detail" questions about a profile's
non-chat machinery. Verified against the live install and the source tree —
cron semantics from the official cron docs, hooks/plan from
`hermes_cli/commands.py`, `tools/skill_usage.py`, `agent/prompt_builder.py`,
and the plan skill itself.

Read this for: "what is cron", "does /hook relate to messaging", "what is
/plan", "can a profile schedule work / plan before executing".

## Cron — the durable scheduler

Owned by the GATEWAY DAEMON, not by a chat session. Each tick (60s) it loads
`<profile home>/cron/jobs.json`, runs due jobs in FRESH agent sessions,
delivers the result, computes `next_run_at`. A `.tick.lock` prevents
double-firing the same batch; attempts are ledgered in `cron/executions.db`
(claimed -> running -> completed|failed|unknown); outputs are kept at
`cron/output/<job_id>/*.md`.

```bash
hermes cron status      # is the scheduler alive? (default profile)
hermes -p NAME cron list
```

Per profile: each profile has its OWN job table, and jobs run under that
profile's model, keys, skills, approvals, and home. A stopped gateway means
nothing fires — always check `hermes cron status` before promising a schedule
works. (Contrast: `delegate_task` subagents die with the process; cron
survives restarts.)

### Schedule forms

`"30m"` | `"2h"` | `"every 2h"` | `"every monday 9am"` | `"every 1d at 09:00"`
| `"0 9 * * *"` (5-field) | an ISO timestamp for a one-shot.

### Two modes

1. **Agent job** (default) — fresh session runs the prompt with the normal
   tool list; can attach skills.
2. **`no_agent` script job** — the scheduler runs your script and delivers
   stdout verbatim. Zero tokens, no model, no provider. Empty stdout = SILENT
   tick (nothing sent) — this is the watchdog pattern, "only speak when
   something is wrong". Non-zero exit or timeout delivers an error alert, so a
   broken watchdog cannot fail silently. `.sh`/`.bash` run under bash; anything
   else under the current Python. **Scripts must resolve inside
   `$HERMES_HOME/scripts/`** (relative, absolute, and `~` paths accepted only
   if the resolved target stays in that dir). The subprocess env is sanitized —
   provider credentials are NOT inherited by cron scripts.

### Knobs that matter

| Knob | Effect |
|---|---|
| `skills=[...]` | Attach one or more skills; loaded in order, prompt layered on top |
| `workdir=/abs/path` | Loads that repo's AGENTS.md/CLAUDE.md and makes terminal/file/code tools run there |
| `context_from=[id]` | Job B receives Job A's most recent output prepended as context (chain any length; list = concatenated) |
| `continuity=true` | Job sees its OWN previous output -> dedupe/continue instead of re-reporting the same thing |
| `deliver=` | origin \| local \| all \| platform:chat_id[:thread_id] |
| `repeat=N` | Bounded recurrence |
| `--paused [--paused-reason ...]` | Create a canary already paused, with an audited reason |
| `--model/--provider/--reasoning-effort` | Per-job pins |

Model resolution at fire time: **per-job pin -> `cron.model` -> the global
default**. The provider+model are SNAPSHOTTED at creation, so switching your
chat model never silently drags an unattended job onto a different (possibly
paid) provider. To move jobs: `hermes cron edit <id> --provider .. --model ..`
(one job) or `hermes config set cron.model <name>` (whole unpinned fleet).

### Use cases worth naming

Watchdogs (RAM/disk/GPU/queue over threshold, `no_agent`, silent when healthy)
· service/URL health checks · morning briefings (news, RSS, inbox, calendar)
· deduping scouts (`continuity=true`) · pipelines collect->triage->format->
ship across chained jobs (`context_from`) · nightly repo maintenance in
`workdir` (audit PRs, summarize CI, lint, deps) · one-shot reminders · weekly
metrics digests · integration glue that polls an API into a file/DB without a
live chat · self-maintenance (`hermes doctor`, checkpoint prune).

### Cron pitfalls

- **3-minute hard interrupt** per run.
- Unattended: nobody to ask. `clarify` is unavailable and the prompt must be
  fully self-contained; state things like the date explicitly in reminders.
- `approvals.cron_mode` defaults to **deny** — risky terminal commands just
  fail rather than prompting.
- Cron sessions run `skip_memory=True`, and a scheduled agent **cannot create
  more cron jobs** unless you opt in with `cron.allow_agent_scheduling: true`.
- `cron.preflight` (default on) validates provider key / skills / delivery
  targets BEFORE any LLM call: failures set `last_status: blocked_config` and
  deliver ONE alert instead of burning tokens every tick.
- Not an exactly-once side-effect guarantee.
- **Jobs created from a CLI session are local-only.** Output is saved and
  visible via `cronjob` list / `cron runs`, but there is no live-delivery
  channel into a terminal session. To actually notify the user the job must
  deliver to a gateway-connected platform (`telegram`, `discord`, `all`, ...).
- Lifecycle verbs accept a job NAME (case-insensitive) as well as the ID;
  ambiguous names are refused with candidate IDs listed rather than mutating
  the wrong job.

## Hooks are not messaging

Three unrelated things get called "hook", and there is **no `/hook` slash
command** (verified: no definition in `hermes_cli/commands.py`; the only
`/hook` string in the tree is a test fixture path). Also note the default
profile's SOUL.md is NOT a source of slash commands.

- **`hooks:` in config.yaml** — shell-script LIFECYCLE hooks that fire on agent
  events (tool use, session start/stop). Manage/inspect with
  `hermes hooks list | test <event> | doctor | revoke`; first-use consent
  allowlist lives at `~/.hermes/shell-hooks-allowlist.json`. Per-profile
  `hooks/` dirs exist (empty when unconfigured). Not messaging.
- **Inbound webhooks** — `hermes webhook` routes: an external service hits a URL
  and that triggers an agent run. Fires FROM an app INTO Hermes.
- **Outbound webhooks** — Hermes POSTs run results to a URL you own.

Messaging platforms are a separate system entirely (platform adapters in
config.yaml, plus cron `deliver=` targets). The only relationship: a messaging
platform's outgoing webhook can be the thing that triggers a Hermes inbound
webhook.

## /plan is a skill-backed one-turn mode

`/plan` is **not** in the slash-command registry (`hermes_cli/commands.py`
`COMMAND_REGISTRY`) — it works because typing `/<name>` loads a skill of that
name, i.e. it is the bundled `plan` skill (`software-development/plan`).

- It is one of the few `PROTECTED_BUILTIN_SKILLS` (`tools/skill_usage.py`), and
  the source comment explains why: the curator must NEVER archive it, because
  archiving silently turns `/plan` into "Unknown command" with no signal.
- Scope is ONE TURN: plan-only — no implementation, no project edits except the
  plan file, no mutating commands; read-only inspection allowed.
- Deliverable: a markdown plan at `.hermes/plans/YYYY-MM-DD_HHMMSS-<slug>.md`
  (relative to the active working directory, so it stays with the workspace on
  every backend). Profiles also carry their own `plans/` dir.
- **Two steps, same session, no restart and no persistent mode to exit**:
  `/plan` writes the plan and stops; your NEXT normal message ("execute the
  plan") does the work with the plan and full context still in the transcript.
  Not a separate process or a separate run command.
- The skill's own handoff for the execution half is
  `subagent-driven-development`: one fresh `delegate_task` per task with
  spec-compliance review then code-quality review before moving on.

## Answer shape for this class of question

This user asks capability questions in short bursts and explicitly caps length
("answer short"). Lead with the verdict, then the one or two facts that change
the decision; hold the exhaustive detail behind an offer to go deeper. When a
question can be settled by reading the live install, read it (per-profile
config, the source tree, `hermes <cmd> --help`) instead of reciting docs — and
name the file or command the answer came from. If a term the user used does not
exist as a field/command ("role", "/hook"), say so plainly first and then give
the nearest real concept.
