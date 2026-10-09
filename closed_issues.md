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

## 🟢 RESOLVED: pkg/rnf sparse runoff reader, per-tile lists and global fraction check

**Date Identified**: 2026-09-29T21:30:00Z
**Date Resolved**: 2026-10-04T22:05:11.774592+00:00
**Status**: Resolved
**UUID**: RUNOFF-004
**Anchors**: MITgcm/pkg/exf/exf_getffields.F::<module>; MITgcm/pkg/profiles/profiles_init_fixed.F::<module>

### Issue or research question
Implement init in the new package `pkg/rnf` (decisions 1, 2, 6, 10 of docs/package_design.md): `data.rnf` parameters (`RNF_PARM01`), the `HAVE_NETCDF` guard, a master-thread NetCDF read of the static arrays, the global index → local `(i,j,k,bi,bj)` mapping on every grid (including exch2/LLC and blank tiles), per-tile source lists, a `GLOBAL_SUM` fraction check (1e-6), and refusal of a land cell or sparse + dense both set. (Refusing an unknown tracer moved to RUNOFF-013 on 2026-10-04, by Arch's scope resolution after both reviewers ruled the deferral legitimate. **As recorded at RUNOFF-004, describing the code as it then stood:** the reader read no tracer variables, so there was no name to match against `PTRACERS_names`, and RUNOFF-013's acceptance already named the refusal; a tracer, temperature or salinity variable present in the file was warned about per variable and not applied, `rnf_init_fixed.F:382-408`, so no value was silently wrong. **Superseded by RUNOFF-013 (closed 2026-10-05):** the warning walk no longer exists and that citation describes only the RUNOFF-004-era code; the refusal is now implemented in `RNF_NC_SERIES` and measured by execution. This correction was made by hand, because `closed_issues.md` is outside `doc_inventory.paths` and no sweep can see it -- see `TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001`.) Then assign exf `runoff` = Σ flux·frac/rA each step from the one guarded `RNF_EXF_RUNOFF` call in `exf_getffields.F`, and refuse a non-blank `runofffile`/`runoftempfile`, non-zero `runoffconst`, missing `useEXF`/`ALLOW_RUNOFF`, and targets under an ice shelf (`kTopC ≠ 0`).

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

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-04T22:05:11.774592+00:00 for iteration 2026-10-04T15:50:28.129477+00:00. Implemented the pkg/rnf sparse-runoff reader: a new rnf_nc_utils.F with six NetCDF helpers under HAVE_NETCDF; rnf_init_fixed.F reads the header and the target table in RNF_nBuf chunks on the master thread of every process, validates each entry, and places it with the mdsio_read_field.F row arithmetic (myXGlobalLo/myYGlobalLo or exch2_txGlobalo/tyGlobalo, including the fold and long-line branches) rather than a box test; per-tile source lists; fractions summed with GLOBAL_SUM_VECTOR_RL to 1e-6; tile-local refusals and array-bound overflows counted, GLOBAL_SUM_INT-ed and only then stopping every rank; RNF_SIZE.h bounds set; the skeleton stop removed from RNF_CHECK; exf runoff assigned sum_s flux_s*frac/rA each step from the one guarded RNF_EXF_RUNOFF call. Created the two sparse oracle inputs the acceptance named and which had never existed. Both reviewers approved with empty must-fix lists and neither found a code defect: review A proved the applied field bitwise identical to an independent float64 reconstruction over all 6144 cs32 cells and the ownership map a bijection with per-process counts 321+443+151+274; review B proved the cross-rank reduction with two cases the suite lacked. Scope resolution: refusing an unknown tracer moved to RUNOFF-013, since the reader reads no tracer variable and a present one is warned about, not applied.

## 🟢 RESOLVED: The configured digit oracle cannot detect a one-cell target move; promote a cell-exact applied-field check

**Date Identified**: 2026-10-04T17:30:00Z
**Date Resolved**: 2026-10-05T09:41:55.227466+00:00
**Status**: Resolved
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

Carry forward (review A, correction round 2, 2026-10-04), two documentation/instrumentation items raised as non-blocking and deliberately NOT taken in RUNOFF-004, because editing an inventoried file after both approvals invalidates them (LL-006, hit twice in this issue):

1. `docs/verification_matrix.md` **understates this project's own coverage**. It calls the sparse = dense oracle a comparison of "the end state of the run", but `compare_results.sh` compares each monitor variable as a time series over every monitor line — its own header documents this — so the oracle verifies the applied constant field at all 48 lab_sea monitor times, not just at the end. Correct it in the project's favour.
2. `tests/runoff/lab_sea_runoff_timing_check.py::check_case` reports `"monitor output has %d runoff records" % len(series["time"])`, i.e. the count of monitor *times*, not of runoff statistics. That is what produced the misleading "48 runoff records" on a sparse run with 48 times and zero runoff statistics. The sparse trigger is gone, but a truncated or misconfigured **dense** run would mislead the same way. Report the time count and the statistic count separately.

Also noted and accepted as-is: `sparse_case()` returns True on the presence of `data.rnf` alone, without requiring `useRNF`. It over-triggers slightly but fails safe — toward SKIP-and-say-so rather than a false pass — and the all-skip guard backs it up. Recorded so it is not later mistaken for an exact test.

Carry forward (Arch, 2026-10-04): `docs/verification_matrix.md` still says "the two "not seen" rows of the historical table below" after correction round 1 removed those two rows; the table now carries one embedded "not seen" value and no such rows. Review A raised it as non-blocking. I wrote the one-line fix, found it staled Bob's sealed documentation report — which both reviewers had already confirmed — and reverted it rather than spend a second correction round re-confirming a cross-reference wording. Fix it in the next issue that edits this file, inside that issue's own documentation plan. The ordering lesson is the closeout doctor's: finalize every signed field before taking the final verification receipt.

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-05T09:41:55.227466+00:00 for iteration 2026-10-05T05:47:20.935406+00:00. Closed the zero-margin gap RUNOFF-004 left in the only configured test guarding placement. Part 1: tests/rnf/applied_field_check.py dumps the exf runoff field the model actually applies (EXFroff snapshot, float64) and compares it cell by cell against an independent float64 reconstruction of sum_s flux*frac/rA from the sparse file and the run's own RAC.data; bitwise exact on lab_sea (1 and 2 processes) and cs32 (1 and 4), and demonstrated FAILING on a perturbed input, with a permanent inverted control. Enrolled as four scientific-suite commands. Part 2: rnf_init_fixed.F refuses a target whose target_lon/target_lat is not its cell's centre, by great-circle distance against 0.5*MIN(dxF,dyF) of that cell, counted into the existing nErrTgt so one tile's observation stops every rank. Review B then found the refusal failed OPEN on a non-finite coordinate while reporting that it ran, and build-dependently; both it and the pre-existing target_cell_area comparison are now fail-closed, with target_coords_nan as the 35th refusal case. That left the schema declaring valid a file the model halts on, closed by new checker rule T09 (level E) on non-finite target_cell_area/target_lon/target_lat.

## 🟢 RESOLVED: Sparse runoff time handling: interpolation, hold-exact, repeat cycles, yearly files

**Date Identified**: 2026-09-29T21:30:00Z
**Date Resolved**: 2026-10-05T19:36:22.236864+00:00
**Status**: Resolved
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

Unblocked 2026-10-04: RUNOFF-004 closed (sparse reader, per-tile lists, placement by the `mdsio_read_field.F` arithmetic, `GLOBAL_SUM` fraction check and the exf volume flux; fork `610d4cbaf`, final verification receipt `2e11b06d`, all 33 scientific commands passing). Note the reader accepts **one constant record only**: `rnf_init_fixed.F:199-217` stops the run for `RNF_useYearlyFiles` or any `RNF_period` other than 0, naming RUNOFF-005.

Carry forward from RUNOFF-033 (review A, correction round 1, 2026-10-05): **own a permanent order-sensitive accumulation case.** `tests/rnf/applied_field_check.py` compares the applied field bitwise (`--rtol 0`), and that criterion is licensed by the premise that `rnf_fields_load.F:75-77` accumulates in the sparse file's table order. Review A measured the premise true on the real binary — three entries of one source on one cell with fractions `(1.0, d, d)` where **both** small terms are 0.3 ulp of the first, giving forward vs reversed differing by exactly 1 ulp — but **no enrolled case exercises it**: both committed files have at most one target entry per cell (lab_sea 7 on 7, cs32 1189 on 1189), so none of the four enrolled oracle cases ever sums more than one term. A reorder of the per-tile list construction in `RNF_INIT_FIXED` (chunk-wise, sorted by source, or tile-local) would void the premise and **all four cases would still pass bitwise**.

This issue is the right home because it makes multi-record live and will touch `RNF_FIELDS_LOAD` itself. Review A also corrected the cost estimate: this needs **no new committed input file**. `tests/rnf/refusal_check.py::split_file` already generates a multi-entry file at run time from the committed one (each source becomes `<id>_a`/`<id>_b`, flux split, fraction 1 on a shared cell), and its docstring already says it "is what exercises the accumulation of `rnf_fields_load.F`". Extend that split from two sub-sources to **three**, sizing the two smaller sub-sources so each contributes 0.3 ulp of the first term. **The pair sum is what makes it order-sensitive, not either term alone** (review A, correction round 2): `fl(t1 + 0.3u) = t1` twice over, but `fl((0.3u + 0.3u) + t1) = t1 + u`. Two sub-sources would give a two-term sum, and two-term floating-point addition is commutative — the case would not be order-sensitive at all and would pass vacuously, which is the exact failure this issue exists to prevent. Verify order-sensitivity directly before enrolling it: reverse the terms in the reconstruction and require the bitwise result to change. Acceptance: the case is order-sensitive by construction (reversing the terms changes the bitwise result), it passes on the current reader, and it is enrolled so the suite would notice a future reorder.

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-05T19:36:22.236864+00:00 for iteration 2026-10-05T09:47:34.718995+00:00. Sparse runoff time handling: all five modes (constant, fixed period, monthly climatology -12, monthly -1, yearly files) plus hold-exact. New RNF_TIME_SETUP resolves the file's normative CF axis and the data.rnf overrides into exf's period, start time and repeat cycle; new RNF_GETREC delegates every mode to its pkg/exf routine rather than reimplementing record selection, so sparse = dense is structural and not coincidental; RNF_FIELDS_LOAD keeps two tagged record buffers, reads only records with non-zero weight and preserves its table-order accumulation. The two refusals that named this issue are gone. Six lab_sea sparse cases, three new or extended checks, and the refusal suite grown 35 -> 54 with every new guard demonstrated firing. Eleven must-fix items across three correction rounds, NONE a code defect: the time handling was correct in all five modes from the first dispatch, and every correction was to a claim about it.

## 🟢 RESOLVED: Temperature and salinity runoff contributions via tendency terms

**Date Identified**: 2026-10-02T22:30:00Z
**Date Resolved**: 2026-10-06T05:45:55.788969+00:00
**Status**: Resolved
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

