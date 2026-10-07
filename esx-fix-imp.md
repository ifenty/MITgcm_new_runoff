# ESX implementation plan: restore scientific delivery

## 1. Handoff, scope and evidence

**Implement this plan in `ifenty/esx-team`, not in the installed framework copy in
`ifenty/MITgcm_new_runoff`.** The objective is independently verified scientific
delivery with less procedural rework. Closing every process issue is not a
prerequisite or a success metric.

This plan was prepared on 2026-10-07 from the runoff repository at revision
`9577fde`. The evidence links below identify that deployed snapshot. They are
not claims about the current upstream ESX release. The receiving agent must first
locate the corresponding upstream owners and tests and compare implementations.
Resolve its checkout root to an absolute path before issuing file operations;
the filenames and qualified symbols below identify mechanisms, not assumed
upstream installation paths.

### Evidence and limitations

- RUNOFF-030's retrospective reports 832 elapsed minutes, 20 dispatches, and
  unchanged Fortran after round 1 through five subsequent rounds. Its 13
  must-fix findings concerned records, documentation or documentation-checking
  machinery. The dollar fields omit unknown usage and coordinator cost; do not
  interpret their zeros as free execution. [E1]
- RUNOFF-013 records 73 identical probes of an unconfigured communication
  provider while verification ran. It also records a substantive review success:
  the configured suite had not exercised the temperature/salinity tendencies.
  Removing independent scientific review would discard an effective safeguard.
  [E2, E3]
- RUNOFF-040 is recorded as implemented but not closed. Its latest documented
  final run stopped after 35 commands passed and the next command started.
  The project attributes that stop to external termination. That is neither a
  completed qualification nor, by itself, a scientific failure. [E4, E5]
- Source inspection found coupling between framework changes, documentation
  seals, scientific fingerprints and review freshness. Several historical
  defects already have local fixes and regression tests. [E6, E7, E8]
- No upstream comparison or tests were executed to prepare this document.
  Historical observations above are attributed records, not fresh reproductions.

The available cloud checkout lacks the nested MITgcm repository, active
issue-start/issue-done records, and the configured project Python executable.
Its committed records cannot reconstruct a current reviewed candidate or supply
missing execution receipts. Recovery of RUNOFF-040 therefore belongs on the
authorized working host, separately from implementing the upstream framework.

## 2. Non-negotiable safeguards and non-goals

Preserve:

- Independent scientific review, risk-based additional review, numerical
  tolerances, conservation checks, negative controls and adequate sample counts.
- Exact source/input/toolchain provenance and immutable historical evidence.
- Refusal to accept interrupted, failed, empty, nonfinite, stale or incomplete
  qualification as PASS.
- Explicit authorization for spending, external communication and publication.
- Failed attempts and their successful continuations under real agent identities.
- The original baseline and evidence for an issue already in flight.

Do not:

- Replace ESX, redesign every gate, or introduce a new orchestration service.
- Weaken an oracle, discard inconvenient findings or fabricate recovered reviews.
- Disable all documentation review or remove framework code indiscriminately
  from execution dependencies.
- Turn retrospective collection or delivery metrics into additional closure gates.
- Reopen the footprint-claim sweep project as part of this work.
- Automatically restore Slack, launch paid agents, or start a scientific run.
- Edit another repository from the upstream implementation task.

An independently demonstrated defect in a scientific oracle is a scientific
blocker. A stale historical count is not equivalent to such a defect. A statement
about current supported behavior, units, tolerances or safety can be substantive
even when the patch changes prose only.

## 3. Delivery sequence

Use small, independently reviewable changes rather than a framework-wide rewrite.
At most one framework repair should interrupt an active scientific acceptance
cycle, and only when necessary to unblock it or protect its evidence.

1. **Reconcile upstream and deployed behavior.** Identify existing fixes and the
   smallest remaining blocker; establish regression witnesses.
2. **Repair verification outcome classification.** Ship independently if it is
   needed to recover RUNOFF-040. Do not hold this repair for scope refactoring.
