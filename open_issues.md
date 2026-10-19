# Open issues

Write each entry in ASD-STE100: short sentences and the active voice (see devel-loop/writing_standard.md).
The gate excludes fenced examples because they are templates. Use stable and unique IDs.
The statuses are Unresolved, Investigating and Blocked.
A blocked entry needs a `Blocked-By` field. The field has a project issue ID, EXTERNAL or OWNER-DECISION.
Then it has ` — ` and an explanation.
A closed dependency prompts a new look at the entry. It does not unblock the work automatically.

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
Sparse runoff must work correctly in these settings:
- `useRealFreshWaterFlux` true and false.
- A linear and a nonlinear free surface (`nonlinFreeSurf`, z* and r*).
- The salinity treatment of each setting: virtual salt flux or volume input.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
An error in the freshwater formulation changes sea level and salinity drift. Nothing warns the user.

### Proposed action and acceptance
Acceptance: test cases in at least one lat-lon configuration and one cs32 configuration for each combination. The volume and salt budgets close (RUNOFF-016).

Unblocked 2026-10-04: RUNOFF-004 closed.
- It added the sparse reader, the per-tile lists, the placement that copies the `mdsio_read_field.F` arithmetic, the `GLOBAL_SUM` fraction check and the exf volume flux.
- The fork commit is `610d4cbaf`. The final verification receipt is `2e11b06d`. All 33 scientific commands passed.
- At that time the reader accepted one constant record only. `rnf_init_fixed.F:199-217` stopped the run for `RNF_useYearlyFiles` or for any `RNF_period` other than 0. The message named RUNOFF-005.
- RUNOFF-005 closed on 2026-10-05 and added the time handling (see RUNOFF-029).

Part 1 finished (partial closeout, 2026-10-19). It covers lab_sea and the default route:
- `tests/rnf/fs_matrix_check.py` runs eight configurations: a linear free surface, and `nonlinFreeSurf = 4` with `select_rStar` 0, 1 and 2, each with `useRealFreshWaterFlux` false and true. The model accepts all eight.
- The model refuses three other settings with its own messages:
  - a nonlinear free surface without `NONLIN_FRSURF`
  - a nonlinear free surface without `exactConserv`
  - a real flux with a nonlinear free surface and `LS_whenToSample = 0`
  A real flux with a nonlinear free surface needs `LS_whenToSample = 2`.
- All eight pass the first-step placement (cell-wise 5.2e-13), the step-1 content budget and a 24-step volume closure. The volume residual is at most 0.64 m³ of 1.7e10 m³, against a tolerance of 23 m³ taken from the noise of the zero run.
- A mutant that skips the cancellation of the generic `temp_addMass` term in the nonlinear branch fails the case `deep_set` in all six nonlinear configurations.
- On nonlinear grids the salt, heat and tracer budgets after step 1 are 2e-4 to 3e-2 of the injected amount. The check reports them and does not assert them. The model's own `addMass` gives the same fields bit for bit, so this is a model property, not a defect of the package. The residual falls linearly with the flux.
- With `LS_whenToSample = 0`, virtual flux and a nonlinear free surface, the tracer tendency differs from the thickness ratio by 4.5e-5. This is the model's step order, not a defect of the package. With `LS_whenToSample = 2` it agrees to 6e-15.
- The check is not in a suite of `esx/project.json`.
Remaining for this issue:
- The same configurations on cs32.
- Cases with `staggerTimeStep` false, with more than one source, and with sea ice.
- A salt and tracer budget on nonlinear grids that closes to round-off, or an exact identity that explains the residual.
- A note on `LS_whenToSample = 0` for tracers in `docs/package_design.md`, and a decision on adding the check to the standard or the full suite.

## UNRESOLVED: global_ocean.90x40x15 and global_oce_latlon sparse runoff testbeds

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-018
**Anchors**: MITgcm/verification/global_ocean.90x40x15/input/data::<module>; MITgcm/verification/global_oce_latlon/input.yearly/data::<module>

### Issue or research question
Cover the global lat-lon grids. Make dense-path references and sparse equivalents for these experiments. Include the yearly-forcing variant, with and without T and S.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
The test grids cover more than the regional lab_sea grid.

### Proposed action and acceptance
Acceptance: dense references exist. The sparse run equals the dense run to the digit threshold, for a single process and for MPI. The budget checks pass.

Unblocked 2026-10-04: RUNOFF-004 closed.
- It added the sparse reader, the per-tile lists, the placement that copies the `mdsio_read_field.F` arithmetic, the `GLOBAL_SUM` fraction check and the exf volume flux.
- The fork commit is `610d4cbaf`. The final verification receipt is `2e11b06d`. All 33 scientific commands passed.
- At that time the reader accepted one constant record only. `rnf_init_fixed.F:199-217` stopped the run for `RNF_useYearlyFiles` or for any `RNF_period` other than 0. The message named RUNOFF-005.
- RUNOFF-005 closed on 2026-10-05 and added the time handling (see RUNOFF-029).

## UNRESOLVED: Regional open-boundary testbeds (seaice_obcs, obcs_ctrl)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-019
**Anchors**: MITgcm/verification/seaice_obcs/input/data::<module>

### Issue or research question
Test runoff in regional configurations with open boundaries. Include sources near the boundary.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
Regional models are a main use case. The boundary handling must not interact badly with runoff.

### Proposed action and acceptance
Acceptance: sparse = dense cases (or cases that pass a budget check), for a single process and for MPI.

