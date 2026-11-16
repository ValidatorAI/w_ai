# Where Guidance Belongs: SOUL.md vs Skill vs AGENTS.md

Answers the recurring class of question "should this rule go in SOUL.md, a
skill, or the repo?" plus the related "what is actually isolated per profile?"
Verified against the live install: `agent/prompt_builder.py`,
`hermes_cli/config_defaults.py`, `hermes_cli/profiles.py`, and the on-disk
profile directories.

## Loading semantics — the deciding difference

| Home | When it loads | Cost | Can it be missed? |
|---|---|---|---|
| `$HERMES_HOME/SOUL.md` | Always — read once at prompt-build time, injected as identity when present | Sits in the cached prompt prefix, paid on every request | No |
| A skill | Only when a task matches its description; body via `skill_view` | Only the name+description sits in the system prompt | Yes — the model must choose to load it |
| Repo `AGENTS.md` / `.hermes.md` | cwd discovery, only in that project | Only while working in that repo | No (in that repo) |

Verified facts behind those rows:

- `agent/prompt_builder.py::load_soul_md` reads `get_hermes_home()/SOUL.md`
  ONCE at prompt-build time. It is independent of project rules and always
  included when present. It passes through the same threat scanner as other
  context files.
- Truncation is governed by `config.context_file_max_chars`. Default `null`
  means the cap SCALES with the model's context window (floor 20K chars,
  ceiling 500K), not a flat 20K. Set a positive integer to pin a fixed cap.
- Because the system prompt is byte-stable for the life of a conversation,
  editing SOUL.md takes effect on the NEXT session — never mid-conversation.
  Same for a new skill (the skill index is part of the system prompt).
- `AGENTS.md` is cwd-only; `.hermes.md` walks parents up to the git root.
  Both are portable across Hermes, Claude Code, Codex, OpenCode — this is why
  AGENTS.md is the right home for repo rules shared with other agents.
- `hermes --ignore-rules` skips all of the above (context files, SOUL.md
  identity, user config, plugins, MCP servers) for one session — the
  isolation switch when diagnosing whether a problem is the setup or Hermes.

## SOUL.md instructs; it does not enforce

SOUL.md is prose in the system prompt. It CANNOT enable or disable a tool.
Actual tool availability is `hermes -p NAME tools enable/disable TOOLSET`
(per profile) and the `toolsets=` parameter on `delegate_task`. Prose only
steers the model's choice.

## Decision rule

- Policy that must apply EVERY time (routing, formatting, delegation
  discipline, memory scoping) -> SOUL.md, as a short imperative line. This is
  exactly the class already present in the shipped default SOUL.md
  ("Bonfire Collaboration Rules": response routing, formatting, kanban,
  memory scoping).
- Procedure with steps, exact commands, tables, pitfalls -> a skill. It can
  be large and loads on demand.
- Quirk specific to ONE repo -> that repo's AGENTS.md / .hermes.md.
- Best practice is the hybrid: one-line rule in SOUL.md that names the skill
  holding the detail, e.g.

```
## Delegation
- Always narrow child toolsets to the minimum the task needs.
  Code -> ["terminal","file"]; research -> ["web"]; never hand a child
  terminal+file+browser unless the task genuinely needs all three.
- Need the full matrix? Load the delegate-toolset-matrix skill.
```

## Reading and writing a profile's SKILLS — no terminal, no file toolset

"Do profiles need the terminal (or file) toolset to read/write their skills?" →
**No.** Skills are managed by the `skills` toolset (`skills_list` / `skill_view` /
`skill_manage`), which is pure Python file I/O against the profile's own
directory. Proven live: every profile here carries `skills` in its enabled set —
including `delegator`, which has no terminal and only 8 toolsets. Terminal is
only needed to talk to the filesystem BY HAND (curl, curl-style probes, launching
a server) or to bypass the write guard below.