3. **Make process triage non-preemptive and persistent.** Retain correctness and
   authorization gates while removing repeated administrative prerequisites.
4. **Prove lifecycle liveness and repair handoff inconsistencies.** Reuse existing
   mechanisms; add missing integration coverage rather than duplicate utilities.
5. **Separate execution and acceptance dependencies incrementally.** This is a
   higher-risk change with its own compatibility tests and release boundary.
6. **Deploy at a safe boundary and pilot three runoff closures.** Restore the
   scientific queue without making the entire framework backlog a dependency.

The runoff project can proceed with already sufficient safeguards while later
upstream improvements are developed. It must not wait for every stage here.

## 4. Work package A: reconcile, reproduce and avoid duplicate fixes

**Owners:** the upstream framework map, installer/upgrader, existing regression
suites, and the equivalent owners of the deployed local fix tests. [E8, E9]

For each relevant finding, determine whether it is absent upstream, present but
untested, already tested, or project-specific. Record that disposition in the
ordinary change description or existing issue record, not a new mandatory ledger.

Check these mechanisms first:

| Mechanism | Deployed evidence | Required decision |
| --- | --- | --- |
| Notification outage backoff and work-first reporting | `notifications.backoff`, `Gate.next` | Preserve or port; do not rebuild from the historical complaint. |
| Waiting during final verification | `ralph_stop.verification_running` and Stop handling | Verify ownership, bounded recovery and wake-up behavior. |
| Repaired-completion supersession | `Gate.defective_completions` | Preserve per-agent/per-round supersession; retain actual unresolved failures. |
| Correction-round start recovery | `Gate._check_start`, latest orientation selection | Preserve an honest on-time start instead of fabricating a late start. |
| Queryable acceptance boundary | `project.acceptance_scope` | Keep it; distinguish diagnostic visibility from actual scope separation. |
| Record-document stale sweeps | `project.record_paths` | Keep records out of scientific acceptance merely because they are swept. |
| Brief interface validation | `brief.interface_errors` | Check real instructions without treating quoted evidence as commands. |
| Footer capture | Native `agent_runtime.stop_record` versus retained capture | Confirm equivalent contracts; a common name does not establish parity. |
| Interruption classification | `verify.interruption`, `_run`, `execute` | Reproduce positive exit plus external termination and classify honestly. |

Reconcile implemented fixes with their release and validation evidence. A patch
may be implemented without demonstrated operational effectiveness; preserve that
distinction. Do not close all open process records simply because similar code
exists, and do not make perfect historical reconciliation block scientific work.

**Acceptance:** every proposed code change has an upstream gap, a bounded
reproducer, and a named existing test route. Already-fixed behavior receives
coverage or no change, not another implementation.

## 5. Work package B: distinguish verification outcomes

**Owners:** `verify.interruption`, `verify._run`, `verify.execute`,
`final_verification.attempt_status`, `no_current_receipt`, receipt readers and
the verification contract. [E4, E7, E10]

### Required behavior

1. Distinguish completed test failure, command timeout, external interruption,
   source drift and infrastructure failure. They must all be non-PASS, but their
   explanations must not make the same scientific claim.
2. Preserve the raw exit code, termination cause when known, command identity,
   completed-command count, planned-command count and immutable logs.
3. Classify the outcome before sealing the attempt record. The stored evidence,
   raised exception, final wrapper and closeout explanation must agree.
4. Prefer trusted runner termination metadata to arbitrary child output. A child
   printing a signal-looking message must not turn its failed test into an
   interruption. If a compatibility fallback consumes a marker, bind that marker
   to the runner and establish why it is authoritative.
5. Do not infer interruption from positive exit 124 alone. It may mean a genuine
   timeout or a program-defined failure. Exercise the actual wrapper/process-group
   path described in RUNOFF-040, not just a text-matching unit case.
6. Keep source stability separate from completion status. In the deployed code,
   `stable` means the fingerprint stayed unchanged, not that execution completed.
   Do not silently redefine that field. Add an explicit outcome/completeness
   distinction and require complete PASS in every evidence consumer.
