# Open ESX-team Issues

This ledger tracks unresolved ESX-team effectiveness and process issues. These entries
are separate from ESX transformation issues and are not selected by `loop_gate.py --next`.

## Template for New Entries

```markdown
## 🔴 PROPOSED: [Brief title]

**Date Identified**: YYYY-MM-DD  HH:MM
**Status**: Proposed | Investigating | Implementing | Implemented — awaiting publication/effectiveness evidence | Blocked
**UUID**: TEAM-AREA-SHORT-NAME-001
**Category**: stable_lowercase_category
**Severity**: Critical | High | Medium | Low
**Assessment**: devel-loop/self-improvement/assessments/YYYY-MM-DD-name/assessment.md
**Anchors**: path[:symbol|:line]; ...
**Implementation-Reference**: path or WORKTREE (required after implementation)
**Blocked-By**: UUID | EXTERNAL | OWNER-DECISION (required only when blocked)

### Issue
[Measured inefficiency or procedural defect.]

### Evidence
[Retained observations, commands, records, timings, or costs.]

### Potential Impact
[Consequence for correctness, cost, time, or evidence integrity.]

### Proposed Fix
[Specific structural or procedural correction.]

### Acceptance Criteria
[Executable checks and required output.]

### Expected Effect
[Metric and expected direction, or a precise qualitative invariant.]
```

## 🔴 PROPOSED: Manual claude runs in the project directory can hijack the ESX loop

**Date Identified**: 2026-09-30  05:39
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-LOOP-FOREIGN-STOP-001
**Category**: loop_stop_hook_isolation
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-30-runoff-001/assessment.md
**Anchors**: tools/esx/ralph_stop.py; tools/esx/loop_control.py; .claude/settings.json
**Implementation-Reference**: ESX-Team 03c7b76 (1.5.8), deployed in project commit 0c3546d

### Issue
The project Stop hook runs for every Claude process started in the project directory, not only the Arch session that owns the loop. A manual `claude --print` witness run received the loop continuation prompt, advanced five iterations and emitted the completion promise, which ended the loop mid-issue.

### Evidence
.claude/esx-loop-exit.log: CONTINUE iterations 2-6 between 05:38:14 and 05:39:18Z, then "END iteration=6 current completion promise fulfilled". The run's output was "I'm ready—just need that bootstrap input from the loop system".

### Potential Impact
Lost loop budget, and a false completion announcement queued (event 1924385e…). A child could also mark work complete.

### Proposed Fix
ralph_stop.py records the owning session_id when the loop starts and ignores Stop events from any other session. Until then, run manual CLI witnesses outside the project directory or with `--settings` that disables hooks.

### Acceptance Criteria
A Stop event from a different session_id leaves the loop state and iteration count unchanged. A test covers it.

### Expected Effect
No loop advancement or termination from sessions other than the loop owner.

## 🔴 PROPOSED: Kit defects reachable only under live role dispatch

**Date Identified**: 2026-09-29  22:05
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-KIT-LIVE-DISPATCH-001
**Category**: esx_kit_live_dispatch_defects
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-30-runoff-001/assessment.md
**Anchors**: tools/esx/runtime_tool_hook.py; tools/esx/agent_runtime.py; tools/esx/permission_match.py
**Implementation-Reference**: ESX-Team upstream commits 8c7ea7d (1.5.1), c92ebe4 (1.5.2), 9518877 (1.5.5), 6566f6e (1.5.6); deployed in project commits 0e0e80c..4ed42ec

### Issue
Four defects in the kit were invisible to the tools-disabled probe and blocked role dispatch:
- the Bash permission rewrite (ESX-002);
- the crash on string message events (ESX-001);
- provider overshoot recorded as a failed turn;
- an assignment argv above 131,072 bytes (E2BIG).

### Evidence
Bob session a7e61b17 turns 8154aebc and 3cc0d65c; failed turns 1b67af36 and 00359eaf ($13.32 and $14.16 against a $12 reservation); Richard launches a7cd0097 and 606c4b7f failed with E2BIG.

### Potential Impact
Every scientific review is blocked or discarded; a replacement Bob was needed.

### Proposed Fix
The upstream fixes are now deployed. The live permission probe runs after every upgrade (lesson LL-002).

### Acceptance Criteria
The live probe passes after upgrade. The next issue's role dispatches complete with no permission, overshoot or argv failures.

### Expected Effect
Zero dispatch failures caused by the kit in the next iteration.

## 🔴 PROPOSED: Documentation disposition reasons drift across correction rounds

**Date Identified**: 2026-09-30  04:50
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DOC-DISPOSITION-DRIFT-001
**Category**: documentation_disposition_drift
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-30-runoff-001/assessment.md
**Anchors**: tools/esx/doc_contract.py; devel-loop/documentation_contract.md
**Implementation-Reference**: ESX-Team 1.6.0 (branch esx-1.6.0 commits 61fcc38, 5858e28): draft --previous carries forward updated/removed code judgments bound to their file; implementer-owned plan in the brief rules; deployed in project commit b2718fb

### Issue
When the documentation plan is redrafted each correction round, Arch fills it from reusable templates. The reasons then go stale as the change grows; for RUNOFF-001 they still said 44 rules when there were 46, and still said "round 1".

### Evidence
RUNOFF-001 round-2 must-fix lists from both Richards. Reproducer devel-loop/loop_state/diag_docstring_rules.py exited 1.

### Potential Impact
A whole review round spent on documentation accuracy alone.

### Proposed Fix
Have doc_contract.py draft pre-fill each target's current docstring first line (and, where a project defines one, the rule ids a symbol emits) as a reference hint, so reasons start from the live source. Keep the per-project docstring/rule test (tests/runoff/test_docstring_rules.py).

### Acceptance Criteria
For the next issue with at least two correction rounds, no reviewer finding concerns a stale disposition.

### Expected Effect
No stale-disposition findings per multi-round issue.

## 🔴 PROPOSED: Default 30-minute role turn limit cuts off large implementation turns

**Date Identified**: 2026-09-30  15:30
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-TURN-TIMEOUT-001
**Category**: role_turn_timeout
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-30-runoff-001/assessment.md
**Anchors**: tools/esx/agent_runtime.py
**Implementation-Reference**: ESX-Team 1.6.0 (commit 80f674b): per-role turn limit, 3600 s for bob, project-configurable, deadline in the assignment; deployed in project commit b2718fb

### Issue
`agent_runtime.py start/followup` default to `--timeout 1800`. A large implementation brief (RUNOFF-009: a 1,500-line module plus tests) hit the limit and the process group was killed mid-work. The turn was recorded as failed and needed a resume turn; the in-flight tool call and the unfinished message were lost.

### Evidence
Bob session 018a3ef4, turn 58df9207: status failed, error timeout, after 30 minutes. targets.py was on disk but no tests. The resume turn 75acd0df with `--timeout 7200` completed.

### Potential Impact
Wasted spend on the killed turn's tail, and a failed record that needs a continuation.

### Proposed Fix
Raise the default (e.g. 3600–7200 s for bob); take the default per role or from the budget kind; warn at 80% of the limit so the role can checkpoint and report; document `--timeout` in the brief template.

### Acceptance Criteria
A large Bob brief completes in one turn without a timeout, or the turn ends with a report before the limit.

### Expected Effect
No implementation turns lost to the default timeout.
