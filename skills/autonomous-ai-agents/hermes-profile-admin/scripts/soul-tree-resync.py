#!/usr/bin/env python3
"""Resync a SOUL source tree into Hermes profiles. Source tree WINS.

Companion to sync-soul-profiles.sh: that one creates profiles + copies .env;
this one re-syncs an EXISTING fleet after the source tree was edited, and it
reports the delta first so a deletion in the source can't slip through unseen.

Usage:
  python3 soul-tree-resync.py <SOURCE_TREE> [--profiles DIR] [--apply]
                             [--only NAME[,NAME...]] [--skip NAME[,NAME...]]

  <SOURCE_TREE>   tree containing SOUL.md / SOUL.MD files, e.g.
                  ~/code/proj/hermes/profiles   (layout <group>/<soul-dir>/SOUL.md)
  --profiles DIR  target profiles dir (default: ~/.hermes/profiles)
  --apply         write (default is dry-run: prints the delta only)
  --only/--skip   restrict by profile id

Mapping rule: profile id = the SOUL file's PARENT DIRECTORY name, lowercased
with spaces -> underscores (group dirs are not profiles). Files that are not
soul.md (case-insensitive) are ignored; dot-dirs are skipped.

Report per profile: status, byte sizes, line adds/dels, and any REMOVED blocks
verbatim (first lines of each delete hunk) — deletions are the risky delta.
On --apply it backs up each changed target to
<profiles>/.soul_backup_<ts>/<profile>__SOUL.md (the dot-prefix keeps it out of
profile enumerations), copies bytes + mode, and re-reads to prove equality.
A write that fails or lands non-identically is reported per profile
(WRITE-FAILED / WRITE-MISMATCH) and the batch still completes; both that case
and a missing profile dir make the exit code 1.

Exit code 1 if any target profile dir is missing (nothing written for it).
"""
import argparse
import difflib
import os
import shutil
import sys
import time

DEFAULT_PROFILES = os.path.expanduser("~/.hermes/profiles")


def find_souls(src):
    found = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.lower() == "soul.md":
                leaf = os.path.basename(root).strip()
                prof = leaf.lower().replace(" ", "_")
                found.append((os.path.relpath(root, src), prof, os.path.join(root, f)))
    return sorted(found)


def delta(before, after):
    """Return (added_lines, removed_lines, removed_blocks) between two texts."""
    b = before.splitlines()
    a = after.splitlines()
    sm = difflib.SequenceMatcher(None, b, a)
    added = removed = 0
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
            blocks.append(b[i1:i2])
        elif tag == "replace":
            removed += i2 - i1
            added += j2 - j1
            blocks.append(b[i1:i2])
    return added, removed, blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--profiles", default=DEFAULT_PROFILES)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--skip")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",")} if args.only else None
    skip = {s.strip() for s in args.skip.split(",")} if args.skip else set()

    souls = find_souls(args.source)
    if not souls:
        print(f"no SOUL.md found under {args.source}")
        return 1

    todo, missing = [], []
    for rel, prof, src in souls:
        if only and prof not in only:
            continue
        if prof in skip:
            continue
        tgt = os.path.join(args.profiles, prof, "SOUL.md")
        if not os.path.isdir(os.path.join(args.profiles, prof)):
            missing.append((rel, prof))
            continue
        todo.append((rel, prof, src, tgt))

    print(f"mode: {'APPLY' if args.apply else 'dry-run'}   "
          f"source: {args.source}   profiles: {args.profiles}\n")
    backup = os.path.join(args.profiles, ".soul_backup_" + time.strftime("%Y%m%d_%H%M%S"))
    rows, changed, deleted_total = [], [], 0
    verified = {}
    errors = {}
    for rel, prof, src, tgt in todo:
        s = open(src, encoding="utf-8").read()
        t = open(tgt, encoding="utf-8").read()
        same = s.encode() == t.encode()
        added, removed, blocks = (0, 0, []) if same else delta(t, s)
        rows.append((prof, len(s.encode()), len(t.encode()), same, added, removed,
                     t.count("#### Related Profiles"), s.count("#### Related Profiles")))
        if same:
            continue
        changed.append(prof)
        deleted_total += removed
        if removed:
            print(f"--- {prof}: REMOVALS in source ({removed} lines) ---")
            for blk in blocks[:3]:
                for ln in blk[:4]:
                    print(f"    - {ln}")
                if len(blk) > 4:
                    print(f"    - ... ({len(blk) - 4} more lines)")
        if args.apply:
            os.makedirs(backup, exist_ok=True)
            try:
                shutil.copy2(tgt, os.path.join(backup, prof + "__SOUL.md"))
                shutil.copyfile(src, tgt)
                shutil.copymode(src, tgt)
                # re-read from disk: a write that silently failed must not be
                # reported as "updated". Checks the equality the docstring promises.
                verified[prof] = open(src, "rb").read() == open(tgt, "rb").read()
            except OSError as exc:
                # never abort the batch: report which profile failed and keep going
                verified[prof] = False
                errors[prof] = f"{type(exc).__name__}: {exc}"

    print(f"\n{'profile':20s}{'src B':>8s}{'tgt B':>8s}  status")
    for prof, sb, tb, same, added, removed, t_rel, s_rel in rows:
        if same:
            status = "identical"
        elif args.apply:
            status = f"updated (+{added}/-{removed})"
            if errors.get(prof):
                status += f"  WRITE-FAILED ({errors[prof].split(':', 1)[0]})"
            elif not verified.get(prof, False):
                status += "  WRITE-MISMATCH"
        else:
            status = f"needs sync (+{added}/-{removed})"
        print(f"{prof:20s}{sb:8d}{tb:8d}  {status}")

    mismatches = [p for p, ok in verified.items() if not ok]
    print(f"\nprofiles: {len(rows)}   changed: {len(changed)}   "
          f"removed lines: {deleted_total}   missing target dirs: {len(missing)}")
    if args.apply and changed:
        print(f"byte-verified after write: {len(verified) - len(mismatches)}/{len(verified)} targets")
    if mismatches:
        print(f"WRITE FAILURES (source != target after copy): {', '.join(sorted(mismatches))}")
        for pro in sorted(mismatches):
            if errors.get(pro):
                print(f"    {pro}: {errors[pro]}")
    for rel, prof in missing:
        print(f"  MISSING profile dir for {rel} -> {prof} (create it first: "
              f"hermes profile create {prof} --clone-from default)")
    if changed and args.apply:
        print(f"backups: {backup} ({len(changed)} files)")
        print("note: SOUL.md is read per session — no gateway restart needed.")
    elif changed:
        print("re-run with --apply to write.")
    return 1 if (missing or mismatches) else 0


if __name__ == "__main__":
    sys.exit(main())
