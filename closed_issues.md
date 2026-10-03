# Closed issues

`loop_gate.py --check-done` moves a completed entry here, with its original UUID,
only when it accepts the closeout. Status is Resolved or False Positive. Preserve the evidence and the scientific bounds of the conclusion.

```markdown
## RESOLVED: <Brief title>

**Date Identified**: <UTC ISO timestamp>
**Date Resolved**: <UTC ISO timestamp>
**Status**: Resolved
**UUID**: <Original ID>

### Issue
<Original contract violation or question>

### Resolution and justification
<Implemented behavior or evidence establishing the finding>

### Verification and remaining bounds
<Regression witness, independent check, final suite receipts and untested conditions>

### Traceability
<Commit SHA or noncommit reason; iteration history/evidence references; related blockers>
```

## 🟢 RESOLVED: Define the sparse-runoff NetCDF schema and its integrity checker

**Date Identified**: 2026-09-29T21:30:00Z
**Date Resolved**: 2026-09-30T12:33:32.470290+00:00
**Status**: Resolved
**UUID**: RUNOFF-001
**Anchors**: docs/runoff_schema.md::<module>; MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/__init__.py::<module>

### Issue or research question
The file layout isn't defined. Needed:
- dimension and variable names, the id string type and the (source, cell) pair layout
- CF time attributes and the timing attributes that `data.exf` can override
- a grid-identity record, so the model refuses a file built for another grid
- (owner, 2026-09-29) room for scientists' metadata the model ignores: several
  names per source (aliases), per-source notes, provenance
- (owner) a defined list of allowed units for each variable
- (owner) a Python integrity checker that validates a runoff file

Decided 2026-09-29: several sources in one cell add volumes, and T, S and tracers are flux-weighted; a missing flux value stops the run; chunking is whatever is most efficient for per-record reads, chosen by measurement.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). Proposed schema 1.0 drafted in `docs/runoff_schema.md` (2026-09-29): an indexed-ragged target table, an alias table, a char-array `source_id` readable by Fortran-77 NetCDF, CF/ACDD metadata, allowed units and calendars, and checker rules S/G/I/A/T/M/D/U/P/X/R. No code exists yet.

### Scientific or engineering impact
Every later issue (converter, reader, timing) depends on this layout. It also sets I/O cost at the 2 km scale. The checker is the first line of defense against silently dropped fractions and mismatched grids.

### Proposed action and acceptance
- Implement `MITgcmutils.runoff` in the fork: schema constants, `check` (library and CLI) and `example.write_example()`.
- Add pytest tests in `tests/runoff/`: the tiny example passes, and each error rule fires on a targeted corruption.
- Insert the example `ncdump -h` into the schema doc, and link the schema from `docs/model_contract.md`.

Acceptance:
- tests pass
- independent review of schema and checker (correctness and MITgcm fit)
- the owner approves schema 1.0

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-09-30T12:33:32.470290+00:00 for iteration 2026-09-29T21:42:58.974959+00:00. Sparse-runoff NetCDF schema 1.0 (docs/runoff_schema.md) defined and owner-approved 2026-09-30: source, alias and target tables, (time, source) series for flux, temperature, salinity and ptracers, CF/ACDD metadata space, allowed units and calendars, and 46 integrity rules. MITgcmutils.runoff (fork new_runoff) implements the checker (library and CLI) and an example writer; 196 tests pass. Two independent reviewers approved after 5 correction rounds, which fixed Fortran-reader fit (no packing, ASCII NC_CHAR attributes, numeric fills, deflate-only filters, exf-consistent timing and yearly-file continuity). The scientific suite passes unchanged.

## 🟢 RESOLVED: Target-table builder: snap sources to wet cells and spread runoff by kernel

**Date Identified**: 2026-09-30T13:30:00Z
**Date Resolved**: 2026-10-02T13:44:13.905808+00:00
**Status**: Resolved
**UUID**: RUNOFF-009
**Anchors**: docs/runoff_schema.md::<module>; MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/__init__.py::<module>

