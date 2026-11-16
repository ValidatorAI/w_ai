#!/usr/bin/env python3
"""turn-phase-report.py — decompose each recent turn of a Hermes profile into
phases, using that profile's OWN agent.log.

    python3 turn-phase-report.py <profile> [--turns 5] [--log /path/to/agent.log]

Phases (see references/turn-latency-profiling.md for the anchor table):

    intake+bootstrap   agent_init / tool tiering / memory-provider registration -> turn start
    recall+assembly    turn start -> model call issued   (memory recall + prompt build, UNSEGMENTED)
    model call         model call issued -> "API call #1" line
    finalize           "API call #1" -> HTTP 200 access line

Why a script: doing this by eye produced two wrong numbers in practice — a regex
that only matched file-tool line prefixes, and a "last match wins" scan in which a
LATER run's turn_context overwrote an EARLIER run's mark (bogus 7.547 s bootstrap).
This resets its pending record at every turn_context, so each marker belongs to one
turn only.
"""
import argparse
import os
import re
import sys
from datetime import datetime

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(.*)$")

PATTERNS = [
    ("boot", r"run_agent: OpenAI client created \(agent_init"),
    ("tier", r"tools\.tool_search: tool_search activated \(tier 1\): (\d+) core/visible tools kept, "
             r"(\d+) deferred \(~(\d+) tokens\), listing full \(budget ~(\d+) tokens\)"),
    ("ov_reg", r"Memory provider 'openviking' registered \((\d+) tools\)"),
    ("ov_act", r"Memory provider 'openviking' activated"),
    ("turn_start", r"agent\.turn_context: conversation turn: session=(\S+) .*?history=(\d+)"),
    ("model_issue", r"OpenAI client created \(chat_completion_stream_request"),
    ("api", r"agent\.conversation_loop: API call #(\d+): .*? in=(\d+) out=(\d+) total=(\d+) "
            r"latency=([0-9.]+)s cache=(\S+)"),
    ("turn_end", r"agent\.conversation_loop: Turn ended:"),
    ("http", r"aiohttp\.access: .*POST /p/([^/]+)/v1/chat/completions HTTP/1\.1\" (\d+) (\d+)"),
]


def parse(path, tail_bytes=8 * 1024 * 1024):
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - tail_bytes))
        text = fh.read().decode("utf-8", "replace")
    out = []
    for line in text.splitlines():
        m = TS_RE.match(line)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f")
        rest = m.group(2)
        for kind, pat in PATTERNS:
            km = re.search(pat, rest)
            if km:
                out.append((ts, kind, km))
                break
    return out


def report(events, limit):
    turns = []
    pending = None
    prebuf = []          # boot/tier/ov markers seen since the last turn closed
    tier_line = None

    def close(turn):
        if turn and turn.get("http"):
            turns.append(turn)

    for ts, kind, m in events:
        if kind == "turn_start":
            close(pending)
            pending = {"session": m.group(1), "history": int(m.group(2)),
                       "t_start": ts, "pre_markers": list(prebuf)}
            prebuf = []
            continue
        if kind == "tier":
            tier_line = m
        if kind in ("boot", "tier", "ov_reg", "ov_act"):
            prebuf.append((ts, kind))
            prebuf = prebuf[-6:]
            continue
        if pending is None:
            continue
        pending[kind] = ts
        if kind == "api":
            pending["in"], pending["out"] = int(m.group(2)), int(m.group(3))
            pending["lat"], pending["cache"] = m.group(5), m.group(6)
        if kind == "http":
            pending["status"], pending["bytes"] = m.group(2), m.group(3)
            close(pending)
            pending = None
    close(pending)

    print("log: %s" % path_used)
    if tier_line:
        print("tool tiering: %s core/visible kept, %s deferred (~%s tokens), listing budget ~%s tokens"
              % (tier_line.group(1), tier_line.group(2), tier_line.group(3), tier_line.group(4)))
    print()
    if not turns:
        print("no completed turns found (are you reading the profile that SERVED the request?)")
        return 1

    hdr = ("%-22s %-13s %-10s %-11s %-10s %-8s %-9s %s"
           % ("session", "turn start", "bootstrap", "recall+asm", "model", "finalize", "internal", "tokens in/out (cache)"))
    print(hdr)
    print("-" * len(hdr))
    for t in turns[-limit:]:
        boot = None
        if t.get("pre_markers"):
            boot = (t["t_start"] - t["pre_markers"][0][0]).total_seconds()
        pre = (t["model_issue"] - t["t_start"]).total_seconds() if t.get("model_issue") else None
        mdl = (t["api"] - t["model_issue"]).total_seconds() if t.get("api") and t.get("model_issue") else None
        post = (t["http"] - t["api"]).total_seconds() if t.get("api") and t.get("http") else None
        internal = (t["http"] - t["t_start"]).total_seconds() if t.get("http") else None

        def f(v):
            return "-" if v is None else "%.3f" % v

        print("%-22s %-13s %-10s %-11s %-10s %-8s %-9s %s/%s (cache %s)"
              % (t["session"][:22], t["t_start"].strftime("%H:%M:%S.%f")[:-3],
                 f(boot), f(pre), f(mdl), f(post), f(internal),
                 t.get("in", "?"), t.get("out", "?"), t.get("cache", "?")))
    print()
    print("recall+asm is UNSEGMENTED (memory recall + prompt assembly): the log has no")
    print("separator. bootstrap excludes intake before agent_init; 'internal' excludes the")
    print("client's socket/intake time, so compare it against curl's total from")
    print("probe-profile-latency.sh rather than treating it as the user-visible time.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--turns", type=int, default=5)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    path_used = a.log or os.path.join(home, "profiles", a.profile, "logs", "agent.log")
    if not os.path.exists(path_used):
        alt = os.path.join(home, "logs", "agent.log")
        print("! %s not found; falling back to %s" % (path_used, alt), file=sys.stderr)
        path_used = alt
    sys.exit(report(parse(path_used), a.turns))