Open-boundary rule (RUNOFF-010 design, decision 5):
- The package refuses a target with `maskInC = 0` at init, and the message names the source.
- The reason: with `useRealFreshWaterFlux`, the code multiplies `EmPmR` by `maskInC` (`external_forcing_surf.F:149-156`).
- Test a source in the first interior cell. Test the refusal beyond the boundary.
- Find out from `pkg/obcs/obcs_init_fixed.F` if the boundary row itself has `maskInC = 0`.

Carry forward from RUNOFF-010 review A: the loops that set `maskInC` to zero start at the open-boundary index itself (`obcs_init_fixed.F:79-87` and `296-301`). So the package refuses a target on the boundary row at init.

Unblocked 2026-10-04: RUNOFF-004 closed.
- It added the sparse reader, the per-tile lists, the placement that copies the `mdsio_read_field.F` arithmetic, the `GLOBAL_SUM` fraction check and the exf volume flux.
- The fork commit is `610d4cbaf`. The final verification receipt is `2e11b06d`. All 33 scientific commands passed.
- At that time the reader accepted one constant record only. `rnf_init_fixed.F:199-217` stopped the run for `RNF_useYearlyFiles` or for any `RNF_period` other than 0. The message named RUNOFF-005.
- RUNOFF-005 closed on 2026-10-05 and added the time handling (see RUNOFF-029).

## UNRESOLVED: Runoff on grids with ice-shelf cavities (top wet level below k=1)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-020
**Anchors**: MITgcm/verification/isomip/input.icefront/data::<module>; MITgcm/pkg/shelfice/shelfice_init_depths.F::<module>

### Issue or research question
Under an ice shelf, the top wet cell is `kSurfC > 1`.

Design (RUNOFF-010, docs/package_design.md, decision 5):
- `SHELFICE_FORCING_SURF` sets `EmPmR` to zero where `kTopC ≠ 0` (`shelfice_forcing_surf.F:57-69`).
- So phase 1 refuses targets under a shelf. It serves sources at the ice front, in open water, through the surface path.
- Targets under a shelf wait for the `addMass` path (RUNOFF-025).

Two more facts:
- isomip does not compile exf. It needs an exf test variant.
- Icefront and shelfice must not count the same water as runoff.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
Glacier runoff near ice fronts is a core use case. A k=1 assumption puts water into dry cells.

### Proposed action and acceptance
Acceptance: cases with sources at the ice front and in open water. The budgets close. The test checks the refusal of a land or dry target.

Update, 2026-10-10, RUNOFF-046: this entry is smaller now.
- The `addMass` path that this entry waited for exists. The generalized route (`RNF_applyAsRain = .FALSE.`, the default) puts each target entry at its own level. A schema-1.1 `target_level` can name any wet level.
- Two refusals still apply on both routes: a target under an ice shelf (`kTopC ≠ 0`, in `RNF_INIT_FIXED`), and `SHI_update_kTopC` (in `RNF_CHECK`).
- Work that remains here: (1) lift these two refusals for the generalized route. This is a code change of a few lines after a test exists. (2) Write that test. The test needs the exf gap of isomip closed in a separate step. No `packages.conf` variant of isomip lists `exf`, and no input variant has a `data.exf`. `pkg/rnf` needs `useEXF` on both routes, because its record selection is the own code of pkg/exf.
- The legacy route stays surface-only. It does not take targets under a shelf.

Moving shelf edge (RUNOFF-010 design, decision 5):
- With `SHI_update_kTopC` (`ALLOW_SHELFICE_REMESHING` and `SHELFICEMassStepping`), the model resets `kTopC` at each step (`shelfice_thermodynamics.F:239-256`). A target that is open at init can come under the shelf.
- `RNF_CHECK` refuses `useRNF` with `SHI_update_kTopC` until the `addMass` path exists (RUNOFF-025). Test that refusal here.

Unblocked 2026-10-06: RUNOFF-013 closed, so the dependency that this entry waited on is met. The code implements the tendency terms, and tests measured them:
- 8 of 8 analytic cases pass over 10 of 10 decision-3 table rows.
- Every Package figure is bitwise zero. The worst Total is 1.43e-14, against an acceptance of 1e-12.
- The exf cross-path agrees to 3.559e-16 over 7 cells.
- Both acceptance instruments are in the suites: `tests/rnf/tendency_term_check.py` and `tests/rnf/exf_heat_check.py`.

Gaps that this entry must assume and not find again. At that date:
- Every tendency case ran on a single process.
- Nothing executed branch N and the lagged time level (`RNF_lagFlds = T`).
- The tracer term had no numerical oracle.

