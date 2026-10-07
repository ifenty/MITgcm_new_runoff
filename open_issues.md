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

## UNRESOLVED: Volume, heat, salt and tracer budget closure checks

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-016
**Anchors**: docs/model_contract.md::<module>

### Issue or research question
Script-based checks that Σ applied volume = Σ source flux, and heat/salt/tracer input equals Σ flux·X per source, every record, across tiles and processes.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Invariants: docs/model_contract.md Invariants.

### Scientific or engineering impact
The strongest independent oracle for the tendency-based contributions where no dense path exists.

### Proposed action and acceptance
Acceptance: checks pass to 1e-12 relative on lab_sea and cs32 sparse cases, single and MPI; deliberately broken fractions fail them.

Adams-Bashforth note (RUNOFF-010 review, 2026-10-03): with forcing inside Adams-Bashforth (`temp_integrate.F:367-372`, `tracForcingOutAB ≠ 1`) the package term is extrapolated like the model's own forcing, so close heat, salt and tracer budgets in the sum over time, or run the check with `tracForcingOutAB=1` or a non-AB scheme.

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle.

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

1. **A duplicate `RNF_trPtr` check is NOT needed: the condition is unreachable.** Review B proposed guarding against two runoff-tracer variables mapped to the same ptracer, of which the `iRnf` loop of `RNF_TENDENCY_APPLY_PTR` silently keeps the last. The "keeps the last" half is true, but the premise is not: `RNF_NC_SERIES` trims the variable name with `ILNBLNK`, which treats **only the literal space** as blank (`eesupp/src/utils.F:123-152`), so two *distinct* NetCDF names can collide on the trimmed name only through a trailing blank, and **NetCDF refuses one** — creating `runoff_ptracer_dye ` fails with `NetCDF: Name contains illegal characters` (measured 2026-10-05, netCDF4 1.7.4, libnetcdf 4.10.0). The one route that rule leaves open closes itself: a trailing **NUL** is accepted but collapsed to the same stored name, after which the duplicate name is refused with `NetCDF: String match to name in use` (same measurement, correction round 2). Distinct names therefore trim to distinct tracer names, which match distinct `PTRACERS_names` entries or none (two equal entries give `nMatch ≥ 2`, itself a refusal), so `RNF_trPtr` cannot hold a duplicate. Recorded here so the suggestion is not re-filed; the `iRnf` loop stays as defence in depth. Do **not** attach the `PTRACERS_num ≥ 2` condition to this item — that belongs to the two-matching-names refusal below.
2. **The two `RNF_NC_SERIES` refusals that still have no case**, both needing another build: a name matching more than one `PTRACERS_names` entry (needs `PTRACERS_num ≥ 2`) and the `#else /* ALLOW_PTRACERS */` branch for a model compiled without pkg/ptracers. Three siblings were enrolled in correction round 1 (`ptracer_name_empty`, `ptracer_name_long`, `ptracer_too_many`), each measured passing on the committed build and failing on a mutant with its guard weakened, and correction round 2 added their at-the-bound counterfactuals (`ptracer_name_min`, `ptracer_name_max`, `ptracer_count_max`), which hold the guards back from `.GE.`; these two refusals are what is left.
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

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle.

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

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle.

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

Inherited residual (RUNOFF-010 review, 2026-10-03): under ice fraction `a` with `temp_EvPrRn` set, the exf cancellation of the model's `temp_EvPrRn` term is scaled by the open-water fraction, so the heat total is `(mT)μ + a·m(temp_EvPrRn − θ)μ`. The dense path has the same residual; record it in the budget check and consider an `RNF_CHECK` warning.

Carry forward from RUNOFF-010 review B: the under-ice residual `a·m(temp_EvPrRn − θ)μ` was derived for `pkg/seaice` with `SEAICE_EXTERNAL_FLUXES` only; under `pkg/thsice` the ice-covered share comes from thsice itself, so the residual may be absent. Measure both packages.

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

## UNRESOLVED: KPP and surface diagnostics do not see tendency-based runoff heat and salt

