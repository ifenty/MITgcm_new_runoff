# esx-fix.md implementation: reconciliation and port handoff

Implemented 2026-10-09 in this project's copy of the kit (`tools/esx/`), on the
owner's sequence: validate here with real loops first, then port to
`ifenty/ESX-Team`. `esx-fix.md` itself says to implement upstream; this record is
what makes the later port a reconciliation rather than a copy.

## The witness this was measured against

ESX-Team's own regression suite (`run_tests.py`, 30 modules), copied to `/tmp`
and run without editing the upstream checkout:

| tools under test | failing modules | failing tests |
|---|---|---|
| ESX-Team 1.6.3, pristine | 0 of 30 | 0 |
| this project at `56b2545` (every local fix 10-05 → 10-09) | 11 of 30 | 51 |
| after package A reconciliation (`871d8b3`) | 4 of 30 | 8 |
| after package C (`433e345`) | 5 of 30 | 7 |
| final tools (`d2db659`) | 5 of 30 | 7 — exactly the seven below, nothing else |

Every remaining failure is a deliberate, plan-backed change listed below. This
project's own `structural` suite never ran that suite, which is how 51 failures
accumulated unseen.

## What each package did

| package | commit | disposition |
|---|---|---|
| A — reconcile | `871d8b3` | done; see below |
| B — verification outcomes | `9afef60`, `871d8b3` | done |
| C — process triage non-preemptive | `433e345` | done |
| D — liveness | `56b2545` (earlier) | covered; no new code |
| E — handoffs and closeout | `f049458`, `d2db659` | done |
| F1 — framework tests out of scientific scope | `9da9318` | done |
| F2/F3 — narrow the fingerprint, split identities | — | **deferred** |
| G — whole-lifecycle fixtures | — | **deferred to the port** |

**Deferred, and why.** F2/F3 is graded by the plan itself as a higher-risk change
with its own review and release boundary, and an under-inclusive dependency
manifest would silently accept stale scientific evidence. Two couplings therefore
remain: the fingerprint's framework component hashes every `tools/esx/*.py`, so any
framework edit stales all evidence; and `esx/project.json` sits whole in the
scientific inventory, so a structural-suite edit there moves the scientific
identity. G uses upstream's disposable-project harness, which lives in the
ESX-Team repository; the pilot's real closures stand in for it here.

## Local fixes reverted or narrowed by the reconciliation

- **TEAM-PAUSE-DEADLINE-CLAMP-001 reverted** (`team_budget.py` is upstream
  byte-for-byte). Its horizon rule let a turn run past an owner-authorized
  extension: 6000 s against an authorized 4200 s. Entry Blocked-By OWNER-DECISION.
- **TEAM-PREPARE-KIND-UNCHECKED-001 is a notice, not a refusal.** It caused 44 of
  the 51 failures by refusing investigations over sources they only read.
- **Completion over an unattempted notification** (introduced by
  TEAM-NOTIFY-OUTAGE-NO-BACKOFF-001's work-first ordering) is closed.
- **Package B against upstream:** termination signals are interruptions, the
  timeout message reads as a failure, `PYTEST_SUMMARY` is retained for log
  readers, and a signalled command no longer counts as completed.

## Upstream tests the port must update, each with its reason

1. `test_arch_reorient::test_refused_when_changed_target_outside_declared_targets_and_documents`
   — local `af5165f` treats an orientation's own `--map` as declared, after four
   reproductions of agents re-typing identical arguments. Upstream wants a full
   navigate. Procedure, not a safeguard: **upstream's decision.**
2. `test_dead_transport::test_reprobe_forced_each_iteration` — the reprobe demand
   is still emitted on the same trigger, reworded ("since iteration N"), but no
   longer preempts work. Plan D.
3. `test_dead_transport::test_reprobe_forced_every_n_covered_events` — same:
   non-preemptive. Plan D.
4. `test_autonomous_loop::test_required_pending_prevents_completion_until_attempt`
   — sequencing only: work-first ordering queues the end-of-loop summary one call
   earlier. Instrumented: `rc 0` with both events pending, so nothing completes
   unattempted. The invariant holds.
5. `test_verify_rerun::test_pytest_log_without_summary_is_interrupted` — asserts
   the removed log-text heuristic, which would hide a real failure (a test that
   calls `os._exit` leaves no summary) as "no verdict". Plan B.4.
6. `test_verify_rerun::test_killed_child_is_interrupted_and_gate_names_the_attempt`
   — classification now agrees (INTERRUPTED); it fails only on requiring the words
   "no test failed", the overclaim plan B.8 removes.
7. `test_parity_integration::test_recurring_owner_blocks_selection_and_deferral_expires`
   — asserts that recurrence alone blocks selection and that a deferral expires
   after one closeout: the two behaviours plan C replaces.

## Port checklist

- Port by package, not by file copy: the local commits mix project narrative
  (RUNOFF-issue citations in comments) with kit code.
- Move the guards from `tests/esx/test_framework_fixes.py` into upstream's tests,
  replacing this host's interpreter paths.
- Update the seven tests above, or reject the corresponding change.
- Re-run `run_tests.py` and the installer/upgrade tests for a fresh project and for
  one with legacy evidence; then release, and upgrade this project so
  `ESX-team-local/version` is true again.
- Effectiveness is not claimed here. The stall fix's release path and the
  claims procedure both await the pilot's real closures.
