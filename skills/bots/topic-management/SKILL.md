---
name: topic-management
description: "owning topics, message analysis, room history topics, and — critically — the `tool_cal_logs` audit trail for every action you take."
---

# Topic management

Type: action skill
Purpose: owning topics, message analysis, room history topics, and — critically — the `tool_cal_logs` audit trail for every action you take.

Topics live on `/knowledge-mcp` (also reachable via `/mcp` and `/action-mcp`). The workspace profile creates topics sparingly: topics are the memory spine, so wrong topics are worse than no topics.

## Tools

| Tool | Endpoint | Required | Notes |
|---|---|---|---|
| `topics`, `get_topic`, `search_topics`, `room_topic_tree` | knowledge/read | — | list/get/search before creating anything |
| `create_topic` | knowledge+action | `name` | optional: `memory`, `state`, `importance_level`, `need_an_action`, `required_actions`, `parent_topic_id`, `related_topics`, `project_id`, `active` |
| `update_topic`, `delete_topic` | knowledge+action | — | merge is per-field: a state/memory write leaves every other field untouched; delete only topics you created |
| `message_topics`, `get/create/update/delete_message_topic` | knowledge+action | create: message↔topic link | attach messages to topics when they extend a known thread |
| `message_analysis`, `get/create/update/delete_message_analysis` | knowledge+action | create: `message_id` | fields: `analysis`, `importance_level`, `message_content_summary`, `message_type`, `tags`, `is_a_response` |
| `room_history_topics`, `get/create/update/delete_room_history_topic` | knowledge+action | — | room-level historical clustering |
| `tool_cal_logs`, `get/create/update/delete_tool_cal_log` | knowledge+action | create: `used_tool_name` | your audit trail |

## Tool-call logging rules (binding for all skills)

After each successful state-changing call, `create_tool_cal_log`:
- `used_tool_name` = exactly the tool you called;
- scope: `project_id`, `room_id`, `topic_id` when applicable to the touched entity;
- `target_entity_id` = id string of the entity changed (dedupe anchor for event redelivery);
- `why_was_it_required` = triggering `event_type` or task id;
- `change_log` = one line, human-readable diff ("created milestone 12", "merged precondition into task 61").

Reads used purely for dedupe do not need logs; reads that drive a decision may be logged when the decision is non-obvious.

Payload keys must match the schema exactly — `create_tool_cal_log` silently DROPS unknown fields (passing `reason` instead of `why_was_it_required` persists the row with the field null and no error). Read every field back from the create echo; repair a dropped field via `update_tool_cal_log` (`tool_cal_log_id` + the field), never by creating a second row for the same action.

When issuing these writes through the deferred `tool_call` wrapper, send ONE invocation per `calls` array — multi-entry batches fail validation at the second entry even when the payload is valid JSON; parallel single-entry calls instead (standing rule in pwr-entities). Also pass numeric-looking ids (`target_entity_id`, `project_id`, `task_id`) as JSON integers, NOT quoted-digit strings: `create_tool_cal_log` with `"target_entity_id": "86"` was rejected twice with a spurious "'calls' is not valid JSON" parse error while the identical body carrying `86` wrote (the server stores the value back as a string either way). If a well-formed payload is rejected near a quoted id, re-send with ids unquoted before changing anything else.

`tool_cal_logs` list filters have NO `target_entity_id` parameter — to dedupe against that anchor, pull a page by `project_id`/`room_id` and match `target_entity_id` client-side.

## Topic discipline

1. Never create a near-duplicate topic: `search_topics(name)` + `room_topic_tree(room_id)` first.
2. `importance_level` (integer) and `need_an_action` gate downstream automation — set them deliberately, copy them from the analysis that justifies the topic.
3. When an event or task belongs to an existing topic, link the task (`ai_tasks.topic_id` — settable ONLY at creation, so route new child tasks with `topic_id` rather than editing old ones) and add a `message_topic` link for the driving message — and for your own reply/outcome message that closes one of the topic's `required_actions`, so the outcome is traceable from the topic side, not only from the message.
4. When your work COMPLETES one of a topic's `required_actions` (e.g. a requested reply is posted), pass the revised `required_actions` list in the SAME `update_topic` call — state/memory updates do not clear finished actions, so you pay a second write otherwise. A list passed as an array comes back JSON-encoded; that's expected.
5. `update_topic` fields are FULL REPLACEMENTS, not appends: to roll `memory`, `get_topic` immediately before writing, resend the entire existing text plus the new fact appended, and confirm the write echo carries both — reconstructing memory from an older read or from context silently drops facts written in between.
6. Answer-only passes (a question answered, nothing decided or executed) touch `memory` ONLY for anything describing a live gate or an action owed by ANOTHER acting/gated task (approval gates, freeze holds, execution plans) — leave those `state`/`required_actions` entries as they are and say so in the close-out ("gates untouched"). The exception: the entries YOUR own answering pass completes — whether an action names the task and source message (an `answer msg <id> (task <id>, in flight)` action) or merely describes the answer as work ("compile the blocker list", "post the inventory to room N") without any id; router-created topics use the id-less form. Completing them means retiring those entries and rolling `state` to answered in the SAME `update_topic` call per rule 4 — leaving them makes the topic claim an answer is still owed, so the next pass routes a duplicate answering task. When no live action remains, also send `need_an_action: false` with `required_actions` replaced by an empty string (the echo verifies it stored empty, not JSON-encoded). Carry the standing obligations (keep-current, no-repost-without-fresh-ask, recorded corrections) into the revised list so `need_an_action: true` never rides a list that lost its live entries.

## Example — record the footprint for a routed task

```json
{"tool": "create_ai_task", "arguments": {"description": "Draft MCP topic taxonomy", "project_id": 2,
  "topic_id": 7, "adder_profile": "workspace", "assigneee_profile": "knowledge",
  "input_event_entity_id": 456, "proposed_task_context": "message 456 in room 9 asks for taxonomy under topic 7"}}

{"tool": "create_message_topic", "arguments": {"message_id": 456, "topic_id": 7}}

{"tool": "create_tool_cal_log", "arguments": {"used_tool_name": "create_message_topic",
  "project_id": 2, "room_id": 9, "topic_id": 7, "target_entity_id": "456",
  "why_was_it_required": "message_created -> routed taxonomy task",
  "change_log": "linked message 456 to topic 7; taxonomy task created under it"}}
```