**Date Identified**: 2026-10-03T04:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-031
**Anchors**: MITgcm/pkg/kpp/kpp_calc.F::<module>; MITgcm/model/src/diags_oceanic_surf_flux.F::<module>

### Issue or research question
The package T/S terms go to `gT`/`gS`, not `surfaceForcingT/S`, so the KPP surface buoyancy flux and non-local transport and the `TFLUX`/`SFLUX` diagnostics omit them (the freshwater buoyancy of the volume still reaches KPP through `EmPmR`). Quantify the effect and decide whether surface targets should also feed `surfaceForcingT/S` (an `EXTERNAL_FORCING_SURF`-end hook, as `SHELFICE_FORCING_SURF` does) instead of, or as well as, the tendency term.

### Evidence
RUNOFF-010 design, decision 3, comparison point 2-3: `kpp_calc.F:419-421`, `kpp_transport_t.F:79`, `diags_oceanic_surf_flux.F:116-152`.

### Scientific or engineering impact
Mixed-layer response to warm or cold river water could differ from the dense exf path; users comparing TFLUX budgets would see unexplained residuals.

### Proposed action and acceptance
Run a KPP configuration (e.g. lab_sea or cs32 with KPP) with a strongly warm/cold source both ways; report the difference in mixed-layer depth and surface T. Acceptance: a documented decision with the measured effect, reviewed by Richard; the package design updated.

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
**Blocked-By**: OWNER-DECISION — choose the phase 1 vs production I/O design
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

From RUNOFF-002 (review A): this issue owns the measured chunking read benchmark (docs/runoff_schema.md §8, docs/model_contract.md scale requirement). The converter writes the §8 default layout: one record per chunk, deflate, about 4 MB pieces along `source`.

## UNRESOLVED: Passive-tracer runoff contributions (ptracers tendency term)

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-008
**Anchors**: MITgcm/pkg/ptracers/ptracers_apply_forcing.F::<module>; docs/package_design.md::<module>

### Issue or research question
Apply per-source tracer concentrations (matched exactly to `PTRACERS_names` at init) as a tendency term in `PTRACERS_APPLY_FORCING`, beside `GCHEM_ADD_TENDENCY`, with the reference value the ptracers freshwater treatment already gives the water (decision 4 of docs/package_design.md).

### Evidence
The owner decision this issue waited on was given 2026-10-02: T, S and tracer input follows the shelfice/icefront tendency pattern (esx/project_profile.md). Salinity moved to RUNOFF-013. Hook: `ptracers_apply_forcing.F:71-78`.

### Scientific or engineering impact
Required for tracer studies (dye, nutrients, isotopes). Wrong reference values break tracer budgets.

### Proposed action and acceptance
Acceptance: analytic single-cell tracer budget to 1e-12 relative; a missing tracer in the file adds nothing; an unknown tracer name is refused at init; budget closure (RUNOFF-016) with at least two tracers; no-change runs unchanged.

Carry forward from RUNOFF-013 (review B, correction round 1, 2026-10-05): **a numerical oracle for the tracer term is the main thing RUNOFF-013 leaves here.** RUNOFF-013 enrolled `refusal_check.py --case ptracer_match`, which is the only configured run that reaches `RNF_TENDENCY_APPLY_PTR`; it asserts that the routine runs, that the match is reported (`runoff tracer 1 is runoff_ptracer_dye, applied to ptracer 1`) and that `RNF_nTrUse = 1`, but **nothing compares the number the term applies**. The T and S terms by contrast have two oracles each in `tests/rnf/tendency_term_check.py` (the `RNFgT`/`RNFgS` diagnostic and the two-run `TOTTTEND`/`TOTSTEND` difference). The cheapest route is to extend `tendency_term_check.py`, which already has the machinery: the `RNFtrNN` diagnostic is registered, `PTRACERS_EvPrRn`/`PTRACERS_ref` give the same three reference-value branches as salinity, and the two-run difference needs a `TOTPTEND`-equivalent or the ptracer state dumps. Acceptance as above, plus the `RNFtr01` diagnostic matching the analytic `[(mC) − m·C_ref]·mass2rUnit·D` to 1e-12 relative on at least one case per reference branch.


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
Compare `runoftemp` in both halves of the condition and print `runoftemp` in the message. Acceptance: a `runoftemp` above 36 degC with `useExfCheckRange` at its default is refused and the message names the temperature and its value; a volume flux of any magnitude is not reported as a temperature error; `tests/rnf/exf_heat_check.py`, which is the only instrument that builds with `ALLOW_RUNOFTEMP`, still passes at its measured 3.559e-16 over 7 cells. Since this is upstream code, decide with the owner whether to carry it as a local fix or report it upstream only.

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

