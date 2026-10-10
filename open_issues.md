# Open issues

Fenced examples are templates and are excluded by the gate. Use stable unique IDs.
Statuses: Unresolved, Investigating, Blocked. A blocked entry requires Blocked-By:
a project issue ID, EXTERNAL or OWNER-DECISION, followed by ` — ` and an explanation.
A closed dependency prompts reconsideration; it does not automatically unblock work.

```markdown
## UNRESOLVED: <Brief title>

**Date Identified**: <UTC ISO timestamp>
**Status**: Unresolved
**UUID**: <PROJECT-ISSUE-001>
**Anchors**: <owning path::<module>; <nearest test path::<module>

### Issue or research question
<Observed behavior, expected contract and what remains uncertain>

### Evidence
<Executed command, cwd, source/input identity, environment and measured result>

### Scientific or engineering impact
<Effect on correctness, interpretation, users or resources>

### Proposed action and acceptance
<Hypothesis, bounded change/inquiry, independent oracle, tolerances and completion criteria>
```

## UNRESOLVED: Survey MITgcm verification experiments as runoff testbeds and build the test matrix

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-011
**Anchors**: MITgcm/verification/README.md::<module>; docs/verification_matrix.md::<module>

### Issue or research question
Which verification experiments can host sparse-runoff tests: grid type (lat-lon, cubed sphere, LLC), regional vs global, open boundaries, sea ice, ice shelves/cavities, free-surface and freshwater settings (useRealFreshWaterFlux, nonlinFreeSurf), forcing package (exf vs other), run cost; which have a dense runoff path usable as an oracle.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Candidates seen: global_ocean.cs32x15, global_ocean.90x40x15, global_oce_latlon (input.yearly), lab_sea, seaice_obcs, obcs_ctrl, isomip (input.icefront), offline_exf_seaice, 1D_ocean_ice_column, tutorial_global_oce_latlon.

### Scientific or engineering impact
Defines which configurations prove the package works; without it testing stays at two grids.

### Proposed action and acceptance
docs/verification_matrix.md gains a testbed table (experiment, grid, features, oracle available, cost) and a prioritized list of new input.<X> cases each tied to an issue. Acceptance: Richard confirms the feature classifications against the experiments' data files.

Carry forward from RUNOFF-012:
- Five verification experiments compile their own `code/` copy of a routine this package hooks, and so will not get the hooks: `tutorial_global_oce_latlon` (ptracers_apply_forcing.F) and four with a local apply_forcing.F, listed in docs/verification_matrix.md. Exclude them as testbeds, or patch their copies in a test variant.
- cs32 `input.in_p` already runs dense exf runoff and runoff temperature in pressure coordinates, with a reference.
- `obcs_ctrl` has only adjoint inputs.

## UNRESOLVED: Real versus virtual freshwater flux and free-surface options

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-014
**Anchors**: MITgcm/model/src/external_forcing_surf.F::<module>; MITgcm/pkg/exf/exf_mapfields.F::<module>

### Issue or research question
Sparse runoff must behave correctly under useRealFreshWaterFlux true/false, linear vs nonlinear free surface (nonlinFreeSurf, z*/r*), and the salinity treatment of each (virtual salt flux vs volume input).

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Freshwater formulation errors change sea level and salinity drift silently.

### Proposed action and acceptance
Acceptance: test cases in at least one lat-lon and one cs32 configuration for each combination; volume and salt budgets closed (RUNOFF-016).

Unblocked 2026-10-04: RUNOFF-004 closed (sparse reader, per-tile lists, placement by the `mdsio_read_field.F` arithmetic, `GLOBAL_SUM` fraction check and the exf volume flux; fork `610d4cbaf`, final verification receipt `2e11b06d`, all 33 scientific commands passing). Note the reader accepts **one constant record only**: `rnf_init_fixed.F:199-217` stops the run for `RNF_useYearlyFiles` or any `RNF_period` other than 0, naming RUNOFF-005.

## UNRESOLVED: Runoff diagnostics and monitor output

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-015
**Anchors**: MITgcm/pkg/exf/exf_diagnostics_fill.F::<module>

### Issue or research question
Diagnostics for applied runoff volume flux, heat and salt tendencies, tracer tendencies, per-cell source counts; monitor statistics for the runoff fields.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Needed for every verification check and for users.

### Proposed action and acceptance
Acceptance: diagnostics listed in available_diagnostics, filled each step, values equal the applied fields (direct check).

Scope decision from RUNOFF-012: the skeleton has no `rnf_diagnostics_init.F`. Decision 1 has `RNF_INIT_FIXED` call it, so RUNOFF-015 adds both the routine and the call.

Unblocked 2026-10-03: RUNOFF-012 closed (pkg/rnf skeleton, fork ac33291aa).

## UNRESOLVED: Refusal and negative tests for invalid runoff input

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-017
**Anchors**: docs/runoff_schema.md::<module>

### Issue or research question
Model-side refusal tests: fraction sum off, land or off-grid target, blank-tile target, unknown tracer, missing variables, wrong units/schema version, grid mismatch, sparse and dense both set, missing flux values.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Required failure behaviour: esx/project_profile.md (stop at init with an EXF/package-prefixed message naming the source).

### Scientific or engineering impact
Silent acceptance of bad input is the highest-risk failure mode (dropped mass).

### Proposed action and acceptance
Acceptance: one negative case per refusal, each stopping with the exact expected message; run by a script in tests/.

Refusals added by the RUNOFF-010 design (docs/package_design.md, decisions 2, 3, 5, 6), each needing its own negative case: `target_cell` outside `0 ≤ g < nx·ny`, including a negative index (and `target_source` out of range); a target with `maskInC = 0` beyond an open boundary; a target under an ice shelf (`kTopC ≠ 0`); `useRNF` with `SHI_update_kTopC`; `exf_outscal_sflux ≠ 1`; a dense `runoftempfile`; `runoffconst ≠ 0`; `useRNF` without `useEXF` or without `ALLOW_RUNOFF`; a blank `RNF_file`; a build without NetCDF; a restart in synchronous nonlinear-free-surface mode whose time minus one step precedes the first record.

Carry forward from RUNOFF-012:
- Configure the cs32 case (`useRNF=.TRUE.` in input.seaice) that triggers both the `runofffile` and `runoftempfile` refusals, giving "2 fatal error(s)". lab_sea cannot test `runoftempfile` because `EXF_CHECK` stops first without `ALLOW_RUNOFTEMP`.
- Refusal branches compiled but never executed: `ALLOW_RUNOFF` undefined, `HAVE_NETCDF` undefined, `useShelfIce` with `SHI_update_kTopC`, and `USE_OLD_EXTERNAL_FORCING`.

Carry forward from RUNOFF-005 (reviews A and B, correction round 4, 2026-10-05): **make the `forbid` class non-vacuous by construction, and grade its evidence honestly.** `tests/rnf/refusal_check.py` has 14 distinct forbidden literals across 54 cases. A round-4 audit found none vacuous, but the audit decays:

1. **One-line permanent fix (review B).** Assert at start-up that every `forbid` literal also appears in some case's positive `stderr`/`stderr_any`/`stdout` expectation. All six currently-unwitnessed literals are today the named positive expectation of exactly one sibling case (`runofffile`, `runoffconst`, `exf_outscal_sflux`, `useEXF_false`, `blank_RNF_file`, `fraction_sum`); **deleting or renaming any one of those six cases would silently turn its literal into an unwitnessed and unasserted forbid string** in the cases that still carry it, with nothing to notice. That is the LL-009 shape — a hole closed by audit rather than by a case — and a start-up assertion closes it permanently.
2. **The matrix reports two grades of evidence as one (review A).** Its "so none is vacuous" is true, but five of the six are `MESSAGES` entries with a **single Python definition** used both as the positive expectation and inside `no_error`, so a rewording breaks the positive case loudly *and* the two uses cannot drift — which is **stronger** than a log witness, since a witness only proves some past binary once emitted the text. The genuinely weaker member is `fraction sum is not 1`, a **duplicated raw string** (positive at `refusal_check.py:721` plus two forbid lists) whose copies can drift apart. The record currently undersells five and misses the real residual; name the one.
3. **The method's true limit is not spelling (review A).** A `forbid` can go vacuous with **no rewording at all**, if the condition that would emit the message stops being reachable in that case's setup. No literal sweep sees that. What protects against it is the positive case existing — which it does for all 14, and which item 1 would make enforced rather than incidental.

Also from review A, cheap and unrelated: anchor `placement_probe.OPEN_FAILED`'s basename (require a path separator or start-of-field before `probe.nc`) so the pattern cannot match a file merely ending in it. Unreachable today because `PROBE_FILE` has one definition driving both `DATA_RNF` and the matcher; purely a tightening.

Carry forward from RUNOFF-013 (correction round 1, 2026-10-05) — **three `RNF_NC_SERIES` items, one of them closed by measurement rather than by code:**

