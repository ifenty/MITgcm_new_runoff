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

## UNRESOLVED: Define the sparse-runoff NetCDF schema

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-001
**Anchors**: docs/model_contract.md#input-one-netcdf-file-per-run-phase-1; tests/mitgcm_oracle.sh::<module>

### Issue or research question
The file layout isn't defined. Needed: dimension and variable names, the id string type, the (source, cell) pair layout, CF time attributes, the attribute names for timing settings that `data.exf` can override, and a grid-identity record so the model refuses a mismatched file. Also confirm three proposed rules: a fill value in the flux is an error, several sources in one cell combine temperature flux-weighted, and one-record chunking.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

### Scientific or engineering impact
Every later issue (converter, reader, timing) depends on this layout. It also sets I/O cost at the 2 km scale.

### Proposed action and acceptance
Write the schema into `docs/model_contract.md`, with an example `ncdump -h` and one tiny example file. Acceptance: the owner approves the schema. It must support per-record contiguous reads (`time` slowest) and yearly `_YYYY` files.

## BLOCKED: Python dense-to-sparse runoff converter

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-001 — the converter must write the approved schema
**UUID**: RUNOFF-002
**Anchors**: docs/model_contract.md#input-one-netcdf-file-per-run-phase-1; docs/verification_matrix.md#scientific-qualification-matrix

### Issue or research question
A tool is needed that reads a dense MITgcm runoff binary (m/s, any grid layout), the grid (`rA`, surface mask) and timing, and writes schema-conformant NetCDF. Flux in m³/s is rA·runoff; each nonzero cell becomes a one-cell source, or cells are grouped with fractions.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

### Scientific or engineering impact
This produces the oracle inputs for every sparse-vs-dense test.

### Proposed action and acceptance
Put the tool under `tools/runoff/`, with pytest tests under `tests/`. Acceptance: the dense→sparse→dense round-trip reproduces cs32 `core_rnof_1_cs32.bin` and the lab_sea dense files exactly (`float32`), fractions sum to 1 within 1e-6, and no source targets a land cell.

## UNRESOLVED: lab_sea dense-path runoff reference runs

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
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

## BLOCKED: exf sparse runoff reader, per-tile lists and global fraction check

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Blocked
**Blocked-By**: RUNOFF-001 — the reader must implement the approved schema
**UUID**: RUNOFF-004
**Anchors**: MITgcm/pkg/exf/exf_readparms.F::<module>; MITgcm/pkg/profiles/profiles_init_fixed.F::<module>

### Issue or research question
Implement init: new `data.exf` parameters, a master-thread NetCDF read of the static arrays, the global index → local `(i,j,k,bi,bj)` mapping on every grid (including exch2/LLC and blank tiles), per-tile source lists, a `GLOBAL_SUM` fraction check (1e-6), and refusal of a land cell, an unknown tracer, or sparse + dense both set. Then fill `runoff` = Σ flux·frac/rA.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

### Scientific or engineering impact
This is the core feature. Mapping errors silently lose mass.

### Proposed action and acceptance
Acceptance: the lab_sea constant case, sparse = dense, single-process and MPI; the negative tests stop with the expected messages; all no-change experiments pass.

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
Proposal: fill new 2D exf fields (runoff salinity, runoff tracers) as flux-weighted means per cell, and add their contribution where exf and ptracers apply freshwater. Owner to confirm the approach. Acceptance: a budget check (Σ S·flux) and no-change runs unchanged.
