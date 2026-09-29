# Measured self-improvement

Every validated completed, partial or blocked iteration creates retrospective
debt. Selection, preparation and retained non-probe dispatch require that debt to
be cleared. An empty scientific queue cannot bypass it. Stop/cancellation records
the debt without extending a time or money allocation.

## Close the feedback loop

After `python3 tools/esx/loop_gate.py --check-done`, record coordinator cost
([record-arch](../team_operations.md#coordinator-arch-cost)), then:

```sh
python3 tools/esx/loop_gate.py --draft-retro
```

Review `devel-loop/loop_state/retrospective-draft.json`; preserve its identity,
accounting reference and measured block. Save the reviewed result as
`devel-loop/loop_state/retrospective.json`, then run:

```sh
python3 tools/esx/loop_gate.py --check-retro
python3 tools/esx/loop_gate.py --next
```

The draft is `schema_version` 3; accepted schema-2 records stay valid and a
schema-2 submission is still accepted unchanged (it may not carry confirmations).
Describe each problem (a defect) using category, summary, evidence and integer
minutes_lost. Each solution indexes a problem and either files it, defers it with
a substantive reason and open process owner, or cites a closed implemented
process issue. Unpublished fixes stay open with an Implementation-Reference. A
verified-effective claim additionally needs hashed, comparable before/after
measurements showing the stated improvement. Missing cost observations are
explicitly unknown.
`measured.cost_scope` states whether coordinator cost is included; cite it rather
than presenting dispatched-agent `cost_usd` as the iteration's total.

Record an approach that was tried deliberately, worked and should be repeated in
`confirmations`, not as a zero-cost problem. Each confirmation carries category,
summary and evidence (at least 20 characters each) and no minutes_lost or
solution. An empty problems list needs an evidence-based explanation: either a
`no_problem_reason` of at least 60 characters or at least one confirmation whose
evidence is at least 60 characters. Recurrence scheduling counts problems only.

Use `carry_forward` for new brief rules. Repeated rules are flagged for promotion
into [the standing rules](../loop_rules.md); retire rules once code enforces them.
Repeated problems owned by the same open issue in two of the last three reflections
block further unrelated work until a measured fix or explicit one-closeout deferral.
Use `python3 tools/esx/self_improvement.py plan` and `followup --help`.

Accepted reflections are immutable in runtime history and archived with their
accounting under `assessments/retrospectives/` for version control. Include these
archives in ordinary authorized project commits. Existing legacy records remain
identifiable; no missing historical costs or start receipts are fabricated.

## Process issue ownership and evidence

Keep scientific issues in the root open/closed ledgers and process issues in
[open-ESX-team-issues.md](open-ESX-team-issues.md) and
[closed-ESX-team-issues.md](closed-ESX-team-issues.md). Their fenced templates define
required fields. All anchors use actual repository paths; Python symbols may use
`path::symbol`. The generated [process changelog](process_changelog.md) has one
source of truth: the closed process ledger.

```sh
python3 tools/esx/self_improvement.py check
python3 tools/esx/self_improvement.py index
python3 tools/esx/self_improvement.py inspect --family team --issue TEAM-AREA-001
python3 tools/esx/process_evidence.py --help
python3 tools/esx/self_improvement.py promote --help
```

Validation receipts bind successful executed commands, output hashes and source
hashes. A closed implementation must name a reachable Git commit containing those
source bytes. Mere prose, an uncommitted object, failed checks, directories and
outside-repository evidence cannot qualify it. The migration manifest only admits
exact explicitly frozen legacy records. A new project starts with none.

Promotion previews complete ledgers, validates them, checks expected source hashes,
then applies under a lock with original-byte archives and a durable journal. Repeat
requests are idempotent. `self_improvement.py recover` completes an interrupted
transaction; `recover --rollback` restores originals. Concurrent edits are refused.
Scientific promotion uses `loop_lifecycle.py promote` and the full scientific gate;
without it, `loop_gate.py --check-done` performs the move itself on acceptance.

Administrative process ledgers, generated indices and prose/data assessment files
are excluded from costly candidate/documentation signatures, but their current
integrity is checked before cached evidence can pass. Normative instructions,
Python/shell witnesses, test registration and anything explicitly declared as
scientific source/test/configuration stay in scope. Put runnable witnesses under
configured `test_paths` when they affect scientific acceptance, and register them
before sealing or reviewing the candidate. Configuration comments remain significant.

The installer/upgrader preserves project-owned ledgers, archives and standing rules.
The framework master supplies the executable controls and blank starting forms.
