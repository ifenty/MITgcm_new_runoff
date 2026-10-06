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
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-TRANSITION-EVIDENCE-001
**Category**: runtime_recovery
**Severity**: Low
**Assessment**: devel-loop/self-improvement/assessments/2026-10-02-runoff-010/assessment.md
**Anchors**: tools/esx/runtime_recovery.py
**Implementation-Reference**: af5165f (runtime_recovery validates check evidence via verify.load_evidence with a raw-bytes fallback; format documented in assess-transition --help)

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
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-PAUSE-EARLY-LIFT-001
**Category**: loop_pause
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-02-runoff-010/assessment.md
**Anchors**: tools/esx/ralph_stop.py
**Implementation-Reference**: af5165f (ralph_stop: the provider-limit auto-lift now requires an unknown reset time)

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
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-PAUSE-DEADLINE-CLAMP-001
**Category**: loop_pause
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-02-runoff-010/assessment.md
**Anchors**: tools/esx/team_budget.py
**Implementation-Reference**: af5165f (team_budget.USABLE_TURN_FRACTION: a scope deadline bounds a turn only while it leaves half of it)

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
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001
**Category**: evidence_integrity
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-10-04-runoff-004/assessment.md
**Anchors**: tools/esx/doc_inventory.py:python_units; tools/esx/doc_contract.py:validate_report
**Implementation-Reference**: af5165f (doc_inventory.python_units: textual module-context digest; tests/esx guards incl. a 3.10.19-vs-3.13.12 cross-interpreter check)

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
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001
**Category**: tool_ergonomics
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-005/assessment.md
**Anchors**: tools/esx/doc_contract.py:stale_lines; devel-loop/documentation_contract.md
**Implementation-Reference**: af5165f (doc_contract.stale_lines returns 'hits_sample' when truncated, plus doc_contract.listed(); guard requires no caller indexes 'hits')

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

## 🔴 PROPOSED: loop_gate --check-start cannot pass in a correction round, and both escape hatches corrupt the record

**Date Identified**: 2026-10-05  21:30
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-LOOPGATE-CHECKSTART-CORRECTION-ROUND-001
**Category**: workflow_integrity
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/loop_gate.py:Gate._check_start; tools/esx/doc_contract.py:navigate
**Implementation-Reference**: af5165f (doc_contract.latest_orientation; loop_gate._check_start accepts a re-navigated orientation when a validated receipt exists)

### Issue
`--check-start` compares the orientation receipt recorded at `--prepare` against the current working tree. That is the right check at the start of an iteration. But it is bound to the *prepare-time* receipt, so once any work has legitimately changed an oriented target — i.e. in every correction round — it can never pass again, and the gate's own remedy text does not fit the situation it is printing for.

The remedy it prints is: "resume the same arch, inspect every changed target, navigate again (`doc_contract.py navigate --issue <id> --reuse-args <receipt> --use <fresh explanation>`)". Navigating again does **not** clear it: the gate keeps reading the prepare-time receipt, so a fresh orientation receipt has no effect on the comparison. Measured on RUNOFF-013 correction round 1: a full `navigate` produced receipt `945ed7db…` and the subsequent `--check-start` still reported the identical six changes against receipt `565747ab…`.

That leaves only the two documented alternatives, and both falsify the record:
- `--late-reason` "validates the orientation as recorded at `--prepare` and marks the receipt **late**". For RUNOFF-013 the gate had actually passed **on time** — receipt `421b6104…`, `validated_at 2026-10-05T19:43:25.513937Z`, 1.4 s after the start record at `…:24.139854Z`, before any work began. Using `--late-reason` would overwrite an honest on-time receipt with one asserting the gate was skipped, and closeout reports that field.
- `--prepare` resets the iteration, destroying the round-0 and review history.

`loop_lifecycle.py rebind-receipt` does not apply: it re-points a prepared closeout at a later matching **final verification** receipt, not the start orientation.

### Evidence
RUNOFF-013, 2026-10-05. The implementer hit this first and refused both escape hatches on the grounds that each corrupts a record, proceeded on the existing on-time receipt, and referred the matter up. Arch independently reproduced the whole chain: `--check-start` blocked with six changed targets, all six verified as legitimate products of round 0 and round 1 (`docs/code_map.md#pipeline`, `rnf_tendency_apply.F`, `rnf_fields_load.F`, `tests/rnf/refusal_check.py::cases`, `docs/package_design.md`, `docs/model_contract.md`); a fresh full `navigate` accepted and receipted; `--check-start` then blocked again, byte-identically, still citing the prepare-time receipt.

Note that `--next` does **not** ask for `--check-start` at this point (it asks to finish the iteration and run `--check-done`), so the condition does not block closeout. It blocks any attempt to re-establish authorization mid-issue, which is exactly what an agent dispatched into a correction round is told to do.

Collateral finding: the brief that dispatched the round told the implementer to run `loop_gate.py --check-start --issue RUNOFF-013 --agent bob`. Those flags **do not exist** — `--check-start` takes no issue or agent, and `--owner` belongs to `--prepare`. The gate is Arch's over Arch's own orientation and is not a per-agent permission check. The implementer measured this rather than guessing, and said so. This is the second interface in one session that a brief cited without verifying (the first being the role-file path `.claude/ESX-team/BOB.md`, which does not exist; role files are `.claude/agents/*.md`).

