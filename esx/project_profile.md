# Project profile

This is the scientific contract agents read. Executable paths and commands are in
[project.json](project.json). The design reference is
[the model contract](../docs/model_contract.md). The test plan is
[the qualification matrix](../docs/verification_matrix.md).

## Mission and scope

- Project name and identifier: MITgcm new runoff (`MITGCM-NEW-RUNOFF`).
- Scientific question or engineering outcome: add a sparse, source-based way to
  specify runoff forcing in MITgcm, as a new package `pkg/rnf` that feeds exf's
  `runoff` field (design: [package design](../docs/package_design.md), RUNOFF-010). Runoff is a volumetric
  water flux, optionally with temperature, salinity (default 0, i.e. freshwater) and
  any number of passive tracers. It is read from NetCDF organized by source.
  - **Current approach:** a dense `runoffFile` with one value per surface cell per
    record. This is wasteful at high resolution, because nearly every cell is zero.
    It is also opaque: you can't tell which river or glacier feeds which cell.
- Intended users and decisions the results will support: MITgcm users forcing
  high-resolution ocean models with river and glacier discharge. The main use case
  is daily runoff for 50 years at every coastal cell of a global 2 km model. The
  feature is intended for an upstream PR to MITgcm/MITgcm.
- **Owner direction, 2026-10-02 (owner away for several days):**
  - Develop and test the runoff program as a robust, versatile, documented new MITgcm package that follows MITgcm coding standards.
  - Test it in many verification configurations: regional and global; lat-lon, cubed sphere and LLC; with and without sea ice, ice shelves and open boundaries.
  - Cover all time modes (constant, daily, monthly, monthly climatology, yearly files), each with and without temperature, salinity and tracer contributions.
  - T, S and tracer input uses the shelfice/icefront tendency-term pattern.
  - Plan the work as RUNOFF-010 to RUNOFF-029 and file new issues as needed.
  - Subsurface discharge (RUNOFF-025) is now in scope. Opening the upstream PR still requires explicit owner approval.
- In-scope deliverables and explicit exclusions:
  - **Phase 1 deliverables:**
    - 2D (surface) sparse runoff in the new package `pkg/rnf`, feeding exf
    - a Python dense→sparse NetCDF converter
    - lab_sea and cs32 oracle tests
    - exf documentation
  - **Excluded from phase 1:** 3D/subsurface runoff via `addMass`, more than one
    runoff file, and adjoint tests. These are in [long-term goals](../long_term_goals.md).
    Phase 1 must not design them out.
- Completion criteria for this deployment:
  - Sparse runoff reproduces the dense-path results on
    `global_ocean.cs32x15` (`input.icedyn`, `input.seaice`) and on the new lab_sea
    cases, single-process and MPI — but **by the instrument appropriate to each
    case**, revised 2026-10-05 on RUNOFF-005 measurements (below). For a constant
    record the dense reference itself is the oracle. For a *timed* case it is the
    applied-field and record-selection comparison, because the digit threshold is
    unachievable there in principle: see the tolerance rationale.
  - The hold-exact mode passes its direct check.
  - All no-change experiments still pass.
  - The MITgcm contribution checks pass (below).

## Scientific and numerical contract

- Model equations, approximations, discretization and applicable scales: for each
  source `s` and target cell `c` on a tile:
  - `runoff(c) = Σ_s flux_s(t) · frac_{s,c} / rA(c)`, in m/s.
  - `flux_s(t)` is in m³/s, and `rA` is the cell area.
  - Only the flux is split by fraction. A source's T, S and tracer concentrations
    apply unchanged to every cell it feeds.
  - Where several sources feed one cell, volumes add, and T, S and all tracers
    are flux-weighted means. This conserves heat, salt and tracer content.
  - The volume goes through exf's `runoff` array, so the downstream exf/model
    physics (`pkg/exf/exf_mapfields.F`) is unchanged. T, S and tracers enter as
    tendency terms (shelfice/icefront pattern); see the package design.
