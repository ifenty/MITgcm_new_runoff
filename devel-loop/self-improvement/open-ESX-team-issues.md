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

## 🔴 PROPOSED: assess-transition rejects verify.py evidence references as returned

**Date Identified**: 2026-10-02  21:30
**Status**: Proposed
**UUID**: TEAM-TRANSITION-EVIDENCE-001
**Category**: runtime_recovery
**Severity**: Low
**Assessment**: devel-loop/self-improvement/assessments/2026-10-02-runoff-010/assessment.md
**Anchors**: tools/esx/runtime_recovery.py

### Issue
`verify.py` names its evidence file by a canonical-JSON digest and returns that digest as `sha256`. `runtime_recovery.validate_assessment` hashes the raw file bytes, so a judgment citing the `verify.py` evidence reference unchanged fails with "compatibility check evidence hash mismatch". The judgment file format (decision, assessor, reason of at least 40 characters, and a check with command, executed, exit and evidence) is documented only in the source.

### Evidence
RUNOFF-010, 2026-10-02: a one-sentence CLAUDE.md edit changed the runtime contract for retained Bob a6fef0e4; the first assessment citing verification/0a296302….json failed; re-hashing the raw file passed (runtime-transitions/a66ccb55….json).

### Potential Impact
A few minutes lost per runtime transition; coordinators may guess the format.

### Proposed Fix
Validate the check evidence with `verify.load_evidence`, as footer evidence is validated, and show the judgment format in `assess-transition --help`.

### Acceptance Criteria
A judgment citing a `verify.py` evidence reference exactly as returned is accepted; `--help` shows the required fields.

### Expected Effect
Transitions are recorded on the first attempt.

## 🔴 PROPOSED: Provider-limit pause lifts before its known reset on a real-output Stop

**Date Identified**: 2026-10-03  07:40
**Status**: Proposed
**UUID**: TEAM-PAUSE-EARLY-LIFT-001
**Category**: loop_pause
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-02-runoff-010/assessment.md
**Anchors**: tools/esx/ralph_stop.py

### Issue
A retained Bob turn hit the session limit, and `pause_for_provider_limit` correctly paused the loop with `paused_until` set to the reset. The coordinator then ended its turn with a real summary message under the grace allowance. The Stop hook classified that turn as 'working', lifted the provider_limit pause and advanced the iteration from 1 to 2, about 90 minutes before the reset.

### Evidence
The loop status after the stop: iteration 2, not paused. Before it: paused, pause_source provider_limit, paused_until 1791018600. The Bob turn 18355f6d failed with "You've hit your session limit · resets 2:10am".

### Potential Impact
An iteration is consumed, and the loop resumes while the provider is still refusing work.

### Proposed Fix
While `paused_until` is in the future, a 'working' Stop must not lift a provider_limit pause; only the reset time, or a later working Stop, lifts it.

### Acceptance Criteria
With paused_until in the future, a working Stop leaves the loop paused and does not advance it.

### Expected Effect
No iterations are lost to the grace-allowance summary turn.

## 🔴 PROPOSED: Provider-limit pause time still shortens later role turns

**Date Identified**: 2026-10-03  09:50
**Status**: Proposed
**UUID**: TEAM-PAUSE-DEADLINE-CLAMP-001
**Category**: loop_pause
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-02-runoff-010/assessment.md
**Anchors**: tools/esx/team_budget.py

### Issue
`team_budget.reserve` clamps each turn to the issue scope's nominal deadline (`started + minutes`) while that deadline is still in the future. The scope clock keeps running through a provider-limit pause. After the 07:37–09:10Z outage, the first resumed Bob turn (`--timeout 5400`) was killed at 09:46Z. That was the original issue deadline (09:36Z) plus grace, after 33 minutes of work. Bob also reported that the resumed brief carried the old deadline, so the turn before it stopped at once.

### Evidence
RUNOFF-002:
- turn 3f39b1ec: completed after 109 s with nothing done, "deadline passed";
- turn e521703f: failed with "timeout" after 1989 s; its reservation deadline was 1791020182 (09:36:22Z).

### Potential Impact
Two wasted turns after every provider outage, and the role's work is cut off mid-edit.