Later updates change these gaps:
- 2026-10-07, RUNOFF-016: the last gap is smaller. `tests/rnf/budget_check.py` compares the applied tracer term with the source series of the file. It does this per cell (worst 2.499e-16 against a criterion of 1e-12) and as a sum over all cells (2.079e-16). It is still one runoff tracer on one grid. The multi-tracer mapping of `RNF_trPtr` is not measured. The term has no analytic decision-3 row. The gap is narrower, but it is not closed.
- 2026-10-09, RUNOFF-008: a degenerate tracer series gave the figures 2.499e-16 and 2.079e-16. On the non-degenerate series they are 2.667e-16 per cell and 1.962e-16 summed. The mapping is now measured on a `PTRACERS_num = 2` lab_sea build (`budget_check.py` case `lab_sea_ptr2` and its `swap` control). `tendency_term_check.py` has analytic rows for the four linear-free-surface reference arms of the tracer term. It is still lab_sea only.
- 2026-10-09, RUNOFF-031: the terms are now surface terms. Heat goes through exf `runoftemp` and `Qnet`. Salt and tracers go into `surfaceForcingS` and `surfaceForcingPTr`. Re-derived figures: Package 0.00e+00 on 8 of 8 cases over 14 of 14 rows, worst Total 1.42e-14, exf cross-path 5.834e-16 over 7 cells with `TFLUX` bitwise. The gaps are the same.
- 2026-10-10, RUNOFF-045 retired the cases `L_set_noatm` and `U_set_noatm`, and the rows T3-NL-set-noatm and T6-U-set-noatm. `RNF_CHECK` now refuses the combination that they built: no `ALLOW_ATM_TEMP` with `temp_EvPrRn` set. Before, the run went on and the test measured the result. No build can pass that case now. Re-measured on the 6 remaining cases: Package figures 0.00e+00 on 6 of 6 cases over 12 of 12 rows. Every other figure above is the same. The case `evprrn_runoff_temp` in `tests/rnf/refusal_check.py` tests the refusal.

## UNRESOLVED: LLC grid coverage

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-021
**Anchors**: docs/verification_matrix.md::<module>

### Issue or research question
No LLC experiment is in `verification/`. Find a configuration that builds. Two examples: the `global_oce_llc90` inputs from the MITgcm verification data, or a small LLC grid that we construct. Use it to test the exch2 LLC mapping of target cells.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

Known gap: the capability boundaries in `esx/project_profile.md` list no LLC experiment.

### Scientific or engineering impact
LLC is a main production grid (the 2 km target). A mapping error on this grid is a top risk.

### Proposed action and acceptance
Acceptance: one of two results. Either a runnable LLC test with sparse runoff and budget checks, or a documented blocker that the owner can see, with the exact missing input.

## UNRESOLVED: Thread, MPI and tile-layout independence (do_tst_2+2)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-023
**Anchors**: MITgcm/tools/do_tst_2+2::<module>

### Issue or research question
The results must not depend on the tile size, the MPI layout or the OpenMP threads. The MITgcm 2+2 restart test must pass with the package active.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

Also see the MITgcm contribution rules in `esx/project_profile.md`.

### Scientific or engineering impact
Upstream acceptance needs this. Correctness on large machines needs it too.

### Proposed action and acceptance
Acceptance: the results are the same across at least three layouts for each grid. `do_tst_2+2` is clean.

Unblocked 2026-10-06: RUNOFF-013 closed, so the dependency that this entry waited on is met. The code implements the tendency terms, and tests measured them:
- 8 of 8 analytic cases pass over 10 of 10 decision-3 table rows.
- Every Package figure is bitwise zero. The worst Total is 1.43e-14, against an acceptance of 1e-12.
- The exf cross-path agrees to 3.559e-16 over 7 cells.
- Both acceptance instruments are in the suites: `tests/rnf/tendency_term_check.py` and `tests/rnf/exf_heat_check.py`.

Gaps that this entry must assume and not find again. At that date:
- Every tendency case ran on a single process.
- Nothing executed branch N and the lagged time level (`RNF_lagFlds = T`).
- The tracer term had no numerical oracle.

Later updates change these gaps:
- 2026-10-07, RUNOFF-016: the last gap is smaller. `tests/rnf/budget_check.py` compares the applied tracer term with the source series of the file. It does this per cell (worst 2.499e-16 against a criterion of 1e-12) and as a sum over all cells (2.079e-16). It is still one runoff tracer on one grid. The multi-tracer mapping of `RNF_trPtr` is not measured. The term has no analytic decision-3 row. The gap is narrower, but it is not closed.
- 2026-10-09, RUNOFF-008: a degenerate tracer series gave the figures 2.499e-16 and 2.079e-16. On the non-degenerate series they are 2.667e-16 per cell and 1.962e-16 summed. The mapping is now measured on a `PTRACERS_num = 2` lab_sea build (`budget_check.py` case `lab_sea_ptr2` and its `swap` control). `tendency_term_check.py` has analytic rows for the four linear-free-surface reference arms of the tracer term. It is still lab_sea only.
- 2026-10-09, RUNOFF-031: the terms are now surface terms. Heat goes through exf `runoftemp` and `Qnet`. Salt and tracers go into `surfaceForcingS` and `surfaceForcingPTr`. Re-derived figures: Package 0.00e+00 on 8 of 8 cases over 14 of 14 rows, worst Total 1.42e-14, exf cross-path 5.834e-16 over 7 cells with `TFLUX` bitwise. The gaps are the same.
- 2026-10-10, RUNOFF-045 retired the cases `L_set_noatm` and `U_set_noatm`, and the rows T3-NL-set-noatm and T6-U-set-noatm. `RNF_CHECK` now refuses the combination that they built: no `ALLOW_ATM_TEMP` with `temp_EvPrRn` set. Before, the run went on and the test measured the result. No build can pass that case now. Re-measured on the 6 remaining cases: Package figures 0.00e+00 on 6 of 6 cases over 12 of 12 rows. Every other figure above is the same. The case `evprrn_runoff_temp` in `tests/rnf/refusal_check.py` tests the refusal.

## UNRESOLVED: Runoff with sea ice (runoff into ice-covered cells)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-024
**Anchors**: MITgcm/verification/lab_sea/input/data.seaice::<module>

