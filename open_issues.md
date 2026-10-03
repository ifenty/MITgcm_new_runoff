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

## UNRESOLVED: Runoff package architecture and MITgcm integration design

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-010
**Anchors**: MITgcm/model/src/apply_forcing.F::<module>; MITgcm/pkg/icefront/icefront_tendency_apply.F::<module>; docs/model_contract.md::<module>

### Issue or research question
Decide how sparse runoff enters MITgcm as a package: package name and files; CPP option header and runtime switch; namelist file; where it plugs in (packages_boot/readparms/init_fixed/check, forcing load each step, and the T/S/tracer tendency hooks in apply_forcing.F next to SHELFICE_FORCING_T and ICEFRONT_TENDENCY_APPLY_T/S); how the volume flux relates to exf runoff (fill exf `runoff` vs own EmPmR contribution), real vs virtual freshwater flux; NetCDF dependency and build guards; diagnostics; TAF considerations.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Sources: model/src/apply_forcing.F lines 705-713 and 937-945 call SHELFICE_FORCING_T/S and ICEFRONT_TENDENCY_APPLY_T/S; pkg/icefront/icefront_tendency_apply.F adds per-cell tendencies; current contract (docs/model_contract.md) assumed an exf extension that fills `runoff`.

### Scientific or engineering impact
Every implementation issue depends on this design; a wrong integration point would mean reworking all model code and tests.

### Proposed action and acceptance
Write docs/package_design.md (decisions with source citations, alternatives considered, integration diagram) and update docs/model_contract.md; review by two Richards (MITgcm integration correctness; physics of tendency-based T/S/tracer input vs surface flux). Acceptance: both approve; RUNOFF-004 and dependents re-anchored to the chosen design.

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

## BLOCKED: Runoff package skeleton, registration and no-change regression

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-010 — the package name, files and hooks come from the architecture design
**UUID**: RUNOFF-012
**Anchors**: MITgcm/model/src/packages_boot.F::<module>; MITgcm/model/src/packages_readparms.F::<module>

### Issue or research question
Create the package (options header, common block header, readparms, init_fixed, check, summary output, diagnostics_init) and register it in model/src package hooks and the package dependency files, with a runtime on/off switch; the package does nothing yet.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Base for all model code; must not change any existing result.

### Proposed action and acceptance
Acceptance: all configured no-change experiments pass unchanged with the package compiled in and switched off and with it compiled out; testreport subset clean; Richard reviews standards conformance.

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
Acceptance: analytic single-cell tests (heat and salt budgets to 1e-12 relative), equivalence with exf runoftemp where both apply (cs32 input.seaice oracle), and budget closure in RUNOFF-016.

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

## BLOCKED: Runoff diagnostics and monitor output

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-012 — diagnostics register through the package skeleton
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

## BLOCKED: Runoff on grids with ice-shelf cavities (top wet level below k=1)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-013 — needs the tendency-based contributions
**UUID**: RUNOFF-020
**Anchors**: MITgcm/verification/isomip/input.icefront/data::<module>; MITgcm/pkg/shelfice/shelfice_init_depths.F::<module>

### Issue or research question
Under ice shelves the top wet cell is kSurfC > 1; surface runoff must go to the top wet level, and icefront/shelfice and runoff must not double count. Use isomip (input.icefront, input) as testbed.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern.

### Scientific or engineering impact
Glacier runoff near ice fronts is a core use case; a k=1 assumption would put water into dry cells.

### Proposed action and acceptance
Acceptance: cases with sources at the ice front and in open water; budgets closed; land/dry-target refusal checked.

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

## BLOCKED: Package documentation (MITgcm RST manual, namelist reference, how-to)

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-012 — documents the package created there
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

## BLOCKED: MITgcm coding standards and TAF-friendliness review

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-012 — reviews the package code
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

## UNRESOLVED: Python dense-to-sparse runoff converter

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-002
**Anchors**: docs/model_contract.md#input-one-netcdf-file-per-run-phase-1; docs/verification_matrix.md#scientific-qualification-matrix

### Issue or research question
A tool is needed that reads a dense MITgcm runoff binary (m/s, any grid layout), the grid (`rA`, surface mask) and timing, and writes schema-conformant NetCDF. Flux in m³/s is rA·runoff; each nonzero cell becomes a one-cell source, or cells are grouped with fractions.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

