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

## BLOCKED: Temperature and salinity runoff contributions via tendency terms

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-004 — needs the sparse reader and per-tile lists
**UUID**: RUNOFF-013
**Anchors**: MITgcm/pkg/icefront/icefront_tendency_apply.F::<module>; MITgcm/pkg/shelfice/shelfice_forcing.F::<module>

### Issue or research question
Apply runoff heat and salt to the target cells as tendency contributions (icefront/shelfice pattern): flux-weighted T and S per cell, missing T meaning ambient water temperature, missing S meaning 0, consistent with the chosen freshwater-flux formulation (real vs virtual).

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Contract: docs/model_contract.md (flux-weighted mixing, conservation invariants).

### Scientific or engineering impact
Core physics deliverable; wrong signs or double counting break heat/salt conservation.

### Proposed action and acceptance
Design (RUNOFF-010, docs/package_design.md): decision 3 gives the term `[(mT) − m_T·T_ref]·mass2rUnit/(drF·hFacC)` (and the S analogue) in `APPLY_FORCING_T/S` after the ICEFRONT calls, with `T_ref`/`S_ref` from the freshwater formulation table, the same-step `PmEpR` time level, and the `rhoConstFresh/rhoConst` mass convention. Acceptance: analytic single-cell tests for every row of the decision 3 tables (heat and salt budgets to 1e-12 relative); cell-by-cell agreement with the exf `runoftemp` term in ice-free cells (dense EXFroff/EXFroft/THETA vs package diagnostic); budget closure in RUNOFF-016.

## BLOCKED: Real versus virtual freshwater flux and free-surface options

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-004 — needs the sparse volume flux in the model
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

## BLOCKED: Volume, heat, salt and tracer budget closure checks

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-013 — needs T/S contributions applied
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

## BLOCKED: Refusal and negative tests for invalid runoff input

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-004 — needs the model reader
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

Carry forward from RUNOFF-004 (review B, correction round 1, 2026-10-04): add the **cross-rank global-count oracle**. `tests/rnf/refusal_check.py::judge` asserts that a tile-local refusal message appears in *some* rank's `STDERR` and that each rank emits one `STOP` line, but it never asserts the **value** of the `GLOBAL_SUM_INT`-ed count, and `sparse_info` always selects a land cell in the western half, i.e. rank 0 — so the zero-local/non-zero-global case has no case. Review B wrote and ran the two that distinguish a correct reduction from a lucky one, on 2 MPI ranks: `land_rank1_only`, where rank 0 owns no refused target and prints no detail line yet still prints `1 refused target(s) on all processes` and stops, and `land_both_ranks`, where each rank sees 1 locally yet both print `2`. Both passed, with no hang. Fold them into `refusal_check.py` and assert the summed value. Its receipt is `devel-loop/loop_state/scratch/ab74b9af824d5b71c/richard_refusal_mpi2.json`; the same run also covered four refusal paths that had no case (`RNF_period` set in `data.rnf`, schema major version 2.0, `constant` sampling with two records, and `runoff_flux` with its dimensions transposed). Low priority: the mechanism is proven by execution and unchanged since. Note the scratch receipt is git-ignored and local to this machine, so re-derive the cases from the description rather than relying on the file surviving.

## BLOCKED: global_ocean.90x40x15 and global_oce_latlon sparse runoff testbeds

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-004 — needs the model reader
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

## BLOCKED: Regional open-boundary testbeds (seaice_obcs, obcs_ctrl)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-004 — needs the model reader
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

## BLOCKED: Runoff on grids with ice-shelf cavities (top wet level below k=1)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-013 — needs the tendency-based contributions
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

## BLOCKED: Pickup/restart reproducibility with sparse runoff

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-005 — needs the time handling
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

## BLOCKED: Thread, MPI and tile-layout independence (do_tst_2+2)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-013 — needs the full model path
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

## BLOCKED: Runoff with sea ice (runoff into ice-covered cells)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-013 — needs the tendency-based contributions
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

## BLOCKED: Subsurface discharge at depth (target_level > 1, schema 1.1)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-013 — builds on the tendency-based contributions
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

## BLOCKED: Time modes for T, S and tracer series (all five modes for every series)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-005 — builds on the flux time handling
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

## UNRESOLVED: exf range check stops point-source runoff above 1e-6 m/s

**Date Identified**: 2026-10-03T04:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-030
**Anchors**: MITgcm/pkg/exf/exf_check_range.F::<module>; docs/package_design.md::<module>

