# w_ai — Hermes profile distribution

Generated 2026-11-16T15:57:11+03:30 from /home/siavash/.hermes/profiles/w_ai by to-profile-dist.sh.

Install on any machine:
    hermes profile install <this-repo-git-url>
    cp ~/.hermes/profiles/w_ai/.env.EXAMPLE ~/.hermes/profiles/w_ai/.env   # fill keys, chmod 600
    hermes -p w_ai chat -Q -q "reply with exactly: PROFILE-OK"

Iterate: edit the files here, bump version in distribution.yaml, push; then on each machine:
    hermes profile update w_ai
User data (memories, sessions, .env, auth) is never overwritten by updates;
config.yaml is preserved unless --force-config.