### Issue or research question
Find out how the model behaves when runoff enters cells with sea ice. Cover pkg/seaice, and thsice where the run uses it. The freshwater and the heat go to the ocean, and the sea-ice growth responds. Exf must not count the same water twice.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
Arctic and Greenland runoff enters ice-covered seas.

### Proposed action and acceptance
Acceptance: lab_sea and cs32 sea-ice cases with budget checks. Richard checks the sea-ice coupling path.

The owner clarification of 2026-10-18 below sets the acceptance for the default route.

Inherited residual, restated for the surface route (RUNOFF-031, 2026-10-09). This text describes the legacy route:
- Since RUNOFF-031, the whole runoff heat term is part of exf `Qnet`. `RNF_EXF_RUNOFF` fills `runoftemp`. `EXF_MAPFIELDS` adds `−Cp·[(mT) − m_T·θ]` (the `RNFqnet` diagnostic). Exf also has its own `temp_EvPrRn` term for the runoff.
- Under `pkg/seaice` with `SEAICE_EXTERNAL_FLUXES`, `seaice_growth.F:956-957` keeps only the open-water share `(1 − A)` of exf `Qnet`. `A` is `AREApreTH`.
- So at an ice fraction `A`, the part `A·[(mT) − m_T·θ]μ` of the runoff heat reaches neither the ocean nor the ice. This holds with `temp_EvPrRn` unset and with it set.
- With `temp_EvPrRn` set and `ALLOW_ATM_TEMP`, the code also drops the cancellation `A·m(θ − temp_EvPrRn)μ`. RUNOFF-010 derived this residual for the tendency route, where only that part had the factor.
- The model does not scale its own freshwater term. It does not scale the runoff volume, salt or tracers.
- The dense `runoftempfile` path behaves in the same way, because both paths share the code from `EXF_MAPFIELDS` on. The tendency route that no longer exists delivered the source heat under ice.

Measured by review A of RUNOFF-031 (Richard `ad7dd3fab4c8e2736`, witness `devel-loop/loop_state/scratch/ad7dd3fab4c8e2736/ice_heat_witness_labels.json`). The setup was lab_sea with pkg/seaice on, the `tests/rnf/kpp_heat_check.py` pair (a source of 25 °C on cell 52), and `SEAICE_initialHEFF = 1`:
- At the first wet step, `AREApreTH = 0.98911` and `RNFqnet = −262.30 W/m²`.
- The ocean receives 0.308 W/m² (`ΔTFLUX`). Reduced freezing takes 2.548 W/m². Together they equal `(1 − A)·262.30` to 1.07e-12.
- The remaining `A·Q = 259.44 W/m²` goes nowhere.
- Without ice, the same pair gives a `ΔTFLUX` equal to the analytic heat, at a relative difference of 0.0.

Acceptance for this issue, as written at that date: a heat budget under ice that states this share, or a decision to deliver it. A decision to deliver it departs from the dense convention. Measure on lab_sea and cs32. Consider a note from `RNF_CHECK` or `RNF_SUMMARY` when runoff with a temperature meets `pkg/seaice`.

Scope narrowed 2026-10-10 by RUNOFF-046:
- Everything above is the legacy route (`RNF_applyAsRain = .TRUE.`). RUNOFF-046 limits it to files where every target is the surface cell of its column. So the residual is the same, and the text needs nothing about files with mixed levels.
- On the new default, the generalized route, the heat is a tendency at the target level. It is not part of `Qnet`, so no open-water factor applies to it.
- `pkg/seaice`, `pkg/thsice` and `pkg/bling` see none of that runoff, because they read the exf `runoff` array, which stays zero on that route. The owner accepted this gap in the RUNOFF-046 decision.
- A budget under ice for this issue therefore has two routes to state.

Owner clarification, 2026-10-18. It sets the acceptance for the default route:
- The default is that the runoff heat enters through the ocean temperature tendency `gT`, not through `Qnet`.
- The figure of 259 W/m² above belongs to the legacy route only. It is not a defect of the default.
- Some of the heat on the default route does not appear as an ocean temperature change, because it melts sea ice. We expect this.
- So the budget for this issue must include the change in sea-ice and snow volume.
- The budget is `runoff heat delivered = change in ocean heat content + latent heat of the change in ice and snow volume + any change in ice heat content`.
- Measure on lab_sea and cs32 with `pkg/seaice` on.
- Acceptance for the default route: that budget closes to a stated tolerance with the ice term included. A control without the ice term fails it.
- `pkg/seaice` and `pkg/thsice` still see none of the runoff volume on this route (accepted in RUNOFF-046). So the freshwater side of the budget needs no ice term.

Part 1 is done (partial closeout, 2026-10-19). It covers the default route on lab_sea with `pkg/seaice` on:
- `tests/rnf/ice_heat_check.py` runs lab_sea on `build_esx_addm` with the runoff source on a fully ice-covered cell. It compares a run with a warm runoff temperature with a run without one.
- The delivered heat is the sum of `RNFgT` over the cells and the steps. The budget is `delivered = change in ocean heat content + melt heat of the ice and snow lost`. The ice heat content has no change, because the ice model has no enthalpy state.
- Measured: the ocean takes 0.352 of the delivered heat and the melt of ice takes 0.663. The residual is 0.011 to 0.023 of the delivered heat. A run pair with `pkg/seaice` off has a residual of the same size, so the residual does not come from the ice. Its cause is unknown.
- The tolerance is 0.03. Three controls fail: no ice term (0.648), the wrong sign (1.311) and the snow density for the ice (0.407). Errors of the ice term inside -6.9 to +2.2 percent still pass.
- The snow term is not verified. No tested cell gave a failing snow control.
- The check is not in a suite of `esx/project.json`.
Remaining for this issue:
- The same budget on cs32 with `pkg/seaice`.
- The legacy route: `pkg/seaice` with `SEAICE_EXTERNAL_FLUXES`, `pkg/seaice` without it, and `pkg/thsice`.
- A start state with snow at the target cell, so that a snow control fails.
- The cause of the residual of 0.011 to 0.023, and a decision on adding the check to the standard or the full suite.