## UNRESOLVED: no per-cell bound on the applied runoff field after the exf relaxation

**Date Identified**: 2026-10-06T13:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-040
**Anchors**: MITgcm/pkg/rnf/rnf_exf_runoff.F::<module>; MITgcm/pkg/rnf/RNF.h::<module>

### Issue or research question
RUNOFF-030 moved the guard on runoff magnitude from a per-cell rate bound in `EXF_CHECK_RANGE` (1e-6 m/s, which could not serve every grid) to a per-source volume bound in `pkg/rnf` (`RNF_srcFluxMax` = 1e7 m³/s, checked on every record as it is read). That trade was judged correct in kind by both reviewers, and the sparse path is better guarded after it than before. But it leaves one error class with no check at all: the **aggregate per-cell magnitude of the applied field**.

### Evidence
Measured by review B during RUNOFF-030 (2026-10-06), not argued. Four sources each carrying **exactly** `RNF_srcFluxMax`, with every target entry collapsed onto one lab_sea cell and `target_cell_area`/`lon`/`lat` moved with them so no area or coordinate check could fire, fractions left summing to 1 per source: the run **ends normally** with `useExfCheckRange` at its default, prints **zero** `EXF WARNING` lines, and applies **1.285228e-3 m/s — 1285× the relaxed bound**. The volume is applied, not merely accepted: the model's own `RNF_INIT_VARIA` flux sums read `4.000000000000E+07` over both the sources and the targets, relative difference 0. Its control — the same file with one source at 2× the bound — **is** refused in `RNF_NC_READ_ONE`, which shows the per-source guard is live in exactly that file shape and only the aggregate escapes it. Arch reproduced the arithmetic independently: 4e7 / 3.112287377e10 = 1.285228e-3.

Two things make this more than theoretical. The route is a converter index bug collapsing sources onto one cell, which is on this project's own highest-risk list, and before RUNOFF-030 the per-cell bound caught exactly that at `nIter0` for any realistic river. And N is not small: the stated use case is 10⁵–10⁶ sources.

Separately, at the 2 km target resolution `RNF_srcFluxMax` is not a per-cell safety bound at all — it admits 2.5 m/s into one cell where a *physically correct* Amazon is 5.25e-2 m/s, a factor of 48. It is a file-scale unit-error filter, which is how the records now describe it.

### Scientific or engineering impact
A silently wrong applied field on the configuration the package exists to serve. The old bound was the wrong shape but it did catch this; nothing does now.

**Implemented 2026-10-06.** The present tense above describes the code *before* this change: `RNF_cellVolMax` = 0.2 in `RNF.h`, enforced in `RNF_EXF_RUNOFF` on every step, now refuses a cell whose one-step runoff exceeds that share of its top-layer volume, naming the cell, the applied value and the limit. Review B's four-source witness was rebuilt from the description in the Evidence section and confirmed on the committed RUNOFF-030 build first (normal end, exit 0, zero `EXF WARNING` lines, 1.2852284e-3 m/s at one cell); it is now the enrolled refusal `cell_above_vol_max`, with `cell_at_vol_max` at 0.99 of the bound as its control. The derivation, the figures on each grid and what the bound does not cover are in `RNF.h` and in [package design](docs/package_design.md) decision 2. Nothing in the "Proposed action and acceptance" paragraph below was changed.

