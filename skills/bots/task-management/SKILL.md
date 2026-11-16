---
name: task-management
description: "owning the AI-task lifecycle on `/task-mcp` — creating, routing, tracking, and closing tasks for any profile."
---

# Task management

Type: action skill
Purpose: owning the AI-task lifecycle on `/task-mcp` — creating, routing, tracking, and closing tasks for any profile.

Verified against `db/schema.rb` (`ai_tasks`), `app/services/mcp/tools/tasks.rb`, and live registry dump 2026-11-02. task-mcp exposes exactly 8 tools: `ai_tasks`, `get_ai_task`, `create_ai_task`, `update_ai_task`, `delete_ai_task`, `get_ai_task_children`, `get_ai_task_parents`, `ai_task_cost`.

## Field reference (the real ai_tasks schema)

- `description` — the only required field and only free-text body (there is no `title`).
- `project_id` / `room_id` / `topic_id` — scope links; `project_id` always set by convention.
- `task_id` — external/linked identifier; `input_event_entity_id` — originating event/entity id. Preserve both when routing from events.
- Hierarchy: `level` (root = 0), `parent_task_id`, `grand_parent_id` (not `parent_id`/`grandparent_id`).
- People: `adder_profile` (creator), `assigneee_profile` (assignee — three e's).
- Context: `proposed_task_context` (known at creation) and `actual_task_context` (learned while working).
- State: `dispatched` / `finished` are the only flags (no `status`). Writing one also co-sets its legacy alias (`dispatched`→`added_to_kanban`, `finished`→`runned`) — never read a legacy flag as an independent signal.
- Cost: `token_used`, `usd_used`, `usd_budget`; `token_budget` is NOT writable through task-mcp; `importance` integer ≥ 0.

## Creating

1. Dedupe first: `ai_tasks(project_id, finished=false[, room_id, topic_id])` — reuse an equivalent open task instead of creating. A large list gets persisted to a spillover file — filter it with `search_files` (regex over the JSON text with context lines) or page it with `read_file`; never re-request the same API payload. To COUNT rows without running code, `search_files` with `output_mode: count` on a per-row field (e.g. `"assigneee_profile"`) equals the row count — unattended surfaces (api_server) can refuse `execute_code`, so treat count-by-grep as the primary path, not the fallback. To REBUILD rows (each id paired with a field) the same way, grep each field anchored at row indentation — pattern `^    "id": ` and `^    "updated_at": ` — and pair the two ordered match lists positionally, because the emitter keeps a stable row order; only then re-fetch the few delta ids with `get_ai_task` for detail instead of paging the whole payload. Before trusting any pairing, confirm both greps return the SAME match count as the row count — a mismatch means that field also appears nested and positional pairing is unsafe. This doubles as the way to prove a "nothing changed since the last pass" claim: a carried row whose paired `updated_at` predates that pass is verifiably untouched.
2. `create_ai_task(description, project_id, [room_id, topic_id, level, parent_task_id, grand_parent_id, adder_profile: "workspace", assigneee_profile, proposed_task_context, input_event_entity_id, task_id, importance, usd_budget], dispatched: false, finished: false, token_used: 0, usd_used: 0)`.
3. Hierarchy: child → `parent_task_id` = parent id, `level` = parent.level + 1, `grand_parent_id` = parent's `parent_task_id`; root → nulls and `level: 0`. Never create children deeper than `level` 3.
4. Never create when the (parent) task budget is exhausted: `usd_used >= usd_budget` (when allocated); `null` budget = no gate.
5. Omit optional fields you don't know — do not invent values.

## Working a task (any profile)

1. `get_ai_task` — confirm exists and not `finished`; never re-open finished tasks, create a follow-up child instead. Findings quoted inside a task `description` are a creation-time snapshot — concurrent bots can supersede them within minutes — so re-verify every cited fact (owner gaps, empty listings, approval/flag states) with live reads before adopting it into the answer, and record the supersession explicitly in `actual_task_context` when live state contradicts the brief.
2. Start: `update_ai_task(task_id, dispatched: true)` — pass only the field you are changing. Do NOT resend `assigneee_profile` even when the task already names you: re-passing the unchanged assignee trips task-mcp's validation and fails the whole dispatch call. There is no start timestamp; `updated_at` serves. A `dispatch_error` (e.g. `Net::ReadTimeout`) persisting on the row while `dispatched: true` is a platform redelivery artifact, not a failed dispatch — do not re-dispatch or re-execute on the redelivery; work the task once and note "worked once, no duplicate" in close-out `actual_task_context` so later deliveries read as noop.
3. Blocked: append the blocker to `description` and/or record the exact input needed plus the post-receipt path in `actual_task_context` via `update_ai_task` (no notes/status fields exist). A blocked task stays dispatched-open: `finished: false` and NO `ai_task_cost` write — cost+finished is close-out only, and a mid-run cost write makes the row look concluded. On task redelivery, read your own `actual_task_context` and the room's `tool_cal_logs` first: an already-posted input question means handle-as-noop, not re-ask.
4. Child tasks: re-validate parent via `get_ai_task_parents` before deep work.
5. Finish: FIRST `ai_task_cost(task_id, token_used, usd_used)` — it writes the costs and rolls deltas up to every ancestor; then `update_ai_task(task_id, finished: true, actual_task_context: "<what was done/learned, ids touched, verdict if no action>")`. Tasks carry no usage meter: estimate `token_used`/`usd_used` best-effort and write "estimated" in `actual_task_context` so later reads don't mistake recorded costs for measured ones. Never forward-cite the close-out `tool_cal_log` id in that context — it does not exist when the context is written and the id may land elsewhere; cite deliverable ids (message, topic link) instead and write the close log after `finished: true`.

6. Every entry in a `tool_call` `calls` array needs BOTH `name` and `arguments`. An entry that lost its `name` surfaces as a misleading JSON parse error, not a schema complaint — the exact wording and offset vary by payload ("Expecting property name enclosed in double quotes", "Expecting ',' delimiter: line N column M", …) and it happens in single-entry calls too, not just multi-entry batches. On any `"calls" is not valid JSON` error, first re-check that each entry carries a `name` key rather than debugging the payload text. If a corrected multi-entry batch STILL fails, do not iterate on the payload again — send each entry as its own single-entry `tool_call` array with the `name` key present; single-entry calls land cleanly.

## Update immutability

`update_ai_task` can change only: `description`, `adder_profile`, `assigneee_profile`, `actual_task_context`, `dispatched`, `finished` (+ legacy aliases), `topic_id`, `task_id`, `input_event_entity_id`. Costs move only via `ai_task_cost`. Everything else (`project_id`, `room_id`, `level`, parent links, budgets, `importance`, `token_budget`) is fixed at creation.

## Deletion

`delete_ai_task` is for erroneous duplicates you created — never for closing work; closing means finished + cost.

## Example — route a follow-up child

```json
{"tool": "create_ai_task", "arguments": {
  "description": "Re-verify ADR-7 scope freeze against reopened item 66",
  "project_id": 2, "parent_task_id": 88, "level": 1, "grand_parent_id": null,
  "adder_profile": "workspace", "assigneee_profile": "coder",
  "proposed_task_context": "all_hands item 66 reopened 2026-11-02; parent task 88 delivered ADR-7",
  "input_event_entity_id": 66, "dispatched": false, "finished": false,
  "token_used": 0, "usd_used": 0, "importance": 3}}
```

Close-out when done:

```json
{"tool": "ai_task_cost", "arguments": {"task_id": 91, "token_used": 24500, "usd_used": 0.19}},
{"tool": "update_ai_task", "arguments": {"task_id": 91, "finished": true,
  "actual_task_context": "ADR-7 still valid; note added to record; blocker 43 left open"}}
```
