# Authoring a Fleet-Wide Governed SOUL Section

Companion to `references/soul-coverage-audit.md`. §9/§10 there cover *auditing*
and *reconciling an existing* section; this file covers the other half: the user
asks for a NEW rule to exist in every profile ("mention in the soul.md when
they should create a card to send another task to another profile"), or asks to
REVISE a section already deployed ("so did you consider creating multiple
cards as well").

Reference implementation: `scripts/soul-section-author.py` +
`templates/fleet-section-spec.json` (the shipped spec is the live
Inter-Profile Card Handoff section). Worked example: 2026-09-30, 32 files
across the two trees, v1 then v2.

## 1. Sequence

1. **Ask the scope question once, then act.** "Each profile" for this user means
   the full set: the 15-file W-ai source tree, the 16 loaded profiles, AND
   `~/.hermes/SOUL.md` (the `default` profile). Name the non-obvious inclusions
   in the reply (`default`, `testprofile`, and any profile with no page sections)
   and offer to strip any of them — do not silently narrow, and do not ask twice.
2. **Write the section as data**: shared `core` + a per-profile `patterns`
   block. A single identical paragraph for 16 roles reads as boilerplate and
   gets ignored; one tailored bullet per role ("coker: a decision you received
   that changes scope … -> `project_manager`") is what makes it actionable.
3. **Dry run, read the plan, then apply.**
   `python3 scripts/soul-section-author.py templates/fleet-section-spec.json`
   then `--apply`.
4. **Source tree first, mirrors in the same pass** (a mirror-only edit
   re-diverges on the next `soul-tree-resync.py`).
5. **Verify** (§4) and report with patch paths + backups.

## 2. Insertion point and the upgrade path

- Insertion anchor: the first line starting `## ` (default
  `## Memory & Knowledge Separation`), so the new section lands right after the
  file's own `### Kanban` block and before the shared boilerplate. Files with no
  such anchor (`config`, `se/config`) get it appended at end — say which.
- **Upgrade, do not append a second copy.** Locate the heading, cut from there
  to the next `\n## `, and splice the new revision in. Cutting to the next
  `\n## ` (not `##`) is what makes this safe: the section contains `###`
  subsections, so matching bare `##` would truncate mid-block.
- Idempotence = comparing the existing slice to the freshly rendered section
  and skipping when equal; a second run must print `already current` for all N.

## 3. Patches and backups — the user's standing rule

- **The W-ai tree is a git repo: do NOT create backup copies there.** The user
  said so explicitly ("when updating in …/W-ai/hermes no need to create a
  backup version"). `git status --short` is the audit trail and
  `git show HEAD:<relpath>` is the diff baseline. Loaded profiles are not in
  git, so they DO get backups — mirrored per-file paths
  (`<backup>/hermes/<profile>/SOUL.md`), never a flat dir (every file is
  named `SOUL.md`).
- **Emit one unified-diff patch per file** (`a/<tree>/<rel>` … `b/…`) plus
  `ALL.patch`, diffed against the **pre-change baseline**, so each patch shows
  the whole change rather than just the latest revision. Baseline = `git show
  HEAD:` for sources, the mirrored backup for loaded.
- Write the patch directory OUTSIDE both repos (this box:
  `~/Documents/codes/Pavel/W/soul-patches/`) so it does not show up as untracked
  noise in the user's repo.
- **Dry runs create the patch directory too** (makedirs happens before the
  loop). Delete it when it holds no patches, and clean up any duplicate dry-run
  directories before reporting, or the user sees four near-identical dirs.
- Expect the W-ai diff to be pure insertions (`git diff --stat` → `N files
  changed, M insertions(+)`, 0 deletions) when the section is new.

## 4. Verification battery (for a NEW section)

Run all five; each catches a different failure:

1. **Structure** — heading occurs exactly ONCE per file and every subsection
   heading is present (`--verify` in the script does this).
2. **No stale phrasing** — for a revision, grep the previous wording that the
   new version supersedes (v2: `One handoff = one card`) and assert zero hits.
   This is the check that proves an upgrade replaced rather than coexisted.
3. **Loaded vs backup line math** — diff every loaded file against its backup:
   for a pure insertion the count is exactly `+N/-0` with N = the section size.
   Any removed line means the splice ate content.
4. **Source ↔ mirror section equality** — extract the section from each of the
   14 source/mirror pairs and compare byte-for-byte; they must be identical or
   the next resync will churn.
5. **Idempotency** — re-run the script: `0 file(s) to change`.

Two extra sanity checks worth the two seconds: the duplicate-source pair
(`main/config` vs `se/config`) is still byte-identical, and the new section in
a file that took the append path (`config`) still reads correctly (blank line
before the following heading, file ends with a newline).

## 5. PITFALL: a rule can be accurate and still forbid what the user wants

The v1 wording was *"One handoff = one card: one owner, one expected outcome."*
Every audit axis was green and the section deployed cleanly — and it was wrong,
because the user's real expectation was fan-out:

> "so did you consider creating multiple cards as well, so in case of
> requirement one profile could create two cards / two or more cards for other
> profiles"

The lesson generalizes to any governance text you author for this fleet: when a
rule states an atomicity constraint, an exclusivity, or a "only/never" clause,
**check it still permits the multi-instance case the user may expect** — and if
it does not, the fix is not to soften the constraint but to state it at the
right level ("one card = one owner and one outcome" + an explicit
"When to split into two or more cards" subsection + "you are expected to create
as many as the work requires").

Practical form of the check, run BEFORE presenting the draft:

- restate the rule as a capability question ("can a profile create two cards?")
  and answer it from the text alone;
- scan for the words `only`, `never`, `single`, `one … =`, `do not … other
  than` and ask what each one forbids;
- if the user's phrasing included a plural ("two or more", "several", "each"),
  the section needs an explicit multi-case clause;
- when revising, keep the superseded phrasing in the spec's `forbids` list so
  `--verify` proves no file kept it.

Related: additive edits keep both placements (SKILL.md pitfall), and this same
reflex extends the earlier audit rule — audit both halves of a capability
(single AND multiple), not just presence of a mention.

## 6. Live state of the fleet section (2026-09-30, v2)

32 files carry `## Inter-Profile Card Handoff`: 15 sources (no backup, git) and
17 loaded (16 profiles + `default`). Structure 32/32 clean, sections
byte-identical across all 14 pairs, idempotent, W-ai diff = 15 files / 810
insertions.

Open editorial items left with the user (do not decide these unilaterally):

- whether `delegator` should carry the section at all (its routing text already
  covers it — redundant but harmless);
- whether `default` / `testprofile` / `mechanical-modeler` should carry it;
- the 7 files whose older boilerplate still says "Escalate unresolved actions
  into delivery tracking when needed: `add_project_todo`, `edit_project_todo`" —
  the new Guardrails line says not to use that as a cross-profile handoff
  substitute, so the two coexist until the user picks one channel;
- committing the W-ai changes.

## 7. Report shape

Order: what was added (the section's subsections, with the rule wording quoted);
where (both trees, counts, backup path, "no backup in W-ai — git is the
history"); the patch directory and its contents; the verification numbers
verbatim (32/32, `+628/-0`, 14/14 identical, idempotent); then the open
editorial items. Plain text, no markdown. When you have just corrected your own
draft, say so in the first line rather than presenting v2 as if it were the
original plan.