### Issue or research question
Users need to build the target table from source locations without a dense runoffFile. The owner's specification (2026-09-30):
- **Inputs:** a source table (CSV with source_id, lon, lat and optional metadata and per-source options; or an existing schema-1.0 NetCDF source table) and MITgcm grid output (hFacC, XC, YC, XG, YG, RAC).
- **Options:** an emission type {pointwise, spread}. If spread, a spread_type {gaussian, exponential, linear} and a spread_scale X, the distance at which the kernel falls to 1/e of its peak.
- **Snapping:** each source goes to the nearest wet surface cell (hFacC level 1 > 0) by great-circle distance, with a maximum snap distance that stops with an error naming the source.
- **Pointwise:** share 1 at the snapped cell.
- **Spread:**
  - Kernels: exponential exp(-r/X); gaussian exp(-r^2/X^2); linear max(0, 1 - r/R_cut) with R_cut = X/(1 - 1/e).
  - r is the shortest-path distance through connected wet cells (owner decision), starting at the snapped cell. Edges are great-circle distances between the centers of neighboring cells; neighbors share a cell edge, found from the corner coordinates XG/YG, so it works on every grid, including across cubed-sphere and LLC faces.
  - Cutoff: 3X for exponential and gaussian by default, settable per source (owner decision); linear stops at R_cut.
  - Shares are proportional to W(r)·rA, per unit area (owner decision), normalized to sum to 1. No wet cell within reach is an error naming the source.
  - Per-source overrides of emission, type, scale, cutoff and max snap distance.
- **Output:** a schema-1.0 NetCDF holding the source and target tables and the grid attributes; time series are appended later. It must pass the checker (time series excepted).

### Evidence
Owner request and design answers 2026-09-30 in the Arch session. Grid output available: MITgcm/verification/global_ocean.cs32x15/output_esx_input.icedyn (hFacC, XC, YC, XG, YG, RAC).

### Scientific or engineering impact
It is the main way to make sparse runoff from river and glacier discharge datasets, and it determines where the freshwater enters the ocean. The per-unit-area weighting and the connected-ocean distance prevent grid-size artefacts and leakage across land.

### Proposed action and acceptance
- Implement MITgcmutils.runoff.targets (library plus CLI) with tests.
- Analytic oracles on synthetic lat-lon grids: kernel values at r = 0, X and R_cut; the 1/e property; sum = 1; area weighting.
- Connectivity oracle: a peninsula or fjord where the path distance exceeds the great-circle distance and a separate basin gets nothing.
- The cs32 real grid: neighbors across faces, and every output passes the checker, including R01 and R02.
- Both reviewers approve.

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-02T13:44:13.905808+00:00 for iteration 2026-09-30T14:59:32.623569+00:00. Target-table builder MITgcmutils.runoff.targets (library and CLI) delivered per the owner specification: snap each source to the nearest wet surface cell within a maximum snap distance; pointwise, or spread with gaussian/exponential/linear kernels (1/e scale X, default cutoff 3X, per-source overrides) over the connected wet-cell graph with r = 0 at the snapped cell; shares proportional to W(r)*rA, normalized to 1. Neighbours are edge-sharing cells: the grid kind is declared (latlon or exch2, default exch2 when data.exch2 is present) and each kind returns the exact graph or an explicit refusal. The checker gained a tables-only mode (S10). 273 tests pass; both reviewers approved after 5 correction rounds and two diagnosis checkpoints; the scientific suite passes unchanged.

## 🟢 RESOLVED: ESX runtime hook makes every retained-agent Bash call require approval

**Date Identified**: 2026-09-29T22:20:00Z
**Date Resolved**: 2026-10-02T16:06:17.589207+00:00
**Status**: Resolved
**UUID**: ESX-002
**Anchors**: tools/esx/runtime_tool_hook.py::handle; tools/esx/agent_runtime.py::<module>

### Issue or research question
`runtime_tool_hook.handle` returns `updatedInput` that rewrites every Bash command to
`/usr/bin/python3 tools/esx/bounded_command.py --timeout … -- /bin/bash -c '<cmd>'`.
Its docstring says "normal tool permission checks still run". But Claude Code checks
permissions on the *rewritten* command, so no project allow rule (`Bash(python3 *)`,
`Bash(pwd)`, …) can match. Every Bash call from a retained role session (Bob, Richard,
Scout, …) in the default permission mode is denied with "This command requires approval".
Roles can still Read, Edit and Write, but can't run tests, builds or verification.
Richard's independently executed check, which acceptance requires, is impossible.

A second defect hides this: `agent_runtime.py probe` runs tools-disabled turns and passes,
and nothing in the kit validates role tool permissions live (the probe output says
"role tool permissions need separate live validation").

### Evidence
- RUNOFF-001 Bob session `a7e61b17-6617-47f7-b90c-b7a2124c40c7`, turn
  `3cc0d65cc31349ecad3b173640b664ac`: `pwd`,
  `/home/ifenty/miniforge3/envs/ecco/bin/python --version`, `python3 tools/esx/doc_contract.py …`
  and `ls -la …` were all denied (`permission_denied`, `decision_reason_type: other`),
  although `Bash(python3 *)` and `Bash(ls *)` are allowlisted and `pwd`/`--version` were added.