### Potential Impact
An agent that follows the gate's printed remedy reaches a state where the only ways forward are to falsify an honest receipt or to destroy review history. A conscientious agent stalls and escalates, costing a round; a less careful one marks a punctual gate as late, which silently degrades every later audit of whether authorization preceded work. Because the false field is "late", the corruption is in precisely the signal the gate exists to protect.

### Proposed Fix
Separate "was authorization in place before work began" from "is the current orientation fresh". The first is a historical fact and is already recorded correctly by the start receipt; it should not be recomputed against a tree that has legitimately moved. The second is what a correction round needs, and a freshly accepted `navigate` receipt should satisfy it. Concretely: have `--check-start` accept the most recent orientation receipt for the issue, not only the prepare-time one, and distinguish a *stale-orientation* refusal (clearable by navigating) from a *skipped-gate* refusal (which is what `--late-reason` is for). Correct the remedy text so it does not prescribe an action that cannot work. Keep `--late-reason` for the case it was built for: a gate genuinely not run before the work.

### Acceptance Criteria
In an iteration whose start receipt validated before the first edit, after round-0 work has changed oriented targets, a fresh accepted `navigate` makes `--check-start` pass **without** marking the receipt late and **without** resetting the iteration. An iteration whose gate genuinely was skipped still cannot pass without `--late-reason`. The on-time/late field of an existing receipt is never overwritten by a later run. Reproduce the RUNOFF-013 case end to end as the regression test.

### Expected Effect
A correction round can re-establish orientation honestly. Direction: receipts marked late because the tool offered no honest alternative go to zero. The qualitative invariant: no gate requires falsifying a record in order to proceed.

## 🔴 PROPOSED: navigate --reuse-args refuses when the changed target is the orientation's own declared map

