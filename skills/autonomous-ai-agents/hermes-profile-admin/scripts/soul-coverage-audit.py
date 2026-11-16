#!/usr/bin/env python3
"""Audit profile SOUL.md coverage against a Bonfire/W-bridge page spec doc.

For every page in the spec, report each tool/entity as:
  strict  in the section whose code maps to that page   (when-to-use, right page)
  any     in SOME SECTION-xx block                      (when-to-use, moved page)
  file    anywhere in the file only                     (bare mention, no contract)

Distinguishing those three columns IS the deliverable -- a name that appears in
an "Approval Request Tool Policy" block is not covered. See
references/soul-coverage-audit.md for the method, the failure classes and a
worked example.

Usage:
  python3 soul-coverage-audit.py --spec /path/page_sections_and_entities.md \
      [--profiles-dir ~/.hermes/profiles] [--default-soul ~/.hermes/SOUL.md] \
      [--mcp-impl /path/W-bridge/mcp/tools.py] \
      [--source-tree /path/W-ai/hermes/profiles]

Exit 1 if a spec tool has no when-to-use anywhere; 0 otherwise.
"""
import argparse, glob, os, re, sys

CODE_PAGE = {                      # SECTION-<code>-nn  ->  spec page keyword
    "CH": ["company home"],
    "CS": ["company status"],
    "PO": ["project overview"],
    "PS": ["project status"],
    "PA": ["all-hands", "all hands"],
    "PK": ["project knowledge"],
}
SKIP_PAGE = re.compile(r"quick|map", re.I)          # trailing summary sections
NAME_RE = r'(?<![a-z0-9_])%s(?![a-z0-9_])'


def parse_spec(path):
    """-> (pages: {page_name: [tools]}, entities: [names])

    Tools are the backticked identifiers under each '## <n>. Page' heading.
    Entities are the bare Capitalised bullets ('  - AttentionItem'); lowercase
    bullets (categories / status values) and multi-word names are ignored, which
    is enough to separate entities from prose in this doc format.
    """
    txt = open(path, encoding="utf-8", errors="replace").read()
    pages, entities, cur = {}, [], None
    for line in txt.splitlines():
        m = re.match(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", line)
        if m:
            title = m.group(1).strip()
            cur = None if SKIP_PAGE.search(title) else title
            if cur:
                pages.setdefault(cur, [])
            continue
        e = re.match(r"^\s*-\s+([A-Z][A-Za-z]+)\s*$", line)
        if e and e.group(1) not in entities:
            entities.append(e.group(1))
        if cur:
            for tok in re.findall(r"`([a-z0-9_]+)`", line):
                if tok not in pages[cur]:
                    pages[cur].append(tok)
    return pages, entities


def code_for_page(page):
    low = page.lower()
    for code, keys in CODE_PAGE.items():
        if any(k in low for k in keys):
            return code
    return None


def collect_souls(profiles_dir, default_soul, source_tree):
    """-> [(label, text)] ; label is the profile id, 'SRC:<id>' for sources."""
    out = []
    if default_soul and os.path.exists(os.path.expanduser(default_soul)):
        out.append(("default", open(os.path.expanduser(default_soul), encoding="utf-8",
                                    errors="replace").read()))
    for p in sorted(glob.glob(os.path.join(os.path.expanduser(profiles_dir), "*", "SOUL.md"))):
        out.append((p.split(os.sep)[-2], open(p, encoding="utf-8", errors="replace").read()))
    if source_tree:
        for d in sorted(glob.glob(os.path.join(os.path.expanduser(source_tree), "*", "*"))):
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):                       # SOUL.md and SOUL.MD both count
                if fn.lower() == "soul.md":
                    pid = os.path.basename(d).lower().replace(" ", "_")
                    out.append(("SRC:" + pid,
                                open(os.path.join(d, fn), encoding="utf-8",
                                     errors="replace").read()))
    return out


def sections(text):
    """-> {SECTION-ID: body}"""
    parts = re.split(r"\n###\s*(SECTION-[A-Z]+-\d+)", text)
    return dict(zip(parts[1::2], parts[2::2]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--profiles-dir", default="~/.hermes/profiles")
    ap.add_argument("--default-soul", default="~/.hermes/SOUL.md")
    ap.add_argument("--mcp-impl")
    ap.add_argument("--source-tree")
    a = ap.parse_args()

    pages, entities = parse_spec(os.path.expanduser(a.spec))
    if not pages or not any(pages.values()):
        sys.exit("spec parse found no pages/tools -- check the '## N. Page' headings "
                 "and that tool names are backticked in the doc")

    souls = collect_souls(a.profiles_dir, a.default_soul, a.source_tree)
    if not souls:
        sys.exit("no SOUL.md found under %s" % a.profiles_dir)

    impl = ""
    if a.mcp_impl:
        impl = open(os.path.expanduser(a.mcp_impl), encoding="utf-8", errors="replace").read()

    allpairs = [(p, t) for p, ts in pages.items() for t in ts]
    sec_hit = {k: 0 for k in allpairs}
    any_hit = {k: 0 for k in allpairs}
    file_hit = {k: 0 for k in allpairs}
    per_profile = {}

    for label, txt in souls:
        secs = sections(txt)
        mine = set()
        for sid, body in secs.items():
            code = sid.split("-")[1]
            for page, tools in pages.items():
                for t in tools:
                    if re.search(NAME_RE % re.escape(t), body):
                        any_hit[(page, t)] += 1
                        mine.add((page, t))
                        if code_for_page(page) == code:
                            sec_hit[(page, t)] += 1
        for page, tools in pages.items():
            for t in tools:
                if re.search(NAME_RE % re.escape(t), txt):
                    file_hit[(page, t)] += 1
        per_profile[label] = (sorted(secs), sorted({p for p, _ in mine}))

    print("spec pages: %d | unique tools: %d | souls audited: %d%s\n"
          % (len(pages), len({t for _, t in allpairs}), len(souls),
             " | source tree included" if a.source_tree else ""))

    gaps = []
    for page in pages:
        print("== %s" % page)
        for t in pages[page]:
            flag = ""
            if sec_hit[(page, t)] == 0:
                if any_hit[(page, t)]:
                    flag = "  <-- RELOCATED (when-to-use under another page)"
                elif file_hit[(page, t)]:
                    flag = "  <-- BARE MENTION only (no Trigger)"
                else:
                    flag = "  <-- ABSENT (no SOUL, and check the upstream spec)"
                    gaps.append((page, t))
            if impl and not re.search(NAME_RE % re.escape(t), impl):
                flag += "  [!! not in mcp impl]"
            print("   %-40s strict:%-2d any:%-2d file:%-2d%s"
                  % (t, sec_hit[(page, t)], any_hit[(page, t)], file_hit[(page, t)], flag))
        print()

    if entities:
        print("== entities (named somewhere / nowhere)")
        for e in entities:
            n = sum(1 for _, txt in souls if re.search(NAME_RE % re.escape(e), txt))
            print("   %-28s %d/%d" % (e, n, len(souls)))
        print()

    print("== profiles: sections -> pages covered")
    for label, (secs, pgs) in per_profile.items():
        print("   %-22s %-42s %s" % (label, ", ".join(secs) or "(none)",
                                     "; ".join(pgs) or "-"))

    if gaps:
        print("\n%d tool(s) with NO when-to-use in any SOUL:" % len(gaps))
        for page, t in gaps:
            print("   %s  (%s)" % (t, page))
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