- Control: the same CLI binary (2.1.285) with the same project settings but without the
  `--settings` PreToolUse hook ran `ls -la`, `python3 --version` and `wc -l` successfully
  (`devel-loop/loop_state/permprobe.jsonl`, 2026-09-29).

### Scientific or engineering impact
Blocks every scientific_change workflow: implementation can't run its tests, and the
independent review's executed check can't run. Local workaround (2026-09-29): an allow rule
for the wrapper prefix in `.claude/settings.local.json`,
`Bash(/usr/bin/python3 /home/ifenty/Projects/MITgcm_new_runoff/tools/esx/bounded_command.py *)`.
That rule allows any command inside the wrapper, so role sessions effectively bypass the allowlist.

### Proposed action and acceptance
Fix in ESX-Team upstream (github.com/ifenty/ESX-Team):
- evaluate the original command against the project allow/deny rules inside the hook,
  and return `permissionDecision` explicitly;
- add a live tool-permission witness to `agent_runtime.py probe`: one allowed Bash
  command must run and one disallowed command must be denied.

Acceptance: with the wrapper rule removed, a role session runs an allowlisted command,
is denied a non-allowlisted one, and the probe fails on the current hook.

### Resolution evidence (2026-09-29)
Fixed upstream in ESX-Team 1.5.1 (8c7ea7d) and 1.5.2 (c92ebe4), both deployed here with no conflicts. The hook now judges the original command with `permission_match` and explicitly allows only allowlisted commands. The live probe runs an allowed and a denied Bash witness, and passes here (`devel-loop/loop_state/probe-152.json`). A matcher witness on this project's rules allows ecco pytest, quoted multi-line `python3 -c` and `cd && python3`. Heredocs, file redirects and unlisted commands get no decision; deny wins through `&&` and `|`. Wrapper allow rule and `Bash(mkdir *)` removed. Awaiting formal closeout.

Acceptance witness on ESX-Team 1.6.0 (2026-10-02): with the workaround rules removed, a retained Bob session (b8a28b11, event e54e8aa9) ran allowlisted commands (pwd, the pinned-python pytest, python3 -c, `ls | head`), was refused the unlisted `mkdir` with nothing created, and the turn recorded the denial without a dispatcher crash. The live probe passes (`devel-loop/loop_state/probe-160.json`).

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-02T16:06:17.589207+00:00 for iteration 2026-10-02T16:03:12.398486+00:00. ESX-002 closed: the ESX runtime hook that rewrote every role Bash command (so no allow rule matched and all role shell calls were denied) is fixed upstream in ESX-Team 1.5.1/1.5.2 and deployed through 1.6.0. Live acceptance on 1.6.0 with the workaround rules removed: a retained Bob session ran allowlisted commands and was refused an unlisted mkdir, with the denial recorded and no dispatcher crash; the live probe passes.

## 🟢 RESOLVED: ESX dispatch adapter crashes on Claude Code permission_denied events

**Date Identified**: 2026-09-29T22:05:00Z
**Date Resolved**: 2026-10-02T16:09:14.557182+00:00
**Status**: Resolved
**UUID**: ESX-001
**Anchors**: tools/esx/agent_runtime.py::_read_tool_events

### Issue or research question
`_read_tool_events` did `event.get("message", {}).get("content", [])`. Claude Code stream-json
`{"type":"system","subtype":"permission_denied",…}` events carry `message` as a string, so
the watchdog raised `AttributeError: 'str' object has no attribute 'get'`. The dispatcher
exited mid-turn and the child session was left without a supervisor. That turn's evidence
was saved only as a failure.

### Evidence
RUNOFF-001 Bob start, event `8154aebc7c6b4c0fbf05966e863adc0c` (2026-09-29): traceback in the
dispatch output, and the offending event at line 8 of that turn's `stdout.jsonl`. Local fix:
guard on `isinstance(message, dict)`. Replaying the same `stdout.jsonl` through the patched
function parses cleanly (`devel-loop/loop_state/compatibility-RUNOFF-001.log`,
sha256 77edaf31…1714).

### Scientific or engineering impact
Any denied tool call (a common event, see ESX-002) kills the dispatch and forces a
runtime-transition assessment to resume.