**Date Identified**: 2026-10-05  21:30
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DOCCONTRACT-NAVIGATE-REUSE-MAP-001
**Category**: tool_ergonomics
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/doc_contract.py:navigate
**Implementation-Reference**: af5165f (doc_contract: the reuse-args 'declared' set now includes the orientation's own map)

### Issue
`navigate --reuse-args` reloads the map, targets and documents of a prior orientation receipt. It refuses if a changed target lies "outside the original orientation's declared targets and documents" — but it tests membership against `targets` and `documents` only, and the **map** is stored in a third field, `map`. So when the thing that changed is the orientation's own `--map` section, the tool reports that section as outside its own declared scope and sends the caller to a full `navigate` to re-declare, by hand, the identical arguments it already holds on disk.

### Evidence
RUNOFF-013 correction round 1, 2026-10-05. Orientation receipt `565747ab…` records `map = "docs/code_map.md#pipeline"`, four `targets` and two `documents`. `docs/code_map.md#pipeline` changed during round 0. `navigate --reuse-args` refused with: `changed targets lie outside the original orientation's declared targets and documents: ["docs/code_map.md#pipeline"]; the dependency slice moved beyond what was read`. The slice had not moved: that section is the receipt's own `map`. Re-running as a full `navigate` with `--map docs/code_map.md#pipeline` and the same four targets was accepted (receipt `945ed7db…`).

**Hit a second time in the next round, by a different agent, and a third by a reviewer.** The implementer hit it in correction round 2 with the changed target being its own declared `docs/code_map.md#verification-routes`, and review B hit it in both rounds 1 and 2 on `#pipeline`. Four independent reproductions across three agents and two rounds; review B noted that this is evidence for raising the severity above Low, and it is raised here on that basis. Every occurrence cleared by re-declaring the identical arguments the receipt already held.

### Potential Impact
Low and self-announcing — the refusal is loud and the workaround is mechanical. The cost is a wasted turn plus the risk that an agent retyping four `--target` arguments by hand drops or mistypes one, which converts an ergonomic nuisance into a real narrowing of what was read. The code map is also the single most likely document to change on an issue that touches it, so this triggers on exactly the common case.

### Proposed Fix
Include the receipt's `map` in the membership set the changed-target check tests against, so a change confined to the declared map section is reusable. Keep the genuine case — a change to a map section that was *not* the declared one — refusing as it does now.

### Acceptance Criteria
With an orientation declaring `--map docs/code_map.md#X`, a change confined to section `X` is accepted by `--reuse-args` with a fresh `--use`. A change to `docs/code_map.md#Y`, not declared, still refuses. Reproduce the RUNOFF-013 case as the regression test.

### Expected Effect
Re-orienting after a round that edited the declared map section costs one command instead of two, with no hand-retyped target list. The qualitative invariant: `--reuse-args` accepts whatever the receipt itself declared.

## 🔴 PROPOSED: doc_inventory omits every project record document, so the ledgers, lessons and assessments get no stale sweep and no disposition

**Date Identified**: 2026-10-05  23:55
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001
**Category**: coverage_gap
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/doc_inventory.py:paths; devel-loop/documentation_contract.md
**Implementation-Reference**: af5165f (project.record_paths, enumerated not listed; doc_contract.stale_lines sweeps inventory + records while acceptance keeps excluding them)

### Issue
`doc_inventory.paths` returns 355 paths. `esx/project_profile.md`, `CLAUDE.md`, `esx/project.json` and all of `docs/` are in it. **Every project record document is outside it** — the eleven enumerated under Evidence plus the whole `devel-loop/self-improvement/assessments/` tree. They are prose documents that make claims about the code, and none receives a `doc_contract.py stale` sweep or a disposition row in a sealed documentation report. So a figure in any of them can go stale with no mechanism able to notice, and an issue can be closed without anything having checked that its own ledger entry still describes the code. (The two first noticed, and the ones that make the cost concrete, are `open_issues.md` and `long_term_goals.md`; do not read the pair as the boundary — that mistake is the subject of the fourth Evidence paragraph.)

`open_issues.md` is the issue ledger — the document the loop reads to choose work and the one an agent reads to learn what an issue is for. It is edited on most issues. It appears in neither of RUNOFF-013's sealed reports (45 dispositions in round 0, 52 in round 1) despite being modified in both.

### Evidence
RUNOFF-013, 2026-10-05. Two agents found the two halves independently and neither half was written down before this entry.

The implementer found the `open_issues.md` half while fixing a different stale statement: a stale "76 statements" figure in `open_issues.md` was invisible to the sweep because the file is not inventoried at all. It reported this as a retrospective item and did not file it.

Review B then measured the boundary directly rather than taking it on report: 355 inventoried paths, with `esx/project_profile.md`, `CLAUDE.md`, `docs/verification_matrix.md` and `esx/project.json` inside, and `open_issues.md` and `long_term_goals.md` outside. It checked `devel-loop/self-improvement/open-ESX-team-issues.md`, `docs/verification_matrix.md` and `esx/project_profile.md` and confirmed the gap is recorded in none of them. The `long_term_goals.md` half is review B's alone.

**This entry originally described the gap as those two files, and that was wrong — it is a class.** Review B measured the full boundary in correction round 2 and Arch reproduced the count independently: **every tracked project record document is outside the inventory.** All eleven of `README.md` (the repository-root one; `devel-loop/self-improvement/README.md` *is* inventoried), `closed_issues.md`, `current_status.md`, `lessons_learned.md`, `lessons_learned_evidence.md`, `old_lessons_learned.md`, `long_term_goals.md`, `open_issues.md`, `devel-loop/self-improvement/open-ESX-team-issues.md`, `devel-loop/self-improvement/closed-ESX-team-issues.md` and `devel-loop/self-improvement/process_changelog.md`, plus every file under `devel-loop/self-improvement/assessments/`. (The `ESX-team-local/` install backups are excluded deliberately: deployment snapshots, legitimately out of documentation scope.) Re-derived independently in correction round 3 by differencing `doc_inventory.paths` against `git ls-files`: 355 inventoried, 77 tracked `.md`, 34 of them outside, 19 `ESX-team-local/` backups and 4 assessments removed, leaving exactly these eleven. Two of those matter especially — `lessons_learned.md`, whose LL-005/LL-009/LL-011 are quoted in every brief, and this ledger itself, so the record of the gap is inside the gap.

**It is not theoretical.** Review B ran the issue's own 27-row figures table by hand over all of them: **8 hits in 5 files**, of which only `open_issues.md` was covered by the hand check the first version of the disclosure prescribed. One — **`closed_issues.md:350`** — was carrying in the present tense the same two stale tokens that had been a must-fix in `esx/project_profile.md` two rounds earlier, uncorrected, because nothing named the file. Everything else was labelled history or self-reference.

**The count is scope-bound and self-referential, so quote it with its scope and its snapshot.** Re-measured at the correction-round-3 seal with the same table, after the `closed_issues.md:350` correction: **7 hits in 5 files** over the tracked record documents, and **8 in 6** once this issue's own still-untracked `assessments/2026-10-05-runoff-013/assessment.md` is counted. Of those eight, **four are this disclosure quoting its own subject matter** — three in this entry and one in the assessment — three are labelled history (`lessons_learned.md:31` and `lessons_learned_evidence.md:226` on RUNOFF-005's "54 of 54", `open_issues.md:74` on the dead `file:line`), and one is `closed_issues.md:350`, now corrected and labelled. Writing the disclosure therefore moves the count — it moved twice inside correction round 3, as these very paragraphs were rewritten — which is why the fix below must be a mechanical enumeration of the boundary and not a hand count of hits: a count over these files measures how much has been written about the gap at least as much as it measures the gap.

This is the companion of TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001 and the second blind spot of the same sweep found on the same issue. The first is that a clean sweep is evidence about the *figures table*, not about the document (a statement survives if no row is spelled the way the prose spells it). This one is sharper, because no table row can help: a document outside the inventory is not swept at all, so there is no wording that would have caught it.

