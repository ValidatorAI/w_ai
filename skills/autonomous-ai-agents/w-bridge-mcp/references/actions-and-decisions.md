# Actions, decisions & approval requests (verified live 2026-09-08)

Backend identity: the w-bridge bridge proxies to the SAME Rails app the bonfire
MCP server runs — puma "[bonfire]" on :3000, dir /home/siavash/Documents/codes/Pavel/bonfire.
Space features (actions, attention_items, approval_requests, decisions) live IN that
Rails app. Dev DB: /home/siavash/Documents/codes/Pavel/bonfire/storage/db/development.sqlite3.
Rooms observed: 1 "All Talk", 2 "project-1", 3 "specifications", 4 "releases", 5 unnamed —
room 4 is project 1's "releases" room.

## add_action_message — real-time action
- Params: room_id REQUIRED (or room_name + project); user_id/user_name/bot_id/bot_name
  optional; action_type `typing_start` | `typing_stop` (default typing_start).
- Numeric user_id passes with NO project context (same rule as add_message).
- Result: `{"status":"ok","action":"typing_start"}`. It ONLY emits an ActionCable
  broadcast (POST /api/rooms/:room_id/actions); NO persistent message is stored — do not
  claim a message was saved to the room.
- Worked examples: room 4 as user 2 (typing_start then typing_stop), then typing_start
  as user 3 — all returned status ok.

## add_decision_message — approval_request_id is MANDATORY in the current stack
Verified empirically 2026-09-08: calling it WITHOUT approval_request_id is rejected by
the MCP schema layer before the server is reached:

    "error": "tool_call to 'mcp__w_bridge__add_decision_message' is missing required
    argument(s): approval_request_id. The tool was NOT invoked."

Enforced at THREE layers:
1. MCP schema — mcp/tools.py registers approval_request_id in the tool's "required" list.
2. Bridge Python — `async def add_decision_message(approval_request_id, ...)`: positional
   arg with no default (mcp/tools.py ~line 2024).
3. Rails Api::DecisionsController#create (bonfire/app/controllers/api/decisions_controller.rb
   lines 16-17): `room.approval_requests.find_by(id: params[:approval_request_id])` →
   404 "Approval request not found" when nil or not belonging to that room.

Semantics: a decision is a RESPONSE to a pre-existing, room-scoped ApprovalRequest record.
It is NOT a standalone "decision message" creator. The user may believe the id is optional
("used for later approval") — that design is NOT implemented in the running backend.
Respond by proving it with a bare call (instant, conclusive) and explaining the three
layers; do not argue from docs and do not invent an id.

- Decision actions: `approve` | `confirm` | `deny` | `cancel` (DECISION_ACTIONS); `note` optional.
- Route: bridge client POSTs /api/projects/{project_id}/rooms/{room_id}/decisions
  (space/api/decisions.py create_decision). Flat /api/rooms/:room_id/decisions also
  exists — both map to Api::DecisionsController#create (routes.rb lines 149 and 160).
- Side effects on approve/confirm: when request_type == "decision" (or payload["decision"]
  present) it auto-creates a ProjectAdr (identifier ADR-YYYYmmddHHMMSS, status "accepted",
  title from payload decision/title/summary/text), resolves linked AttentionItems
  (source_type "ApprovalRequest" on the request or "Message" on its message), and records
  an OutputEvents event (decision_approved / approval_request_approved|confirmed|denied|canceled).
- HTML twin: ApprovalRequestsController#approve/confirm/deny/cancel (Turbo Stream card
  replace) — browser UI only.

## ApprovalRequest domain model (bonfire Rails)
- Table approval_requests: id, room_id, message_id, agent_id, request_type, payload
  (validated JSON object), status enum pending(0)/approved(1)/denied(2)/canceled(3)
  default pending, requested_at (auto-set before_create), resolved_at, resolved_by_id
  (→ users), has_many approval_request_actions (actor polymorphic, action, note).
- A request hangs off a MESSAGE (Message has_one :approval_request, dependent: :destroy)
  and renders as an in-room card (views/approval_requests/card, referenced from
  views/messages/_presentation.html.erb). message_id can be null, but seeds always pair them.
- Creation API EXISTS now (added after this note was first written): bridge
  `add_approval_request` POSTs /rooms/:room_id/approval_requests and returns the
  created row (verified live 2026-09-08: id 1, room 4, request_type "decision",
  status pending, payload JSON round-trips verbatim incl. arbitrary keys like
  requested_by_user_id). Params: request_type, status, message_id, agent_id,
  requested_at, resolved_at, resolved_by_id, payload. NO user/creator param — a
  request has no requester-user column; put "on behalf of user X" in payload.

## Trap: decisions_waiting attention items ≠ room approval requests
- decisions_waiting/blockers/outcomes_review/... are company-home AttentionItem rows
  (category decisions_waiting). The sample item (id 1) returned room_id: null,
  source_id: null — a bare dashboard card, NOT an approval request. Filtering the list
  tool by room_id does NOT surface room-scoped approval requests; do not harvest an
  approval_request_id from there.
- IF an item IS linked (source_type "ApprovalRequest"), its source_id IS the
  approval_request_id to pass to add_decision_message.

## Inspection recipe (when a decision cannot be sent)
    DB=/home/siavash/Documents/codes/Pavel/bonfire/storage/db/development.sqlite3
    sqlite3 "$DB" "SELECT id,room_id,message_id,request_type,status FROM approval_requests WHERE room_id=4;"
    sqlite3 "$DB" "SELECT count(*) FROM approval_requests;"          # whole-DB sanity
Live state 2026-09-08: was ZERO approval_requests until add_approval_request created
id 1 in room 4 — a decision demo can now target approval_request_id 1.