1. **A duplicate `RNF_trPtr` check is NOT needed: the condition is unreachable.** Review B proposed guarding against two runoff-tracer variables mapped to the same ptracer, of which the `iRnf` loop of `RNF_TENDENCY_APPLY_PTR` silently keeps the last. The "keeps the last" half is true, but the premise is not: `RNF_NC_SERIES` trims the variable name with `ILNBLNK`, which treats **only the literal space** as blank (`eesupp/src/utils.F:123-152`), so two *distinct* NetCDF names can collide on the trimmed name only through a trailing blank, and **NetCDF refuses one** — creating `runoff_ptracer_dye ` fails with `NetCDF: Name contains illegal characters` (measured 2026-10-05, netCDF4 1.7.4, libnetcdf 4.10.0). The one route that rule leaves open closes itself: a trailing **NUL** is accepted but collapsed to the same stored name, after which the duplicate name is refused with `NetCDF: String match to name in use` (same measurement, correction round 2). Distinct names therefore trim to distinct tracer names, which match distinct `PTRACERS_names` entries or none (two equal entries give `nMatch ≥ 2`, itself a refusal), so `RNF_trPtr` cannot hold a duplicate. Recorded here so the suggestion is not re-filed; the `iRnf` loop stays as defence in depth. Do **not** attach the `PTRACERS_num ≥ 2` condition to this item — that belongs to the two-matching-names refusal below. [**2026-10-09, RUNOFF-031:** `RNF_TENDENCY_APPLY_PTR` was deleted; its successor `RNF_FORCING_SURF_PTR` loops over the runoff tracers and would add both rather than keep the last. The condition stays unreachable, so the conclusion is unchanged.]
2. **The two `RNF_NC_SERIES` refusals that still have no case**, both needing another build: a name matching more than one `PTRACERS_names` entry (needs `PTRACERS_num ≥ 2`) and the `#else /* ALLOW_PTRACERS */` branch for a model compiled without pkg/ptracers. Three siblings were enrolled in correction round 1 (`ptracer_name_empty`, `ptracer_name_long`, `ptracer_too_many`), each measured passing on the committed build and failing on a mutant with its guard weakened, and correction round 2 added their at-the-bound counterfactuals (`ptracer_name_min`, `ptracer_name_max`, `ptracer_count_max`), which hold the guards back from `.GE.`; these two refusals are what is left. [**2026-10-09, RUNOFF-008:** the first of the two is reachable by input on the `PTRACERS_num = 2` build, measured once and not enrolled: with `PTRACERS_names = ('dye', 'dye')`, `useMNC = .FALSE.` and a file carrying `runoff_ptracer_dye`, the run stops with `RNF_NC_SERIES: RNF: runoff_ptracer_dye: the name matches   2 PTRACERS_names entries` and `ABNORMAL END: S/R RNF_INIT_FIXED`, while `('dye', 'dye2')` runs and applies the term. With lab_sea's default `useMNC = .TRUE.` it never gets there: pkg/mnc stops first on the duplicate name (`MNC_CW_ADD_VNAME ERROR: 'dye' is already defined`). It is not in `refusal_check.py` because that script runs every case on one binary chosen by `--mpi` and is enrolled without `--build`; see the RUNOFF-008 entry.]
3. **A missing value of `runoff_salinity` or of a tracer** still drives no case, so the per-series naming of that message is unmeasured for those two series even though seven flux cases run the same code path (six until RUNOFF-030 added `flux_above_source_max`). See the matrix refusal row. RUNOFF-030 also widened that code path: `RNF_NC_READ_ONE` now carries an out-of-range refusal with its own per-series count line beside the missing-value one, and that line too is measured for the flux only.

Carry forward from RUNOFF-033 (review A, correction round 2, 2026-10-05): **enrol a non-finite `target_cell_area` case.** Commit `016fdee5d` made the same one-token NaN fail-open fix at **two** sibling comparison sites in `rnf_init_fixed.F` — the cell-centre check and the pre-existing `target_cell_area` check — but only the first got a permanent case (`target_coords_nan`). The existing `cell_area` case is `scale_var("target_cell_area", 0, 1.01)`, a **finite** error, and the coordinate check is reached only *after* the area check passes, so reverting the area comparison to `.GT.` would leave **both** existing cases green and no configured command would notice. The behaviour is correct today — review A measured `area_nan` refused with exit 1 in correction round 1 — and `T09-cell-area-nan` covers the checker side, so what is missing is regression coverage of the model-side backstop, which exists precisely for files that never went through `MITgcmutils.runoff.check`. One line closes it: a `file_case` with `set_var("target_cell_area", 0, float("nan"))` expecting the message the model already prints, `target_cell_area differs from the cell area rA`, confirmed by review A's round-1 probe. See LL-009.

Carry forward from RUNOFF-004 (review B, correction round 1, 2026-10-04): add the **cross-rank global-count oracle**. `tests/rnf/refusal_check.py::judge` asserts that a tile-local refusal message appears in *some* rank's `STDERR` and that each rank emits one `STOP` line, but it never asserts the **value** of the `GLOBAL_SUM_INT`-ed count, and `sparse_info` always selects a land cell in the western half, i.e. rank 0 — so the zero-local/non-zero-global case has no case. Review B wrote and ran the two that distinguish a correct reduction from a lucky one, on 2 MPI ranks: `land_rank1_only`, where rank 0 owns no refused target and prints no detail line yet still prints `1 refused target(s) on all processes` and stops, and `land_both_ranks`, where each rank sees 1 locally yet both print `2`. Both passed, with no hang. Fold them into `refusal_check.py` and assert the summed value. Its receipt is `devel-loop/loop_state/scratch/ab74b9af824d5b71c/richard_refusal_mpi2.json`; the same run also covered four refusal paths that had no case (`RNF_period` set in `data.rnf`, schema major version 2.0, `constant` sampling with two records, and `runoff_flux` with its dimensions transposed). Low priority: the mechanism is proven by execution and unchanged since. Note the scratch receipt is git-ignored and local to this machine, so re-derive the cases from the description rather than relying on the file surviving.

Unblocked 2026-10-04: RUNOFF-004 closed (sparse reader, per-tile lists, placement by the `mdsio_read_field.F` arithmetic, `GLOBAL_SUM` fraction check and the exf volume flux; fork `610d4cbaf`, final verification receipt `2e11b06d`, all 33 scientific commands passing). Note the reader accepts **one constant record only**: `rnf_init_fixed.F:199-217` stops the run for `RNF_useYearlyFiles` or any `RNF_period` other than 0, naming RUNOFF-005.

## UNRESOLVED: global_ocean.90x40x15 and global_oce_latlon sparse runoff testbeds

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-018
**Anchors**: MITgcm/verification/global_ocean.90x40x15/input/data::<module>; MITgcm/verification/global_oce_latlon/input.yearly/data::<module>

### Issue or research question
Global lat-lon coverage: dense-path references and sparse equivalents in these experiments, including the yearly-forcing variant, with and without T/S.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Global lat-lon coverage beyond the regional lab_sea grid.

### Proposed action and acceptance
Acceptance: dense references and sparse=dense to the digit threshold, single and MPI, plus budget checks.

Unblocked 2026-10-04: RUNOFF-004 closed (sparse reader, per-tile lists, placement by the `mdsio_read_field.F` arithmetic, `GLOBAL_SUM` fraction check and the exf volume flux; fork `610d4cbaf`, final verification receipt `2e11b06d`, all 33 scientific commands passing). Note the reader accepts **one constant record only**: `rnf_init_fixed.F:199-217` stops the run for `RNF_useYearlyFiles` or any `RNF_period` other than 0, naming RUNOFF-005.

## UNRESOLVED: Regional open-boundary testbeds (seaice_obcs, obcs_ctrl)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-019
**Anchors**: MITgcm/verification/seaice_obcs/input/data::<module>

### Issue or research question
Runoff in regional configurations with open boundaries, including sources near the boundary.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Regional models are a main use case; boundary handling must not interact badly with runoff.

### Proposed action and acceptance
Acceptance: sparse=dense (or budget-checked) cases single and MPI.

Open-boundary rule (RUNOFF-010 design, decision 5): a target with `maskInC = 0` is refused at init, naming the source, because `EmPmR` is multiplied by `maskInC` with `useRealFreshWaterFlux` (`external_forcing_surf.F:149-156`). Test a source in the first interior cell and the refusal beyond the boundary, and establish from `pkg/obcs/obcs_init_fixed.F` whether the boundary row itself has `maskInC = 0`.

Carry forward from RUNOFF-010 review A: the loops that zero `maskInC` start at the open-boundary index itself (`obcs_init_fixed.F:79-87`, `296-301`), so a target on the boundary row is refused at init.

Unblocked 2026-10-04: RUNOFF-004 closed (sparse reader, per-tile lists, placement by the `mdsio_read_field.F` arithmetic, `GLOBAL_SUM` fraction check and the exf volume flux; fork `610d4cbaf`, final verification receipt `2e11b06d`, all 33 scientific commands passing). Note the reader accepts **one constant record only**: `rnf_init_fixed.F:199-217` stops the run for `RNF_useYearlyFiles` or any `RNF_period` other than 0, naming RUNOFF-005.

## UNRESOLVED: Runoff on grids with ice-shelf cavities (top wet level below k=1)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-020
**Anchors**: MITgcm/verification/isomip/input.icefront/data::<module>; MITgcm/pkg/shelfice/shelfice_init_depths.F::<module>

### Issue or research question
Under ice shelves the top wet cell is kSurfC > 1. Design (RUNOFF-010, docs/package_design.md): decision 5: `SHELFICE_FORCING_SURF` zeroes `EmPmR` where `kTopC ≠ 0` (`shelfice_forcing_surf.F:57-69`), so phase 1 refuses under-shelf targets and serves sources at the ice front in open water through the surface path; under-shelf targets wait for the `addMass` path (RUNOFF-025). isomip does not compile exf and needs an exf test variant. Icefront/shelfice and runoff must not double count.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Glacier runoff near ice fronts is a core use case; a k=1 assumption would put water into dry cells.

### Proposed action and acceptance
Acceptance: cases with sources at the ice front and in open water; budgets closed; land/dry-target refusal checked.

Moving shelf edge (RUNOFF-010 design, decision 5): with `SHI_update_kTopC` (`ALLOW_SHELFICE_REMESHING` and `SHELFICEMassStepping`) `kTopC` is reset every step (`shelfice_thermodynamics.F:239-256`), so a target open at init can come under the shelf. `RNF_CHECK` refuses `useRNF` with `SHI_update_kTopC` until the `addMass` path exists (RUNOFF-025); test that refusal here.

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle. [**Superseded 2026-10-07 by RUNOFF-016:** the last clause no longer holds. `tests/rnf/budget_check.py` compares the applied tracer term against the file's source series per cell (worst 2.499e-16 against a 1e-12 criterion) and as a sum over all cells (2.079e-16). It is still **one** runoff tracer on **one** grid, with `RNF_trPtr`'s multi-tracer mapping unmeasured and no analytic decision-3 row for the term, so treat the gap as narrowed rather than closed.] [**Superseded again 2026-10-09 by RUNOFF-008:** the 2.499e-16 and 2.079e-16 above are the historical figures of a degenerate tracer series; on the non-degenerate one they are 2.667e-16 per cell and 1.962e-16 summed. The mapping is now measured on a `PTRACERS_num = 2` lab_sea build (`budget_check.py` case `lab_sea_ptr2` and its `swap` control), and `tendency_term_check.py` has analytic rows for the four linear-free-surface reference arms of the tracer term. Still lab_sea only.] [**2026-10-09, RUNOFF-031:** the terms are now surface terms (heat through exf `runoftemp`/`Qnet`, salt and tracers into `surfaceForcingS`/`surfaceForcingPTr`); re-derived: Package figures 0.00e+00 on 8 of 8 cases over 14 of 14 rows, worst Total 1.42e-14, exf cross-path 5.834e-16 over 7 cells with `TFLUX` bitwise. The residual gaps listed here are unchanged.]

## UNRESOLVED: LLC grid coverage

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-021
**Anchors**: docs/verification_matrix.md::<module>

### Issue or research question
No LLC experiment is in verification/. Find a buildable LLC configuration (e.g. global_oce_llc90 inputs from the MITgcm verification data, or a constructed small LLC) to test the exch2 LLC mapping of target cells.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Known gap: esx/project_profile.md capability boundaries (no LLC experiment).

### Scientific or engineering impact
LLC is a main production grid (2 km target); mapping errors there are a top risk.

### Proposed action and acceptance
Acceptance: either a runnable LLC test with sparse runoff and budget checks, or a documented, owner-visible blocker with the exact missing input.

## UNRESOLVED: Pickup/restart reproducibility with sparse runoff

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-022
**Anchors**: MITgcm/model/src/the_model_main.F::<module>

### Issue or research question
A run restarted from a pickup in mid-record (and across a yearly-file boundary) must reproduce the continuous run exactly.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Production runs always restart; record state must be re-derived correctly.

### Proposed action and acceptance
Acceptance: continuous vs restarted runs identical to the digit threshold for daily, monthly and yearly modes.

Synchronous restart case (RUNOFF-010 review, 2026-10-03): add a restart without `staggerTimeStep` in nonlinear-free-surface, real-freshwater mode across a record boundary, with temperature present; the first step after the restart needs the package fields at `myTime − deltaT` (docs/package_design.md, decision 3, time level).

Unblocked 2026-10-05: RUNOFF-005 closed (sparse time handling, all five modes plus hold-exact; fork `a81f290f0`, final verification receipt `6e2a5194`, all 57 scientific commands passing). Record selection is delegated to the `pkg/exf` routines themselves, and the suite measures 0 of 49/769/1465/1465/1201 forcing steps disagreeing with `pkg/exf`, largest weight error 0.0e+00.

## UNRESOLVED: Thread, MPI and tile-layout independence (do_tst_2+2)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-023
**Anchors**: MITgcm/tools/do_tst_2+2::<module>

### Issue or research question
Results independent of tile size, MPI layout and OpenMP threads; MITgcm 2+2 restart test passes with the package active.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. MITgcm contribution rules (esx/project_profile.md).

### Scientific or engineering impact
Required for upstream acceptance and for correctness on large machines.

### Proposed action and acceptance
Acceptance: same results across at least three layouts per grid; do_tst_2+2 clean.

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle. [**Superseded 2026-10-07 by RUNOFF-016:** the last clause no longer holds. `tests/rnf/budget_check.py` compares the applied tracer term against the file's source series per cell (worst 2.499e-16 against a 1e-12 criterion) and as a sum over all cells (2.079e-16). It is still **one** runoff tracer on **one** grid, with `RNF_trPtr`'s multi-tracer mapping unmeasured and no analytic decision-3 row for the term, so treat the gap as narrowed rather than closed.] [**Superseded again 2026-10-09 by RUNOFF-008:** the 2.499e-16 and 2.079e-16 above are the historical figures of a degenerate tracer series; on the non-degenerate one they are 2.667e-16 per cell and 1.962e-16 summed. The mapping is now measured on a `PTRACERS_num = 2` lab_sea build (`budget_check.py` case `lab_sea_ptr2` and its `swap` control), and `tendency_term_check.py` has analytic rows for the four linear-free-surface reference arms of the tracer term. Still lab_sea only.] [**2026-10-09, RUNOFF-031:** the terms are now surface terms (heat through exf `runoftemp`/`Qnet`, salt and tracers into `surfaceForcingS`/`surfaceForcingPTr`); re-derived: Package figures 0.00e+00 on 8 of 8 cases over 14 of 14 rows, worst Total 1.42e-14, exf cross-path 5.834e-16 over 7 cells with `TFLUX` bitwise. The residual gaps listed here are unchanged.]

## UNRESOLVED: Runoff with sea ice (runoff into ice-covered cells)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-024
**Anchors**: MITgcm/verification/lab_sea/input/data.seaice::<module>

### Issue or research question
Behaviour when runoff enters cells with sea ice under pkg/seaice (and thsice where used): freshwater and heat go to the ocean, seaice growth responds; no double counting with exf.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Arctic and Greenland runoff enters ice-covered seas.

### Proposed action and acceptance
Acceptance: lab_sea and cs32 seaice cases with budget checks; Richard confirms the seaice coupling path.

Inherited residual, **restated for the surface route (RUNOFF-031, 2026-10-09)**. Since RUNOFF-031 the whole runoff heat term is part of exf `Qnet`: `RNF_EXF_RUNOFF` fills `runoftemp` and `EXF_MAPFIELDS` adds `−Cp·[(mT) − m_T·θ]` (the `RNFqnet` diagnostic), beside exf's own `temp_EvPrRn` term for the runoff. Under `pkg/seaice` with `SEAICE_EXTERNAL_FLUXES`, `seaice_growth.F:956-957` keeps only the open-water share `(1 − A)` of exf `Qnet` (`A` = `AREApreTH`), so at an ice fraction `A` the part `A·[(mT) − m_T·θ]μ` of the runoff heat reaches **neither the ocean nor the ice**, with `temp_EvPrRn` unset as well as set; with `temp_EvPrRn` set and `ALLOW_ATM_TEMP` the cancellation `A·m(θ − temp_EvPrRn)μ` is dropped too (the residual RUNOFF-010 derived for the tendency route, where only that part was scaled). The model's own freshwater term and the runoff volume, salt and tracers are not scaled. The dense `runoftempfile` path behaves identically, because the code from `EXF_MAPFIELDS` on is shared; the deleted tendency route delivered the source heat under ice. **Measured by review A of RUNOFF-031** (Richard `ad7dd3fab4c8e2736`, witness `devel-loop/loop_state/scratch/ad7dd3fab4c8e2736/ice_heat_witness_labels.json`): lab_sea with pkg/seaice on, the `tests/rnf/kpp_heat_check.py` pair (25 °C source on cell 52), `SEAICE_initialHEFF = 1`: at the first wet step `AREApreTH = 0.98911`, `RNFqnet = −262.30 W/m²`, the ocean receives 0.308 W/m² (`ΔTFLUX`) and reduced freezing takes 2.548 W/m², which together equal `(1 − A)·262.30` to 1.07e-12; the remaining `A·Q = 259.44 W/m²` is delivered nowhere. Ice-free, the same pair gives `ΔTFLUX` equal to the analytic heat at relative 0.0. Acceptance for this issue: a heat budget under ice that states this share (or a decision to deliver it, which would depart from the dense convention), measured on lab_sea and cs32; consider an `RNF_CHECK`/`RNF_SUMMARY` note when runoff with a temperature meets `pkg/seaice`.

Carry forward from RUNOFF-010 review B, restated: the scaling above is `pkg/seaice`'s with `SEAICE_EXTERNAL_FLUXES`. Without that option `pkg/seaice` computes its own open-water flux and does not use exf `Qnet` at all (`seaice_budget_ocean.F:110-149`), so none of the exf runoff heat would arrive, on either path; under `pkg/thsice` `Qnet` keeps `opFrac·Qnet` (`thsice_step_fwd.F:273-275`) and thsice adds runoff heat at the surface temperature for the ice-covered share itself (`thsice_map_exf.F:104-121`), so the undelivered part there is `(1 − opFrac)` of the runoff's departure from θ. Measure all three.

## UNRESOLVED: Subsurface discharge at depth (target_level > 1, schema 1.1)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-025
**Anchors**: docs/runoff_schema.md::<module>; MITgcm/pkg/icefront/icefront_tendency_apply.F::<module>

### Issue or research question
Allow sources to discharge at a chosen level or distributed over depth (subglacial discharge), using the tendency pattern for interior cells and the volume treatment of the chosen design; schema 1.1 relaxes rule T07.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Schema 1.0 reserves target_level (docs/runoff_schema.md section 12).

### Scientific or engineering impact
Glacier subglacial discharge enters at depth; interior-cell T/S tendencies are what the owner pointed to in shelfice/icefront.

### Proposed action and acceptance
Acceptance: schema 1.1 and checker update, analytic interior-cell tests, budget closure, isomip/cs32 cases.

## UNRESOLVED: Package documentation (MITgcm RST manual, namelist reference, how-to)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-026
**Anchors**: MITgcm/doc/phys_pkgs/exf.rst::<module>

### Issue or research question
MITgcm-manual documentation for the package: purpose, schema summary, namelist parameters, CPP options, diagnostics, examples, the Python tools (checker, builder, converter), and verification cases.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
A package without manual documentation will not be accepted upstream or used.

### Proposed action and acceptance
Acceptance: Sphinx build of the doc section succeeds; Richard reviews accuracy against code and namelist.

Unblocked 2026-10-03: RUNOFF-012 closed (pkg/rnf skeleton, fork ac33291aa).

## UNRESOLVED: MITgcm coding standards and TAF-friendliness review

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-027
**Anchors**: MITgcm/doc/contributing/contributing.rst::<module>

### Issue or research question
Check all new Fortran against MITgcm standards: fixed form, 72 columns, CPP guards, _RL/_RS, myThid/bi,bj loops, header include order, no tabs, comment style, STOP via ERROR handling, and TAF compatibility (store directives where needed).

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Required for an upstream PR.

### Proposed action and acceptance
Acceptance: a scripted lint of new files passes; reviewer checklist complete.

Carry forward from RUNOFF-010 review B: the previous-step field set of the time-level rule is state carried between steps. It needs store directives like the exf record fields, or must be recomputed from model time each step. Review A: once surface levels differ between columns (RUNOFF-025), 2D state-dependent diagnostics need one fill per step.

Carry forward from RUNOFF-012:
- The lint must grep for `RUNOFF-[0-9]` and the development-repo URL. Stub comments, one run-time message and README.md carry them and must be swept as the stubs are filled.
- The TAF list files (`rnf_ad_diff.list`, `rnf_ad.flow`) were deferred here because they need a TAF build.

Unblocked 2026-10-03: RUNOFF-012 closed (pkg/rnf skeleton, fork ac33291aa).

## BLOCKED: Upstream readiness: full testreport master vs branch, MPI and 2+2

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-023 — needs layout independence first
**UUID**: RUNOFF-028
**Anchors**: MITgcm/verification/testreport::<module>

### Issue or research question
Before any PR: full testreport on master and branch (and -mpi), diff clean except new experiments; do_tst_2+2; contribution checklist and PR text with a tag-index suggestion.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Final gate before proposing the package upstream (owner approval still required to open the PR).

### Proposed action and acceptance
Acceptance: tr_out diff clean; 2+2 clean; checklist complete.

## UNRESOLVED: Time modes for T, S and tracer series (all five modes for every series)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-029
**Anchors**: MITgcm/pkg/exf/exf_getffieldrec.F::<module>

### Issue or research question
Every time series (flux, temperature, salinity, each tracer) must follow the same time modes (constant, daily/fixed, monthly, monthly climatology, yearly files) and interpolation, record-consistent with the flux.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Mismatched record selection between flux and T/S would mix the wrong properties.

### Proposed action and acceptance
Acceptance: lab_sea cases per mode with T/S/tracers; direct timing checks extended to all series.

Reconsidered 2026-10-05 on RUNOFF-005's closure. The flux time handling this issue was waiting on is done, but its stated acceptance is "lab_sea cases per mode with T/S/tracers; direct timing checks extended to all series" — and no T, S or tracer series is read or applied yet. The genuine dependency is therefore RUNOFF-013, not RUNOFF-005, and it is re-blocked on that rather than left blocked on a closed issue. What RUNOFF-005 does supply is the pattern to extend: `RNF_GETREC` delegates each mode to its `pkg/exf` routine, so a second series needs the same delegation rather than its own record logic, and `tests/runoff/lab_sea_runoff_timing_check.py` already compares the model's own record trace against the exf conventions at every forcing step — extending it to a second series is the shape of this issue's check.

## UNRESOLVED: Python runoff tools assume level 1 is the surface (pressure coordinates)

**Date Identified**: 2026-10-03T11:00:00Z
**Status**: Unresolved
**UUID**: RUNOFF-032
**Anchors**: MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::<module>; MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::<module>; MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/convert.py::<module>

### Issue or research question
The checker's grid rules (R01 land target), the target builder's wet mask and the converter's land refusal all read `hFacC` level 1 as the surface. In pressure coordinates the surface is level `Nr` (package design decision 5); under shelfice it is `kSurfC`. With `--grid-dir` on a pressure-coordinate grid the checker would flag valid targets as land.

### Evidence
RUNOFF-002: on the cs32 `input.in_p` grid, 1011 of the 1189 runoff cells are dry at level 1 and none are dry at level `Nr` (Bob round 1; review B confirmed).

### Scientific or engineering impact
Users of pressure-coordinate or ice-shelf configurations get false land errors, or wrong spread targets.

### Proposed action and acceptance
Add a surface-level option to all three tools: `--surface-level top|bottom|kSurfC`, or detect it from `data` (`buoyancyRelation`) when a run directory is given, and document it. Acceptance: the cs32 `input.in_p` grid checks cleanly with the converted cs32 file; a shelfice grid uses `kSurfC`; the existing tests are unchanged.

## UNRESOLVED: cs32 sparse-runoff oracle (exch2 volume path; runoff temperature cell-by-cell)

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-006
**Anchors**: MITgcm/pkg/exf/exf_mapfields.F::<module>; tests/mitgcm_oracle.sh::<module>

### Issue or research question
Convert `core_rnof_1_cs32.bin` and `runoff_temperature.bin`, and add cs32 `input.<X>` variants of `input.icedyn` / `input.seaice` that use the sparse path.

### Evidence
`global_ocean.cs32x15` is the only experiment with exf runoff (6 faces of 32×32, 12 tiles; `SIZE.h_mpi` 4 processes × 3 tiles).

### Scientific or engineering impact
Checks exch2 index mapping, sources spanning faces, tiles and processes, and runoff temperature.

### Proposed action and acceptance
Design (RUNOFF-010, docs/package_design.md): runoff temperature enters as a tendency term, not through exf `runoftemp`, and differs from the exf term under sea ice (exf scales it by open-water fraction, `seaice_growth.F:956-957`). The volume oracle stays: `input.icedyn` and a variant of `input.seaice` without runoff temperature must match the dense references. Runoff temperature is checked cell by cell (dense `EXFroff`, `EXFroft`, `THETA` vs the package heat diagnostic) in ice-free cells. Acceptance: volume-only cases match their dense references to the digit threshold, single-process and `-mpi 4`.

From RUNOFF-002: `verification/global_ocean.cs32x15/input.rnof_sparse/runoff_sparse.nc` holds the cs32 conversion (1189 sources, 12 records, flux and temperature). All 12 cs32 records are identical in time, so the cs32 oracle cannot detect a timing error; timing is covered by lab_sea.

Carry forward from RUNOFF-005 (review B, correction rounds 1-2, 2026-10-05). Three items, all measured, none a defect, filed here because this issue owns the **no-`pkg/cal` path** that the first two are reachable only on — cs32's 12-record file is what will first exercise it.

1. **The repeat-cycle tolerance disagrees with exf's own test, on the no-cal path only.** `RNF_TIME_SETUP` consistency check 7 accepts a repeat cycle within 1e-3 s of `nRecFile·period`, but on the no-`pkg/cal` path `GET_PERIODIC_INTERVAL` stops unless `cycleLength` equals `nbRec·recSpacing` **exactly**. So a file off by less than 1e-3 s passes init and then aborts at the first step — a late failure instead of an init refusal. Unreachable today because no configured command exercises the no-cal path.
2. **Hold-exact inherits exf's +0.5 s record rounding.** `INT((fldsectot+0.5)/fldPeriod)+1` means that for the last half second before a record time, the next record is applied. Negligible against periods of 3600 s and up.
   **Review B's ruling on both, which is the reason they are carried rather than fixed:** each is *faithfulness to `pkg/exf`*, and the delegation to exf's own record-selection routines exists precisely so the sparse path cannot drift from the dense oracle that is its acceptance criterion. "Fixing" either would make the sparse path diverge from the dense path it is measured against. Change them only if exf changes, or if a measured defect appears on the no-cal path. Worth a line in the `RNF_GETREC` header whenever it is next touched.
3. **`timing_field_check.py --min-discrimination` could tighten from 5e-3 to about 2e-2.** Review B's sealed runs passed at 2.1e-2 on both the rejected 1980-12-01 span and the committed 1981-12-01 one, so the floor has about 4.3x slack. A tighter floor would warn earlier if a future span change eroded the discrimination — which is the failure RUNOFF-005 hit once already, when the chosen span turned out blind to the likeliest wrong anchoring. The right home is whichever issue next touches that span.

Reconsidered 2026-10-04 on RUNOFF-004's closure, which satisfied both of this issue's original dependencies (the reader, and the RUNOFF-002 converter). **Half of this issue's acceptance is already met:** RUNOFF-004 created `global_ocean.cs32x15/input.rnof_sp_icedyn` (record 1 of `core_rnof_1_cs32.bin` as one constant record, 1189 one-cell sources) and it matches the dense `results/output.icedyn.txt` at 11 matching digits single-process **and** `-mpi 4`, which is the "volume-only cases match their dense references, single-process and -mpi 4" criterion. Review A also proved the exch2 placement bijective over all 6144 cells with per-process counts 321+443+151+274. What remains is therefore narrower than the original scope: the **12-record** file (`input.rnof_sparse/runoff_sparse.nc`), which needs RUNOFF-005, and the **cell-by-cell runoff temperature** check, which needs RUNOFF-013's tendency term. Re-blocked on those two rather than left blocked on a closed issue. Keep the recorded limit that all 12 cs32 records are identical in time, so this oracle cannot detect a timing error; timing stays with lab_sea.

Reconsidered 2026-10-05 on RUNOFF-005's closure, the second of this issue's two dependencies to close. **Half of what remains is now actionable and half is not, so read the acceptance carefully before starting.**
- **Actionable now:** the 12-record `input.rnof_sparse/runoff_sparse.nc` oracle on the exch2 volume path, because sparse time handling exists. This also carries the coverage RUNOFF-005 implemented but could not exercise: cs32 has no `pkg/cal`, so its times are seconds of model time on a 360_day file calendar, and the entire no-`pkg/cal` branch of `RNF_TIME_SETUP` — including its three unenrolled refusals at lines 491, 497 and 579 — is reached by no configured command today. A 12-record cs32 file is what reaches it.
- **Still blocked:** the cell-by-cell runoff-temperature check, which needs RUNOFF-013's tendency term.
Either split the volume and no-cal half into its own issue so it can be done now, or do it here and do not claim closure until RUNOFF-013 lands. Note the recorded limit that all 12 cs32 records are identical in time, so this oracle cannot detect a timing error — timing stays with lab_sea.

## BLOCKED: Per-record parallel I/O strategy at 2 km scale

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-028 — owner decision 2026-10-09: phase 1 (every process reads the full record) ships in the upstream PR; the single-reader scatter is a to-do after it
**UUID**: RUNOFF-007
**Anchors**: docs/model_contract.md#scale-requirement; MITgcm/pkg/exf/exf_getffields.F::<module>

### Issue or research question
Two options: every process reads the full record (a few MB) and keeps its own sources, or one process reads and hands out the data. With thousands of processes, the first may overload the file system.

### Evidence
Target: daily × 50 years × 10⁵–10⁶ coastal cells on a global 2 km grid (owner, 2026-09-29).

### Scientific or engineering impact
Sets production feasibility. Phase 1 correctness doesn't depend on it.

### Proposed action and acceptance
Phase 1 default: every process reads the full record. Owner to decide whether a scatter design is needed before the upstream PR.

**Owner decision, 2026-10-09:** keep phase 1 as it is for the upstream PR, and add the single-reader scatter to the to-do list afterwards, following MITgcm's `useSingleCpuIO` convention (the owner's stated preference).
- **Design:** a `data.rnf` switch, e.g. `RNF_singleCpuIO`, default `.FALSE.`. At init each process sends the global source indices its tiles need (`RNF_srcGlob`) to the reader process in one collective call. When a record is needed, only the reader opens the file and reads it, then sends each process its own values in one `MPI_Scatterv`.
- **Per-record traffic:** about the number of sources (~8 MB for one float64 series of 10⁶ sources), against processes × that figure today.
- **Scope:** confined to the record read (`RNF_NC_READ_FLUX` / `RNF_LOAD_REC`), with MPI under `ALLOW_USE_MPI`. Placement, the time handling and the tendency terms are unchanged.
- **Acceptance:** results bitwise identical to the phase 1 path on lab_sea `-mpi 2` and cs32 `-mpi 4`, including the budget and applied-field oracles; only the reader opens the file (counted); a single-process run is unchanged.
- **Optional:** the measured chunking read benchmark below, to size the benefit.