### Potential Impact
The documents least protected by the contract are the project's own records: what it is *for*, what is still open, what it has already learned, and what it has already closed. A stale ledger entry misdirects issue selection and misinforms every agent dispatched against it; a stale `lessons_learned.md` propagates a wrong lesson into every brief that quotes it; a stale `closed_issues.md` leaves a superseded claim standing as the project's account of finished work. Because the sweep reports clean, all of them read as checked. The failure is invisible in exactly the way the documentation contract exists to prevent — and the under-scoped first version of the disclosure reproduced that failure at one level up, giving a reader confidence about two files while nine went unchecked.

### Proposed Fix
Add the project record documents to `doc_inventory.paths` so they receive sweeps and dispositions like any other project prose. If some are deliberately excluded — a plausible argument for the ledgers, whose entries are superseded by design rather than kept current — then say so **as a class, with the measured membership**, in `devel-loop/documentation_contract.md` and wherever the project states what the sweep covers, so an agent reading a clean sweep knows what it does not cover. Silence is the defect; either resolution is acceptable. Naming a subset is a third outcome and is worse than either, because it converts an unknown gap into a confident wrong boundary.

### Acceptance Criteria
For **every** tracked project prose document, either `doc_contract.py stale` visits it and a sealed report can carry a disposition for it, or the documentation contract names it out of scope with the reason — with no document in neither category. Enumerating the boundary must be mechanical rather than a hand-maintained list, so a newly added record document cannot land silently outside both. Reproduce the RUNOFF-013 case twice over: the stale "76 statements" figure in `open_issues.md` must be findable by the mechanism or provably outside it by a written rule, and the same must hold for `closed_issues.md:350`, which the first, two-file version of the disclosure left unchecked. The existing 355 inventoried paths keep their dispositions either way.

### Expected Effect
No project prose is both unswept and undeclared. Direction: documents that are neither inventoried nor disclosed as uninventoried go to zero. The qualitative invariant: a clean sweep's scope is written down, so "clean" cannot be read as "complete" by mistake.

## 🔴 PROPOSED: A structurally dead provider is probed every iteration and gates the loop before any other instruction

**Date Identified**: 2026-10-06  05:50
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-NOTIFY-OUTAGE-NO-BACKOFF-001
**Category**: loop_cost
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/notifications.py:active_outage; tools/esx/loop_gate.py:Gate.next; devel-loop/communication.md
**Implementation-Reference**: af5165f (notifications.backoff doubling per consecutive down, capped at 32; loop_gate defers the communication notice instead of returning on it)

### Issue
While an outage is active, `--next` demands a recorded re-probe **every loop iteration**, and separately the outage record expires after `OUTAGE_RENEW_ITERATIONS` and must be renewed with fresh evidence. Both demands are emitted *before* any other instruction, so each iteration pays the toll before the gate will say what the actual work is. Neither mechanism distinguishes a transient provider fault from a structural one — a provider that has never been configured is re-probed on exactly the same cadence as one that might come back in a minute.

### Evidence
RUNOFF-013, loop iterations 1-85, 2026-10-05/06. **73 probes**, every one returning the identical `claude mcp list` output: `No MCP servers configured. Use `claude mcp add` to add a server.` (exit 0). Plus **14 outage renewals** under the five-iteration bound. **Loop iterations 13-85 produced no scientific work at all** — 73 of 100 authorized iterations, 73% of the budget — because the only pending work was a 59-command verification (6449 s) that nothing could accelerate, and every cycle spent its turn on the probe first. The probe count exceeded the number of genuine review findings the issue's last two correction rounds produced.

The cause was structural and known from the first probe: no Slack MCP server was registered for the session, so there was no authenticated message-posting tool to discover, and the remedy (`claude mcp add`) is an owner action no agent can perform. The owner was told the exact command and ultimately revoked the provider instead.

This is the third retrospective in which an absent notification provider is a recorded problem (`provider_api_error_and_absent_notification_provider` on RUNOFF-005), so it is a recurrence with no open owner until now.

### Potential Impact
Direct, measured consumption of the finite loop budget with zero information gained. In the worst case the budget is exhausted on probes before the active issue can be closed, which would leave a fully reviewed and verified issue open because the loop ended during its closeout. The toll scales with how long real work takes, so the slowest and most valuable issues pay the most.

### Proposed Fix
Distinguish a structural outage from a transient one, and back off. A probe whose evidence is byte-identical to the previous probe's should extend the outage rather than reset the per-iteration demand; after N identical probes, stop demanding per-iteration re-probes and demand one per closeout, or none until the provider's configuration changes. Separately, never emit the probe demand ahead of the active issue's own next instruction — report both, work first. If `communication.provider` names a provider with no discoverable tool at session start, say so once and mark the channel unavailable for the session rather than re-deriving it every iteration.

### Acceptance Criteria
With a provider that cannot be discovered and probe evidence that does not change, a 100-iteration loop records at most a bounded number of probes (one per closeout, or one per configuration change) and `--next` reports the active issue's instruction first. Reproduce the RUNOFF-013 case: 85 iterations with an unconfigured provider must not produce 73 probes. An outage with *changing* evidence keeps the existing per-iteration cadence, since that is a provider that might recover.

