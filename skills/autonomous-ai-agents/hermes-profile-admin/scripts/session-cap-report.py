#!/usr/bin/env python3
"""Report the effective chat-session cap and the current slot holders.

Read-only probe for the recurring question "is there a max number of running
sessions on this box — and who is holding the slots?".

Mirrors the resolution used by
``hermes_cli/active_sessions.py::resolve_max_concurrent_sessions``:
top-level ``max_concurrent_sessions`` wins, ``gateway.max_concurrent_sessions``
is the fallback, and null / 0 / invalid (bool, non-numeric) = unlimited.
Then reads the lease registry each surface writes to
``<HERMES_HOME>/runtime/active_sessions.json``.

Usage (PyYAML lives in the Hermes venv):
    ~/.hermes/hermes-agent/venv/bin/python session-cap-report.py [--root ~/.hermes]

Facts the output encodes:
- The cap is PER $HERMES_HOME (profile), not machine-wide — hence one row per
  profile. It IS shared across surfaces inside a profile.
- Only the messaging gateway snapshots it at boot (`hermes gateway restart`);
  the TUI/dashboard path re-reads config.yaml behind an mtime cache, and CLI /
  kanban workers are fresh processes that read config.yaml at start.
- A stale lease (dead pid) is pruned by the lease code on the next claim, so a
  holder whose pid no longer exists is not really consuming a slot.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time


def load_yaml(path: str) -> dict:
    try:
        import yaml
    except ImportError:  # pragma: no cover - environment dependent
        sys.exit(
            "PyYAML not importable. Re-run with the Hermes venv python:\n"
            "  ~/.hermes/hermes-agent/venv/bin/python " + os.path.basename(__file__)
        )
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception as exc:
        print(f"  ! could not read {path}: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


def coerce_int(value) -> "int | None":
    """Positive int cap, or None when disabled/unset/invalid (matches the source)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, float):
            if not value.is_integer():
                return None
            parsed = int(value)
        elif isinstance(value, str):
            parsed = int(value.strip(), 10)
        else:
            parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def resolve_cap(cfg: dict) -> "tuple[int | None, str]":
    """Return (cap, where-it-came-from)."""
    if "max_concurrent_sessions" in cfg:
        return coerce_int(cfg.get("max_concurrent_sessions")), "top-level"
    gateway = cfg.get("gateway")
    if isinstance(gateway, dict) and "max_concurrent_sessions" in gateway:
        return (
            coerce_int(gateway.get("max_concurrent_sessions")),
            "gateway.max_concurrent_sessions (fallback)",
        )
    return None, "unset"


def lease_entries(home: str) -> list:
    path = os.path.join(home, "runtime", "active_sessions.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        print(f"    ! registry unreadable ({exc}) -> cap fails OPEN, sessions admitted")
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("entries", "sessions", "leases"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def home_rows(root: str) -> "list[tuple[str, str]]":
    """(label, HERMES_HOME) for the root config plus every profile."""
    rows = [("default (root)", root)]
    for cfg_path in sorted(glob.glob(os.path.join(root, "profiles", "*", "config.yaml"))):
        rows.append((os.path.basename(os.path.dirname(cfg_path)), os.path.dirname(cfg_path)))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.join(os.path.expanduser("~"), ".hermes"),
                    help="Hermes root (default: ~/.hermes)")
    args = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(args.root))

    print(f"root: {root}")
    print(f"{'home':<18} {'cap':>6}  {'source':<38} holders")
    print("-" * 96)

    for label, home in home_rows(root):
        cfg_path = os.path.join(home, "config.yaml")
        cfg = load_yaml(cfg_path) if os.path.exists(cfg_path) else {}
        cap, source = resolve_cap(cfg)
        entries = lease_entries(home)
        counts: "dict[str, int]" = {}
        stale = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("pid") is not None and not pid_alive(entry.get("pid")):
                stale += 1
                continue
            surface = str(entry.get("surface") or "unknown")
            counts[surface] = counts.get(surface, 0) + 1
        held = ", ".join(f"{k} x{v}" if v > 1 else k
                         for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
        if not held:
            held = "none"
        if stale:
            held += f" (+{stale} stale lease(s) from dead pids)"
        print(f"{label:<18} {('unlimited' if cap is None else cap):>6}  {source:<38} {held}")

    print()
    print("Reminder: per-profile value, shared across that profile's CLI / TUI / "
          "dashboard / messaging surfaces.")
    print("Only the messaging gateway needs `hermes gateway restart` to honour a "
          "change; CLI and kanban workers pick it up in their next process.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