From RUNOFF-002 (review A): this issue owns the measured chunking read benchmark (docs/runoff_schema.md §8, docs/model_contract.md scale requirement). The converter writes the §8 default layout: one record per chunk, deflate, about 4 MB pieces along `source`.

## UNRESOLVED: test_write_formats cannot type a WRITE item declared in a model header

**Date Identified**: 2026-10-05T08:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-034
**Anchors**: tests/runoff/test_write_formats.py::<module>; MITgcm/pkg/rnf/rnf_init_fixed.F::<module>

### Issue or research question
`tests/runoff/test_write_formats.py` builds its item-type table from `RNF_SIZE.h` and `RNF.h` only, so a `WRITE(msgBuf,...)` item declared in a *model* header — `GRID.h`'s `xC`, `yC`, `dxF`, `dyF`, for instance — is unclassifiable. It fails loudly rather than silently (the coverage test refuses any item it cannot type), so this is not a correctness hole, but it makes the checker an obstacle instead of a guard the moment a message quotes a grid quantity.

### Evidence
Found by the implementer during RUNOFF-033 (2026-10-05). Writing the new cell-centre refusal message, `test_write_formats.py` reported `XC(...)` as "no known type". The implementer worked around it by holding the values in typed `_RL` locals rather than extending the checker — a reasonable local choice that leaves the limitation in place for the next message. The checker itself was created in RUNOFF-004 after two real Fortran runtime format bugs reached the tree on refusal-only paths, so weakening its reach is a direct loss of what it was built for.