### Expected Effect
Loop budget is spent on work. Direction: iterations whose only activity is a provider probe go to zero. The qualitative invariant: a mechanism that has returned the same answer N times in a row stops being asked.

## 🔴 PROPOSED: The documentation seal and every reviewer approval share one invalidation set, so any policy edit mid-review strands them

**Date Identified**: 2026-10-06  05:50
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-ACCEPTANCE-POLICY-EDIT-STRANDS-APPROVALS-001
**Category**: workflow_integrity
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/project.py:source_signature; tools/esx/project.py:administrative; tools/esx/doc_inventory.py:paths
**Implementation-Reference**: af5165f (project.acceptance_scope and `project.py acceptance-scope PATH`)

### Issue
`project.source_signature` digests exactly `inventory_paths(root, cfg, scientific)`, and `doc_inventory.paths` returns `inventory_paths(root, config(root, ready=False))` — measured to be the **identical** 355-path set, empty symmetric difference. So the sealed documentation report and every reviewer approval are invalidated by precisely the same files, in one event. Because `FRAMEWORK_PATHS` places all of `tools/esx`, `.claude`, `devel-loop`, `docs`, `esx`, `CLAUDE.md` and `.gitignore` inside that set, **44 policy and instruction documents** sit inside the candidate beside 49 executable witnesses. Editing any one of them during review — including to fix a defect a reviewer just asked for — strands every approval and forces a re-affirmation round.

### Evidence
RUNOFF-013 correction rounds 2 and 3, 2026-10-05. Review B's single round-2 must-fix lay entirely in *record* documents, all outside the candidate, so that round need not have cost an approval. One of the five resulting fixes landed in `devel-loop/documentation_contract.md`, a policy file inside the candidate: the signature moved `1cb143ef…` → `7e6343dc…`, `doc_contract.py check` reported the sealed report stale, and review A's approval was stranded — causing correction round 3 outright, at the cost of one implementer turn and two reviewer re-affirmations for zero code change.

Three successive hand-counts of this boundary gave **1, 10 and 44**; only the mechanical enumeration was right. `project.administrative()`'s own docstring already states the intended rule — *"Exclude records, not policy or executable witnesses, from acceptance."* — but nothing surfaces the boundary at dispatch time, so a coordinator cannot tell which of its pending edits will strand an approval.

This is the second retrospective with this problem (`post_approval_edit_invalidates_evidence` on RUNOFF-033), so it is a recurrence with no open owner until now.

### Potential Impact
A correction round per policy-file edit, each costing an implementer turn plus a re-affirmation from every reviewer. The failure is discovered only when the next gate refuses, long after the edit, and the diagnosis is unobvious: the natural reading is that something about the work changed, when in fact only a contract document moved. It also creates a perverse incentive to leave a policy document wrong until after closure.

Note a tension this interacts with: `TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001` proposes bringing the project's record documents *into* the inventory. Because the inventory set is the signature set, doing so would move `open_issues.md` inside the candidate and silently void the corollary that a record-only round need not strand an approval. The two must be decided together, or the inventory needs a scope the signature does not share.

### Proposed Fix
Make the boundary visible and actionable rather than implicit. At minimum: a command that answers "will editing this path strand approvals?" from the live inventory, and a line in the dispatch records naming the records-versus-policy rule against the measurement rather than against a file list. Better: give the documentation inventory a scope the signature does not share, so a policy-document correction can be re-sealed without invalidating reviews of unchanged code — the seal already carries per-reference hashes that could decide this per file. One carve-out must survive either fix: an edit to an issue's own acceptance criteria inside `open_issues.md` is policy in substance, because it is what a reviewer judges against.

### Acceptance Criteria
A coordinator can determine, before editing, whether a path is inside the acceptance set, from the live configuration rather than a documented list. A correction confined to record documents provably does not invalidate a sealed report or an approval. If the inventory and signature scopes are separated, a policy-only edit re-seals without requiring reviewer re-affirmation of unchanged source, and an edit to an issue's acceptance criteria still does require it. Reproduce the RUNOFF-013 round-3 case as the regression test.

### Expected Effect
Re-affirmation rounds are caused by changed work, not by changed prose. Direction: correction rounds whose only content is a stranded approval go to zero. The qualitative invariant: the acceptance boundary is queryable, so stranding an approval is always a choice rather than a surprise.

## 🔴 PROPOSED: Briefs are hand-written and cite tool interfaces that do not exist, while brief.py goes unused

**Date Identified**: 2026-10-06  05:50
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-BRIEF-UNVALIDATED-INTERFACE-001
**Category**: dispatch_quality
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/brief.py:build; tools/esx/footer_contract.py:reference_errors; devel-loop/team_operations.md
**Implementation-Reference**: af5165f (brief.interface_errors refuses unknown ESX commands/flags, subcommand-aware; brief states the required footer agent; loop_gate.defective_completions reports uncaptured turns)

### Issue
`brief.py build` exists to assemble a dispatch brief with the baseline, orientation suggestions, figures and sweep sections. Briefs are nonetheless written by hand, and nothing validates the interfaces, paths or required references they cite. A brief that instructs an agent to run a command with flags that do not exist, or omits a reference the receiving contract requires, is discovered only by the agent — if the agent is careful enough to measure rather than comply.