- Inputs/outputs, dimensions, units and coordinate/reference conventions: one
  NetCDF file with:
  - source ids (alphanumeric)
  - (source, cell) pairs, where each cell is a 0-based global index
  - fractions
  - a time series per source on one shared time axis: flux in m³/s (required),
    temperature in °C, salinity (default 0), and tracers matched to ptracers by
    name
  - `float32` storage allowed

  Details are in [the model contract](../docs/model_contract.md).
- Grid topology, masks, boundaries and exchange conventions:
  - Must work on every MITgcm grid: Cartesian, lat-lon, cubed-sphere (exch2) and
    LLC, including exch2 blank tiles.
  - A global cell index is a cell's 0-based position in the flattened global 2D
    layout of a dense `runoffFile` on that grid.
  - At init, each tile converts its indices to local `(i,j,bi,bj)`. In phase 1
    every target is the column's surface cell (level 1 in z coordinates, `Nr` in
    pressure coordinates, `kSurfC` under shelfice); targets under an ice shelf are
    refused until the `addMass` path exists (RUNOFF-025).
  - Each tile stores only its own cells.
  - A target cell on land (surface `maskC` = 0) is a fatal error that names the
    source.
- Calendar, time alignment, sampling and missing-data semantics:
  - **Time axis:** a CF-style `time` variable (`units = "days since …"`, plus a
    `calendar` attribute). Sampling is constant, repeating (climatology) or
    non-repeating, at hourly, daily, monthly (calendar months) or yearly intervals.
  - **Timing overrides:** runtime timing settings come from file attributes or
    `data.rnf`, and **`data.rnf` overrides the file**.
  - **Yearly files:** `_YYYY` files follow exf `useExfYearlyFields`.
  - **Interpolation:** chosen in `data.rnf`, either exf-style linear interpolation
    or hold-exact.
  - **Missing temperature:** runoff enters at the surface water temperature, as
    exf does now.
  - **Missing values** (owner decision, 2026-09-29): not allowed in the flux. A
    missing or fill value in the flux stops the run with an error naming the
    source and time.
- Conserved quantities, positivity, symmetry, monotonicity or other invariants:
  - Each source's fractions sum to 1 across the whole domain, within 1e-6. This is
    checked with `GLOBAL_SUM` over all tiles and processes. Land, open-boundary
    and off-grid targets are caught by the init checks of the package design
    (decisions 5 and 6: `maskC`, `maskInC`, index range); a target on a blank
    tile is owned by no tile and shows up as a fraction deficit.
  - Total applied volume flux, `Σ runoff·rA`, equals `Σ_s flux_s(t)`.
  - Heat, salt and tracer input (`Σ F_c·X_c`) equals `Σ_s flux_s·X_s`.
  - Fractions are ≥ 0.
  - With the feature compiled in but not used, results are bit-for-bit unchanged.
- Parameters, control variables, objectives and statistical estimands: new
  `data.rnf` namelist parameters (file name, interpolation mode, timing overrides).
  Code stays TAF-friendly because exf runoff is a control variable in ECCO setups.
  There are no statistical estimands.
- Acceptable error, oracle uncertainty and tolerance rationale:
  - **Dense-vs-sparse oracles, constant record:** match the dense reference
    `output.txt` to the `compare_results.sh` / testreport digit threshold. The
    expected difference is round-off from `flux·frac/rA` versus the precomputed
    dense m/s value. `lab_sea/input.rnof_sp_const` and
    `cs32/input.rnof_sp_icedyn` meet this; their references are byte copies of
    their dense twins, so these two cases carry the whole-model-response
    cross-path evidence.
  - **Dense-vs-sparse oracles, timed cases:** the digit threshold is
    **unachievable in principle** and is not the instrument. Measured on
    RUNOFF-005 (2026-10-05) and confirmed independently by review A: the
    dense-versus-sparse forcing difference is at most **1 ulp** (max 2.0e-16, with
    ~88% of values bitwise identical and identical non-zero cell sets in every
    record), yet lab_sea amplifies that round-off seed so `cg2d_init_res` reaches
    only 4, 16, 3, 16 and 4 matching digits for daily, month, month1, clim and
    yearly against the 10 required. Review A's decisive check: perturbing every
    `runoff_flux` by exactly one ulp and changing nothing else collapses the same
    case from 16 digits to 4 — so the figure is amplification, not a defect.
    - `month` and `clim` do in fact meet the digit criterion, at 16 digits, being
      numerically identical to their dense runs in every monitor variable. Only
      `daily`, `month1` and `yearly` cannot.
    - The instrument for the timed cases is therefore
      `tests/rnf/timing_field_check.py` (the dense run's applied `EXFroff` against
      the sparse run's, cell by cell at every step, 1e-12, measured 3.7e-16 to
      4.3e-16) together with
      `tests/runoff/lab_sea_runoff_timing_check.py` (record choice against pkg/exf's
      own conventions, 0 of 49-1465 steps disagreeing). Each timed case also carries
      its **own** sparse-path reference as a regression guard; that reference is not
      a cross-path test, and it is labelled as such in the matrix.
    - **Known weakness of the replacement:** the digit oracle compared the whole
      model response; this chain compares the runoff field and the record choice. A
      `pkg/rnf` side effect outside the exf `runoff` array specific to the timed
      path would be invisible to all three instruments. That coverage survives only
      in the two constant cases above.
  - **Fraction sum:** within 1e-6.
  - **No-change experiments:** must be identical.
