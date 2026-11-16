# Per-Profile Providers, Models & Fallback

Verified against the live install by reading `hermes_cli/fallback_config.py`,
`hermes_cli/config_defaults.py`, and the per-profile `config.yaml` / `.env`
files. Answer provider questions for a profile from the live files — never
from inference.

## The isolation fact

Each profile owns its own `config.yaml`, `.env`, `auth.json`, sessions,
skills, and memory. So provider/model choice is genuinely per profile:

```bash
hermes -p coder   config get model.provider   # -> deepseek
hermes -p coder   config env-path             # -> ~/.hermes/profiles/coder/.env
```

The global `-p/--profile` flag applies to any subcommand, so
`hermes -p NAME fallback list` scopes the fallback chain to that profile.
Read it back to confirm rather than assuming.

## Three distinct mechanisms — do not conflate them

1. **Parallel role routing** (providers live at the same time, no failure
   needed). Main agent plus each aux task plus the delegation block can each
   point at a different provider.
2. **Sequential fallback** (`fallback_providers`) — only fires on
   rate-limit, overload, or connection errors on the primary. Not
   load-balancing, not per-task routing.
3. **Session override** — `hermes -p NAME -m MODEL`, or `/model MODEL`
   in-session (`--global` to persist), plus `model.aliases.<name>` which
   resolve before the built-in alias table.

## 1. Role routing (parallel)

Main agent:

```yaml
model:
  provider: deepseek
  default: deepseek-v4-flash
  base_url: https://api.deepseek.com/v1
```

`auxiliary.<task>` — side-LLM calls. Each accepts
`provider | model | base_url | api_key | timeout | extra_body |
reasoning_effort`, and each is **independent**: main-agent provider routing
and `openrouter.min_coding_score` explicitly do NOT propagate to aux calls
(by design, per the config_defaults comments).

Full task list (from `config_defaults.py`, the `auxiliary` block):

```
vision, web_extract, compression, skills_hub, approval, mcp,
title_generation, memory_query_rewrite, tts_audio_tags,
triage_specifier, kanban_decomposer, profile_describer,
goal_judge, curator
```

`provider: auto` means "pick sensibly"; an empty `model` means the provider's
default aux model. Example split: vision + delegation on gemini, compression
on a free OpenRouter model, main agent on deepseek.

`delegation` block — what `delegate_task` subagents run on:

```yaml
delegation:
  model: google/gemini-3-flash-preview   # empty = inherit parent model
  provider: openrouter                   # empty = inherit parent provider
  base_url: ""                           # direct OpenAI-compatible endpoint
  api_key: ""                            # for base_url; falls back to OPENAI_API_KEY
  api_mode: ""                           # chat_completions | codex_responses | anthropic_messages
```

Voice is likewise per profile: `stt.provider` (local/groq/openai/mistral/
elevenlabs/deepinfra) and `tts.provider`.

## 2. Fallback chain (sequential)

Schema (`hermes_cli/fallback_config.py`) — a list, order preserved,
duplicates (same provider+model+base_url) dropped:

```yaml
fallback_providers:
  - {provider: openrouter, model: anthropic/claude-sonnet-4-6}
  - {provider: gemini,     model: gemini-2.5-pro}
  - {provider: custom,     model: my-local, base_url: "http://x:8080/v1", key_env: MY_KEY}
```

- Per-entry key resolution: inline `api_key`, else `key_env` (alias
  `api_key_env`). `key_env` is resolved through
  `agent.secret_scope.get_secret`, which respects the ACTIVE profile's scope —
  so in a multiplexed gateway profile A cannot read profile B's credential.
  If neither yields a value, resolution falls through to the provider's own
  standard credential lookup.
- Only provider+model are required; `base_url` is normalized (trailing `/`
  stripped) and required for `custom`.
- Legacy `fallback_model` still works and is appended after
  `fallback_providers`.

CLI (per profile):

```bash
hermes -p NAME fallback list      # default when no subcommand; ls/rm also exist
hermes -p NAME fallback add       # provider+model picker, appends to chain
hermes -p NAME fallback remove
hermes -p NAME fallback clear
```

## 4. Custom / self-hosted OpenAI-compatible endpoints

`custom` is a first-class provider (aliases: ollama, local, vllm, llamacpp) with
`env_vars=()` and no default URL — both are user-configured. Routes:
`hermes model` → Custom entry (probes `<url>/models`, saves to
`custom_providers`, key → `.env` via `key_env`), or
`config set model.provider|custom.base_url|model.default` (scalars), or a
multi-entry `custom_providers:` list.

The three facts that decide whether it works:

- `model.base_url` is only honoured for a bare `custom` when `model.provider` is
  literally `custom` (or an ollama/vllm/llamacpp alias). Otherwise the stale-URL
  guard ignores it and the session quietly hits OpenRouter/DeepSeek instead —
  so a "config set base_url didn't do anything" report is usually this.
- `OPENAI_BASE_URL` is NOT consulted any more; `CUSTOM_BASE_URL` env still is.
  Key chain: explicit → `model.api_key` → host-gated `OLLAMA_/OPENAI_/
  OPENROUTER_API_KEY` → `<VENDOR>_API_KEY` derived from the host
  (`mysiavash.com` → `MYSIAVASH_API_KEY`) → custom credential pool → literal
  `"no-key-required"` (why an auth-less local server works).
- The endpoint needs `POST /chat/completions` **with tool calling** — Hermes is
  a tool-calling agent; a model that can't emit tool calls is unusable, not
  merely limited. Dead host = every turn fails unless `fallback_providers` is set.

Full resolution order, env-var naming, verification commands, and the answer
shape for this question class: `custom-openai-compatible-endpoints.md`.

## Pitfalls specific to providers

- **`hermes config set` cannot write the fallback list.** `set_config_value`
  coerces bool/int/float and never parses lists/JSON, so
  `config set fallback_providers ...` is not the path. Use
  `hermes fallback add`, or `hermes config edit`.
- **Scalar keys are fine to set.** `config set model.provider gemini`,
  `model.default ...`, `model.base_url ...`, and
  `auxiliary.compression.provider ...` all work — they are scalars.
- **A provider with no key in THAT profile fails closed at request time.**
  Key presence is per profile `.env`; profiles cloned from the same source
  share whatever key set the source had. Check before promising a switch
  works — `scripts/profile-provider-audit.sh` prints key NAMES only (never
  values) to keep secrets out of transcripts.
- **Switching a profile's model changes everything bound to that profile** —
  its alias wrapper (`hermes -p coder` / the `coder` alias), and any cron job
  or `delegate_task` that runs under it.

## What to check before answering

```bash
scripts/profile-provider-audit.sh          # per-profile provider, default, keys
hermes -p NAME config get model            # full resolved model block
hermes -p NAME fallback list               # chain state
```