Unblocked 2026-10-04: RUNOFF-004 closed (sparse reader, per-tile lists, placement by the `mdsio_read_field.F` arithmetic, `GLOBAL_SUM` fraction check and the exf volume flux; fork `610d4cbaf`, final verification receipt `2e11b06d`, all 33 scientific commands passing). Note the reader accepts **one constant record only**: `rnf_init_fixed.F:199-217` stops the run for `RNF_useYearlyFiles` or any `RNF_period` other than 0, naming RUNOFF-005.

Scope moved in from RUNOFF-004 (Arch, 2026-10-04): **refusing a tracer name with no matching ptracer** belongs here. **As recorded at RUNOFF-004, describing the code as it then stood:** the reader read no tracer, temperature or salinity variable, so there was no name to match against `PTRACERS_names`; a variable present in the file was warned about per variable and not applied (`rnf_init_fixed.F:382-408`). Both RUNOFF-004 reviewers ruled the deferral legitimate because no value is silently wrong. This issue's acceptance already names the refusal; `docs/runoff_schema.md` §3.5 and `esx/project_profile.md` now mark it as arriving here. **Implemented 2026-10-05 (RUNOFF-013):** the warning walk of that paragraph no longer exists; the matching and its refusals are in `RNF_NC_SERIES` (`MITgcm/pkg/rnf/rnf_nc_utils.F`), so the `rnf_init_fixed.F:382-408` citation above describes only the RUNOFF-004-era code. This line was found by hand, because `open_issues.md` is outside `doc_inventory.paths` and receives no stale sweep (see [the documentation contract](devel-loop/documentation_contract.md), `TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001`).

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-06T05:45:55.788969+00:00 for iteration 2026-10-05T19:43:24.139854+00:00. pkg/rnf applies the runoff heat, salt and passive-tracer tendency terms in decision 3's form [(mX) - m_X*X_ref]*mass2rUnit*recip_drF(k)*recip_hFacC, hooked after the ICEFRONT calls in APPLY_FORCING_T/S and beside GCHEM_ADD_TENDENCY for tracers, with the per-branch T_ref/S_ref table resolved from the live pkg/exf sources rather than from the design table. Where several sources feed one cell, volumes add while temperature, salinity and tracers are flux-weighted means, and a source carrying no temperature delivers its volume and salt and no heat. RNF_NC_SERIES refuses seven conditions around matching a runoff tracer to a ptracer; five now have an executed case. Both acceptance instruments are enrolled and both ran in the final receipt: 8 of 8 analytic cases covering 10 of 10 decision-3 table rows with every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, and the exf cross-path at 3.559e-16 over 7 cells. Three correction rounds and fifteen must-fix items from two independent reviewers, none of them a defect in the tendency terms. The load-bearing finding was review A's: no configured command executed RNF_TENDENCY_APPLY_T or _S at all, because only cs32/input.rnof_sparse carries runoff_temperature and no suite command ran that directory, none carries runoff_salinity, and no enrolled input set salt_EvPrRn - so both routines returned at their first executable statement in all 57 scientific commands. Review A proved by mutation that a wrong X_ref or a sign flip would therefore have shipped green, and that the Package column is blind to the sign flip (0.00e+00) while the two-run Total column catches it at 2.000e+00. Both instruments are now enrolled (focused 9->10, scientific 57->59), each builds its own binary under a staleness rule, and --allow-missing-rows was deleted because it suppressed both the uncovered-row failure and the missing-binary exit. Review B established the physics independently with an input shape no case had - three sources, two cells, fractions != 1, one source with no temperature - closing the domain salt budget to the same number for two different fraction splits (rel 0.0 and 1.70e-16) and the source heat to 1.63e-16 in both. refusal_check grew 58 -> 64 cases: three RNF_NC_SERIES refusals a reviewer fired against a record calling them unreachable, and three at-the-bound counterfactuals that pin .GT. against .GE. from the non-firing side. Record work: the stale-sweep scope is now stated as a class after measurement showed every tracked project record document is outside doc_inventory.paths - eleven files plus the assessments tree, including lessons_learned.md and the ledger the framework issue is filed in. Three framework issues filed with an assessment, plus RUNOFF-036. Four of my own process errors cost rounds: a brief citing a loop_gate interface that does not exist, two briefs omitting the sealed report, resuming both reviewers at once (an LL-005 collision that destroyed one sealed run), and editing a policy file after the seal, which stranded an approval and caused round 3 outright. Decisions made in-issue: the two reviewers conflicted on --allow-missing-rows and I took review A's ruling, which dissolved the conflict because main's coverage branch already exempts --case selections, so the flag was deleted and --build replaces it. Review B's optional duplicate-RNF_trPtr hardening was rejected as unreachable rather than implemented: NetCDF refuses a name with a trailing blank and collapses a trailing NUL to the same stored name, then refuses the duplicate, so two distinct variables can never trim to one tracer name - measured by Arch and re-measured by review B, which concurred. The owner revoked Slack authorization mid-iteration ('cancel the slack for now'); all 102 undelivered events were recorded unauthorized rather than failed or unavailable, because that is a revocation and not a provider fault, and removing the provider from esx/project.json was deferred to the framework pass because that file is inside the candidate signature and could not be edited while this verification held the candidate.

## 🟢 RESOLVED: exf range check stops point-source runoff above 1e-6 m/s

**Date Identified**: 2026-10-03T04:30:00Z
**Date Resolved**: 2026-10-06T20:17:12.743896+00:00
**Status**: Resolved
**UUID**: RUNOFF-030
**Anchors**: MITgcm/pkg/exf/exf_check_range.F::<module>; docs/package_design.md::<module>

### Issue or research question
`EXF_CHECK_RANGE` stops the run if `runoff` exceeds 1e-6 m/s on a wet cell, and `useExfCheckRange` defaults to true. A 1000 m³/s river into one 2 km cell is 2.5e-4 m/s. Decide between documenting `useExfCheckRange=.FALSE.`, skipping the runoff upper bound when `useRNF` is true (one more guarded exf line), or a package-specific bound.

### Evidence
RUNOFF-010 design, decision 2: `exf_check_range.F:175-191`, `211-216`; default `exf_readparms.F:307`. Those two line ranges are the **pre-change** ones and no longer resolve; after correction round 1 the runoff block is `exf_check_range.F:215-261`, the freshwater-flux block `84-109` and the stop `280-285`.

