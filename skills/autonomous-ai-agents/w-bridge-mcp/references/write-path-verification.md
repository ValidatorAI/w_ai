# Write-path verification (three layers) — verified 2026-09-30

Companion to the "Capability surface" section of SKILL.md. That section lists
objects the registry does NOT appear to have. Before repeating such a "missing"
claim — especially to a user reviewing whether W-space/Bonfire can carry a feature
— check all three layers, in order, and say which one breaks:

1. **Rails schema**:
   `sqlite3 /home/siavash/Documents/codes/Pavel/W/bonfire/storage/db/development.sqlite3 ".tables"`
   then `".schema <table>"`. The schema prints on one long line, so parse the
   `"name" type` pairs (cut at the first `CONSTRAINT`) rather than grepping `^"`.
2. **Bridge payload**: `space/api/<entity>.py` — the `create_*` / `update_*`
   argument lists are exactly what gets POSTed (`prune({...})`). A column the
   bridge never sends is unreachable from this server.
3. **Agent reach**: `TOOL_DEFINITIONS` in `mcp/tools.py` (112 entries 2026-09-30);
   each tool's `properties` block is the contract.

Why this matters: a 2026-09-30 profile-capability review concluded from layer 3
headings alone that experiments / metrics / releases had "no object to write to",
and the user pushed back — "the feature exists in the bonfire & w-bridge mcp".
Layer 1+2 showed real carriers for most of it; the true gaps are narrower and
sit in the write path.

## Verified field map (2026-09-30)

- **Column ≠ writable**: `company_status_items.evidence`, `.impact`,
  `.target_date`, `.severity`, `.actions`, `.percent`, `.detail_category` exist in
  the DB and are absent from layers 2 and 3 (`source_type` is filter-only).
  Writable there: title, status, health, badge, summary, details, owner_name,
  position, project_id, company_status_period_id.
- **attention_items — fully writable**: title, category, meta_text, due_at,
  status, overdue, project_id/room_id/user_id, source_id + source_type,
  target_id + target_type, action_label, ai_confirm. No history table
  (`attention_item_events` is only a proposal in
  `DEMO_FUNCTIONALITIES_DB_IMPACT.md`), so per-item audit = resolved_at +
  resolved_by_id.
- **approval_requests + approval_request_actions — the human-approval and audit
  carriers.** Requests: request_type, payload json, status
  pending/approved/denied/canceled, agent_id, requested_at, resolved_at,
  resolved_by_id, message_id, room_id. Actions: action, actor_type, actor_id,
  note. `request_type` is the intended discriminator for kinds such as decision /
  knowledge_proposal / a deployment approval (the demo UI has an explicit
  "Deployment action approve/deny" prompt).
- **project_adrs**: identifier, title, decision_date, status, file_path, active →
  the decision and supersession carrier.
- **project_knowledge_activities**: actor_name, action_text, actor_color,
  target_path, target_url → traceability feed.
- **project_bottlenecks**: title, description, severity, resolved_at, resolved →
  severity is the ranking field.
- **project_all_hands_action_items**: assignee_name + due_date; **decisions**:
  basis + impact + badge. These are the only task/decision records carrying owner
  and date context.
- **Thin write sets**: `project_knowledge_items` → title/description/badge/active
  only (no source, confidence, evidence, version, supersedes). `project_todos` →
  title/meta_text/completed/completed_at only (no owner, due, evidence).
- **Present in the DB and referenced by NO profile SOUL** (unused-capability
  finding worth reporting): `file_reservations` (patterns, exclusive, expires_at,
  reason), `output_events` (event_type, event_data, group_id, synced),
  `ai_profile_tools` / `ai_profile_mcps` / `ai_profile_skills` (the structured
  per-profile allowed-tools boundary), `room_ai_activity_states` (the
  loading-message lifecycle state).
- **Naming**: `grep -c neurostack mcp/tools.py` → 0. The live note family is
  `project_obsidian_note` + `add_project_obsidian_note` /
  `edit_project_obsidian_note` / `delete_project_obsidian_note`. The neurostack
  MCP is a separate vault server (`vault_*` tools); the canonical knowledge
  subdomain in the Bonfire convention is `obsidian_notes`.

## Feature docs, and what each is authoritative for

- `bonfire/docs/page_sections_and_entities.md` — page → entities → MCP tool map
  (the surface a SOUL should attribute per profile).
- `bonfire/docs/DEMO_FUNCTIONALITIES_DB_IMPACT.md` — the demo flows and their DB
  impact: attention inbox lifecycle, company status snapshots, structured
  knowledge records, the AI-profile approval-constraint catalog, the approval
  workflow, AI room activity state.
- `W-bridge/mcp/tools.py` — the actual agent-reachable contract.
- The live DB schema — the last word on whether an entity/column exists at all.
