# Reviewing a SOUL.md against a standard soul (low-end-model focus)

When: the user hands a SOUL.md to review against ANOTHER soul they name as the standard, asks "what should be improved / added", and often adds "this soul must also work with low-end models (~28B)". Follow-up rounds come as "I updated the soul, re-analyze". This is NOT the spec-coverage audit (`soul-coverage-audit.md`) and NOT fleet section authoring (`soul-section-authoring.md`) — it grades ONE soul as an executable program.

## Workflow
1. Read both files fully. Extract the STANDARD's structural devices first (what makes it executable), then grade the target against those devices. Do not diff content topically.
2. Inventory every tool / field / endpoint / argument claim in the reviewed soul and verify each against the LIVE surface the profile actually loads: per-endpoint `tools/list` on the Bonfire/PWR Rails MCP (see the `bonfire-mcp` skill for the recipe), and the W-bridge surface via `w-bridge-mcp`. Resolve the repo path first — the tree and tool names get renamed between sessions, and a stale local deferred-tool catalog must never be used to fault the soul.
3. Grade against the failure classes below; every finding carries evidence (file:line for the claim, endpoint/schema/source for the verdict).
4. Deliver verdict-first, grouped: (a) verified factual/executability errors, (b) structural gaps vs the standard, (c) low-end-model hardening, (d) what the file already gets right. Review only — offer the fix as an additive patch against the W-ai source tree (no backups in the git-backed tree; patch files per their workflow).
5. Re-review rounds: keep a finding ledger across rounds and report THREE things explicitly — which findings the edit fixed (with evidence), which NEW errors the edit introduced, which carry over unchanged. The common round-2 shape is a surgical fix that adds a fresh unverified factual section: the NEW section is exactly what to verify this time.

## Standard-soul anatomy (the devices that make instructions executable)
- ENTITY DEFINITIONS: every entity the agent creates/updates, field by field, with type/allowed values and 2-3 example values. A bare list of entity names is not buildable into a payload.
- A SCORED RUBRIC: numeric scale with a table (level, meaning, typical content), adjustment rules, ~10 real input→level examples, an explicit tie-breaker ("if torn between two levels, choose the lower unless X"), and hard stop thresholds ("0-1: stop after analysis").
- CANONICAL WORKFLOW: numbered steps, each naming the exact tool, with the dedup rule baked in ("check for an existing record by key first; if present, update; never create a duplicate", "always search before creating").
- DECISION TABLES: situation→action rows, creation criteria ("all must be true"), and per-run caps (at most 1 new entity, at most 3 links).
- WORKED EXAMPLES: real input JSON payload → per-step output JSON per tool, covering the full path, the light path, and the stop path; note which reasoning-only labels are NOT persisted fields.
- EVENT PLAYBOOKS for a soul that receives N named events: one subsection per event — what the event MEANS → exact commands in order (registry reads first, then the write mechanism per axis) → the readback that verifies → when it takes effect. Shared "operating model" prose and declarative "example patterns" bullets (bullets describing an example, not a trace) do not survive in a 28B context; templates do. Prefer playbooks over a generic workflow section when both would exist.
- A compact text-arrow pipeline as a recap.
- MERGE SEMANTICS warning: tools REPLACE fields, so read-merge-write must be spelled out with the merged-value format.
- MCP tools section grouped by purpose, every name live-checked; inline pitfalls for tool behavior (helper defaults that write invalid values, fields the backend silently drops).

## Failure classes (each = a review finding)
- UNIMPLEMENTABLE STEP: the workflow demands an operation the tools do not expose (e.g. "update the task result/status" — `update_ai_task` has no such field; see `bonfire-mcp`). Fix = define the writeback convention on fields that exist.
- NONEXISTENT TOOL NAMES: a fabricated family (e.g. `mcp__memory__find`) when no such MCP server is configured. Verify every name against the profile's config + live `tools/list`.
- WRONG ENDPOINT/SCOPE CLAIM: a soul mapping a domain to the wrong MCP endpoint (project-knowledge mutations are action-scope, NOT on `/knowledge-mcp`), or instructing the agent to "route to the matching endpoint" — endpoint choice is connection config, not per-call behavior. Rewrite as a connection contract + "a tool missing from your list means a missing endpoint connection — stop and record why, never improvise a call".
- READ-ONLY SURFACE MISTAKEN FOR A WRITE PATH: every tool the soul names is `get_*`/`list_*` while the workflow says "apply the mutation" — the model invents `create_*`/`edit_*` calls. Fix: label the read tools read-only explicitly, add a mechanism map of how changes ACTUALLY land (per axis: a `hermes -p <target>` command or a named file edit where no CLI exists — for a Hermes fleet, `SOUL.md`, `mcp_servers.<n>.enabled`, `skills.disabled`), and keep the guard "no write mechanism exists for this mutation -> stop and report, never improvise a call".
- RUBRIC-LESS CATEGORIES: qualitative triage prose ("a real decision", "routine noise") with no numeric scale, no tie-breaker, no stop thresholds.
- INSTRUCTION-SHAPE EXAMPLES: bullet-listed actions with no input payload, no arguments, no output. Low-end models overfit examples over prose — replace with 2-3 worked JSON traces.
- NO DEDUP/IDEMPOTENCY rule on a record-creating router → re-runs duplicate blockers/approvals/messages.
- NO PER-RUN CAPS → small models spam records.
- DANGLING WAIT: "wait for the approval event" inside a single run. State the lifecycle: create the approval request, record a waiting-for-approval outcome in the task, END the run; a follow-up task resumes after checking the request status. Never claim done while waiting, and never decide the approval yourself.
- CROSS-FILE REFERENCE: "follow the same core logic as the X soul" — the other file is never loaded at runtime. Inline the rules it needs or delete the pointer.
- UNDEFINED JARGON ("tool trail", "company home" if never defined): each undefined term is a hallucination slot for a small model — define with an example or map to a real entity/tool.
- SOFT FILLER that maps to a real field: "keep the task visible and trackable" → `added_to_kanban: true` + `assigneee_profile` set; "attach sufficient context" → description contains the verbatim source text + room/project ids + why.
- LOW-END (28B) HARDENING: front-load the one-page decision procedure (small models attend hardest at the top; architecture prose goes after it); call templates with required args AND their value source, not 35-name inventories; short literal sentences, one instruction per line; a closed outcome vocabulary (nothing_to_do | routed | acted | pending_approval | escalate-ask-human); every rule either maps to a tool call/field or gets deleted; shrink the visible tool surface via endpoint selection / per-server tool include filters.

## Delivery preferences (this user)
- Verdict first, then grounded detail; every missing-feature or wrong-name claim verified against the live implementation before it is written down — unverified gap reports get called out.
- Additive-only edits to SOULs, source tree first, unified-diff patch files for review.
