#!/usr/bin/env python3
"""Section-scoped, ADDITIVE edits across a SOUL.md fleet (source tree first, then mirrors).

Why a script and not `patch`/`sed`: the target lines are byte-identical across
many profiles, and doing N whole-file edits through tool calls blows the 50-call
sandbox cap. One script, dry-run first, mirrored backups, then a requirement
re-scan.

Model of the job (2026-09-30, page-attribution reconciliation):
  rule = (a SECTION block, an anchor line that must occur EXACTLY once,
          a replacement that mentions the tools the section is missing)
The anchor-count assertion is the whole safety story: it turns "which section did
I edit?" into a hard failure instead of a silent wrong edit.

Usage:
  python3 soul-section-edit.py                      # dry run, both trees
  python3 soul-section-edit.py --apply
  python3 soul-section-edit.py --apply --only loaded
  python3 soul-section-edit.py --src /path/to/source --dst ~/.hermes/profiles

After --apply it re-reads every target and re-checks `require`, then prints a
+/- line summary per file so the operator can compare against the expected
line math (a two-rule file = +2/-1 when one rule appends a bullet and the other
replaces a line; a bullet-only file = +1/-0; a replace-only file = +1/-1).
"""
import argparse
import datetime
import difflib
import glob
import os
import re
import shutil
import sys

# ---------------------------------------------------------------- rules ------
# Each rule targets ONE section id. `require` is the set of tool names the
# section must end up naming (also used as the idempotence guard).
RULES = [
    {
        "why": "doc page 3 (Project Overview) owns the milestone write tools",
        "section": "SECTION-PO-01",
        "require": ["add_project_milestone", "edit_project_milestone"],
        "anchor": ("- Build the execution-side project snapshot: `project_milestones`, "
                   "`project_todos`, `project_bottlenecks`.\n"),
        "replace": ("- Build the execution-side project snapshot: `project_milestones`, "
                    "`project_todos`, `project_bottlenecks`.\n"
                    "- Milestone lifecycle writes for overview-level planning: "
                    "`add_project_milestone`, `edit_project_milestone`.\n"),
    },
    {
        "why": "doc page 4 (Project Status) owns the knowledge-item write tools",
        "section": "SECTION-PS-01",
        "require": ["add_project_knowledge_item", "edit_project_knowledge_item"],
        "anchor": ("- Context support for status decisions: `project_knowledge_items`, "
                   "`project_decision_records`.\n"),
        "replace": ("- Context support for status decisions: `project_knowledge_items`, "
                    "`add_project_knowledge_item`, `edit_project_knowledge_item`, "
                    "`project_decision_records`.\n"),
    },
]


# ------------------------------------------------------------- helpers ------
def blocks(txt):
    """SECTION-ID -> block text (header included, ends at the next ### SECTION-)."""
    out = {}
    for blk in re.split(r'\n(?=###\s*SECTION-)', txt):
        m = re.match(r'###\s*(SECTION-[A-Z]+-\d+)', blk)
        if m:
            out[m.group(1)] = blk
    return out


def plan(path):
    """Return (new_text, [edit labels]) or raise SystemExit on an unsafe anchor."""
    txt = open(path, encoding="utf-8").read()
    bl = blocks(txt)
    new, labels = txt, []
    for rule in RULES:
        sec = rule["section"]
        if sec not in bl:
            continue                                     # profile has no such page
        body = bl[sec]
        if all(re.search(r'(?<![a-z_])' + re.escape(t) + r'(?![a-z_])', body)
               for t in rule["require"]):
            continue                                     # already reconciled
        n = new.count(rule["anchor"])
        if n != 1:
            raise SystemExit("ABORT %s: anchor for %s occurs %d times (need 1)"
                             % (path, sec, n))
        new = new.replace(rule["anchor"], rule["replace"])
        labels.append("%s += %s" % (sec, ", ".join(rule["require"])))
    return new, labels


def source_files(root):
    out = []
    for d in sorted(glob.glob(os.path.join(root, "*", "*"))):
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.lower() == "soul.md":
                    out.append(os.path.join(d, fn))
    return out


def mirror_files(root):
    return sorted(glob.glob(os.path.join(root, "*", "SOUL.md")))


def rel_key(path, root, tag):
    """Backup path that is unique per file (never a flat dir: all files are SOUL.md)."""
    return os.path.join(tag, os.path.relpath(path, root))


# --------------------------------------------------------------- driver -----
def run(label, files, root, tag, backup_root, apply_):
    print("\n" + "#" * 18 + " %s " % label + "#" * 18)
    patched = 0
    for p in files:
        rel = os.path.relpath(p, root)
        old = open(p, encoding="utf-8").read()
        new, labels = plan(p)
        if not labels:
            print("  skip  %-45s (no target section / already reconciled)" % rel)
            continue
        patched += 1
        print("  EDIT  %-45s %s" % (rel, "; ".join(labels)))
        if not apply_:
            continue
        bp = os.path.join(backup_root, rel_key(p, root, tag))
        os.makedirs(os.path.dirname(bp), exist_ok=True)
        if not os.path.exists(bp):
            shutil.copy2(p, bp)
        open(p, "w", encoding="utf-8").write(new)
        # verify in place: requirements met, and diff math reported
        nb = blocks(open(p, encoding="utf-8").read())
        for rule in RULES:
            if rule["section"] in nb:
                missing = [t for t in rule["require"]
                           if t not in nb[rule["section"]]]
                if missing:
                    print("        !! REQUIREMENT FAIL after write: %s" % missing)
        d = list(difflib.unified_diff(old.splitlines(True), new.splitlines(True), n=0))
        add = [l for l in d if l.startswith("+") and not l.startswith("+++")]
        rem = [l for l in d if l.startswith("-") and not l.startswith("---")]
        print("        +%d/-%d lines" % (len(add), len(rem)))
    print("  -> %d file(s) %s" % (patched, "patched" if apply_ else "would be patched"))
    if apply_:
        print("  backup: %s" % backup_root)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser(
        "~/Documents/codes/Pavel/W/W-ai/hermes/profiles"),
        help="SOUL source tree (group>soul-dir>SOUL.md)")
    ap.add_argument("--dst", default=os.path.expanduser("~/.hermes/profiles"),
        help="loaded profiles dir")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", choices=["source", "loaded", "both"], default="both")
    a = ap.parse_args()

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if a.only in ("source", "both"):
        bak = os.path.join(os.path.dirname(os.path.dirname(a.src)),
                           ".soul_backup_sectionedit_%s" % ts)
        run("SOURCE", source_files(a.src), a.src, "src", bak, a.apply)
    if a.only in ("loaded", "both"):
        bak = os.path.join(os.path.dirname(a.dst),
                           ".soul_backup_sectionedit_%s" % ts)
        run("LOADED", mirror_files(a.dst), a.dst, "loaded", bak, a.apply)
    print("\nMODE:", "APPLY" if a.apply else "DRY-RUN  (source tree first, then mirrors)")


if __name__ == "__main__":
    sys.exit(main())
