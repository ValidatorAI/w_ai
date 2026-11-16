---
name: bash-script-authoring
description: "Author/verify bash scripts: parsing, prompts, exit codes."
version: 1.0.0
license: MIT
author: Hermes Agent
metadata:
  hermes:
    tags: [bash, shell, scripting, cli, verification]
    related_skills: [systematic-debugging, test-driven-development]
---

# Bash Script Authoring & Verification

## When to Use

Writing or debugging a non-trivial `.sh`: one that parses structured files (YAML-ish manifests, key=value files), prompts users interactively, fetches git repos, or merges output into an existing file. Skip for one-liners.

The traps below each cost a real debug round; they are silent — `bash -n` and shellcheck both pass on them. Apply while writing, not after.

## Record parsing traps

- **Never use TAB (or space) as a field separator for records with possibly-empty fields.** TAB is IFS whitespace, so `IFS=$'\t' read -r a b c d e` COLLAPSES consecutive delimiters and silently shifts columns (a trailing field lands in an earlier variable). Use the unit separator: `US=$(printf '\037')`, emit rows with awk `BEGIN{U=sprintf("%c",31)}`, read with `IFS="$US"`. If a column is empty, the shifted-value bug appears only in the empty-field cases — the worst kind.
- **awk `printf "%s%s..."` with a literal after the last `%s` eats the delimiter** ("...%s\037skills" vs "...%s\037\037skills" for an empty field). Build rows with `print f1 U f2 U f3 U U "src"` concatenation instead of counting `%s` specifiers.
- For "parse YAML-ish blocks in bash", write an awk block-state machine (enter on `^key:$`, leave on any top-level line), and remember nested keys can be indented — strip leading whitespace before matching a bare `key:` that switches block state.

## Interactive-prompt traps

- **A prompt loop inside `while read; done < datafile` steals stdin: the inner `read` consumes DATA ROWS as user answers.** Keep the data on another FD — `while read -u3 ...; done 3< "$SORTED"` — so stdin stays free for `read -p`. This corrupts answers silently in exactly the mixed prompt/read case.
- **Make every read EOF-safe or piped input hangs the script in a re-prompt loop:** `IFS= read -r -p "..." val || rc=$?` then treat `rc!=0` as empty; a confirm-with-skip should pre-default to the skip answer (`ans="y"; read ans || true`). `read ... || continue` is the hang.
- Hide secret-shaped answers: `read -rs` for names matching `*KEY|*TOKEN|*SECRET|*PASSWORD|*CREDENTIAL*`, and print a bare `echo` after (no newline on `-s`).
- When merging collected values into an existing key=value file (like a `.env`), default to PRESERVE and require an explicit `--overwrite` to re-ask a key; rewrite by copying all lines except the re-asked keys, then append.

## Exit-code / control traps

- **Under `set -e`, a trailing `[ cond ] && cmd` as the last statement exits 1 when the condition is false** even though the script succeeded. End scripts with `if ...; fi` or an explicit `exit 0`. The same shape mid-script is fine (it is a &&-list) — the bug is only for the FINAL command, where it becomes the script's status.
- Anything after `exec` never runs — `exec` replaces the process. Two `exec` lines is dead code, not failover.
- `[ -d "$arg" ] ||` local-directory acceptance before the git-clone path saves a confusing `git clone` failure on the most common dev input.

## Verification sequence (run before claiming the script works)

1. `bash -n` syntax gate.
2. Build a fixture tree covering every parse branch (present + absent sources, empty fields, nested blocks) and run a `--dry-run`/report path first.
3. Pipe answers for the interactive path: `printf 'a\nb\n' | timeout 20 bash script.sh ...` — `timeout` catches the EOF-hang class; assert the OUTPUT FILE content line-by-line (preserve/merge/overwrite), not just exit 0.
4. Exercise the real fetch path with a `file://` git clone (init a fixture repo) — clone vs local-dir code paths differ.
5. Feed an EARLY-EOF input stream (fewer answers than prompts): must exit 0 with partial results, not hang or loop.
6. `shellcheck -S warning` last — it flags unused variables that reveal feature gaps (e.g. a parsed-but-unused column that should appear in the prompt).
