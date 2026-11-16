# Auditing SOUL Coverage Against a Page / Functionality Spec

Answers the class of question: *"here is a doc that lists pages, entities and
MCP tools — do the profiles' SOUL.md files cover these functionalities, both in
mentioning the MCP tools and in defining WHEN to use them?"* Also: "which
profile covers page X", "is tool Y defined anywhere".

Reference implementation: `scripts/soul-coverage-audit.py`.
Worked example below: `W/bonfire/docs/page_sections_and_entities.md` vs the
17-SOUL fleet (16 profiles + `default`), 2026-09-30.

## 1. What counts as coverage

A tool is **covered** only when its name appears inside a `### SECTION-xx` block.
Those blocks are the when-to-use contract — the section schema is:

```
### SECTION-XX-01: <Title>
#### Intent            <- purpose
#### Trigger           <- THE when-to-use definition
#### Expected Behavior <- ordered steps
#### Key Entities      <- entity axis
#### Boundaries        <- what NOT to do
#### Example Task Framing
#### W-bridge MCP Tools to Use   <- the tool list for this page
```

**A bare mention elsewhere does NOT count.** These look like coverage and are
not: `## Approval Request Tool Policy`, `## Workspace Bot Identity Policy`
(they name `add_message`, `add_approve_request_with_message`,
`add_decision_message`), role paragraphs ("Primary tools: `project_todos*`, …"),
and "send the final task result using add_message" lines. Always separate
*sections:* (has a Trigger) from *files:* (anywhere in the text) — the gap
between those two columns is where the real findings are.

## 2. Method

```python
import re
# page headings are level 2; sub-blocks are level 3
pages = re.findall(r'^##\s+(?:\d+\.\s*)?(.+)$', spec, re.M)      # skip ones matching /quick|map/i
tools = re.findall(r'`([a-z0-9_]+)`', page_body)                  # spec backticks tool names only
# SOUL sections (note \n prefix and the ### level)
parts = re.split(r'\n###\s*(SECTION-[A-Z]+-\d+)', soul_txt)
bodies = dict(zip(parts[1::2], parts[2::2]))
hit = re.search(r'(?<![a-z0-9_])' + re.escape(name) + r'(?![a-z0-9_])', body)
```

Then report three columns per tool and flag the difference:

- `strict` — present in the section whose code maps to the spec page it belongs to
- `any` — present in any `SECTION-xx` block (page placement ignored)
- `file` — present anywhere in the text (prose/policy)

Entities are a second axis: the spec's `- Entities used:` bullets and the SOULs'
`#### Key Entities` lists. Audit them separately — a page can have full tool
coverage and zero entity coverage, or vice versa.

## 3. Page ↔ section-code map

Section codes are `SECTION-<CODE>-<nn>`; codes are stable per page:

| Code | Page |
|---|---|
| CH | Company Home |
| CS | Company Status |
| PO | Project Overview |
| PS | Project Status |
| PA | Project All-Hands |
| PK | Project Knowledge |

Sections are assigned per-profile by ROLE, not globally — `company` carries
CH+CS, `company_project` carries all five execution pages, `coder` carries
PS+PK+PA, and so on. So "the doc says tool T is on page P" and "the SOUL defines
T under page Q" are both true facts to report; do not silently treat one as the
answer.

## 4. Three failure classes — name the class, they need different fixes

1. **Absent** — in no SOUL and not in the upstream shared spec either
   (`hermes/shared/profile-knowledge-sections.md`). This is a *generation gap*:
   the section schema never produced a block for it, so no amount of re-syncing
   will help. Fix = author a new `SECTION-xx` in the shared spec / source tree.
2. **Relocated** — present, but under a different page's section than the doc
   assigns. Report as "relocated, not missing" with both page names; fixing it
   means moving the tool bullet, which is an editorial decision for the user.
3. **Bare mention** — appears only in prose/policy blocks, never in a section
   with a Trigger. Functionally a slot where the agent has no when-to-use.

## 5. Verify tool names exist before blaming the SOULs

Grep the MCP implementation (`W-bridge/mcp/tools.py`) for every name the spec
lists. If all names exist, the gaps are genuinely SOUL-side and the spec is
accurate. Two results from the worked audit:

- All 55 unique spec tool names exist in `mcp/tools.py` → spec reliable.
- `project_neurostack_note` (which the NEWER W-ai source SOULs use) has **0**
  occurrences there, while `project_obsidian_note` has 24. So a source tree can
  be *newer and wrong at the same time* — never treat "source is newer" as proof
  a tool name is real; grep the server first.