### Scientific or engineering impact
Bounded and visible, not silent. The risk is behavioural: an implementer facing a loud refusal will route around the checker, as happened here, so messages that quote model state drift outside its coverage exactly where new refusals are being added.

### Proposed action and acceptance
Extend the symbol table to the model headers `pkg/rnf` actually includes (`GRID.h`, `SIZE.h`, `PARAMS.h`, `EEPARAMS.h`), or give it a declared-type override table for named externals. Acceptance: a `WRITE(msgBuf,...)` quoting `xC` or `dxF` directly is typed correctly rather than refused; the existing 140-statement/0-finding result is unchanged; and the negative controls still detect both historical bugs plus an `I` descriptor with a `_RL` item.

Carry forward from RUNOFF-013 (review B, correction round 1, 2026-10-05): **a `diagTitle` length guard, filed here as diagnosability and explicitly not as a detection gap.** `rnf_diagnostics_init.F` writes fixed-width diagnostic names and titles, and `test_write_formats.py` does not check that a title fits its field. Review B measured that the *class* is already caught loudly rather than silently: every runoff experiment sets `useDiagnostics=.TRUE.`, so an overflow aborts all of them, which is the opposite of a silent pass. What is missing is **diagnosability** — the abort does not say which title overflowed — so the value of a guard here is a better message, not new detection. Low priority; size it accordingly, and keep the distinction, because recording it as a detection gap would overstate the risk.