### Proposed action and acceptance
**Not a parameter.** Review B's judgment, which Arch accepted and which the design records: a fixed header constant is the right mechanism for the per-source bound, a `data.rnf` scalar would be a cost with no benefit, and the remaining gap cannot be closed by a different *number* — it needs a different *shape* of check. The grid-independent form is the volume added per step as a fraction of the target cell's top-layer volume, which requires `rA`, the top-layer thickness and `deltaT`, so it belongs in `RNF_EXF_RUNOFF` where all three are available and the applied field exists.

Acceptance: review B's four-source aggregate file is **refused**, naming the cell and the applied value; a physically plausible configuration on each test grid is not; the figure chosen is derived from the physics and stated as a fraction of the cell's top-layer volume per step rather than as a rate; and the case is enrolled in `refusal_check.py` with a negative control, since the whole point is that the current suite cannot see this. Note the control route under `ALLOW_CTRL` + `ALLOW_GENTIM2D_CONTROL` (`xx_runoff` added at `exf_getffields.F:531-534`, after `RNF_EXF_RUNOFF` and before the check) would also be covered by a check in the applied field, where `RNF_srcFluxMax` cannot reach it.

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

## UNRESOLVED: the footprint sweep cannot see claims in .py, and that gap has now cost a stale figure

**Date Identified**: 2026-10-07T02:15:00Z
**Status**: Unresolved
**UUID**: RUNOFF-042
**Anchors**: tests/footprint_claim_sweep.py::tracked; tests/footprint_claim_sweep.py::<module>

### Issue or research question
`tests/footprint_claim_sweep.py` sets `SUFFIXES = (".md", ".rst", ".F", ".h")`,
so it never scans `.py`. It therefore cannot see a footprint or figure claim in
a test, a tool or a docstring — including its own fixtures, which is part of why
the gap was left open.

RUNOFF-030 carried this as a note on the explicit ground that it hid **no live
false claim**. That ground no longer holds.

### Evidence
RUNOFF-040 review B, round 1, measured it: `tests/rnf/refusal_check.py:1530`
still read "The four \"which bounds applied\" lines of `RNF_SUMMARY`, asserted
on every normal-end case" after RUNOFF-040 added a fifth — contradicted by the
file's own comment three lines below. Its twins in `docs/code_map.md:50` and
`MITgcm/pkg/rnf/README.md:136` **were** caught and corrected by the sweep; this
one survived precisely because the sweep does not scan `.py`. So the gap has
produced a live stale figure, not a hypothetical one.

Review B also measured in RUNOFF-030 that 41 footprint candidates sit in `.py`
prose, **23 of them the sweep's own `MUST_MATCH`/`KEEP` fixtures**.

### Scientific or engineering impact
Bounded but real: a false claim in a test or tool is invisible to the mechanism
built to catch exactly that class, and the project now has one measured instance
of the class escaping. The direct risk is a stale assertion count or a wrong
validity condition in a helper — RUNOFF-040 produced one of each.

### Proposed action and acceptance
Add `.py` to `SUFFIXES` and **exclude the sweep's own file**, without which
triage floods with its 23 fixture lines (measured by review B). Expect the
candidate count to rise; the figure is bound to a candidate signature in the
records, so a changed count is a recorded measurement rather than drift.

Acceptance: the `refusal_check.py:1530`-shaped claim is returned as a candidate
by the sweep when reintroduced (demonstrate it failing, LL-009, since the whole
point is that the current sweep cannot see it); `--self-test` still reports its
full recall with `0` benign false positives; the sweep's own fixtures do not
appear in triage; and the recorded figures are re-measured and re-bound to the
new candidate.

Note the standing decision this interacts with: the sweep is enrolled in **no**
configured suite, so all its guards run only when someone invokes the procedure.
Both RUNOFF-030 reviewers raised that and deferred to Arch; enrolling
`--self-test` alone (exit 4, no triage noise) is one line in `esx/project.json`
and would wire the alarm. **Decide it with this issue rather than carrying it a
third time.**
