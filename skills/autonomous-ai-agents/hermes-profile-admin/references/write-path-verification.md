# Follow-on review: "the feature EXISTS in Bonfire / the W-bridge MCP — re-analyse"

Companion to `soul-coverage-audit.md` §11 (the read-only E2E/use-case capability
review). That section's Step 3 said: read the MCP tool-reference headings, and if
the spec needs an object with no section there, the object does not exist. This
file records why that inference is unsound and what to do instead.

Worked 2026-09-30, one turn after a §11 review. The user pushed back:

> "there are gaps in soul.md but feature exists in the bonfire & w-bridge mcp
> (you can see features in /home/siavash/Documents/codes/Pavel/W/bonfire/docs/page_sections_and_entities.md)
> so re analyze the gaps in case soul.md of profile are aligned for using bonfire
> features due to required usecases"

The §11 pass had declared two of six E2E flows "NOT SUPPORTED — no object to write
to" from the registry headings alone. Verified against the implementation, that
verdict was too strong. **Treat any "platform object missing" verdict from §11 as
provisional until the write path has been checked here.**

## Protocol: check the WRITE PATH in three layers

In this order; report the layer where it breaks.

1. **Rails schema**
   `sqlite3 /home/siavash/Documents/codes/Pavel/W/bonfire/storage/db/development.sqlite3 ".tables"`
   then `".schema <table>"`. To list columns, cut the CREATE statement at the first
   `CONSTRAINT` and regex the `"name" type` pairs (the schema prints on one long
   line, so a `grep '^"'` finds nothing — parse instead).
2. **Bridge payload** — `space/api/<entity>.py`. The `create_*` / `update_*`
   argument lists are exactly the transmitted keys (they go through
   `prune({...})`). A DB column the bridge never sends is unreachable from this
   server no matter what the table holds.
3. **Agent reach** — `TOOL_DEFINITIONS` in `mcp/tools.py` (112 entries on
   2026-09-30). Each tool's `properties` block is the contract an agent actually
   gets.

## Corollaries (the part that changed the verdict)

- **A DB column is not a writable field.** `company_status_items.evidence`,
  `.impact`, `.target_date`, `.severity`, `.actions`, `.percent`,
  `.detail_category` all exist in the schema; layers 2 and 3 expose none of them,
  and `source_type` is filter-only. So "progress supported by evidence", impact
  ordering and "owner + target date" ARE features of the data model but are NOT
  producible by a profile. That is the finding — not grounds to call the flow
  unsupported.
- **A design doc's proposed table is not an entity.** `attention_item_events`
  (described in `DEMO_FUNCTIONALITIES_DB_IMPACT.md`) is absent from `.tables`. The
  real audit carriers are `approval_request_actions` and `output_events`.
