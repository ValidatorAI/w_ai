#!/usr/bin/env python3
"""Disable (or restore) EVERY MCP server in EVERY Hermes profile config.

Covers the fleet-wide case: root config.yaml + profiles/*/config.yaml.
Sets `enabled: false` on each server under `mcp_servers` via a MINIMAL textual
splice, then verifies in two layers (semantic + textual).

WHY NOT the obvious routes
--------------------------
* `hermes config set mcp_servers.X.enabled false` — works, but rewrites the
  whole file through the YAML dumper: every comment line is dropped (36 of them
  in each of the 17 configs on this box).
* a ruamel.yaml round-trip dump with `preserve_quotes`/comment preservation —
  semantically lossless BUT it re-wraps long plain scalars (the persona strings)
  and re-indents block sequences (ruamel indent 2 vs the original 0), so the
  textual diff is ~200 lines per file for a 3-line change. Splice, never dump.

THE PITFALL THIS SCRIPT EXISTS TO AVOID
---------------------------------------
A naive "find every `  <name>:` line" scan is NOT constrained to the
`mcp_servers` block, so it also matches `platform_toolsets` children
(`  cli:`, `  discord:`, ...) and `plugins` children (`  enabled:`,
`  disabled:`) and injects `enabled: false` into them. Observed live: default
reported "17 servers", coder reported "4" — i.e. corruption, silently applied.
Always bound the scan: the block ends at the next non-blank line at indent 0.

USAGE
-----
    python3 disable-mcps-fleet-wide.py                 # dry run (default)
    python3 disable-mcps-fleet-wide.py --apply         # back up, then write
    python3 disable-mcps-fleet-wide.py --restore       # roll back newest backup
    python3 disable-mcps-fleet-wide.py --root ~/.hermes
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import time

from ruamel.yaml import YAML  # only used for load/compare, never for dump

SAFE = YAML(typ="safe")
TOP = re.compile(r"^([^\s#][^:]*):")


def config_paths(root: str) -> list[str]:
    paths = [os.path.join(root, "config.yaml")]
    paths += sorted(glob.glob(os.path.join(root, "profiles", "*", "config.yaml")))
    return [p for p in paths if os.path.isfile(p)]


def profile_name(path: str) -> str:
    return path.split("/profiles/")[-1].split("/")[0] if "/profiles/" in path else "default"


def find_block(lines: list[str]) -> tuple[int, int, int] | None:
    """Return (mcp_idx, mcp_end, server_indent) for the top-level mcp_servers block."""
    mcp_idx = None
    for i, s in enumerate(lines):
        m = TOP.match(s)
        if m and m.group(1).strip() == "mcp_servers":
            mcp_idx = i
            break
    if mcp_idx is None:
        return None
    mcp_end = len(lines)
    for i in range(mcp_idx + 1, len(lines)):          # bound the scan!
        s = lines[i]
        if not s.strip():
            continue
        if len(s) - len(s.lstrip()) == 0:
            mcp_end = i
            break
    sind = None
    for s in lines[mcp_idx + 1 : mcp_end]:
        if s.strip():
            sind = len(s) - len(s.lstrip())
            break
    if sind is None:
        return None
    return mcp_idx, mcp_end, sind


def rewrite(path: str, lines: list[str], mcp_idx: int, mcp_end: int, sind: int) -> tuple[list[str], int]:
    """Splice `enabled: false` into each server block. Returns (lines, count)."""
    body = lines[mcp_idx + 1 : mcp_end]
    name_re = re.compile(r"^ {%d}([^\s#][^:]*?):\s*(#.*)?$" % sind)
    starts = [i for i, s in enumerate(body) if name_re.match(s)]
    if not starts:
        return lines, 0
    starts.append(len(body))

    out = list(lines[: mcp_idx + 1])
    count = 0
    for bi in range(len(starts) - 1):
        bstart, bend = starts[bi], starts[bi + 1]
        real_end = bend
        for k in range(bstart + 1, bend):             # crisp end of THIS server
            s = body[k]
            if not s.strip():
                continue
            if len(s) - len(s.lstrip()) <= sind and not s.lstrip().startswith("#"):
                real_end = k
                break
        block, rest = body[bstart:real_end], body[real_end:bend]
        eidx = next(
            (k for k, s in enumerate(block) if re.match(r"^ {%d}enabled:\s*" % (sind + 2), s)),
            None,
        )
        if eidx is not None:
            block[eidx] = " " * (sind + 2) + "enabled: false\n"
        else:
            block.insert(1, " " * (sind + 2) + "enabled: false\n")
        count += 1
        out.extend(block)
        out.extend(rest)
    out.extend(lines[mcp_end:])
    return out, count


def strip_enabled(obj) -> dict:
    o = json.loads(json.dumps(obj))
    for cfg in (o.get("mcp_servers") or {}).values():
        if isinstance(cfg, dict):
            cfg.pop("enabled", None)
    return o


def verify(path: str, backup: str) -> tuple[bool, str]:
    """Layer 1: semantics identical apart from enabled flags.
    Layer 2: every textual change is an `enabled:` line."""
    old = strip_enabled(SAFE.load(open(backup)))
    new = strip_enabled(SAFE.load(open(path)))
    if old != new:
        keys = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
        return False, f"semantic drift in {keys}"
    import subprocess

    diff = subprocess.run(["diff", "-u", backup, path], capture_output=True, text=True).stdout
    bad = [
        l
        for l in diff.splitlines()
        if l[:1] in "+-" and l[:3] not in ("+++", "---") and "enabled:" not in l
    ]
    if bad:
        return False, f"non-enabled textual change: {bad[:3]}"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.expanduser("~/.hermes"))
    ap.add_argument("--apply", action="store_true", help="write changes (default is dry run)")
    ap.add_argument("--restore", action="store_true", help="roll back newest backup")
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d-%H%M%S")
    total = ok = 0
    for path in config_paths(args.root):
        prof = profile_name(path)
        if args.restore:
            baks = sorted(glob.glob(path + ".bak-mcpdisable-*"))
            if not baks:
                print(f"{prof:20s} no backup -> skip")
                continue
            shutil.copy2(baks[-1], path)
            print(f"{prof:20s} restored from {os.path.basename(baks[-1])}")
            continue

        lines = open(path).read().splitlines(keepends=True)
        blk = find_block(lines)
        if blk is None:
            print(f"{prof:20s} no/empty mcp_servers -> skip")
            continue
        new_lines, count = rewrite(path, lines, *blk)
        if not count:
            print(f"{prof:20s} no servers parsed -> skip")
            continue
        names = [s.strip().rstrip(":") for s in lines[blk[0] + 1 : blk[1]]
                 if re.match(r"^ {%d}([^\s#][^:]*?):" % blk[2], s)]
        if not args.apply:
            print(f"{prof:20s} WOULD disable {count}: {', '.join(names)}")
            total += count
            continue
        backup = f"{path}.bak-mcpdisable-{ts}"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)          # PRE-write copy, always
        open(path, "w").writelines(new_lines)
        good, why = verify(path, backup)
        ok += good
        total += count
        print(f"{prof:20s} disabled {count}: {', '.join(names)}  verify={'OK' if good else 'FAIL:' + why}")

    if args.apply and not args.restore:
        print(f"\n{total} servers disabled; {ok} configs verified clean")
        print("MCP discovery is startup-time: a running gateway/agent keeps its "
              "existing connections until its next rebuild. `hermes mcp list` "
              "(non-TTY) is the status view; `hermes -p NAME mcp list` per profile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