**Implemented 2026-10-06 (RUNOFF-030, round 0).** The present tense of the question above describes the code *before* this change. What the code does now: the runoff **upper** bound of `EXF_CHECK_RANGE` carries `.AND. .NOT.useRNF`, the negative-runoff test is unchanged and fires either way, the four-line m/yr advisory of that block prints only with `.NOT.useRNF` (its text unchanged), and — **corrected 2026-10-06 on review B's finding** — the freshwater `sflux` bound of the same routine **was** also conditioned on `useRNF`, in round 1, after the scope was widened: it now tests `sflux + runoff`, re-adding what `exf_getforcing.F:313` subtracts, so the quantity tested under `useRNF` is `evap - precip`. The original wording here said no other field's range check was touched, which was true of round 0 and false after round 1; paragraph below corrected the scope for a sequential reader but not for anyone reading or grepping this line alone. Every exf range check **other than those two** is untouched. The package-side bound is `RNF_srcFluxMax` = 1e7 m³/s on the volume flux of one source, enforced in `RNF_NC_READ_ONE` as each record is read and reported by `RNF_SUMMARY` in four lines naming which bounds the run was held to — RUNOFF-040 added a fifth, for the per-cell bound `RNF_cellVolMax`, so "four" is this issue's count and not the present one — (the fourth added in correction round 2 on review A's finding that the conditioned `sflux` bound was unreported). Both enrolled tendency instruments (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`) had been switching `useExfCheckRange` off to work around the bug; both overrides are removed and both still pass (8 of 8 cases over 10 of 10 decision-3 rows; 7 cells at 3.559e-16). `refusal_check.py` grew 64 → 66 cases with `flux_above_source_max` (shown failing on a mutant with the bound weakened fourfold) and its at-the-bound control `flux_at_source_max`. Derivation of the number, and what a per-source bound does not cover, are in [package design](docs/package_design.md) decision 2.

**Correction round 1 widened the scope to a second condition in the same routine, after round 0 measured that the first was not sufficient, and the issue's stated problem is now actually fixed.** `EXF_CHECK_RANGE` also stops the run when `ABS(sflux)` exceeds 1e-6 m/s (`exf_check_range.F:84-109`), and `EXF_GETFORCING` subtracts runoff into `sflux` at `exf_getforcing.F:313` before calling the check at `:346-349`, so skipping the runoff upper bound alone left every point source refused anyway. That bound is now applied to `sflux + runoff` when `useRNF`, re-adding exactly what `:313` subtracted, so what is tested is `evap - precip` — the part of `sflux` the bound exists for — and an out-of-range `evap - precip` is **still refused**, which the new case `sflux_out_of_range` measures with `useRNF` on, no runoff at all and `precipconst = 1e-4` m/s. The coordinator verified the three source sites independently before widening the scope.

Measured acceptance, now enrolled rather than a hand probe: `flux_at_source_max` applies 3.21e-4 m/s, 321 times the exf bound, and **ends normally with `useExfCheckRange` at the lab_sea default `.TRUE.`**, on 1 and on 2 processes. Each condition is necessary and was attributed separately by reverting it alone: with the `sflux` restore disabled the case fails on the `sflux` warning; with the runoff skip reverted it fails on `EXF WARNING: runoff out of range ... 0.321307089844219D-03`, the model's own print of the applied field. Replacing the restore by a removal (`.AND. .NOT.useRNF` on the whole `sflux` test) leaves that case passing and fails `sflux_out_of_range` on exactly the missing `sflux` warning, so the pair separates "restore" from "remove". `refusal_check.py` is 64 → 67 cases, 67 of 67 passing single-process (86 s) and on `-mpi 2` (110 s).

**Deliberately not widened:** the dense path. A dense `runoffFile` above 1e-6 m/s is still refused by both bounds and still needs `useExfCheckRange=.FALSE.`, because both conditions are guarded by `useRNF` alone. The same pair has always fired for the dense path, so that defect is wider than `pkg/rnf` and belongs in the eventual upstream discussion.

Two corrections to the premises this issue was dispatched with, both measured: (1) `tendency_term_check.py` does **not** exercise the runoff bound at all — the check is called only at `nIter0` and the case's first record is dry under `RNF_holdRecord`, so the one call sees zero runoff (retained `L_set` run: `exf_debugLev = 2`, `it= 0` selects `rec0 = 1` with `fac = 1.0`, 0 `EXF WARNING` lines) — and `exf_heat_check.py` applies 4.0e-7 to 7.6e-7 m/s, under the bound on both paths. Both overrides were unnecessary; removing them measures that nothing regressed, not that the relaxation works, and both instruments are unchanged (8 of 8 over 10 of 10 rows; 7 cells at 3.559e-16). (2) The round-0 limit that no enrolled case could assert an `EXF_CHECK_RANGE` outcome is now **lifted for the cases that matter**, because `flux_at_source_max` asserts a normal end rather than a stop, and `sflux_out_of_range` is built with a uniform `precipconst` so that every process has out-of-range cells of its own and prints its own `STOP` line. The limit still holds for any case whose breach would be confined to one tile, since `EXF_CHECK_RANGE` calls `STOP` without `ALL_PROC_DIE`.

### Scientific or engineering impact
Without a decision every realistic point-source configuration on a fine grid stops at the first step, or users disable all exf range checks.

### Proposed action and acceptance
Recommend skipping only the runoff upper bound when `useRNF` (other exf checks stay), with a package-side sanity bound reported in the summary. Acceptance: a lab_sea case with a point source above 1e-6 m/s runs with default `useExfCheckRange`; the dense path behaviour is unchanged.


**Correction round 3 (2026-10-06): the error class, swept by a predicate instead of by another review round.** Review B's fifth must-fix was `docs/package_design.md:333`, "This call is the only change to exf code" — false, because `exf_check_range.F` is a second exf change made by this issue and enumerated 70 lines below in the same decision. It now reads "one of the two changes to exf code", names the other and points at its paragraph, and keeps the true second sentence (`exf_mapfields.F` is not edited). The diagnosis checkpoint established that the mistaken premise was the *scope* of each round, not the code: rounds 1 and 2 were scoped as "fix these named lines", so round 1 found four and round 2's review found a fifth in a file round 2 had just edited. **In three rounds no reviewer finding has touched the implementation.**

The predicate is `tests/footprint_claim_sweep.py`, keyed on *(a package mention) near (an exclusivity marker) near (a footprint word)* — on the package rather than on the edit, because **a footprint claim never names the site that was added**, which is why Arch's changed-path predicate returned zero. It ships a `--self-test` so recall is measured rather than asserted: **8 of 8** known claims of the class match (the five must-fixed, plus three recall gaps found while building it), with 0 of 3 benign lines wrongly matched. Five measured facts shaped it, each of which had silently cost recall:

- the window must reach the **preceding** line, because the fifth must-fix put its marker on the last of three lines and its only package mention on the middle one;
- the package must be matched as a **substring**, since `\bexf\b` matches neither `useExfCheckRange` nor `EXF_CHECK_RANGE` (`_` is a word character) — that alone had cost two of the five;
- a package name in the **file path** counts as a mention, which is what finds `exf_check_range.F`'s own banner and `exf.rst`'s paragraph;
- Markdown emphasis splits a marker (`no *other* exf field` does not match `\bno other\b`), so emphasis is stripped before matching — this had hidden round 3's own fix;
- `git ls-files` at the project root lists **nothing** under `MITgcm/`, which is a separate, git-ignored clone. Until that was fixed the sweep covered neither the package source nor the MITgcm docs, and every future run would have been a false clean.

**It found a sixth instance, live, which two review rounds and two of my own passes had missed:** `esx/project_profile.md` asserted "the exf **negative**-runoff test is not skipped … and no other exf field's range check changed". The `sflux` check *is* another exf field's range check and round 1 conditioned it, so the sentence was false. Fixed to name both conditioned tests before the exclusion. That is the evidence that the predicate has recall over the class in practice and not merely on its own self-test.

**Triage of the sweep, after the scope was made declarative. At candidate `993054b2` (round 4): 167 files swept, 73 candidate hits, 62 to triage, 11 keep hits covering 11 distinct claims from 11 `KEEP` entries — a one-to-one mapping, exit 1. At candidate `496538905` (round 5, as approved): 167 / 74 / 63 / 11, the extra hit being the round-5 paragraph below.** Three figures in the round-3 version of this paragraph were wrong and are corrected here rather than quietly: it said "69 candidates: 10 deliberate keeps, 59 out of class", which matched neither the round-3 seal (72/62/10) nor the state after Arch committed both repositories (70/61/9). **State the self-reference, because otherwise no reader can reproduce a single number:** `open_issues.md` is itself swept, and lines 458, 468 and this one are themselves candidates, so editing this paragraph changes the count it reports. The "10 keeps" figure was also ambiguous in a second way review B identified — it was 10 *hits* over 8 distinct claims out of 11 entries, because the path-keyed `kept()` labelled two lines in one file with the same needle's reason. With per-needle matching that ambiguity is gone: hits, claims and entries are all 11. The keeps are recorded in the script's `KEEP` list, each with the antecedent that makes it true, matched by substring rather than line number so an entry cannot rot on an insertion above it; three guards now fail loudly — a dead needle or a multi-line needle (exit 2), and a `KEEP` path absent from the swept set (exit 3). The ones to triage are out of class and were read individually: coverage claims ("only at `nIter0`", "only the records exf would read"), behaviour claims ("exf applies it only when a dense file is set"), measurement claims ("unchanged with the check at its default: 8 of 8 cases"), set-up descriptions in the matrix's sparse-equals-dense rows, and live issue prose describing this change correctly. None asserts exclusivity over a set of edit sites. Three rule-based exclusions keep that number workable and are stated in the script: a no-change **result** claim is excluded by its object, dated history files by their name (`open_issues.md` deliberately **not** among them, since it carried one of this issue's stale claims), and upstream `MITgcm/` files this project neither wrote nor may edit by an authored-set filter that is **declared, not derived from VCS state**: it resolves `source_paths` and `configuration_paths` from `esx/project.json`, plus the two MITgcm doc pages named individually in `DOC_EXTRA`. That declaration is what keeps the upstream-but-edited `exf_check_range.F` in scope — `esx/project.json` lists `MITgcm/pkg/exf`. The round-3 version of this clause said the filter retained "anything currently modified", which is the premise the diagnosis checkpoint refuted: it keyed on working-tree dirtiness, so Arch committing emptied it and dropped that very file out of the swept set. Review A caught this clause still stating the retired rule as live — a footprint claim about the sweep, inside the paragraph describing the sweep, of exactly the class the sweep exists to catch.

**Judgment call Arch asked me to make rather than inherit, on `esx/project_profile.md`'s "every other field's range check are untouched".** I agree with both reviewers that it is **true** and I have kept it implicit, and the reason it differs from `docs/package_design.md`, which was made explicit, is the audience and not consistency for its own sake. The profile's bullet is read top to bottom as a contract: its two enumerating sub-items are two lines above, inside the same bullet, and a reader who has not read them has not read the convention either. `package_design.md:407` sits in a 60-line decision whose bullets are routinely cited and quoted *individually* — the fifth must-fix was created by exactly that, a clause lifted out of its antecedent — so there the exclusion is spelled out. Both are in the sweep's `KEEP` list with these reasons, so the asymmetry is recorded rather than looking like an oversight. Where the profile *did* assert exclusivity with no local antecedent, which is the sixth instance above, it was corrected and not kept.

**Correction round 4 (2026-10-06): the sweep's scope made declarative and its guard made per-needle.** Review B's must-fix was `docs/package_design.md:333`, "This call is the only change to exf code" — the fifth instance of the class, false because `exf_check_range.F` is a second exf change enumerated 70 lines below in the same decision. It now reads "one of the two changes to exf code", names the other, points at its paragraph and keeps the true second sentence; it states a **count**, so a third site contradicts a number rather than slipping past a vague word.

**Two defects underneath it, which compose, and neither was in the round-3 measurement.** Nothing in round 3 was wrong when it was measured at 13:52:58 UTC; Arch committed both repositories at 14:02:13 UTC and that is what changed the answer.

1. **Scope was a function of VCS state.** `nested_scope()` kept a nested-repo file if it appeared in `git status --porcelain` or lay under one of three guessed prefixes. Committing MITgcm emptied that status and dropped `pkg/exf/exf_check_range.F` — the file carrying this issue's own code change — out of the swept set: 72 candidates to 70, 10 keeps to 9. The docstring stated the premise outright ("any file we have modified"), and working-tree dirtiness is not a stable property; it empties on exactly the act `CLAUDE.md` tells this project to perform often.
2. **The guard that should have caught it was blind.** `unused` asked `kept(path, text)`, which returns the *first* matching reason for that **path**, so one live needle marked every needle on that file as used. `KEEP` holds **eleven** entries, not the ten recorded in the round-3 seal and in this file. Entry 7 was dead under *every* scope including the sealed one, masked by three live needles in the same file, and its needle was **multi-line** while `kept()` compares one stripped line — so it could never match by construction. The sealed "0 stale KEEP needles" was therefore an artifact of the defect, not a property of the allowlist, and the live consequence was that `esx/project_profile.md:228`, the corrected sixth instance, landed in TRIAGE on every run instead of being retired with its reason.

Above both, review A named the generative premise, which belongs in the retrospective: **the candidate signature is a sufficient guard only for artifacts that are functions of file content.** This one was a function of (content, VCS state), so committing changed its behaviour while the signature stayed `6ab98655` and neither the signature, the documentation contract nor the focused suite objected.

**Mechanism chosen, with its measured cost: derive the nested-repo scope from `esx/project.json`.** `source_paths` and `configuration_paths` already *are* this project's declarative statement of what it owns, and they cover all eleven authored files — `model/inc/PARAMS.h`, the seven `model/src` hooks, `pkg/exf/exf_check_range.F`, `pkg/exf/exf_getffields.F` and `pkg/ptracers/ptracers_apply_forcing.F` — plus `pkg/rnf` and the verification set. The argument for it over a parallel list in the script is that the thing which failed was scope drifting away from the project's own declaration, so the fix is to *use* that declaration rather than to add a second one that can rot independently. The two MITgcm documentation pages this project writes are not build inputs and so are not in `project.json`; they are declared in the script as `DOC_EXTRA`, named individually rather than as the `doc/phys_pkgs/` prefix, which is 29 upstream pages this project neither wrote nor may edit — that prefix was part of round 3's over-coverage. Measured result **at candidate `993054b2`: 167 files swept, 73 candidate hits, 62 to triage, 11 keeps, exit 1**, identical with both repositories committed and clean and with the tree dirty — which is the property round 4 existed to establish, since round 3's scope inverted on exactly the act of committing. (This sentence carried 72/61 until closeout: it was written mid-round, before the final edit to this record added the 73rd hit. That is the third instance on this issue of a figure going stale as it was written, and the reason every figure here is now bound to the candidate it was measured at.) Because `MITgcm/pkg/exf` is declared as a directory, the swept set still includes exf files this project never edited; that over-coverage is the stated price of using the existing declaration.

**Merge-base keying was refused, not deferred to.** Arch proposed it; both reviewers refuted it independently and I re-measured it: `git merge-base --is-ancestor master HEAD` returns 0 **today**, with 38 commits in `master..HEAD`, so the moment `master` contains this work — the upstream PR landing, a merge, a sync fast-forward — `base..HEAD` empties and the failure returns byte for byte at 70/61/9 with exit 2. That is deferral, not immunity, and must not be recorded as immunity. `master` is also unavailable as a ref in two further ways, both checked: the clone's only remote is `origin` (the fork), there is **no `upstream` remote at all**, and a clone made with `-b new_runoff` would have no local `master`. **Rebase is safe in the opposite direction from the one feared:** rebasing `new_runoff` onto a newer `master` replays this project's commits, so they stay in `base..HEAD`; the harmful move is `master` gaining the work, which is the planned upstream rebase and is already RUNOFF-036's trigger.

**The scope guard is what closes the class**, and both reviewers proposed it independently: every path named in `KEEP` must be present in the swept set, else the sweep fails loudly naming the absent file (exit 3). It is required rather than nice to have because round 4's alarm fired **by luck of placement** — of the eleven authored files, exactly one (`exf_check_range.F`) happens to hold a needle, so a silent shrink in any region without one would have fired nothing and reported a confident, wrong clean. An assertion on the *set* does not depend on where the keeps live, and it makes scope and recall one check.

**Demonstrated failing as well as passing, per LL-009, 16 of 16 acceptance checks:** the per-needle guard reports round 3's multi-line entry 7 **dead** while round 3's path-keyed test calls it live; the scope guard names `MITgcm/pkg/exf/exf_check_range.F` when it is removed from the swept set; and the pre-fix variant reproduces **70 candidates, 61 to triage, 9 keeps, blind guard reporting 1 stale while the per-needle guard finds 2 really dead**. Scope independence from VCS state is proved behaviourally rather than textually: `authored_paths` resolves with `subprocess` **denied**. One defect in my own acceptance harness was found this way and is worth recording — `kept()`'s default argument binds the module-level `KEEP` list object at definition time, so rebinding the name left the reconstruction reading the repaired list and it first reported 70/60/10; mutating the list in place gave the correct 70/61/9.

**`MUST_MATCH` provenance corrected on review B's check.** Round 3 listed `docs/package_design.md:404` as the fifth must-fixed sentence; it was **never must-fixed** — review B judged that line true in round 1 and I tightened it voluntarily in round 2. The genuine fifth is `open_issues.md:441`'s "…and no other field's range check was touched", and the predicate does match it, so recall was intact and only the record was wrong. **Which one was missing matters:** it is the only must-fixed instance that lived in a *record* file, which is the very reason the script's `HISTORY` list keeps `open_issues.md` in scope while excluding the append-only records, so a provenance list that omitted it also quietly undercut that decision. It is quoted from review B rather than verbatim from git and labelled as such, because the pre-fix bytes are in no commit: this record paragraph was first committed only after it had been corrected.

**Carried findings, recorded and deliberately not implemented this round** (review B measured that none hides a live false claim today): `RESULT_CLAIM` can shield a genuine footprint claim that happens to sit beside a true no-change claim, and `CONDITIONAL` can fire on an edit verb it should not — both narrow-able by requiring the result or condition word to be the marker's own object rather than merely nearby; and the sweep's `SUFFIXES` exclude `.py`, so a footprint claim in a test or tool is undeclared scope. Also unenrolled by Arch's deliberate decision: the sweep is registered as a required procedure in `esx/project_profile.md` but is in no configured suite, because a nonzero exit means "triage these candidates" rather than "these are defects". **(Both of those two were resolved by RUNOFF-042 on 2026-10-08 and the sentences above are the RUNOFF-030 state, annotated in place rather than rewritten because this file is an append-only record of what that issue delivered: `.py` is now in `SUFFIXES` with the sweep's own file excluded, and `--self-test` plus the new `--guards` mode are in the `structural` suite — the default invocation still is not, for the triage-noise reason stated here. The two predicate narrowings, `RESULT_CLAIM` and `CONDITIONAL`, were explicitly out of scope on RUNOFF-042 and remain carried.)**

**Correction round 5 (2026-10-06): the last open item, review B's item 2 — the provenance of `MUST_MATCH` element 5.** Arch applied the two-line correction himself because the review fully specified it; I audited it rather than trusting it, 11 of 11 audit checks passing.

**Arch's fixture correction is right, and verified independently.** Element 5 is now a **contiguous, single-line, verbatim** substring of `1224dd2:open_issues.md` line 441, and it is absent from `d95645a` — so the old "verbatim from the pre-change tree" label was indeed false for it, and the element is **recovered text traceable to a commit**, not a reconstruction. Arch's correction of review B's proposed remedy also holds: the **bare** committed clause does **not** match the predicate, because `candidate()` needs a package mention inside its window and "no other field's range check was touched" carries none, so trimming to it would have dropped recall from 8 of 8 to **7 of 8 silently**. The stem is load-bearing.

**What Arch got wrong, and it is this issue's own error class one generation later.** Three places state element 5's provenance — the module docstring, the `MUST_MATCH` block comment and the element's own comment. Round 4 replaced the element and updated the docstring; round 5 corrected the block comment and the element comment and **left the docstring behind**, still saying the fifth "is quoted from review B's provenance check, because its pre-fix bytes are in no commit". The block comment Arch wrote in the same edit says "Keep all three statements in step" while the third was out of step. Corrected: the docstring now names the commit and states that all five fixtures are recovered text, and it records that three places state this and that both failures had the same shape, so the method is to compare all three rather than read one.

**A measured weakness of element 5 as an exemplar, which the brief asked me to report if true, and it is true.** It matches on marker `no other` + footprint word `check` + package token **`RNF`** — and that `RNF` comes from `` `useRNF` `` in the *stem*, not from the claim's own subject, which names no package. So element 5 tests the package window reaching back across a sentence to a mention the claim does not itself make. That is a real property of this class — element 4 has the same shape, marker on the last line and package on the middle one — so the fixture is legitimate, but it is weaker than a claim that names its own package, and a future narrowing of `PACKAGE_WINDOW` would drop it before the elements that name their own package. Recorded in the element's comment so that becomes a decision rather than a surprise. **Corrected at closeout on review A's and review B's independent measurements: element 4, not element 5, drops first.** Both measured the frontier — 8 of 8 at windows 90/80/70, 7 of 8 at 60 (missing element 4), 6 of 8 at 50 and below (missing 4 and 5), with zero false positives at every width. The mechanism and the judgment were right and are in fact reinforced, since element 4 sharing the cross-clause shape is exactly why it goes first; only the ordering was wrong. Both reviewers classed it a carried note rather than a must_fix, because it is wrong about an ordering and not a capability, it cannot cause a silent loss (the tool names the dropped elements by index on the first run), and a re-seal over a comment would have stranded two fresh approvals for less than the error costs. The same claim in `tests/footprint_claim_sweep.py` is therefore **still uncorrected by design** — that file is inside the acceptance set and this record is not, so the two deliberately differ until the next issue edits that file.

**Attribution corrected on both reviewers' finding:** the `docs/package_design.md` line-333 fix was made by **round 3**, not round 4. `ffca56b` carries the false text and `1224dd2` already carries "one of the two", so the round-4 `Edit` was a no-op on already-correct bytes; the round-4 disposition's "round 4's must-fix" wording is corrected in this round's seal. Measured state after round 5: self-test **8 of 8 and 0 of 3**, sweep **167 files swept, 74 candidate hits, 63 to triage, 11 keeps**, zero dead, absent or multi-line needles, exit 1. The hit count is one higher than round 4's 73 for the reason this record already states: `open_issues.md` is itself swept, so writing this paragraph added a candidate line to it. No fixture's match status moved, which is what the provenance correction should leave untouched.

**Scope widened by Arch, 2026-10-06, on an escalation from round 0 that I verified myself.** Skipping the `runoff` upper bound is **not sufficient** and the issue's own acceptance is unreachable without a second change, so the scope now includes it.

`EXF_CHECK_RANGE` has a second bound that refuses the same configuration: `ABS(sflux) .GT. 1.E-6` (`exf_check_range.F:63-64` as it stood at fork commit `6aa841e2e`, now `:103-104` reading `ABS(sfluxLoc)`), and `exf_getforcing.F:313` does `sflux = sflux - runoff` inside `#ifdef ALLOW_RUNOFF` **before** the check is called at `:346-349`. Measured by the implementer on the committed build: a source applying 3.21e-4 m/s draws no `runoff out of range` line at all — the skip works — and then stops on `EXF WARNING: sflux out of range for bi,bj,i,j,it= 2 1 3 3 1 -0.321319428044935D-03`. I confirmed all three source sites independently before deciding. **Citation corrected 2026-10-06** on review A's finding: this paragraph originally cited `:74-75`, which resolved against neither the pre-change file (`:63-64`) nor the candidate (`:103-104`) — it matched a round-0 intermediate state, and the line numbers moved twice during the issue. The Evidence paragraph below already handled that class correctly by naming the enclosing blocks rather than the bare condition, which is the form to prefer.

So with only the runoff bound relaxed, this issue's stated problem — "every realistic point-source configuration on a fine grid stops at the first step" — remains true, and a point-source user must still set `useExfCheckRange=.FALSE.`, which is exactly the outcome the issue exists to avoid. Closing on the half change would deliver none of its value.

The scope therefore adds the implementer's proposed minimal form: **compare `ABS(sflux + runoff)` when `useRNF`**, which re-adds the quantity `:313` subtracted so the check still guards `evap - precip`, the part of `sflux` it is actually for. Unchanged: the workflow policy (still `scientific_change` / `guard_relaxation`, so no `workflow_amendment`), the `sflux` bound for every non-`useRNF` run, and every other field's check.

**Deliberately not widened:** the same pair fires for a dense `runoffFile` above 1e-6 m/s, so the upstream defect is wider than `pkg/rnf`. Relaxing it for the dense path too is an upstream change beyond this project's remit and is not in scope; it belongs in the eventual upstream discussion, and the dense behaviour stays exactly as it is today.

**Two premises of my round-0 brief were wrong, both corrected by the implementer's measurement, and the corrected figures are what this issue now carries.** I had claimed the two enrolled tendency instruments exercise the check because they disable it. They do disable it, but: `EXF_CHECK_RANGE` is called only at `myIter.EQ.nIter0` or `exf_debugLev.GE.debLevC` (`exf_getforcing.F:346-349`), and `tendency_term_check.py` presents **zero** runoff to it at `nIter0` because record 1 is dry under `RNF_holdRecord`; `exf_heat_check.py` applies 4.0e-7 to 7.6e-7 m/s, **under** the bound. Removing their overrides therefore measures that nothing regressed, not that the skip works. The applied field of the tendency cases is **3.21e-5 m/s (32x the bound)**, not the "about 4e-5, forty times" that I took from a source comment instead of measuring.

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-06T20:17:12.743896+00:00 for iteration 2026-10-06T06:25:01.472116+00:00. Relaxed two pkg/exf range checks for sparse point-source runoff, both guarded by useRNF alone, and moved the magnitude guard into pkg/rnf. EXF_CHECK_RANGE refused any wet cell above 1e-6 m/s with useExfCheckRange defaulting true, so every realistic point-source run stopped at its first step: 1000 m3/s into one 2 km cell is 2.5e-4 m/s. The runoff upper bound is now skipped when useRNF, and the sflux bound is applied to sflux + runoff because EXF_GETFORCING subtracts the runoff just before the call, so without the restore the same volume would be refused there instead; both relaxations are needed and each was attributed to its own warning by a reverting mutant. The negative-runoff test, the m/yr advisory and every other field's range check are untouched, and a run with useRNF false is byte-for-byte unaffected including the dense runoffFile path, measured by two no-change experiments at 11 and 13 digits. pkg/rnf takes over the displaced guard: RNF_srcFluxMax = 1e7 m3/s per source enforced in RNF_NC_READ_ONE on every record as it is read, naming the source, record, value and limit, and reported in four RNF_SUMMARY lines that this issue also enrolled in refusal_check so the bound report is observed rather than inert. Both enrolled tendency instruments had been switching useExfCheckRange off to work around the bug; both overrides are removed and both still pass. The bound is a file-scale unit-error filter and not a per-cell bound, which review B measured: four sources at the bound collapsed onto one lab_sea cell apply 1.285228e-3 m/s, 1285 times the relaxed exf bound, ending normally with no warning. That uncovered class is filed as RUNOFF-040 and is the one genuinely scientific residual. Six rounds and five rejections, none of them in the implementation: the Fortran was approved in round 1 and is byte-identical across all five later rounds, verified by hash five times by review A and twice by review B. Every must_fix concerned records, documentation, or tests/footprint_claim_sweep.py, the predicate built in round 3 to retire the recurring stale-footprint-claim class after the diagnosis checkpoint measured that keying on the changed path finds zero candidates because a footprint claim never names the site that was added. That predicate found a sixth live false claim both reviewers had missed, and then produced four further rounds of defects of its own: VCS-keyed scope broken by Arch's own commit, a stale-keep guard keyed on the path so one live needle vouched for eleven, provenance mislabels, and three independent figure-drift instances.

## 🟢 RESOLVED: no per-cell bound on the applied runoff field after the exf relaxation

**Date Identified**: 2026-10-06T13:30:00Z
**Date Resolved**: 2026-10-08T00:44:51.379738+00:00
**Status**: Resolved
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

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-08T00:44:51.379738+00:00 for iteration 2026-10-06T20:31:34.534989+00:00. Closed the one genuinely scientific residual of RUNOFF-030: the aggregate per-cell magnitude of the applied runoff field had no check at all. RNF_cellVolMax = 0.2 in pkg/rnf/RNF.h, enforced in RNF_EXF_RUNOFF every step, refuses a cell whose one-step runoff exceeds that share of its top-layer volume, naming the cell, its XC/YC, the value, the limit and the thickness, with the count reduced by GLOBAL_SUM_INT so one tile's refusal stops every process. The witness was review B's four-source collapse file, rebuilt from its description and confirmed on the committed pre-change build FIRST: normal end, zero EXF WARNING lines, 1.2852284e-03 m/s at one cell, 1285 times the bound RUNOFF-030 relaxed. It is now the refusal case cell_above_vol_max, shown failing on a mutant with the bound weakened tenfold, with cell_at_vol_max at 0.99 of the bound as its control. The value is derived, not fitted: f is exactly the Courant number of the top-layer outflow the injection requires, so 0.2 is a fifth of the advective stability limit, and the linearisation error of the surface tracer dilution is exactly f squared, 4 per cent at 0.2. It separates the two measured configurations with room on both sides, flux_at_source_max at 0.578 of the bound and the witness 2.31 times over. Review A established that the bound generalises and that the 2 km Amazon refusal is correct, finding no legitimate single-source configuration it refuses; review B cleared the mechanism, finding no evasion route, no deadlock, and the enrolled case non-vacuous. Both approved candidate 04447c36 with empty must_fix lists, and the implementation was byte-identical from round 0, rnf_exf_runoff.F hashing e6baaf17 in all four rounds. Four correction rounds were spent entirely on records, and three of the four corrections in the final round traced to Arch's own text rather than to the implementation.

## 🟢 RESOLVED: Volume, heat, salt and tracer budget closure checks

**Date Identified**: 2026-10-02T22:30:00Z
**Date Resolved**: 2026-10-08T13:19:08.884967+00:00
**Status**: Resolved
**UUID**: RUNOFF-016
**Anchors**: docs/model_contract.md::<module>

### Issue or research question
Script-based checks that Σ applied volume = Σ source flux, and heat/salt/tracer input equals Σ flux·X per source, every record, across tiles and processes.

### Evidence
Owner direction 2026-10-02 (owner away for several days): develop and test the new runoff program across many MITgcm configurations, with and without T, S and tracer contributions, in every time mode, as a robust, documented MITgcm package following MITgcm coding standards; T/S fluxes follow the shelfice/icefront tendency pattern. Invariants: docs/model_contract.md Invariants.

### Scientific or engineering impact
The strongest independent oracle for the tendency-based contributions where no dense path exists.

### Proposed action and acceptance
Acceptance: checks pass to 1e-12 relative on lab_sea and cs32 sparse cases, single and MPI; a deliberately broken **fraction sum** fails them.

**Acceptance reworded 2026-10-08 by Arch, on the implementer's escalation, because the original was unachievable as written.** It said "deliberately broken fractions fail them", and Arch's brief named a *permutation* of one source's fractions across its target cells. A permutation cannot fail a budget: every right-hand side is weighted by `Σ_c frac_{s,c}`, which a permutation leaves at exactly 1, so it is budget-invariant **by construction**. Measured bitwise — all four residuals unchanged from the unperturbed run — while the per-cell oracles see 3.333e-01, so a permutation is caught by `applied_field_check` and `tendency_term_check` and is precisely the wrong control for this instrument. Arch reproduced the arithmetic independently.

The perturbation that *does* justify a budget is a fraction **sum** error: it leaves every per-cell value consistent with its own declared fraction while the total delivered to the grid is wrong. The implementer built it as `--control fracsum`, scaling one source's fractions by `1 + 5e-7` — **inside** `RNF_fracTol = 1e-6`, so `RNF_INIT_FIXED` accepts the file and `RNF_INIT_VARIA` does not even warn (asserted) — and the four closures then miss by 1.47e-07, 1.68e-07, 1.64e-07 and 1.41e-07 while the per-cell criterion stays at round-off. **Scoped 2026-10-08 by Arch after review B refuted the first wording by execution.** I wrote that the perturbation "is invisible to every other instrument in the project", repeating the implementer's claim without checking it. It is false for the **volume** leg: review B built the perturbed file and ran `applied_field_check` on it, whose applied-volume invariant (`applied_field_check.py:873`, `VOLUME_RTOL = 1e-12`) **fails** at 1.4719309093e-07 — which is `budget_check`'s own volume residual — while its per-cell leg stays bitwise equal. Arch reproduced the figure arithmetically from the committed file's own fluxes, `5e-7·flux_baffin/Σflux = 1.4719309086e-07`, agreeing to nine significant figures and exceeding that tolerance by a factor of 147,000.

The overclaim sat two lines from its own refutation: this entry's finding 3 already records that `applied_field_check` has asserted `Σ_c applied·rA == Σ_s flux_s` to 1e-12 on **every dump** since RUNOFF-005.

The accurate standing justification, which `docs/model_contract.md:372-381` already states correctly by class: **no per-cell criterion can see a fraction-sum error, and no other instrument's heat, salt or tracer criterion can** — which is this instrument's real novelty, since nothing else in the project sums those three against a source total at all. `applied_field_check` sees the **volume** leg at the identical figure, consistent with finding 3 that the volume leg is a second independent path rather than new coverage. `refusal_check` is blind **by tolerance** rather than by construction: review B ran its shipped flux-sum criterion against the perturbed run and measured 1.15e-2 against a 1e-6-relative allowance of 7.83e-2, blind by a factor of 6.8.

Adams-Bashforth note (RUNOFF-010 review, 2026-10-03): with forcing inside Adams-Bashforth (`temp_integrate.F:367-372`, `tracForcingOutAB ≠ 1`) the package term is extrapolated like the model's own forcing, so close heat, salt and tracer budgets in the sum over time, or run the check with `tracForcingOutAB=1` or a non-AB scheme.

**Unblocked 2026-10-06:** RUNOFF-013 closed, so the dependency this entry waited on is satisfied. The tendency terms are implemented and measured -- 8 of 8 analytic cases over 10 of 10 decision-3 table rows, every Package figure bitwise zero and the worst Total 1.43e-14 against a 1e-12 acceptance, plus the exf cross-path at 3.559e-16 over 7 cells -- and both acceptance instruments are enrolled in the suites (`tests/rnf/tendency_term_check.py`, `tests/rnf/exf_heat_check.py`). Residual gaps this entry should assume rather than rediscover: every tendency case is single-process, branch N and the lagged time level (`RNF_lagFlds = T`) are executed by nothing, and the tracer term has no numerical oracle. [**Superseded 2026-10-07 by RUNOFF-016:** the last clause no longer holds. `tests/rnf/budget_check.py` compares the applied tracer term against the file's source series per cell (worst 2.499e-16 against a 1e-12 criterion) and as a sum over all cells (2.079e-16). It is still **one** runoff tracer on **one** grid, with `RNF_trPtr`'s multi-tracer mapping unmeasured and no analytic decision-3 row for the term, so treat the gap as narrowed rather than closed.]
**Implemented 2026-10-08 (bob):** `tests/rnf/budget_check.py`, test-only, no model change. Four closures (volume, heat, salt, tracer) summed over every cell of the global layout -- all tiles, all processes, and not only the cells the file names -- against the file's source series, for every record a run applies; enrolled in `focused` (three commands) and `scientific` (one full command plus both controls). Worst residuals, 1e-12 acceptance: volume **0.000e+00** on both grids and all process counts; heat **3.353e-16** (lab_sea, 1 and 2 processes, identical) and **1.444e-16** (cs32, 1 and 4 processes, identical); salt **2.107e-16** everywhere; tracer **2.079e-16** (lab_sea). The tracer term now has a numerical oracle, which closes the residual gap this entry recorded.

Three findings that correct premises in this entry and in the RUNOFF-016 brief, each measured:

1. **A permutation of one source's fractions across its own target cells is provably invisible to a budget, so it cannot be the perturbation that justifies one.** Every right-hand side is weighted by `Sum_c frac_{s,c}`, which a permutation leaves at exactly 1. Measured with `--control permute` (one source's three fractions cyclically shifted): all four residuals **bitwise unchanged** from the unperturbed run, while the per-cell comparison sees 3.333e-01. The acceptance paragraph above asks for "deliberately broken fractions fail them" and the brief named a permutation; a permutation is caught by the *per-cell* oracles (`applied_field_check`, and this check's own per-cell criterion), not by a sum. Arch should decide whether the acceptance wording changes -- that paragraph was not edited here.
2. **The perturbation that does justify the instrument is a fraction sum that is wrong but accepted.** `--control fracsum` scales one source's fractions by 1 + 5e-7, inside `RNF_fracTol` = 1e-6, so `RNF_INIT_FIXED` accepts the file and `RNF_INIT_VARIA` does not even warn (asserted). The four closures then miss by 1.472e-07 (volume), 1.676e-07 (heat), 1.637e-07 (salt) and 1.414e-07 (tracer) -- five orders above the tolerance -- while the per-cell comparison stays at round-off. **Correction, round 1:** I closed this finding with "no other instrument in the matrix can see it", and that is false for the volume leg -- two lines from finding 3, which records the refutation. Review B built the perturbed file and ran `applied_field_check` on it: its applied-volume invariant (`applied_field_check.py:873`, `VOLUME_RTOL` = 1e-12) **fails** at 1.4719309093e-07, the same figure measured here and 147,000 times its tolerance, while its per-cell leg stays bitwise equal with 0 extra and 0 missing over 48 dumps. I reproduced the figure arithmetically from the committed fluxes: 5e-7*flux_baffin/sum(flux) = 1.4719309086e-07, nine significant figures. The accurate statement is about a **class of criterion**: no *per-cell* criterion can see a fraction-sum error, and no other instrument's **heat, salt or tracer** criterion can, because nothing else in the project sums those three against a source total. That is the real novelty and it is enough. Of the rest, only `tendency_term_check` is blind *by construction* -- it writes `frac[:] = 1.0` (`tendency_term_check.py:358`) and its oracle multiplies by a literal `1.0` (`:879`) rather than by the file's fraction -- while `refusal_check` and the `RNF_INIT_VARIA` pair are blind only *by tolerance*, which review B measured at 1.15e-2 against an allowance of 7.83e-2, a factor of 6.8.
3. **The volume closure was already instrumented more widely than this entry and the brief record.** `applied_field_check.check_case` asserts `Sum_c applied*rA == Sum_s flux_s` to `VOLUME_RTOL` = 1e-12 on **every** dump of every case -- lab_sea (1, 2), cs32 (1, 4), `lab_sea_daily`, `lab_sea_hold` and `order_sensitive_sum` -- not only at the start time through `RNF_INIT_VARIA` and `refusal_check`'s control cases. The new check's volume leg is a second, independent path to the same invariant (it reads the dumped field rather than the reconstruction), which is why it is reported as a calibration point rather than as new coverage.

Adams-Bashforth: resolved by **none of the issue's three options**, and measured rather than assumed. The closure reads the `RNFgT`/`RNFgS`/`RNFtrNN` diagnostics where `RNF_TENDENCY_APPLY_*` fills them, which is upstream of `gtForc` and of the extrapolation (`temp_integrate.F:367-372`), so it needs neither a sum over time nor `tracForcingOutAB = 1` nor a non-AB scheme. The `ab_out`/`ab_in` pair measures that: two runs differing only in `tracForcingOutAB` (1 against 0) give **bitwise identical** volume, salt and tracer residuals, and heat residuals of 1.608e-16 against 1.677e-16 -- heat alone reads `theta`, for `T_ref`, and the two runs' states genuinely differ, which the pair also asserts so the insensitivity cannot be vacuous. The state-change form of the budget, which does need the forcing out of AB, remains `tendency_term_check`'s, and that script already refuses a run reporting `tracForcingOutAB != 1`.

Missing-temperature rule: measured, not assumed. `lab_sea_missing` (one source with no temperature in any record, a second with none in one record of an interpolating pair) closes heat at 3.850e-16 with the rule applied and **1.946e-01** with it ignored, and the case fails unless that second figure exceeds 1e-9.

New residual gaps this leaves:
- **The tracer closure runs on one tracer, on lab_sea only.** cs32 does not compile `pkg/ptracers` and giving it the package would change the binary every other committed cs32 oracle is measured through; lab_sea's build has `PTRACERS_num = 1`. So the mapping of several runoff tracers onto several ptracers (`RNF_trPtr`) is unmeasured, and an error that swapped two runoff tracers would not show up. RUNOFF-008's acceptance asks for "budget closure (RUNOFF-016) with at least two tracers" and that half is **not** delivered; it needs a lab_sea build with `PTRACERS_num >= 2`.
- Every case runs with `nonlinFreeSurf = 0` and `select_rStar = 0`, because the model otherwise rewrites `recip_hFacC` at the surface on every step -- the rewrite is guarded by `useLatest .AND. nonlinFreeSurf.GT.0` (`update_surf_dr.F:49`, assigning at `:57`) -- and the run's own `hFacC.data` would not be the thickness the term was divided by. So the budget is **not** closed in branch N or on r*; for cs32 that is a departure from its committed configuration (`nonlinFreeSurf = 4`, `select_rStar = 2`, `useRealFreshWaterFlux = .TRUE.`). **Narrowed in correction round 1 (review A): my first statement of this, that closing it on r* "requires a model change", was overstated.** `hFac_surfC` is an explicit function of the free surface (`calc_surf_dr.F:120-121`) and `ETAN` is a registered diagnostic (`diagnostics_main_init.F:141`), so a test-side reconstruction of the surface thickness is possible, modulo getting the time level right and reproducing the `Rmin_surf`/`hFacInf` clipping (`calc_surf_dr.F:84-98`). What is genuinely absent is a **direct** thickness diagnostic; that is the narrower escalation, and it is a convenience rather than a blocker. `useRealFreshWaterFlux = .FALSE.` is also set but, contrary to what I first wrote, has no bearing on `recip_hFacC` at all: it only reaches the salinity and tracer branch tests (`rnf_tendency_apply.F:298-299`, `:455-456`), which `salt_EvPrRn = 0` and `PTRACERS_EvPrRn(1) = 0` already short-circuit.
- A zero initial temperature, which would have removed `T_ref` from the heat inversion altogether, is not available: MITgcm writes no snapshot of a negative-frequency diagnostic stream at a run's start time, so the first dump of a run from iteration 0 is the second step and its `theta` has already moved (measured: 150 of 320 values away from 0, the largest by 6.0e-2).
- The record *choice* still comes from the run's own `RNF_FIELDS_LOAD` trace, as in `applied_field_check`, so this check cannot see a wrong choice of record. `RNF_lagFlds` remains executed by nothing.

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-08T13:19:08.884967+00:00 for iteration 2026-10-08T00:58:40.965069+00:00. Built tests/rnf/budget_check.py, the budget-closure oracle for volume, heat, salt and tracer, and gave the tracer term its first numerical oracle of any kind. TEST-ONLY: zero diffs under MITgcm/pkg, model and utils across all three rounds. It observes RNF_vflx through EXFroff and recovers the applied property sums from the package's own RNFgT/RNFgS/RNFtr01 diagnostics by undoing the single factor RNF_TENDENCY_APPLY_* applies, with mass2rUnit, delR(1), hFacC and rA all read from the run itself, then sums over every cell of the global layout against the file's source series at the record the run reported. Worst residuals against a 1e-12 acceptance: volume 0.000e+00 on both grids at every process count, heat 3.353e-16 on lab_sea and 1.444e-16 on cs32, salt 2.107e-16, tracer 2.079e-16. No tolerance was widened anywhere. The control that justifies the instrument is a fraction SUM error deliberately inside RNF_fracTol = 1e-6, so RNF_INIT_FIXED accepts the file and RNF_INIT_VARIA does not even warn; the four closures then miss by about 1.5e-07 while every per-cell criterion stays at round-off. Three premises of Arch's brief were refuted by measurement rather than followed: a fraction PERMUTATION is budget-invariant by construction and so cannot be the justifying control, which is the opposite of what the brief said; the volume closure was already asserted per dump by applied_field_check since RUNOFF-005, so the volume leg is a second path rather than new coverage; and Adams-Bashforth needed none of the three options the issue named, because the closure reads the diagnostics upstream of the extrapolation, proven with an ab_out/ab_in pair giving bitwise identical residuals with the two runs' states asserted to differ. Both reviewers approved candidate 8fe7a943 with empty must_fix lists after two correction rounds, every item of which was a statement rather than a design defect.

## 🟢 RESOLVED: the footprint sweep cannot see claims in .py, and that gap has now cost a stale figure

**Date Identified**: 2026-10-07T02:15:00Z
**Status**: Resolved
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
prose, **23 of them the sweep's own `MUST_MATCH`/`KEEP` fixtures**. (Both are
RUNOFF-030 figures, kept here as filed. On today's tree it is 52 and 25,
re-measured in RUNOFF-042 round 0; `tests/rnf/budget_check.py`, added after
RUNOFF-030, is 7 of the 11 difference.)

