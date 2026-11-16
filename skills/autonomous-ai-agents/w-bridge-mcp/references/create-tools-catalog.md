# W-bridge create/send tools — catalog & semantics

All verified live 2026-09-07 against the dev backend (project 1, room 4 "releases").
Create-only tools listed below; delete tools exist for nearly all of them (delete_*).
Read/list variants exist too (`project_milestones`, `project_todos`, `knowledge_activity_log`, ...).

## Result shapes
- add_message / add_loading_message return the Rails message JSON: id, room_id,
  creator_id, creator_type ("User"|"Bot"), system, body, has_attachment, timestamps.
- add_action_message returns `{"status": "ok", "action": "<type>"}` — ephemeral
  broadcast (typing indicator), NOT a stored message. No message id comes back.
- All other project/company create tools return the created record JSON (id, project_id, timestamps).

## Room messaging & actions
- add_message(room_id, user_id|user_name|bot_id|bot_name, body=) — body OR attachment required.
  Attachment = `attachment_path` (local file) or `attachment_url`; response gains
  has_attachment, attachment_filename, attachment_content_type, attachment_url
  `/api/projects/{p}/rooms/{r}/messages/{id}/attachment` (verified 2026-09-08).
- add_loading_message(...) — same args; body auto-prefixed `:spin: `.
- edit_loading_message(message_id, body) / delete_loading_message(message_id) — message_id ONLY.
- add_action_message(room_id, sender..., action_type="typing_start"|"typing_stop") — typing_stop
  pairs with a prior typing_start to clear the indicator.

## Project item tools (all take project_id|project_name)
| tool | required | notable optionals |
|---|---|---|
| add_project_milestone | title | description, icon |
| add_project_todo | title | meta_text, completed, completed_at |
| add_project_bottleneck | title | description, severity (e.g. "high") |
| add_project_all_hands_action_item | title | assignee_name, due_date (ISO 8601), completed |
| add_project_all_hands_decision | title | basis, impact (badge defaults to "Logged in System") |
| add_project_all_hands_takeaway | category, content | — |
| add_project_obsidian_note | title | content, tags ("a,b,c"), html_source_type/path |
| add_project_knowledge_item | title, description | badge |
| add_external_knowledge_asset | title, url | source_type ("external_url"), doc_type |
| add_knowledge_activity_log | actor_name, action_text | target_path/url, actor_color |
| add_knowledge_summary_item | title, description | badge |
| add_tree_based_project_directory_item | name, item_type ("file"\|"directory") | file_path, parent_id, content, attachment_path (local) / attachment_url |

## Company-scoped (NO project param — global company home, not per-project)
- add_company_status_period(name, slug, starts_on, ends_on, current, position) — returns
  period JSON with embedded `company_status_items: []`. Company status item tools
  (changes/decisions/priorities/progress/risks/learnings/dependencies) may take room/user filters instead.
- Attention-item readers are company-home lists: ai_confirm, blockers, decisions_waiting,
  material_changes, mentions, outcomes_review, knowledge_proposals. Return
  `{"count": N, "attention_items": [...]}` — decisions_waiting legitimately returns count 0
  when no approval requests are pending in the project.

## Gotchas
- add_decision_message responds to an EXISTING approval request: approval_request_id is
  REQUIRED and it errors if the id doesn't exist. You cannot create a decision from nothing
  with it; when decisions_waiting is empty there is nothing to answer.
- add_external_knowledge_asset: no project_id needed if project_name given; title+url required.
- Most optional position/active fields default sanely (position 0, active true).
- Directory items: to attach a file to an EXISTING item use
  tree_based_project_directory_data(project_id, item_id, attachment_path) — PATCH multipart;
  Rails keeps the item's current name and resets file_path to that name. For a new item under
  its own filename use add_tree_based_project_directory_item(name=..., item_type="file",
  attachment_path=...). Details → SKILL.md "Directory explorer / tree-based project directory".
