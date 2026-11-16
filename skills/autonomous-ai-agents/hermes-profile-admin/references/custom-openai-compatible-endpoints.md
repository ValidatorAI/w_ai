# Custom / Self-Hosted OpenAI-Compatible Endpoints

"Can I use my own endpoint (mysiavash.com/v1, a local vLLM, a LAN box) instead
of DeepSeek?" — yes, `custom` is a first-class provider, not a fallback hack.
Everything below was read out of the live install (`~/.hermes/hermes-agent`,
2026-09): `plugins/model-providers/custom/__init__.py`,
`hermes_cli/runtime_provider.py`, `hermes_cli/main.py::_save_custom_provider`,
`hermes_cli/model_setup_flows.py::_model_flow_custom`,
`hermes_cli/config.py::custom_endpoint_key_env`.

## The provider

`CustomProfile(name="custom", aliases=("ollama","local","vllm","llamacpp",
"llama.cpp","llama-cpp"), env_vars=(), base_url="", default_max_tokens=65536)`.
No fixed env var and no default URL: both are user-configured. Endpoint quirks
it handles: `ollama_num_ctx` → `extra_body.options.num_ctx`; reasoning disabled
→ top-level `reasoning_effort="none"` **plus** `extra_body.think=false` (Ollama's
`/v1/chat/completions` ignores the latter, so both are sent); reasoning enabled
with an effort → top-level `reasoning_effort` only.

## Three ways to wire it

1. **Guided (preferred)** — `hermes model` → pick the Custom / OpenAI-compatible
   entry. `_model_flow_custom` prompts base URL (prefilled from
   `OPENAI_BASE_URL` / `OPENAI_API_KEY` **env only for prefill**), prompts a
   masked key, requires `http://`/`https://`, hints `/v1` for localhost-ish
   hosts, then probes `<url>/models` via `hermes_cli/models.probe_api_models` —
   and if only a variant URL answers it saves THAT resolved base URL instead of
   what was typed. Then it asks for `api_mode` (`chat_completions` |
   `codex_responses` | `anthropic_messages` | auto-detect) and the model name,
   and saves the entry to `custom_providers`. The key is written to the
   profile's `.env` and referenced as `key_env` when the flow took that path.
2. **Manual scalars** (`hermes config set` handles scalars fine):
   `model.provider custom`, `model.base_url https://host/v1`,
   `model.default <model-id>`.
3. **Named endpoints** — `custom_providers:` list, several endpoints side by
   side, each `{name, base_url, model, key_env | api_key, api_mode,
   models: {<id>: {context_length}}}`. `_save_custom_provider` dedupes by
   normalized (trailing-slash-stripped) `base_url` and updates the existing
   entry rather than appending. A legacy `providers:` mapping keyed by name
   (value `{api: ...}`) also resolves — see
   `tests/hermes_cli/test_custom_provider_identity.py`.

## Resolution order (the part that actually bites)

`runtime_provider.resolve_explicit_or_default_provider()`:

- **base_url** — explicit arg → `CUSTOM_BASE_URL` env → `model.base_url` (only
  when TRUSTED, below) → `OPENROUTER_BASE_URL` → built-in OpenRouter default.
  **`OPENAI_BASE_URL` is no longer consulted at all** ("config.yaml is the
  single source of truth for endpoint URLs"). So a user who exports
  `OPENAI_BASE_URL` and expects it to take effect gets OpenRouter instead.
- **Trust gate for a bare `custom` provider**
  (`_config_base_url_trustworthy_for_bare_custom`, GH #14676 / #27132): the
  config base URL is used only when `model.provider` is literally `custom` (or
  an alias that resolves to custom — ollama/vllm/llamacpp/…), or when the
  requested provider is `auto`. A non-loopback URL WITH a different
  `model.provider` is deliberately ignored (stale-URL hijack guard);
  `openrouter.ai` hosts are rejected even for loopback. **Symptom of tripping
  it: the session silently talks to OpenRouter/DeepSeek and never touches your
  endpoint.** Fix: set `model.provider custom` explicitly.
- **api_key** (non-OpenRouter context, first usable wins): explicit →
  `model.api_key` (only while the config base_url is the one in use) →
  `OLLAMA_API_KEY` if host is `ollama.com` → `OPENAI_API_KEY` if host is
  `openai.com`/`openai.azure.com` → `OPENROUTER_API_KEY` if OpenRouter →
  `_host_derived_api_key(base_url)`, i.e. `<VENDOR>_API_KEY` from the
  registrable host label (`api.deepseek.com` → `DEEPSEEK_API_KEY`,
  `mysiavash.com` → `MYSIAVASH_API_KEY`; returns `""` for IPs/loopback).
  Keys are host-gated on purpose so a `DEEPSEEK_API_KEY` can't leak to an
  unrelated endpoint. A custom credential-pool entry (keyed by base_url +
  optional provider name) is checked before all of this for `custom`.
- **No key at all is legal** — for `custom` with a non-OpenRouter URL the key
  falls back to the literal string `"no-key-required"`, which is what makes a
  local server with no auth work.
- **api_mode** — `model.api_mode` → `_detect_api_mode_for_url(base_url)`
  (`api.openai.com` → Responses API, `api.anthropic.com` → Messages) →
  `chat_completions`.

`.env` var name for an endpoint key is `HERMES_CUSTOM_<SLUG>_API_KEY`
(`custom_endpoint_key_env`: non-alphanumerics → `_`, uppercased), where the slug
comes from whatever identity the saving path used (the CLI flow passes
`host:port`) — so READ `custom_providers[i].key_env` instead of guessing it.

## Requirements on the endpoint

- `POST <base_url>/chat/completions` with OpenAI message/tool schema, and
  **function/tool calling** — Hermes is a tool-calling agent; a model that
  can't emit tool calls degrades to unusable, not "limited".
- `GET <base_url>/models` should list models: the picker probe and
  `hermes model --refresh` use it, and a probe failure only warns
  (`could not verify this endpoint … Hermes will still save it`).
- Put `/v1` in `model.base_url`; it must start with `http://` or `https://`.
- A dead/placeholder host fails every turn. Without `fallback_providers`
  (see `providers-and-fallback.md`) there is no automatic rescue.

## Verify before promising it works

```bash
curl -s -H "Authorization: Bearer $KEY" https://host/v1/models | head -c 400
hermes -p NAME doctor
hermes -p NAME status
hermes -p NAME config get model          # provider/base_url/default actually stored
hermes -p NAME chat -q "reply with exactly: ENDPOINT-OK"
```

If the endpoint needs no auth, the last command is the only real proof the
tool-calling path works end to end.

## Answer shape for this class of question

Lead with the verdict ("yes — `custom` provider"), then the three setup routes
in one line each, then ONLY the gotchas that would actually break them (provider
must be literally `custom`; `OPENAI_BASE_URL` ignored; key resolution order; the
endpoint must speak tool calling). Cap it — this user caps capability answers and
reads the verdict first. Do not answer from the bundled provider docs alone: the
trust gate and the key chain are not documented there, and they are the failure
modes users hit.