### Scientific or engineering impact
Bounded but real: a false claim in a test or tool is invisible to the mechanism
built to catch exactly that class, and the project now has one measured instance
of the class escaping. The direct risk is a stale assertion count or a wrong
validity condition in a helper — RUNOFF-040 produced one of each.

### Proposed action and acceptance
Add `.py` to `SUFFIXES` and **exclude the sweep's own file**, without which
triage floods with its 23 fixture lines (measured by review B on RUNOFF-030's
tree; 25 on today's, and see the implementation note below — the volume is not
in the end the reason the file is excluded). Expect the
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

### Measured during implementation (bob, round 0, 2026-10-08)

Three statements above are corrected by measurement; they are left standing as
the issue as filed, with the corrections here.

1. **The Evidence section attributes the escape to the wrong mechanism.** The
   claim at `refusal_check.py:1530` was a *figure* claim ("The four "which
   bounds applied" lines"), and `footprint_claim_sweep.py` cannot see it with
   `.py` in `SUFFIXES` or without: the line carries **no exclusivity marker**,
   so the predicate returns 0 candidates for it either way (measured, both
   scopes, on the exact bytes of commit `4a4add7`). The mechanism a figure
   claim belongs to is `doc_contract.py stale`, which reads the documentation
   inventory — and that inventory **does** cover `.py`: `test_paths` has been
   `["tests"]` since before RUNOFF-040, and the inventory lists this file among
   66 `.py` entries. What missed was the figure *token*: the rows RUNOFF-040
   recorded were `four lines`, `four RNF_SUMMARY lines` and ``four
   `RNF_SUMMARY` ``, and this wording puts the quoted phrase between the number
   and its noun, so none of them matches the `.py` line, while both `.md` twins
   said "four lines" contiguously and were listed and fixed. A row of plain
   `four` matches the line (measured). The same wrong attribution is in
   `devel-loop/loop_state/figures-RUNOFF-040.tsv` and was in the comment at
   `refusal_check.py` itself, which this issue corrected in place.
