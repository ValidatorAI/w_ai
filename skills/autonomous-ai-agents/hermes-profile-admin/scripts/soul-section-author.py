#!/usr/bin/env python3
"""Author or upgrade a UNIFORM governed section across the whole SOUL fleet.

Use when the task is "add this rule/instruction to every profile's SOUL.md"
(as opposed to reconciling an existing section — that is soul-section-edit.py).

Drives from a JSON spec so the section TEXT is data, not code:
see templates/fleet-section-spec.json (the shipped spec is the working
Inter-Profile Card Handoff section, 2026-09-30).

  python3 soul-section-author.py [SPEC.json] [--apply] [--verify]

Mechanics that matter (all learned the hard way, see
references/soul-section-authoring.md):
  * writes the SOURCE tree first, then the loaded mirrors, in one pass
  * insert-or-UPGRADE: an existing section is replaced from its heading up to
    the next "## " heading, so a v2 revision never duplicates the block
  * the loaded profiles are backed up to per-file unique mirrored paths;
    the git-backed source tree is NOT backed up (git HEAD is the baseline)
  * one unified-diff patch per file against the PRE-CHANGE baseline
    (git show HEAD:<rel> for the source tree, the mirrored backup for loaded)
    so patches show the whole change, not just the v1->v2 delta
  * idempotent: a second run is a no-op ("already at vN" / "unchanged")
"""
import os, sys, json, glob, shutil, difflib, datetime, subprocess

SPEC_DEFAULT = os.path.expanduser(
    "~/.hermes/skills/autonomous-ai-agents/hermes-profile-admin/templates/fleet-section-spec.json")

SRC_ROOT = os.path.expanduser("~/Documents/codes/Pavel/W/W-ai/hermes/profiles")
REPO = os.path.expanduser("~/Documents/codes/Pavel/W/W-ai")
LOADED_ROOT = os.path.expanduser("~/.hermes/profiles")
DEFAULT_SOUL = os.path.expanduser("~/.hermes/SOUL.md")


