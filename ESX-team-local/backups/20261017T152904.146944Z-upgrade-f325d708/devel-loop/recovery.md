# Evidence handoff and recovery

The dispatcher prepares one candidate packet for review and then updates its exact
completion selections for final verification. Human judgments remain explicit.
Readiness checks perform no agent dispatch, scientific execution, issue closure,
or modification of a stored packet.

## Ordered handoff

1. Bob finishes the bounded implementation and focused regression checks. Retain
   failed attempts and the successful continuation under the same session ID.
2. Complete source comments, docstrings, owning documents and the code map. Use
   `doc_contract.py draft --previous` to retain judgments whose measured source,
   enclosing context and documentation dependencies remain unchanged. Inspect
   every pending disposition and seal the report. Preserve the original baseline.
3. Refresh Arch's orientation if its dependency slice changed. Capture the
   candidate after source and documentation are stable.
4. Build a packet at stage `review`. It supplies the exact candidate, sealed report,
   baseline, map disposition, Arch orientation, implementation events and brief.
   Richard's approval is obtained after this stage.
5. Dispatch each required independent Richard with `--review-packet`. Supply a
   different review question to each reviewer. Resume the same identities for
   corrections. A correction requires a refreshed candidate/report and packet.
6. Build the final packet from explicit completion events. Run stage `final`
   readiness, resolve findings, then let the assigned owner run final verification.
7. Complete the remaining closeout decisions using the measured final receipt.
   Issue outcome, scope, git, lessons and communication decisions remain Arch's
   responsibility under the project's closeout contract.

## Build and inspect a packet

The reference input files contain the exact `{ "path": "...", "sha256": "..." }`
objects returned by the candidate, documentation and navigation tools. The brief
input contains `outcome`, `constraints` and `acceptance_tests`. Those fields state
the agreed behavior, preserved invariants and executable acceptance criteria.
A previous packet can be supplied with `--prior` to retain exact historical events.

Run `selections` first, every time — before hand-searching `dispatch_log.jsonl`
or re-dispatching a role "to be safe." A real, already-completed review that
is not selected from this inventory is not corrected later; it is discarded,
and its work (including any independent check it already ran) must be redone
from scratch under a new identity.

```bash
python3 tools/esx/workflow_records.py selections > /tmp/available-events.json
# Select explicit event IDs from this inventory and save /tmp/selected-events.json.
python3 tools/esx/workflow_records.py review-packet \
  --select /tmp/selected-events.json \
  --candidate /tmp/candidate-ref.json \
  --documentation /tmp/documentation-ref.json \
  --orientation /tmp/arch-orientation-ref.json \
  --handoff /tmp/brief.json --stage review \
  --output devel-loop/loop_state/review-candidate-001.json
python3 tools/esx/workflow_records.py readiness \
  --review devel-loop/loop_state/review-candidate-001.json \
  --stage final --owner arch --format text
```

Repeat `review-packet` with `--stage final`, the required reviewer events, and a
new output filename after review. The builder validates twice before atomic
publication. Every consumer revalidates source freshness. An existing packet is
immutable; a changed candidate receives a new packet. `closeout_pending` carries
administrative questions separately from readiness prerequisites.

Read-only CLI inputs accept absolute paths such as `/tmp/selected-events.json`.
Relative input paths resolve against `--root`. Stored evidence references and
outputs remain project-relative and reject traversal, protected active records
and symlink paths. A review packet must be written beneath `devel-loop/loop_state`.

`selections` is an inventory for explicit selection. It never chooses a successful
review by timestamp. `selection_scope: "history"` imports an older event with
its original identity and round. Failed/incomplete attempts retain measured
status, error, timing and process return code. They supply no approval, independent
check or successful test. Running attempts keep readiness blocked. The final
validators require the failed attempt's successful continuation or explicit
replacement disposition and reject a later failed review that would otherwise
expose an older approval. A later completed turn of the same retained agent is
its continuation, whether it was resumed in the same correction round (a turn
limit, a stale orientation) or a later one. A turn closed by `agent_runtime.py
recover` has no correction round; select it with `correction_round: null`.
Reference arguments (`--baseline`, `--candidate`, `--before`, `--previous`) take
the JSON reference inline or the path of a file holding it. A stale candidate
names the added, removed and changed paths; a new file inside the inventory
scope, such as a project record, invalidates the reviewed candidate too.

## Readiness diagnostics

`readiness --format json` returns `status`, `stage` and `findings`. Each finding has
`code`, `field`, `observed`, `recovery`, `status`, `agent` and
`dispatch_event_id`. Text output renders the same findings. Candidate, report,
orientation, brief and completion failures are collected independently. Final
approval checks remain pending while their prerequisites are invalid.

A stale orientation reports the receipt, every changed target, old/new hashes and
whether the source, module context, enclosing definition or documentation changed.
The named reviewer reads that delta, records its own orientation, reruns the
check affected by the change and returns a fresh footer. Arch cannot create a
reviewer's orientation or approval. An unrelated function change preserves a
symbol's orientation when its recorded dependencies remain identical. Dependency
lists remain a human responsibility; a static source map cannot infer every
scientific dependency.

When a commissioned edit changed only references the stale orientation already
declared as targets or documents, refresh it without retyping the arguments:
`doc_contract.py navigate --issue <id> --reuse-args <receipt> --use '<fresh
explanation>'`. The receipt is the prior orientation's JSON reference or digest.
The command reloads its role, baseline, map, targets and documents and prints the
current excerpt of every one. It refuses a missing `--use` or one that repeats the
original. It also refuses when the map heading changed or a reference no longer
resolves: the slice moved beyond what was read, so run full `navigate`. No hash
or other value echoed by the refusal clears a stale orientation.