- Invalid input, unsupported cases and required failure behavior: stop at init
  with an `RNF`-prefixed error naming the file, variable or source id for any of
  these:
  - fraction sum out of tolerance
  - target cell on land or off the grid
  - tracer name with no matching ptracer — **implemented in RUNOFF-013**, in
    `RNF_NC_SERIES` (`rnf_nc_utils.F:660`), which stops naming the variable and
    listing the `PTRACERS_names` of `data.ptracers` it was matched against; a
    file carrying runoff tracers while `pkg/ptracers` is not in use is a
    separate stop at `rnf_nc_utils.F:637`. Both line numbers are the enclosing
    `IF` and resolve against fork commit `6aa841e2e`. Both are measured by
    execution
    (`refusal_check.py --case ptracer_unknown --case ptracer_off`, with
    `ptracer_match` and `ptracer_ignored` as the must-run controls). This entry
    was moved here from RUNOFF-004 on 2026-10-04 because matching to ptracers
    belongs with the tendency term that consumes it; the RUNOFF-004-era warning
    walk it describes was replaced by this refusal and no longer exists.
    `RNF_NC_SERIES` has five more refusals around the same matching, of which
    three were enrolled in correction round 1 (`ptracer_name_empty`,
    `ptracer_name_long`, `ptracer_too_many`, each measured passing on the
    committed build and failing on a mutant with its guard weakened).
    Correction round 2 added the complementary **at-the-bound**
    counterfactuals of those three (`ptracer_name_min` with a 1-character
    name, `ptracer_name_max` at exactly `RNF_idLen` = 64 and
    `ptracer_count_max` with exactly `RNF_nTr` = 5 tracer variables): each
    must get past the guard and be refused by the `usePTRACERS` test that
    follows it, naming the variable, which is what holds a `.GT.` back from
    becoming a `.GE.` — the direction a weakened-guard mutant cannot
    measure. The two refusals that remain unenrolled need another build: a name matching more than one
    `PTRACERS_names` entry, which needs `PTRACERS_num ≥ 2`, and the branch for
    a model compiled without `pkg/ptracers` at all.
    - **Not a gap after all.** Earlier wording here carried, as an optional
      hardening, "two runoff-tracer variables whose names differ only in
      trailing blanks, which both match the same ptracer and of which
      `rnf_tendency_apply.F` keeps the last". The last clause is true — the
      `iRnf` loop of `RNF_TENDENCY_APPLY_PTR` assigns on every match, so it
      keeps the last — but the condition is **unreachable**, on three
      measured legs (the second and third added in correction round 2 from
      review B's measurements, re-measured here):
      - `RNF_NC_SERIES` trims the variable name with `ILNBLNK`, which treats
        **only the literal space** as blank
        (`MITgcm/eesupp/src/utils.F:123-152`: the scan skips a character only
        when `string(L:L) .EQ. ' '`). This is the premise the argument needs:
        any other trailing character stays in the trimmed name, so only a
        trailing *space* could make two distinct names collide.
      - NetCDF refuses a trailing space: creating `runoff_ptracer_dye ` fails
        with `NetCDF: Name contains illegal characters` (measured 2026-10-05,
        netCDF4 1.7.4, libnetcdf 4.10.0).
      - A trailing **NUL** is the one remaining route the character rule
        leaves open, and it closes itself: NetCDF *accepts*
        `runoff_ptracer_dye\0` but collapses it to the stored name
        `runoff_ptracer_dye`, after which creating the plain
        `runoff_ptracer_dye` beside it is refused with `NetCDF: String match
        to name in use` (same measurement). So the file can hold either name
        but never both.

      Any two distinct names therefore trim to distinct tracer names, which
      match distinct `PTRACERS_names` entries or none, so two runoff tracers
      can never share one ptracer and `RNF_trPtr` can never hold a
      duplicate. The
      `PTRACERS_num ≥ 2` condition the old wording attached to this item
      belongs to the *different* refusal above (a name matching two
      `PTRACERS_names` entries), not to this one.
  - both a sparse file and a dense `runoffFile` set (they are mutually exclusive)
  - missing required variables
  - grid mismatch (the file's grid-identity check is proposed in RUNOFF-001)
- Floating-point precision, parallel reductions and reproducibility expectations:
  - `_RL` (real*8) in the model, `float32` allowed in the file.
  - The global fraction check uses MITgcm `GLOBAL_SUM_*`.
  - Results must be independent of the tile/process layout to the oracle threshold.
  - NetCDF reads are done by the master thread only.

## Evidence and qualification

- Independent analytical/manufactured/reference/observational checks: reference
  runs through the existing dense `runoffFile` path are the oracles, using the same
  runoff converted to sparse form. Hold-exact is checked directly against the input
  values through runoff diagnostics.
- Small local regression dataset and representative input classes:
  - `global_ocean.cs32x15` (`input.icedyn`, `input.seaice`): cubed sphere, 12 tiles
  - new `lab_sea` `input.<X>` cases: lat-lon 20×16, 4 tiles
  - the cases cover constant, daily, monthly, monthly-repeating, yearly-file and
    hold-exact timing
- Full scientific qualification matrix, including relevant hardware/configurations:
  [docs/verification_matrix.md](../docs/verification_matrix.md). It covers
  single-process and MPI runs, and the no-change experiments.
- Stochastic seeds/replicates, uncertainty intervals and train/test separation:
  not applicable. The model is deterministic, and the oracles are exact reference
  runs.
- Data identities, access restrictions, licenses and external input manifests:
  - All test inputs are MITgcm verification data (MIT license) or are generated
    from them by scripts kept in the experiment input directories.
  - The 2 km production dataset is not used in local tests.
- What a local test establishes and what requires cluster/field/full-data evidence:
  local container runs establish correctness on the verification grids. Scale
  behavior needs a cluster run: per-record I/O at 10⁵–10⁶ sources and thousands of
  processes.
- Known capability boundaries to document:
  - No LLC experiment exists in `verification/`.
  - Adjoint behavior is untested in phase 1.
  - Parallel-I/O scaling is unverified locally.

## Runtime and operations

- Languages, compiler/interpreter, environment/lockfiles and platform:
  - **Fortran 77:** fixed-form `.F` through CPP, built with gfortran 12.2.0, MPI
    and NetCDF 4.9.0 (`-lnetcdff`) inside the `mitgcm:latest` container image,
    built from `../MITgcm_verification_docker/Dockerfile` (Debian bookworm).
  - **Python:** the conda env `/home/ifenty/miniforge3/envs/ecco` (Python 3.10.19,
    numpy 2.2.6, netCDF4 1.7.4, xarray 2025.6.1, pytest 9.1.1, all conda-forge
    except pytest). Run ESX verification as
    `/home/ifenty/miniforge3/envs/ecco/bin/python tools/esx/verify.py …`, so
    `{python}` resolves to that env. Hooks use the system `python3` (stdlib only).
    - **Pinned interpreter for the documentation contract.** Run `loop_gate.py`,
      `doc_contract.py` and `audit.py` with the env interpreter, never the system
      `python3` (3.13.12). `doc_inventory.python_units` digests
      `ast.dump(ModuleContext().visit(tree))`, and `ast.dump` output changed
      between 3.10 and 3.13, so the same unmodified tree yields a different
      inventory digest: `7230056ee9…` under 3.10.19 and `8086e2cb…` under
      3.13.12. A report sealed under one and checked under the other is reported
      `stale` with no file changed, and both RUNOFF-004 reviewers hit this (one
      could not root-cause it). Byte `sha256`s and `project.py` signatures are
      interpreter-independent; only the documentation contract is affected.
    - No project code needs more than 3.10: everything compiles under it, no
      3.11+ stdlib is used, and nothing declares `requires-python`.
    - Importing `netCDF4` warns `numpy.ndarray size changed ... Expected 16 from
      C header, got 96 from PyObject`. **Benign, do not chase it.** 96 is what
      `numpy.ndarray.__basicsize__` really is; the 16 is netCDF4's Cython module
      built against a numpy 2 header that declares the struct opaque. float64
      written through netCDF4 and read back is bitwise identical (checked
      2026-10-04 on π, e, 1/3, 1e±300, denormals, `nextafter(1,2)`, `-0.0`), so
      the precision this project relies on is intact.
  - **Platform:** Oracle Linux Server 9.7, kernel 6.12 (`el9uek`), x86_64,
    SELinux enforcing. The container engine is rootless **podman** 5.6.0, not
    Docker; `tests/mitgcm_oracle.sh` and the harness still invoke `docker`, which
    resolves to a shim. See [the code map](../docs/code_map.md) for the shim, its
    two required flags and the host prerequisites.
- Local compute budget, allowed scheduler/cluster queues and timeout: local
  container only, and each suite command must finish within 3600 s. No cluster
  queues are configured.
- Commands that submit jobs must wait for completion and return scientific verdicts:
  `tests/mitgcm_oracle.sh` compiles, runs and compares in the foreground. It exits
  non-zero on build failure, abnormal run end or FAIL.
- Data/output paths, retention and artifact transfer from isolated worktrees:
  - Build and run outputs go to `build_esx*` / `output_esx_*` inside each
    experiment. They are git-ignored (`.git/info/exclude` in `MITgcm/`) and
    disposable.
  - New reference outputs go in `results/output.<X>.txt` and are committed.
- Allowed source edits, protected files and prohibited operations:
  - **Allowed:** edit only `MITgcm/`, which is a clone of the fork
    `ifenty/MITgcm`, on the branch `new_runoff`, plus this project's own files.
  - **Protected:** never edit `../MITgcm_verification_docker`; it is a clone of
    `ifenty/MITgcm_verification_docker`, and the harness is shared with other
    projects. Changes there belong in a PR to that repository.
  - The fork's `master` matched upstream at clone time, plus 3 docs-only commits
    (`doc/outp_pkgs/outp_pkgs.rst`). In `MITgcm/`, the harness script symlinks in
    `verification/` and the `build_docker*` / `output_docker*` / `build_esx*` /
    `output_esx*` directories are listed in `.git/info/exclude`.
  - **Prohibited:** never push to MITgcm/MITgcm. Its `upstream` push URL is set to
    `no_push`. Never commit to the fork's `master`, and never edit `doc/tag-index`.
- Commit cadence and applicable owner authorization reference:
  - The owner's standing instruction (2026-09-29) is "commit as we go, but not to
    the mitgcm".
  - Commit MITgcm changes often to `new_runoff` and push to `origin` (the fork).
  - Commit project and ESX records to this repo's `main` and push to
    `origin main` (github.com/ifenty/MITgcm_new_runoff).
- Communication provider/channel, audience and authorization reference: Slack
  channel `C0C5EV9TFCJ`, created 2026-09-29 by the owner for this project, with
  the prefix `[new-runoff]`. Audience: the owner. The owner's approval of this
  channel is standing authorization to post routine issue start/resolution
  updates, not to commit outside the policy above or to deploy.
- Deployment/publication and paid-resource authorization:
  - Opening the upstream PR to MITgcm/MITgcm requires explicit owner approval.
  - No paid resources are authorized beyond normal Claude usage.
- Agent runtime, supported resume operation and configured role models: Claude
  Code CLI with retained agent sessions, per the ESX defaults. No role model pins.
  Live-session qualification (`agent_runtime.py probe`) passed 2026-10-04 on this
  host for runtime fingerprint `1d9758f9`, with both halves of the witness: a
  project-allowed Bash command ran and a disallowed one was blocked and recorded.
  Re-run it after any ESX upgrade, permission change or machine move (LL-002).
- Notification provider: **disabled by the owner on 2026-10-06** ("cancel the
  slack for now"). `esx/project.json` now sets `communication.provider` to
  `disabled`, which stops the loop generating events at all; the channel and
  prefix are kept, with the previous value in `provider_before_disable`, so
  restoring it is a one-word edit once a provider exists.
  - Slack was never reachable on this host: `claude mcp list` reports no MCP
    servers, and there is no `slack` CLI, no `SLACK_*` variable and no slack
    entry in `.claude/settings*.json` — the machine move did not carry the MCP
    configuration. The remedy was always a one-time owner action
    (`claude mcp add`), which no agent can perform.
  - Measured cost of not disabling it sooner, recorded because it is the whole
    argument for the `disabled` setting: **73 probes across loop iterations
    1-85**, every one returning the same output, under an outage renewed 14
    times, and **loop iterations 13-85 produced no scientific work**. The gate
    demanded a probe before reporting any other instruction, so each idle cycle
    paid the toll first. Both halves are now fixed in the kit
    (`TEAM-NOTIFY-OUTAGE-NO-BACKOFF-001`): the probe interval backs off per
    consecutive `down`, and the communication notice no longer pre-empts the
    work.
  - All **102** queued events were recorded `unauthorized` rather than `failed`
    or `unavailable`, because the owner revoked authorization — that is a
    revocation, not a provider fault. Nothing is queued now.
  - To re-enable: register a Slack MCP server, then set
    `communication.provider` back to `slack`. The owner's standing
    authorization to post routine issue start/resolution updates to
    `C0C5EV9TFCJ` is unchanged and applies again at that point.

**MITgcm conventions:**

- Include `*_OPTIONS.h` first. Use `_RL`/`_RS`, `myThid` and `bi,bj` tile loops.
- New code lives in `pkg/rnf` under `#ifdef ALLOW_RNF` with run-time switch
  `useRNF`; the only exf change is one guarded call in `exf_getffields.F`
  (package design, decision 2).
- Put new parameters in `data.rnf` (`RNF_PARM01`), read in `rnf_readparms.F` and
  reported in the package summary.

**MITgcm contribution rules** (`MITgcm/doc/contributing/contributing.rst`):

- **testreport before and after:** run `testreport` on all experiments on
  unmodified master, save it as `tr_out_master.txt`, repeat on the branch, and
  `diff` the two. Also run `testreport -mpi`, because the code uses `GLOBAL_SUM`.
- **`tools/do_tst_2+2`** is required for algorithmic changes.
- **Documentation:** update `doc/phys_pkgs/exf.rst` and add a page for `pkg/rnf` (RUNOFF-026). The docs are built in CI.
- **PR template:** suggest a `tag-index` entry in the template; don't edit
  `tag-index`.
- **New verification experiment:** add one with `results/` reference output.

## Project-specific procedures

- Specialist skill paths and triggers: none yet. Candidate skill: "MITgcm exf
  record timing", triggered by edits to `exf_set_gen.F` or `exf_getffieldrec.F`.
- Domain rule catalogue locations, if used: not used. Conventions are listed above.
- Documentation/rendering tools and intended renderer: MITgcm docs are Sphinx RST
  under `MITgcm/doc/`, rendered by GitHub Actions and readthedocs. Project records
  are GitHub-flavored Markdown.
- Issue priorities and scientific-risk examples:
  - **Highest risk:** a silently dropped fraction (mass not conserved), wrong
    tile/process mapping on exch2 or LLC, and time-record off-by-one at month or
    year boundaries.
  - **Also high:** any change to results when the feature is off.
  - Rank issues in dependency order: schema → converter → oracles → reader → timing.
