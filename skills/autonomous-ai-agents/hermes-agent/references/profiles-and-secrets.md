# Profiles, Distributions & Cross-Profile Secrets

How per-profile secret scoping, git profile distributions, the api_server cross-profile API, and pluggable secret sources fit together. All routes verified against the live source tree.

## Cross-profile messaging: api_server + multiplexing

Enable the API surface in the DEFAULT profile's `config.yaml`:

```yaml
platforms:
  api_server:
    enabled: true
    extra:
      port: 8642          # default; env fallbacks API_SERVER_HOST/API_SERVER_PORT
```

with `API_SERVER_KEY` (≥16 chars) in `~/.hermes/.env`, then restart the gateway. Serves OpenAI-compatible `/v1/chat/completions`, `/v1/responses`, `/v1/runs`, `/v1/models`, `/api/sessions`, `/health`.

- `gateway.multiplex_profiles` is forced `true` (the only topology; an explicit `false` parses but is ignored with a warning). The default profile's gateway also serves every secondary profile under `/p/<profile>/v1/...` — so "message the message_analyzer profile" = `POST http://localhost:8642/p/message_analyzer/v1/chat/completions`.
- `/p/<profile>/` auth fails CLOSED: the request must carry the `API_SERVER_KEY` from **that profile's own secret scope** (`~/.hermes/profiles/<name>/.env`). It deliberately does not inherit the default profile's key — missing → 401, not a config bug.
- Bot-to-bot DMs across gateways: `hermes peer` + `bot_peers` in config.yaml; targets `<peer>/<profile>` hit exactly that `/p/<profile>/` mirror; the key lives as `HERMES_PEER_<NAME>_KEY` (profile-scoped secret store, then raw env).
- Session-key space: a routed `/p/<profile>/` prefix namespaces the session seed, so two profiles opening with identical text don't collide.

## Per-profile secret scope

- Each profile owns `$HERMES_HOME/.env` (`~/.hermes/profiles/<name>/.env`); MCP `${VAR}` headers, `API_SERVER_KEY`, webhook/HMAC secrets all resolve from the ACTIVE profile's scope (`agent.secret_scope.get_secret`).
- Under multiplexing with no scope active, `get_secret` RAISES `UnscopedSecretError` (fail closed) instead of reading `os.environ` — profile A's keys must never leak into profile B's turns. Single-profile deployments keep the `os.environ` fallthrough (systemd `Environment=`, `op run`).

## Skills, plugins, MCPs declare env requirements — three separate places

| Surface | Declaration | Enforcement |
|---|---|---|
| Skill | SKILL.md frontmatter: `required_environment_variables:` (bare names or dicts `name/prompt/url/help/optional`), `setup.collect_secrets:` (`env_var/prompt/provider_url`), legacy `prerequisites.env_vars` — all merged+deduped | At skill load: missing vars trigger an interactive capture that persists into the profile `.env`; until filled the skill reports `setup_needed`. **Messaging-gateway surfaces cannot prompt** — they tell the user to load the skill in the local CLI, so pre-fill `.env` for gateway-served profiles. |
| Plugin | manifest capabilities `requires_env: [NAME]` | Informational (`hermes plugins info` prints it); the plugin reads values from profile scope at runtime. |
| MCP connector | catalog `required_env` specs `{name, required, secret, default}` (`tools/connectors/mcp.py`) | The connector install flow writes the credential; the row stops asking once set. |

None of these feed `distribution.yaml env_requires` — the manifest is the only install-time declaration surface, so MIRROR the important skill/plugin/MCP var names into `env_requires` manually (a packaging script can scrape them from the staged tree: SKILL.md frontmatter entries + `${VAR}` tokens in `mcp.json`). Otherwise the installer only discovers missing keys mid-chat at skill-use time.

