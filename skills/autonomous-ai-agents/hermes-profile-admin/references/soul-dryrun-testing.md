# Dry-Run SOUL Behaviour Testing

Test a profile's SOUL workflow instructions against scripted messages WITHOUT
side effects: the profile must output only the steps it would take and the exact
tool calls it would have issued. Use when the user asks to "run the tests
against the profile" or "show what it would do, not actually using the MCP
tools".

## 1. Test-file shape
Author one markdown file with 3-5 tests. Each test carries three parts, and the
file carries a shared instruction block:

- **Shared dry-run instruction** (pasted with every test): "DRY RUN: do not call
  any MCP tool, do not write anything. Output: ordered steps per the canonical
  workflow; for each step the exact tool call with all arguments, or 'no call'
  with the reason; where the workflow stops early, name the rule that caused
  the stop."
- **Message payload** (JSON: project/room/sender ids and message content) PLUS
  **hypothetical tool data** — what the reads (`message_analysis` by message_id,
  `search_topics`, etc.) return. Without stipulated returns the plan is not
  deterministic and the model is invited to invent data.
- **Expected checklist** — one box per SOUL rule the test exercises (cite the
  rule text so scoring maps back to the SOUL), plus a global scoring note and
  one automatic-fail condition (e.g. "create when a prior record exists =
  automatic fail").

Good tests target the SOUL's *decision points*, not its happy path: the
dedupe/update guard, the stop-threshold, reactivate-vs-create, child-topic
creation limits, and any exception path in the thresholds table. A multi-part
test (two messages) that fires both the normal stop and the exception is worth
more than two singletons.

## 2. Guard — make writes structurally impossible
Do not trust a small model to honour "don't call tools". Temporarily disable the
profile's MCP server so no call can reach the live backend:

```python
# back up, then splice 'enabled: false' right after the server-name line
import shutil
p = f"{home}/.hermes/profiles/{name}/config.yaml"
shutil.copy(p, p + ".pretest.bak")
lines = open(p).read().split("\n")
out = []
for l in lines:
    out.append(l)
    if l == f"  {server}:":
        out.append("    enabled: false")
open(p, "w").write("\n".join(out))
```

`enabled: false` is honoured at MCP discovery, which is per-process for
one-shot CLI runs — no gateway restart needed. Restore from the backup after the
suite and re-check with `grep -A2 '{server}:'`. Do not panic if
`grep -c 'enabled: false'` returns 1 after restore: unrelated keys (e.g. `stt:`)
legitimately carry that line; verify the SERVER block specifically.

## 3. Run the suite
```bash
for i in 1 2 3 4 5; do
  hermes -p NAME chat --query-file test$i.md --oneshot > out$i.txt 2>err$i.txt
done
```

- `--query-file`, never `-q`: prompts embed JSON payloads with quotes and
  backticks.
- Each run is a fresh session; run sequentially (shared profile state.db).
- A fast (<5 s) `exit=1` is almost always the missing provider key in the
  profile's own `.env` — see the SKILL.md pitfall "A profile NOT created by
  `--clone`" before debugging anything else.
- Expect ~1-3 min per test on a small model; keep the loop in one background
  command and `process_manage wait` it.

## 4. Extract the reply
The console echoes the prompt, then the answer arrives in a box panel:

```python
import re
lines = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", open(f"out{i}.txt").read()).split("\n")
s = next(j for j, l in enumerate(lines) if l.startswith("\u256d"))
e = next(j for j, l in enumerate(lines) if l.startswith("\u2570"))
resp = "\n".join(re.sub(r"^\s*[\u2502\u2503]\s?(.*)$", r"\1", l).rstrip() for l in lines[s+1:e])
```

Also parse the footer `Messages: N (1 user, K tool calls)` — assert **K = 0 for
every run**; that is the dry-run compliance proof, stronger than any prose
claim.

When splitting the test md into per-test prompt files, slice by heading line
indexes — do NOT use one greedy `.*` capture group with `re.S` to grab "the
blockquote lines" (it swallows the whole rest of the file; every test got a
10 KB paste of all five). Verify each built prompt contains exactly one
`## Test` heading before launching.

## 5. Score — the negation trap
A passing answer mentions every tool it REFUSES ("`create_message_analysis` is
forbidden here", "Tool call NOT issued: `create_topic` — reason ..."). Keyword
presence would fail the best runs. Scoring procedure:

1. Assert 0 tool calls per run (footer).
2. Run the mechanical checks (update-vs-create, explicit enum values, merged
   string contains the existing item, id pairing like room_id+topic_id).
3. For EVERY apparent violation, extract ±150 chars of context and read
   whether it is a call or an explicit refusal. Most "failures" dissolve here.
4. Check argument VALUES inside the matched call's block (e.g. the merged
   `required_actions` appears in the `update_topic { ... }` args), not merely
   anywhere in the response — stipulated data is echoed too.
5. Strong runs self-audit against the checklist; use their summary as a
   cross-check of your mechanical score, never as the score itself.

## 6. Deliver
Reply with the per-test PASS/FAIL table, the notable beyond-spec behaviours
(read-before-write of merged fields, refusal to call tools whose return was not
stipulated, justified extra links), and the saved response paths
(`resp1.txt ... respN.txt`). Scratch dirs are pruned after 24 h — tell the user
to copy responses to a permanent path if they should become regression
baselines, or copy them there yourself when asked.
