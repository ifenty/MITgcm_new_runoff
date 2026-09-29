# ESX records and evidence schema

All timestamps are UTC ISO strings. The start timestamp identifies an iteration
and remains unchanged in done, footers and communication refreshes. State lives
under devel-loop/loop_state. Examples under esx/templates are blank forms.

## Start

--prepare writes id, title, timestamp, priority_reason, workflow, maintenance
(baseline and Arch orientation references), and pending communication. Record its
actual delivery outcome when known. Every role's orientation references the same
baseline. --check-start validates source/map/document navigation.

## Workflow

Version and execution_version are 1. execution_version is immutable across the
iteration; a workflow amendment cannot weaken this enforcement. kind is scientific_change/harness_change/documentation/investigation.
required_roles lists needed specialists/implementers/reviewers; minimum_reviewers
is 0, 1 or 2. Scientific changes require Bob and at least one Richard. review_reasons
contains applicable risk keys from Arch's contract. Any risk requires two reviewers.
final_verify_owner is arch/bob/richard. verify_signature_at_start and
numerical_signature_at_start contain measured 64-hex signatures; the latter tracks
the project's configured scientific source/test/configuration scope.

A changed decision needs workflow_amendment with previous (the complete start
workflow) and reason. Preserve measured initial signatures. The gate checks
structure; Arch judges whether the stated semantic risk matches the change.

## Done

Required: id, timestamp, outcome (completed/partial/blocked), summary, workflow,
scope_decisions, git and communication or Slack disposition. Partial/blocked work
retains the open entry and next_step. Blocked work mirrors the exact blocked_by.
Completed work passes required evidence; acceptance by --check-done then moves its
open entry, preserved byte for byte apart from heading, Status and Date Resolved, into
closed_issues.md. An entry already moved is accepted; a refusal moves nothing.
lessons lists actual active LL IDs, or an empty list when none was warranted.

subagents maps only used roles to arrays of dispatch_id and dispatch_event_id.
These refer to actual hook completions; copied scientific fields must match the
captured footer. Required roles need at least one completion. Every footer has
agent, issue_id, iteration_timestamp, correction_round and its own orientation
reference. All six roles copy the assigned correction_round as an integer: 0
for the initial dispatch and the supplied value on followups. The retained
runtime records a missing or mismatched round as incomplete, which prevents
that dispatch from satisfying closeout.

agent_continuity lists initial runtime IDs followed by replacements under bob/richard, tracks correction
rounds and unsuccessful_since_checkpoint, and records replacements with reason,
role, old_id/new_id and carried findings. After two unsuccessful rounds, diagnosis_checkpoint
uses the versioned diagnosis template with an executed reproduction, hashed
evidence, mistaken/unproven premise, bounded decision and failed-round cursor. Keep parent session IDs in
assignment/replacement records. The gate checks identities and required checkpoint
fields; Arch enforces use of resume and judges the diagnosis.

Final Richard footers contain verdict, empty must_fix, candidate_signature,
independent_check, and documentation_review. independent_check has cmd, exit=0,
executed=true, evidence (the verifier's reference), and a coverage explanation.
The receipt's actual owner equals Richard's runtime ID and was executed during
this iteration. documentation_review names the exact sealed report, status=confirmed
and substantive notes. Candidate signatures must match the current review source.
Preserve earlier reviews; replacement approvals need explicit review_supersessions
with event_id, by_event_id, reason and evidence_refs for outstanding current findings.

verification has final_owner and structural evidence; scientific changes additionally
require scientific evidence and the final_verification receipt. The latter binds
the candidate, actual reviews, documentation and measured verification environment.
The scientific evidence must execute the complete configured suite. `candidate`
contains the issue_candidates snapshot reference and original baseline binding.
Preserve the wrapper's EXECUTED/REUSED EVIDENCE result alongside references.
maintenance contains original baseline, fresh Arch orientation and sealed documentation;
map_delta exactly matches that report. Every changed Python symbol and file/module
needs a documentation disposition. Non-Python source uses its module/file contract.

Git: committed is Boolean. A true value requires a resolvable SHA; false requires
a substantive reason. Communication: status, detail and actual receipt for sent
messages. Slack may use slack_ts or slack_error. No delivery is fabricated.

## History and qualifications

A successful --check-done persists the complete validated done object, including
Git, communication, reviewer/evidence references, optional timings and deliverables.
The last matching id/timestamp is atomically refreshed when contents change;
identical repeats perform no write. Earlier history is retained.

Hook and content hashes establish local correlation and freshness. Independent
service attestation is outside this mechanism. They cannot prove an
agent understood the map, a scientific claim is true, undeclared inputs are covered,
or a configured action is authorized. Those judgments remain explicit role duties.

## Evidence packet fields

The [handoff contract](recovery.md) defines `handoff`, `closeout_pending`, exact
completion selections and structured readiness findings. Source and sealed report
references remain immutable. Orientation receipts include source, module-context,
enclosing-definition and documentation component hashes for precise recovery.