2. **So the LL-009 demonstration here is a different, real one.** Adding `.py`
   returned 27 candidates outside the sweep's own file, and one was a live
   stale claim of the swept class: `refusal_check.py`'s "A refusal detected on
   one tile only (land, cell area, array bound)" had named three of the
   **five** tile-local checks — RUNOFF-033 added the cell-centre check and
   RUNOFF-040 the per-cell aggregate, and neither was added to the list.
   Corrected, and tied to a mechanical antecedent: the cases carrying a
   `stderr_any` message, which is **seven cases over five checks**, measured
   by *calling* `cases()` with the real lab_sea namelists and `sparse_info()`.
   The planted-mutant demonstration used a footprint-class claim in the same
   file: 0 candidates before the change, 1 after, restored.

   **Corrected in round 1, and the correction is the lesson of this issue.**
   Round 0 wrote "six cases" over four checks, because it enumerated the AST
   for `file_case(...)` calls, and `cell_above_vol_max` is a dict literal at
   `refusal_check.py:1304-1314` that such a walk cannot see. Both reviewers
   found that independently. So the prose "mechanical antecedent" chosen to
   make the list unrottable rotted in the same round, and it had already been
   pinned behind its own `KEEP` entry — `kept()` returned a reason, so the
   default run printed the false line as a keep and `--guards` reported `0 of
   38 needle(s) dead` at exit 0, where neither the triage queue nor guard (2)
   could ever raise it. Round 1 therefore made the tie **executable** rather
   than better worded: `tests/esx/test_instrument_claims.py` asserts the seven
   names and both counts against a real `cases()` call, in `structural`.