### Issue or research question
`EXF_CHECK_RANGE` stops the run if `runoff` exceeds 1e-6 m/s on a wet cell, and `useExfCheckRange` defaults to true. A 1000 m³/s river into one 2 km cell is 2.5e-4 m/s. Decide between documenting `useExfCheckRange=.FALSE.`, skipping the runoff upper bound when `useRNF` is true (one more guarded exf line), or a package-specific bound.

### Evidence
RUNOFF-010 design, decision 2: `exf_check_range.F:175-191`, `211-216`; default `exf_readparms.F:307`.

### Scientific or engineering impact
Without a decision every realistic point-source configuration on a fine grid stops at the first step, or users disable all exf range checks.

### Proposed action and acceptance
Recommend skipping only the runoff upper bound when `useRNF` (other exf checks stay), with a package-side sanity bound reported in the summary. Acceptance: a lab_sea case with a point source above 1e-6 m/s runs with default `useExfCheckRange`; the dense path behaviour is unchanged.

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

## UNRESOLVED: pkg/rnf sparse runoff reader, per-tile lists and global fraction check

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-004
**Anchors**: MITgcm/pkg/exf/exf_getffields.F::<module>; MITgcm/pkg/profiles/profiles_init_fixed.F::<module>

### Issue or research question
Implement init in the new package `pkg/rnf` (decisions 1, 2, 6, 10 of docs/package_design.md): `data.rnf` parameters (`RNF_PARM01`), the `HAVE_NETCDF` guard, a master-thread NetCDF read of the static arrays, the global index → local `(i,j,k,bi,bj)` mapping on every grid (including exch2/LLC and blank tiles), per-tile source lists, a `GLOBAL_SUM` fraction check (1e-6), and refusal of a land cell or sparse + dense both set. (Refusing an unknown tracer moved to RUNOFF-013 on 2026-10-04, by Arch's scope resolution after both reviewers ruled the deferral legitimate: the reader does not read tracer variables, so there is no name to match against `PTRACERS_names`, and RUNOFF-013's acceptance already names the refusal. A tracer, temperature or salinity variable present in the file is warned about per variable and not applied, `rnf_init_fixed.F:382-408`, so no value is silently wrong.) Then assign exf `runoff` = Σ flux·frac/rA each step from the one guarded `RNF_EXF_RUNOFF` call in `exf_getffields.F`, and refuse a non-blank `runofffile`/`runoftempfile`, non-zero `runoffconst`, missing `useEXF`/`ALLOW_RUNOFF`, and targets under an ice shelf (`kTopC ≠ 0`).

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

Design requirement (2026-09-30): map `target_cell` to owned points with the same arithmetic `pkg/mdsio` uses to place tile rows in a global file (`mdsio_write_field.F:445-480`: `tBx`/`tBy` from `myXGlobalLo`/`myYGlobalLo` or `exch2_txGlobalo`/`exch2_tyGlobalo`, plus the `iGjLoc`/`jGjLoc` fold cases), not a rectangular box test. Under compact `W2_mapIO` (0 or > 0) or when a face is wider than the global array, tile rows are folded or strung into a line (`w2_set_map_tiles.F:189-203`). Test cases: cs32 with `W2_mapIO = -1` (verified by Richard B for the flattened index) and a compact `W2_mapIO` layout.

Precision note from RUNOFF-003 review (Richard, 2026-10-02): the oracle pass criterion is 10 matching digits on `cg2d_init_res`, and a float32-level (6e-8) change in applied runoff moves it by about 6e-10. Sparse files for the oracle tests must therefore reproduce the dense m/s values to better than 1e-9 relative: store `runoff_flux` as float64 (flux = dense·rA computed in float64), not float32.

Design (RUNOFF-010, docs/package_design.md): mapping uses the `mdsio_read_field.F:399-430` placement arithmetic; the package skeleton (RUNOFF-012) is the first step of this work.

### Scientific or engineering impact
This is the core feature. Mapping errors silently lose mass.

### Proposed action and acceptance
Acceptance: the lab_sea constant case, sparse = dense, single-process and MPI; the negative tests stop with the expected messages; all no-change experiments pass.

Unblocked 2026-09-30: RUNOFF-001 closed; schema 1.0 is approved (docs/runoff_schema.md), and MITgcmutils.runoff.check validates files against it.

