---
name: hermes-profile-admin
description: Create, clone, configure, and verify Hermes profiles.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, profiles, configuration, multi-agent, cloning]
    category: autonomous-ai-agents
    related_skills: [hermes-agent]
---

# Hermes Profile Admin Skill

Create, clone, and configure isolated Hermes profiles (independent config,
`.env`, SOUL.md personality, skills, sessions, and memory). This skill holds
the profile-specific workflow and the gotchas that the bundled `hermes-agent`
docs don't cover — load that skill for the full CLI reference, this one for
the profile path.

Reference files: `references/providers-and-fallback.md` (per-profile
model/provider/fallback), `references/per-profile-memory-providers.md` (the
MEMORY backend axis: `memory.provider` is per profile and NOT inherited from the
root config, `hermes -p NAME memory status` as the verification, the 8 provider
plugins, and why two profiles on one provider still share one store unless
`OPENVIKING_AGENT`/account are per-profile),
`references/custom-openai-compatible-endpoints.md`
(point a profile at your own / self-hosted OpenAI-compatible endpoint — the
`model.provider: custom` trust gate, the api_key resolution chain, the
`custom_providers` list, and what the endpoint must implement), `references/kanban-toolset-gating.md`
(the 12 `kanban_*` tools: the `check_fn` gate reads the TOP-LEVEL `toolsets` key,
NOT `platform_toolsets`, so a terminal-less profile can create and assign;
`hermes tools enable kanban` refuses; the working fix, its scalar-set pitfall,
and the offline verification recipe), `references/context-files-vs-skills.md` (SOUL.md vs
skill vs AGENTS.md loading semantics + the full per-profile isolation
surface), `references/automation-surface.md` (cron per profile, hooks vs
webhooks, `/plan` semantics), `references/mcp-vs-toolsets.md` (MCP is a
separate axis from toolsets: per-profile `mcp_servers`, the `no_mcp` sentinel,
deferred tool catalogs, the restart requirement), and
`references/concurrency-and-scopes.md` (what is per-profile vs machine-global:
delegation/cron/kanban caps, board-wide vs per-profile limits, and the kanban
dispatch cadence), and `references/toolset-change-propagation.md` (does a tool
toggle or MCP change need a gateway restart — the config→agent propagation path
with source line numbers), `references/toolset-enumeration-surfaces.md` (the four
surfaces that enumerate toolsets — 24/25/27/28 rows for the SAME profile — and
which one a "how many toolsets do I have / which are active" request means), and
`references/toolset-cost-and-quality-tradeoffs.md` (per-toolset quality / latency
/ token profile — what "which of your tools costs me time and tokens" means, the
compression amplifier, and the scope rule that the answer is built-in toolsets,
NOT MCP-provided tools), and `references/turn-latency-profiling.md` (decomposing
one turn's wall-clock into intake/bootstrap / recall+assembly / model call /
finalize — the send-a-message probe, the agent.log anchor table, the Langfuse
cross-check and its limits, plus worked numbers for a 4.5–5.3 s turn).
Starter SOUL copy:
`templates/coder-soul.md`.
Fleet MCP shut-off: `scripts/disable-mcps-fleet-wide.py` (every server in every
profile, comment/format-preserving splice, dry-run + `--restore`, two-layer
verification — see "Disabling an MCP Server Fleet-Wide" below).
Audit script: `scripts/profile-provider-audit.sh`.
Bulk sync script: `scripts/sync-soul-profiles.sh` (one profile per SOUL.md in a
source tree, with `.env` inheritance).
Re-sync script: `scripts/soul-tree-resync.py` (source tree edited after the
profiles exist — prints the per-profile delta, flags REMOVALS, backs up, mirrors).
Cap report: `scripts/session-cap-report.py` (per-profile `max_concurrent_sessions`
plus the live slot holders each profile's `runtime/active_sessions.json` records).
Toolset census: `scripts/list-profile-toolsets.py` (per-profile `name,active`
rows — offline via the real resolvers, or live via the dashboard API; `--csv`
writes the file).
Latency probe: `scripts/probe-profile-latency.sh` (one message through the API
server — curl timing + that turn's token usage) and
`scripts/turn-phase-report.py` (per-turn phase table read out of that profile's
own `logs/agent.log`).
Cross-machine clone: `scripts/pack-hermes-profile.sh` +
`scripts/unpack-hermes-profile.sh` (zip ONE profile minus machine-local bulk —
embedded manifest, re-entry guards, .env 600 fixups, alias re-creation; see
"Cross-Machine Profile Clone").
Dry-run SOUL behaviour harness: `references/soul-dryrun-testing.md` (scripted
profile tests — payload + stipulated tool data + pass checklist, MCP disabled
mid-run so writes are structurally impossible, replies extracted from the box
panel, negation-aware scoring).
SOUL quality review: `references/soul-quality-review.md` (grading one SOUL against a
standard soul as an executable program for low-end models — entity-field definitions,
the scored rubric, worked JSON traces, dedup/caps, live tool-claim verification, and
the finding-ledger method for re-review rounds).
Coverage audit: `references/soul-coverage-audit.md` + `scripts/soul-coverage-audit.py`
(does the SOUL fleet actually cover a page/functionality spec — tool names AND
their when-to-use definitions — plus page-attribution mismatches, absent tools,
tool-existence checks against the MCP implementation, and source-tree drift;
§10 audits inter-profile kanban handoff; §11 covers a USE-CASE/E2E spec read-only
— SOUL-rule vs platform-object vs missing-owner vs policy-conflict gap classes).
Same reference carries the two follow-ons: §9 APPLYING the fix
(`scripts/soul-section-edit.py` — idempotent, section-scoped, additive edits to
the source tree FIRST and then the mirrors, mirrored per-file backups, anchor
uniqueness assertion, post-write requirement re-scan) and §10 auditing
INTER-PROFILE INTERACTIVITY (kanban board creation, card-flow direction,
outbound destination profiles, generic "if important" trigger wording).
Authoring a NEW fleet-wide section (as opposed to reconciling one):
`references/soul-section-authoring.md` + `scripts/soul-section-author.py` +
`templates/fleet-section-spec.json` — the shipped spec IS the live
Inter-Profile Card Handoff section: shared `core` + a per-profile trigger block,
insert-or-upgrade in place, one patch per file against the pre-change baseline
(git HEAD for the source tree, mirrored backup for the mirrors), and the
no-backup-in-a-git-tree rule.

## When to Use

- "Create a profile named X" / "clone the default profile"
- "Update the profiles from the SOUL folder" / "the SOUL.md files changed, sync
  them again" — source tree wins, but the delta (especially removals) must be
  reported first: see "Re-sync" + `scripts/soul-tree-resync.py`
- Setting a per-profile personality (SOUL.md) or enabling tools/skills for one profile
- "How does a profile actually change ANOTHER profile's soul / MCPs / tools / skills?" / "is it through the files and config?" — one table answers it: "Change Surface" below (four axes have a `hermes -p <target>` CLI, three are file-edit-only)
- Verifying a profile actually boots with its keys, personality, and tools
- "Run these tests against the X profile" / "ask the profile to just show what
  steps it would do, NOT actually calling the MCP tools" — scripted dry-run
  behaviour tests with zero side effects: `references/soul-dryrun-testing.md`
- "Review this SOUL.md — treat <other soul> as the standard, what should be
  improved/added?" / "the soul should also work with low-end models (28B)" /
  "I updated the soul.md, re-analyze" — grade the SOUL as an executable program,
  not as prose: verify every tool/field/endpoint claim against the live MCP
  surface, score against the standard's structural devices, keep a findings
  ledger across rounds, and review-only unless asked to fix:
  `references/soul-quality-review.md`
- "Do the profiles/their SOUL.md cover this doc?" / "is X covered — the MCP tool
  mention AND the definition of when to use it?" / "which profile covers page Y?"
  — audit SECTION-block coverage (Intent/Trigger/Expected Behavior/Key
  Entities/Boundaries + the `W-bridge MCP Tools to Use` list), never prose or
  policy-block mentions: `references/soul-coverage-audit.md` +
  `scripts/soul-coverage-audit.py`
- "Review this E2E / use-case doc — do the profiles support these
  functionalities, and what should change in each SOUL? (do NOT change them)" —
  a read-only capability audit of BEHAVIOURS and lifecycle states, not page
  tools: enumerate with `find -iname`, sweep the capability vocabulary, check the
  MCP object surface, then classify each gap as SOUL-rule / platform-object /
  missing-owner / policy-conflict, and deliver the per-profile "what is
  required" without writing anything: §11 of `references/soul-coverage-audit.md`
- "…but the feature EXISTS in Bonfire / the w-bridge MCP — re-analyse the gaps" —
  the follow-on to the review above, and a correction: a missing heading in the
  MCP tool reference is NOT a missing capability. Re-check the WRITE PATH in three
  layers (Rails schema → `space/api/*.py` payload → `TOOL_DEFINITIONS` in
  `mcp/tools.py`), where a DB column is not a writable field and a design doc's
  proposed table is not an entity; then re-run the section×tool attribution matrix
  and lead the reply by correcting your own earlier verdict:
  `references/write-path-verification.md`
- "Should status items / project data live in memory, OV or NeuroStack so profiles
  don't have to read from w-bridge or Bonfire?" — the read-model question. Do not
  answer "yes, correct" or "no": split AUTHORITY (writes, approvals, audit stay in
  Bonfire/w-bridge) from MIRROR (vault/OV for reading), verify what the event
  pipeline actually carries before agreeing, and name the freshness-marker,
  scoping and coverage gaps: §"Read model vs authority" of
  `references/write-path-verification.md`
- "Use tool X for this in every profile's SOUL" — when the user names a tool
  inside the instruction, verify that tool's real semantics before shipping the
  wording; if it cannot do the job, implement as dictated AND report the gap with
  evidence rather than silently substituting another tool. Same reference,
  §"Dictated tool rules"
- "Fix it" / "reconcile the page attribution so the SOULs match the doc" —
  ADDITIVE, section-scoped edits, source tree first then the mirrors, dry-run
  before writing, anchor asserted unique, then verify by re-scan + backup diff
  line math: `scripts/soul-section-edit.py` + §9 of
  `references/soul-coverage-audit.md`
- "Add this rule / instruction to EVERY profile's SOUL" / "mention in the
  soul.md when a profile should create a card to send a task to another
  profile" — author a new governed section fleet-wide as data (shared core +
  per-profile patterns), insert before `## Memory & Knowledge Separation`,
  source tree first, patches per file with no backup in the git-backed tree:
  `scripts/soul-section-author.py` + `templates/fleet-section-spec.json`,
  explained in `references/soul-section-authoring.md`
- "so did you consider …" / "you missed the two-or-more case" about a rule you
  just wrote — that is a revision, not a rewrite: upgrade the section in place
  (never append a second copy), keep the superseded wording in the spec's
  `forbids` list so `--verify` proves no file kept it, and lead the reply by
  naming your own draft's defect: §5 of `references/soul-section-authoring.md`
- "Do the profiles tell each other to hand work over via kanban?" / "if
  something important or required comes up, can a profile create a board and
  assign a card to another profile?" — four axes (board creation, card-flow
  direction, outbound destination profiles, generic trigger wording) plus
  channel-enforcement and competing-mechanism checks: §10 of
  `references/soul-coverage-audit.md`
