---
name: rails-mcp-surface-audit
description: "Audit Rails MCP tool scopes without booting the server."
version: 1
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [mcp, rails, verification, documentation]
    related_skills: [w-bridge-mcp, bonfire-mcp-chat]
---

# Rails MCP surface audit

## When to Use

Write or review SOUL/skill/doc files naming MCP tools of a Rails-backed MCP app (PWR, Bonfire) where you must cite verified tool names, arguments, and event_type strings — without starting the server.

Purpose: get the authoritative, per-endpoint tool list + input schemas from the app's registry. from a Rails MCP server (PWR/Bonfire-style registries) without HTTP, so docs/skills cite verified tool names and arguments.

## Steps

1. Find the scope model: grep routes (`config/routes.rb`) for the MCP endpoints and the registry (`app/services/mcp*/registry.rb` or similar) for the scope sets (`action/read/knowledge/task/config/all`).
2. Dump schemas with the runner (no server boot needed):
   ```bash
   bin/rails runner 'require "json"; File.open("/tmp/tools.json","w") { |f| f.write JSON.pretty_generate({action: Mcp::Registry.instance.list_tools(:action), read: Mcp::Registry.instance.list_tools(:read)}) }'
   ```
   Adjust module/scope names per app. The scopes passed to `list_tools` are the same symbols the controllers pass.
3. Dynamic tool families: Rails MCP registries often generate tools from category lists (`AttentionItem::CATEGORIES` → `add_<cat>`/`edit_<cat>`/`<cat>`; `for_category` metaclass pattern). Enumerate families from the model constants, not from static `def name` greps — plain grep missed 123 of 134 tools in a PWR audit (regex parse of `tools/*.rb` found only 11).
4. Event-driven profiles: pair the tool dump with the event recorder (`app/services/output_events/recorder.rb`, model `record_*_event!` methods) to learn exact event_type strings (`<singular_category>_<normalized_action>` pattern in `CompanyStatusItem#action_event_type`) and watch for event-name collisions (`decision_approved` is emitted by both ApprovalRequest and CompanyStatusItem in PWR — disambiguate by `event_data.target_type`).
5. Verify docs: extract backticked identifiers from the markdown, diff against the dumped tool-name set, and whitelist payload-field names to avoid false positives.

## Pitfalls

- Never document tool args from another app's dialect (PWR uses `assigneee_profile` with three e's, `action_item_id`, `parent_task_id` — not `assignee`/`parent_id`).
- Check field immutability in the update tool's schema, not the DB schema: `update_ai_task` writes far fewer fields than `create_ai_task` accepts.
- `list_tools(:all)` returned 0 in PWR because the umbrella scope is populated differently — dump per-scope, don't trust the `all` count.
