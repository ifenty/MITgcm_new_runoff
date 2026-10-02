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
