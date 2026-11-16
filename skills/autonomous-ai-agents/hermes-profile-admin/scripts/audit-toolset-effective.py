#!/usr/bin/env python3
"""Audit the EFFECTIVE toolset set for every profile x platform.

Answers "is toolset X actually available to profile P on surface S?" using the
real resolver (hermes_cli.tools_config._get_platform_tools), NOT by scanning
the platform_toolsets lists.

Why not a literal scan: in a cloned fleet a messaging-platform key usually
holds a COMPOSITE name (``hermes-discord``, ``hermes-google_chat``), so
``'terminal' in platform_toolsets['discord']`` is False while the RESOLVED set
does contain terminal. A literal scan once reported 11 surfaces as "missing
terminal" that were in fact only blocked by agent.disabled_toolsets. Audit the
resolution, never the list membership.

Usage:
  python3 audit-toolset-effective.py [TOOLSET] [--profiles-dir DIR] [--src DIR]

  python3 audit-toolset-effective.py terminal
  python3 audit-toolset-effective.py file --profiles-dir ~/.hermes/profiles

Runs the resolver for every surface a profile configures, plus cli / api_server
/ cron (the surfaces that matter for bots). ~2s per profile — each profile is
resolved in a FRESH interpreter (this script re-execs itself), because the
resolver is home-dependent: plugin toolsets and credential-gated auto-enables
(x_search via xAI creds, homeassistant via HASS_TOKEN) read the profile's own
home, so one shared process across profiles can contaminate results.

Exit code: 0 when every profile has TOOLSET effective on every surface, 1
otherwise — so it can gate a rollout (`audit && for ... enable`).

Read-only. Two things it deliberately surfaces instead of hiding:
  * the resolver's own stderr warnings, e.g. "platform 'google_chat' has no
    valid toolsets configured (unknown name(s): hermes-google_chat)" — a
    PRE-EXISTING config defect in that profile (issue #38798), not caused by
    this run; reported here as a leading "⚠" line.
  * the profile's declared agent.disabled_toolsets, printed next to the
    resolved answer so you can see WHICH mechanism holds a toolset off.

The script itself writes nothing, but importing hermes_cli against a bare
profile dir can create empty hooks/ pairing/ skills/ scaffolding — same caveat
as the inline snippet in SKILL.md.
"""

import argparse
import glob
import json
import os
import subprocess
import sys

# Surfaces that matter even when a profile configures no key for them: bots and
# cron resolve these through the platform default, not through platform_toolsets.
DEFAULT_SURFACES = ("cli", "api_server", "cron")


def _resolve_one(args):
    """--_effective-one child mode: resolve TOOLSET for a single profile."""
    sys.path.insert(0, args.src)
    os.environ["HERMES_HOME"] = args.home

    import yaml

    from hermes_cli.tools_config import _get_platform_tools

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh) or {}

    platforms = list(cfg.get("platform_toolsets") or {})
    for extra in DEFAULT_SURFACES:
        if extra not in platforms:
            platforms.append(extra)

    off = []
    for plat in platforms:
        try:
            resolved = _get_platform_tools(cfg, plat)
        except Exception as exc:  # one bad surface must not abort the audit
            off.append("%s:ERR(%s)" % (plat, type(exc).__name__))
            continue
        if args.toolset not in resolved:
            off.append(plat)

    disabled = (cfg.get("agent") or {}).get("disabled_toolsets") or []
    print(
        "RESULT "
        + json.dumps(
            {
                "profile": args.profile,
                "off": off,
                "disabled": [str(x) for x in disabled],
            }
        )
    )
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("toolset", nargs="?", default="terminal")
    ap.add_argument(
        "--profiles-dir", default=os.path.expanduser("~/.hermes/profiles")
    )
    ap.add_argument("--src", default=os.path.expanduser("~/.hermes/hermes-agent"))
    # child-mode plumbing (not for human use)
    ap.add_argument("--_effective-one", dest="one", action="store_true")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--home", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    if args.one:
        return _resolve_one(args)

    hermes_root = os.path.expanduser("~/.hermes")
    root_cfg = os.path.join(hermes_root, "config.yaml")

    targets = []
    if os.path.isfile(root_cfg):
        targets.append(("default", hermes_root, root_cfg))
    for cfg in sorted(glob.glob(os.path.join(args.profiles_dir, "*", "config.yaml"))):
        home = os.path.dirname(cfg)
        targets.append((os.path.basename(home), home, cfg))

    if not targets:
        print("no configs found under %s or %s" % (args.profiles_dir, root_cfg))
        return 2

    print(
        "toolset: %s   profiles: %d   src: %s\n"
        % (args.toolset, len(targets), args.src)
    )

    bad = []
    for name, home, cfg in targets:
        cmd = [
            sys.executable,
            os.path.abspath(__file__),
            args.toolset,
            "--_effective-one",
            "--src",
            args.src,
            "--profile",
            name,
            "--home",
            home,
            "--config",
            cfg,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        line = next(
            (l for l in proc.stdout.splitlines() if l.startswith("RESULT ")), None
        )
        if line is None:
            tail = (proc.stderr.strip().splitlines() or ["?"])[-1]
            print("%-18s RESOLVE FAILED (%s)" % (name, tail))
            bad.append(name)
            continue

        data = json.loads(line[len("RESULT ") :])
        off = data["off"]
        print(
            "%-18s %s"
            % (name, "OK everywhere" if not off else "OFF: " + ", ".join(off))
        )
        if data["disabled"]:
            print(
                "%-18s   declared agent.disabled_toolsets: %s"
                % ("", ", ".join(data["disabled"]))
            )
        for warn in proc.stderr.splitlines():
            if "no valid toolsets" in warn:
                print("%-18s   ⚠ %s" % ("", warn.strip()))
        if off:
            bad.append(name)

    print()
    if bad:
        print("MISSING %s: %s" % (args.toolset, ", ".join(bad)))
        print(
            "Fix (clears the global block AND writes the platform list, "
            "all surfaces at once):"
        )
        print(
            "  HERMES_HOME=~/.hermes/profiles/<name> "
            "hermes tools enable %s --platform cli" % args.toolset
        )
        return 1

    print("every profile resolves %s on every surface" % args.toolset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