3. **The fixture count is 25, not 23** (review B's 41/23 were RUNOFF-030
   figures): 52 new candidates, 25 in the sweep's own file — 8 in `KEEP`, 7 in
   `MUST_MATCH`, 3 in `MUST_MATCH_PATHED` and 7 in prose that quotes an example
   claim to explain the predicate. The volume is not why the file is excluded;
   being quotations rather than claims this project makes is.

Enrolment as settled (Arch's decision, this issue): `--self-test` **and** a new
`--guards` mode, both in `structural`. `--self-test` alone would wire the wrong
alarm, since it never calls `tracked()` or `sweep()` and so cannot see exit 3
or exit 2.

### Measured during implementation (bob, round 1, 2026-10-08)

4. **Scan scope narrowed, measured:** `ESX-team-local/backups/` is excluded
   (`EXCLUDED_PREFIXES`). It held **79** of the swept files — 61 of the 126
   `.py` this issue added, plus 18 `.md` swept since RUNOFF-030 — all vendored
   pre-upgrade snapshots of the ESX kit, which this project may not edit, so a
   candidate there would be unactionable and a kit upgrade could turn
   `structural` red over a file we do not own. The 79 produce **0** candidates
   today, so the swept figure went 293 → **214** with candidates, keeps and
   all three guards unchanged (95 / 38 / exit 0). `tools/esx/` (35 files) is
   kept in scope, because this project edits it constantly; the asymmetry with
   `doc_contract.stale_lines`, which skips `tools/esx/`, is deliberate and
   recorded in the constant's own documentation.
5. **Arch's round-1 figure of "61 of 126" is right about the `.py` share but
   understates the exclusion:** dropping the prefix removes **79** files,
   because 18 non-`.py` files under it were already swept before this issue.
   Recorded rather than quietly adjusted.
6. **The exposure claim was overstated and is now named:** `KEEP` is 38
   needles over 13 paths, of which **12 paths / 37 needles** are in the
   acceptance set (`project.py acceptance-scope`, per path) and **0 of 13** are
   records. The exception is `MITgcm/doc/phys_pkgs/exf.rst`, the one path where
   the reason the exposure is acceptable — an edit obliges a re-seal anyway —
   does not hold.
7. **`docs/verification_matrix.md`'s twin of the corrected claim** ("Land, cell
   area and array bounds are seen by the process that owns the tile only") was
   the same stale three-item list and is corrected in the same round;
   `candidate()` returns `False` on that line, so the sweep would never have
   watched it.
8. **Carried fix, discharged:** the *Target cell centres* row said two
   distinct centres are "at least" `0.5*(s_from + s_to)` apart where
   `MITgcm/pkg/rnf/RNF.h::<module>` says "about" with the reason — and the row
   refuted its own claim later in the same line. Corrected, and the forward
   note in `lessons_learned_evidence.md` (LL-015) is marked discharged.

### Resolution 2026-10-08 (RUNOFF-042)

Delivered in `caa6c92`, both reviewers approving on candidate `31442c39` after
one correction round; final scientific qualification `EXECUTED PASS`, receipt
`74616934`, 62 commands, exit 0, stable, 6467 s.

**The filing premise above is false, and it was Arch's.** The Evidence section
says the RUNOFF-040 claim survived "precisely because the sweep does not scan
`.py`". Measured three ways and confirmed by review A on the bytes at
`dbc50fd^`: that line carries no exclusivity marker, so `candidate()` returns
`False` for it with `.py` and without, and `candidate()` takes no suffix
argument at all. The footprint sweep could never have caught it. The
stale-figure mechanism had covered `.py` all along —
`tests/rnf/refusal_check.py` is one of 66 inventoried `.py` files and
`test_paths` has been `["tests"]` since before RUNOFF-040. The real escape was
the figure **token**: the rows recorded were `four lines` and kin, while the
`.py` line reads `four "which bounds applied" lines`, so none matched
contiguously, while both `.md` twins did say `four lines` and were caught.
RUNOFF-040's review B measured something true and attached an inference; Arch
relayed the inference into this Evidence, the design and the brief, where it
became a requirement. `TEAM-ARCH-UNVERIFIED-CLAIM-001`, instance twelve.
`figures-RUNOFF-040.tsv` is corrected.

**So acceptance item 1 was void and the change had to earn its keep on what it
caught.** It did: the paragraph at `tests/rnf/refusal_check.py` had named three
of four tile-local checks since RUNOFF-033, and review A confirmed it genuinely
stale, genuinely of the swept class, and watched by nothing else.

**Then the correction repeated the error class it was correcting**, which is
LL-019. `cases()` returns seven cases over five checks, not six over four;
`cell_above_vol_max` is a dict literal at `refusal_check.py:1304-1314` that the
AST walk producing the figure could not see. Worse, the correction was
registered as a `KEEP` entry, so the sweep printed it as a keep and `--guards`
reported `0 of 38 needle(s) dead` at exit 0 — the instrument built to find
stale claims had put one beyond its own triage queue and guard. Both reviewers
found it independently; nothing mechanical would have.

**Delivered.** `.py` in `SUFFIXES`; the sweep's own file excluded whole (all 25
of its hits are quotations of example claims); `ESX-team-local/backups/`
excluded; `KEEP` 11 → 38 entries over 13 paths; `--self-test` and a new
`--guards` mode enrolled in `structural`; a route in `docs/code_map.md`, which
had none; and the claim made executable in
`tests/esx/test_instrument_claims.py`, which fails in both directions. 214
files swept at the reviewed candidate, 95 candidates, 57 to triage,
`--self-test` unmoved at 8 of 8 / 0 of 3, `refusal_check.py` 69 of 69 in the
final run.