7. A fresh interrupted or failed attempt must not reveal an older PASS as its own
   result. Preserve older history, but require a successful continuation/new run.
8. Missing failure tokens establish only that no matching tokens were observed.
   They do not prove that every started test passed.

Treat missing executables and runner failures as infrastructure failures, not
evidence that model equations are wrong. Preserve the configured command-timeout
policy and report it explicitly; do not silently convert timeout into success.

### Regression acceptance

- Normal success produces a reusable, complete PASS.
- A real failed assertion remains a failed verification.
- A real per-command timeout remains non-PASS and says which command timed out.
- Direct SIGTERM and wrapper/process-group termination produce interrupted
  attempts when the cause is established, including the positive-exit case.
- An unrelated command returning 124 or printing a signal marker is not
  automatically classified as externally interrupted.
- Launch failure produces an infrastructure explanation and no candidate verdict.
- Source mutation during execution prevents acceptance.
- Failure before a later interruption remains visible in the attempt's results.
- Neither interruption nor timeout can expose an earlier cached PASS.
- Unknown legacy outcomes remain conservative; do not infer missing provenance.

Do not edit historical content-addressed records. If a historical diagnosis needs
correction, append a diagnosis referring to the original artifact.

## 6. Work package C: make self-improvement serve the scientific queue

**Owners:** `team_retrospective.pending`, `require_clear`, `followup_due`,
`require_followup`, `decide_followup`, `recurring_issues`, `Gate.prepare`,
`Gate._check_start`, `Gate._next_instruction`, retained dispatch preflight and
the self-improvement/loop contracts. [E11, E12]

Changing only the text printed by `--next` is insufficient: preparation and
dispatch enforce the same debt independently.

### Scheduling policy

Use one authoritative classification and decision across these consumers:

| Finding | Effect on work |
| --- | --- |
| Scientific defect or invalid acceptance evidence | Blocks the affected acceptance/dependent work. |
| Authorization violation or unknown authorization | Prevents the unauthorized operation; independent authorized work may continue. |
| Framework defect preventing the next necessary operation | Allows a bounded repair for that operation. |
| Ergonomic problem with a safe workaround | Non-blocking process backlog. |
| Historical wording, cosmetic counts, optional generalization | Non-blocking maintenance, preferably when the owning file is otherwise edited. |

A blocking decision must name the affected issue/operation, concrete evidence,
and condition that clears it. Severity or recurrence alone must not imply a
project-wide stop. A supposedly safe workaround that falsifies receipts or skips
required evidence is not safe.

### Persistent triage and deferral

- Recurrence surfaces evidence and a triage recommendation, not a mandatory repair.
- Store a deferral against a milestone or a relevant condition, with rationale,
  affected scope and a resolvable trigger.
- Unchanged recurrence across subsequent closeouts must not require the same
  justification again. A milestone closure or relevant dependency change surfaces
  reconsideration once.
- New evidence that changes correctness, authorization or the workaround's
  validity reopens triage promptly; deferral is not an indefinite correctness waiver.
- A re-opened advisory finding remains advisory until its impact is classified.
- Preserve accepted historical retrospectives and old one-closeout decisions.
  Do not silently convert an old decision into permanent authorization.

### Lightweight reflection

Capture available measurements automatically at closeout. Human commentary may be
brief or explicitly pending and completed at the next milestone. Neither pending
commentary nor a missing cost observation should block unrelated scientific work.
Do not let structural audit reject that supported pending state indirectly.

Keep an honest explanation of missing observations. Remove incentives to invent a
problem, confirmation, lesson or sufficiently long paragraph just to clear a gate.
Prevent inherited reminders such as the self-assessment notice from retaining a
contradictory “before continuing” obligation.

### Regression acceptance

After a completed issue, seed repeated advisory findings and pending human
reflection. The next scientific issue must remain selectable, preparable and
dispatchable through both native and retained paths.