## 6. Source-tree drift is a separate finding, report it separately

The W-ai sources were 15–33 lines ahead of the loaded mirrors, and the entire
delta was the knowledge stack renamed Obsidian → NeuroStack (tool
`project_neurostack_note`, prose "neurostack MCP", the four `knowledge/`
subdomains, the `## neurostack MCP integration` block, plus NeuroStack
retrieval/graph instructions). The loaded mirrors still match the spec doc.
So a coverage answer can be correct for the *loaded* fleet and wrong for the
*source of truth* — state which tree you audited, and check three-way
(doc / loaded / source) when the trees differ.

## 7. Worked result (2026-09-30) — shape to imitate

- 6 pages, 19 entities, 55 unique tools; 53 have a when-to-use somewhere.
- Hard gap: `list_ai_profiles`, `get_ai_profile` (doc page 3 "Attached AI
  teammates") — zero hits in all 17 SOULs AND zero in the upstream shared spec.
- Relocated: `add_project_milestone` / `edit_project_milestone` (doc: Project
  Overview; SOULs: SECTION-PS-01), `add_project_knowledge_item` /
  `edit_project_knowledge_item` (doc: Project Status; SOULs: SECTION-PK-01).
- Bare mention only: `add_message`, `approval_requests` on page 3's "Resources &
  channels" (they live in CS-01 / PA-01 / PK-01 and in the policy blocks).
- Pages complete where carried: CH 7/7, CS 9/9, PA 9/9, PK 15/15. Page 3 is the
  weak one.
- Profiles with no page sections at all: `default`, `config`,
  `mechanical-modeler`, `testprofile` → none of this functionality is defined.

## 8. Report shape for this user

Verdict first in one line ("mostly yes, but not fully — 53 of 55"), then the
hard gap, then per-page status, then the drift warning, then an offer to fix
(each fix named concretely: author the missing section, move the bullets,
decide obsidian-vs-neurostack before resyncing). State the provenance of every
number ("verified against … + the live mcp/tools.py") — this user checks claims
about their own install and dislikes invented detail. No markdown; plain text.

## 9. Remediation: applying the fix across BOTH trees

Script: `scripts/soul-section-edit.py`. Run it dry-run first, read the per-file
plan, then `--apply`.

- **Source tree first, then the mirrors, in ONE pass.** Editing only one tree
  re-diverges on the next `soul-tree-resync.py` — the sync is a mirror, not a
  merge, so the un-edited side loses.
- **Additive by default.** Section 4's "relocated" class does NOT require moving
  the bullet: a tool may legitimately be listed in two sections. Prefer ADDITION
  (the doc's page gains the tool, the incumbent section keeps its context) and
  say which choice you made — moving is an editorial decision the user owns.
- **Pick the edit shape to fit the semantics** rather than always appending:
  when the section already carries a matching bullet, extend that line
  (the line "- Context support for status decisions: project_knowledge_items,
  project_decision_records." → insert the two write tools into that list);
  only add a fresh bullet when no natural host line exists
  ("- Milestone lifecycle writes for overview-level planning: …").
- **Assert the anchor occurs exactly ONCE per file** (`new.count(anchor) == 1`,
  abort otherwise). The anchor line is identical across the fleet, so a
  miscount means a duplicated block, not a lucky match.
- **Verify three ways**, in this order: (a) re-scan `require` per section after
  the write; (b) diff every file against its backup and check the **line math**
  — a file hit by both rules is `+2/-1` (one appended bullet, one replaced
  line), bullet-only is `+1/-0`, replace-only is `+1/-1`; anything else is a
  stray edit; (c) re-run the coverage audit and quote before/after (that round:
  "spec tools without a page-section definition: 7 → 2").
- **Backups must be per-file unique paths** (`<backup>/src/...`,
  `<backup>/loaded/...` mirroring the tree) — never one flat directory, because
  every file is named `SOUL.md` (see the collision pitfall in SKILL.md). Keep
  the earlier backups; do not overwrite.
- **Idempotence is the acceptance test**: a second run must print
  `skip … (already reconciled)` for every file.
- **Surface the residual and editorial items instead of deciding them**: an
  absent section (authoring one is a *generation* change, not a reconciliation),
  whether a routing-only profile (`delegator`) should carry write tools at all,
  and files that have no such section so nothing could be attributed.

Result 2026-09-30: 11 files per tree, `+15/-7` lines each, no requirement
failures, `add_message`/`approval_requests` still bare-mention on page 3, and
`list_ai_profiles`/`get_ai_profile` still absent everywhere.

## 10. Second axis: auditing inter-profile interactivity (kanban handoff)

Different question, same fleet, same technique:
*"is there anything in the SOULs telling profiles (other than delegator) that
when something important is required they can create a kanban board and assign
it to another profile — e.g. a decision handed to the coder should be raised as
a card for whoever owns the consequence?"*

Classify every file on four axes and report a **matrix**, not prose:

1. **Board creation** — does the file say "if no board exists, create one"?
   Only `default` + `mechanical-modeler` (the generic "one board per room" rule)
   and `delegator` ("verify company kanban board existence first") do; the other
   14 assume a board exists, and four literally say "Use one kanban board which
   is specially created for room" without ever naming who creates it.
2. **Card flow direction** — inbound ("use kanban-assigned cards as the source of
   truth") vs outbound (create/reassign). `knowledge` is inbound-only, which is
   the tell.
3. **Outbound destinations** — enumerate the profile names each file may hand
   off TO. This is the axis that exposes the gap: `coder`'s only outbound route
   is coder→`knowledge` *and only* "if implementation changes require new shared
   knowledge structure" (line 64), so a decision that belongs to
   `project_manager`/`business_analyst` has no defined route at all.
4. **Trigger wording** — is there a generic clause ("if important / required /
   when needed") or only enumerated cases? Grep for the phrase, don't infer:
   every "required" hit is a section heading (`Required Hierarchical Memory`,
   `Message delivery lifecycle (required)`) or the escalation boilerplate. No
   SOUL carries a generic "if required, raise a card" rule.

Add two cross-cutting checks:

- **Channel enforcement** — which files forbid the non-kanban path? Only
  `delegator` ("do not use hermes api server … just use kanban mechanism"),
  `cron_profile` and `not_known_task` ("do not directly invoke target profiles
  outside kanban card reassignment flow"). Everywhere else nothing stops an
  agent from handling cross-profile work inline with no card.
- **Competing mechanism** — the PA-01 boilerplate "Escalate unresolved actions
  into delivery tracking when needed: `add_project_todo`, `edit_project_todo`"
  (7 files) escalates into a W-bridge *entity*, while the delegation sections
  escalate via a *kanban card*. Two mechanisms for one intent; name the
  inconsistency rather than picking one silently.

Report shape: verdict ("No — the general rule does not exist"), the axis matrix,
then trace the user's own example through the real file, then the proposed
uniform section with the open scope questions (which files to include/exclude).

## 11. Third axis: auditing against a USE-CASE / E2E spec (read-only capability review)

Trigger phrasing: *"review this file … check if the current profiles support
these functionalities (soul.md) and if not what should be changed in the soul.md
for each profile (do not change the profile just mention what is required)"*.
Worked 2026-09-30: `W-ai/W-Management-E2E-Demos-v0.1.0.md` (6 management /
venture-building E2E flows, a "Demo principles" section, roles named CEO /
Researcher / Builder / Reviewer / Knowledge Curator) vs the 15-file W-ai source
tree.

This is NOT the §1 page audit. The spec's units are **behaviours and states**
(plan → draft → waiting-for-approval → approved → executed → verified outcome;
"a merge must never be presented as a deployment"; source + confidence +
last-refresh on every claim; "a negative result is a valid result"), so tool-name
matching finds almost nothing. Audit the capability vocabulary instead.

**Read-only mode.** When the user says "do not change…, just mention what is
required", edit NEITHER tree — no `soul-section-edit.py`, no resync. Still state
the mirror drift (below) as a blocker for any later apply, and write the review
report to a file OUTSIDE the W-ai repo (no new files in a git tree the user asked
to be left as the diff baseline), then give the summary in the terminal.

**Step 1 — enumerate the fleet with a case-INSENSITIVE find.** The fleet is not
what `find . -name "SOUL.md"` returns:

```bash
find /path/to/hermes/profiles -iname "soul.md" | sort        # 15 files
```

11 are `SOUL.md`; 4 are uppercase `SOUL.MD` (`main/action`,
`bots/business analyst`, `bots/market research`, `bots/ask from w`). A
case-sensitive sweep silently audits 11 of 15 and every count in the report comes
out wrong. Profile id = leaf dir name, lowercased, spaces → underscores, so the
same tree also holds `bots/project manager` → `project_manager`.

**Step 2 — skeleton first, then keyword evidence.** Per file,
`grep -n "^#\+ "` gives the heading outline in one screen and shows at a glance
which `SECTION-xx` blocks a profile carries. Then sweep every SOUL for the spec's
capability words — this is what turns an impression into a citable line number:

```bash
for k in staging rollback "pull request" sandbox production hypothes metric \
         experiment supersed "self-approv" "least privilege" "audit trail" \
         "confidence level" evidence approved executed verified; do ...
```

Run the sweep through `search_files` (tool), not a hand-written
`grep -ril -- "$k" --include="SOUL.md" .` — a `--` before `--include=…` makes grep
treat the flag as a PATH: it prints `grep: --include=… No such file or directory`
and *still* emits partial matches from every other file, which reads like a
result. Note the real hits that exist here: coder has deploy/port-83 only,
`market research` has `hypothes*` + `confidence`, `knowledge` has one `Stage`
(false positive on `staging`), and life-cycle words (approved / executed /
verified / rollback / staging / sandbox / metric / experiment) appear in **no**
SOUL.

**Step 3 — enumerate the platform object surface before blaming the SOULs.**
Read the MCP tool reference's own headings
(`docs/W-bridge/docs/mcp/TOOLS_REFERENCE.md` → `## Canonical Tools` →
`### Core | Company Home | Company Status | Project Milestones | Bottlenecks |
Todos | Knowledge Items | All Hands | Decision Records | External Knowledge
Assets | Knowledge Activity Log | Tree Directory | Knowledge Summary Items |
Obsidian Notes | Room Interaction | Approval Requests | AI Config`). If a spec
needs an object that has no section there, the SOUL is not the problem — the
object does not exist, and no text edit fixes it.

**Four gap classes (distinct from §4's three — name the class):**

1. **SOUL rule missing** — the tool exists, the behaviour is undefined in every
   file. Fix = author a shared section (see §3 / `soul-section-authoring.md`).
2. **Platform object missing** — spec needs hypothesis, experiment, metric /
   measured outcome, evidence artifact, release / deployment record, incident /
   rollback, review state, qualified-sample record. Not in the registry, so
   demos needing those fields can only be forced into knowledge items / todos /
   status categories which cannot carry them. This is a data-model decision for
   the user, NOT a SOUL edit — say so in the verdict.
3. **Owner missing** — a spec role has no profile. Builder→`coder`,
   Researcher→`market research`, Knowledge Curator→`knowledge`, but **Reviewer
   has none**, and demos 2/4/5 require review independent of the producer
   (code-review states, factual + regulatory + brand check). Either a new
   `bots/reviewer` profile (plus registry, delegator's "main profiles are …"
   list, kanban owner) or an explicit rule that a NAMED different profile
   reviews — never self-review.
4. **Policy conflict** — an existing block contradicts the spec. Found here:
   `## Workspace Bot Identity Policy` makes a bot the acting identity for
   approval messages while the spec requires a HUMAN approver;
   `## Approval Request Tool Policy` names the tools but forbids neither
   pre-approval execution nor self-approval; coder's
   `### Deployment and runtime port policy (required)` forces every
   execution/deploy to port 83 and forbids running unless asked — incompatible
   with staging → production → rollback. Report as conflicts to resolve, not as
   missing text.

**Step 4 — report shape.** Per-use-case verdict line (SUPPORTED / PARTIAL /
NOT SUPPORTED, one row each — here: 1/2/5/6 PARTIAL, 3/4 NOT SUPPORTED), then
(a) blockers no SOUL edit can fix (platform objects, missing owner, card-schema
fields, missing lifecycle vocabulary), (b) ONE shared section to append to all
files, (c) per-profile "what is required" (role in the flows, what it already
has, what to add), (d) conflicts, (e) "not verified in this review" — the W-bridge
backend fields and whether the loaded profiles actually have the MCP/terminal
tools the SOULs name. Close with the concrete next-step offer (per-profile
unified-diff patch files / draft the missing profile's SOUL / verify tool
wiring). Never write the changes.

**Still report drift.** Here the loaded mirrors lag the sources on the whole
knowledge stack (loaded: "memory MCP" / "Obsidian MCP" / `obsidian_notes`;
source: "Workspace memory MCP" / "neurostack MCP" / `neurostack_notes`) — for the
4 uppercase files `diff <(cat "src/SOUL.MD") ~/.hermes/profiles/<id>/SOUL.md`
shows it in ~5 hunks each. The agents run the loaded copies, so a §6-style drift
line belongs in the report even when the request is read-only.
