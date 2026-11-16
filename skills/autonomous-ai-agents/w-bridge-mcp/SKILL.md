---
name: w-bridge-mcp
description: "Use when working with the w-bridge MCP server or its tools."
---

# W-bridge MCP

W-bridge is the user's Python MCP server — sibling to the Bonfire Rails server in the same multi-agent architecture. It began minimal (single `hello` tool, 2026-09-04) but has since grown a LARGE tool registry (~121 tools, observed 2026-09-07): room messaging CRUD, project items (milestones, todos, bottlenecks, all-hands, obsidian notes, knowledge items, directory items), and company-status tools. Most tools are thin proxies (httpx) to a Rails "space" backend, plus a `/space_events` webhook. Developed/launched out of VS Code (debugpy); registered in Hermes config as an HTTP MCP server.

## Trigger
- User says "use the X tool from the w-bridge MCP" / "send a message via w-bridge" (room messaging, project items, company status).
- User asks which MCP servers are active/configured.
- Work on code under /home/siavash/Documents/codes/Pavel/W-bridge (git branch `mcp`).

## Project facts (verified 2026-09-07)
- Location: /home/siavash/Documents/codes/Pavel/W-bridge. Layout: `main.py` (FastAPI app), `mcp/server.py` (JSON-RPC handler), `mcp/tools.py` (parallel `TOOL_DEFINITIONS` + `TOOL_HANDLERS` dicts — new tools must go in BOTH; ~3200 lines), `space/api/*.py` (httpx client to the Rails backend), `space/schema/`, `db/models.py` + `alembic/`, venv at `bridge/`.
- Transport: `POST /mcp` → `handle_mcp_request()` in mcp/server.py. Protocol 2024-11-05, serverInfo name "w-bridge-mcp". MCP transport itself is unauthenticated (no Bearer/Mcp-Session-Id) — but the tools' backend bridge IS Bearer-authed (below).
- Tool registry families: room messaging (`add_message`, `add_loading_message`, `edit_loading_message`, `delete_loading_message`), project+room+user resolution, project items, company status periods/items, attention items. Camel-case alias names exist alongside snake_case (e.g. `AddMessage` == `add_message`).
- BACKEND BRIDGE: tools proxy through `space/api/_client.py` → httpx to `OUTPUT_BASE_URL` (default http://localhost:3000) with path prefix `/api/...` and header `Authorization: Bearer $OUTPUT_EVENTS_TOKEN` (default "your-token" in dev). Verified endpoints: GET /api/projects, GET /api/projects/{id}/rooms, GET /api/projects/{id}/users, POST message creation. Responses come back as Rails-style JSON (message objects carry id, room_id, creator_id, creator_type "User"/"Bot", system, body, has_attachment, timestamps).
- Env vars (read from the RUNNING process via `/proc/<pid>/environ`, pid from `ps aux | grep W-bridge/main.py`): `PORT` (default "80" — DO NOT assume; observed 8031), `OUTPUT_BASE_URL`, `OUTPUT_EVENTS_TOKEN`, `ROOM_BASE_URL`, `DATABASE_URL`.
- Listeners to check: `ss -tlnp | grep -E "3000|8031"` — 8031 = the MCP server, 3000 = the Rails backend it bridges to.

## Company status items — schema/mapping mismatch (verified live 2026-09-07)
- Rails `company_status_items` table columns (bonfire/db/schema.rb + `CompanyStatusItemsController#item_params`): company_status_period_id, category, position, title, status, subtitle, text, description, detail_category, owner, target_date, impact, percent, color, evidence, severity, icon, from_name, to_name, actions[]. NO project_id column — company status items are company-scoped, project_id is silently meaningless.
- The MCP "List or manage" tools (priorities/progress/risks/decisions/learnings/dependencies/changes → shared handler `_company_status_category_tool`) and `add_*` creators advertise a DIFFERENT vocabulary: health, badge, summary, details, owner_name. The bridge POSTs those raw keys (mcp/tools.py → space/api/company_status_items.py), Rails strong params does NOT permit them → silently dropped. Only keys that exist in BOTH vocabularies persist: title, status, position, category, company_status_period_id. Verify: created items 8–14 came back with description/owner/subtitle/... all null.
- Response shape is the Rails `as_json` vocabulary (description, owner, subtitle, color, icon, ...), so the mismatch is visible in every tool result: you send `details`/`owner_name`, the item echoes `description`/`owner` null.
- TRULY max-filled item requires POSTing to the Rails API directly: `POST http://localhost:3000/api/company_status_items` with `Authorization: Bearer your-token` and ALL permitted fields (verified: item id 15 with 15 populated fields incl. actions:["review","approve"]; round-trips fine through the MCP list tools — read path is correct).
- List filters share the bug: bridge sends `owner_name`/`health`/`badge` filters, Rails `index` filters on `owner`/`color`/`severity`/`detail_category`/`target_date`.
- Fix location if ever wired up: map in space/api/company_status_items.py create/update/list payloads + the `_company_status_category_tool` schema (health→color, badge→icon?, summary→subtitle, details→description, owner_name→owner) and add the missing permitted fields (text, impact, percent, evidence, severity, from_name, to_name, target_date, detail_category, actions) to the tool schemas.

## Room messaging semantics (verified live 2026-09-07)
- `add_message(room_id, user_id|user_name|bot_id|bot_name, body)` — room_id required (or room_name + project). `body` or an attachment required.
- Attachments (verified live 2026-09-08): pass `attachment_path=<local file>` or `attachment_url=<url>`. Response includes `has_attachment: true`, `attachment_filename`, `attachment_content_type` (guessed via mimetypes, e.g. text/markdown), `attachment_url: /api/projects/{p}/rooms/{r}/messages/{id}/attachment` (downloadable with the Bearer token; round-trip content is byte-identical to the source file). Numeric `user_id` (e.g. 2) works with no project context; creator_type "User".
- Loading-message lifecycle: `add_loading_message` auto-prefixes the body with `:spin: `; `edit_loading_message(message_id, body)` re-prefixes; `delete_loading_message(message_id)` removes. Edit/delete take ONLY `message_id` (no project/room needed).
- Tool results are JSON strings (the message object) or "Success" — not Bonfire's double-nested shape.
- Full create/send-tool catalog (all add_* tools, required fields, result shapes, company- vs project-scoped) → references/create-tools-catalog.md.

## Real-time actions & decision messages (verified live 2026-09-08)
- `add_action_message(room_id, user_id?, action_type)` — action_type `typing_start`|`typing_stop` (default typing_start). Numeric user_id works with no project context. Result `{"status":"ok","action":...}`. Emits an ActionCable broadcast ONLY — no persistent message is stored.
- `add_decision_message` REQUIRES `approval_request_id` in the current stack, enforced at three layers (MCP schema "required", bridge Python positional arg, Rails Api::DecisionsController 404). A decision (`approve`|`confirm`|`deny`|`cancel`, optional `note`) RESPONDS to an existing room-scoped ApprovalRequest — it does NOT create a standalone decision message. Approval requests ARE now mintable via the MCP: `add_approval_request(room_id, request_type="decision"|"knowledge_proposal"|..., status="pending", payload={...})` POSTs /rooms/:room_id/approval_requests (or /projects/:p/rooms/:r/... with project context) and returns the created row (verified live 2026-09-08: id 1 in room 4, payload round-trips incl. arbitrary keys). NOTE: NO creator/requester-user param exists anywhere in the chain (table has room_id, message_id, agent_id, request_type, payload, status, requested_at, resolved_at, resolved_by_id only) — "on behalf of user X" attribution goes in payload only; resolved_by_id is the resolver, set on decision. approve/confirm of a request_type "decision" auto-records a ProjectAdr and resolves linked attention items.
- Trap: `decisions_waiting` attention items are company-home cards (room_id null) — NOT room approval requests; never harvest an approval_request_id from them.
- Domain model, three-layer enforcement, side effects, and DB inspection recipe → references/actions-and-decisions.md.

## What the user means by "w-space" / "send_message" (2026-09-08)
- "w-space MCP" is NO LONGER just a nickname for this bridge: the Hermes root config now registers a real `W-space` MCP server pointing at the Bonfire/PWR Rails MCP `http://localhost:3000/mcp` (Bearer `${MCP_W_SPACE_API_KEY}`, ~163 tools, surfaced as `mcp__W_space__*`) — a DIFFERENT server from w-bridge (:8031, `mcp__w_bridge__*`). When the user says "w-space", check the live `mcp_servers` config and route by which server name actually exists; the Rails surface has its own skill (`bonfire-mcp`). (Historical note: earlier configs listed only `bonfire` (disabled) and `w-bridge`, and users' "w-space" meant THIS bridge.)
- The user calls the message-send action "send_message"; the actual tool is `add_message` (with attachment_path/attachment_url). Do NOT correct the name — just invoke add_message.
- The Rails :3000/mcp "bonfire" chat MCP is a DIFFERENT surface: its `send_message` takes only room_id + body — NO file/attachment param (verified live 2026-09-08). Do not route file-sending there and do not re-probe its tools/list when asked for "w-space": user directive "do not check rails mcp, file sending should exist in the send_message", then "do not check any file, just send_message with a file."


## Company Home / attention items (verified live 2026-09-07)
- The 7 categories have BOTH list and create tools: list views (`decisions_waiting`, `blockers`, `outcomes_review`, `mentions`, `material_changes`, `ai_confirm`, `knowledge_proposals` → `GET /api/attention_items?category=<cat>`) AND `add_*` creators (`add_decisions_waiting`, `add_blockers`, `add_outcomes_review`, `add_mentions`, `add_material_changes`, `add_ai_confirm`, `add_knowledge_proposals` → POST). The `add_*` tools take `title` (required) + optional project_id/user_id/room_id, meta_text, due_at ISO, status (default "pending"), overdue, ai_confirm, source/target polymorphic, action_label; they return the created Rails JSON item with `category` set server-side from the tool name. (Earlier on 2026-09-07 these were list-only — the create handlers got registered since; see git history of mcp/tools.py.)
- Writer payload semantics (Rails side, bonfire app on :3000 the bridge proxies to): `POST /api/attention_items` (title + category required; optional meta_text, due_at ISO, status default "pending", overdue/ai_confirm default false, project_id/room_id/user_id, source/target polymorphic, action_label). Full CRUD routed under `/api`; auth = `Authorization: Bearer $OUTPUT_EVENTS_TOKEN`. Verified example batch: 7 items ids 1–7, one per category, project_id=1 + user_id=1, listed back correctly.
- Rails `AttentionItem::CATEGORIES` == exactly those 7 strings. Company home is a user dashboard grouping open `attention_items` by category; table has NO company_id (user/project/room optional, polymorphic source/target).
- Payload semantics, response envelope, and the general "read-only tool but write needed" diagnostic recipe → references/company-home-attention-items.md.

## Directory explorer / tree-based project directory (verified 2026-09-08)
- Tools: `tree_based_project_directory_data(project_id, item_id?, delete?, attachment_path|attachment_url?)` — no item_id = LIST all items (JSON array: id, name, item_type "file"|"directory", file_path, parent_id, content); item_id alone = GET one; item_id + delete=true = DELETE; item_id + attachment_path|attachment_url = UPLOAD a local/remote file onto that existing item. `add_tree_based_project_directory_item(name, item_type "file"|"directory", attachment_path...)` creates a NEW item and can carry a file in one shot; `edit_tree_based_project_directory_item` mirrors it.
- Upload semantics (Rails side, verified live): upload PATCHes /api/projects/{id}/directory_items/{item_id} with multipart `file`. If the item already has a name it is KEPT even when it differs from the uploaded filename; the file is written to the Rails storage root as storage/projects/<project_id>/<item.name> and item.file_path is RESET to that name (e.g. docs/architecture.md → architecture.md — old relative path lost); item.content auto-fills from file text when blank.
- Worked example: attachment_path=/tmp/example-directory-explorer.md + project_id=1 + item_id=1 (item "architecture.md") → file landed at bonfire/storage/projects/1/architecture.md and the item JSON echoed the content. VERIFY uploads by checking that storage dir (file present + bytes match) — same discipline as elsewhere.
- Backend routes live in the bonfire Rails app on :3000: config/routes.rb maps `directory_items` → Api::ProjectDirectoryItemsController under /api/projects/:project_id/directory_items; the storage base dir is Rails.root/storage/projects/<project_id>.

## Resolution rules — THE key gotcha
- Numeric `room_id` + `user_id` pass through with NO project context needed.
- Name-based resolution (`user_name`, `room_name`, `bot_name`) REQUIRES `project_id` or `project_name`. Fuzzy matching is project-scoped. Failure is explicit: `user_name resolution requires project_id or project_name.` (same pattern for room_name/bot_name).
- Fix when the user gives a bare name (e.g. "send as siavash"): just pass `user_name` (or `bot_name`) + `project_id` (or `project_name`) and let the tool's fuzzy match resolve the user. DO NOT curl the backend to pre-discover user ids — user preference (stated 2026-09-07): "no need to find username, just send using the name and the tool automatically understands the correct user." Reserve backend probing for when the project itself is unknown.
- Observed example: room 4 ("releases") and user "siavash" (siavash mohammady, id 1) both live in project 1 (the only project); `add_message(project_id=1, room_id=4, user_name="siavash")` created the message as creator_id 1.

## Hermes tool availability (updated 2026-09-07)
- w-bridge tools appear in-session as deferred tools named `mcp__w_bridge__<tool>`: `tool_search` finds them, `tool_describe` loads the schema, `tool_call` invokes. These worked mid-session with NO Hermes restart while the server ran under VS Code debugpy.
- The native underscore form `mcp_w_bridge_*` still only loads at session start; if the server comes up after a session began and even the deferred catalog lacks the tools, restart Hermes or call the server directly over JSON-RPC (below).
- `hermes mcp test w-bridge` opens a fresh client, so it passes even when the current session hasn't discovered the tools — not proof of in-session availability.

## Direct JSON-RPC call (curl fallback)
No initialize handshake required before tools/call, no auth headers at the MCP layer. Verified working:

    curl -s -X POST http://127.0.0.1:8031/mcp -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}'

    curl -s -X POST http://127.0.0.1:8031/mcp -H 'Content-Type: application/json' \
      -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"hello","arguments":{"name":"example"}}}'
    # → {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"Hello, example!"}],"isError":false}}