Carry forward from RUNOFF-010 review B, restated:
- The scaling above belongs to `pkg/seaice` with `SEAICE_EXTERNAL_FLUXES`.
- Without that option, `pkg/seaice` computes its own open-water flux. It does not use exf `Qnet` at all (`seaice_budget_ocean.F:110-149`). So none of the exf runoff heat arrives, on either path.
- Under `pkg/thsice`, `Qnet` keeps `opFrac·Qnet` (`thsice_step_fwd.F:273-275`). Thsice itself adds the runoff heat at the surface temperature for the ice-covered share (`thsice_map_exf.F:104-121`). So the part that does not arrive is `(1 − opFrac)` of the departure of the runoff from θ.
- Measure all three cases.

## UNRESOLVED: MITgcm coding standards and TAF-friendliness review

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-027
**Anchors**: MITgcm/doc/contributing/contributing.rst::<module>

### Issue or research question
Check all new Fortran against the MITgcm standards:
- fixed form and 72 columns
- CPP guards
- `_RL` and `_RS`
- `myThid` and `bi,bj` loops
- the order of the header includes
- no tabs
- the comment style
- `STOP` through the ERROR handling
- TAF compatibility (store directives where needed)

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
An upstream pull request needs this.

### Proposed action and acceptance
Acceptance: a scripted lint of the new files passes. The reviewer checklist is complete.

Carry forward from RUNOFF-010 review B: the previous-step field set of the time-level rule is state that the model carries between steps. It needs store directives like the exf record fields. Or the model must recompute it from the model time at each step. Review A: when the surface levels differ between columns (RUNOFF-025), the 2D state-dependent diagnostics need one fill for each step.

Carry forward from RUNOFF-012:
- The lint must search for `RUNOFF-[0-9]` and the URL of the development repository. Stub comments, one run-time message and `README.md` contain them. Sweep them as the stubs get their code.
- RUNOFF-012 deferred the TAF list files (`rnf_ad_diff.list` and `rnf_ad.flow`) to this issue, because they need a TAF build.

Unblocked 2026-10-03: RUNOFF-012 closed (pkg/rnf skeleton, fork commit `ac33291aa`).

Part 1 finished (partial closeout, 2026-10-19):
- `tests/runoff/test_fortran_standards.py` is a static lint with nine rules. It reads `pkg/rnf` and the added lines of the hook files (the diff against `upstream/master`). It is part of the standard suite, because `tests/runoff` runs under `pytest -q`.
- Each rule fails on a mutant. Three named exceptions carry a reason. The hook part reports `HOOK LINT NOT RUN` as a warning on a clone without the `upstream` remote.
- The sweep fixed 82 findings in `pkg/rnf` (51 tracker ids or URLs, 23 CPP comments, 8 long comment lines) and 13 in the hook lines. It changed comments, line breaks, `#endif` comments, one `ALLOW_RNF` guard and one message text. A statement-level diff by Richard A found no other change.
- `docs/code_standards_checklist.md` is the reviewer checklist.
Open for this issue:
- TAF: store directives, `rnf_ad_diff.list` and `rnf_ad.flow` need a TAF build. This includes the RUNOFF-010 review B item on the state of the previous-step fields.
- Manual items: the choice between `_RL` and `_RS` per variable, the `bi,bj` loops, thread safety, and the contribution items outside the code.
- About 44 comments that cite the package design and 21 pointers to files of the development repository remain in `pkg/rnf` and `doc/phys_pkgs/rnf.rst`. Richard B recommends removing them or making them self-contained before an upstream pull request.
- The text of rule i still occurs in `doc/phys_pkgs/rnf.rst` (a URL) and in 5 lines of `utils/python/MITgcmutils/MITgcmutils/runoff/*.py`. A strict expected failure in the lint tracks them.

## BLOCKED: Upstream readiness: full testreport master vs branch, MPI and 2+2

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-023 — needs layout independence first
**UUID**: RUNOFF-028
**Anchors**: MITgcm/verification/testreport::<module>

### Issue or research question
Before any pull request, do these steps:
- Run the full testreport on master and on the branch, also with `-mpi`. The diff must be clean except for the new experiments.
- Run `do_tst_2+2`.
- Complete the contribution checklist.
- Write the text of the pull request, with a tag-index suggestion.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
This is the final gate before we propose the package upstream. The owner must still approve the pull request.

### Proposed action and acceptance
Acceptance: the `tr_out` diff is clean. The 2+2 test is clean. The checklist is complete.

## UNRESOLVED: Time modes for T, S and tracer series (all five modes for every series)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-029
**Anchors**: MITgcm/pkg/exf/exf_getffieldrec.F::<module>

### Issue or research question
Every time series must follow the same time modes and the same interpolation. The series are the flux, the temperature, the salinity and each tracer. The modes are constant, daily or fixed, monthly, monthly climatology and yearly files. The records must agree with the flux records.

