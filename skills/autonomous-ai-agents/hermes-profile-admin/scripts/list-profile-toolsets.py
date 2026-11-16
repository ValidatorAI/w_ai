#!/usr/bin/env python3
"""List a profile's toolsets as `name,active` rows.

Answers "list the N toolsets I have and which are active" / "make me a CSV".
Two modes:

  * offline (default): mirrors hermes_cli/web_routers/tools.py::get_toolsets
    using the real resolvers, per profile, with HERMES_HOME pinned so plugin
    toolsets and credential-gated auto-enables read THAT profile's home.
  * --url/--token: reads the live dashboard API
    (`GET /api/tools/toolsets?profile=NAME`), which is the better source when
    the dashboard is running because it also includes plugin toolsets that only
    the dashboard process discovers (here: `a2a`). Expect the live call to
    return one row MORE than the offline run in that case; check
    discover_plugins() scope before calling the delta a bug.

The dashboard token is embedded in the dashboard HTML:
  curl -s http://127.0.0.1:9119/ | grep -o '__HERMES_SESSION_TOKEN__="[^"]*"'

Usage:
  python3 list-profile-toolsets.py [--profile NAME] [--csv OUT]
  python3 list-profile-toolsets.py --url http://127.0.0.1:9119 --token TOK --profile default

`--profile default` reads the root ~/.hermes config; any other name reads
~/.hermes/profiles/<name>. Exit code is always 0 unless the read itself failed.

Detail on why four surfaces return 24/25/27/28 rows for one profile:
references/toolset-enumeration-surfaces.md
"""

import argparse
import csv
import json
import os
import sys


def _home_for(profile):
    if profile in ("default", ""):
        return os.path.expanduser("~/.hermes")
    return os.path.expanduser(os.path.join("~/.hermes/profiles", profile))


def rows_offline(profile, src):
    """Resolve rows exactly like the dashboard handler does, no server needed."""
    os.environ["HERMES_HOME"] = _home_for(profile)
    sys.path.insert(0, src)

    from hermes_cli.config import load_config
    from hermes_cli.tools_config import (
        _CONFIG_ONLY_TOOLSETS,
        _get_effective_configurable_toolsets,
        _get_platform_tools,
        _toolset_configuration_platform,
    )

    cfg = load_config()
    enabled_by_platform = {}
    rows = []
    for name, _label, _desc in _get_effective_configurable_toolsets():
        if name in _CONFIG_ONLY_TOOLSETS:
            # Config-only capabilities (stt) switch on their own config section,
            # not on platform_toolsets -- the handler reads it the same way.
            section = cfg.get(name)
            section = section if isinstance(section, dict) else {}
            enabled = bool(section.get("enabled", True))
        else:
            plat = _toolset_configuration_platform(name)
            if plat not in enabled_by_platform:
                enabled_by_platform[plat] = _get_platform_tools(
                    cfg, plat, include_default_mcp_servers=False
                )
            enabled = name in enabled_by_platform[plat]
        rows.append((name, bool(enabled)))
    return rows


def rows_api(url, token, profile):
    import urllib.request

    req = urllib.request.Request(
        "%s/api/tools/toolsets?profile=%s" % (url.rstrip("/"), profile),
        headers={"X-Hermes-Session-Token": token or ""},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    # `available` is set equal to `enabled` by the handler; `enabled` is the toggle.
    return [(t["name"], bool(t["enabled"])) for t in data]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", default="default")
    ap.add_argument("--csv", default=None, help="also write the rows to this path")
    ap.add_argument("--url", default=None, help="dashboard base URL (live mode)")
    ap.add_argument("--token", default=None, help="dashboard session token")
    ap.add_argument(
        "--src",
        default=os.path.expanduser("~/.hermes/hermes-agent"),
        help="hermes install to import for offline mode",
    )
    args = ap.parse_args()

    if args.url:
        rows = rows_api(args.url, args.token, args.profile)
    else:
        rows = rows_offline(args.profile, args.src)

    pairs = [(n, "active" if e else "inactive") for n, e in rows]
    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["name", "active"])
            w.writerows(pairs)

    print("name,active")
    for name, state in pairs:
        print("%s,%s" % (name, state))

    active = sum(1 for _, e in rows if e)
    print(
        "\n# profile=%s  toolsets=%d  active=%d  inactive=%d  (MCP servers excluded)"
        % (args.profile, len(rows), active, len(rows) - active),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
