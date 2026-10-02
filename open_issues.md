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

## UNRESOLVED: ESX runtime hook makes every retained-agent Bash call require approval

**Date Identified**: 2026-09-29T22:20:00Z
**Status**: Unresolved
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

## UNRESOLVED: ESX dispatch adapter crashes on Claude Code permission_denied events

**Date Identified**: 2026-09-29T22:05:00Z
**Status**: Unresolved
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

## UNRESOLVED: Python dense-to-sparse runoff converter

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
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

Unblocked 2026-09-30: RUNOFF-001 closed; schema 1.0 is approved (docs/runoff_schema.md), and MITgcmutils.runoff.check validates files against it.

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

## UNRESOLVED: exf sparse runoff reader, per-tile lists and global fraction check

**Date Identified**: 2026-09-29T21:30:00Z
**Status**: Unresolved
**UUID**: RUNOFF-004
**Anchors**: MITgcm/pkg/exf/exf_readparms.F::<module>; MITgcm/pkg/profiles/profiles_init_fixed.F::<module>

### Issue or research question
Implement init: new `data.exf` parameters, a master-thread NetCDF read of the static arrays, the global index → local `(i,j,k,bi,bj)` mapping on every grid (including exch2/LLC and blank tiles), per-tile source lists, a `GLOBAL_SUM` fraction check (1e-6), and refusal of a land cell, an unknown tracer, or sparse + dense both set. Then fill `runoff` = Σ flux·frac/rA.

### Evidence
Design decisions from the project owner, recorded in `esx/project_profile.md` and `docs/model_contract.md` (2026-09-29). No code exists yet.

Design requirement (2026-09-30): map `target_cell` to owned points with the same arithmetic `pkg/mdsio` uses to place tile rows in a global file (`mdsio_write_field.F:445-480`: `tBx`/`tBy` from `myXGlobalLo`/`myYGlobalLo` or `exch2_txGlobalo`/`exch2_tyGlobalo`, plus the `iGjLoc`/`jGjLoc` fold cases), not a rectangular box test. Under compact `W2_mapIO` (0 or > 0) or when a face is wider than the global array, tile rows are folded or strung into a line (`w2_set_map_tiles.F:189-203`). Test cases: cs32 with `W2_mapIO = -1` (verified by Richard B for the flattened index) and a compact `W2_mapIO` layout.

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
