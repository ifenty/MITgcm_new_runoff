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