### Evidence
Owner direction, 2026-10-02 (the owner was away for several days):
- Develop and test the new runoff program in many MITgcm configurations.
- Test with and without T, S and tracer contributions, and in every time mode.
- Make it `a robust, documented MITgcm package` that follows the MITgcm coding standards.
- Apply the T and S fluxes in the same way as the shelfice and icefront tendencies.

### Scientific or engineering impact
If the record selection for the flux and for T and S do not match, the model mixes the wrong properties.

### Proposed action and acceptance
Acceptance: lab_sea cases for each mode, with T, S and tracers. The direct timing checks cover all series.

Reconsidered 2026-10-05, when RUNOFF-005 closed:
- RUNOFF-005 finished the flux time handling that this issue waited for.
- The acceptance of this issue says: `lab_sea cases per mode with T/S/tracers; direct timing checks extended to all series`. At that date, the model did not read or apply any T, S or tracer series.
- So the real dependency is RUNOFF-013, not RUNOFF-005. The entry waits again for RUNOFF-013, not for a closed issue.
- RUNOFF-005 gives the pattern to extend. `RNF_GETREC` hands each mode to its `pkg/exf` routine. A second series needs the same hand-over, not its own record logic.
- `tests/runoff/lab_sea_runoff_timing_check.py` already compares the record trace of the model with the exf conventions at every forcing step. Extending it to a second series is the shape of the check for this issue.

## UNRESOLVED: cs32 sparse-runoff oracle (exch2 volume path; runoff temperature cell-by-cell)

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-006
**Anchors**: MITgcm/pkg/exf/exf_mapfields.F::<module>; tests/mitgcm_oracle.sh::<module>

### Issue or research question
Convert `core_rnof_1_cs32.bin` and `runoff_temperature.bin`. Add cs32 `input.<X>` variants of `input.icedyn` and `input.seaice` that use the sparse path.

### Evidence
`global_ocean.cs32x15` is the only experiment with exf runoff. It has 6 faces of 32×32 cells and 12 tiles. `SIZE.h_mpi` has 4 processes with 3 tiles each.

### Scientific or engineering impact
The oracle checks the exch2 index mapping. It checks sources that span faces, tiles and processes. It checks the runoff temperature.

### Proposed action and acceptance
Design (RUNOFF-010, docs/package_design.md):
- The runoff temperature enters as a tendency term, not through exf `runoftemp`.
- It differs from the exf term under sea ice, because exf scales it by the open-water fraction (`seaice_growth.F:956-957`).
- The volume oracle stays. `input.icedyn` and a variant of `input.seaice` without runoff temperature must match the dense references.
- Check the runoff temperature cell by cell in ice-free cells. Compare dense `EXFroff`, `EXFroft` and `THETA` with the heat diagnostic of the package.

Acceptance: the cases with volume only match their dense references to the digit threshold, for a single process and for `-mpi 4`.

From RUNOFF-002: `verification/global_ocean.cs32x15/input.rnof_sparse/runoff_sparse.nc` holds the cs32 conversion. It has 1189 sources and 12 records, with flux and temperature. All 12 cs32 records are identical in time. So the cs32 oracle cannot detect a timing error. The lab_sea cases cover the timing.

Carry forward from RUNOFF-005 (review B, correction rounds 1 and 2, 2026-10-05). There are three items. We measured all three, and none is a defect. We file them here because this issue owns the no-`pkg/cal` path. The first two items are reachable only on that path, and the 12-record file of cs32 is the first thing that will use it.

1. The tolerance for the repeat cycle disagrees with the own test of exf, on the no-cal path only.
   - `RNF_TIME_SETUP` consistency check 7 accepts a repeat cycle within 1e-3 s of `nRecFile·period`.
   - On the no-`pkg/cal` path, `GET_PERIODIC_INTERVAL` stops unless `cycleLength` equals `nbRec·recSpacing` exactly.
   - So a file that is off by less than 1e-3 s passes init and then aborts at the first step. The failure comes late, and it is not an init refusal.
   - No configured command uses the no-cal path today, so nobody can reach this case now.
2. Hold-exact inherits the +0.5 s record rounding of exf.
   - `INT((fldsectot+0.5)/fldPeriod)+1` means that the next record applies in the last half second before a record time.
   - This is negligible for periods of 3600 s and more.
   - The ruling of review B on both items explains why we carry them and do not fix them.
   - Each item is faithfulness to `pkg/exf`. The hand-over to the record-selection routines of exf exists so that the sparse path cannot drift from the dense oracle. The dense oracle is its acceptance criterion.
   - A "fix" would make the sparse path differ from the dense path that we measure it against.
   - Change them only if exf changes, or if a measured defect appears on the no-cal path.
   - Add a line to the `RNF_GETREC` header when somebody next touches it.
3. `timing_field_check.py --min-discrimination` can become tighter, from 5e-3 to about 2e-2.
   - The sealed runs of review B passed at 2.1e-2 on both spans: the rejected 1980-12-01 span and the committed 1981-12-01 span. So the floor has a margin of about 4.3x.
   - A tighter floor would warn sooner if a later change of span lowered the discrimination. RUNOFF-005 had this failure once: the chosen span could not detect the most likely wrong anchoring.
   - The right place for this change is the issue that next touches that span.