**Existing toolkit** (extend, don't rebuild): `~/Documents/codes/Pavel/W/pwr/`
- `to-profile-dist.sh PROFILE` — converts a live profile into a distribution repo: harvests secret NAMES (never values) from the profile `.env` into `env_requires`, writes `.env.template`, builds git history, post-commit leak-grep. Its rsync exclude list is narrower than `_SECRET_STORES` above — when touching it, keep the two lists in sync (`mcp-tokens/`, `auth/`, `vault/`, `webhook_subscriptions.json` etc. are the classic misses).
- `profile-env-collect.sh <repo-url|dir> [--install] [-o FILE] [-O] [--dry-run]` — closes the "install reports but never collects" gap: fetches the repo, harvests names from manifest + skill frontmatter + `${VAR}` placeholders, prompts one-by-one (hidden input for KEY/TOKEN/SECRET-style names), merges answers into the profile `.env` without clobbering existing keys.

## Profile distributions (`hermes profile install <git-url>`)

- `distribution.yaml` at the repo root is THE manifest (read by `hermes_cli/profile_distribution.py`; a repo without it is "not a distribution"). `env_requires:` is a list of `{name, description, required, default}`.
- Install reports, never collects: the preview checks each required var against the installer's shell env AND the target profile's existing `.env`, printing `✓ set` / `needs setting` / `—` (optional). The only prompt in the whole flow is "Proceed?". Afterwards it writes `.env.EXAMPLE` generated FROM `env_requires` (only if the staged tree didn't ship one). Filling values is manual (`cp .env.EXAMPLE .env`) or interactive via `hermes -p <name> setup` / `hermes -p <name> auth add` (OAuth, writes the profile's own `auth.json`).
- Credential stores are hard-excluded at INSTALL/UPDATE time on the installer's machine even if the author committed them — but git history is NOT policed, so the author's `.gitignore` is the real guard. Canonical list to mirror in any packaging script: `_SECRET_STORES` in `hermes_cli/profiles.py` — `auth.json`, `.env`, `auth/` (note: excluding `auth.json` does NOT exclude the `auth/` dir), `mcp-tokens/`, `.op.env`, `npmrc`, `honcho.json`, `mem0.json`, `webhook_subscriptions.json` (per-route HMACs), `teams_pipeline_store.json`, `vault/`, `proxy/`, `home/`, platform session stores, `.ssh/.aws/.gnupg/.kube/.docker/.azure/.config/gh/.config/gcloud`, `.envrc` (root or nested under a skill).
- Updates never touch user-owned data: memories, sessions, `.env`, `auth.json`, logs, state — filled keys survive version bumps. `config.yaml` is preserved unless `--force-config`. Shipped cron jobs install PAUSED (`hermes -p <name> cron list` to review).
- After `--clone`, `.git/` is stripped from the installed profile — don't assume the profile dir is a git checkout.

## External secret managers (secret sources)

- Contract: `agent/secret_sources/` — built-ins Bitwarden + 1Password (`hermes secrets bitwarden|onepassword`), third-party plugins register via `PluginContext.register_secret_source()`; the registry rejects sources whose `api_version` doesn't match the installed core.
- Sources resolve AT PROCESS STARTUP (via `hermes_cli/env_loader` `apply_all`), before Hermes reads `os.environ`, and land in each profile's scope. Strictly read-only at startup — there is no hot reload.
- Consequence for restart discipline: `hermes profile update` or a secret rotation while the gateway runs leaves the running process on stale plugin/secret/MCP state → `hermes gateway restart`. A gateway started AFTER install picks everything up fresh — no restart needed; entrypoint scripts that install/update profiles then `exec hermes gateway run` as the last line are correct.
- A mapped source with `override_existing: true` beats `.env` values — so runtime skill-capture prompts still write into `.env`, but the next start overrides those values with the manager's; bind everything in the manager and treat capture as the fallback.
- Worked example: `antonba/hermes-infisical-plugin` — registers a mapped source (`inf://project/env/folder/NAME` refs, optional `?type=dynamic&field=&ttl=`) plus a bulk source (whole project/folder injection that yields conflicts); config lives in `secrets.sources: [infisical, infisical_bulk]`. One bootstrap agent-token file per machine replaces N plaintext keys, and `plugins/` is distribution-owned so the plugin itself can ship inside a profile dist. Audit any third-party secret plugin before enabling — it reads every credential at startup.

## Pitfalls

- Anything after an `exec` in a shell script never runs (`exec` replaces the process). Dead `exec` lines after a gateway `run`/`restart` look like failover but are unreachable.
- A bootstrap that checks "$PROFILE_DIR/$name exists → update, else install" must point the SAME path `hermes profile install` writes to: `$HERMES_HOME/profiles/<name>`. If the existence check and the install target diverge, every boot re-runs install against an existing profile (which errors).
- `hermes config set gateway.multiplex_profiles true` in a bootstrap is unnecessary (forced on) and silently strips every comment from config.yaml.