### Evidence
RUNOFF-013, 2026-10-05, three instances in one issue. (1) A brief instructed the implementer to run `loop_gate.py --check-start --issue RUNOFF-013 --agent bob`; **those flags do not exist**, and the gate is Arch's over Arch's own orientation rather than a per-agent permission check. The implementer measured this, established the gate had already passed on time, and proceeded — but a less careful agent would have stalled or falsified a receipt. (2) Two consecutive briefs **omitted the sealed documentation report's path and sha256**, which the documentation contract requires in a standalone section and without which an approval is rejected at capture; both reviewers had to locate it themselves, and one noted that an approval citing the wrong report is rejected. (3) A brief asserted that three enrolled test cases needed `data.ptracers` and `data.longstep` when they need neither, and asserted a reviewer had not hit a prerequisite it had in fact hit — both traceable to Arch repeating an implementer's summary about a *different* set of cases without checking.

The same issue also produced a related defect from invented naming: calling the two reviewers "Richard A" and "Richard B" in every brief led one to write `"agent": "richard-a"` in its footer, which `agent_runtime.py:236` compares against the registered `agent_type`. **All four of that reviewer's completions were silently recorded `incomplete`** and were unavailable to the closeout packet, discovered only hours later when closure needed them.

This is the second retrospective with this problem (`stale_role_file_path_in_briefs` on RUNOFF-033, where every brief cited `.claude/ESX-team/BOB.md` and `RICHARD.md`, which do not exist), so it is a recurrence with no open owner until now.

### Potential Impact
Wasted agent turns, and worse, a nudge toward falsifying records: an agent told to run a command that cannot succeed must either stall, improvise, or use an escape hatch that corrupts a receipt. The footer instance shows the sharper risk — correct work recorded as incomplete, invisibly, until a gate needs it.

### Proposed Fix
Validate a brief before dispatch against the things that are already machine-checkable: that every `tools/esx/...` command and flag it names exists (argparse introspection), that every cited path resolves, and that the references the receiving contract requires are present — the sealed report, the baseline, the orientation. `footer_contract.reference_errors` already does the symmetric check on the way back; the same discipline belongs on the way out. State the exact required `agent` footer value in the dispatch, since it is the registered `agent_type` and an agent cannot otherwise know that a descriptive name voids its record. Prefer `brief.py build` over hand-assembly so these checks have a single place to live.

### Acceptance Criteria
A brief naming a nonexistent flag, an unresolvable path, or omitting a contract-required reference is refused before dispatch, with the offending item named. The required footer `agent` value appears in every dispatch. Reproduce all three RUNOFF-013 instances as regression cases, plus the `richard-a` footer case.

### Expected Effect
Agents spend their turns on the work rather than on diagnosing their instructions. Direction: reviewer or implementer findings that concern the brief rather than the candidate go to zero. The qualitative invariant: anything in a brief that a machine could have checked, was checked.

## 🔴 PROPOSED: capture accepts a stale orientation receipt that check-orientation refuses

**Date Identified**: 2026-10-06  13:40
**Status**: Proposed
**UUID**: TEAM-FOOTER-ORIENTATION-FRESHNESS-001
**Category**: workflow_integrity
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/footer_contract.py:reference_errors; tools/esx/agent_runtime.py:stop_record; tools/esx/doc_contract.py:validate_orientation

### Issue

**Corrected 2026-10-06 by review A, which measured the gate rather than reading it, and the correction narrows the claim: the gap is path-dependent.** `agent_runtime.py:246` — the native-subagent capture path — calls `footer_contract.reference_errors` only. `agent_runtime.py:977` — the retained/dispatched-turn path — calls `footer_contract.validate`. Review A measured both legs with everything else fresh so the orientation receipt was the only stale reference: `reference_errors` returned `[]` while `validate` returned the stale-orientation error, naming the same three changed selections as `check-orientation`. So capture **does** enforce orientation freshness on the dispatcher path and **does not** on the native path. The original text below said "accepted at capture" without qualification; that is true for native subagents and false for dispatched turns.

The same asymmetry covers the **sealed documentation report**: `reference_errors` takes no `expected_report` parameter, so on the native path a footer citing a superseded report is accepted. Review A measured that too, in round 1, with report `66a3634d`. That makes a brief's instruction to read the current sealed report *load-bearing* rather than belt-and-braces, which is worth knowing given that two briefs on the previous issue omitted it entirely.

The comment at `agent_runtime.py:238-239` states that the native path exists to give native turns the same capture-time contract a retained turn gets (citing TEAM-NATIVE-FOOTER-VALIDATION-001). So parity is the stated intent and the measured behaviour falls short of it in exactly two respects. Review A's minimal fix: have that path call `validate`, which needs only `correction_round` and the packet documentation reference beyond what it already reads.

`footer_contract.reference_errors` validates a footer's orientation receipt by calling `doc_contract.validate_orientation` with `fresh=False`, so a receipt whose selected targets have since moved is **accepted at capture**. The same receipt is refused by `doc_contract.py check-orientation`, which validates it fresh. So the two gates disagree about the same artifact, and the lenient one is the one that decides whether a turn is recorded `completed`.