Unblocked 2026-10-03: RUNOFF-010 closed (docs/package_design.md). Do RUNOFF-012 (package skeleton) first. Carry forward from review A: `RNF_CHECK` must test `useShelfIce .AND. SHI_update_kTopC` under `ALLOW_SHELFICE`, because `SHELFICE_READPARMS` returns before setting the default when shelfice is unused (`shelfice_readparms.F:79-87`, `103-107`). Carry forward from review B: the contract bullet "a source without a temperature contributes at the surface water temperature" needs the qualifier "except in a build without `ALLOW_ATM_TEMP` that sets `temp_EvPrRn`, where it enters at `temp_EvPrRn`". Also label the time-level row "start at iteration 0" rather than "cold start". Review A also noted that the time-level table assumes `exactConserv`, which always holds with a nonlinear free surface (`config_check.F:725`).

Carry forward from the 2026-10-04 machine move: the two sparse oracle input directories this issue's acceptance names, `lab_sea/input.rnof_sp_const` and `global_ocean.cs32x15/input.rnof_sp_icedyn`, do not exist and never did — RUNOFF-002 put its sparse files inside the dense case directories (`lab_sea/input.rnof_*/runoff_sparse*.nc`) and in `cs32x15/input.rnof_sparse/`. They were listed in `project.json` `configuration_paths` ahead of being built, which blocked the ESX gate ("configured input is missing") on work that creating them is part of. They have been removed from `configuration_paths` (cs32's entry replaced by the `input.rnof_sparse` directory that does exist). Create both directories here, then add them back to `configuration_paths`; the `focused` and `scientific` suite commands that name them were left in place as this issue's acceptance.

Carry forward from RUNOFF-012:
- Remove the skeleton "reader not implemented" stop at the end of `RNF_CHECK`.
- A refusal detected on one tile only (land, maskInC, under-shelf) must reach every rank before the stop. Count it, `GLOBAL_SUM` the count, then stop on all ranks; otherwise `ALL_PROC_DIE` hangs the other ranks (review B).
- `RNF_SIZE.h` holds five placeholder bounds from decision 9, to be set here.

## BLOCKED: Sparse runoff time handling: interpolation, hold-exact, repeat cycles, yearly files

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-004 — needs the reader and per-tile lists
**UUID**: RUNOFF-005
**Anchors**: MITgcm/pkg/exf/exf_getffieldrec.F::<module>; MITgcm/pkg/exf/exf_getyearlyfieldname.F::<module>

### Issue or research question
Read only the bracketing records each step, applying CF time with `data.exf` overrides. Support exf-style linear interpolation and hold-exact, calendar months, the climatology wrap, and `_YYYY` file switching.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

From RUNOFF-001 review round 1 (Richard B, 2026-09-30): schema 1.0 puts yearly-sampled `time` at the bound midpoint. exf has no yearly-midpoint mode (exf_set_fld.F branches only on fldPeriod -12, -1 or > 0), and Gregorian year midpoints are 365.5/365.5/365 days apart, so the reader must map yearly records itself. A fixed fldPeriod works only on noleap and 360_day calendars.

### Scientific or engineering impact
Time off-by-one errors at month or year boundaries are a main scientific risk.

### Proposed action and acceptance
Acceptance: the lab_sea daily, monthly, monthly-repeating and yearly cases match their dense references (single-process and MPI), and the hold-exact direct check passes.

Carry forward from RUNOFF-002 (converter):
- **Gregorian fixed-period climatology:** the reader must anchor the repeat cycle at the file's real dates (package design decision 7), not at a nominal year. Read the nominal way, the lab_sea clim file departs from exf from 1980-02-29 by up to 2.2% of peak, and the 50-day oracle cannot tell the difference. Add a longer test.
- **Constant files** carry a reference date of 0001-01-01 Gregorian, before the pkg/cal reference date of 1582-10-15. The reader must not pass it to cal.
- **cs32 (no pkg/cal):** times are seconds of model time on a 360_day file calendar; do not demand a calendar match without cal.
- **Yearly files:** records sit at the start of their bounds (1 January 00:00); define hold-exact behaviour.
- **No multi-cell source in the timed oracles:** only the lab_sea const case has one, because gendata.py gives each cell its own phase. Add a group-coherent timed case.
- **Not expressible in schema 1.0:** a repeat cycle that is not one calendar year, and yearly files that are not a whole number of periods. A schema 1.1 attribute would fix this if ever needed.

## BLOCKED: cs32 sparse-runoff oracle (exch2 volume path; runoff temperature cell-by-cell)

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-004 — needs the reader; also needs the RUNOFF-002 converter
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

## BLOCKED: Passive-tracer runoff contributions (ptracers tendency term)

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-013 — the tracer term reuses the T/S tendency routine and its tests
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