Repeat across three closeouts: the same deferral remains valid without renewal.
Then close its milestone or change its specified condition: one reconsideration
is surfaced. Introduce an evidence-integrity or authorization blocker: affected
work is refused while unrelated authorized work can proceed. Preserve cancellation
and termination behavior even when retrospective commentary remains pending.

## 7. Work package D: waiting and liveness without more busywork

**Owners:** `ralph_stop`, `loop_control`, `notifications`, runtime completion
events and the existing waiting contracts. [E9, E13]

Start with the deployed fixes. Do not replace them unless the lifecycle witness
shows a gap.

- Waiting on native agents, retained agents or the issue's verification must not
  consume productive-work iterations.
- Only work belonging to the current project/run may hold that loop. An unrelated
  Python process, stale PID, PID reuse or another checkout must not hold it.
- A held loop needs a reliable continuation: completion event, existing bounded
  wake mechanism or retained wait. “The process is alive” alone does not ensure
  the coordinator resumes after it exits.
- A dead process, expired work lease or abandoned run must produce a recoverable
  state, not an indefinite hold or a false completion.
- An absent optional communication provider must not preempt work. Keep pending
  authorized events visible, back off transient failures, and stop rediscovering
  an unchanged structural absence.
- A revoked provider remains disabled; no automatic retry may restore authority.
- Waiting does not extend owner-authorized money or wall-clock limits.

**Acceptance:** drive repeated Stop events during each supported wait path.
Productive iteration counts remain unchanged, completion resumes the coordinator,
and orphan recovery works. With communications unavailable, a scientific lifecycle
can still finish with an honest non-delivery disposition. Existing required
authorization and explicit delivery-attempt policy remain enforced.

## 8. Work package E: structured handoffs and proportionate correction review

**Owners:** `brief.build`, `interface_errors`, `footer_contract`,
native/retained capture, `workflow_records`, `workflow_handoff`,
`closeout_doctor` and their existing schemas. [E9, E14]

- Generate identity, baseline, candidate, current sealed report, exact completion
  events and supported command forms from authoritative structured state.
- Validate actual executable instructions separately from quoted prior packets,
  logs, JSON and historical examples. Do not keep expanding a prose regex to parse
  arbitrary shell syntax. Unknown free-text claims may need review rather than a
  false machine refusal.
- Use the same required footer semantics for native and retained capture. Preserve
  role-specific freshness rules: historical evidence is history, not current
  approval. A current approving reviewer must cite the current report.
- Report malformed completions immediately. A successful continuation suppresses
  only the repaired agent/round warning; it does not erase the failed event or
  suppress another round's unresolved problem.
- Give intentional consultation/checkpoint turns an explicit non-approval
  disposition. They must never count as independent review simply because they
  are exempt from an approval footer.
- Reuse packet/closeout builders and the existing closeout doctor. Derive their
  required fields from the same contracts used by the acceptance gate. Collect
  independent missing-field findings in one pass; avoid thirteen successive
  refusals to discover the shape.
- Keep material scientific claims in owning contracts. Keep changing counts in
  versioned measurement artifacts rather than repeating live totals throughout
  policy, maps and prose. Do not require a new prose scanner.

**Acceptance:** malformed outgoing instructions are caught without rejecting
quoted valid evidence; native and retained approving footers enforce equivalent
current references; repaired warnings clear correctly; consultation supplies no
approval; one doctor pass reports independent closeout omissions and its completed
output is accepted by the same gate without another schema surprise.

## 9. Work package F: separate execution from acceptance dependencies

**Owners:** `project.selected`, `inventory_paths`, `source_signature`,
`acceptance_scope`, `verify.fingerprint`, documentation inventory/receipts,
review packet identity, `workflow_policy`, `final_verification._reissue` and
configuration/install validation. [E6, E7, E10, E15]

This change needs its own review. A broad exclusion by extension or directory is
not an adequate solution.

### F1. Separate framework tests from scientific inputs

The receiving project's configuration currently includes its entire tests tree
in scientific scope, including ESX regression tests. Provide an explicit
framework/structural test category and validated migration.

