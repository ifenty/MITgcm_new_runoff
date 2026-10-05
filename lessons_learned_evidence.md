# Lesson evidence

One detailed entry per stable ID. Include counterexamples and the cost of being wrong.

```markdown
## LESSON: <Title> [LL-001]

**Date Identified**: <UTC ISO timestamp>
**Confidence**: <tentative / supported / strongly supported>

### Lesson and applicability
<General principle and conditions>

### Evidence
<Exact command, inputs, source/environment identity and measured result>

### Limits and counterexamples
<What the evidence cannot establish>

### Recommended action
<How to apply or validate it>
```

## LESSON: Dispositions and docstrings drift when regenerated from templates [LL-001]

**Date Identified**: 2026-09-30T06:00:00Z
**Confidence**: supported

### Lesson and applicability
Across correction rounds the rule set grew (42 -> 44 -> 46 rules). Disposition reasons and function docstrings produced from fixed templates kept stating the old scope. Write reasons from the current source (the function docstring plus the rule ids it actually emits, and counts from the rule table), and keep a test that fails when a rule function's docstring omits an emitted rule id.

### Evidence
RUNOFF-001 round 2: both reviewers rejected on documentation accuracy only. Reproducer devel-loop/loop_state/diag_docstring_rules.py exited 1 (_check_structure omitted P02, S07, S09; _check_timeseries omitted D09, P02). After the round-3 rewrite and tests/runoff/test_docstring_rules.py, it exits 0 and reviewers confirmed 18 spot-checked dispositions.

### Limits and counterexamples
The docstring test is one-directional (a docstring may name delegated rules). Source-derived reasons are only as good as the docstrings they quote.

### Recommended action
Regenerate the documentation plan from source every round; never carry template text across rounds.

## LESSON: Tools-disabled probes cannot qualify role capability [LL-002]

**Date Identified**: 2026-09-30T06:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
ESX 1.5.0's probe ran tools-disabled turns and passed while every retained-role Bash call was denied (ESX-002). Three more kit defects surfaced only under real dispatch: permission_denied events crashing the adapter (ESX-001), provider overshoot failing completed turns, and review context exceeding the 131,072-byte argv limit. All four were fixed upstream (ESX-Team 1.5.1-1.5.6).

### Evidence
Bob session a7e61b17 turn 3cc0d65c: permission denials for pwd and python. Richard round-3 launches: E2BIG at a 152,783-byte argv string. The live probe added in 1.5.1 (allowed plus denied witness) passes after each upgrade (probe-152 ... probe-156).

### Limits and counterexamples
The live probe checks Bash permissions only, not other role tools or large-context dispatch.

### Recommended action
Run agent_runtime.py probe after every upgrade and settings change. Report kit defects upstream with session and event IDs.

## LESSON: Cite MITgcm source for runtime-behavior claims [LL-003]

**Date Identified**: 2026-09-30T06:00:00Z
**Confidence**: supported

### Lesson and applicability
Reviewer B found six imprecise statements about exf, exch2 and cal behavior across rounds 1-4: yearly midpoints, where exch2 prints the global map, climatology repeat, the per-update read count, first-time vs bound offsets, and exf -12 January start. Each cost a correction round.

### Evidence
RUNOFF-001 Richard B (12879e9b) must-fix lists, rounds 1-4, each citing lines such as exf_set_fld.F:184-242, w2_eeboot.F:75-93 and exf_getffieldrec.F:152-190.

### Limits and counterexamples
Source citations drift with upstream MITgcm changes; cite routine names as well as lines.

### Recommended action
Before review, check each behavior claim against the live source and record the citation in the text or the disposition.

## LESSON: Declare the grid kind; do not infer it from geometry [LL-004]

**Date Identified**: 2026-10-02T00:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
The target-table builder first chose neighbour connectivity automatically from grid geometry. Each heuristic failed silently on some layout: cs32 with blank tiles hiding every mismatched seam (192 links lost), LLC-like stacked lat-lon facets (seam links lost), blank tiles at the wrap column, polar rows under corner matching. Geometry cannot distinguish an exch2 mosaic with blank tiles from a lat-lon block.

### Evidence
RUNOFF-009 Richard B (9e7ef5a1) must-fix lists, rounds 1-4, with verification records 2442fb8f, a543755b, 0682223540 and a21e7c51; diagnosis checkpoints diagnosis-RUNOFF-009-r2.json and -r4.json. After the design changed to a declared kind (latlon or exch2, default exch2 with data.exch2) with exact-or-refuse checks, round 5 was approved by both reviewers.

