---
name: bot-messaging
description: Use when posting to PWR rooms, threads, or private chats as a bot.
version: 0.1.0
author: siavash (drafted by Hermes)
license: MIT
metadata:
  hermes:
    tags: [pwr, bots, rooms, messaging]
    related_skills: [pwr-entities, bot-approvals]
---

# Bot room & private messaging

Purpose: the discipline of talking **as a bot** in PWR — routing, the loading-message lifecycle, formatting, and how your messages get consumed downstream. Procedures here are binding, not stylistic.

Source of quality: the same lifecycle coder/project-manager souls run in production; verified tool names: `add_loading_message`, `edit_loading_message`, `delete_loading_message`, `add_message`, `add_action_message`, `search_messages_of_room` (action/read surfaces per workspace soul's rooms row).

## Routing (where a reply belongs)

- A request from a room or thread gets its answer in that same room/thread, sent with `user_name: "<your-bot-profile>"`. Never reply only in logs.
- A private chat gets its answer in the private chat. Never paste private-chat content into a room; never carry another room's context into an answer (the room is the memory boundary — see pwr-entities).
- Questions the user must see, and status of in-flight work tied to a task/event, are posted with `add_message` in the same room you received the input — prose anywhere else gets missed. `add_action_message` carries only an `action_type` indicator (typing-style signals) and has **no body parameter** — never route content through it.
- Post permission is per-profile AND per-room: one profile's `Forbidden` on `add_message` in a room does not predict another's. Sweep `tool_cal_logs` for that room to see which creator shapes landed before guessing — observed: plain posts as project_manager rejected across every creator shape in cobalt-main while `user_name: "w_ai"` (exact, lowercase) landed loading and answer messages in the same room. A rejected plain post is a permission finding to record in the close-out, not a gate to route around: never raise an approval request just to smuggle content into a room your profile cannot post to.

### Posting walls are per-profile

A `Forbidden` reported for ANOTHER bot profile — quoted in a task description or found in a cal log from its failed attempts — does not bind you. Before routing your answer through a workaround channel (approval-raise fold, surfacing trick), test `add_message` once with your own creator token: walls are enforced per creator, and inherited constraints cost you the natural delivery path for nothing. Resolve an uncertain bot token via `get_users(user_id)`: the User `name` (profile slug, hyphens included) is what `user_name` fuzzy-matches — not the display name.

## Loading-message lifecycle (required for any multi-step request)

1. **Start:** `add_loading_message` for the room; keep the returned loading message id. The server re-prefixes `:spin: ` on create AND edit responses even when you send plain text — never include `:spin:` yourself or the prefix renders twice.
2. **Every meaningful step:** `edit_loading_message` on that same loading message — what is being done now, what changed, what is next. Do NOT batch hidden operations without intermediate updates.
3. **Finish:** `delete_loading_message`, then `add_message` with the final result to the same room.
4. **Blocked:** immediately post a room update with the blocker details and the **exact** input/approval needed to unblock. Never leave a loading message spinning on a dead plan.
5. **Concurrent tasks:** other assigned tasks may be running in the same room with their own loading messages. Track the loading id YOU created this session and never edit or delete a `:spin:` message you did not create — its owning task's session closes it.

If the request came as an assigned AiTask with a `room_id`, the lifecycle runs in that room. No room at all (private chat or contextless task): skip loading messages there, but keep the same step-by-step visibility in the chat/task thread.

## Formatting (required)

- No Markdown. HTML tags only: `<ul>`, `<li>`, `<a>`, `<b>`.
- Always wrap code in `<pre>`.
- Verdict first, detail behind it. One subject per message; spell entity ids inline ("task 91", "milestone 12") so message analysis and topic linking can do their job — your messages are scored into `message_analysis` and attached to topics after the fact.
- Write bodies to survive flattening: the server stores `add_message` bodies with HTML stripped (`<li>` → `•`, tags gone). Send HTML per spec, but verify delivered content by text, not markup fidelity — markup-sensitive emphasis won't render as sent. The flattener glues adjacent blocks and newline counts immediately BEFORE a `<ul>` are unreliable: both a single `\n` and a BLANK line `\n\n` before the list still delivered "...intro:• first bullet" with no separator, while `\n\n` AFTER the last `</li>` and between paragraphs survives (the server may even emit it doubled). So: use `\n\n` for prose that follows the list — that is dependable; for the intro line before a list, assume it may glue regardless of how many newlines you send. Keep intros short, read the delivered body back via `search_messages_of_room`, and if the glue hurts legibility restructure (fold the intro into the verdict line above the blank-paragraph gap, or split into two messages) instead of stacking more newlines.

## What not to do

- Do not send the same content twice (dedupe via `tool_cal_logs` footprint + `search_messages_of_room` when unsure).
- `search_messages_of_room` treats `from_message_id` as an **inclusive upper bound**: the page starts AT the anchor message itself (when that id exists in the room) and walks older, descending. Anchoring just below a target message silently returns only history — to reach the newest traffic, pass a `from_message_id` above the highest known id, or omit the filter; anchoring ON a target id is how you fetch that message plus its neighbors.
- The `message_analysis_content_summary` / `message_analysis_tags` filters match the ANALYSIS text only — never message bodies or authors. Searching "flux" returns nothing for a message flux actually authored when its summary omits his name (observed: msg 557). Attribution and author sweeps need raw `search_messages_of_room` pages filtered on `creator_id` in code, not the analysis filter.
- A `topic_id` filter on `search_messages_of_room` matches only topic-LINKED messages — decision lines and older records are often un-analyzed with empty `topics`, so a topic-filtered sweep can return just the question itself. Re-sweep raw room history over the relevant time/id window before concluding "nothing on record".
- Do not use `add_decision_message` yourself — it carries the human's decision, not yours (see bot-approvals).
- `add_message` silently creates messages with NO topic link. After posting an answer that belongs on a topic spine, call `create_message_topic(message_id, topic_id)` and verify by reading the `topics` array back via `search_messages_of_room` — a topic id cited in the body text is not a link.
- Do not chat socially; you are practical, precise, outcome-first.
- Do not mention ids without naming which kind ("37" is meaningless; "task 37" / "topic 37" is traceable).

## Worked example (room mention → result)

```
@coder fix the export
→ add_loading_message(room: Engineering)  [keep id 512]
→ edit_loading_message(512, "Reproduced: export crashes on empty date column")
→ edit_loading_message(512, "Patch written, running tests")
→ delete_loading_message(512)
→ add_message(room Engineering, user_name coder,
     "<b>Fixed.</b> Empty date column crashed export.py; guarded + test added.
      <pre>def month_export(d): ...</pre> Next: awaiting your run on staging.")
→ create_tool_cal_log(...) for each state-changing action
```
