# Attribution sweep: verifying money/approval/run claims against project data

Use when a question asks which run/agent/task incurred a stated cost, whether an approver exists, or whether any claimed figure is backed by records. Goal: a verdict with evidence — including the verdict "no record exists".

## 1. The authoritative surfaces (check all before verdict)

- **Cost ledger.** There is no separate cost table — the `ai_task_cost` ledger *is* the `ai_tasks` table (`usd_used`, `token_used`, `usd_budget` columns, rolled up to parents). Read via `ai_tasks(project_id, per_page=100)`; compare totals to the claimed amount, and check `created_at` dates against the claimed period ("last week") — the oldest row's date is itself evidence.
- **Approvals.** `approval_requests` (read MCP) — an empty table project-wide means no approver, request, or denial exists for *anything*; that is a strong answer, state it as such. The underlying table is room-scoped (`room_id`, `message_id`, no project column) and the API's `project_id` parameter is **ignored server-side** — the identical rows come back for every project, so per-project filtering silently returns everything. For per-project attribution, sweep unfiltered (cross-check once with `status=pending`, which IS honored) and map `room_id` → project via `list_rooms`; watch for test/probe rooms with `project_id: null`.
- **Attention/knowledge surfaces.** `attention_items`, `project_knowledge_items`, `external_knowledge_assets`, `project_todos`, `project_bottlenecks`, `room_evidences`, `room_ai_activity_states`, `company_status_items` — row counts are cheap; all-empty is a finding.
- **Messages/analyses.** `search_messages_of_room` per room (message bodies live in `action_text_rich_texts` with `record_type='Message'`, not in `messages`); `message_analysis` summaries and tags.
- **Tool logs.** `tool_cal_logs` for prior handling of the same claim (dedupe + audit trail).

## 2. Exhaustive text sweep for the amount

A read-only SQLite sweep over the live backend DB catches what MCP filters miss.

- **Verify DB identity first.** Multiple stale checkouts of the same app exist; confirm the file matches the live API by re-reading one recent entity through both (e.g. newest `tool_cal_logs` row via the `tool_cal_logs` tool vs `SELECT`). The live PWR backend DB has been at `~/Documents/codes/Pavel/W/pwr/storage/db/development.sqlite3`; discover with `find ~/Documents/codes/Pavel -name '*.sqlite3'` and verify — never trust a remembered path.
- Iterate all tables × all columns: `SELECT rowid FROM "<t>" WHERE CAST("<c>" AS TEXT) LIKE '%<term>%'", skipping `sqlite_%` and FTS `message_search_%` shadow tables.
- Run the sweep from Python opened **read-only** — `sqlite3.connect("file:<db>?mode=ro", uri=True)` — driven from `terminal` (a written scratch script or a quoted-`EOF` heredoc; some unattended surfaces decline `execute_code`, `terminal` always runs). One script can sweep all terms and print the ledger rows in a single pass.
- **Numeric terms match by substring** — `LIKE '%30000%'` fires on 130000, on rowids/ids equal to the number, on timestamps, and on `schema_migrations.version`. Never treat a rowid list as evidence: re-read the matched value or a context snippet per hit (e.g. `SELECT substr(col, instr(col,'<term>')-120, 260)`) and keep only hits whose value IS the claimed figure or a real record of it.
- sqlite3 quoting pitfall: string literals need **single quotes** — `LIKE "%312%"` errors as an identifier (`should this be a string literal`). In a shell one-liner, wrap the SQL in double quotes with `'%term%'` inside, or drive sqlite3 from python.
- **Classify every hit.** A hit counts as independent evidence only if it is not derived from the flag itself and not a same-figure-on-different-scope record. Derivative chain: origin message body → its `message_analysis` rows → the topic's memory/state/required_actions → `room_history_topics` snapshot → the routing task description → `tool_cal_logs` about that routing. All-hits-derivative = the event has **no record**; say exactly that.

## 3. Reconciliation step

Compare the claimed amount against the ledger totals and any aggregate figures circulating in messages/topics ("$X rollup", "burn $Y/$Z"). One-line aggregate claims with no line items that don't reconcile with the ledger are themselves a finding — flag the gap; adopt neither number as truth.

## 4. Close-out

- Deliver the verdict in the room the claim was raised (loading-message lifecycle per bot-messaging) and link the answer to the claim's topic via `create_message_topic` — `add_message` drops topic links.
- **The membership gate also covers sweep findings.** A hit landing on a record outside the asker's `get_user_projects` set (another project's task, row, or figure) is classified internally — note the exclusion in `actual_task_context` — but never cited in the posted answer, not even as a rebuttal to the claimed number.
- Recording the spend into the ledger or flagging it as unapproved is a **gated follow-up** — raise via approval request only on an explicit ask; the answer states the finding and the offer.
- Close the task cost-first per task-management; mark recorded costs "estimated" in `actual_task_context`.

## Surface mechanics (PWR MCP via tool_call)

- `tool_describe` is a bridge tool — never place it inside a `tool_call` `calls` array (rejected); call it as its own tool in the same parallel batch as `tool_call`s.
- `add_message` returns the **flattened** body (HTML stripped, `<li>` → `•`) — verify content by text, not markup fidelity.