- tools/call result is a FLAT content array `{"content":[{"type":"text","text":...}],"isError":bool}` — NOT Bonfire's double-nested shape. Most tools' `text` is itself a JSON string (use _format_result in mcp/tools.py).
- Error codes: -32700 parse, -32600 invalid request, -32601 method not found, -32602 invalid params.
- `notifications/initialized` with no `id` returns HTTP 204.

## Capability surface — what the registry HAS, and what it does NOT (verified 2026-09-30)

Read off the `##` / `###` headings of `docs/W-bridge/docs/mcp/TOOLS_REFERENCE.md`
(and `TOOL_DEFINITIONS` in `mcp/tools.py`). Canonical families: Core; Company Home
(7 attention categories, list + `add_*` + `edit_*`); Company Status (period +
priorities/progress/risks/dependencies/changes/decisions/learnings); Project
Milestones; Project Bottlenecks; Project Todos; Project Knowledge Items; Project
All Hands (takeaway/decision/action item); Project Decision Records (ADRs);
External Knowledge Assets; Knowledge Activity Log; Tree Directory; Knowledge
Summary Items; Project Obsidian Notes; Room Interaction (+ approval requests,
loading messages, action/decision messages); AI Config (profiles / tools / skills
/ MCPs / settings).

Objects that do NOT exist — know this BEFORE promising an E2E/demo flow that
needs them: hypothesis, experiment, metric / measured outcome, evidence artifact,
release / deployment record, incident / rollback record, review state
(ready-for-review / changes-requested / approved), qualified-sample or
participant record. Consequence, seen in a 2026-09-30 profile-capability review:
a spec asking for activation / repeat use / willingness-to-pay, or for version +
rollout scope + rollback plan on a release, has nothing to persist those fields
to — the values can only be forced into knowledge items, todos or company-status
items, which do not carry them. Answer such a request as a data-model gap (add a
tool family, or a decision to live with a lossy mapping), never by inventing a
tool name. Nearest partial fit: `company_status_items` DOES have an `evidence`
column at the Rails layer even though the MCP tool schemas drop it (see the
schema/mapping section above) — cite that as the exception, not the rule.
Re-verify before reusing this list: the registry grows (121 tools on 2026-09-07 →
171 by 2026-09-30), so re-read the headings rather than trusting these two dates.