- "How many toolsets do I have?" / "list my toolsets and whether they're active"
  / "make me a CSV of them" — the count depends on WHICH surface you count from
  (24, 25, 27 or 28 for one profile): `references/toolset-enumeration-surfaces.md`
  + `scripts/list-profile-toolsets.py`
- "Which of your active tools increases quality but also response time and token
  usage?" / "what should I turn off to make you faster/cheaper?" — built-in
  toolsets only (MCP tools are the separate axis; do not answer with them unless
  asked): `references/toolset-cost-and-quality-tradeoffs.md`
- "Why is profile X slow?" / "send a message to the knowledge profile and see what
  makes the whole time of response" / "where do the seconds go?" — probe ONE real
  turn and decompose it instead of reasoning from config:
  `scripts/probe-profile-latency.sh` + `scripts/turn-phase-report.py`, explained in
  `references/turn-latency-profiling.md`
- "What differs between profiles?" / "Where does this rule go — SOUL.md or a skill?"
- "Can one profile use several providers / fall back between them?" (see
  `references/providers-and-fallback.md`)
- "Could different profiles use different MEMORY — one on OpenViking, another on
  something else?" / "is memory per profile or shared?" — YES, and it is NOT
  inherited from the root config; verify with `hermes -p NAME memory status`,
  then answer the second half (two profiles on the same provider still share one
  store until the provider's own scope vars are per-profile):
  `references/per-profile-memory-providers.md`
- "Could I use my own / a custom / a dummy API endpoint instead of DeepSeek?" /
  "point Hermes at my self-hosted OpenAI-compatible server" / "I set
  `model.base_url` and nothing changed" — read the trust gate and key chain in
  `references/custom-openai-compatible-endpoints.md` before answering; the
  bundled provider docs omit both
- "Should this env var / API key / plugin be added to ALL profiles?" / "I
  changed the default `.env` — why doesn't profile X see it?" (per-profile
  snapshot semantics, see Pitfalls)
- "Delete profile X" / "stop tracing profile X" — distinct requests, see
  Pitfalls before removing anything
- "Remove all profiles except default" / "the gateway is fine without a
  restart, right?" after a fleet teardown — chunked delete + smart-exclude
  archive + live verification: "Bulk Profile Delete"
- "Clone profiles to another machine" / "make two machines identical with
  minimal copy" / "how is profile X 66M of disk" — the three-layer portability
  rule and the pack/unpack pair: "Cross-Machine Profile Clone"
- "Explain cron / scheduled jobs for a profile", "is /hook messaging", "what is
  /plan" (see `references/automation-surface.md`)
- "Does using MCP require the terminal tool?" / "which profiles can call
  MCP server X?" / "why aren't my MCP tools there?" (see
  `references/mcp-vs-toolsets.md`)
- "Can a profile without terminal (or file/code_execution) access create and
  assign kanban tasks for other profiles?" / "why doesn't this profile have any
  kanban tools even though `platform_toolsets.cli` lists `kanban`?" — kanban is
  its own axis gated by the TOP-LEVEL `toolsets` key, and
  `hermes tools enable kanban` refuses: `references/kanban-toolset-gating.md`
- "Disable MCP X for all profiles" / "turn off the Obsidian MCP everywhere" /
  "disable ALL MCPs in all profiles"
  (no `hermes mcp disable` exists — per-server `enabled: false`; see
  "Disabling an MCP Server Fleet-Wide" below)
- "Disable terminal / file / code execution on all profiles except X"
  (fleet-wide fail-closed lock-down — see "Fleet-Wide Toolset Lock-Down"
  below; do NOT just edit `platform_toolsets.cli`)
- "I enabled/disabled a tool — do I need to restart the gateway?" / "my new tool
  isn't showing up" (no for toolsets — see "Does a Tool Toggle Need a Gateway
  Restart?" and `references/toolset-change-propagation.md`)
- "Does a profile need the terminal/file toolset to read or write its skills?" /
  "are skills shared between profiles?" (no, and no — see
  `references/context-files-vs-skills.md`)
- "Is that cap / interval per-profile or global?" — delegation, cron, kanban
  limits and the kanban dispatch cadence (see
  `references/concurrency-and-scopes.md`)
- "Is `max_number_of_workers` / `max_workers` per profile?" — a setting name you
  don't recognize: grep it before answering. `max_number_of_workers` is NOT a
  Hermes key (zero hits in `$HOME`, the source, and the docs bundle); the real
  pair is `delegation.max_concurrent_children` + `delegation.max_spawn_depth`,
  both per profile. Two traps to state: `hermes config get` reports the
  effective DEFAULT, not "is pinned" (all 16 profiles here pin only
  `max_iterations: 50`), and "$HERMES_HOME` is the resolution root" is provable
  on a throwaway home without touching a live profile — see
  `references/concurrency-and-scopes.md` §"Key names users reach for that do NOT
  exist" and §"Proving per-profile resolution".
- "Is there a max number of running sessions?" / "can I cap it globally?" / "why
  did a kanban worker die instantly?" — chat-session slots vs task caps:
  `max_concurrent_sessions` is per profile yet shared across that profile's
  CLI/TUI/dashboard/gateway surfaces, and only the messaging gateway needs a
  restart (see `references/concurrency-and-scopes.md`, plus
  `scripts/session-cap-report.py` for the live value + holders)