The practical consequence: an agent that does not voluntarily run `check-orientation` can report work against an orientation it took before the targets changed, and nothing in the capture path objects. The footer then carries a receipt that the closeout gate — which does validate fresh for the current implementer and approving reviewers — may later refuse, or that simply misrepresents what was read.

### Evidence
RUNOFF-030 correction round 2, 2026-10-06. The implementer's documentation edits changed three of its own declared selections (`docs/code_map.md#pipeline`, `docs/package_design.md`, `docs/model_contract.md`). `check-orientation` refused the round-1 receipt and named all three with before/after hashes, so it re-navigated. It then ran the capture validator against a footer citing the **stale** receipt as a deliberate control, and recorded the result: **no error**. Its own words: "capture would have accepted the stale receipt silently and `check-orientation` is what caught it."

This is the mirror of the error Arch made earlier in the same issue, and the pairing is what makes it worth filing. Arch measured that the *review packet* does not re-fingerprint verification evidence and generalised that to "nothing re-fingerprints it"; capture does, and an instruction based on that generalisation would have produced a third rejected footer. Here the asymmetry runs the other way: `check-orientation` is strict and capture is lenient. In both directions the lesson is the same and is now recorded twice — **two gates that validate the same artifact need not agree, and knowing which one decides is part of knowing the answer.**

**Sharpened 2026-10-06 by the implementer on RUNOFF-030 round 3, which pre-flighted its own footer through both capture functions with three must-fail controls.** The two gates are *complementary*, not merely unequal in strictness: superseded verification evidence is caught by `reference_errors` only, and a superseded orientation receipt by `validate` only. Neither alone is sufficient, which rules out the simplest fix of picking one. And a third artifact is covered by neither on the implementer path: a **Bob** footer citing a superseded sealed documentation report returns no error from either function, because `validate`'s report-identity check compares against an `expected_report` that only a validated reviewer packet supplies, and an implementer has no packet. So the currency of `documentation_review.report` in an implementer footer rests on diligence alone. This is the artifact the implementer re-seals every single round, i.e. the one most likely to go stale, and the role that re-seals it is the role with no gate on it. Add to the acceptance criteria: an implementer footer citing a superseded sealed report is refused at capture.

### Potential Impact
A completion recorded as valid against an orientation that no longer describes what the agent read. The failure is silent at the moment it matters and surfaces, if at all, at closeout — the same shape as TEAM-BRIEF-UNVALIDATED-INTERFACE-001's footer-identity defect, which voided four reviews before anything reported it. It also rewards not checking: an agent that runs `check-orientation` discovers work to do, while one that does not is captured clean.

### Proposed Fix
Decide which semantics capture should have, and make the two gates agree or make the difference explicit. If `fresh=False` is deliberate — plausibly it is, so that a historical completion retains its own orientation — then capture should still record a warning naming the changed targets, and the closeout gate's stricter check should be the only place staleness is fatal. If it is not deliberate, validate fresh for the *current* round's completions and keep `fresh=False` only for completions imported from earlier rounds. Either way, state the rule where an agent reads it: `devel-loop/documentation_contract.md` describes `check-orientation` as the reuse test without saying that capture applies a weaker one.

### Acceptance Criteria
A footer citing an orientation whose selected targets have moved is either refused at capture, or accepted with the changed targets named in the recorded completion. Reproduce the RUNOFF-030 round-2 case: the round-1 receipt, after three declared documentation selections changed, must not be silently accepted. A completion imported from an earlier correction round keeps its own orientation without a new refusal.

### Expected Effect
The two gates agree, or their disagreement is visible in the record. Direction: completions recorded against a stale orientation go to zero. The qualitative invariant: no artifact is valid at one gate and invalid at another without the record saying so.

## 🔴 PROPOSED: the defective-completion notice never clears after the agent fixes it

**Date Identified**: 2026-10-06  14:20
**Status**: Proposed
**UUID**: TEAM-GATE-DEFECT-NOTICE-NOT-SUPERSEDED-001
**Category**: workflow_integrity
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/loop_gate.py:defective_completions; tools/esx/loop_gate.py:rejection_streak

### Issue

`defective_completions` reports every dispatch record whose `status` is
`incomplete` or `failed` for the active iteration, with no suppression for a
later record showing the same agent re-emitted the same round successfully. The
notice is therefore permanent for the rest of the iteration: it is emitted on
every subsequent `--next`, long after the condition it describes was repaired.

The sibling method directly below it, `rejection_streak`, does the same job
correctly — it accumulates into `verdicts[number]`, so the latest record for a
round replaces the earlier one and only the current state is reported. The two
methods are adjacent, read the same log, and disagree about whether a later
record supersedes an earlier one.

### Evidence

