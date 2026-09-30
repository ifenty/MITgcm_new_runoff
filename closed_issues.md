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