- **Read the sibling feature doc, not only the tool reference.**
  `bonfire/docs/page_sections_and_entities.md` is the page→entity→tool map (the doc
  the user pointed at). The demo-flow features and their DB impact live in
  `bonfire/docs/DEMO_FUNCTIONALITIES_DB_IMPACT.md` (attention lifecycle + per-item
  history intent, the approval workflow including an explicit "Deployment action
  approve/deny" thread prompt, knowledge versioning). Read both before ruling.
- **The honest verdict is usually "partial, with the layer named."**
- **"Exists but referenced by NO profile SOUL" is its own finding class** — name it
  separately from "missing".

## Verified carriers (2026-09-30) — quote these instead of "no object"

- Human approval + audit: `approval_requests` (request_type, payload json
  `{version, scope, rollback…}`, status pending/approved/denied/canceled,
  agent_id, requested_at / resolved_at / resolved_by_id, message_id, room_id)
  plus `approval_request_actions` (action, actor_type, actor_id, note). Cite the
  actions table whenever "who approved what, with what note" is asked.
- Decision + supersession: `project_adrs` (identifier, decision_date, status,
  file_path, active).
- Traceability feed: `project_knowledge_activities` (actor_name, action_text,
  target_path, target_url).
- Provenance / deadlines: `attention_items.due_at`, `.overdue`, `.action_label`,
  `.source_type` + `.source_id`, `.target_type` + `.target_id` — all writable.
  No history table, so per-item audit is only resolved_at + resolved_by_id.
- Existing but referenced by NO profile SOUL (unused-capability finding):
  `file_reservations` (patterns/exclusive/expires_at/reason — the safe-parallel-
  implementation feature), `output_events` (event_type/event_data/group_id/synced
  — the event/audit delivery path), `ai_profile_tools` / `ai_profile_mcps` /
  `ai_profile_skills` (the structured per-profile allowed-tools boundary that an
  "allowed tools + boundaries" assignment-card field should cite).

## Still genuinely absent / thin (the residual blockers)

- No entity for: experiment/hypothesis, metric or measured outcome, qualified
  sample/participant, release/deployment, incident/rollback, code-review state.
- `project_todos` writes title/meta_text/completed/completed_at — no owner, due
  date or evidence. `project_all_hands_action_items` is the only task record with
  `assignee_name` + `due_date`.
- `project_knowledge_items` writes only title/description/badge/active — no
  version, source, confidence or supersedes field. Supersession must ride on ADRs
  (identifier + status) or the vault layer.
- `ai_profiles` has no structured human-approval-required / permission-scope
  column even though the demo profile modal displays one.
- Note-tool naming: `grep -c neurostack mcp/tools.py` → 0. The live family is
  `project_obsidian_note` (+ add_/edit_/delete_); the neurostack MCP is a separate
  vault server (`vault_*` tools); the canonical knowledge subdomain is
  `obsidian_notes`.

## Re-run the attribution matrix at this stage too

Compact per-profile section×tool scan: regex `###\s+(SECTION-[A-Z]{2}-\d{2})`
over each SOUL, take the backticked names inside each block, diff against the
per-page expected tool list from the feature doc. This round it produced two
findings on top of §9's: PO-01 missing `approval_requests` + `add_message` in 8
files (the doc's "Resources & channels" group) and PK-01 missing the paired note
tools in 6 files. Same edit shape as §9 — additive, section-scoped, source tree
first, mirrors second.

## Reply shape for this follow-on

1. Correct your own earlier verdict first, in one line ("v1 said no object exists;
   verified now, the carriers exist — the gap is the rule, except at these two
   layers").
2. Capability table: writable / column-only / absent.
3. The profile × section matrix.
4. Per-use-case alignment gaps.
5. Residual real blockers (now a short write-path extension list).
6. The same next-step offer (per-profile unified-diff patches / draft the missing
   reviewer SOUL / verify loaded-profile tool wiring).

Write the revision to a NEW file (v2) rather than overwriting v1 — this user reads
the delta between rounds.

## Read model vs authority: "should the data live in memory / OV / NeuroStack?"

Asked 2026-09-30, later the same session: *"status items already should be stored
in the memory or ov memory or neurostack so profiles do not need to access status
or other data from w-bridge or bonfire … by reviewing stored data in the memory
or ov or neurostack they should have enough required information, correct?"*

Do not answer yes or no. The correct answer is **yes for reading, no for
authority** — and it must be verified, not asserted.

What already supports the idea:

- Every Bonfire business event carries a resolved `knowledge_path`
  (`app/services/output_events/knowledge_path_resolver.rb`), whose segments are
  the canonical ones (`items`, `external-assets`, `directory-items`,
  `obsidian-notes`, `activities`, `adrs`). The design intent is on the user's
  side, and it is also further evidence for the note-tool naming finding:
  `obsidian-notes`, never `neurostack-notes`.
- Transport exists end to end: `output_events` (synced flag) → `DeliverJob` →
  HTTP POST to `OUTPUT_EVENTS_URL` → W-bridge `space_events` (dedupe_key) →
  queues → `bus/cron.py` tick.
- BUT `bus/executors.py::run_space_event` forwards an event to **Hermes chat
  completions** — the pipeline exists to WAKE agents, not to maintain a readable
  state mirror. Say that plainly: the substrate is there, the mirror writer is not.

Verify coverage before agreeing: enumerate the recorded types with
`grep -rhoE 'event_type: *"[a-z_]+"' bonfire/app | sort -u`. On 2026-09-30 they
covered ai_config, projects, rooms, users, messages, skills, mcps,
attention_items and approval_requests only — **no** events for
company_status_items, project_todos, project_bottlenecks, project_milestones,
knowledge items/assets/notes/activities/directory, or all-hands. A mirror built
on today's stream would be missing exactly the state the E2E demos read.

The split to state, with its reasons:

1. **Authority = writes, gate, audit.** Approvals (`approval_requests` +
   `approval_request_actions`), attention resolution (`resolved_by`/`resolved_at`),
   status transitions. A note cannot enforce no-self-approval, cannot reject an
   invalid transition, and is not the audit record — and humans approve in the
   Bonfire UI, so the approval write must land in the API.
2. **Mirror = context and answering.** The vault under
   `company/[id]/projects/[id]/…` (the knowledge_path shape) plus OV memories for
   profile-scoped recall. Reads get faster, cheaper and path-scoped.
3. **Freshness is mandatory, not optional.** Mirror records need `source_type` /
   `source_id`, `source_updated_at` and `last_synced_at`, or profiles will present
   stale state as current — the single failure mode the demo contract ("source,
   last-refresh time, confidence") exists to prevent. Nothing sets those markers
   today.
4. **Scoping conflict.** OV memory is per-room/per-profile and the SOUL rules
   forbid mixing rooms, but a portfolio question is company-wide — so the mirror
   must be path-organised per project (vault), not per-room memory.

Two more things to say in the same reply: aggregates and change detection (open /
overdue counts, "what changed since the last review") are queries over structured
fields, so keep numbers structured instead of distilling them to prose; and a
mirror does NOT remove the need for the absent write-side entities
(§"Still genuinely absent" above) — it only softens the read side.

## Dictated tool rules: verify the tool BEFORE shipping the wording

The user may name a tool in the instruction itself ("insist that use
AddActionMessage when agent has any question from the user or create other
required entities which required approvement"). A tool name in the request is NOT
evidence the tool can do the job — check its schema first, in the same three
layers. This round: `add_action_message` (alias `AddActionMessage`) accepts only
`action_type: typing_start|typing_stop`, takes **no body**, and stores **no
persistent message**; `space/api/actions.py::send_action` is the whole contract
and the `w-bridge-mcp` skill already documents it as a typing broadcast. The
working persistent path is `add_approve_request_with_message` (message +
approval request) resolved by the human via `add_decision_message`.

Behaviour when the gap is real, and both halves are required: implement the rule
as dictated (it is their platform, and the tool may be extended), AND report the
semantic gap in the reply with the exact evidence and an offer to scope the
extension. Do not silently substitute a different tool name, and do not silently
ship wording you know is inert.