## Built-in Portability Commands (check these BEFORE hand-rolling copy scripts)
Live-verified 2026-11-04 (hermes --help + hermes profile --help + measured runs):
- `hermes profile export NAME [-o file.tar.gz]` / `hermes profile import ARCHIVE [--name NAME]` — per-profile snapshot; import renames via `--name`. Default export dir: `~/.hermes/profile-exports/`.
- `hermes backup [-o zip] [-q|--quick] [-l label] [-k N]` / `hermes import zipfile [--force]` — FULL home zip (config+skills+sessions+data, excludes hermes-agent codebase; `--quick` = just config/state.db/.env/auth/cron).
- `hermes profile install <git-url|dir>` / `update` / `info` — profile DISTRIBUTION path with a manifest; the right mechanism for fleet-reinstall across machines.
- Exclusion authorities live in `hermes_cli/profiles.py` (`DEFAULT_EXPORT_EXCLUDE_ROOT` root-allowlist; comment: "export uses a root allow-list, a clone must run") and `hermes_cli/backup.py` (`_EXCLUDED_ROOT_DIRS`, `_KEPT_CACHE_SUBDIRS`).
Two gotchas measured on `ai_settings` (66M folder):
1. Export's exclude list is ROOT-SCOPED: inside a named profile it still carries `skills/.hub` (48M index), `.curator_backups`, `logs/`, `*cache/`, a few sessions/state entries → 17.7M tar.gz vs 2.9M for a hand-rolled zip with depth-independent prunes (`-name .hub` style, NOT `-path '*/x'` which misses top-level entries — find starts from the bare name).
2. Export DELIBERATELY EXCLUDES `.env` + `auth.json` ("an archive is a portable snapshot" = no secrets). So `export`+`import` alone gives a key-less profile (see the "no API keys" Pitfall) — transfer `.env` separately over ssh, then `chmod 600` and smoke-test.
## Converting a Live Profile into a Distribution Repo
`~/hermes-clone/to-profile-dist.sh PROFILE -o DIR [-V ver] [-r git-url] [-b branch] [--no-git] [--force]` (built + install-verified 2026-11-04). Contract it enforces, all live-verified against `hermes_cli/profile_distribution.py` and a scratch-home `hermes profile install`:
- Root `distribution.yaml` (only `name` mandatory; `version`, `description`, `env_requires[{name,description,required}]`, `distribution_owned` overrides DEFAULT_DIST_OWNED = SOUL.md config.yaml mcp.json skills cron + manifest).
- cron: ONLY `cron/jobs.json` is distribution-owned; every other cron/* file (executions.db, output/, ticker_*) is runtime state the installer must not write.
- `skills/.*` top-level entries (`.hub`, `.archive`, `.curator_backups`, `.locks`) are bookkeeping the installer CANNOT write — archived skills are silently unshippable; report the count instead of shipping them.
- `.env` + `auth.json` never ride the repo; ship `.env.template` (NAME= lines) → installer turns it into `.env.EXAMPLE` and flags env_requires as "needs setting" at install time.
- Leak-scan regex needs WORD BOUNDARIES + long runs (`\bsk-[A-Za-z0-9]{16,}`): bare `sk-[A-Za-z0-9]{10,}` false-matches "task-concu[r]ency"; scan `git ls-files`, not the tree, to skip .git/index.
- `install` from a LOCAL DIRECTORY also copies README.md/.git into the profile dir (cosmetic noise, not the git-URL path); update semantics: dist-owned overwritten, user data (memories/sessions/.env/auth) untouched, config.yaml preserved unless `--force-config`.
## Prerequisites

- `hermes` CLI on PATH (global flag `-p/--profile NAME` applies any subcommand to a profile: `hermes -p coder config show`)
- Profiles live under `~/.hermes/profiles/<name>/` (or `$HERMES_HOME` when a profile is active)

## How to Run

```bash
hermes profile create NAME --clone-from SOURCE --description "one-two sentence role description"
```

- `--clone` copies config.yaml, `.env`, SOUL.md, and skills from the ACTIVE profile.
  Prefer `--clone-from SOURCE` to name the source explicitly instead of depending on which profile is active.
- `--description` feeds the kanban orchestrator's task routing (role, not just name).
- An alias wrapper is auto-created at `~/.local/bin/<name>`; the new profile shows up in `hermes profile list` with a `◆` on the active one.

## Quick Reference

| Task | Command |
|---|---|
| Create/clone | `hermes profile create NAME --clone-from SOURCE --description "..."` |
| List | `hermes profile list` |
| Per-profile config | `hermes -p NAME config get/set KEY` |
| Per-profile tools | `hermes -p NAME tools list --platform cli` / `tools enable TOOLSET --platform cli` |
| Show details | `hermes profile show NAME` / `describe NAME` |
| Delete | `hermes profile delete NAME -y` (alias goes too; bulk: "Bulk Profile Delete") |
| Smoke test | `hermes -p NAME chat -Q -q "..."` |
| Scripted one-shot (multiline/quoted prompt) | `hermes -p NAME chat --query-file FILE --oneshot` — `--query-file` preserves quotes, backticks and `$(...)` verbatim; use it for any prompt embedding SOUL text or JSON payloads (`-q` risks shell mangling) |

## Change Surface — every axis a cross-profile write touches

| Axis | How the change lands |
|---|---|
| SOUL.md | File edit ONLY — no CLI; writes via file tools are human-approval-gated |
| Profile create/delete/describe/show | `hermes profile <cmd> NAME` (name is POSITIONAL here, `-p` is not read by it; `describe --text` sets it) |
| MCP add/remove/test/tool selection | `hermes -p <target> mcp add / remove / test / configure` (`add` is interactive — pipe answers) |
| MCP server on/off | File edit `mcp_servers.<n>.enabled: false` — no CLI; read back with `hermes -p <target> mcp list` (`✗ disabled`) |
| Builtin toolsets + MCP tools | `hermes -p <target> tools enable / disable NAME`; MCP tools use `server:tool` notation |
| Skill install/uninstall/update | `hermes -p <target> skills install / uninstall / update / check / list` |
| Skill enable/disable | File edit the `skills.disabled:` list (read at session build; no CLI toggle) |
| Settings keys | File edit preferred — `hermes config set` is scalar-only and silently drops all comments |
| Secrets / `${VAR}` resolution | `<target>/.env` — copied at create time, never live-synced |

Timing is one rule: nothing applies mid-session. SOUL/toolset/skill changes land at the target's next new session (`/reset`); MCP server changes at its next start (gateway-only live path: `/reload-mcp`).

## Procedure

1. **Create**: `hermes profile create <name> --clone-from default --description "..."`.
2. **Personality**: write `<profile>/SOUL.md`. It is plain markdown injected as
   system-prompt identity slot #1 (`agent/prompt_builder.py::load_soul_md`).
   Cover identity, working style, communication rules, and boundaries (e.g. a
   coder profile: read-before-change, verify with real execution, no commits
   unless asked, no drive-by refactors). Starter copy:
   `templates/coder-soul.md`.
   **Approval gate**: a `SOUL.md` write through the file tools raises a human-approval
   prompt; a timeout blocks the write and bypassing it via terminal/execute_code is
   forbidden ("silence is not consent"). On a block, park the drafted text as an
   adjacent `SOUL-upgraded.md` (a content draft, not a backup copy) for the user to
   review and `cp`, or re-attempt once and ask the user to answer the prompt.
3. **Tools**: the clone inherits the source's `platform_toolsets.<platform>`
   lists. Add known toolsets with `hermes -p NAME tools enable X --platform cli`.
   Do NOT try to enable posture toolsets (see Pitfalls).
4. **Skills**: bundled skills are enabled by default; only `skills.disabled` /
   `skills.platform_disabled` turn them off. A clone inherits them all —
   "enabling" means confirming the relevant category exists under
   `<profile>/skills/` and nothing is disabled in its config.
5. **Verify** (below).

## Bulk Sync From a SOUL Directory (repo-driven profiles)

When a project keeps its agent identities as a tree of SOUL files (e.g.
`<repo>/hermes/profiles/<group>/<soul-dir>/SOUL.md`) and wants one Hermes
profile per soul, use `scripts/sync-soul-profiles.sh` instead of hand-running
`hermes profile create` N times:

```bash
bash scripts/sync-soul-profiles.sh /path/to/profiles \
     [--clone-from default] [--dry-run] [--desc-file descriptions.tsv] [--skip NAME]
```

Layout it expects: `SOURCE/<group>/<soul-dir>/SOUL.md` (`SOUL.MD` accepted
too; group depth arbitrary; `example` skipped by default). The soul-dir name
becomes the profile id — lowercased, spaces → underscores, because the id must
match `[a-z0-9][a-z0-9_-]{0,63}` (so `normal message` → `normal_message`).

Per soul, idempotently: (1) `hermes profile create NAME --clone-from
<clone-from>` if the profile is missing; (2) copy the SOUL to
`<profile>/SOUL.md`, backing up the old one *only if it differs*; (3) copy the
default profile's `.env` over (`chmod 600`) so keys are inherited; (4) set a
role description via `hermes profile describe` **only when the profile has no
`profile.yaml`**, so a curated description is never clobbered. Re-running is a
no-op (`created=0`) — that is the acceptance test.

Then verify (see Verification below) — creation alone proves nothing about the
`.env`, MCP, or skill inheritance of profiles that already existed.

### Re-sync: "update the profiles from the SOUL folder again"

The source tree is authoritative and the profile SOULs are mirrors, so a repeat
request means: diff → report → mirror, never a blind overwrite. Run
`python3 scripts/soul-tree-resync.py <SOURCE_TREE>` (dry-run first, `--apply` to
write). What the run must produce, because the user reads the delta:

1. **Map by the file's own parent directory** — group dirs (`main/`, `bots/`)
   are not profiles; the leaf dir name is the id, lowercased, spaces →
   underscores (`main/normal message` → `normal_message`). `SOUL.MD` counts too.
2. **Print additions AND removals per profile.** Removal hunks are the ones that
   need eyes: they are either a deliberate edit by the user or a truncated save.
   List the removed lines (first few per hunk) verbatim in the reply so the user
   can catch the second case. Do NOT silently "restore" them.
3. **Back up the previous profile SOULs** to
   `<profiles>/.soul_backup_<YYYYmmdd_HHMMSS>/<profile>__SOUL.md` before writing
   (dot-prefixed, so the sweep never mistakes it for a profile — see Pitfalls),
   and keep the earlier backups around instead of overwriting them.
4. **Verify by re-reading bytes** (`open(src,'rb').read() == open(tgt,'rb').read()`)
   for all N targets, then run `hermes profile list` to prove the fleet still
   enumerates. `soul-tree-resync.py --apply` now does that re-read itself and
   prints `byte-verified after write: N/N targets`; a failed or non-identical
   write is reported as `WRITE-FAILED (<err>)` / `WRITE-MISMATCH` per profile,
   the batch still finishes, and the exit code goes 1 (it previously crashed on
   the first PermissionError and left the rest of the fleet unwritten with no
   report). SOUL.md is read per session, so no gateway restart is involved —
   say that explicitly rather than leaving the user to guess.
5. **Leave profiles with no source folder alone.** On this box that is `default`
   (`~/.hermes/SOUL.md`, which carries the Bonfire Collaboration Rules) and
   `testprofile`; the tree has no folder for either, so they are out of scope of
   "update all souls" and must be named as untouched in the reply.

In practice the tree moves in BOTH directions between rounds: round 1 the sources
were strict SUPERSETS of the loaded files (additions only: the raw three-bullet
memory list plus the appended `SECTION-xx` Bonfire page blocks — a straight byte
copy was safe, and that was verified before writing); round 2 the sources had
been edited to DELETE every `#### Related Profiles` cross-reference list
(action 2, company 2, …, company_project 5 — 38 blocks total) and no additions;
round 3 (2026-09-17) the sources gained per-role `#### W-bridge MCP Tools to Use`
blocks under each SECTION-xx (additions only, +206 lines across 13 files — still
a superset, so lossless); round 4 the same day added two NON-SECTION top-level
policies to 12 of 13 files — `## Approval Request Tool Policy (2026-09-17)`
(all 12; prefers `add_approve_request_with_message` over `add_approval_request`)
and `## Workspace Bot Identity Policy (2026-09-17)` (the 7 execution-side
profiles: action, company, company_project, cron_profile, knowledge,
normal_message, not_known_task) — plus ONE tool-name swap in the three files
that carried the old bullet. Same command both times, different verdict in the
report. So check the direction of the diff every round instead of assuming "the
source is newer therefore richer" — this is the difference between a safe copy
and quietly dropping content the user still wanted.

Round 5 (2026-09-23, commit `bec4431`): a two-part request — "update all SOUL
profiles AND create the config profile from the related SOUL, clone it from
default first". Order matters: create the profile FIRST, then resync, or the
script only tells you `MISSING profile dir for main/config -> config` (exit 1)
and that profile is left at its cloned SOUL. After the clone +
`soul-tree-resync.py --apply`, the run reads 14 changed / 88 removed lines but
the only large removal is the NEW profile's cloned boilerplate SOUL being
replaced by the real W Config SOUL (-81/+45) — expect that on any
create-then-sync combo and say so instead of presenting it as data loss. Other
deltas that round: `delegator` gained `config` in its "main profiles are …" line
plus routing rules to/from `config`; `ask_from_w` had its relay bullets replaced
by an Access and Authorization Policy; every non-coder file got the
Obsidian→Memory MCP fallback line.

Two things that make an edit round ambiguous, both seen in round 4, so surface
them instead of deciding silently:

- **A file the user did NOT touch is a question, not a no-op.** `delegator` was
  byte-identical between source and mirror that round, which is exactly what a
  freshly-synced profile looks like — but it also means its source still carries
  `add_approval_request`, the tool-name the other 12 files just renamed away
  from. Report "X is unchanged / still has the old token" and let the user say
  whether it was deliberate; do NOT extend the policy to it on your own.
- **The shared spec file can drift from the SOULs it feeds.** In this repo
  `hermes/shared/profile-knowledge-sections.md` is the documented origin of the
  appended `SECTION-xx` blocks, and that round it received the tool-name swap
  (line 48) but NOT the two new top-level policies, which exist only in the 12
  SOULs. Mirroring the SOULs is the requested job; note the divergence in the
  reply (it affects the next regeneration) rather than editing the spec file.

## Bulk Profile Delete ("remove all profiles except default")

Fleet teardown. The per-profile rules of `hermes profile delete` still apply
(see Pitfalls), plus these batch mechanics:

1. **Enumerate from the CLI, cross-check the directory.** `hermes profile list`
   is the registry; `~/.hermes/profiles/` holds dot-prefixed decoys
   (`.soul_backup_*`, the CLI's `.deleted` quarantine stub) that are NOT
   profiles. **`default` has no directory there** — its home IS `~/.hermes` —
   so a correct full sweep leaves `profiles/` empty while `default` still
   lists; do not "fix" that.
2. **Archive before deleting, but archive smart — never tar the raw trees.**
   Most of a profile dir is re-downloadable infrastructure (`node/`, `bin/`,
   `lsp/`, `logs/`, `cache/`, `sandboxes/`, `telemetry/`), and a 16-profile
   fleet is ~1.8G on a disk that may have <4G free. Check `df` first, then per
   profile:

   ```bash
   tar czf bk/<name>.tar.gz -C ~/.hermes/profiles \
     --exclude='*/node' --exclude='*/bin' --exclude='*/lsp' --exclude='*/logs' \
     --exclude='*/cache' --exclude='*/sandboxes' --exclude='*/telemetry' <name>
   ```

   Keep-worthy state (config.yaml, `.env`, SOUL.md, profile.yaml, skills/, `cron/`,
   memories/, sessions/, kanban/) survives; a whole fleet archives at ~280M.
   Restore: extract into `~/.hermes/profiles/`; the alias is recreated with
   `hermes profile alias NAME` (`hermes -p NAME` works without it anyway).
3. **Budget 30–60 s per profile and chunk the batch.** One loop over 15+ profiles
   blows a terminal timeout mid-sweep. After a timeout, NEVER re-run the whole
   loop — re-enumerate the survivors (`ls ~/.hermes/profiles/`) and delete only
   those.
4. **The first `hermes` call in the loop auto-completes any pending source
   update** (the `a source update is unfinished` banner): it runs a full
   dependency + skills + config sync inside your batch, takes minutes, and
   changes the installed version mid-operation. Report it as a side effect in
   the final reply; do not treat it as an error or retry.
5. **Verify three surfaces**: `hermes profile list` shows only `◆default`,
   `ls ~/.hermes/profiles/` is empty apart from the dot decoys, and the deleted
   aliases are gone from `~/.local/bin`.

**"Do I need to restart the gateway after that?" — usually No, and verify
rather than assume.** `hermes profile delete` prints `⚠ Gateway is running —
it will be stopped` for EVERY profile, yet the gateway can survive the whole
sweep — check `systemctl --user show hermes-gateway -p
ExecMainStartTimestamp` against the delete times before repeating the warning
as fact. Even when the running gateway booted while all the profiles existed,
no restart is needed:

- The gateway re-resolves its profile registry live: `hermes cron status`
  prints "the host gateway (PID N) serving profiles <list>" — deleted profiles
  fall out on their own, with no stale jobs.
- Profile resolution is per-request (the same mtime-keyed config path as "Does
  a Tool Toggle Need a Gateway Restart?"), so `/p/<deleted>/…` fails cleanly on
  the missing directory. No ghost routing.
- What a long-lived gateway does keep is cached agents for the deleted profiles
  in RAM. Frame a restart as an OPTIONAL memory cleanup ("harmless, frees
  RSS"), never as a correctness requirement.

## Cross-Machine Profile Clone ("same profiles on two machines, minimal copy")

A Hermes install is THREE layers and only the middle one is portable — the
answer to "copy my profiles to machine B" is a layer choice, not a raw copy.
Diagnose bulk in a profile folder with `du -ah <profile> | sort -rh | head`:
the first entry is usually one cache file, not the profile's content.

1. **Machine-global runtime — NEVER copy**: `hermes-agent/`, `node/`, `bin/`,
   `lsp/`, `tools/`, `installs/`, `sandboxes/`, `telemetry/` under the
   `$HERMES_HOME` root. Architecture- and path-specific; reinstall hermes on
   the target instead.
2. **Profile state — what you transfer**: `config.yaml`, `.env`, `SOUL.md`,
   `profile.yaml`, `skills/` minus `.hub`, `plugins/`, `memories/`, `cron/`,
   `hooks/`, `platforms/`, `pairing/`, `plans/`, `workspace/`, `kanban/` minus
   `_archived` boards and `boards/*/workspaces`, `kanban.db`.
3. **Local caches — exclude; they regrow on the target**: `skills/.hub/`
   (a single ~48M JSON listing ~100k skills, re-downloaded on first hub browse
   and duplicated per profile), `.curator_backups/`, `cache/`, `logs/`,
   `runtime/`, `image_cache/`, `audio_cache/`, `plugin-update-checks/`,
   `*.lock`, `*.db-shm`/`*.db-wal`, `*.bak*`, `__pycache__`,
   `cron/ticker_heartbeat` + `cron/ticker_last_success`. `sessions/` +
   `state.db*` are chat HISTORY, not identity — include only on explicit ask
   (`--include-sessions`).

**`default` has no profile folder** — its home IS the `$HERMES_HOME` root — so
cloning default is an allow-list subset of the root (layer 2), never a copy of
the whole 7.8G home.

Procedure — pack on A, unpack on B:

```bash
scripts/pack-hermes-profile.sh ai_settings -o ai_settings.zip   # any named profile
scripts/pack-hermes-profile.sh default   -o default.zip         # root allow-list subset
scp *.zip user@B:~/
# on B, AFTER a fresh hermes install:
scripts/unpack-hermes-profile.sh default.zip     -t ~/.hermes --force
scripts/unpack-hermes-profile.sh ai_settings.zip -t ~/.hermes
```

`pack` embeds a `.profile-manifest` (profile name, mode, origin) that `unpack`
reads and dispatches on: named → clean import to `<target>/profiles/<NAME>`
(refuses a non-empty target without `--force`, which moves the old dir aside to
`<NAME>.pre-import-<ts>` — never deletes — or `--merge` to overwrite in place);
default → MERGES into the target root, backing up the target's own
`config.yaml/.env/SOUL.md/profile.yaml` to `backups/pre-import-<ts>/` first.
Unpack then `chmod 600`s the `.env`, recreates the CLI alias, and verifies.
`--as NAME` renames on import (possible because entries are stored relative to
the profile dir). Measured: 66M named profile → 2.9M zip; default → 4.1M /
854 files; round-trip into a throwaway `HERMES_HOME` byte-identical except the
excluded machine-local bits. For a one-off fleet archive before a teardown, the
same layer rules apply — see "Bulk Profile Delete".

For RECURRING identity (two machines stay equal), rsync beats re-packing:
`rsync -a --delete` with the same exclude set over `~/.hermes/profiles/`, plus
the layer-2 root files for default. `--delete` converges both directions; a zip
only adds.

Pitfalls (each cost a re-do while building these scripts):

- **GNU find `-path '*/x'` does NOT match when the traversal starts at a bare
  relative name**: `find kanban` yields paths `kanban/...` with no leading
  component for `*/` to consume, so the prune silently keeps everything
  (~22M of archived board bulk slipped into the zip). Write prefix-agnostic
  patterns (`*kanban/boards/_archived`) or always `cd` + `find .`.
