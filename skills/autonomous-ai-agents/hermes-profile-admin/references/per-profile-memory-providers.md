# Per-Profile Memory Providers (built-in, and OpenViking vs another backend)

Verified live 2026-10-05 by reading `hermes_cli/config.py` + `config_defaults.py`,
`plugins/memory/openviking/__init__.py`, every profile's `config.yaml`, and by
running `hermes [-p NAME] memory status`. Answer this question class from the
live install, not from the bundled docs.

## Verdict shape

YES — the external memory backend is per profile, and it is NOT inherited from
the root config. Two axes matter and they are separate:

1. **Which provider** a profile uses (built-in only vs openviking vs …) —
   `memory.provider` in THAT profile's `config.yaml`.
2. **Whether two profiles on the SAME provider share one store** — decided by
   the provider's own connection/scope settings (per-profile `.env`), not by
   Hermes. By default: shared.

## Axis 1 — provider resolution (per profile, no root inheritance)

- `get_config_path()` → `get_hermes_home() / "config.yaml"`, and profiles switch
  `HERMES_HOME` (cache is keyed on the path, so profiles don't collide). So the
  effective config is `DEFAULT_CONFIG` deep-merged with
  `~/.hermes/profiles/<name>/config.yaml` — `_load_config_impl` /
  `_deep_merge` in `hermes_cli/config.py`.
- **There is no fallback to `~/.hermes/config.yaml`.** The root file is read only
  by the `default` profile. A new profile is a fresh workspace (profiles.py
  comment: "A new profile is a fresh workspace — inheriting the source …").
- `DEFAULT_CONFIG["memory"]["provider"]` is `""` = built-in only
  (`config_defaults.py`, the `memory:` block ~L1638-1662). Comment there: "Only
  ONE external provider is allowed at a time."
- 8 external providers ship as plugins under `hermes-agent/plugins/memory/`:
  `honcho, openviking, mem0, hindsight, holographic, retaindb, byterover,
  supermemory`. Built-in `MEMORY.md` / `USER.md` is ALWAYS on alongside whichever
  external provider is selected.
- Change it per profile (scalar — safe with the CLI):
  `hermes -p coder config set memory.provider openviking` (or holographic, mem0,
  hindsight, …). Only one at a time.

### Verify (per profile, non-interactive)

```bash
hermes -p NAME memory status      # prints "Provider:  openviking" / "(none — built-in only)"
hermes memory status              # = the `default` profile
```

Unlike `hermes tools`, `memory status` runs fine through a pipe — it is the
authoritative, cheap answer for "which memory does profile X use".

### Trap: a `memory:` block with no `provider:` key

A profile can have a `memory:` block (char limits, `flush_min_turns`, …) and no
`provider:` line — that resolves to DEFAULT_CONFIG's `""`, i.e. **built-in
only**. It does not "inherit the root profile's openviking". Live on this box
(2026-10-05): `default` + 14 profiles = `provider: openviking`; `coder` (block,
no provider key) and `testprofile` (no `memory:` block at all) = built-in only.

## Axis 2 — same provider, shared store unless you partition it

Two profiles both pointing at `provider: openviking` still read/write ONE OV
store, because the connection + scope come from env/config values that are
currently identical:

- `plugins/memory/openviking/__init__.py::_resolve_connection_settings` resolves
  endpoint/api_key/account/user/agent from env FIRST, then `ovcli.conf.ov`
  (when `memory.openviking.use_ovcli_config: true` + `ovcli_config_path`).
- Keys, per profile `.env`: `OPENVIKING_ENDPOINT`, `OPENVIKING_API_KEY`,
  `OPENVIKING_ACCOUNT`, `OPENVIKING_USER`, `OPENVIKING_AGENT`. **`OPENVIKING_AGENT`
  is the peer id** (`_DEFAULT_AGENT = "hermes"`); peer-scoped memories land under
  `viking://user/<account>/peers/<agent>/memories/`.
- On this box NO profile `.env` sets any `OPENVIKING_*` var, so every openviking
  profile resolves endpoint from `~/.openviking/ovcli.conf.ov`
  (`http://127.0.0.1:1933`) and agent to `hermes` → one shared peer namespace
  across all of them. To isolate: set a per-profile `OPENVIKING_AGENT` (and,
  if wanted, account/user/endpoint) in each `profiles/<name>/.env`.

## Also per profile via the same mechanism (worth naming in the reply)

`profiles/<name>/memories/MEMORY.md` + `USER.md`, the session DB, `skills/`,
`cron/`, `plugins/`, and `.env`. So `hermes -p coder memory status` reports on
coder's world only.

## Answer shape for this user

Verdict first ("yes — per profile, and profiles don't inherit the root config"),
then the live per-profile table, THEN the sharing nuance (same provider =
shared store until `OPENVIKING_AGENT`/account are per-profile). Hold the
provider catalog and the env-var list behind an offer — they cap length on
factual lookups.