## UNRESOLVED: doc_contract rejects a Fortran header as a documentation reference

**Date Identified**: 2026-10-05T08:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-035
**Anchors**: tools/esx/doc_contract.py::validate_report; MITgcm/pkg/rnf/RNF.h::<module>

### Issue or research question
`doc_contract.py seal` accepts `MITgcm/pkg/rnf/RNF.h::<module>` as a disposition *target* but rejects it as a disposition *reference*, with "contains no inventoried documentation". A Fortran header is where `pkg/rnf` documents its parameters and their tolerances, so it is a legitimate thing for a judgment to cite.

### Evidence
Found by the implementer during RUNOFF-033 correction round 1 (2026-10-05): two dispositions that cited `RNF.h` were refused at seal and had to cite the verification-matrix and schema headings instead. The reason those dispositions existed was the `RNF_lonLatTol` comment block, which lives in `RNF.h` — so the citation was redirected away from the text it was actually about.

### Scientific or engineering impact
Minor and framework-side. It pushes a judgment's citation away from the prose it concerns, which makes the sealed record slightly less useful to the next reader, and it is asymmetric in a way that is not obvious from the error text.

### Proposed action and acceptance
Decide whether this is intended. If a reference must resolve to inventoried Markdown, say so in the error message and in the documentation contract. If a commented Fortran header should be citable, treat `path::<module>` the way a disposition target already does. Acceptance: either the refusal names the rule it enforces, or a `RNF.h` citation seals.