Reconsidered 2026-10-04, when RUNOFF-004 closed. RUNOFF-004 met both original dependencies of this issue: the reader, and the RUNOFF-002 converter.
- Half of the acceptance is already met. RUNOFF-004 made `global_ocean.cs32x15/input.rnof_sp_icedyn`. It uses record 1 of `core_rnof_1_cs32.bin` as one constant record with 1189 one-cell sources.
- It matches the dense `results/output.icedyn.txt` at 11 matching digits, for a single process and for `-mpi 4`. This is the criterion "volume-only cases match their dense references, single-process and -mpi 4".
- Review A also proved that the exch2 placement is bijective over all 6144 cells, with per-process counts 321+443+151+274.
- What remains is smaller than the original scope. First, the 12-record file (`input.rnof_sparse/runoff_sparse.nc`), which needs RUNOFF-005. Second, the check of the runoff temperature cell by cell, which needs the tendency term of RUNOFF-013.
- The entry waits again for those two issues, not for a closed issue.
- Keep the recorded limit: all 12 cs32 records are identical in time, so this oracle cannot detect a timing error. The timing stays with lab_sea.

Reconsidered 2026-10-05, when RUNOFF-005 closed. It was the second of the two dependencies to close. Half of what remains is actionable now and half is not. Read the acceptance with care before you start.
- Actionable now: the oracle with the 12-record file `input.rnof_sparse/runoff_sparse.nc` on the exch2 volume path, because the sparse time handling exists. This oracle also covers what RUNOFF-005 implemented and could not test. Cs32 has no `pkg/cal`, so its times are seconds of model time on a 360_day file calendar. No configured command reaches the whole no-`pkg/cal` branch of `RNF_TIME_SETUP` today. This includes its three refusals at lines 491, 497 and 579, which no test covers. A 12-record cs32 file reaches that branch.
- Still blocked: the check of the runoff temperature cell by cell. It needs the tendency term of RUNOFF-013.
- Choose one of two ways. Split the volume and no-cal half into its own issue, so that somebody can do it now. Or do it here, and do not claim closure until RUNOFF-013 lands.
- Keep the recorded limit: all 12 cs32 records are identical in time, so this oracle cannot detect a timing error. The timing stays with lab_sea.

## BLOCKED: Per-record parallel I/O strategy at 2 km scale

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-028 — owner decision 2026-10-09: phase 1 (every process reads the full record) ships in the upstream PR. The single-reader scatter is a to-do after it
**UUID**: RUNOFF-007
**Anchors**: docs/model_contract.md#scale-requirement; MITgcm/pkg/exf/exf_getffields.F::<module>

### Issue or research question
There are two options. In the first, every process reads the full record (a few MB) and keeps its own sources. In the second, one process reads the record and hands out the data. With thousands of processes, the first option can overload the file system.

### Evidence
The target is daily records for 50 years, with 10⁵ to 10⁶ coastal cells on a global 2 km grid (owner, 2026-09-29).

### Scientific or engineering impact
This sets the feasibility of production runs. The correctness of phase 1 does not depend on it.

### Proposed action and acceptance
The phase 1 default: every process reads the full record. The owner decides if a scatter design must exist before the upstream PR.

Owner decision, 2026-10-09: keep phase 1 as it is for the upstream PR. Add the single-reader scatter to the to-do list after it. Follow the `useSingleCpuIO` convention of MITgcm (the stated preference of the owner).
- Design: a `data.rnf` switch, for example `RNF_singleCpuIO`, with the default `.FALSE.`.
  - At init, each process sends the global source indices that its tiles need (`RNF_srcGlob`) to the reader process, in one collective call.
  - When the model needs a record, only the reader opens the file and reads it. It then sends each process its own values in one `MPI_Scatterv`.
- Traffic for each record: about the number of sources (about 8 MB for one float64 series of 10⁶ sources). Today it is the processes times that figure.
- Scope: only the record read (`RNF_NC_READ_FLUX` and `RNF_LOAD_REC`), with MPI under `ALLOW_USE_MPI`. The placement, the time handling and the tendency terms do not change.
- Acceptance: the results are bitwise identical to the phase 1 path on lab_sea `-mpi 2` and cs32 `-mpi 4`. This includes the budget and applied-field oracles. Only the reader opens the file (a test counts the opens). A single-process run does not change.
- Optional: the measured chunking read benchmark below, to size the benefit.

From RUNOFF-002 (review A): this issue owns the measured chunking read benchmark (docs/runoff_schema.md §8 and the scale requirement in docs/model_contract.md). The converter writes the default layout of §8: one record for each chunk, deflate, and pieces of about 4 MB along `source`.

## BLOCKED: support pkg/longstep with LS_nIter > 1 for runoff tracers (average the tracer input over the long step)

**Date Identified**: 2026-10-09T09:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-028 — owner decision 2026-10-09: do this after the upstream PR, with the single-reader scatter (RUNOFF-007). Phase 1 refuses this configuration instead (RUNOFF-043, option C)
**UUID**: RUNOFF-044
**Anchors**: MITgcm/pkg/rnf/rnf_forcing_surf.F::<module>; MITgcm/pkg/longstep/longstep_average.F::<module>

### Issue or research question
Make `RNF_TENDENCY_APPLY_PTR` exact for any `LS_nIter`. Pass its tracer input through the averaging of pkg/longstep, in the same way as `EmPmR` becomes `LS_fwFlux`. Today the package refuses `LS_nIter ≠ 1` (RUNOFF-043).

Update, 2026-10-09, RUNOFF-031: the routine is now `RNF_FORCING_SURF_PTR`. It adds the term to `surfaceForcingPTr` from `LONGSTEP_FORCING_SURF`. Read the design below with that name.