Keep scientific test oracles and scientific harness inputs in execution scope.
A test that affects both categories belongs in both. Report every moved or
unclassified dependency; never silently drop a scientific witness because it
lives near framework tests.

**Acceptance:** an ESX-only regression edit requires framework checks but does
not change the numerical execution identity; a scientific-oracle edit does.
Legacy configuration stays conservative until explicitly migrated.

### F2. Separate identities by what they establish

| Identity | Required dependencies | What changing it requires |
| --- | --- | --- |
| Scientific execution | Source/build inputs, scientific tests/oracles, data, commands, toolchain, relevant environment and execution-affecting framework logic | New execution for affected qualification. |
| Scientific acceptance | Execution identity, issue criteria, supported semantics, applicable policy, selected reviews and reviewer independence | Fresh acceptance judgment; never an automatic approval. |
| Documentation | Affected prose and its declared source/contract dependencies | Updated documentation review and seal. |
| Administrative history | Notifications, measurements, issue narration and historical records | Record integrity checks, not automatic numerical reruns. |

The issue's acceptance criteria remain acceptance dependencies even when stored
inside an otherwise administrative ledger. An edit changing units, tolerances,
supported behavior or scientific interpretation cannot be hidden as cosmetic
documentation.

### F3. Preserve safe reuse

- Build on existing execution receipt rebinding rather than inventing a parallel
  cache. Keep old execution time, owner, logs and hashes visible.
- Remove unrelated framework modules from numerical fingerprints only after
  identifying the execution-affecting dependency set and testing its boundary.
  Runner, environment, input hashing, oracle and command-selection changes remain
  relevant even if they are called “framework” changes.
- Unknown/dynamic dependencies use conservative invalidation. An explicit reviewed
  dependency manifest is preferable to unproven automatic call-graph inference.
- A prose-only correction can receive a new documentation approval and fresh
  acceptance binding without rerunning unchanged numerical work.
- Do not hand-edit a reviewer's old signature or transform their earlier footer
  into approval of new text. Preserve independent targeted review where required.
- Distinguish unrelated work completed since an issue's baseline from edits in
  that issue's acceptance slice. Preserve the baseline and attribution rather
  than reclassifying every long-lived issue solely on global signature drift.

### Dependency-mutation acceptance

| Deliberate change | Required result |
| --- | --- |
| Notification adapter or administrative note only | No numerical rerun; relevant framework/record checks still run. |
| ESX-only test only | Structural validation changes; scientific identity is unchanged. |
| Ordinary explanatory wording | Documentation reviewed; unchanged numerical execution reusable. |
| Issue criterion or tolerance | Acceptance stale; changed executable oracle also invalidates execution. |
| Numerical source, compiled header or scientific harness | Execution stale. |
| Dataset, compiler, MPI configuration or relevant environment | Execution stale. |
| Runner, evidence integrity logic or relevant framework dependency | Relevant evidence invalidated and requalified. |
| Missing, modified or mismatched artifact/log | Reuse refused. |
| Fresh failed/interrupted attempt after PASS | Old PASS unavailable as the new attempt's qualification. |

### Compatibility

Version new receipt/configuration formats. Read old evidence according to the
contract it actually recorded; do not infer a narrower dependency scope from an
old broad hash. First-use migration may conservatively require new execution.

Migration must be inspectable, preserve original artifacts and avoid in-flight
candidate changes. Installer updates preserve project ledgers, owner decisions,
communication revocations and standing scientific criteria. Rollback must select
a compatible framework/configuration pair without rewriting immutable evidence.

## 10. Work package G: prove the whole lifecycle

Use the upstream project's existing disposable-project tests. Extend an existing
integration suite rather than adding another testing framework. The deployed map
names candidate suites including `test_execution`, `test_runtime`, `test_ralph`,
`test_self_improvement`, `test_parity_integration`, `test_workflow_recovery` and
`test_closeout_doctor`; confirm their actual upstream paths and collection first.
These names are navigation hints, not a claim that the tests were run. [E9]