## UNRESOLVED: a BUILD_SOURCES entry that does not exist silently narrows the staleness guard

**Date Identified**: 2026-10-06T02:10:00Z
**Status**: Unresolved
**UUID**: RUNOFF-036
**Anchors**: tests/rnf/tendency_term_check.py::newest_source_time; tests/rnf/tendency_term_check.py::build_if_stale

### Issue or research question
`newest_source_time` walks each `BUILD_SOURCES` entry to decide whether a `--build` binary may be reused. An entry that does not exist contributes nothing and raises nothing: `os.path.isfile` is false and `os.walk` yields `[]`, so the maximum is simply taken over the remaining entries and the build is reported `reused`. A renamed, moved or mistyped path therefore narrows the staleness reference silently, which is the exact LL-011 failure `build_if_stale` exists to prevent.

### Evidence
RUNOFF-013 correction round 2 (2026-10-05). This is the **third** instance of one class in the same function, each found by a different agent. The first: `os.walk` of a plain file yields nothing, so `MITgcm/pkg/pkg_depend` would have looked like coverage and measured nothing — found by the implementer while fixing review A's finding, and fixed by stat-ing a plain-file entry. The second: `MITgcm/model/inc`, `MITgcm/pkg/ptracers` and `pkg_depend` were absent from the list altogether, so an edit to `PARAMS.h` — where `temp_EvPrRn`, `salt_EvPrRn`, `convertFW2Salt` and `UNSET_RL` are declared, all read by the tendency routines — could not mark any binary stale; found and quantified by review A, fixed in round 2. This third one is review A's: `newest_source_time(extra=<nonexistent path>)` returns the unchanged maximum, `delta 0.000`, with no error.

Review B then supplied the figure that makes it legible: per-entry maxima are `MITgcm/pkg/rnf` at 2026-10-05T16:13:57 and every other entry at 2026-10-04T07:38:32, so **`pkg/rnf` is the entry that sets the maximum.** Losing it to a rename would move the staleness reference back **117 326 s (1 d 8 h 35 m)** and stop the guard from guarding the one directory under active development, while still printing `reused`.

### Scientific or engineering impact
No current defect: all six entries exist, and both reviewers judged this optional for RUNOFF-013's closure on that basis. The impact is scheduled rather than hypothetical — this package is to be rebased on upstream MITgcm before the PR, and a rebase is exactly when a path is renamed or moved. The failure mode is silent and the tool keeps reporting success, so it would be discovered through a wrong figure rather than through an error.

### Proposed action and acceptance
Make a missing entry fail loudly, or treat the build as unconditionally stale. Acceptance: `newest_source_time` with a nonexistent entry raises or forces a rebuild rather than returning a smaller maximum; the six current entries still resolve and still produce today's reference (`pkg/rnf/rnf_nc_utils.F`); and the existing plain-file and directory branches are unchanged. Add a negative control that a nonexistent entry is detected, since all three instances of this class were found by perturbing the mechanism and none by inspecting the list.

**The generalisable lesson, worth carrying beyond this function:** a listed entry that looks like coverage and measures nothing is invisible to inspection. Check such a list by measuring the output change when an entry is perturbed, never by reading it.

## UNRESOLVED: exf runoff-temperature range check tests the wrong array

**Date Identified**: 2026-10-06T07:20:00Z
**Status**: Unresolved
**UUID**: RUNOFF-037
**Anchors**: MITgcm/pkg/exf/exf_check_range.F::<module>

### Issue or research question
`EXF_CHECK_RANGE`'s runoff-temperature check compares the wrong array. At `exf_check_range.F:264-271`, inside `#ifdef ALLOW_RUNOFTEMP`, the upper bound reads `runoff(i,j,bi,bj) .GT. 36` where it means `runoftemp`, and the message then prints `runoff` rather than the temperature it is reporting on. The lower bound of the same `IF` does test `runoftemp`.

### Evidence
Found by the implementer during RUNOFF-030 (2026-10-06) while relaxing the runoff upper bound in the same routine, and deliberately left untouched there because RUNOFF-030 is scoped to one guard relaxation. This is upstream MITgcm code, not `pkg/rnf`.

### Scientific or engineering impact
Two defects in one condition, in opposite directions. A runoff temperature above 36 degC is **not** caught, because the array tested is a volume flux in m/s and never exceeds 36. And a *volume flux* above 36 m/s would be reported as a temperature error with a misleading message. Neither is likely to be hit by a realistic configuration — which is why it has survived — but the check silently does not do what its name and message claim, and `pkg/rnf` is about to make `runoftemp` configurations more common.

### Scope note
Out of RUNOFF-030's scope by construction: that issue relaxes a guard, and this would tighten a different one. It also affects the dense `runoffFile` + `runoftempfile` path identically, so it is a candidate for the eventual upstream report rather than a `pkg/rnf` change.

### Proposed action and acceptance
Compare `runoftemp` in both halves of the condition and print `runoftemp` in the message. Acceptance: a `runoftemp` above 36 degC with `useExfCheckRange` at its default is refused and the message names the temperature and its value; a volume flux of any magnitude is not reported as a temperature error; `tests/rnf/exf_heat_check.py` still passes at its measured 5.834e-16 over 7 cells (3.559e-16 before RUNOFF-031). [**2026-10-09, RUNOFF-031:** this issue matters more now: the sparse heat goes through `runoftemp`, so the misnamed test applies to sparse runoff too, and every lab_sea instrument that carries a temperature (`tendency_term_check`, `budget_check`, `exf_heat_check`, `kpp_heat_check`) builds with `ALLOW_RUNOFTEMP`; cs32 always did.] Since this is upstream code, decide with the owner whether to carry it as a local fix or report it upstream only.

## UNRESOLVED: refusal_check.py has no build-staleness rule and relies on suite ordering

**Date Identified**: 2026-10-06T08:10:00Z
**Status**: Unresolved
**UUID**: RUNOFF-038
**Anchors**: tests/rnf/refusal_check.py::main; tests/rnf/tendency_term_check.py::build_if_stale

### Issue or research question
`refusal_check.py` reads `lab_sea/build_esx/mitgcmuv` and never checks that the binary postdates its sources. It is correct only because the configured suites happen to run `tests/mitgcm_oracle.sh lab_sea input` before it. Any command that rebuilds a *different* directory breaks that assumption: `mitgcm_oracle.sh lab_sea input -mpi 2` rebuilds only `build_esx_mpi2`, and the two enrolled tendency instruments build `build_esx_noatm` and `build_esx_roft`. A single-process `refusal_check.py` run after any of those can read a `build_esx` that predates the current source.

### Evidence
RUNOFF-030, 2026-10-06. The implementer hit it: after running `mitgcm_oracle.sh lab_sea input -mpi 2`, a single-process `refusal_check.py` read a stale mutant `build_esx` and reported a spurious `flux_at_source_max` failure. It recorded the cause in the verification matrix rather than working around it, and recommended filing this.

`tests/rnf/tendency_term_check.py` already solves exactly this with `build_if_stale`, which compares the binary against `BUILD_SOURCES` (widened on RUNOFF-013 to six entries, with plain-file handling) and rebuilds when needed. It is importable.

### Scientific or engineering impact
The direction that bit us is the cheap one — a stale binary producing a spurious *failure*, which is loud and gets investigated. The dangerous direction is the same mechanism producing a **pass**: `refusal_check.py` is the instrument that carries 67 refusal expectations, including the two new cases that are RUNOFF-030's whole acceptance, so a stale binary could report a guard as working when the current source has broken it. That is the lesson class LL-014 names — a mechanism that looks like coverage and measures the wrong bytes — and LL-011, which exists because a figure came from a binary predating its own source.

