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