### Evidence
RUNOFF-043, review A of RUNOFF-008: at a dry-to-wet step with `LS_nIter = 2`, the ratio of delivered tracer to source-carried tracer is 2.0.

Pkg/longstep already has the averaging machinery. It uses `LONGSTEP_RESET_3D`, `LONGSTEP_FILL_3D` and `LONGSTEP_AVERAGE_3D` for `EmPmR`, `Qsw` and the velocities (`longstep_average.F:56-164`). It forbids restarts in the middle of a long step (`longstep_check_iters.F:33-40`), so new accumulators need no pickup. It has no autodiff code.

### Scientific or engineering impact
Only runs that combine tracers for each river (nutrients, dye) with long-stepped biogeochemistry need this. Phase 1 refuses that combination.

### Proposed action and acceptance
Design (Arch estimate, 2026-10-09):
- Add 2D accumulators for the runoff mass flux `m` and for `(mC_n)` of each runoff tracer. Put them in `RNF.h` under `#ifdef ALLOW_LONGSTEP`.
- Add one `#ifdef ALLOW_RNF` hook inside `LONGSTEP_AVERAGE`, beside the `EmPmR` sample. It calls `RNF_LONGSTEP_ACCUM`, which resets, fills and averages the accumulators with the own routines of longstep. The samples are then co-located with those of `EmPmR` for every `LS_whenToSample`.
- `RNF_TENDENCY_APPLY_PTR` uses the averages when longstep is active. `C_ref` stays the current tracer, as `LONGSTEP_FORCING_SURF` does.
- Remove the RUNOFF-043 refusal.

The main risk is the timing. We must prove that the averaged runoff and the averaged `EmPmR` come from the same steps for `LS_whenToSample` = 0, 1 and 2, with `RNF_lagFlds`.

Acceptance:
- The witness of review A gives a ratio of 1 to 1e-12 for `LS_nIter = 2`.
- Analytic tendency rows and a budget closure over long steps with time-varying runoff, under each `LS_whenToSample`.
- Mutant failures show that the code uses the averaging.
- The RUNOFF-043 refusal case becomes a case that ends normally.
- The no-change runs do not change.

Kind: scientific_change, risk supported_semantics (two Richards). Size: comparable to RUNOFF-008.

## UNRESOLVED: refusals that need an open-boundary or blank-tile build (maskInC = 0 target, blank-tile target)

**Date Identified**: 2026-10-13T00:00:00Z
**Status**: Unresolved
**UUID**: RUNOFF-048
**Anchors**: MITgcm/pkg/rnf/rnf_init_fixed.F::<module>; tests/rnf/refusal_check.py::<module>

### Issue or research question
This issue was split out of RUNOFF-017 (scout matrix, 2026-10-13). Two refusals have no case in the tests, because no runoff experiment can reach them:
- refuse = 2: a target with `maskInC = 0` beyond an open boundary (`rnf_init_fixed.F:799-800`).
- A target on a blank exch2 tile. Only the global sum catches it, as a fraction deficit (`rnf_init_fixed.F:1009-1047`, comment at :1044).

### Evidence
The scout read `packages.conf` in all 17 runoff experiment configurations. None has obcs and none has a blank tile. The scout inferred this from the package lists, not from the data files. Check it before you build.

RUNOFF-019 lists `seaice_obcs` and `obcs_ctrl` as regional testbeds. They would supply the open-boundary build.

### Scientific or engineering impact
This is the highest risk of silent acceptance in the RUNOFF-017 list. The model never applies a target of this kind, so it drops the mass. The only guard for a blank tile is a fraction-sum deficit, and nobody tested its exact condition on a blank tile.

### Proposed action and acceptance
Add an experiment with obcs. Add one with a blank exch2 tile. Both need new `code/` directories. They may reuse the testbed of RUNOFF-019.

Acceptance:
- A target beyond the open boundary stops with the message of refuse = 2.
- A target on a blank tile stops through the fraction deficit, with a message that names the source, on `-mpi N`.
- Each stop fails on a mutant without the guard.
- A control with a valid target runs.

## UNRESOLVED: refusals that need a shelfice build (target under an ice shelf, SHI_update_kTopC)

**Date Identified**: 2026-10-13T00:00:00Z
**Status**: Unresolved
**UUID**: RUNOFF-049
**Anchors**: MITgcm/pkg/rnf/rnf_check.F::<module>; MITgcm/pkg/rnf/rnf_init_fixed.F::<module>

### Issue or research question
This issue was split out of RUNOFF-017. Two refusals exist in the code:
- `useRNF` with `useShelfIce` and `SHI_update_kTopC` (`rnf_check.F:216`).
- A target with `kTopC /= 0`, as refuse = 3 (`rnf_init_fixed.F:802-804`, under `#ifdef ALLOW_SHELFICE`).

No runoff experiment compiles pkg/shelfice (0 hits in 17 configurations). So the compiler builds both branches, but nothing runs them.

### Evidence
The scout read `packages.conf` (inferred, so check it). Related: RUNOFF-020 (grids with ice-shelf cavities, top wet level below k = 1). It would supply the build.

### Scientific or engineering impact
Without the refusals, the target "loses its volume" (a code comment). The model loses mass under an ice shelf, and nothing warns the user.

### Proposed action and acceptance
Make one shelfice + rnf build. It may share the build with RUNOFF-020.

Acceptance:
- A target under a shelf stops with the message of refuse = 3.
- `SHI_update_kTopC` stops with its message.
- Each stop fails on a mutant without the guard.
- A control runs.