### Proposed action and acceptance
Upstream the guard to ESX-Team, with a unit test that feeds a `permission_denied` event
(string `message`) and a normal assistant event through `_read_tool_events`.
Audit other `event.get(...).get(...)` chains in the adapter for the same assumption.
Acceptance: the test passes upstream, and the local copy matches upstream after the next kit update.

### Resolution evidence (2026-09-29)
Fixed upstream in ESX-Team 1.5.1 (tolerant stream parser, recorded failed turn on dispatcher error, `permission_denials` in turn records). The local guard was reverted to 1.5.0 bytes before the upgrade. `agent_runtime.py recover` closed orphaned turn 8154aebc in Bob session a7e61b17. Awaiting formal closeout.

Acceptance witness on ESX-Team 1.6.0 (2026-10-02): the 1.5.0 crash stream (turn 8154aebc, a string `message` on a permission_denied event) replays through the deployed `_read_tool_events` without error, and a live Bob turn (b8a28b11, e54e8aa9) with one denied command completed with the denial in `permission_denials` (verification record 5c001a7b…).

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-02T16:09:14.557182+00:00 for iteration 2026-10-02T16:08:16.931383+00:00. ESX-001 closed: the dispatch adapter crash on Claude Code permission_denied events (a string message field) is fixed upstream since ESX-Team 1.5.1 and deployed through 1.6.0. The 1.5.0 crash stream replays through the deployed parser, and a live turn with a denied command completed with the denial recorded.

## 🟢 RESOLVED: lab_sea dense-path runoff reference runs

**Date Identified**: 2026-09-29T21:30:00Z
**Date Resolved**: 2026-10-02T21:39:06.713663+00:00
**Status**: Resolved
**UUID**: RUNOFF-003
**Anchors**: MITgcm/verification/lab_sea/input/data.exf::<module>; tests/mitgcm_oracle.sh::<module>

### Issue or research question
No lat-lon verification experiment uses exf runoff. Build `lab_sea/input.<X>` cases with generated dense runoff: constant, daily, calendar-monthly, monthly-repeating, and yearly `_YYYY` files. Sources come from coastal cells of `bathy.labsea1979`, and at least one spans a tile boundary and the MPI process boundary.

### Evidence
`lab_sea`: 20×16 lat-lon at 2°, 4 tiles of 10×8, `SIZE.h_mpi` 2 processes × 2 tiles; `input/data.exf` has `runoffFile = ' '`; the forward build uses the default `EXF_OPTIONS.h` (`ALLOW_RUNOFF` on, `ALLOW_RUNOFTEMP` off).

### Scientific or engineering impact
These are the lat-lon oracles for sparse = dense on all timing modes. Without them, only exch2 cs32 is covered.

### Proposed action and acceptance
Keep a generator script (`gendata.py`) in each input directory. Runs span ≥ 1 month, and cross Dec → Jan where needed. Save `results/output.<X>.txt`. Acceptance: each case runs to `Execution ended Normally` single-process and with `-mpi 2`, and the MPI output matches the single-process output to the digit threshold. Commit to the fork `new_runoff`.

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-02T21:39:06.713663+00:00 for iteration 2026-10-02T16:10:58.211518+00:00. Six lab_sea verification cases (input.rnof_const, rnof_daily, rnof_month, rnof_month1, rnof_clim, rnof_yearly) now exercise the existing dense exf runoffFile path on a lat-lon grid in every timing mode, with committed references, a generator, and a direct timing check that matches the applied runoff to the input records to 1e-12, including interpolated and year-wrap samples. Each case passes single-process and -mpi 2 to 16 digits; sources straddle the tile and MPI process boundaries. No Fortran changed; the scientific suite passes.

## RESOLVED: Runoff package architecture and MITgcm integration design

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Resolved
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

### Resolution (2026-10-03)
docs/package_design.md records the architecture of the new package `pkg/rnf`: ten decisions with alternatives, reasons and MITgcm source citations.
- **Volume:** goes through the exf `runoff` array, from one guarded call in `exf_getffields.F`.
- **T, S and tracers:** enter as tendency terms in `APPLY_FORCING_T/S` and `PTRACERS_APPLY_FORCING`. The reference-value algebra is given for every freshwater formulation, with the time-level rule.
- **Refusals:**
  - a target cell out of range;
  - a land, `maskInC = 0` or under-shelf target;
  - `SHI_update_kTopC`;
  - `exf_outscal_sflux ≠ 1`;
  - a dense runoff file or runoff constant set.
- **Reading and records:** `HAVE_NETCDF` guards, mdsio placement arithmetic, exf record routines reused, no pickup, fixed-size TAF arrays, `data.rnf`.