Build one representative lifecycle with controllable test commands and simulated
provider responses:

1. Prepare a bounded scientific issue with fixed acceptance and real fixture
   source/input identity.
2. Make optional communication unavailable without changing authorization.
3. Capture implementation and independent review through the supported adapters.
4. Correct one malformed report; confirm only the repaired warning disappears.
5. Start verification, exercise waiting, then interrupt execution externally.
6. Confirm non-PASS interruption, preserved logs and no productive iteration loss.
7. Resume with unchanged inputs and finish the entire configured fixture suite.
8. Apply a non-semantic documentation correction; obtain targeted current review
   and rebind unchanged execution where the new dependency rules permit.
9. Collect all closeout omissions, complete them and close the issue exactly once.
10. Record available metrics, leave human reflection pending, and carry a repeated
    advisory deferral into the next closeout.
11. Select, prepare and dispatch the next scientific issue without clearing the
    process backlog or renewing an unchanged deferral.

Also run deliberately invalid variants: changed oracle, unauthorized operation,
stale approving review, wrong artifact hash, failed scientific command, lost
input, unrelated waiting process and incompatible legacy receipt.

**Acceptance:** the valid lifecycle reaches the next scientific dispatch; every
invalid variant is rejected at the relevant boundary with a useful explanation.
Fixtures establish framework behavior only, not MITgcm qualification.

Discover and use the upstream repository's existing test, lint, build and
installer-validation commands. Record the exact selected command, absolute
working directory and result in each implementation brief. Do not invent commands
or add tooling just to satisfy this plan.

## 11. Release and runoff-host recovery

### Upstream release boundary

- Release the smallest independent liveness/evidence repair first.
- Run upstream regressions plus install/upgrade tests for a fresh project and a
  project with legacy evidence. Use simulated providers for ordinary tests.
- Opt-in live runtime qualification must have existing authorization and must not
  send unsolicited messages or start paid work.
- Document changed policy, receipt compatibility and safe rollback.
- Deploy larger scheduling/dependency changes between issues. A blocker repair
  needed mid-issue requires an explicit runtime compatibility assessment.

### Separate handoff to the runoff project

These actions require a later authorized task on the host holding MITgcm and the
original runtime records; they are not part of editing the upstream repository.

1. Establish the exact RUNOFF-040 source state, original baseline, selected
   review events, current seal and latest attempt. Do not reconstruct approval
   from narrative summaries.
2. Preserve the interrupted attempt and use existing recovery/packet tooling.
   If evidence is missing, obtain the necessary new review rather than fabricate it.
3. Check the actual executor's lifetime and process-group behavior against the
   full suite. Fix the demonstrated external termination cause; do not assume
   increasing a per-command timeout fixes a parent execution limit.
4. Freeze framework, policy and candidate changes during acceptance. Keep Slack
   disabled. Use one named final owner and the complete configured suite.
5. Close RUNOFF-040 only after readiness, full qualification and receipt checks
   pass on the actual candidate.
6. Resume bounded scientific work in this order:
   - RUNOFF-008/016: tracer and conservation evidence, including MPI tendencies.
   - RUNOFF-014/029: freshwater formulation, nonlinear/lagged time levels and
     temperature/salinity/tracer time modes.
   - RUNOFF-011: prioritize LLC, open boundaries, restart and decomposition
     qualification from the actual testbed inventory.
7. Keep diagnostics/documentation attached to those deliverables. Retain
   subsurface discharge in scope without making it a prerequisite for validating
   the existing surface package.

No item above authorizes an upstream MITgcm pull request.

## 12. Pilot, stop conditions and completion

Use the next three bounded runoff closures as an operational pilot. Collect from
existing records rather than adding a new dashboard or a measurement gate:

| Measure | Interpretation |
| --- | --- |
| Capabilities or qualification gaps closed | Primary delivery result; cite scientific acceptance evidence. |
| Science versus procedural-repair effort | Separate observed durations, estimates, overlaps and unmeasured coordination. |
| Re-review with unchanged scientific code | Distinguish necessary oracle/contract review from administrative churn. |
| Suite reruns and invalidation reason | Identify avoidable reruns without assuming every repeat was unnecessary. |
| Waiting-only productive iterations | Should be zero; waiting still consumes wall-clock resources. |
| Cost coverage | Report measured usage and unknown components separately; never total unknown as zero. |

Do not sum overlapping self-reported losses into a supposedly measured total.
Compare like-for-like evidence where available; differently scoped scientific
issues do not establish a precise causal savings percentage.

If the same procedural dispute survives two correction rounds, use the existing
diagnosis checkpoint. Decide whether it invalidates scientific acceptance, blocks
the next operation or can be deferred. Do not automatically commission another
general-purpose guard. A correctness blocker stays blocking; an advisory finding
must not acquire blocking status just because it recurs.

Honor actual owner spending/time limits. Do not quietly reinterpret nominal
expectations as hard authorization or rely on a work-iteration counter to bound
cost. If resources are exhausted, retain an honest partial handoff.

### Definition of done

- Upstream gaps are distinguished from fixes already deployed locally.
- Verification outcomes are truthful and consistent across evidence consumers.
- Advisory process debt cannot monopolize selection, preparation or dispatch.
- Durable deferrals survive unrelated closeouts and reopen on relevant triggers.
- Waiting neither burns productive iterations nor strands the coordinator.
- Structured handoffs and closeout diagnostics agree with acceptance gates.
- Dependency mutation tests demonstrate both safe reuse and required invalidation.
- Existing scientific safeguards, authorization and immutable history remain intact.
- A complete framework lifecycle reaches the next scientific dispatch.
- Release/deployment evidence and the separate runoff recovery handoff are clear.

Framework implementation, framework validation, successful deployment and improved
scientific delivery are four distinct claims. Report each only when demonstrated.
The upstream change need not wait for all three pilot closures to be released;
operational effectiveness remains pending until those observations exist.

## Evidence index

All links below refer to the installed runoff snapshot, not upstream ESX HEAD.
Read the linked owner and its consumers before porting a mechanism.

- [E1: RUNOFF-030 retrospective](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/devel-loop/self-improvement/assessments/retrospectives/4f6213927602650f864964164371357e4864d69e8535df35205ddc53f44fb0a7.json#L12-L169)
- [E2: notification outage evidence](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/devel-loop/self-improvement/open-ESX-team-issues.md#L434-L465)
- [E3: RUNOFF-013 scientific-evidence findings](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/devel-loop/self-improvement/assessments/2026-10-05-runoff-013/assessment.md#L110-L153)
- [E4: interrupted RUNOFF-040 verification](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/devel-loop/self-improvement/open-ESX-team-issues.md#L819-L905)
- [E5: RUNOFF-040 implementation and acceptance](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/open_issues.md#L672-L697)
- [E6: acceptance and inventory boundaries](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tools/esx/project.py#L112-L263)
- [E7: verification fingerprints and outcomes](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tools/esx/verify.py#L47-L214)
- [E8: deployed framework regression tests](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tests/esx/test_framework_fixes.py)
- [E9: framework owners and upstream test routes](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/docs/esx_framework_map.md)
- [E10: final verification status, receipts and reuse](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tools/esx/final_verification.py#L126-L215)
- [E11: retrospective debt and recurrence implementation](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tools/esx/team_retrospective.py#L22-L202)
- [E12: scheduler enforcement](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tools/esx/loop_gate.py#L539-L659)
- [E13: Stop-hook waiting and iteration advancement](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tools/esx/ralph_stop.py#L582-L648)
- [E14: structured handoff and recovery contract](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/devel-loop/recovery.md)
- [E15: receiving-project scientific configuration](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/esx/project.json)
- [E16: nominal budget implementation](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/tools/esx/team_budget.py#L1-L30)
- [E17: scientific review and scope policy](https://github.com/ifenty/MITgcm_new_runoff/blob/9577fde/.claude/ESX-team/ARCHITECT.md#L50-L155)