### Limits and counterexamples
Three documented non-detections remain for constructed grids (lone triangle, apex that is another cell's SW corner, polar cells wider than about 45 degrees). No LLC grid output was available for a direct test.

### Recommended action
RUNOFF-004 (the Fortran reader) must take tile placement from exch2/mdsio variables, never from geometry. Test any layout logic with blank tiles.

## LESSON: Check build link targets before claiming coverage; serialize oracle runs per experiment [LL-005]

**Date Identified**: 2026-10-03T07:00:00Z
**Confidence**: supported

### Lesson and applicability
A verification experiment can carry its own copy of a model or package routine in `code/`. genmake2 then links that copy into the build, and the edited routine in `model/src` or `pkg/` is never compiled there. Coverage claims must rest on the build's link target, not on the package being "compiled and used". Separately, all input variants of one experiment share its build directory, so concurrent oracle runs of the same experiment overwrite each other's build.

### Evidence
RUNOFF-012:
- **The false claim:** Richard B (round 0) proposed `tutorial_global_oce_latlon` as compiled-out ptracers coverage. Bob found that `build_esx/ptracers_apply_forcing.F` links to `../code/ptracers_apply_forcing.F`. Both reviewers confirmed this in round 1, and `tutorial_advection_in_gyre` (linked to `pkg/ptracers`) replaced it.
- **Scope of the trap:** a search of every `verification/*/code*` directory found five experiments with local copies of hooked routines.
- **The build collision:** Richard A (round 0) discarded his first evidence after running the focused suite and `lab_sea input -mpi 2` at the same time.

### Limits and counterexamples
A local copy that contains the same hook would be covered. The check is per routine and per experiment.

### Recommended action
- Cite coverage with the link target: `ls -l build/<file>.F`.
- Keep a list of experiments with local copies in docs/verification_matrix.md.
- Run oracle commands for a given experiment sequentially.


## LESSON: Do not edit an inventoried document after its report is sealed or approved [LL-006]

**Date Identified**: 2026-10-04T18:40:00Z
**Confidence**: strongly supported

### Lesson and applicability
A sealed documentation report binds the whole inventory, not just the files an issue meant to change, and `validate_report` requires `report.candidate == digest(snapshot(root))`. Independently, a reviewer's `candidate_signature` is sampled at the end of its turn. So an edit to any inventoried document after sealing can invalidate the seal, strand a reviewer's signature, or both — regardless of how small the edit is or whether a reviewer called it non-blocking. Reverting is not a symmetric undo. Route post-approval findings to `open_issues.md`, `lessons_learned.md` or the ESX ledger, none of which are inventoried.

### Evidence
- **What I did:** after both reviewers approved RUNOFF-004, I took review A's explicitly non-blocking item — a one-line dangling cross-reference in `docs/verification_matrix.md` left by correction round 1.
- **First cost:** `doc_contract.py check` on the sealed report `5d05a2d5` went from `valid: true` to `documentation report is stale`. Both reviewers had already confirmed that exact report.
- **Second cost, from the fix:** reverting restored `valid: true` but moved the live signature from `47f925ff` back to `fba754589b`. `final_verification check` then reported "1 independent approvals; 2 required", because review B's footer carried the transient value. One reviewer re-affirmation turn was spent recovering it.
- **The asymmetry:** review B established that it never actually reviewed the edited tree. Its round-1 `doc_contract check` returned `valid: true`, which is only possible pre-edit, so the edit landed between that check and its closing signature sample. The signature was the single stranded field; nothing it reviewed had changed.
- **Counterexample that bounds the lesson:** edits to `open_issues.md`, `lessons_learned.md`, `lessons_learned_evidence.md` and `devel-loop/self-improvement/` left both the seal and the signature untouched, verified after each edit. These are the safe places to record a late finding.
- **Cost of being wrong:** one reviewer turn, plus the risk of a reviewer re-opening settled work to explain a refusal that has nothing to do with the work.

### Correction
- Take optional documentation fixes inside the round that seals them, or defer them to the next issue that edits the file.
- After any edit late in an iteration, re-run `doc_contract.py check` and `project.py signature` and compare against the approving footers before assuming the approvals still hold.

## LESSON: A matching-digit oracle cannot see a misplaced target [LL-007]

**Date Identified**: 2026-10-04T18:40:00Z
**Confidence**: strongly supported

### Lesson and applicability
`compare_results.sh` compares monitor statistics. Moving runoff from one wet cell to another conserves mass exactly, so the global statistics barely move and the threshold cannot resolve it. A digit threshold therefore qualifies *how much* runoff was applied, never *where*. Any claim that an oracle covers placement needs a cell-exact comparison of the applied field.

### Evidence
- **Measured by review A on `b8251cd1c`, cs32, 4 processes:** target entry 1035 moved from global cell 5247 to 5248 — one cell in x, across the facet 2/3 boundary, flux 3.714e-2 m³/s (≈1st percentile). The two cells' `rA` are *bitwise equal*, so `RNF_areaTol` (1e-4) is blind, and the fractions still sum to 1.
- **Result:** the run ended normally with no `RNF` message, and `compare_results.sh` reported **10 matching digits against the 10 required — a pass with zero margin**. `cg2d_init_res` moved 1.062e-10 absolute, 4.103e-11 relative.
- **What did see it:** a cell-exact comparison of the applied `EXFroff` field against an independent float64 reconstruction of `Σ_s flux_s·frac/rA` flagged it immediately — `extra cells = 1`, `missing cells = 1`, relative error 1.0 — with global mass still exactly conserved, which is precisely why the digits did not move.
- **Not a contrived case:** 47 of the 1189 cs32 targets have a global-index neighbour that is wet, not already a target, and within `RNF_areaTol` in area.
- **Why a tighter tolerance does not help:** the two cells' areas are bitwise equal, so no area tolerance separates them. The schema's own `target_lon`/`target_lat` do: for entry 1035 they match cell 5247's `XC`/`YC` exactly while cell 5248 lies 172° of longitude away.
- **Cost of being wrong:** a placement regression ships silently, and at 2 km production scale with 10⁵–10⁶ sources the blindness scales with the number of sources while the cell-exact check does not.

### Correction
- RUNOFF-033 promotes the cell-exact oracle into the configured suite and adds an init-time coordinate check.
- State the oracle's blindness wherever the matrix claims placement coverage, rather than letting a PASS imply it.

## LESSON: A discovery glob needs an explicit scope predicate that reports its out-of-scope matches [LL-008]

**Date Identified**: 2026-10-04T18:40:00Z
**Confidence**: supported

### Lesson and applicability
Discovery by name pattern silently equates "matches the pattern" with "is in scope for this model". A new input directory is therefore enrolled in every test whose glob it happens to match, including tests that cannot judge it. The durable fix is a scope predicate in the test that reports out-of-scope matches explicitly; relying on an author to grep for matching globs is not enforced and will not hold.

### Evidence
- **What happened:** `tests/runoff/lab_sea_runoff_timing_check.py` discovered cases with `glob("input.rnof_*")`. Creating `lab_sea/input.rnof_sp_const` for the sparse oracle enrolled it in that check, which models only the dense `pkg/exf` path — `Case()` reads `data.exf` settings to predict held records and weights. The sparse case has a blank `runoffFile` and takes its runoff from `pkg/rnf`.
- **How long it survived:** five focused-suite executions under four owners, two independent reviewers and two rounds of must-fix items. It failed only at Arch's final verification, as `FAIL input.rnof_sp_const … monitor output has 48 runoff records`.
- **Why nobody caught it:** the scientific suite was in nobody's assignment. Bob was not assigned it, and both reviewers recorded in their limits that they did not run it. All three were explicit, so the gap was visible in the record and still reached final verification.
- **Why the message misled:** the check reported `len(series["time"])`, the count of monitor *times*, as a count of runoff records. Review A measured the cause: `pkg/exf/exf_monitor.F:190` writes `_runoff` statistics only when `runofffile` is non-blank — 240 `exf_runoff` lines in the dense run, 0 in the sparse one, 48 `exf_time_sec` lines in both.
- **Completeness check:** the only other `glob(` calls in the test tree, `refusal_check.py:700` and `test_convert.py:218`, are over run-output patterns rather than input case directories, so this was the sole glob enrolling verification input cases.
- **Cost of being wrong:** one correction round, one failed 33-command scientific suite (~50 minutes), and a full suite re-run.

### Correction
- `sparse_case()` is the predicate: it discriminates on configuration intent (`data.rnf`, `useRNF`), not on the name pattern, and reports a match it cannot judge as `SKIP` with the reason and owning issue.
- A skip counts as neither a pass nor a failure, it is recorded under `skipped` in the JSON rather than in `results`, and a guard makes a run of only skips exit non-zero — verified by execution, so the check cannot pass vacuously.

## LESSON: A closed hole needs a case that catches its reopening; a new guard needs a demonstrated failure [LL-009]

**Date Identified**: 2026-10-05T10:30:00Z
**Confidence**: supported

### Lesson and applicability
A measurement establishes that code is correct now. A test establishes that it stays correct. The two are routinely conflated when a fix is accompanied by a careful measurement, because the measurement feels like verification — and it is, of the present tense only. Two shapes are especially prone to it: a one-token fix applied to several sibling call sites where only one receives a case, and a guard reachable only after an earlier check passes, where reverting the earlier one leaves every existing case green and the later guard never runs.

### Evidence
- **Instance 1 — the accumulation-order premise.** `applied_field_check.py` compares bitwise (`--rtol 0`), licensed by the premise that `rnf_fields_load.F:75-77` accumulates in the file's table order. Review A measured the premise true on the real binary with a three-term order-dependent cell. But both committed sparse files have at most **one** target entry per cell (lab_sea 7 on 7, cs32 1189 on 1189), so no enrolled case sums more than one term: a future reorder of the per-tile list construction would void the premise while all four enrolled cases still passed bitwise. Disclosed in the matrix and the oracle docstring; the permanent case filed against RUNOFF-005.
- **Instance 2 — the `--min-dumps` guard.** The zero-sample PASS review A found was closed by a range check in `main`. A direct `check_case(..., min_dumps=0)` would still compare zero dumps. `main` is the only caller in the repo, so this is bounded — recorded, not requested.
- **Instance 3 — the non-finite `target_cell_area`.** Commit `016fdee5d` fixed the same NaN fail-open in **two** sibling comparisons. `target_coords_nan` was enrolled for the coordinate one; nothing sets `target_cell_area` non-finite. The existing `cell_area` case is a finite 1.01× error, and the coordinate check is reached only *after* the area check passes — so reverting the area comparison to `.GT.` leaves both cases green and no configured command notices. Correct today (review A measured `area_nan` refused in round 1) and covered checker-side by `T09-cell-area-nan`, but the model-side backstop, which exists precisely for files that never saw the checker, is held by nothing. One `file_case` closes it; filed against RUNOFF-017.
- **The counterexample that shows the standard is reachable:** `target_coords_nan` was enrolled in the same round as its fix, and review B verified it cannot go green through the skip path — both by confirming the forbidden skip-warning string is text the model really emits, and by noting its required messages can only be produced by the check firing. That is what a closed hole looks like when it is done.
- **The demonstrated-failure half:** the new oracle was required to be shown failing on a perturbed input before it was accepted — lab_sea 48 extra / 48 missing at relative deviation 1.0, cs32 entry 1035 at 10/10. A test never observed to fail carries no information about what it would catch. Review A then went further and showed the *control* itself fails when fed a blind model's field, so the control is not vacuous either.
- **Cost of being wrong:** a reopened hole is invisible until it ships. The NaN fail-open that started this round was itself build-dependent — accepted at the project's own `-O0`, refused at `-O3` — which is exactly the kind of regression a suite is supposed to hold and a measurement cannot.

### Correction
- When a fix touches sibling call sites, enrol a case per site, not per fix.
- When a guard sits behind an earlier check, ask what reverting the earlier check would do to the later one's coverage.
- State plainly in the record when a measurement closed a *correctness* question but not *regression coverage*, and file the permanent case rather than letting the measurement stand in for it.

## LESSON: Replace an unachievable criterion by measurement, and record what the replacement does not cover [LL-010]

**Date Identified**: 2026-10-05T13:30:00Z
**Confidence**: supported

### Lesson and applicability
Two failure modes meet here. An acceptance criterion that cannot be met invites quietly redefining it — most easily by generating the reference from the code under test, which converts a cross-path oracle into a reproducibility check while leaving every surface reading unchanged. And the claim "this criterion is unachievable" is itself a claim, which can be wrong in either direction: too broad (it holds for some cases) or unfounded (a defect is hiding behind it). Both are resolved the same way, by measuring rather than arguing — and the replacement's blind spot must be written into the governing contract, not only into the test that implements it.

### Evidence
- **The criterion.** RUNOFF-005's stated acceptance was that the timed lab_sea sparse cases match their dense references to the `compare_results.sh` digit threshold. Measured: `cg2d_init_res` reached only 4, 16, 3, 16 and 4 matching digits for daily, month, month1, clim and yearly against the 10 required.
- **The decisive measurement, by review A.** Independently of the implementer, it capped the dense-vs-sparse forcing difference offline at **at most 1 ulp** (max 2.0e-16, ~88% of values bitwise identical, identical non-zero cell sets in every record). Then it ran one case twice from the same binary — unperturbed, and with every `runoff_flux` moved by exactly one float64 ulp, nothing else different: **16 digits, then 4.** A 1-ulp forcing perturbation alone reproduces the figure attributed to the dense/sparse difference. The criterion is therefore unachievable in principle for any implementation computing `flux·frac/rA` in float64 rather than reading a precomputed float32 m/s, and a masked defect is excluded.
- **The claim was too broad, and measurement caught that too.** `month` and `clim` are numerically identical to their dense runs in *every* monitor variable — 16 digits. They meet the original criterion. Only three of five cases needed the replacement; the implementer had generalised to five.
- **What the replacement does not cover, stated because a reviewer insisted:** the digit oracle compared the whole model response; the replacement compares the applied runoff field and the record choice. A `pkg/rnf` side effect outside the exf `runoff` array specific to the timed path would be invisible to all three instruments, and a self-referential reference would be content. That coverage survives only in the two constant cases, whose references remain byte copies of their dense twins.
- **Where it had to be written.** `esx/project_profile.md` — the governing contract — still stated the superseded oracle as both the tolerance rationale and a completion criterion, and was *outside* the documentation inventory precisely because it was unchanged, so no disposition would have flagged it. It is also what a later agent or the closure gate consults. Review A required it there, not only in the matrix.
- **Cost of getting this wrong:** the five own-references are sharply sensitive to the sparse path (a 1-ulp change is 16 → 4 digits FAIL), so they are not weak tests — they are simply not *cross-path* tests. Had the substitution gone unlabelled, the project would have retained a criterion that reads as dense-vs-sparse agreement and measures something else.

### Correction
- Measure the impossibility before accepting it, by the smallest-perturbation test; then check whether it holds for every case or only some.
- Label a self-referential reference as one, in the governing contract and in the upstream-facing documentation, with what it does and does not establish.
- Keep the cross-path instrument wherever it still works — here, the two constant cases — and say that is where it survives.

## LESSON: Establish build provenance before trusting a figure, and bytes before reusing evidence [LL-011]

**Date Identified**: 2026-10-05T15:10:00Z
**Confidence**: supported

### Lesson and applicability
Two forms of the same error. A test figure carries no information unless the binary that produced it postdates the source it is supposed to be testing — and the tempting shortcut, "the change was comment-only so the behaviour is identical", answers a different question: it establishes behaviour, not the provenance of the number. Symmetrically, a reviewer reusing its own earlier evidence must show that the bytes that evidence depended on are unchanged, and a comparison of reference *sets* will not do it, because a newly-cited file is indistinguishable from a modified one.

### Evidence
- **The figure.** RUNOFF-005 reported `refusal_check.py --mpi 2` at 54 of 54. Checking mtimes, the implementer found `lab_sea/build_esx_mpi2/mitgcmuv` at 05:18, predating its own 08:56 edit to `rnf_time_setup.F`. The edit was comment-only, so the behaviour was in fact identical — but the number had been produced by a binary that could not have contained the change. It rebuilt rather than argue the premise: 11 digits PASS, binary at 10:05:43, and the figure re-measured to 54 of 54 on a binary postdating all source. Review B then verified both halves independently — the mtime ordering (both binaries now after the 08:56:41 newest source) and a fresh sealed execution of the contested command on the 10:05:43 binary.
- **It was caught unprompted.** Nothing in the brief asked for mtimes. The implementer checked them *before* running, having been told that a 4-of-4 from a stale build is worth less than nothing because it displaces the real result.
- **The reviewer's symmetric error.** Review B's round-3 reuse argument diffed the reference-hash maps of two sealed reports and reported an empty changed set. In round 4 the same method flagged `MITgcm/pkg/rnf/rnf_init_fixed.F` as changed, contradicting "no Fortran moved" — it had been newly *cited* by two new dispositions, not modified. Round 3's conclusion was correct and its basis was not. The defensible form it adopted: separate added, removed and moved, then confirm bytes with `git diff --quiet a81f290f0 -- pkg/rnf/` and compare the live sha256 against the `source` component the report records.
- **Why it bit here and not earlier:** `placement_probe.py` runs through `experiment_run_no_compile`, so it never rebuilds. A probe reporting on a stale binary is silent about the staleness by construction.
- **Cost of being wrong:** a figure from a stale build is worse than a missing figure, because it occupies the place where the real measurement would have gone and reads as coverage. In this issue the stale figure happened to be correct; nothing about the report distinguished that from the case where it is not.

### Correction
- State build and source mtimes beside any figure that depends on a compiled binary, and check the ordering before the run.
- Rebuild rather than argue from the nature of the change.
- To reuse earlier evidence, confirm the bytes it rests on with a direct diff against a named commit; never infer it from a comparison of reference sets.