RUNOFF-030, 2026-10-06. `dispatch_log.jsonl` holds six records for
`bob a3ded3177de1902a7` at `correction_round` 1: one `incomplete`
("report cites a reference that does not resolve: independent_check.evidence:
verification evidence is stale") followed by four `completed` records with no
error, the re-emissions that fixed exactly that defect. Round 3 is also
recorded `completed`. The gate still printed
`UNCAPTURED COMPLETION: bob a3ded3177de1902a7 (round 1) ...` and its remedy —
"Resume that agent and ask it to re-emit its footer" — names work that had
already been done five records earlier in the same file.

### Potential Impact

This is the failure mode the mechanism was built to prevent, inverted. The
notice exists because four valid RUNOFF-013 reviews were recorded `incomplete`
and nothing reported it (TEAM-BRIEF-UNVALIDATED-INTERFACE-001). A notice that
cannot clear teaches the operator to read past it, so the next real one is
skipped too — and a real one is indistinguishable from a stale one by
inspection, since both name a resumable agent and a plausible remedy. It also
costs a dispatch each time it is believed: resuming an agent to re-emit a
footer it has already re-emitted correctly.

### Proposed Fix

Key the scan by `(agent_id, agent_type, correction_round)` and keep only the
last record for each key, as `rejection_streak` already does for verdicts; report
only keys whose final state is `incomplete` or `failed`. Do not merely compare
counts — an agent may legitimately have a later *different* round still broken,
so the suppression must be per round and not per agent.

### Acceptance Criteria

A round with an `incomplete` record followed by a `completed` one for the same
agent and round produces no notice. A round whose only record is `incomplete`
still produces one. An agent with round 1 repaired and round 2 broken is
reported for round 2 only. Reproduce the RUNOFF-030 six-record round-1 sequence
above as the regression case, and assert that `rejection_streak` and
`defective_completions` agree about supersession on the same log.

### Expected Effect

Every notice the gate emits describes a condition that is true when it is
printed. Direction: notices naming already-repaired records go to zero. The
qualitative invariant: a gate notice is actionable, so it can be trusted without
re-deriving whether it still holds.

## 🔴 PROPOSED: the loop hold condition ignores Arch's own long-running work and drains the iteration budget

**Date Identified**: 2026-10-06  20:05
**Status**: Proposed
**UUID**: TEAM-LOOPHOLD-ARCH-BACKGROUND-WORK-001
**Category**: workflow_integrity
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md
**Anchors**: tools/esx/loop_control.py:run; tools/esx/ralph_stop.py:main

### Issue

The Stop-hook loop driver holds the iteration counter while a **native subagent**
is running, and advances it otherwise. It does not recognise Arch's own
long-running background work. The final scientific verification is Arch-owned by
workflow design (`final_verify_owner: arch`), runs ~60 commands over roughly 110
minutes, and is **mandatory for every `scientific_change` issue** — so the
longest required step of the standard workflow is precisely the step that spends
the iteration budget fastest, at about one iteration per Stop cycle while no work
can proceed.

This is the structural half of LL-018 ("bookkeeping can cost more than the
science, and the loop will not tell you so"). LL-018 records the *mitigation* —
`loop_control.py pause` preserves the budget — but the mitigation requires Arch
to notice, and the failure is silent and fast, so the default outcome is a
quietly drained budget.

### Evidence

RUNOFF-030, 2026-10-06, from `.claude/esx-loop-exit.log`, which states the rule
in its own words on every line. Every turn with a subagent running:

    17:51:22  HOLD iteration=3 native subagent running: richard (1 min); iteration not advanced

The two turns after the subagents finished and the Arch-owned final verification
started as a background shell command:

    18:19:13  CONTINUE iteration=4 budget=20
    18:20:33  CONTINUE iteration=5 budget=20

Eighty seconds apart, with no work possible in between. Two iterations of an
owner-granted 20-iteration budget spent waiting on Arch's own required run. The
run itself took 6628.9 s (110 min) across 59 commands.

### Potential Impact

At the observed ~80 s per iteration, a single mandatory verification run can
exhaust a 20-iteration budget before the issue it is verifying closes. The budget
would read "spent" with one issue delivered, and the owner's instruction to run N
iterations would silently mean something far smaller than N issues. It also
penalises the correct behaviour: an issue that reaches final verification — i.e.
one that is nearly done — is the one that burns budget.

### Proposed Fix

Extend the hold condition to cover Arch-owned background work the loop itself
requires, not only native subagents. The cheapest sufficient form is to hold
while a `final_verification.py` or `verify.py` process belonging to this run is
alive, which is the same `ps`-based liveness check the kit already performs for
container and suite clearance elsewhere. Alternatively, have `final_verification.py
run` take the pause itself and release it on exit, so the protection does not
depend on Arch remembering.

### Acceptance Criteria

A Stop cycle during a live Arch-owned `final_verification.py` or `verify.py` run
logs `HOLD` with the process named and does not advance the iteration.
Reproduce the RUNOFF-030 sequence: two consecutive Stop cycles 80 s apart during
a running final verification must consume zero iterations. A Stop cycle with no
subagent and no Arch-owned run still advances, so the loop cannot stall.

### Expected Effect

The iteration budget measures work attempted rather than turns taken. Direction:
iterations consumed while no work can proceed go to zero. The qualitative
invariant: an owner who grants N iterations gets N units of work, not N polls.