**Two further Arch figures corrected by the people doing the work.** The
backups exclusion drops 79 swept files, not the 61 claimed — 61 `.py` plus 18
`.md` swept since RUNOFF-030 — so as stated it shrank coverage by more than was
justified; verified to lose zero candidates (95 before and after), with no
`KEEP` path or needle under the prefix and a planted one failing loudly at exit
3. Review B judged the whole-prefix exclusion right anyway, since "vendored,
frozen, not ours to edit" is a property of the directory, not the suffix. And
four of the `six cases` lines Arch flagged were unrelated figures.

**Workflow amended at closeout.** Arch prepared this as `harness_change`; the
gate refused, because `source_signature(scientific=True)` moved and four
committed paths are in the 272-path scientific inventory. Anything under
`tests/` or in `esx/project.json` lands there, so the brief's "test/tooling
change only" could never have been `harness_change`. The amendment is recorded
with its measurement, and the qualification it forced earned its cost: nobody
ran the focused suite this iteration, so `refusal_check.py` passing had rested
on an AST-identity measurement until this run executed it.

**Residual, all measured.** The guard fires on the next added *case*, not the
next added *check*: `pkg/rnf` has seven tile-local refusal paths, and
`refuse = 2` (`maskInC == 0`) and `refuse = 3` (`kTopC /= 0`) have no case at
all — zero of the 69 mention them — which belongs to RUNOFF-019 and RUNOFF-020
rather than to a new issue. `CHECK_CASES` compares only the union and the group
count, so swapping its label-to-case mapping keeps the test green (one
per-group assertion closes it). `stderr_any` is an optional kwarg, so a case
writing its owner-only message in `stderr` is invisible to `measured()`, and
only `refusal_check.py --mpi 2` would catch that — a `scientific`-only command.
Guard (1) makes a scope shrink loud only where a needle lies under the excluded
path, and `report()` names neither the exclusions nor their size, so what makes
the backups exclusion safe is the 0-candidate measurement, not the guard.
`EXCLUDED_PREFIXES` is applied only to the project-repo leg of `tracked()`. The
swept figure is 214 for the reviewed candidate and 215 once this round's new
test file is tracked, recorded in `figures-RUNOFF-042.tsv` rather than
corrected in the acceptance set, which would have stranded both approvals.

## 🟢 RESOLVED: Passive-tracer runoff contributions (ptracers tendency term)

**Date Identified**: 2026-09-29T21:30:00Z
**Date Resolved**: 2026-10-09T19:03:30.131124+00:00
**Status**: Resolved
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

Carry forward from RUNOFF-013 (review B, correction round 1, 2026-10-05): **a numerical oracle for the tracer term is the main thing RUNOFF-013 leaves here.** RUNOFF-013 enrolled `refusal_check.py --case ptracer_match`, which is the only configured run that reaches `RNF_TENDENCY_APPLY_PTR`; it asserts that the routine runs, that the match is reported (`runoff tracer 1 is runoff_ptracer_dye, applied to ptracer 1`) and that `RNF_nTrUse = 1`, but **nothing compares the number the term applies**. [**Superseded 2026-10-07 by RUNOFF-016:** `tests/rnf/budget_check.py` now does, per cell at 1e-12 (worst 2.499e-16) and as a sum over all cells against `rhoConstFresh*Sum_s flux_s*C_s` (2.079e-16), on lab_sea with one real passive tracer. What this paragraph asks for that is still missing is the **analytic** oracle -- a decision-3-style row per reference branch -- and the two-tracer case; see the status note below.] The T and S terms by contrast have two oracles each in `tests/rnf/tendency_term_check.py` (the `RNFgT`/`RNFgS` diagnostic and the two-run `TOTTTEND`/`TOTSTEND` difference). The cheapest route is to extend `tendency_term_check.py`, which already has the machinery: the `RNFtrNN` diagnostic is registered, `PTRACERS_EvPrRn`/`PTRACERS_ref` give the same three reference-value branches as salinity, and the two-run difference needs a `TOTPTEND`-equivalent or the ptracer state dumps. Acceptance as above, plus the `RNFtr01` diagnostic matching the analytic `[(mC) − m·C_ref]·mass2rUnit·D` to 1e-12 relative on at least one case per reference branch. [**2026-10-09, RUNOFF-008:** "the only configured run that reaches `RNF_TENDENCY_APPLY_PTR`" and the 2.499e-16/2.079e-16 above are history: every `tendency_term_check.py` case and every lab_sea `budget_check.py` case now reach it, and those two figures are 2.667e-16 and 1.962e-16 on the non-degenerate tracer series. See the 2026-10-09 status below.]