Two independent Richard reviews (A: MITgcm integration; B: physics and algebra) rejected round 0 with nine must-fix items. Both approved round 1 with no must-fix items. Their witnesses:
- A: placement on 109 layouts and 2.7 M cells, with the off-grid defect reproduced and then fixed;
- B: exact-arithmetic budget for 108 formulation cases, a negative control, and a cold-start/restart time-level witness.

Design only; no model code changed. Follow-ups: RUNOFF-030 (exf range check) and RUNOFF-031 (KPP visibility).

## RESOLVED: Runoff package skeleton, registration and no-change regression

**Date Identified**: 2026-10-02T22:30:00Z
**Status**: Resolved
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

Unblocked 2026-10-03: RUNOFF-010 closed. The package identity, file set and registration table are decision 1 of docs/package_design.md; the refusals that guard the static read belong in `RNF_READPARMS` or `RNF_INIT_FIXED` (`PACKAGES_INIT_FIXED` runs before `PACKAGES_CHECK`).

### Resolution (2026-10-03)
`MITgcm/pkg/rnf` exists as a skeleton:
- **Files:** `RNF_OPTIONS.h`, `RNF_SIZE.h` and `RNF.h`; `rnf_readparms`, `rnf_check` and `rnf_summary`; init stubs; forcing and tendency stubs with final argument lists; a README.
- **Registration:** PARAMS.h, the packages_* routines, guarded hooks in load_fields_driver.F, exf_getffields.F, apply_forcing.F and ptracers_apply_forcing.F, and pkg_depend `rnf +exf`.
- **Namelist:** `data.rnf` / `RNF_PARM01`.
- **Refusals:** every refusal that needs no runoff file, plus a "reader not implemented" stop for RUNOFF-004 to remove.

rnf is compiled into lab_sea and cs32.

**No-change evidence:**
- Compiled in and switched off: lab_sea (±MPI), cs32 input.seaice (±MPI), input.icedyn and input.in_p, and dense lab_sea cases all PASS. A same-platform A/B on cs32 input.in_p is byte-identical on all 48 output files.
- Compiled out: isomip, 1D_ocean_ice_column, seaice_obcs, offline_exf_seaice, seaice_itd, global_oce_latlon input.yearly, global_ocean.90x40x15 and tutorial_advection_in_gyre (ptracers) all PASS.
- A 2-thread OpenMP run passes.
- tests/rnf/refusal_check.py: 7 of 7, single and 2 processes. It judges each process on its own files and was mutation-tested by both reviewers.

**Reviews:** Richard A approved; Richard B rejected round 0 on one record (ptracers compiled-out coverage), and both approved round 1. NetCDF is available in the Docker build (HAVE_NETCDF, -lnetcdff).

## RESOLVED: Python dense-to-sparse runoff converter

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Resolved
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
Put the tool in the `MITgcmutils.runoff` package, as `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/convert.py` (not under `tools/runoff/`, as first planned), with pytest tests in `tests/runoff/test_convert.py`. Acceptance: the dense→sparse→dense round-trip reproduces cs32 `core_rnof_1_cs32.bin` and the lab_sea dense files exactly (`float32`), fractions sum to 1 within 1e-6, and no source targets a land cell.

Unblocked 2026-09-30: RUNOFF-001 closed; schema 1.0 is approved (docs/runoff_schema.md), and MITgcmutils.runoff.check validates files against it.

### Resolution (2026-10-03)
`MITgcmutils.runoff.convert` (`dense_to_sparse`, `sparse_to_dense` and a CLI) converts dense runoff and runoff-temperature binaries into schema-1.0 NetCDF:
- any precision and any global 2D layout;
- every exf timing mode: 0, > 0 with a start date or start time, a repeat cycle, -12, -1, and yearly files;
- timing conventions cited to pkg/exf and pkg/cal source (schema §14).

Sparse files exist for all six lab_sea dense oracle cases and for the cs32 runoff and temperature. They regenerate byte-identically with `gen_sparse.py`. Every file passes the full checker with grid checks, and each round-trips exactly at float32. cs32 float64 matches to one ulp, which review B proved is the best any float64 flux can do.

**Tests:** tests/runoff gives 325 passed. They include a test that each lab_sea file reproduces the field exf applies at every forcing time, to 1e-12.

**Reviews:**
- A independently transliterated exf record selection: zero mismatches over about 70,000 model times in every mode.
- B confirmed rA is bit-identical to the model's, and that 30 of 30 mutants are caught after round 1.