## Pitfalls
- EXECUTE FIRST, INVESTIGATE LAST (user directive, 2026-09-08): when the user asks to run a tool demo ("send X to project Y using w-bridge mcp"), drive the MCP tools directly with sensible defaults — pick targets from a quick tool call (e.g. list directory items) and only create/pick a payload file as needed. Do NOT dig through git history, demo HTML, controller source, or storage dirs to infer intent; the user explicitly interrupted a repo-investigation detour with "just use w-bridge mcp, do not search repository to find what to do." Backend/repo probing is reserved for when the project or target itself is genuinely unknown.
- File payloads: when the user says "send a file" without naming one, CREATE a small clearly-labeled example file (e.g. /tmp/example-<topic>.md) and pass it as attachment_path — do not hunt for a canonical "example" file, and do not read/probe files to choose one ("do not check any file, just send_message with a file", 2026-09-08). Report the tool's returned JSON as the result; extra verification curl round-trips beyond one cheap check are noise unless asked.
- Name resolution needs project context (see above) — the #1 failure mode when sending as a named user.
- Never assume port 80: check `ss -tlnp` for the python listener (8031 observed under VS Code debugger); the backend Rails API it bridges to is on 3000.
- The URL in Hermes config is `http://0.0.0.0:8031/mcp` — fine for localhost calls, unreachable from other hosts.
- Verification style: assert against the backend API responses (Rails JSON), same discipline as bonfire-mcp-chat.
- Read the MCP process env (`/proc/<pid>/environ`) for the actual OUTPUT_BASE_URL / OUTPUT_EVENTS_TOKEN before curling the backend directly.
- To CREATE attention items use the `add_*` MCP tools (`add_decisions_waiting`, `add_blockers`, `add_mentions`, ...) — they POST to the Rails API and return the created item. Older sessions/skill notes claiming these are list-only are stale.
- Required id vs invented target: "execute first, investigate last" applies to CHOOSING a demo target — but when a tool's required id must reference an EXISTING record (e.g. add_decision_message's approval_request_id) and the user claims it is optional, prove it with a bare tool_call first (schema rejection is instant and conclusive), then check the backend controller/DB only to explain why. Never invent an id, and never insist from docs — the user's correction on 2026-09-08 ("approval id is not mandatory, used for later approval") was wrong for the running stack, but the empirical test settled it in one call.
