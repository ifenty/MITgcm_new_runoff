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
  - Sparse runoff reproduces the dense-path results to round-off on
    `global_ocean.cs32x15` (`input.icedyn`, `input.seaice`) and on the new lab_sea
    cases, single-process and MPI.
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
  - **Dense-vs-sparse oracles:** match the reference `output.txt` to the
    `compare_results.sh` / testreport digit threshold. The expected difference is
    round-off from `flux·frac/rA` versus the precomputed dense m/s value.
  - **Fraction sum:** within 1e-6.
  - **No-change experiments:** must be identical.
- Invalid input, unsupported cases and required failure behavior: stop at init
  with an `RNF`-prefixed error naming the file, variable or source id for any of
  these:
  - fraction sum out of tolerance
  - target cell on land or off the grid
  - tracer name with no matching ptracer
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
  Live-session qualification (`agent_runtime.py probe`) is not yet run.

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
