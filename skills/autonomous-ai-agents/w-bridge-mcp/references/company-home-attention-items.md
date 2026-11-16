# Company Home / attention items — data model & insert path

Verified against the running bridge (localhost:8031) and Rails backend (bonfire app, localhost:3000) on 2026-09-07. Rails source: /home/siavash/Documents/codes/Pavel/bonfire.

## The 7 categories
`AttentionItem::CATEGORIES` in `app/models/attention_item.rb`:
decisions_waiting, blockers, outcomes_review, mentions, material_changes, ai_confirm, knowledge_proposals

Company home (`Users::CompaniesController#home`) renders `AttentionItem.for_user(Current.user).open_items.ordered` grouped by category (`@items_by_category`). Doc: bonfire/docs/company_home_data_model.md.

## attention_items table semantics
- NO company_id column. Items are optionally scoped: `user_id`, `project_id`, `room_id` all optional; polymorphic `source`/`target` (source_type/source_id, target_type/target_id) plus `resolved_by` user.
- Columns: category, title, meta_text, due_at, overdue (bool), status, action_label, ai_confirm (bool), resolved_at, timestamps.
- The home-page partial uses `target_type` to build links: "project_status" → open project status, "project_knowledge" → open knowledge, "room" → open room.

## MCP exposure (w-bridge) — list-only
All seven category tools funnel through one handler `_list_attention_items_by_category(category)` (mcp/tools.py) → GET `/api/attention_items?category=<cat>`. Tool schemas expose only filters: project_id/project_name, room_id/room_name, user_id/user_name, status, overdue, ai_confirm, page, per_page. No create/update/delete attention tool is registered.

## Rails API — the writer
Routes (bonfire/config/routes.rb): `resources :attention_items, only: %i[index show create update destroy]` under the `/api` namespace (Api::BaseController).

- POST /api/attention_items — body:
  - required: `title`, `category` (free-form string; the 7 CATEGORIES are the canonical values the home page groups by)
  - optional: `meta_text`, `due_at` (ISO string; Time.zone.parse — bad format → 422 "Invalid date format"), `status` (default "pending"), `overdue` (bool, default false), `ai_confirm` (bool, default false), `project_id`/`room_id`/`user_id` (must exist if given, else 404), `source_id`+`source_type`, `target_id`+`target_type`, `action_label`
- PATCH /api/attention_items/:id and DELETE /api/attention_items/:id mirror the same fields.
- Auth: `before_action :authenticate_token!` in Api::BaseController — `Authorization: Bearer $OUTPUT_EVENTS_TOKEN` (Rails env), secure_compare.
- Index filter params: category, status, user_id, project_id, room_id, created_at_gt/lt, page/per_page (40 default, max 200). Response envelope: `{"count": N, "attention_items": [...]}` — the bridge unwraps the list via `_paginated_list` (key "attention_items").

## Why MCP can't insert (dead-import pattern)
- `space/api/attention_items.py` fully implements `create_attention_item` / `update_attention_item` / `delete_attention_item` (+ get/list) against the endpoints above.
- `mcp/tools.py` imports all three at the top (`from space.api import ...`) but they appear in NO `_TOOL_METADATA` entry (~line 1955+) and NO `TOOL_HANDLERS` mapping (~line 1824+) — dead imports, likely leftovers from when the list tools were added. Only `list_attention_items` is wired.
- As of 2026-09-07 nothing else in the Rails app auto-creates attention rows (grep for `AttentionItem.new/create` in app/ matches only api/attention_items_controller.rb) — POST is the only writer.

## Diagnostic recipe: "tool X is read-only but I need to write"
1. `tool_describe` the live tool — a filters-only schema means a list view.
2. Grep `mcp/tools.py` for the handler + check the `from space.api import ...` block for an unused write function (create/update/delete_<resource>).
3. Confirm it is NOT in `_TOOL_METADATA` / `TOOL_HANDLERS` → the backend supports the write; only MCP exposure is missing.
4. Insert either via direct Rails call (curl POST http://localhost:3000/api/<resource> with `Authorization: Bearer` from `/proc/<pid>/environ` of the running bridge, OUTPUT_EVENTS_TOKEN) or by registering the tool (add handler + `_TOOL_METADATA` entry + snake/camel alias) — then the MCP server must reload (VS Code debugpy session restart).