### Proposed Fix
Pause the scope clock while the loop is paused (shift the scope deadline by the pause duration), or exempt the issue scope deadline from the turn clamp, keeping it only as a measured overrun (the module's own docstring calls these nominal, not caps).

### Acceptance Criteria
After a pause of N minutes, a turn dispatched with `--timeout T` gets at least min(T, remaining nominal + N) seconds.

### Expected Effect
No turns are lost after an outage.

## 🔴 PROPOSED: doc_contract digests `ast.dump` output, so a valid sealed report reads as stale under a different Python

**Date Identified**: 2026-10-04  18:10
**Status**: Proposed
**UUID**: TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001
**Category**: evidence_integrity
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-10-04-runoff-004/assessment.md
**Anchors**: tools/esx/doc_inventory.py:python_units; tools/esx/doc_contract.py:validate_report

### Issue
`doc_inventory.python_units` digests `context = digest(ast.dump(ModuleContext().visit(tree)))` for every inventoried `.py` file. `ast.dump` is explicitly not a stable cross-version serialization, so the same unmodified source tree yields a different inventory digest under different interpreters. A documentation report sealed under one Python and checked under another is reported `stale; regenerate the change inventory` with **no file changed**, and conversely a genuinely stale report could be accepted. Byte `sha256`s and `project.py signature` are interpreter-independent; the coupling is confined to the documentation contract.

### Evidence
Measured on MITGCM-NEW-RUNOFF, RUNOFF-004, 2026-10-04. The identical tree gives inventory digest `7230056ee9…` under Python 3.10.19 and `8086e2cb…` under 3.13.12, for all 57 inventoried `.py` files, with every inventoried file byte-identical and no mtime after the seal.

Both independent reviewers hit it in the same iteration, which is what makes it High rather than Medium. Review B diagnosed it correctly. Review A reported it as a must-fix, eliminated every tree-side explanation (all 29 sealed targets byte-identical to their recorded `file_sha256`, no mtime after the seal, condition persisting after its scratch directories were removed) and stated it **could not root-cause it** — it had run the system `python3` while the seal was made under the project env. It cost one reviewer a wrong diagnosis and both of them a must-fix item, on a report whose content both later confirmed as accurate. Reproduced again on the re-sealed report: `valid: true` exit 0 under 3.10.19, `stale` exit 1 under 3.13.12.

Hooks are specified to use the system `python3` while `{python}` is the project env, so the two interpreters are both in normal use in one deployment.

### Potential Impact
Wasted review rounds, and worse, misplaced trust: a reviewer who sees `stale` on an accurate report may hunt a non-existent tree change (as happened), and the symmetric failure silently accepts a stale report on a host whose Python happens to match the seal. It also makes the documentation contract non-portable across machines and CI, which the 2026-10-04 machine move showed is not hypothetical.

### Proposed Fix
Digest a normalized structural form instead of `ast.dump` output — e.g. an explicit walk emitting only the node kinds, names and nesting the contract actually relies on — so the digest depends on the source, not the interpreter's serialization. Until then, pin the interpreter per project (done for MITGCM-NEW-RUNOFF in `esx/project_profile.md`) and consider having `doc_contract.py` record the sealing interpreter version in the report and refuse, with a clear message naming both versions, when `check` runs under a different one. The clear refusal is worth doing even after the durable fix, as a guard against the next serialization that turns out to be unstable.

### Acceptance Criteria
`tools/esx/doc_inventory.py` digests a normalized structural form, and the inventory digest of an unmodified tree is byte-equal under at least Python 3.10 and 3.13: seal a report under one, run `doc_contract.py check` under the other, and require `valid: true` exit 0 from both. The existing per-file `sha256` and `project.py signature` must be unchanged by the fix (both are already interpreter-independent and are the control). Additionally, with the sealing interpreter version recorded in the report, a `check` run under a different version prints a message naming both versions and does not attribute the refusal to the tree.

### Expected Effect
No reviewer spends a must-fix item, or a wrong diagnosis, on an accurate report again, and a stale report cannot pass merely because the checking host's Python matches the sealing host's. Direction: reviewer must-fix items attributable to the documentation-contract toolchain rather than to the work under review go to zero. The qualitative invariant: the inventory digest depends on the source tree, not on the interpreter that reads it.

## 🔴 PROPOSED: doc_contract stale returns a truncated hits list that reads as complete

**Date Identified**: 2026-10-05  12:40
**Status**: Proposed
**UUID**: TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001
**Category**: tool_ergonomics
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-005/assessment.md
**Anchors**: tools/esx/doc_contract.py:stale_lines; devel-loop/documentation_contract.md

### Issue
`stale_lines` returns `{'lines': len(hits), 'hits': hits[:limit], 'truncated': max(len(hits)-limit, 0)}` with `limit=200`. The total and the truncation count are both reported, but the returned `hits` list is the natural thing to count and carries nothing at the point of use that says it is partial. Counting entries of `hits` rather than reading `lines` understates a sweep silently, by up to the cap.

### Evidence
RUNOFF-005, 2026-10-05. Measured on the tree at closure, with a figures row of `12` over this project's inventory: **`lines` 335, `hits` returned 200, `truncated` 135**, and all 200 returned hits carrying the figure (trivially, every row being that row). Excluding `MITgcm/` the true count is **191**. Review A, review B and Arch each measured 335 and 191 independently, by three separate routes; Arch's run also reproduced 200 returned and 135 truncated under the default cap, which is the mechanism itself.

The figure that reached the contract was **199**, and it is now accounted for exactly. It is **not** "the returned hits that carry the figure" — for a single-row probe *all* 200 do, because `stale_lines` sets each hit's `figure` from its own row. It is the capped list **minus the paragraph's own self-reference**: exactly one of the 200 returned hits is `devel-loop/documentation_contract.md:172`, the sentence being written, which contains a literal `12` and is correctly not an "unrelated" line. 200 − 1 = **199**. Review A derived this and Arch reproduced it independently.

So the count was of `hits[:200]`, not of the matches — and the author also, reasonably, excluded a self-reference. A defensible count of the wrong population. Three retellings of the arithmetic were wrong before this one (336/136 for the totals, then "199 of the returned hits carry the figure"), which is itself evidence for how easily this return shape is misread.

Review A's sharper statement of the defect, which supersedes the framing above: the trap is not merely that `hits` is capped. It is that **`lines` and `hits` answer different questions inside one returned dict**, at the same call site, with `truncated` present but easy to skip. Same category as TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001: a tool whose output invites a reading it does not support.

The 199 reached permanent prose in `devel-loop/documentation_contract.md`, in the paragraph that teaches agents that a clean sweep is evidence about the figures table and not about the document. It survived a reviewer pass and was caught only because review A re-measured a figure it had no specific reason to doubt. It also could not be protected by the mechanism it described: a `199` figures row is exactly the bare-number row that paragraph warns against enrolling.

### Potential Impact
Silent understatement of a documentation sweep, in a tool whose output is used to decide whether a document still describes the code. The artefact looks like a plausible measurement, so it does not announce itself. The same tool already carries a separate blind spot (TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001), and both were found by a reviewer re-measuring something that looked settled rather than by the tool reporting a problem.

### Proposed Fix
Make the partial list self-describing so that counting it cannot be mistaken for a total. Options, in rough order of preference: return a sentinel or wrapper type for a truncated list so `len()` of it is obviously not the answer; or name the key `hits_sample` when `truncated > 0`; or have the CLI print the total adjacent to every listing. Independently, add a sentence to `devel-loop/documentation_contract.md` warning that the listing is capped — the implementer proposed exactly this and correctly declined to write it, because the authorised change was one clause.

### Acceptance Criteria
A caller that counts the returned listing of a sweep with more than `limit` hits either gets the true total or cannot obtain a number that looks like one. Reproduce the RUNOFF-005 case: a figures row matching 335 lines under a cap of 200 must not yield a usable 199. The existing `lines` and `truncated` keys keep their meanings, and `doc_contract.py check` and `stale` keep their exit statuses.

### Expected Effect
A figure derived from a sweep listing is either right or visibly unavailable. Direction: occurrences of an understated sweep count reaching a committed document go to zero. The qualitative invariant: no return value of this tool can be counted to produce a plausible wrong total.