## UNRESOLVED: The configured digit oracle cannot detect a one-cell target move; promote a cell-exact applied-field check

**Date Identified**: 2026-10-04T17:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-033
**Anchors**: MITgcm/pkg/rnf/rnf_fields_load.F::<module>; tests/rnf/placement_probe.py::main

### Issue or research question
Every configured sparse = dense oracle judges `output.txt` monitor digits, and that criterion cannot see a misplaced target. Measured on the RUNOFF-004 candidate (`b8251cd1c`, cs32, 4 processes) by review A: moving one target entry one cell in x, across the facet 2/3 boundary of the 192 x 32 layout, with the two cells' `rA` **bitwise equal** so `RNF_areaTol` is blind and the fractions still summing to 1, is accepted silently with no `RNF` message, the run ends normally, and `compare_results.sh` reports **10 matching digits against the 10 required — PASS with zero margin**. `cg2d_init_res` moves 1.062e-10 absolute, 4.103e-11 relative. A cell-exact oracle flags the same run immediately (`extra cells = 1`, `missing cells = 1`, relative error 1.0), with global mass still exactly conserved, which is why the digit check cannot see it: the water is not lost, only moved.

Should the project adopt a cell-exact applied-field check as a configured test, so that placement is guarded by something with real margin rather than by a threshold it passes exactly?

### Evidence
Review A built the oracle and ran it: an added `EXFroff` snapshot stream with `diag_mnc=.FALSE.`, `writeBinaryPrec=64` and `useSingleCpuIO`, dumping the field the model actually applies, compared cell by cell at float64 against an independent reconstruction of `Σ_s flux_s·frac_{s,c}/rA(c)` computed from the NetCDF file and the model's own `RAC.data`. On the unperturbed candidate it is **bitwise identical** over all 6144 cs32 cells and all 10 dumped steps (1189 non-zero, 0 extra, 0 missing, `sum(applied·rA)` equal to `Σ flux` exactly), and likewise on lab_sea on 2 processes where `baffin`'s 0.2667/0.4/0.3333 split straddles the process boundary. Review A also censused the exposure: **47 of the 1189** cs32 targets have a global-index neighbour that is wet, not already a target, and within `RNF_areaTol` in area, so the move above is not a contrived single case.

### Scientific or engineering impact
This is the issue's own stated failure mode — "mapping errors silently lose mass" — except that mass is conserved and the water simply arrives in the wrong cell, which is worse for detection. At 2 km production scale with 10^5-10^6 sources the digit oracle's blindness scales with the number of sources, while the cell-exact check does not. Without it, a future refactor of the placement arithmetic has no configured test with margin.

### Proposed action and acceptance
Promote review A's oracle to `tests/rnf/` as a configured command, reusing the `EXFroff` diagnostic path so no model code is needed, and add it to the `scientific` suite beside `placement_probe.py`. Acceptance: the check is bitwise exact on the unperturbed candidate for lab_sea (1 and 2 processes) and cs32 (1 and 4 processes), and fails with a non-zero extra/missing count on a deliberately perturbed input.

Second, add an init-time coordinate check. Review A's correction-round-1 refinement (2026-10-04), which supersedes an earlier framing of this issue that asked whether `RNF_areaTol` should be tightened or `target_cell_area` required to match `rA` bitwise: **neither can work.** The two cells of the move above have `rA` that is *bitwise equal*, so no area tolerance however tight separates them. But the schema already carries `target_lon`/`target_lat`, and for entry 1035 those equal cell 5247's `XC`/`YC` exactly (133.8655, 28.5373) while cell 5248 lies at (−38.1226, 39.2996) — **172° of longitude away**. Comparing `target_lon`/`target_lat` against the owning cell's `XC`/`YC` at init would refuse that move outright, cheaply, for every target, and is a far stronger guard than any area tolerance. Acceptance for this part: the move of entry 1035 is refused with an `RNF` message naming the source and cell, the unperturbed committed files pass, and the tolerance is justified against the grid's own cell spacing rather than chosen.

Carry forward (Arch, 2026-10-04): `docs/verification_matrix.md` still says "the two "not seen" rows of the historical table below" after correction round 1 removed those two rows; the table now carries one embedded "not seen" value and no such rows. Review A raised it as non-blocking. I wrote the one-line fix, found it staled Bob's sealed documentation report — which both reviewers had already confirmed — and reverted it rather than spend a second correction round re-confirming a cross-reference wording. Fix it in the next issue that edits this file, inside that issue's own documentation plan. The ordering lesson is the closeout doctor's: finalize every signed field before taking the final verification receipt.