## Resume after configuration changes

Runtime contracts retain the raw fingerprint and a sanitized effective manifest.
Settings values are hashed, so the evidence does not expose credentials. Equivalent
JSON formatting permits continuation under the same session ID. Semantic changes
require an explicit assessed transition. This includes permissions, hooks,
plugins, instructions, tools, executable and relevant environment changes.
Unknown legacy contracts require an explicit replacement because the saved hash
cannot establish the semantic delta.

For a measured semantic change, Arch first runs an appropriate isolated compatibility
check. Record a project-relative log reference and its SHA-256. The judgment JSON
contains:

```json
{
  "assessor": "arch",
  "decision": "resume",
  "reason": "Describe the actual changed fields, their consequences and why continuation preserves the role contract.",
  "check": {
    "command": "the actual compatibility check command",
    "executed": true,
    "exit": 0,
    "evidence": {"path": "devel-loop/loop_state/compatibility.log", "sha256": "the measured log hash"}
  }
}
```

```bash
python3 tools/esx/agent_runtime.py assess-transition \
  --session SESSION_UUID --judgment /tmp/transition-judgment.json \
  > /tmp/transition-ref.json
python3 tools/esx/agent_runtime.py followup --session SESSION_UUID \
  --correction-round 1 --transition /tmp/transition-ref.json \
  --review-packet devel-loop/loop_state/review-candidate-001.json \
  --prompt-file /tmp/correction.txt
```

The sealed assessment binds the issue, session, old/new fingerprints and exact
measured delta. Further drift requires a fresh assessment. The transition context
is supplied on the retained turn; changed role/tool settings are passed in the
invocation. Confirm changed instruction behavior with a bounded live witness when
that behavior is material to the transition. Successful process exit alone cannot
establish that changed scientific instructions were understood. A plugin with a
`PermissionRequest` hook must receive explicit review of its authorization effect.

## Diagnose hook and dispatch failures

```bash
python3 tools/esx/agent_runtime.py hook-doctor
python3 tools/esx/agent_runtime.py hook-doctor --event EXACT_DISPATCH_EVENT
python3 tools/esx/workflow_records.py timings --issue ISSUE_ID
```

The doctor inventories user/project/local settings and installed plugin hooks.
It reports source, scope, event, executable and command hash without running any
hook. An exact dispatch adds measured process status, signal information and
stderr metadata. Installed-plugin presence does not prove activation. Match the
actual CLI diagnostic to establish which hook failed. Empty stderr cannot establish
the cause of a killed executable; inspect its OS crash report when necessary.

A preflight refusal is recorded in `runtime-preflight.jsonl` separately from
`dispatch_log.jsonl`; it grants no role completion and consumes no correction
round. If the evidence directory itself is unsafe or inaccessible, the original
refusal is returned without attempting an alternate evidence location. Timing
reports separate configuration recovery and packet repair from captured role
turns. Unmeasured orchestration time remains unmeasured; overlapping turns are
accounted for with the existing interval-union calculation.

## Reuse execution with fresh acceptance

Session compatibility, orientation freshness, reviewer approval, suite execution
and final acceptance have separate validity checks. Refreshed review or
documentation evidence requires current approval and a fresh acceptance receipt.
The final wrapper can reference an unchanged successful scientific execution when
its issue, owner, measured source/tests/configuration/toolchain dependencies and
intact log still agree. It records **reused evidence** and retains the original
execution receipt. Changed numerical dependencies, invalid logs or unresolved
correctness findings prevent reuse. No agent edits a stored receipt to refresh it.
A receipt taken from the review packet never matches the finished closeout,
because the packet lacks the closeout fields that `review_signature` covers
(`scope_decisions`, `agent_continuity` and the others). After filling
issue-done.json, run `loop_lifecycle.py rebind-receipt`: it issues a receipt for
the closeout from the unchanged execution, without running the suite, and cites
it in `verification.receipt` ([verification](verification.md)). It refuses when
the execution can no longer be reused; a fresh `final_verification.py run` is
then required. The closeout draft's `preparation.shapes` lists the expected form
of each judged field; delete the `preparation` object before rebinding.

## Process ledgers and budget exhaustion

For a pending ledger journal, run `python3 tools/esx/self_improvement.py recover`
(or `recover --rollback`) before other acceptance work. A changed original is
never overwritten. Unknown cost retains its reservation. Do not delete budget
ledgers or reset timestamps to resume. Use the existing Owner-authorized extension
interface described in [bounded operations](team_operations.md). A stopped loop
retains retrospective debt for completion before the next issue.

## Repeated stops and provider limits

A native agent can stop more than once at the end of one turn: once with its
report, and again when background work it started finishes. The second stop
repeats the same footer. It is recorded with `duplicate_of: <event id>` and kept
in the dispatch log, but it is not a new completion: `selections` lists it with
`selection_scope: "duplicate"`, a packet cannot select it, and it never replaces
the original as the reviewer's latest completion. A packet built from the
original therefore stays valid.

A retained turn the provider refuses for a usage or rate limit is recorded as
failed with a `provider_limit` object (`limit_type`, and `reset_at` in UTC when
the provider gave one). It did no work. `--next` prints `LIMIT:` with the pause
command to run. After the reset, resume the same session; select the failed turn
and its completed continuation together when building the packet.