Precision note from RUNOFF-003 review (Richard, 2026-10-02): the oracle pass criterion is 10 matching digits on `cg2d_init_res`, and a float32-level (6e-8) change in applied runoff moves it by about 6e-10. Sparse files for the oracle tests must therefore reproduce the dense m/s values to better than 1e-9 relative: store `runoff_flux` as float64 (flux = dense·rA computed in float64), not float32.

### Scientific or engineering impact
This produces the oracle inputs for every sparse-vs-dense test.

### Proposed action and acceptance
Put the tool under `tools/runoff/`, with pytest tests under `tests/`. Acceptance: the dense→sparse→dense round-trip reproduces cs32 `core_rnof_1_cs32.bin` and the lab_sea dense files exactly (`float32`), fractions sum to 1 within 1e-6, and no source targets a land cell.

Unblocked 2026-09-30: RUNOFF-001 closed; schema 1.0 is approved (docs/runoff_schema.md), and MITgcmutils.runoff.check validates files against it.

## BLOCKED: exf sparse runoff reader, per-tile lists and global fraction check

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-010 — the reader is implemented in the package chosen by the architecture design
**UUID**: RUNOFF-004
**Anchors**: MITgcm/pkg/exf/exf_readparms.F::<module>; MITgcm/pkg/profiles/profiles_init_fixed.F::<module>

### Issue or research question
Implement init: new `data.exf` parameters, a master-thread NetCDF read of the static arrays, the global index → local `(i,j,k,bi,bj)` mapping on every grid (including exch2/LLC and blank tiles), per-tile source lists, a `GLOBAL_SUM` fraction check (1e-6), and refusal of a land cell, an unknown tracer, or sparse + dense both set. Then fill `runoff` = Σ flux·frac/rA.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

Design requirement (2026-09-30): map `target_cell` to owned points with the same arithmetic `pkg/mdsio` uses to place tile rows in a global file (`mdsio_write_field.F:445-480`: `tBx`/`tBy` from `myXGlobalLo`/`myYGlobalLo` or `exch2_txGlobalo`/`exch2_tyGlobalo`, plus the `iGjLoc`/`jGjLoc` fold cases), not a rectangular box test. Under compact `W2_mapIO` (0 or > 0) or when a face is wider than the global array, tile rows are folded or strung into a line (`w2_set_map_tiles.F:189-203`). Test cases: cs32 with `W2_mapIO = -1` (verified by Richard B for the flattened index) and a compact `W2_mapIO` layout.

Precision note from RUNOFF-003 review (Richard, 2026-10-02): the oracle pass criterion is 10 matching digits on `cg2d_init_res`, and a float32-level (6e-8) change in applied runoff moves it by about 6e-10. Sparse files for the oracle tests must therefore reproduce the dense m/s values to better than 1e-9 relative: store `runoff_flux` as float64 (flux = dense·rA computed in float64), not float32.

### Scientific or engineering impact
This is the core feature. Mapping errors silently lose mass.

### Proposed action and acceptance
Acceptance: the lab_sea constant case, sparse = dense, single-process and MPI; the negative tests stop with the expected messages; all no-change experiments pass.

Unblocked 2026-09-30: RUNOFF-001 closed; schema 1.0 is approved (docs/runoff_schema.md), and MITgcmutils.runoff.check validates files against it.

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

## BLOCKED: cs32 sparse-runoff oracle (exch2, runoff temperature)

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
Acceptance: matches `results/output.icedyn.txt` / `output.seaice.txt` to the digit threshold, single-process and `-mpi 4`.

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

## BLOCKED: Runoff salinity and passive-tracer plumbing

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: OWNER-DECISION — approve the salinity/tracer design
**UUID**: RUNOFF-008
**Anchors**: MITgcm/pkg/exf/exf_mapfields.F::<module>; docs/model_contract.md#each-time-step

### Issue or research question
exf has no runoff salinity or runoff tracer fields. Per-source S (default 0) and tracer concentrations, matched to ptracers by name, need a path into the salt flux and the `pkg/ptracers` surface forcing.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

### Scientific or engineering impact
Required for glacier or brackish sources and for tracer studies. Wrong plumbing breaks salt and tracer budgets.

### Proposed action and acceptance
Proposal: fill new 2D exf fields (runoff salinity, runoff tracers) with per-cell flux-weighted means (the combination rule was decided 2026-09-29), and add their contribution where exf and ptracers apply freshwater. Owner to confirm where these hook into the salt and ptracers forcing. Acceptance: a budget check (Σ S·flux) and no-change runs unchanged.