**Status against that acceptance, 2026-10-07 (RUNOFF-016, bob).** The acceptance sentence above is unchanged; this is only a record of which of its clauses now have evidence. LANDED: "budget closure (RUNOFF-016)" for **one** tracer -- `tests/rnf/budget_check.py` closes `Sum_c (mC_n)(c)*rA(c) = rhoConstFresh*Sum_s flux_s*C_{s,n}` at 2.079e-16 and the per-cell field at 2.499e-16 (historical figures of the degenerate series; 1.962e-16 and 2.667e-16 since RUNOFF-008, see the 2026-10-09 note), on lab_sea, single process and 2 processes, at every record of an interpolating file. NOT LANDED: "with at least two tracers" -- lab_sea's build has `PTRACERS_num = 1` and cs32 does not compile pkg/ptracers, so `RNF_trPtr`'s mapping of several runoff tracers onto several ptracers is unmeasured and a swap of two runoff tracers would not show up; it needs a lab_sea build with `PTRACERS_num >= 2`. ALSO NOT LANDED: the "analytic single-cell tracer budget" and the per-reference-branch `RNFtr01` comparison, which are `tendency_term_check`'s shape of evidence and remain unwritten -- a budget closure is not an analytic row. One further limit a future implementer should know: the single tracer series `budget_check` writes gives sources `newfound` and `baffin` identical values at every record, so that oracle cannot distinguish those two sources from each other.

**Status against that acceptance, 2026-10-09 (RUNOFF-008, bob).** The acceptance sentence is unchanged; this records each clause. The 2.079e-16 and 2.499e-16 of the 2026-10-07 note are historical: on the series below they are 1.962e-16 and 2.667e-16. Test-only, no Fortran change.
- **Analytic single-cell tracer term, per reference branch, 1e-12: LANDED.** `tests/rnf/tendency_term_check.py` carries one passive tracer in all 8 cases and a table `C_ROWS` of four rows (`PTRACERS_EvPrRn` set or unset, branch L or U); `main` fails if one has no passing case. Package column: `RNFtr01` against `[(mC) − m·C_ref]·mass2rUnit·D` with the local tracer read from the run's own `PTRACER01` dump, measured 0.00e+00 on every case. Total column: the two-run difference of `Tp_gTr01`, measured at most 1.68e-15. Which quantity is the total was measured on retained runs: lab_sea compiles pkg/longstep, which takes the ptracer step over and sets the tracer's surface forcing in `LONGSTEP_FORCING_SURF` (`pkg/longstep/longstep_forcing_surf.F`) rather than `PTRACERS_FORCING_SURF`; with `LS_nIter = 1` the `Tp_gTr01` snapshot labelled 1 holds the second step and equals `(C^2−C^1)/dt` from the state dumps to the last bit, and `ForcTr01` matches the analytic total to 0.0. The model's own share follows the longstep routine, which has the same three arms as the ptracers one with `EmPmR` replaced by its one-sample long-step average. Initial tracer 0.75, `PTRACERS_ref` 0.25, `PTRACERS_EvPrRn` 1.25 and source tracer 3.0/0.5 are distinct; the measured package term is at least 8.3e-2 away from the term of every other reference. Both columns were measured failing on mutant binaries: branch-L arm using `PTRACERS_ref` fails `L_unset` at 2.222e-01; the applied term's sign flipped leaves the package column at 0.00e+00 and fails the total at 1.27 to 2.00. Adding pkg/ptracers left every T and S figure of all 8 cases bitwise unchanged. Branch N stays with RUNOFF-014. Limit: in the two local-arm rows the tracer at the cell is still exactly 0.75 when the step starts, so they cannot tell the step's local tracer from the initial one. Focused runs `L_set`, `U_set`, `L_unset`, `U_unset`, which cover C3/C1/C2/C4 (`--case L_unset --case U_unset` added for that).
- **Budget closure with at least two tracers: LANDED.** `budget_check.py --build` compiles `build_esx_ptr2` (lab_sea `code/` plus `PTRACERS_SIZE.h` with `PTRACERS_num = 2`, written by `write_ptr2_code`; `lab_sea/code` is not edited). Case `lab_sea_ptr2` feeds ptracers `rnfa`, `rnfb` from variables in the opposite order; new per-ptracer closures read `ForcTrNN` (what each ptracer received), because the `RNFtrNN` closures are blind to `RNF_trPtr` (the diagnostic is named and filled per runoff tracer). Measured: all four tracer closures 1.962e-16 to 2.170e-16, runoff tracer 1 matching ptracer 2. `--control swap` (names exchanged, data kept) leaves `RNFtrNN` at round-off and fails the ptracer closures at 5.002e-01 and 3.334e-01; an identity-mapping mutant gives the same two figures. The series degeneracy is removed: every (record, source, tracer) value is distinct and the tracers are not proportional, asserted in `series()`.
- **A tracer missing from the file adds nothing: LANDED.** Case `lab_sea_unfed` feeds only `rnfa`; `rnfb` (`PTRACERS_ref` 0.5, `PTRACERS_EvPrRn` unset) must have `ForcTr02` exactly 0 everywhere and a state bitwise equal to a run with no tracer variable: measured 0 and 0. `--control feed_zero` (a zero-valued `rnfb` variable, so the package applies `−m·C_ref`) fails both legs (6 dumps, 676 values). A mutant applying the term to every unfed ptracer is caught by the forcing leg (3.4e-08) and missed by the state leg, whose reference run shares the binary; the forcing leg is the decisive one, and the docstring says so.
- **Unknown tracer name refused at init: LANDED earlier** (`refusal_check.py --case ptracer_unknown`, RUNOFF-013).
- **Ambiguous name (one variable matching two `PTRACERS_names`): reachable, measured once, not enrolled.** On `build_esx_ptr2` with `useMNC = .FALSE.` the run stops with `the name matches   2 PTRACERS_names entries`; with lab_sea's `useMNC = .TRUE.` pkg/mnc refuses the duplicate name first. `refusal_check.py` runs every case on one binary chosen by `--mpi` and is enrolled without `--build`, so the case does not fit it cleanly; left recorded (and in the RUNOFF-013 carry-forward of the entry above).
- **No-change runs unchanged: holds by construction**, since no Fortran changed; the existing configured experiments are the evidence.
- **Iteration state, 2026-10-09 (Arch):** reviewed (review A approves, no must-fix) and committed (`8c9837f`), closed out as **partial**: final verification has not run, because both configured suites start with `pytest -q tests/runoff`, which cannot pass while `envs/ecco` (replaced 2026-10-08 19:43 by Python 3.14.7) lacks matplotlib. Owner decision pending. Next: re-prepare, confirm the candidate is unchanged (`61feac9a`), and run `final_verification.py` as arch. Review A's pkg/longstep finding is RUNOFF-043.
- **Interpreter resolved, 2026-10-09 (Arch, `c68788d`):** the project now runs on the dedicated `envs/mitgcm_rnf` (Python 3.14.7 plus matplotlib). The same minor version as the seal, so the seal's Python digests are unaffected. The repoint edited four acceptance-scope files (`esx/project.json`, `esx/project_profile.md`, `CLAUDE.md`, `docs/code_map.md`), so Bob's sealed report `af354f05…` is now **stale** and the candidate moved from `14406b8a…` to `cb41a501…`. **Next, in order:**
  1. Re-prepare RUNOFF-008 as `scientific_change`.
  2. Correction round 1 with the same identities. Bob `a23fa823c56a8ffb7` reseals with `doc_contract.py draft --previous af354f05…`, giving the four files their own dispositions; there are no test or Fortran changes. Richard `ad98e39fd4b872093` re-confirms only the changed lines and the new seal.
  3. Build a fresh review packet, then run `final_verification.py` as arch with Bash `run_in_background`. This is the first live test of TEAM-LOOPHOLD-NO-RELEASE-001: the loop must resume within minutes of the suite finishing.
- **Correction round 1 and final verification, 2026-10-09 (Arch):**
  - Neither native subagent of the ended session was resumable. Replacement Bob `ad208460ccaf86130` resealed the report (`0c8886e4…`).
    - The candidate signature is `c8e6be78…`, not `cb41a501…`: the owner's "don't ask again" approval added one allow rule to `.claude/settings.local.json`, which lies inside the acceptance scope (TEAM-SETTINGS-LOCAL-IN-ACCEPTANCE-001).
  - Replacement Richard `a0199106f3c3c2fc8` confirmed the seal: APPROVE_WITH_FIXES, empty must-fix.
    - His own focused run passed 13/13, and all 89 round-0 figure lines reproduce verbatim.
    - An A/B of seven tendency and budget measurements, envs/mitgcm_rnf against the 3.10 stack of ecco_py310 (used read-only, not modified), gave 2004 floats bitwise identical.
  - Final verification by Arch, packet `packets/runoff-008-final.json`: **EXECUTED PASS**, 09:40–11:53 -0700.
    - Receipt `final-verification/4a411df2…`.
    - This was the first live final verification of the pilot. The session was re-invoked at the moment the suite finished, so TEAM-LOOPHOLD-NO-RELEASE-001 holds in practice.
  - The owner's 2026-10-09 decision on RUNOFF-031 will move this term, for surface targets, to `surfaceForcingPTr`. This issue's oracles are the regression witnesses for that move.
- Enrolment: focused `tendency_term_check.py --case L_set --case U_set --case L_unset --case U_unset`; scientific `budget_check.py --build` (now including `lab_sea_ptr2` and `lab_sea_unfed`) plus `--build --case lab_sea_ptr2 --mpi 0 --control swap` and `--build --case lab_sea_unfed --mpi 0 --control feed_zero` (62 → 64 commands). Not covered: two tracers on MPI (no `_mpiN` build of it), cs32 (no pkg/ptracers), branch N, tracer series in time modes other than this fixed period (RUNOFF-029).

### Gate acceptance

Accepted by `loop_gate.py --check-done` at 2026-10-09T19:03:30.131124+00:00 for iteration 2026-10-09T15:32:16.031263+00:00. Test/oracle change, no Fortran (8c9837f), now final-verified. RUNOFF-008 acceptance delivered: analytic tracer rows C1-C4 in tendency_term_check (PTRACERS_EvPrRn set/unset x branch L/U; Package RNFtr01 0.00e+00, Total two-run Tp_gTr01 <=1.68e-15); two-tracer budget on a PTRACERS_num=2 lab_sea build (per-ptracer ForcTrNN closures 1.962e-16..2.170e-16, swap control fails at 5.002e-01/3.334e-01); non-degenerate tracer series; missing-tracer oracle lab_sea_unfed with feed_zero control; unknown name refused (RUNOFF-013). Correction round 1 resealed the documentation after the interpreter repoint c68788d (seal 0c8886e4, candidate signature c8e6be78); replacement Richard confirmed (APPROVE_WITH_FIXES, empty must-fix; focused 13/13; 2004 floats bitwise identical across Python stacks). Final verification EXECUTED PASS (receipt 4a411df2), 09:40-11:53 -0700.