def load_spec(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def targets():
    """[(tree, path)] for every SOUL file in both trees."""
    out = []
    for d in sorted(glob.glob(os.path.join(SRC_ROOT, "*", "*"))):
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.lower() == "soul.md":          # SOUL.MD and SOUL.md
                    out.append(("W-ai", os.path.join(d, fn)))
    for p in sorted(glob.glob(os.path.join(LOADED_ROOT, "*", "SOUL.md"))):
        out.append(("hermes", p))
    if os.path.exists(DEFAULT_SOUL):
        out.append(("hermes", DEFAULT_SOUL))         # the default profile
    return out


def profile_key(tree, path):
    """leaf dir name for sources, profile id for loaded files."""
    if path == DEFAULT_SOUL:
        return "default"
    parent = os.path.basename(os.path.dirname(path))
    if path.startswith(LOADED_ROOT + os.sep):
        return parent
    return parent.lower().replace(" ", "_")           # "normal message" -> normal_message


def rel_key(tree, path):
    if tree == "W-ai":
        return "W-ai/" + os.path.relpath(path, SRC_ROOT)
    return "hermes/" + os.path.relpath(path, os.path.expanduser("~/.hermes"))


def section(spec, key):
    patterns = spec["patterns"].get(key) or spec["patterns"].get("_default", [])
    return spec["core"] % (spec["heading"], "\n".join("- " + p for p in patterns))


def upsert(spec, txt, key):
    """insert the section, or replace an older revision of it in place."""
    sec = section(spec, key)
    head = spec["heading"]
    i = txt.find(head)
    if i >= 0:
        j = txt.find("\n## ", i + len(head))          # next level-2 heading
        end = j if j >= 0 else len(txt)
        if txt[i:end] == sec:
            return txt, "unchanged"
        return txt[:i] + sec + txt[end:], "upgraded in place"
    anchor = spec.get("anchor", "## Memory & Knowledge Separation")
    if anchor in txt:
        return txt.replace(anchor, sec + "\n" + anchor, 1), "inserted before %s" % anchor
    if not txt.endswith("\n"):
        txt += "\n"
    return txt + "\n" + sec, "appended at end of file"


def baseline(tree, path):
    """pre-change content for diffing: git HEAD for the source tree, the
    mirrored backup for the loaded profiles."""
    if tree == "W-ai":
        r = subprocess.run(["git", "show", "HEAD:%s" % os.path.relpath(path, REPO)],
                           cwd=REPO, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None
    bp = os.path.join(BACKUP_DIR, "hermes/" + os.path.relpath(path, os.path.expanduser("~/.hermes")))
    return open(bp, encoding="utf-8").read() if os.path.exists(bp) else None


def verify(spec, files):
    """presence + sanity battery; run after --apply (and again as the acceptance test)."""
    head = spec["heading"]
    subs = ["### " + s for s in spec.get("subsections", [])]
    bad = []
    for _tree, p in files:
        t = open(p, encoding="utf-8").read()
        if t.count(head) != 1:
            bad.append((p, "heading count %d" % t.count(head)))
        for s in subs:
            if s not in t:
                bad.append((p, "missing %s" % s))
        for stale in spec.get("forbids", []):        # phrasing the revision removed
            if stale in t:
                bad.append((p, "stale phrasing: %s" % stale))
    print("structure: %d file(s) checked, %d problem(s)" % (len(files), len(bad)))
    for p, why in bad:
        print("   !! %s: %s" % (p, why))
    return not bad


def main():
    global BACKUP_DIR
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply_ = "--apply" in sys.argv
    do_verify = "--verify" in sys.argv
    spec = load_spec(args[0] if args else SPEC_DEFAULT)
    BACKUP_DIR = os.path.expanduser(spec.get("backup_dir", "~/.hermes/.soul_backup_%s" % spec["label"])) \
        + "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    patch_dir = os.path.expanduser(spec.get("patch_dir", "~/soul-patches")) + "/%s-%s" % (
        spec["label"], datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(patch_dir, exist_ok=True)

    files = targets()
    combined, changed, patched = [], 0, 0
    for tree, path in files:
        old = open(path, encoding="utf-8").read()
        rel = rel_key(tree, path)
        new, how = upsert(spec, old, profile_key(tree, path))
        if how == "unchanged":
            print("  skip  %-52s (already current)" % rel)
            continue
        changed += 1
        print("  EDIT  %-52s %s" % (rel, how))
        base = baseline(tree, path)
        if base is not None and base != new:
            diff = list(difflib.unified_diff(base.splitlines(True), new.splitlines(True),
                                             fromfile="a/" + rel, tofile="b/" + rel, n=3))
            open(os.path.join(patch_dir, rel.replace("/", "__") + ".patch"),
                 "w", encoding="utf-8").writelines(diff)
            combined.extend(diff)
            patched += 1
        if apply_:
            if tree == "hermes":                     # git trees need no backup
                bp = os.path.join(BACKUP_DIR, "hermes/" + os.path.relpath(path, os.path.expanduser("~/.hermes")))
                os.makedirs(os.path.dirname(bp), exist_ok=True)
                shutil.copy2(path, bp)
            open(path, "w", encoding="utf-8").write(new)

    if combined:
        open(os.path.join(patch_dir, "ALL.patch"), "w", encoding="utf-8").writelines(combined)
    print("\n%d file(s) to change, %d patch(es) -> %s" % (changed, patched, patch_dir))
    # dry runs also create the patch dir — delete it if it holds no patches
    if not patched:
        shutil.rmtree(patch_dir, ignore_errors=True)
        print("(empty patch dir removed)")
    if apply_:
        print("loaded-profile backup (pre-change state): %s" % BACKUP_DIR)
    print("MODE:", "APPLY" if apply_ else "DRY-RUN")
    if do_verify:
        verify(spec, [(t, p) for t, p in files])


main()
