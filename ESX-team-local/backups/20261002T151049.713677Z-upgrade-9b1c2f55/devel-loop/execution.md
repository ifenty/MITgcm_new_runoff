# Retained agents and execution evidence

## Qualify the runtime

The project needs the Claude CLI available as `claude`, authenticated through the
owner's normal installation, with the configured role tools permitted. Models
inherit the runtime configuration unless a role explicitly pins one. Run:

```sh
python3 tools/esx/check_ralph_hook.py
python3 tools/esx/agent_runtime.py probe
python3 tools/esx/agent_runtime.py probe-status
```

The probe performs two real tools-disabled turns and checks remembered context
under the same session identity. Its receipt is reusable for the measured CLI,
settings, roles, common skill and runtime-helper fingerprint. It establishes
continuity; role tool permissions and peer communication need a bounded actual
role task. The kit's tests/live_runtime.py provides an opt-in scratch check
with a --resume-root option after an interrupted attempt. Offline tests do not establish provider availability. Qualify a
changed configuration once, and investigate a real dispatch failure directly.

## Assign, resume and communicate

Keep prompts under devel-loop/loop_state. Include the issue ID, original baseline,
iteration timestamp, scope, measured facts, acceptance, role question and allowed
resources. Every agent supplies its own source/map orientation. Start a role:

```sh
python3 tools/esx/agent_runtime.py start --role bob --issue PROJECT-001 \
  --prompt-file devel-loop/loop_state/bob-brief.txt --correction-round 0
```

The adapter supplies measured agent/session identity, issue, iteration, correction
round and baseline in the role’s dispatcher context. Use that agent_id as the
verification owner. Retain returned session_id, agent_id and dispatch_event_id. Use that session
for corrections, and relay Richard's precise findings through a prompt file:

```sh
python3 tools/esx/agent_runtime.py followup --session BOB_SESSION \
  --prompt-file devel-loop/loop_state/correction.txt --correction-round 1
```

A peer can send bounded issue-scoped evidence to another retained session:

```sh
python3 tools/esx/agent_runtime.py message --from-session SENDER_SESSION \
  --session RECIPIENT_SESSION --prompt-file devel-loop/loop_state/finding.txt \
  --correction-round 1
```

The receiver resumes and its answer is recorded. These calls wait for a turn;
concurrent turns on one recipient serialize. Budget a waiting caller for its own
work plus the receiver’s configured timeout. The receiver returns its answer in
the current response; starting a synchronous callback into the waiting sender
would contend for that sender’s active turn lock. Start distinct sessions for independent
parallel work. Cross-issue routing is rejected. Peer messages carry source identity
and scope; they convey evidence and questions without expanding authorization.
Arch receives decisions and changes of premise. Richard's first review has its
own context and independently selected check. Corrections retain both agents.

The adapter uses declared built-in role tools, preserves permission configuration,
retains project hooks and disables child loop advancement. It saves full stdout,
stderr, original structured footers, timing and status. Process failure, timeout,
interruption and missing footers remain failed/incomplete evidence. Resume after
investigation; never relabel these events as successful. A replacement needs its
actual predecessor ID, reason and transferred findings. Runtime history supports
recovery without requiring another agent to reconstruct prior conversations.

For an active issue, Richard's initial and corrected reviews require the exact
candidate and sealed documentation packet. Build it using `workflow_records.py
review-packet`, then dispatch with `--review-packet`:

```sh
python3 tools/esx/agent_runtime.py start --role richard --issue PROJECT-001 \
  --prompt-file devel-loop/loop_state/richard-brief.txt --correction-round 0 \
  --review-packet devel-loop/loop_state/review-candidate-001.json
```

The adapter revalidates saved references on every continuation. Supply a new
packet when the candidate or its documentation changes.

## Candidate and closeout records

Capture exact candidate bytes before review, including any explicit witness inputs:

```sh
python3 tools/esx/issue_candidates.py capture --issue PROJECT-001 --baseline "$esx_doc_base"
```

The returned reference identifies a content-addressed snapshot with file bytes,
paths, modes and internal symlink targets. Configured untracked source is included.
Use `check`, `diff` and `extract --help` to validate, compare or reconstruct snapshots
in an empty scratch directory. Git HEAD alone cannot identify a dirty candidate.
A candidate binds the original maintenance baseline; retain it in the review
packet's `candidate` field. Science datasets outside inventory need explicit
configured input provenance and their own scientific qualification.

**First, list every dispatch already recorded for this issue** — do not hand-search
`dispatch_log.jsonl`, which risks missing a real, already-completed review and
redispatching a fresh identity to redo work that already exists:

```sh
python3 tools/esx/workflow_records.py selections --start devel-loop/loop_state/issue-start.json
```

Build the selection JSON file from that output's exact `agent`, `dispatch_id`,
`dispatch_event_id` and `correction_round` fields — for example:

```json
[{"agent":"bob","dispatch_id":"ACTUAL_ID","dispatch_event_id":"ACTUAL_EVENT","correction_round":0}]
```

```sh
python3 tools/esx/workflow_records.py prepare-done \
  --select devel-loop/loop_state/selections.json \
  --output devel-loop/loop_state/review-draft.json
python3 tools/esx/workflow_records.py continuation
python3 tools/esx/workflow_records.py timings --issue PROJECT-001
```

Import helpers copy the captured fields and leave acceptance judgments pending.
Fill every listed pending item, remove `preparation.pending` only once addressed,
and pass the resulting packet through the ordinary gates. Preceding iteration
evidence is retained through --prior; when it is omitted, prepare-done uses the
issue's latest accepted closeout in loop_state/closed/ (same baseline) and names it
in `preparation.prior` (`--no-prior` opts out). Preserve failed turns honestly; they
remain historical and need a qualifying successful recovery before completion. For
each unresolved failed identity the draft carries an `agent_continuity.replacements`
entry with role, old_id and (when unambiguous) new_id prefilled and `reason` and
`evidence_refs` empty: the gates refuse it until Arch supplies both. Never resolve a
failed reviewer by marking it `waived`; that erases a review that did not happen. Never edit a footer
hash to manufacture an approval. The start timestamp remains the iteration identity.

For a milestone, `workflow_records.py milestone --heading 'Exact heading'` returns
a hash of the precise section in current_status.md. Appending unrelated sections
preserves the reference. Use the diagnosis JSON template for two failed corrections:
it records the observed rounds, reproduction result, hashed evidence, mistaken or
unproven premise, and revise_design/split_scope/gather_evidence decision.

Timing summaries add per-role work and take the union of overlapping intervals
for observed elapsed time. Missing starts remain unmeasured. Include verification
and orchestration delays separately when evaluating actual issue throughput.

## Packet preparation and recovery

Follow [Evidence handoff and recovery](recovery.md) for explicit packet assembly,
readiness diagnostics, failed-attempt history, assessed session transitions and
reuse of a measured scientific execution with fresh acceptance.

## Shared limits and generated briefs

[Bounded operations](team_operations.md) supplies the metered coordinator, shared
run/issue/turn budgets, generated role briefs, typed handoffs and continuation
receipts. Run structural verification before paid review. Use `brief.py` with the
actual design and review question. CLI status is completed only after early footer
validation; incomplete reports remain explicit and use retained correction turns.