- **Never prune common dir names (`scripts`, `bin`, `tools`, `cache`) at
  arbitrary depth with `-name`** — skills legitimately ship `scripts/` and
  `bin/` subtrees, and a `-name scripts` prune deletes skill payload silently.
  Prune those only path-anchored at the tree root (`-path './bin'`);
  arbitrary-depth name-prunes are safe only for pure artifact names
  (`__pycache__`, `*.lock`, `*.bak-*`, `.hub`, `.curator_backups`).
- **Do not store the profile dir's own name as the zip entry prefix** —
  extracting such a zip INTO `profiles/<name>/` double-nests it
  (`profiles/<name>/<name>/...`) and `.env`/`SOUL.md` land at the wrong level.
  Entries relative to the profile dir; the unpacker chooses the folder name —
  which is what enables `--as` renames.
- **Verify an import against the TARGET's registry**: `HERMES_HOME=<target>
  hermes profile list`. A bare `hermes profile list` queries the live home on
  the SOURCE machine, shows the original profile, and reads as a pass for an
  import that may not exist anywhere.
- zip preserves unix perms so `.env` arrives 600, but the zip CONTAINS API
  keys — scp/rsync-over-ssh only, never a cloud drop or shared archive.
- Both machines running gateway/cron at once double-fires jobs — schedule on
  one box. And the unpacker refusing a nonexistent target home is CORRECT
  behaviour (install hermes there first), not a friction to bypass.

## Fleet-Wide Toolset Lock-Down (`agent.disabled_toolsets`)

To remove a toolset (terminal, file, code_execution, …) from EVERY entry point of
a profile, edit `agent.disabled_toolsets` — not the per-platform lists.

Why the per-platform route fails: `platform_toolsets` is an ALLOWLIST keyed by
platform, and the platform that matters for bots is not `cli`. W-bridge/bot
traffic calls the multiplexed API server (`/p/<profile>/v1/chat/completions`),
and `gateway/platforms/api_server.py` resolves via
`_get_platform_tools(config, "api_server")` — falling back to the
`hermes-api-server` platform default when the key is absent (which it is in most
fleets), and that default INCLUDES terminal/file/code_execution. So a profile
can show a terminal-free `cli` list while still handing a bot a shell. Same
class of hole: the `cron` platform key, and messaging-platform composites.

`agent.disabled_toolsets` is subtracted LAST inside
`tools_config._get_platform_tools()` ("This runs last so it overrides everything
above"), so one list covers cli, api_server, cron, every messaging platform, and
delegated subagents (`tools/delegate_tool.py` inherits parent
enabled/disabled). `cron/scheduler.py::_resolve_cron_enabled_toolsets` merges it
into its disabled list too, so per-job `enabled_toolsets` can't re-enable it.

Procedure (no CLI can do this — the key is a list, and
`hermes config set` writes scalars only):

```python
import re, shutil, datetime
block = "  disabled_toolsets:\n  - terminal\n  - file\n  - code_execution\n"
p = f"/home/user/.hermes/profiles/{name}/config.yaml"
t = open(p).read()
assert not re.search(r"^\s*disabled_toolsets:", t, re.M)      # idempotence
shutil.copy2(p, p + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
lines = t.split("\n")
i = next(i for i, l in enumerate(lines) if l.startswith("agent:"))  # top-level agent:
lines[i+1:i+1] = block.rstrip("\n").split("\n")
open(p, "w").write("\n".join(lines))
```

Surgical insertion (not a YAML round-trip) is deliberate: configs carry
comments a `yaml.dump` would erase. Back up first, insert right after the
top-level `agent:` line, then verify.

Verify in two layers.

1. Offline, per profile — fresh process, `HERMES_HOME` set, so nothing is
   cached across profiles:

```python
import os, sys; os.environ["HERMES_HOME"] = home
sys.path.insert(0, "/home/user/.hermes/hermes-agent")
from hermes_cli.config import load_config
from hermes_cli.tools_config import _get_platform_tools
cfg = load_config(); blocked = {"terminal", "file", "code_execution"}
for plat in ["cli", "api_server", "cron", "telegram", "discord"]:
    leak = blocked.intersection(_get_platform_tools(cfg, plat))
    print(plat, "LEAK:" + ",".join(sorted(leak)) if leak else "CLEAN")
```

2. Live, through the running gateway — proves it took effect without a restart
   (config reads are mtime-keyed, so no gateway restart is needed):

```bash
K=$(python3 -c "import yaml;print(yaml.safe_load(open('$HOME/.hermes/config.yaml'))['API_SERVER_KEY'])")
curl -s -H "Authorization: Bearer $K" http://127.0.0.1:8642/p/<profile>/v1/toolsets
# -> {"platform":"api_server","data":[{"name":"terminal","enabled":false},...]}
```

The endpoint reads the profile's own config (HERMES_HOME override from the
`/p/<profile>/` prefix) and reports `platform: "api_server"` — it is the same
resolution the agent gets, minus MCP (called with
`include_default_mcp_servers=False`, so a configured MCP server stays enabled
even though it isn't listed).

Caveats:
- **Entries must be exact toolset KEYS, not UI labels.** Users dictate from the
  Built-in Toolsets UI, which shows labels; map them before writing or the entry
  silently no-ops. Live mapping (this install):
  `Computer Use (macOS/Windows/Linux)`→`computer_use`,
  `Discord Server Admin`→`discord_admin`,
  `Discord (read/participate)`→`discord`,
  `Speech-to-Text`→`stt`, `BFL FLUX 3 Video`→`bfl`, `Text-to-Speech`→`tts`,
  `Image Generation`→`image_gen`, `Vision / Image Analysis`→`vision`,
  `Video Analysis`→`video`, `Video Generation`→`video_gen`. Doubt: enumerate
  `_get_effective_configurable_toolsets()` from `tools_config.py` and print
  `key | label`. Watch for near-neighbours — `video` vs `video_gen` are separate
  rows, so "disable the video ones" needs both named explicitly.
- A profile with NO `config.yaml` (a bare `profiles/<name>/` with only `cron/`)
  cannot be locked down until one exists — `load_config()` then returns built-in
  defaults. Create a minimal `config.yaml` holding just `agent:` +
  `disabled_toolsets:`. Note such a profile also has no `API_SERVER_KEY`, so its
  `/p/<name>/v1/toolsets` route answers `Invalid gateway API key` and can only be
  verified offline (layer 1).
- Importing `hermes_cli.*` while pointed at a bare profile creates empty
  `hooks/`, `pairing/`, `skills/` scaffolding dirs. `rmdir` them if you want the
  tree left exactly as found.
- Reversing = delete the `disabled_toolsets` lines (keep the backup path in the
  report so the user can diff/restore).
- **Lock-downs arrive in BATCHES — each batch is scoped to the items it names.**
  A follow-up "also disable A, B, C for all profiles" means apply A/B/C; it does
  NOT re-open the scope decision made for the previous batch. Failure mode to
  avoid: keeping one accumulated DENY list in the script and unioning it into
  every profile, which silently revokes an exemption the user granted earlier.
  This happened in-session — the accumulated 11-item list was written to the two
  profiles deliberately exempted from terminal/file, and had to be pulled back
  out mid-turn. Rules: drive each batch from that batch's own key list; decide
  per profile between "append to the existing block" and "leave untouched"; and
  print a per-profile `declared(...)` diff in the report so over-reach is visible
  in the very next command. Re-read the standing exemption list before every
  batch (here: `default` + `coder` keep terminal/file/code_execution).
- **Appending to an existing block is a different edit from creating one.**
  Batch 1 inserts after the top-level `agent:` line; batch N must locate the
  existing `disabled_toolsets:` key, consume the following `- ` item lines,
  diff against the new keys, and splice. Verify by re-reading the declared list
  per profile, not by trusting the write.
- `hermes profile list` / `hermes tools list` do NOT show this switch, so state
  it explicitly in the reply; a user re-enabling via the Desktop Toolsets UI will
  find the toggle "saves" but stays off (`tools_config.py` clears
  `agent.disabled_toolsets` only for toolsets the user re-enables for a platform).

## Does a Tool Toggle Need a Gateway Restart?

**No — not for a built-in toolset toggle.** Same answer for every platform key
(`cli`, `telegram`, `api_server`, …): the gateway re-reads config per message and
rebuilds its cached agent when the toolset set changes. Verified in source:

- `hermes tools enable/disable X` persists into `platform_toolsets.<platform>`
  (`hermes_cli/tools_config.py` ~L2527-2566) — no CLI writes lists, which is also
  why the fleet lock-down above is a hand edit.
- Per message the gateway runs `_load_gateway_config()` (mtime-keyed raw-yaml
  cache → an edit on disk is visible immediately) then
  `enabled_toolsets = sorted(_get_platform_tools(user_config, platform_key))`
  (`gateway/run.py` ~L24038-24044; background-task path ~L19233-19251).
- The cached AIAgent is keyed by `_agent_config_signature(...)`, whose blob
  includes `sorted(enabled_toolsets)`, plus `_CACHE_BUSTING_CONFIG_KEYS` — a
  tuple that explicitly lists `("agent", "disabled_toolsets")`
  (`gateway/run.py` ~L22225-22247, signature ~L22336-22402, commented as
  values "baked at construction" that would otherwise be silently ignored until
  some other eviction). A toolset edit therefore changes the signature, the
  cached agent is discarded and rebuilt on the NEXT message, and the new toolset
  is live. No gateway restart, no manual eviction.

Two boundaries, and they are part of the answer:

1. **Not instantaneous mid-conversation.** A running agent keeps its frozen
   toolset until the rebuild, which invalidates that session's prompt-cache
   prefix (deliberate trade, per the AGENTS.md cache invariant). If a toggle
   seems not to land, the fix is `/reset` (new session), never `/restart`.
2. **MCP servers are a different axis.** Adding/removing an *MCP server* is
   reconnected live by the gateway slash command `/reload-mcp`
   (`gateway/run.py::_execute_mcp_reload` ~L20086 — reports reconnected/added/
   removed servers + available tool count). Still not a full restart.

What a **gateway restart** IS for: Hermes code/plugin changes, platform/channel
wiring, and machine-global boot-read knobs (e.g. `kanban.dispatch_interval_seconds`).
In-chat that is `/restart`
(`gateway/slash_commands.py::_handle_restart_command` — drains active work, then
restarts the process); from a shell, `hermes gateway restart`. On the **CLI**
surface toolsets are baked into the running agent, so a CLI session needs a new
session (`/reset`, `/new`) or a relaunch — the gateway-restart question does not
apply there.

Source line numbers and verification probes:
`references/toolset-change-propagation.md`.

## Pitfalls

- **Posture toolsets cannot be manually enabled.** `coding` is marked
  `"posture": True` in `toolsets.py`; `hermes tools enable coding` fails with
  `✗ Unknown toolset 'coding'`. It auto-activates per-session via
  `agent/coding_context.py` whenever the session is in a code workspace
  (default `agent.coding_context: auto`) and propagates to delegated
  subagents. Don't fight it — the posture is the feature.
- **The `kanban` toolset is the other unenableable one — and the gate is not
  where you'd look.** `hermes tools enable kanban` fails with `✗ Unknown toolset
  'kanban'` (kanban is absent from `CONFIGURABLE_TOOLSETS`), yet all 12
  `kanban_*` tools ride in `_HERMES_CORE_TOOLS` with
  `check_fn=_check_kanban_mode()`, which is True only for a dispatcher-spawned
  worker (`HERMES_KANBAN_TASK`) or when the profile's **top-level `toolsets:`
  list** contains `"kanban"` — `platform_toolsets.cli` is NOT consulted. So a
  profile can list `kanban` for the cli platform and still have zero kanban
  tools (live-verified on `delegator`/`coder`/`testprofile`). Fix = add it to
  the top-level list by hand (`hermes config set toolsets '[...]'` writes a
  STRING, which only works by substring accident). And no, this has nothing to
  do with the `terminal` toolset: the handlers only touch the shared SQLite
  board, so a terminal-less profile can create and assign. Full recipe +
  measured tool counts + verification: `references/kanban-toolset-gating.md`.
- **`hermes config set` writes scalars only.** `set_config_value` in
  `hermes_cli/config.py` coerces bool/int/float but never parses lists/JSON.
  You cannot set a list key like `platform_toolsets.cli` with it. Use
  `hermes tools enable/disable` for toolsets instead.
- **The dashboard's Config page is a THIRD write path with the SAME comment
  hazard — and a type quirk.** `PUT /api/config` deep-merges the form into the
  raw file; the YAML toggle on that page (`PUT /api/config/raw`) parses the whole
  document and re-dumps it with `merge_existing=False`. Both go through the YAML
  dumper, so a comment-rich config comes back comment-free exactly like
  `hermes config set` (this box's root config would lose its 36 comments). Two
  more quirks when sending a user to the UI instead of the CLI: the form is
  generated from `DEFAULT_CONFIG`, so a field whose default is `null` (e.g.
  `max_concurrent_sessions`) infers a **string** type and renders as a plain text
  input that saves a quoted value (loaders coerce numeric strings, so it still
  works); and the field set is whatever the RUNNING version ships. Before naming
  a control to click, confirm it exists with `GET /api/config/schema` — that
  endpoint answers WITHOUT a token, while `GET/PUT /api/config` need one.
- **The "⚠ This profile has no API keys yet" warning after a clone is
  generic.** `.env` (provider keys included) IS copied by `--clone`. Trust
  the smoke test, not the warning.
- **A profile NOT created by `--clone` (or hand-created) can boot with no
  provider key at all, and `hermes -p NAME chat` then dies in <1 s with the
  generic `The model request failed` — injecting the key into the caller's
  shell env does NOT fix it.** Observed on a profile whose `.env` held only an
  MCP token: nothing in `agent.log`/`errors.log`, no exception in the console.
  Profile-scoped runs resolve provider credentials from `<profile>/.env`; the
  same exported, VALID env key made a default-profile run exit 0 while the `-p`
  run still failed. Fix: append the key to the profile's own `.env` (back it up
  first, keep mode 600), then smoke-test with `-q "reply with exactly:
  PROFILE-OK"`. Diagnose in 30 s instead of guessing: (a) CHECK THE REAL VALUE
  of any key you harvest from a config file — a `.env` line can be a redacted
  placeholder (`KEY=***`, len 3); harvest the live value from a running user
  process's `/proc/<pid>/environ` if the files only hold redactions, and never
  print it. (b) curl the provider directly with the key — HTTP 200 proves the
  key is fine and the problem is profile-scoped, not auth. (c) `hermes -p NAME
  doctor` names the missing key per profile ("No API key found in
  profiles/<NAME>/.env") even while its own "API Connectivity ✓ OpenRouter"
  check passes via the global pool — the two lines can disagree; trust the
  per-profile one. (d) run the same minimal `say hi` probe on default AND the
  target profile with identical env to isolate the axis.
- **Toolset taxonomy surprises**: `project` is GUI-sessions-only (Desktop),
  `debugging` is a scenario toolset that only bundles terminal/web/file (usually
  redundant when those are already enabled).
- **Four surfaces enumerate toolsets, so a count is never "wrong" by itself —
  find the surface the user is counting.** For one profile this box answers 24
  (`_checklist_toolset_keys`, the interactive checklist), 25
  (`hermes -p NAME tools list --platform cli`, resolved built-ins only), 27
  (`_get_effective_configurable_toolsets()`, the configurator universe incl.
  config-only `stt`), or 28 (`GET /api/tools/toolsets?profile=NAME` on the
  dashboard, which also carries plugin toolsets discovered in that process —
  `a2a` here). A user quoting a number is usually reading the dashboard: match
  it and name the surface yours came from instead of replying "there are only
  25". Auth/port recipe + the `name,active` CSV shape:
  `references/toolset-enumeration-surfaces.md`,
  `scripts/list-profile-toolsets.py`.
- **`hermes tools` refuses to run non-interactively — scripting must go around
  it.** Both `hermes tools` and `hermes tools --summary` exit with `Error:
  'hermes tools' requires an interactive terminal. It cannot be run through a
  pipe or non-interactive subprocess.`; a pty does NOT bypass it. Use
  `hermes tools list --platform NAME` (prints `✓ enabled` / `✗ disabled` rows
  plus a separate "MCP servers" block — never count those lines as toolsets) or
  the dashboard API. Related doc drift: `cli-config.yaml.example` (~L1025) still
  advertises `hermes chat --list-toolsets`, which this build rejects as
  `unrecognized arguments`.
- **Never hand-edit a profile's config.yaml** — use `hermes config set` /
  `hermes tools`; a stray indent breaks YAML loading. The one exception is
  `agent.disabled_toolsets` (and other list-valued keys): no CLI writes lists, so
  back the file up, insert the block after the top-level `agent:` line, and
  re-verify by loading the config (`load_config()` runs the YAML linter) — see
  "Fleet-Wide Toolset Lock-Down".
- **The live `/p/<profile>/v1/toolsets` view is the `api_server` resolution, not
  your CLI session's toolset set — they can disagree for one profile.** Observed
  2026-09-24: that endpoint reported `clarify` OFF while the live CLI session had
  the `clarify` tool. Quote it as "the api_server view" and name the platform you
  read. Port trap found in the same probe: 9119 is the DASHBOARD and answers with
  SPA HTML, 8642 is the JSON API server — a wrong-port curl looks like a broken
  endpoint rather than a wrong address, so resolve both with `ss -ltnp | grep
  hermes`. Per-tool quality/latency/token answers:
  `references/toolset-cost-and-quality-tradeoffs.md`.
- **`platform_toolsets.cli` is not the list bots get.** Each gateway surface has
  its own platform key (`api_server`, `cron`, `telegram`, …) and an absent key
  falls back to that platform's default toolset, so "I removed terminal from the
  profile" can be true of the CLI and false of bot/API traffic. Only
  `agent.disabled_toolsets` is cross-surface. See "Fleet-Wide Toolset
  Lock-Down".
- **There is no `role` field on a profile.** `<profile>/profile.yaml` holds
  exactly `description` + `description_auto` (`hermes_cli/profiles.py`,
  `read_profile_meta` / `write_profile_meta`). The source comment only CALLS
  the description the profile's role — it is free prose the kanban decomposer
  reads for routing. No role list, no per-role settings, no role→model map;
  a profile with no `profile.yaml` routes by name alone. Set it with
  `hermes profile describe NAME --text "..."`, or `--auto` to draft it with
  `auxiliary.profile_describer` (marks `description_auto: true` → review
  badge). So "can one profile have multiple roles?" -> functionally yes
  (skills across domains + a multi-capability description + the 14
  `auxiliary.*` slots each on its own provider), structurally no (no role
  container). Distinct identities/models/memory = distinct profiles.
- **`HERMES_PROFILE=<name>` is NOT the way to target a profile from a script —
  `-p/--profile` is, and the failure is SILENT.** With
  `HERMES_PROFILE=coder hermes tools list`, the command exits 0 and prints the
  **default** profile's state (verified live: `file` enabled under
  `HERMES_PROFILE=coder` vs `✗ disabled` under `hermes -p coder`, and
  `-p coder skills list --enabled-only` shows `bonfire-mcp` enabled while the
  default profile shows both bonfire skills disabled). A fleet sweep written
  against the env var therefore reports 16 identical profiles and looks
  plausible. Always `subprocess.run(["hermes", "-p", name, ...])`. Per-profile
  inventory of the three axes in one pass:
  `hermes -p NAME tools list --platform cli` (and `--platform api_server` — the
  bot traffic surface; it can differ from cli), `hermes -p NAME skills list
  --enabled-only`, `hermes -p NAME mcp list` (a whitespace table, not a box
  table: `name  transport  tools  ✓ enabled`; `testprofile` legitimately has 1
  server where its peers have 3). Two more things that bite when parsing:
  `--enabled-only` counts include platform-gated skills only if the platform
  matches, so cross-check against `<profile>/skills/**/SKILL.md` minus
  macOS-only frontmatter and expect the delta to be exactly the profile's
  `skills.disabled` entries; and rich truncates long names in a non-TTY, so set
  `COLUMNS=250` in the child env to get full table cells.
- **`hermes profile show` takes the NAME positionally.** `hermes -p coder
  profile show` fails with `the following arguments are required:
  profile_name` — that subcommand has its own positional arg and does not read
  the global `-p`. Use `hermes profile show coder`. `-p` does work on the
  config-reading subcommands (`config get/set`, `config env-path`, `tools`,
  `fallback`).
- **SOUL.md is always injected; a skill is not.** A rule that must apply every
  time belongs in SOUL.md (a short imperative); procedure/tables/commands
  belong in a skill. SOUL.md cannot enable or disable tools — enforcement is
  `hermes tools`. Full decision matrix and the complete per-profile isolation
  surface: `references/context-files-vs-skills.md`.
- **`/hook` does not exist, and hooks are not messaging.** There is no `/hook`
  command in `hermes_cli/commands.py`; `hooks:` in config.yaml are shell-script
  LIFECYCLE hooks (`hermes hooks list/test/doctor`), inbound/outbound webhooks
  are a separate HTTP trigger/delivery system, and messaging platform adapters
  are a third thing. Don't let a user's naming convention pull the answer into
  the wrong system — say plainly that the term doesn't exist as a command, then
  give the nearest real concept. Detail:
  `references/automation-surface.md`.
- **`/plan` is a skill-backed one-turn mode, not a separate command.** It isn't
  in the slash-command registry — it works because `/<name>` loads a skill, and
  `plan` is a PROTECTED built-in (`tools/skill_usage.py`) the curator must
  never archive (archiving turns `/plan` into "Unknown command" silently). It
  is plan-only for that turn, writes to `.hermes/plans/`, and the execution
  half happens in the NEXT normal message, same session — no restart, no
  persistent mode to exit. Detail: `references/automation-surface.md`.
- **Cron is per-profile and gateway-owned.** Each profile has its own job table;
  nothing fires while the gateway is stopped (`hermes cron status`). Jobs
  created from a CLI session are LOCAL-ONLY — output is saved and readable but
  there is no live delivery into a terminal, so notification requires
  `deliver` pointing at a gateway-connected platform. Never promise a
  `deliver='origin'` cron job will message the user in a CLI session. Detail:
  `references/automation-surface.md`.

- **`hermes mcp add` is interactive — and saves `enabled: false` when the
  server isn't up.** It prompts "Does this server require authentication?
  [Y/n]", then (after a failed connect) "Save config anyway? [y/N]", then
  "Enable all N tools? [Y/n/select]". Pipe the answers
  (`printf 'n\ny\n' | hermes -p NAME mcp add X --url ... --connect-timeout 10`);
  a pty is not required. If the endpoint isn't listening you get
  `✓ Saved 'X' to config (disabled)` — the entry lands with
  `enabled: false` + a `connect_timeout`, which does NOT match a sibling
  profile's bare-`url` entry. Remove those two keys with a targeted `patch`
  (YAML re-checked by the linter) so the server is enabled like its peers, and
  confirm with `hermes -p NAME mcp list` showing `✓ enabled`.
### Disabling an MCP Server Fleet-Wide ("disable MCP X for all profiles")

There is **no `hermes mcp disable`** (`hermes mcp` has only serve/add/remove/list/
test/configure/login/reauth/picker/catalog/install). Two ways to switch a server
off, and they differ:

- **`enabled: false` under that server in `mcp_servers`** — the real disable
  switch, config kept intact, one-line revert. Honoured on every path:
  `tools/mcp_tool.py` filters `_parse_boolish(cfg.get("enabled", True))` both in
  discovery (`~L6488`, the `new_server_names` list) and in the probe path
  (`~L6637`), and `hermes_cli/tools_config.py::enabled_mcp_server_names()`
  (`~L2123`) keeps the name out of the enabled toolset set that
  `_get_platform_tools()` folds into cli/api_server/cron/messaging. `hermes mcp
  list` renders it `✗ disabled` (`status:"disabled"`, distinct from a failed
  connect). Recognised falsey values: `false/0/no/off` (quoted strings too).
- **`hermes -p NAME mcp remove X`** — deletes the entry (transport, headers,
  `${VAR}` reference) as well. Only when the user means "remove", not "turn off".

Procedure (edited in place, comments preserved):

```python
import yaml
KEY_LINE, INSERT = "  obisidian:\n", "    enabled: false\n"
# per file: assert KEY_LINE occurs exactly once, splice INSERT after it, then
# yaml.safe_load both versions and assert the ONLY flattened-key delta is
# ("mcp_servers", <name>, "enabled") and the comment lines are byte-identical.
```

Do **not** use `hermes config set mcp_servers.X.enabled false` on this box: it
works, but it rewrites the file through the YAML dumper and drops all 36 comment
lines in every one of the 17 configs (same hazard as the dashboard Config page).
Back up to `<hermes>/config-backups/<label>-<ts>/{root-config,profile-<name>}.yaml`
first, one file per profile.

Verify in two layers:

```bash
hermes -p NAME mcp list        # ✗ disabled  (the authoritative status view)
```

```python
from hermes_cli.tools_config import enabled_mcp_server_names, _get_platform_tools
# assert name not in enabled_mcp_server_names(cfg), and for plat in
# ("cli","api_server"): no toolset entry containing the server name
```

Two misleading surfaces, both seen live:

- **`hermes tools list` prints a `MCP servers:` block that is NOT the enable
  state.** It iterates raw `mcp_servers` (disabled servers included) and reports
  only the per-tool `include`/`exclude` filter — `obisidian  all tools enabled`
  means "no tool filter", not "server on". Don't quote it as proof either way;
  never count those lines as toolsets.
- **`GET /p/<profile>/v1/toolsets` is called with
  `include_default_mcp_servers=False`**, so it never lists MCP servers — a blank
  there is not evidence of a disable. And `/p/<profile>/...` needs that
  **profile's own** `API_SERVER_KEY` (from `profiles/<name>/.env` line ~500); the
  root key returns `gateway_auth_failed`. The no-prefix `/v1/toolsets` uses the
  root key.

Restart picture: MCP discovery is startup-time, so a *running* agent keeps the
server until its next rebuild — a gateway picks the change up live (config read
is mtime-keyed, plus `mcp.auto_reload_on_config_change`); a CLI session needs
`/reset`/new session. Cross-check whether any connection existed at all:
`ss -tnp | grep <port>` and the log line `MCP server 'X' failed initial
connection … parking` in `~/.hermes/logs/agent.log` prove it was never
connected, i.e. nothing was live to begin with (this box: Obsidian local REST
API on 27123 was down, so `obisidian` had been failing every startup).

### Fleet-WIDE = EVERY server in EVERY profile ("disable ALL MCPs")

Same `enabled: false` switch; the whole-scope sweep is the hard part, and the
obvious implementation is subtly WRONG — so do not hand-type it. Run
`scripts/disable-mcps-fleet-wide.py` (`--apply`; `--restore` rolls every config
back from its backup). It does the dry run, the splice, the backups and the
two-layer verification below.

Worked numbers (2026-10-08): 17 configs = root + 16 profiles, 52 server entries
flipped/inserted — w-bridge/memory/obisidian on every profile, `neurostack` on
`default`, `open-scad` + `open-scad mcp` on `mechanical-modeler`. `testprofile`'s
one server was already `false`, so its file is a legitimate zero-diff (don't
"fix" that by forcing a line). Confirm per profile with `hermes -p NAME mcp
list` — every row reads `✗ disabled`.

Two pitfalls that each cost a re-do here; both are about HOW you edit:

- **Bound the server-name scan to the `mcp_servers` block, or you corrupt
  `platform_toolsets` and `plugins`.** A regex like `^  ([^\s#][^:]*?):$`
  (server indent = 2 spaces) ALSO matches `platform_toolsets`' children
  (`  cli:`, `  discord:`, `  telegram:`, …) and `plugins`' children
  (`  enabled:`, `  disabled:`). Observed live: the naive version reported
  `default: 17 servers, coder: 4` and injected `enabled: false` into every
  `platform_toolsets.<platform>` entry — silently, because the write "worked".
  Compute the block end FIRST (next non-blank line at indent 0), slice
  `body = lines[mcp_idx+1 : mcp_end]`, and only then match names inside `body`.
  Sanity check: the per-file count must equal the number of keys
  `yaml.safe_load` returns under `mcp_servers`.
- **A ruamel round-trip dump is NOT formatting-neutral, even with
  `preserve_quotes` + comment preservation.** It re-wraps long plain scalars
  (the persona strings) and re-indents block sequences (ruamel indent 2 vs the
  original 0), so a 3-line change produced a ~200-line textual diff per file;
  `yaml.width = 4096` only un-wraps instead of preserving. Splice text lines —
  never `yaml.dump` a config.yaml. Prove it two ways: (1) semantic — normalise
  both loads to plain JSON, `pop("enabled")` from every server, deep-compare,
  must be EMPTY; (2) textual — `diff -u` must contain ONLY `enabled:` lines.
  The script does both; the one-off pair that first proved it is worth
  re-creating if you hand-roll the edit.

Restart picture matches the single-server case (discovery is startup-time): the
running gateway/dashboard/CLI keep their connections — the stdio watchdogs
(`tools/mcp_stdio_watchdog.py --ppid <pid> -- …`, e.g. `neurostack serve`) stay
up — until the next rebuild. Say so explicitly and OFFER `hermes gateway
restart`; do not claim the fleet is already off just because the config says so.

- **MCP does NOT require the terminal tool — do not answer otherwise.**
  `mcp_servers` is a top-level, per-profile config key on its own axis; each
  enabled server becomes a runtime toolset named after itself and is folded into
  the enabled set by `tools_config.py`. Proven live: the `delegator` profile has
  terminal removed from `platform_toolsets.cli` and still loads `w-bridge` +
  `memory`. stdio servers are spawned by `tools/mcp_tool.py`'s own asyncio
  subprocess path, never through the model-facing terminal tool. The only opt-out
  is the `no_mcp` sentinel. Two follow-ons worth stating up front: MCP discovery
  happens at agent STARTUP, so a server added mid-session is invisible to the
  running agent — in a gateway `/reload-mcp` reconnects servers live (see "Does
  a Tool Toggle Need a Gateway Restart?"), on the CLI only a new session is; and
  a large server's tools may arrive via the deferred `tool_search`/`tool_call`
  catalog instead of the system-prompt index. Detail + fleet audit snippet:
  `references/mcp-vs-toolsets.md`.
- **A clone only carries config/.env/skills into a *new* profile; an
  already-existing profile keeps its own.** So after a bulk sync, diff the
  pre-existing profiles against the source: `hermes -p NAME mcp list`, and
  compare skill trees (`diff <(cd $HERMES_HOME/skills && find . -name SKILL.md
  | sort) <(cd profiles/NAME/skills && find . -name SKILL.md | sort)`). A
  profile can look fine (right SOUL) while being unable to call the tools that
  SOUL tells it to use.
- **Writing a SOUL is not "updating a profile".** The SOUL is identity text
  only — it cannot enable MCP servers, toolsets, or skills. When a soul
  references specific tools (`add_loading_message`, `project_todos*`), treat the
  tool wiring as a separate, explicit deliverable.
- **`.env` inheritance is a one-time SNAPSHOT, not a live link.** A profile
  reads its own `<profile>/.env` (`hermes_cli/config.py::get_env_path()` →
  `get_hermes_home() / ".env"`). `profiles.py::backfill_profile_envs()` copied
  the default `.env` into each named profile exactly ONCE, at the migration that
  made credentials profile-scoped, and never re-syncs ("Users can then diverge
  per profile from there"); `--clone` and `sync-soul-profiles.sh` likewise COPY
  at create/run time. So a key added to the default `.env` afterwards exists in
  NO profile — verified live: root had 3 `HERMES_LANGFUSE_*` keys, all 14
  profiles had 0. Same trap for plugin opt-in: `plugins.enabled` is written by
  `plugins_cmd._save_enabled_set()` → `save_config()`, i.e. into the ACTIVE
  profile's `config.yaml`. To change something fleet-wide, loop the CLI
  (`hermes -p NAME config set KEY VAL`, `hermes -p NAME plugins enable X`); for
  env-var sweeps use `hermes-observability/scripts/rollout_langfuse_to_profiles.py`
  (idempotent, `--remove` to undo). Always verify per profile afterwards —
  `hermes -p NAME config get KEY`, `hermes -p NAME plugins list`.
- **Memory is per profile too, and NOT inherited from the root config.** Each
  profile's effective config is `DEFAULT_CONFIG` deep-merged with its OWN
  `config.yaml`; `~/.hermes/config.yaml` is read only by `default`. So a profile
  with a `memory:` block but no `provider:` key resolves to
  `DEFAULT_CONFIG["memory"]["provider"] = ""` → built-in only — it does NOT
  inherit the root profile's `openviking`. And two profiles that both select the
  same provider still share ONE store, because the store's connection/scope
  comes from per-profile `.env` vars that are identical by default (OV:
  `OPENVIKING_AGENT` is the peer id, default `hermes`). Verdict + verification:
  `hermes -p NAME memory status` + `references/per-profile-memory-providers.md`.
- **A SOUL source tree is not guaranteed to be a SUPERSET of the profile files.**
  "Update the profiles from the SOUL folder" can mean additions, deletions, or
  both, and the source can shrink between rounds (observed: round 1 additions
  only, round 2 a deliberate deletion of all `#### Related Profiles` blocks).
  Always diff first and list the removals in the reply; mirror the tree as asked
  (source wins), but never assume a straight copy is lossless — see "Re-sync:
  'update the profiles from the SOUL folder again'" and
  `scripts/soul-tree-resync.py`. Also: profiles with no matching source folder
  (`default`, `testprofile` on this box) are out of scope and stay untouched.
  And **newer does not mean correct**: the round after that, the sources renamed
  the whole knowledge stack Obsidian→NeuroStack — including a tool name
  (`project_neurostack_note`) that does not exist in the MCP implementation
  (grep `W-bridge/mcp/tools.py`; `project_obsidian_note` is the real one). So
  before treating a renamed/added tool in a fresher source as authoritative,
  check the server, and audit three-way (spec doc / loaded mirror / source):
  `references/soul-coverage-audit.md`.
- **A capability-gap verdict is a claim about the IMPLEMENTATION — verify it in
  the implementation, in three layers.** Concluding "no object exists" from the
  MCP tool-reference headings produced a verdict the user rejected ("there are
  gaps in soul.md but feature exists in the bonfire & w-bridge mcp"). Check, in
  order, and report the layer that breaks: (1) Rails schema —
  `sqlite3 <bonfire>/storage/db/development.sqlite3 ".tables"` / `".schema <t>"`;
  (2) bridge payload — `space/api/<entity>.py` create/update arg lists (the
  `prune({...})` keys are exactly what is POSTed); (3) agent reach —
  `TOOL_DEFINITIONS` in `mcp/tools.py`. Two traps this exposed: a DB column is NOT
  a writable field (`company_status_items.evidence`/`.impact`/`.target_date`/
  `.severity`/`.actions` exist in the schema while neither the bridge nor the tool
  schema accepts them), and a design doc's proposed table is NOT an entity
  (`attention_item_events` is described in DEMO_FUNCTIONALITIES_DB_IMPACT.md and
  absent from `.tables`).  Also treat "exists in the DB and referenced by NO SOUL"
  as its own finding class, separate from "missing":
  `references/write-path-verification.md`.
  Re-verify EVERY review round, not once: the tool surface grows between
  sessions — params that were "not writable" when the gap list was written may
  be accepted now, and SOUL text patched to match a stale gap then becomes
  wrong in the opposite direction (a refusal written against an old limit that
  the tool has since lifted). Before endorsing or faulting any SOUL sentence
  about a tool, grep the current schemas again, same pass.
- **A SOUL content edit belongs in BOTH trees, source first — and it is additive
  by default.** Editing only the loaded mirrors (or only the sources) means the
  next `soul-tree-resync.py` silently re-diverges one of them, so pair any
  reconciliation with the mirror step in the same pass. Reconciling a spec doc
  against the SOULs does NOT mean moving bullets: a tool may legitimately be
  listed in two sections, so ADD unless the user explicitly asked for a move.
  Anchor-uniqueness assertion, mirrored per-file backups, and the line-math
  verification (`+2/-1` for a two-rule file, `+1/-0` bullet-only, `+1/-1`
  replace-only): `scripts/soul-section-edit.py` +
  `references/soul-coverage-audit.md` §9.
- **A rule you author can be accurate and still forbid what the user wants —
  check the multi-instance case before shipping the text.** Drafted v1 of the
  handoff section said "One handoff = one card: one owner, one expected
  outcome"; every audit axis was green and it deployed cleanly, but it banned
  the fan-out the user actually expected ("did you consider creating multiple
  cards … one profile could create two cards"). The fix is to state the
  constraint at the right level ("one card = one owner and one outcome" plus an
  explicit "When to split into two or more cards" subsection and "create as many
  as the work requires"), NOT to soften it. Before presenting any governance
  text: restate each rule as a capability question ("can a profile create two
  cards?") and answer it from the text alone, then scan for `only` / `never` /
  `single` / `one … =` / `do not … other than` and ask what each forbids. Same
  reflex as the audit rule — check BOTH halves of a capability, single and
  multiple. §5 of `references/soul-section-authoring.md`.
- **The W-ai source tree is a git repo: do not create backup copies there.**
  The user's standing instruction ("when updating in …/W-ai/hermes no need to
  create a backup version"), and `git show HEAD:<relpath>` is a better baseline
  than a copy anyway. The LOADED profiles are not in git, so they still get
  mirrored per-file backups. When both trees are edited in one pass, emit one
  patch per file diffed against its own pre-change baseline, keep the patch
  directory outside both repos, and delete the empty directory a dry run leaves
  behind (makedirs runs before the loop — otherwise the reply points the user at
  four near-identical patch dirs). Also state the COMMIT status in the same reply:
  the user asked whether `soul-patches/` "is only for showing the history of
  changes" — it is not history at all. It is one diff per file per RUN, kept
  outside both repos, with no cumulative index; every round adds a new
  timestamped directory (six of them accumulated in one day here), and deleting
  them loses only the review artifacts. The history is the repo, so say whether
  this round is committed and offer to commit — an edit left in the working tree
  has no history entry anywhere.
- **When a round is scoped as "just minimal changes now", ship the smallest
  additive set.** One dated section plus only the anchors the named rules need —
  do not bundle the pending gap analysis, the reviewer-profile decision or the
  API extensions into the same edit. Hold those as an explicit offer at the end
  instead. The user said "for just a minimal changes now update soul.md" and later
  "so besides soul.md you changed some skills … correct?" — so the reply must also
  enumerate EVERY artifact the round touched (SOUL files per tree, the scripts,
  the patch dirs, any skill edit, any memory write), because a skills-tree write
  is not visible to them in the SOUL diff.
- **Never hand-roll the re-sync as an inline `cp` loop — the backups collide.**
  Every source file is named `SOUL.md`, so `cp -p "$tgt/SOUL.md" "$BACKUP/"`
  into ONE flat backup dir overwrites the same path 13 times; you keep the last
  profile's file and silently lose the other 12 snapshots (observed live, round 3
  of this tree). Two fixes, both already in the scripts: back up as
  `<BACKUP>/<profile>__SOUL.md` (flat, unique names — what
  `soul-tree-resync.py` and `sync-soul-profiles.sh` write), or
  `<BACKUP>/<profile>/SOUL.md` (per-profile subdir, what
  `sync-soul-profiles.sh` writes). The inline-loop route also blows the
  50-call sandbox cap on 13 profiles when each copy is verified separately —
  run one script file instead of per-file tool calls. Recovery when it has
  already happened: if the source tree is a strict superset (additions only),
  nothing is lost — the pre-sync mirror was byte-identical to the previous
  source revision, so rebuild the backup with
  `git show HEAD~1:<path-to-SOUL.md>` and confirm one survivor with `cmp`
  before trusting it.
- **Capture the pre-change text BEFORE writing — never copy the file after the
  edit.** A backup taken with `shutil.copy2(path, dest)` placed after the append
  stores the NEW content, so the backup equals the live file: every loaded-side
  patch comes out empty (`+0 -0`, zero files in the patch dir) while the source
  side looks perfect because it diffs against `git HEAD`. Observed live
  2026-09-30 on a 32-file append. Keep the pre-write string returned by the
  append helper and write THAT to the backup (or `git show HEAD:<rel>` for a
  git-backed tree). Recovery when it has already happened: the appended block is
  a known constant, so rebuild the original as
  `new.replace("\n" + BLOCK, "", 1)` and regenerate the diffs from that.
- **Re-sync acceptance test = run `scripts/soul-tree-resync.py <SRC>` dry-run and
  read `changed: 0`.** That is the cheapest proof the mirror is complete; it also
  prints `removed lines:` so a deletion round can't pass unnoticed. Follow with
  `hermes profile list` (fleet still enumerates) and state that SOUL.md is read
  per session so no gateway restart is involved.
- **A loaded SOUL can be a seed copy of `default` — persona PLUS the shared
  collaboration tail — while the source tree holds persona only. Mirror as a MERGE,
  not an overwrite.** A profile cloned from default inherits `~/.hermes/SOUL.md`
  verbatim: generic identity paragraph + `## Bonfire Collaboration Rules` … `## Agent
  Questions and Approval Discipline`. Overwriting it with a bare persona silently
  strips the room-routing/kanban/approval rules that profile runs by. Before any soul
  mirror, read the TARGET's loaded file and grep for the shared headers; if present,
  assemble programmatically — `cat <persona> > SOUL.md && echo >> SOUL.md && sed -n
  '/^## Bonfire Collaboration Rules/,$p' <backup> >> SOUL.md` — never retype the tail
  by hand (a retyped 149-line tail carried two single-word drifts only a full
  byte-diff caught), then verify BOTH halves separately (persona==source,
  tail==backup) and keep the per-file backup of the replaced file. Siblings vary
  (one profile's loaded soul may be a standalone persona with no tail): judge each
  profile from its own file, never from a neighbour's shape.
- **Cross-profile reads during a single-profile change look like edits.** A terminal
  probe that greps another profile's `SOUL.md` to learn fleet convention earns a
  "why are you changing X's soul?". Label such probes read-only in the step you
  announce, and answer the suspicion with evidence: `ls -la` mtime on the sibling
  file plus a one-line enumeration of every path actually written.
- **Not every directory under `profiles/` is a profile.** Backups such as
  `.soul_backup_20260914_095345` sit in the same tree; treat a directory as a
  profile only when it has `config.yaml`, or a `for d in profiles/*/` sweep
  writes credentials into backups.
- **Before calling a log traceback "still happening", attribute it.**
  Traceback lines carry no timestamps, and an awk string filter like
  `awk '$1" "$2 >= "2026-..."' gateway.log` lets EVERY untimestamped line
  through (letters sort after digits), resurrecting month-old tracebacks as
  current errors. Find each traceback's nearest preceding timestamped line:
  `awk 'NR<=<traceback_line> && /^2026/ {t=$0} END{print t}' gateway.log`.
  Also read `gateway.log` with `grep -a` — it contains binary bytes, and plain
  grep prints only "binary file matches" and hides the hits.
- **Enumerate a SOUL source tree case-INSENSITIVELY — the fleet is not all
  `SOUL.md`.** The W-ai tree holds 15 files, but only 11 are lowercase `SOUL.md`;
  4 are uppercase `SOUL.MD` (`main/action`, `bots/business analyst`,
  `bots/market research`, `bots/ask from w`). `find . -name "SOUL.md"` returns 11
  and every count, keyword sweep and "the fleet is N profiles" line in the reply
  is then wrong — this happened live 2026-09-30 (an audit replied "13 SOUL files"
  from a case-sensitive sweep). Use `find . -iname "soul.md"`, or the bundled
  scripts, which already accept both (`find_souls` in
  `sync-soul-profiles.sh` / `soul-tree-resync.py`). Anything you hand-roll for a
  fleet-wide count needs the same tolerance. Related: `grep -ril -- "$k"
  --include="SOUL.md" .` puts `--` before an option, so grep treats
  `--include=…` as a PATH — it errors AND still prints partial matches from every
  other file, which reads as a result; prefer `search_files` or put the flags
  before `--`.
- **Creating a profile named `config` (or any hermes subcommand name) succeeds
  but silently gets NO CLI alias.** `hermes profile create config --clone-from
  default` prints `✓ Profile created` + `Cloned config, .env, SOUL.md, and
  skills` and the profile works, but the wrapper step fails with `⚠ Cannot
  create alias 'config' — 'config' conflicts with a hermes subcommand` and the
  Alias column of `hermes profile list` stays `—`. So `config chat` / `config
  gateway start` (the paths the "Next steps" hint prints) do NOT work; reach it
  as `hermes -p config …`, or make a wrapper with
  `hermes profile alias config --name <custom>`. Same trap would hit `setup`,
  `chat`, `tools`, `skills`, `cron`, `mcp`. Note the "⚠ This profile has no API
  keys yet" warning printed in the same breath is the known generic false
  positive — `.env` is copied by `--clone` (verify by line count: 511 = 511).
- **Two source dirs under different groups can map to the SAME profile id, and
  `find_souls` will not warn.** The profile id is only the file's parent dir
  name, so `main/config/SOUL.md` and `se/config/SOUL.md` both resolve to
  `config` — the report then shows a `config` row twice and the LAST one in
  sorted path order wins (both write the same target). Harmless while the files
  are byte-identical, but if they ever diverge the sync flip-flops between them
  with no error. When the tree gains a group dir that repeats an existing leaf
  name, diff the two (`cmp`) and surface it in the reply rather than trusting
  the clean-looking report.
- **`hermes profile delete NAME -y` removes the directory AND the CLI alias.**
  Output: `✓ Removed ~/.local/bin/NAME` then `✓ Removed
  ~/.hermes/profiles/NAME`, after listing what goes (config, API keys, memories,
  sessions, skills, cron jobs). Before running it: (a) archive first if there is
  any chance the user wants something back —
  `tar czf /tmp/NAME-backup-$(date +%Y%m%d_%H%M%S).tar.gz -C ~/.hermes/profiles NAME`
  (a test profile of ~18M compresses to ~5M); (b) unwind anything you attached
  to that profile (per-profile credentials, plugin opt-ins) so it does not
  outlive the directory; (c) say plainly that telemetry already exported to an
  external backend is NOT deleted with the profile. `-y` is the only guard, so
  treat the alias removal as the point of no return for `NAME`-as-a-command.
  If the request is ambiguous between "delete the profile" and "stop tracing
  it", ask — the two differ by irreversible data loss. For bulk teardown
  ("remove all profiles except default"), the per-profile full-tree tar is the
  wrong archive and one loop is the wrong execution — see "Bulk Profile
  Delete".

## Answer Shape

This user asks capability questions in short bursts and explicitly caps length
("answer short"). Lead with the verdict plus the one or two facts that change
the decision, and hold the exhaustive detail behind an offer to go deeper.
Settle what can be settled by reading the live install — `hermes -p NAME config
get`, `hermes <cmd> --help`, the source tree at `~/.hermes/hermes-agent/` — and
name the file or command the answer came from instead of reciting docs. When
the user's term is not a real field or command ("role", "/hook"), say so first,
then give the nearest real concept.

**Fleet-wide requests: ask which SET, then answer the scope question as the
deliverable.** "Disable X for all profiles" is ambiguous in a way that matters,
because `default` is the user's own interactive profile. Ask once, with concrete
choices (all N / bots only / all except default), and lead the reply with the set
you touched. Observed split on this box: the user exempts `default` + `coder` from
capability-stripping toolsets (terminal/file/code_execution) but answers
"literal all profiles" for peripheral ones (vision, image_gen, tts, stt, discord,
computer_use, bfl) — and MCP servers belong to that second bucket: "in all
profiles disable all mcps" was answered by touching all 17 (root included) with
no push-back, so don't stop to ask for that class. Never guess silently — but
never ask twice about the same batch either, and don't widen a later batch to
re-litigate an earlier decision.

Also: when a config question's answer is a scope (per-profile vs global), state
the scope as the verdict, then the proof — the live value, the file/line it came
from, and whether applying a change needs a restart. That structure is what this
user reads for. Restart-or-not questions follow the same shape: verdict with the
negation spelled out ("No — not for a tool toggle"), then the one-line mechanism
and the source it came from, then the boundary cases that DO need a restart —
work from `references/toolset-change-propagation.md`.

## Verification

```bash
hermes -p NAME chat -Q -q "State your identity in one sentence, then reply with exactly: PROFILE-OK"
```

Expect the SOUL.md identity text in the reply plus the marker. A correct
reply proves config, `.env` keys, model, and personality all load end-to-end.
