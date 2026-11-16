---
name: bonfire-mcp
description: "Use when working with the Bonfire/PWR Rails MCP (W-space)."
---

# Bonfire / PWR Rails MCP (W-space)

The Rails app (repo `pwr`, app historically "bonfire", platform branded PWR in the workspace SOULs) serves the business-object MCP surface on localhost:3000. Hermes registers it as the `W-space` MCP server; its tools arrive as `mcp__W_space__<tool>`. Sibling to `w-bridge-mcp` (the Python bridge on :8031) — different server, different tool naming surface. Load this skill for any work against `mcp__W_space__*` tools, any endpoint/scope question, and whenever reviewing a SOUL or doc that makes tool claims about PWR.

## Repo and endpoints
- Repo: /home/siavash/Documents/codes/Pavel/W/pwr. Earlier checkouts (`W/bonfire`, `~/Documents/codes/Pavel/bonfire`) have been renamed/moved between sessions — when a remembered path is missing, re-resolve before grepping.
- MCP endpoints (config/routes.rb, all POST JSON-RPC, protocol 2024-11-05, serverInfo "bonfire-mcp"):
  - `/mcp` — every tool (~163)
  - `/action-mcp` — mutations plus most reads (~142)
  - `/read-mcp` — read tools only (~78)
  - `/knowledge-mcp` — topics/analysis family only (~29)
  - `/task-mcp` — the AiTask family only (9)
- Auth: `Authorization: Bearer $MCP_W_SPACE_API_KEY` (value in ~/.hermes/.env). Send `Accept: application/json, text/event-stream`. The server answered `tools/list` with no Mcp-Session-Id (stateless on this box). GET on `/mcp` returns 404 while POST works — normal.

## Scope partitioning — read app/services/mcp.rb before trusting endpoint intuition
`registry.rb` enforces scope at CALL time: a tool outside the endpoint's scope errors `Tool 'x' not found in scope '<s>'`. Registration pattern in `app/services/mcp.rb`:
- `add_/edit_/delete_` → `all + action`; topic mutations also `knowledge`; task mutations also `task`.
- list/get tools → `all + read` (+`action` for most families; RoomContext/* and AiConfig/* are `all + read` only).
- NON-OBVIOUS: the project-knowledge family (`add_project_knowledge_item`, `add_project_decision_record`, `add_knowledge_activity_log`, `add_tree_based_project_directory_item`, `add_external_knowledge_asset`) is ACTION-scope only — it is NOT on `/knowledge-mcp`, which holds only topics, message analysis, room history, and topic tool-call logs. Anything routing "knowledge capture" to `/knowledge-mcp` breaks at runtime.
- Endpoint choice is PROFILE CONFIGURATION, not agent behavior: one connected server URL fixes the visible toolset; a model cannot route per call. Use `/task-mcp`, `/knowledge-mcp`, or `mcp_servers.<name>.tools.include` to shrink a low-end model's surface — 163 schemas is a heavy token/attention tax.

## Names and aliases
- Canonical task family: `ai_tasks`, `get_ai_task`, `create_ai_task`, `update_ai_task`, `delete_ai_task`, `get_ai_task_children`, `get_ai_task_parents`, `ai_task_cost`. Aliases (`get_task`, `create_task`, `task_cost`, ...) resolve at call time but NEVER appear in `tools/list`. A local deferred-tool catalog showing the short names predates the rename — live `tools/list` is authoritative; do not fault a SOUL's tool names against a stale local catalog.
- `update_ai_task` accepts ONLY: task_id, description, adder_profile, assigneee_profile, added_to_kanban, runned. There is NO status/result field anywhere in the task family — record outcomes by appending a result line to `description` and setting `runned=true`. A SOUL step saying "update the task status/result" is unimplementable as written.
- `create_ai_task`: required `description`; optional project_id, room_id, parent_task_id, grand_parent_id, adder_profile, assigneee_profile, token_used, usd_used, usd_budget, importance, level.

## Live surface check (the verification recipe)
Use whenever reviewing a SOUL/doc's tool claims, after any repo rename, or when a session catalog conflicts with source:

```bash
KEY=$(grep -h "^MCP_W_SPACE_API_KEY=" ~/.hermes/.env | cut -d= -f2 | tr -d '"')
for ep in mcp task-mcp knowledge-mcp action-mcp read-mcp; do
  curl -s -X POST http://localhost:3000/$ep \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
done
# Response may be a plain JSON body or an SSE 'data: {...}' line — parse both.
```

The returned names + inputSchema are the exact set a profile connected to that endpoint can call.

## Pitfalls
- Repo paths, dir names, and tool names drift BETWEEN sessions (bonfire→pwr; get_task→get_ai_task). Re-verify each round; never carry forward a previous round's counts or names.
- Verify scope claims about endpoints against the registration list in `app/services/mcp.rb`, not against the endpoint's name — the knowledge split is the counterintuitive one.
- Company status item tools keep the write-path vocabulary mismatch documented in `w-bridge-mcp` (that bridge is a separate server; scope facts here apply to the Rails MCP itself).
