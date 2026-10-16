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

**Re-scoped 2026-10-10 by RUNOFF-046.** The `addMass` path this entry waited on exists: the generalized route (`RNF_applyAsRain = .FALSE.`, the default) places each target entry at its own level, and a schema-1.1 `target_level` can name any wet level. What remains here: (1) lifting the two refusals that still apply on **both** routes -- a target under an ice shelf (`kTopC ≠ 0`, `RNF_INIT_FIXED`) and `SHI_update_kTopC` (`RNF_CHECK`) -- for the generalized route, which is a code change of a few lines once there is a test; and (2) that test, which still needs **isomip's exf gap closed separately**: none of isomip's `packages.conf` variants lists `exf` and no input variant has a `data.exf`, while `pkg/rnf` requires `useEXF` on both routes (its record selection is pkg/exf's own code). The legacy route stays surface-only and will not take under-shelf targets.

Moving shelf edge (RUNOFF-010 design, decision 5): with `SHI_update_kTopC` (`ALLOW_SHELFICE_REMESHING` and `SHELFICEMassStepping`) `kTopC` is reset every step (`shelfice_thermodynamics.F:239-256`), so a target open at init can come under the shelf. `RNF_CHECK` refuses `useRNF` with `SHI_update_kTopC` until the `addMass` path exists (RUNOFF-025); test that refusal here.

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle. [**Superseded 2026-10-07 by RUNOFF-016:** the last clause no longer holds. `tests/rnf/budget_check.py` compares the applied tracer term against the file's source series per cell (worst 2.499e-16 against a 1e-12 criterion) and as a sum over all cells (2.079e-16). It is still **one** runoff tracer on **one** grid, with `RNF_trPtr`'s multi-tracer mapping unmeasured and no analytic decision-3 row for the term, so treat the gap as narrowed rather than closed.] [**Superseded again 2026-10-09 by RUNOFF-008:** the 2.499e-16 and 2.079e-16 above are the historical figures of a degenerate tracer series; on the non-degenerate one they are 2.667e-16 per cell and 1.962e-16 summed. The mapping is now measured on a `PTRACERS_num = 2` lab_sea build (`budget_check.py` case `lab_sea_ptr2` and its `swap` control), and `tendency_term_check.py` has analytic rows for the four linear-free-surface reference arms of the tracer term. Still lab_sea only.] [**2026-10-09, RUNOFF-031:** the terms are now surface terms (heat through exf `runoftemp`/`Qnet`, salt and tracers into `surfaceForcingS`/`surfaceForcingPTr`); re-derived: Package figures 0.00e+00 on 8 of 8 cases over 14 of 14 rows, worst Total 1.42e-14, exf cross-path 5.834e-16 over 7 cells with `TFLUX` bitwise. The residual gaps listed here are unchanged.] [**Superseded 2026-10-10 by RUNOFF-045:** `L_set_noatm`/`U_set_noatm` and rows T3-NL-set-noatm/T6-U-set-noatm are retired -- `RNF_CHECK` now refuses the no-`ALLOW_ATM_TEMP`-with-`temp_EvPrRn`-set combination they built, rather than letting it run and measuring the result, so no build can pass that case any more. Re-measured on the remaining 6 cases: Package figures 0.00e+00 on 6 of 6 cases over 12 of 12 rows, every other figure above unchanged. The retired algebra is tested as a refusal instead (`tests/rnf/refusal_check.py`, case `evprrn_runoff_temp`).]

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

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle. [**Superseded 2026-10-07 by RUNOFF-016:** the last clause no longer holds. `tests/rnf/budget_check.py` compares the applied tracer term against the file's source series per cell (worst 2.499e-16 against a 1e-12 criterion) and as a sum over all cells (2.079e-16). It is still **one** runoff tracer on **one** grid, with `RNF_trPtr`'s multi-tracer mapping unmeasured and no analytic decision-3 row for the term, so treat the gap as narrowed rather than closed.] [**Superseded again 2026-10-09 by RUNOFF-008:** the 2.499e-16 and 2.079e-16 above are the historical figures of a degenerate tracer series; on the non-degenerate one they are 2.667e-16 per cell and 1.962e-16 summed. The mapping is now measured on a `PTRACERS_num = 2` lab_sea build (`budget_check.py` case `lab_sea_ptr2` and its `swap` control), and `tendency_term_check.py` has analytic rows for the four linear-free-surface reference arms of the tracer term. Still lab_sea only.] [**2026-10-09, RUNOFF-031:** the terms are now surface terms (heat through exf `runoftemp`/`Qnet`, salt and tracers into `surfaceForcingS`/`surfaceForcingPTr`); re-derived: Package figures 0.00e+00 on 8 of 8 cases over 14 of 14 rows, worst Total 1.42e-14, exf cross-path 5.834e-16 over 7 cells with `TFLUX` bitwise. The residual gaps listed here are unchanged.] [**Superseded 2026-10-10 by RUNOFF-045:** `L_set_noatm`/`U_set_noatm` and rows T3-NL-set-noatm/T6-U-set-noatm are retired -- `RNF_CHECK` now refuses the no-`ALLOW_ATM_TEMP`-with-`temp_EvPrRn`-set combination they built, rather than letting it run and measuring the result, so no build can pass that case any more. Re-measured on the remaining 6 cases: Package figures 0.00e+00 on 6 of 6 cases over 12 of 12 rows, every other figure above unchanged. The retired algebra is tested as a refusal instead (`tests/rnf/refusal_check.py`, case `evprrn_runoff_temp`).]

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

**Scope narrowed 2026-10-10 by RUNOFF-046.** Everything above is the **legacy route** (`RNF_applyAsRain = .TRUE.`), which RUNOFF-046 restricts to files whose every target is its column's surface cell, so the residual is unchanged and needs no text about mixed-level files. On the new default, the generalized route, the heat is a tendency at the target level and is not part of `Qnet`, so no open-water scaling applies to it; but `pkg/seaice`, `pkg/thsice` and `pkg/bling` see none of that runoff (they read the exf `runoff` array, which stays zero on that route), a gap the owner accepted in the RUNOFF-046 decision. A budget under ice for this issue therefore has two routes to state.

Carry forward from RUNOFF-010 review B, restated: the scaling above is `pkg/seaice`'s with `SEAICE_EXTERNAL_FLUXES`. Without that option `pkg/seaice` computes its own open-water flux and does not use exf `Qnet` at all (`seaice_budget_ocean.F:110-149`), so none of the exf runoff heat would arrive, on either path; under `pkg/thsice` `Qnet` keeps `opFrac·Qnet` (`thsice_step_fwd.F:273-275`) and thsice adds runoff heat at the surface temperature for the ice-covered share itself (`thsice_map_exf.F:104-121`), so the undelivered part there is `(1 − opFrac)` of the runoff's departure from θ. Measure all three.

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


## UNRESOLVED: no diagnosability for a diagTitle fixed-width overflow in rnf_diagnostics_init.F

**Date Identified**: 2026-10-05T08:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-047
**Anchors**: MITgcm/pkg/rnf/rnf_diagnostics_init.F::<module>; tests/runoff/test_write_formats.py::<module>

### Issue or research question
Split out of RUNOFF-034 (carry forward from RUNOFF-013 review B, correction round 1, 2026-10-05) so it is not lost when that issue closes. `rnf_diagnostics_init.F` writes fixed-width diagnostic names and titles, and `test_write_formats.py` does not check that a title fits its field.

### Evidence
Review B (RUNOFF-013, correction round 1) measured that the *class* is already caught loudly rather than silently: every runoff experiment sets `useDiagnostics=.TRUE.`, so an overflow aborts all of them, which is the opposite of a silent pass. What is missing is **diagnosability** — the abort does not say which title overflowed.

### Scientific or engineering impact
Low. This is explicitly not a detection gap (the class is already caught); the value of a fix is a better message, not new coverage. Keep the distinction, because recording it as a detection gap would overstate the risk.

### Proposed action and acceptance
Give `RNF_DIAGNOSTICS_INIT` (or the surrounding diagnostics setup) a message naming which `diagTitle`/`diagName` overflowed its fixed field, on the existing abort path. Acceptance: a deliberately-oversized title aborts with a message naming it; the existing abort-on-overflow behavior for every other title is unchanged.

## UNRESOLVED: refusals that need an open-boundary or blank-tile build (maskInC = 0 target, blank-tile target)

**Date Identified**: 2026-10-13T00:00:00Z
**Status**: Unresolved
**UUID**: RUNOFF-048
**Anchors**: MITgcm/pkg/rnf/rnf_init_fixed.F::<module>; tests/rnf/refusal_check.py::<module>

### Issue or research question
Split out of RUNOFF-017 (scout matrix, 2026-10-13). Two refusals have no enrolled case because no runoff experiment can reach them: refuse = 2, a target with `maskInC = 0` beyond an open boundary (`rnf_init_fixed.F:799-800`), and a target on a blank exch2 tile, which is caught only as a fraction deficit by the global sum (`rnf_init_fixed.F:1009-1047`, comment at :1044).

### Evidence
Scout read of `packages.conf` over all 17 runoff experiment configurations: no obcs, no blank tile (inferred from the package lists, not from the data files; verify before building). RUNOFF-019 lists `seaice_obcs` and `obcs_ctrl` as regional testbeds, which would supply the open-boundary build.

### Scientific or engineering impact
Highest silent-acceptance risk of the RUNOFF-017 list: a target the model never applies drops its mass, and the only guard for a blank tile is a fraction-sum deficit whose exact condition is untested on one.

### Proposed action and acceptance
Add an experiment with obcs and one with a blank exch2 tile (new `code/` directories; may reuse RUNOFF-019's testbed). Acceptance: a target beyond the open boundary stops with the refuse = 2 message; a target on a blank tile stops through the fraction deficit with a message naming the source, on `-mpi N`; each shown failing on a guard-removed mutant; a control with a valid target runs.

## UNRESOLVED: refusals that need a shelfice build (target under an ice shelf, SHI_update_kTopC)

**Date Identified**: 2026-10-13T00:00:00Z
**Status**: Unresolved
**UUID**: RUNOFF-049
**Anchors**: MITgcm/pkg/rnf/rnf_check.F::<module>; MITgcm/pkg/rnf/rnf_init_fixed.F::<module>

### Issue or research question
Split out of RUNOFF-017. `useRNF` with `useShelfIce` and `SHI_update_kTopC` is refused (`rnf_check.F:216`) and a target with `kTopC /= 0` is refused as refuse = 3 (`rnf_init_fixed.F:802-804`, under `#ifdef ALLOW_SHELFICE`). No runoff experiment compiles pkg/shelfice (0 hits in 17 configurations), so both branches are compiled-but-unexecuted.

### Evidence
Scout read of `packages.conf` (inferred; verify). Related: RUNOFF-020 (grids with ice-shelf cavities, top wet level below k = 1), which would supply the build.

### Scientific or engineering impact
Without the refusals the target "loses its volume" (code comment): silent mass loss under an ice shelf.

### Proposed action and acceptance
One shelfice + rnf build. Acceptance: a target under a shelf stops with the refuse = 3 message and `SHI_update_kTopC` stops with its message, each shown failing on a guard-removed mutant, with a control that runs. May share the build with RUNOFF-020.

## UNRESOLVED: restart-before-first-record refusal in synchronous nonlinear free-surface mode is never executed

**Date Identified**: 2026-10-13T00:00:00Z
**Status**: Unresolved
**UUID**: RUNOFF-050
**Anchors**: MITgcm/pkg/rnf/rnf_fields_load.F::<module>; tests/rnf/refusal_check.py::<module>

### Issue or research question
Split out of RUNOFF-017. `rnf_fields_load.F:173-190` stops a restart in synchronous nonlinear-free-surface mode whose time minus one step precedes the first record. The code comment (`rnf_fields_load.F:166-169`) says "No case is enrolled", and no experiment configures that branch. The same branch exercises `RNF_lagFlds = T`, which has never run (verification matrix, restart rows).

### Evidence
Scout read of the code and of `docs/verification_matrix.md:614-621`. Related: RUNOFF-022 (pickup/restart reproducibility).

### Scientific or engineering impact
Without the stop the lagged fields would be wrong or zero on restart. Rare branch; lower priority than RUNOFF-048 and RUNOFF-049.

### Proposed action and acceptance
Configure branch N (nonlinear free surface, real freshwater flux, no staggerTimeStep) with a restart. Acceptance: the stop fires on a file whose first record is after t - dt and is shown failing on a guard-removed mutant; a control with an earlier record or a repeat cycle runs. May be done together with RUNOFF-022.
