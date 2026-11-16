# Profile Directory Semantics: `workspace/`, `home/`, `sandboxes/`, `plans/`

Companion to `references/context-files-vs-skills.md` (which lists the full
per-profile isolation surface). That file names these dirs; this one explains
what they ARE, because all three are routinely mistaken for "my project folder".
Verified on the live install + source: `hermes_cli/profiles.py::_PROFILE_DIRS`,
`hermes_constants.get_subprocess_home`, `tools/environments/base.py::get_sandbox_dir`,
`agent/file_safety.py`, `hermes_cli/profile_distribution.py`.

## The nine bootstrap dirs

Every NEW profile gets `_PROFILE_DIRS` created in its home:
memories, sessions, skills, skins, logs, plans, workspace, cron, home.

## `workspace/`

The profile's own private scratch/persistent area. NOT your project folder.

- What plugins use for per-profile state (e.g. google_meet writes
  `workspace/meetings/auth.json` via `get_hermes_home()/workspace/meetings/`).
- The persistent workspace inside container backends.
- Usually EMPTY on a host install. The `default` profile may have no
  `workspace/` at all if it predates the bootstrap — absence is not a problem.

## `home/`

NOT the workspace. A back-compat / container `HOME` for tool subprocesses,
governed by `terminal.home_mode` (`hermes_constants.get_subprocess_home`):

| mode | behaviour |
|---|---|
| `auto` (default) | host installs keep the REAL user `$HOME` for subprocesses so normal CLI credentials stay visible; containers use `{HERMES_HOME}/home` for persistent state |
| `real` | always prefer the real OS-user HOME |
| `profile` | use `{HERMES_HOME}/home` when it exists — the older strict per-profile tool-config isolation |

Empty on a correct host install.

## `sandboxes/`

Host-side storage root for SANDBOXED terminal backends — Docker workspaces,
Singularity overlays/SIF cache. Nothing to do with the local shell.

- `tools/environments/base.py::get_sandbox_dir()` → `{HERMES_HOME}/sandboxes/`,
  overridable with `TERMINAL_SANDBOX_DIR`.
- Layout: `sandboxes/<backend>/<task>/…` including `home/.hermes` mirrors.
- `agent/file_safety.py` pattern-matches
  `…/sandboxes/<backend>/<task>/home/.hermes/…` and classifies writes there as a
  **sandbox-mirror of authoritative Hermes state** — not a normal project file.
- Per-profile, because HERMES_HOME is per-profile (hence both
  `~/.hermes/sandboxes/<backend>/` and `~/.hermes/profiles/<name>/sandboxes/<backend>/`).
- Stays empty when `terminal.backend` is `local` (the common case). An empty
  `<backend>/` subdir just means that backend path was initialized/probed once —
  it does NOT mean anything ran there. Do not present it as evidence of activity.

## `plans/`

Profile-scoped plans dir. `/plan` itself writes workspace-relative
`.hermes/plans/YYYY-MM-DD_HHMMSS-<slug>.md` relative to the active working
directory; see `references/automation-surface.md`.

## All four are runtime/user data

`hermes_cli/profile_distribution.py::USER_OWNED_EXCLUDE` lists memories,
sessions, logs, plans, workspace, home, sandboxes (plus caches and state DBs),
so clone / export / import never carries them.

## The "workspace" that actually matters

The agent's working directory — where `terminal`, `read_file`, `write_file`,
`patch`, and `search_files` operate. It is **not** profile-owned: it is wherever
`hermes` was launched, or `terminal.cwd`, or a cron job's `workdir=`. "Code
workspace" detection for the coding posture + LSP
(`agent/coding_context.py`) keys off that cwd being a git repo.

Answer shape for this class: separate the two meanings first ("workspace means
two different things in Hermes"), name the per-profile dir as usually-empty
scratch, then state that the workspace that matters is the cwd the profile does
not own. Give the source file the claim came from.