- Resolution is **live and profile-scoped on every call**, not cached at import:
  `tools/skills_tool.py::_skills_dir()` and
  `tools/skill_manager_tool.py::_skills_dir()` both re-read the active
  `HERMES_HOME` per invocation, with comments saying exactly why (a kanban worker
  may import the module once under a different home). So one process serving
  several profiles still reads the right tree per request.
- Skills are COPIES, not references: verified counts per profile — `default` 80
  `SKILL.md`, each of 13 profiles 77, `testprofile` none until scaffolding is
  created. A skill you add to `default` does NOT appear in `coder`; use
  `scripts/sync-soul-profiles.sh`-style or per-profile `skill_manage` loops for
  fleet-wide skill changes. `skills.disabled` / `skills.platform_disabled` only
  switch them off, they never share them.
- **Cross-profile writes are soft-guarded, not blocked.** `write_file` / `patch`
  / `execute_code` run `tools/file_tools.py::_check_cross_profile_path`
  (→ `agent/file_safety.classify_cross_profile_target`) when the target lands in
  ANOTHER profile's `skills/`, `plugins/`, `cron/`, or `memories/` — it returns a
  warning the caller must acknowledge with `cross_profile=True`. The docstring is
  explicit that this is defense-in-depth, NOT a security boundary: the terminal
  tool runs as the same OS user and can write any of those paths directly.
- `skill_manage`'s write path has its own gates independent of toolsets:
  agent-created-skills enabled check, security scan of the skill dir, frontmatter
  + size validation, pinned-skill protection, and a read-before-write
  requirement (a patch is refused unless the current file was loaded in the same
  turn — hit live while curating this very file). Plan for one extra read.

## The complete per-profile isolation surface

Each profile is a full independent HERMES_HOME (`hermes_cli/profiles.py`:
"Each profile is a fully independent HERMES_HOME directory"). Verified by
listing `~/.hermes/profiles/coder/`:

```
SOUL.md          identity slot (always injected)
profile.yaml     description + description_auto ONLY (the kanban routing hint)
config.yaml      model.provider/default, fallback_providers, auxiliary.*,
                 delegation.*, approvals.*, display.skin, stt/tts
.env             provider API keys  (auth.json when an OAuth provider is used)
skills/          installed skills
memories/        memory store (+ built-in MEMORY.md/USER.md)
sessions/ state.db   conversation history
cron/            scheduled jobs
hooks/  skins/  plans/  workspace/  sandboxes/  logs/
```

Users typically name only four (soul, skills, memory, tools). The rest —
config, secrets, cron, hooks, skins, session history — are just as isolated,
and config (model/provider/fallback/aux) is the biggest practical
differentiator.

NOT per-profile: `~/.hermes/kanban.db` is shared across ALL profiles (that is
the point of the kanban board as the cross-profile task layer). `ls` of the
hermes root vs a profile dir is the quick way to see what is root-level
shared vs per-profile.

## Profile routing: there is no `role` field

`profile.yaml` contains exactly two keys — `description` and
`description_auto` (`read_profile_meta` / `write_profile_meta`). The source
comment ("metadata ABOUT the profile itself — its role, who described it")
only CALLS the description the profile's role. Consequences:

- No role list, no per-role settings, no role->model map exists.
- The kanban decomposer reads `description` to route work; a profile with no
  `profile.yaml` (or an empty description) routes by name alone.
- `hermes profile describe NAME --text "..."` sets it;
  `hermes profile describe NAME --auto` drafts it with `auxiliary.profile_describer`
  and marks `description_auto: true` (dashboard shows a review badge).

So "can one profile have multiple roles?" -> functionally yes (skills across
domains + a description naming several capabilities + the 14 `auxiliary.*`
slots each on its own provider/model), structurally no (no role container).
Distinct identities/models/memory = distinct profiles.

## CLI gotcha

`hermes -p NAME profile show` FAILS with `the following arguments are
required: profile_name` — `profile show` takes its own positional arg and
does not read the global `-p`. Use `hermes profile show NAME`. The `-p` flag
does apply to the config-reading subcommands (`config get/set`,
`config env-path`, `tools`, `fallback`), which is why
`hermes -p coder config get model.provider` works.