### Proposed action and acceptance
Call `build_if_stale` from `refusal_check.main` before the first case, or at minimum compare the binary's mtime against `BUILD_SOURCES` and exit 2 with the comparison printed. Acceptance: with `build_esx/mitgcmuv` stamped older than the newest `BUILD_SOURCES` entry, `refusal_check.py` either rebuilds or exits 2 and says so, and does not run a single case; with a current binary its 67 cases and their timings are unchanged. Audit the other `tests/rnf` instruments for the same assumption while there: `applied_field_check.py` and `timing_field_check.py` also read `build_esx` without a staleness rule, and RUNOFF-036 is the related finding that a nonexistent `BUILD_SOURCES` entry contributes nothing.

## UNRESOLVED: the code map routes no brief.py, which now refuses briefs

**Date Identified**: 2026-10-06T10:05:00Z
**Status**: Unresolved
**UUID**: RUNOFF-039
**Anchors**: docs/code_map.md::<module>; tools/esx/brief.py::build

### Issue or research question
`docs/code_map.md`'s Framework-routes table names `project.py`, `loop_gate.py`, `verify.py`, `doc_contract.py`, `records.py` and `hooks.py`, and the map mentions `brief.py` nowhere. The omission predates this project's work, but it stopped being harmless on 2026-10-06: `brief.build` now **refuses** a brief that names an ESX command or flag which does not exist, so it is a gate an agent can be blocked by, with no route in the map that would lead anyone to it.

### Evidence
Found by the implementer during RUNOFF-030's third re-seal (2026-10-06) while writing the disposition for `tools/esx/brief.py::<module>`, and deliberately **not** fixed there: `docs/` is inside the candidate signature, so editing the map would have moved the candidate a fourth time mid-review. Recorded in that seal's `map_delta` reason instead. That restraint was the right call and is why this is a filed issue rather than a fourth churn.

The gate is real and fired twice on RUNOFF-030, both times on a true defect in the brief: once for `loop_gate.py --check-start --issue X --agent bob`, whose flags do not exist, and once as a false positive whose boundary bug is fixed in `ffca56b`.

### Scientific or engineering impact
Low and purely navigational, but of exactly the kind this project keeps paying for: a mechanism that can block work and is absent from the document agents are told to read first. An agent refused by `brief.build` has no map route explaining what refused it or why.

### Proposed action and acceptance
Add `brief.py` to the Framework-routes table with its inputs (the issue's orientation, the sealed report, the design file, `--sweep-symbol`), its refusal condition (an unknown ESX command or flag, introspected from argparse including subcommands), and its output. Acceptance: `audit.py` still PASS, the map names the refusal so a blocked agent can find it, and the change is made when no review is in flight so it does not strand a seal. Pairs naturally with RUNOFF-026 (documentation) or with the next issue that edits the map for its own reasons.

## UNRESOLVED: RNF_SUMMARY does not report a dTtracerLev/deltaTFreeSurf mismatch

**Date Identified**: 2026-10-07T02:10:00Z
**Status**: Unresolved
**UUID**: RUNOFF-041
**Anchors**: MITgcm/pkg/rnf/rnf_summary.F::<module>; tests/rnf/refusal_check.py::cases

### Issue or research question
`RNF_cellVolMax` bounds `|RNF_vflx|·deltaTFreeSurf / (drF(ks)·hFacC(ks))`. Under a
linear free surface that quantity is also read as the fractional freshwater
dilution the surface tracer forcing applies in a step — but only where
`dTtracerLev(ks) = deltaTFreeSurf`. `deltaTFreeSurf` defaults to `deltaTMom`,
not `deltaTtracer` (`ini_parms.F:1068`, whose own comment calls that default
"inappropriate" and advises `deltaTFreeSurf = deltaTtracer` under asynchronous
stepping). Where they differ, the dilution per tracer step exceeds the bounded
`f` by `dTtracerLev/deltaTFreeSurf`, so the bound is that much looser **on that
reading only** — the volume reading, which is primary, stays exact.

RUNOFF-040 qualified the records and deliberately did not change the bound.

### Evidence
RUNOFF-040 review A, round 1, measured and confirmed by review B and by the
implementer. This project's `global_ocean.cs32x15` has `deltaTMom` = 1200
against `deltaTtracer` = 86400 — a ratio of **72** — and escapes the trap only
because its `data` sets `deltaTFreeSurf = 86400` explicitly; `lab_sea` has them
equal. So **no enrolled case can see a mismatch**, which is why the exposure is
documented rather than tested.

### Scientific or engineering impact
Missed detection, never a false refusal: the exposure is one-sided (only
looser). A user in an asynchronous set-up that leaves `deltaTFreeSurf` at its
default gets a dilution-reading bound up to ~72× weaker than the record implies,
with nothing saying so in the run's own output.

### Proposed action and acceptance
**Both reviewers recommended against bounding with
`MAX(deltaTFreeSurf, dTtracerLev(ks))`, and Arch accepted.** Reasons on the
record: `deltaTFreeSurf` is the step `integr_continuity.F:221` integrates the
free surface with, which is the bound's primary reading, so `MAX()` would make
one constant stop having one physical meaning across configurations — the very
property that justified a fixed header constant over a `data.rnf` parameter; the
failure mode is missed detection in a self-announcing set-up, never a blocked
user; and it would change a guard just approved on measured evidence for a case
no test covers.

The agreed action is a **report, not a bound change**: have `RNF_SUMMARY` print
at `nIter0`, when `dTtracerLev(1) ≠ deltaTFreeSurf`, a line naming both steps
and their ratio and stating that the dilution reading of `RNF_cellVolMax` is
looser by that factor while the volume reading is unaffected. One `WRITE` in a
routine that already prints the bound lines, no numerical change, visible in
every `STDOUT`.

Acceptance: the line appears in a run where the two differ and is absent where
they are equal; it is enrolled in `refusal_check.py`'s existing `bounds_report`
assertions, which every normal-end case receives, so it cannot go inert (LL-014);
and the no-change experiments still match their references, since nothing
numerical moves.


## UNRESOLVED: runoff tracer term is mis-sampled in time under pkg/longstep with LS_nIter > 1

**Date Identified**: 2026-10-09T07:50:00Z
**Status**: Unresolved
**UUID**: RUNOFF-043
**Anchors**: MITgcm/pkg/rnf/rnf_forcing_surf.F::<module>; MITgcm/pkg/longstep/longstep_forcing_surf.F::<module>

### Issue or research question
With pkg/longstep the passive tracers step every `LS_nIter` dynamics steps with `PTRACERS_dTLev = LS_nIter*dTtracerLev` (`pkg/ptracers/ptracers_readparms.F:159`), and the model's own freshwater term uses `LS_fwFlux`, the long-step **average** of `EmPmR` (`pkg/longstep/longstep_average.F`, `longstep_forcing_surf.F:66-147`). `RNF_TENDENCY_APPLY_PTR` instead applies the `RNF_ap*` fields of the **current** dynamics step for the whole long step. The two agree only when the runoff is constant over the long step or `LS_nIter = 1`. [**2026-10-09, RUNOFF-031:** the term moved to `surfaceForcingPTr` and is re-added after `LONGSTEP_FORCING_SURF` by `RNF_FORCING_SURF_PTR`; it is still the current step's, so the mis-sampling stands, and the option-C refusal was implemented in RUNOFF-031 (`RNF_CHECK`, `refusal_check.py` cases `longstep_tracer` and `longstep_no_tracer`, the refusal shown failing on a guard-removed mutant).]

### Evidence
Found by review A of RUNOFF-008 (2026-10-09, agent ad98e39fd4b872093) and confirmed by Arch from source. Witness `devel-loop/loop_state/scratch/ad98e39fd4b872093/longstep_nIter_witness.json`: the `tendency_term_check` `L_unset` pair (record 1 dry, record 2 wet), tracer change at the target cell over two steps against the source-carried `(mC − m·C_L)·mu·D·dt` of the one wet step: ratio 1.000000000000002 at `LS_nIter = 1`, **1.9999999999999998 at `LS_nIter = 2`**. Stock `lab_sea/input.longstep/data.longstep` sets `LS_nIter = 2`. With `PTRACERS_EvPrRn` set there is also a cancellation residual `(m_avg − m_now)·EvPrRn·mu` between the model term and the package term (derived from source, not measured). The longstep arms themselves match `PTRACERS_FORCING_SURF` and the package's `C_ref` choice; only the time sampling differs. T and S are unaffected (pkg/longstep steps only ptracers).

### Scientific or engineering impact
Silent tracer-budget error, up to a factor `LS_nIter` at a step where runoff switches on, for any longstep run whose runoff varies within a long step. pkg/longstep was never declared a supported class of pkg/rnf, and no document states the limit yet; every RUNOFF-008 oracle runs `LS_nIter = 1`.

### Proposed action and acceptance
Decide between (a) averaging the package's tracer inputs over the long step the way `LONGSTEP_AVERAGE` averages `EmPmR`, so the term is exact for any `LS_nIter`, and (b) refusing `useRNF` tracer variables with `LS_nIter > 1` in `RNF_CHECK` and documenting it. Either way document the limit in `docs/package_design.md` decision 4 and the verification matrix. Acceptance: Richard's witness reproduces at ratio 1 to 1e-12 under (a), or is refused with a named message under (b); an enrolled case with `LS_nIter = 2` that fails on the current code; no-change runs unchanged. Kind: scientific_change (risk supported_semantics under (a)).

**Owner decision, 2026-10-09: (b).** "pkg/rnf does not need to support pkg/longstep at this time. If the model is configured with both, throw an error and stop (similar to other occasions when the model encounters incompatible package combinations) — refuse and document the limit." One point is waiting on the owner. pkg/longstep has no run-time switch: it is active whenever it is compiled and `usePTRACERS` is set (`longstep_readparms.F:47`), and `LS_nIter` defaults to 1. lab_sea compiles it, and every RUNOFF-008 tracer oracle runs on lab_sea with `LS_nIter = 1`, which is exact. Arch proposed refusing in `RNF_CHECK` when longstep actually long-steps, i.e. `ALLOW_LONGSTEP`, `usePTRACERS` and `LS_nIter ≠ 1`, rather than whenever both packages are compiled, which would stop every lab_sea tracer run.

**Owner decision, 2026-10-09 (final): option C.** Refuse only the broken configuration.
- **Condition:** in `RNF_CHECK` under `#ifdef ALLOW_LONGSTEP`, stop when `usePTRACERS`, `LS_nIter ≠ 1` and `RNF_nTrUse > 0`, i.e. the file feeds at least one ptracer. `RNF_nTrUse` is set by `RNF_NC_SERIES` in `RNF_INIT_FIXED`, which runs before `RNF_CHECK`.
- **Message:** names pkg/longstep, `LS_nIter` and the runoff tracer variables. It suggests `LS_nIter = 1` or `RNF_usePtracers = .FALSE.`.
- **Not refused:** `LS_nIter ≠ 1` with no runoff tracer variables. There the volume reaches `EmPmR` and `LS_fwFlux` by exf's own path (`RNF_EXF_RUNOFF` fills exf `runoff`), which is time-consistent under longstep.
- **Documentation:** the limit goes in package design decision 4, the verification matrix and the code map.
- **Acceptance:** an enrolled refusal case with `LS_nIter = 2` and a runoff tracer, shown failing on a mutant with the guard removed. A companion case with `LS_nIter = 2` and no tracer variables must run normally. A third case at `LS_nIter = 1` with tracers must run (the RUNOFF-008 oracles already do). No-change runs unchanged. One Richard.
- **Option D (support by averaging) is deferred to RUNOFF-044.** Once it lands, this refusal is removed.

Also carried here from the same review (coverage, not a defect): in RUNOFF-008's enrolled local-arm tendency rows the cell's tracer still equals its initial value at the measured step, so a stale-time-level reference would pass them; review A's witness with a wet first record (local 1.50318 vs initial 1.5) shows the code uses the current tracer. Enrolling a wet-first-record case closes that gap.

## BLOCKED: support pkg/longstep with LS_nIter > 1 for runoff tracers (average the tracer input over the long step)

**Date Identified**: 2026-10-09T09:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-028 — owner decision 2026-10-09: on the to-do list after the upstream PR, next to the single-reader scatter (RUNOFF-007); phase 1 refuses this configuration instead (RUNOFF-043, option C)
**UUID**: RUNOFF-044
**Anchors**: MITgcm/pkg/rnf/rnf_forcing_surf.F::<module>; MITgcm/pkg/longstep/longstep_average.F::<module>

### Issue or research question
Make `RNF_TENDENCY_APPLY_PTR` exact for any `LS_nIter` by feeding its tracer input through pkg/longstep's averaging, the way `EmPmR` becomes `LS_fwFlux`, instead of refusing `LS_nIter ≠ 1` (RUNOFF-043). [**2026-10-09, RUNOFF-031:** the routine is now `RNF_FORCING_SURF_PTR`, which adds the term to `surfaceForcingPTr` from `LONGSTEP_FORCING_SURF`; read the design below with that name.]

### Evidence
RUNOFF-043, review A of RUNOFF-008: ratio 2.0 of delivered to source-carried tracer at a dry-to-wet step with `LS_nIter = 2`. pkg/longstep already has the averaging machinery (`LONGSTEP_RESET_3D`, `LONGSTEP_FILL_3D`, `LONGSTEP_AVERAGE_3D`, used for `EmPmR`, `Qsw` and the velocities in `longstep_average.F:56-164`). It forbids restarts in the middle of a long step (`longstep_check_iters.F:33-40`), so new accumulators need no pickup, and it has no autodiff code.

### Scientific or engineering impact
Needed only for runs that combine per-river tracers (nutrients, dye) with long-stepped biogeochemistry. Phase 1 refuses that combination.

### Proposed action and acceptance
Design (Arch estimate, 2026-10-09):
- 2D accumulators of the runoff mass flux `m` and of `(mC_n)` per runoff tracer, in `RNF.h` under `#ifdef ALLOW_LONGSTEP`.
- One `#ifdef ALLOW_RNF` hook inside `LONGSTEP_AVERAGE`, beside the `EmPmR` sample, to an `RNF_LONGSTEP_ACCUM` that resets, fills and averages them with longstep's own routines, so the samples are co-located with `EmPmR`'s for every `LS_whenToSample`.
- `RNF_TENDENCY_APPLY_PTR` uses the averages when longstep is active. `C_ref` stays the current tracer, as `LONGSTEP_FORCING_SURF` does.
- Remove the RUNOFF-043 refusal.

The main risk is timing: proving that the averaged runoff and the averaged `EmPmR` come from the same steps for `LS_whenToSample` = 0, 1 and 2, with `RNF_lagFlds`.

Acceptance:
- Review A's witness reproduces at ratio 1 to 1e-12 for `LS_nIter = 2`.
- Analytic tendency rows and a budget closure over long steps with time-varying runoff, under each `LS_whenToSample`.
- Mutant failures show the averaging is used.
- The RUNOFF-043 refusal case becomes a normal-end case.
- No-change runs unchanged.

Kind: scientific_change, risk supported_semantics (two Richards). Size: comparable to RUNOFF-008.

## UNRESOLVED: runoff heat enters at temp_EvPrRn + T_r − θ without ALLOW_ATM_TEMP when temp_EvPrRn is set (dense and sparse)

**Date Identified**: 2026-10-09T22:00:00Z
**Status**: Blocked
**Blocked-By**: OWNER-DECISION — keep the dense exf convention, refuse that build for a runoff temperature, or fix exf for both paths
**UUID**: RUNOFF-045
**Anchors**: MITgcm/pkg/exf/exf_mapfields.F::<module>; MITgcm/model/src/external_forcing_surf.F::<module>

### Issue or research question
Found by Bob in RUNOFF-031 round 0. Confirmed from source by Arch, and by review A (Richard `ad7dd3fab4c8e2736`).
- The model gives runoff water the temperature `temp_EvPrRn` when that is set (`external_forcing_surf.F:299-305`).
- exf cancels that assumption for runoff only inside `#ifdef ALLOW_ATM_TEMP` (`exf_mapfields.F:136-197`).
- exf's runoff-temperature block (`exf_mapfields.F:199-210`) then adds `Cp·(θ − runoftemp)·runoff·ρ_fresh` either way.

So in a build without `ALLOW_ATM_TEMP` that sets `temp_EvPrRn`, runoff enters with heat at:
- `temp_EvPrRn + T_r − θ` in branches N and L;
- `T_r − θ + temp_EvPrRn − tRef` in branch U;

instead of at `T_r`. This is pre-existing in upstream's dense `runoftempfile` path. Since RUNOFF-031, sparse runoff takes the same route and inherits it (tendency-table rows T3/T6). The deleted tendency route gave `T_r`.

### Evidence
- RUNOFF-031 round 0: Bob's T3/T6 rows pass on the dense algebra.
- Review A answered question 4 from `exf_mapfields.F:136-219` and `external_forcing_surf.F:258-349`.

### Scientific or engineering impact
Wrong runoff heat in that one build combination, on both paths, with no message. `temp_EvPrRn` is unset by default, and most exf configurations define `ALLOW_ATM_TEMP`.

### Proposed action and acceptance
Owner decision, with three options:
- (a) Keep the dense convention and document it.
- (b) Have `RNF_CHECK` refuse a runoff temperature without `ALLOW_ATM_TEMP` when `temp_EvPrRn` is set, with an enrolled refused case and a must-run control. Report the dense-path inconsistency upstream as well.
- (c) Fix exf for both paths by moving the runoff cancellation out of `ALLOW_ATM_TEMP`. That is an upstream behaviour change to dense runoff.

Arch recommends (b). RUNOFF-031 is closed on (a), the dense convention, pending this decision.
