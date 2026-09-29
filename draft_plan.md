# Draft plan: sparse runoff forcing for MITgcm

Early design stage. The goal and requirements below come from the project owner. Items marked **(open)** are undecided and are collected in "Open questions". Settle them with the user rather than assuming, and update this file as the design firms up.

## 1. Status and decisions

**Decided:**

- Input format is **NetCDF**. JSON is not planned for now.
- The feature is built by **extending `pkg/exf`**, not as a new standalone package.
- **Phase 1 is 2D (surface) runoff only.** 3D and subsurface runoff via `addMass` comes later. Don't design it in yet, but don't design it out either.
- **All sources share one time axis.**
- **Every source has the same set of variables:** volume flux, plus any optional temperature, salinity and tracers, applied the same way to each source.
- **Only the volume flux is split among cells.** A source's fractions divide its total flux among one or more cells. Its temperature, salinity and tracer concentrations apply unchanged to every cell it feeds.
- **It must work on every MITgcm grid type:** Cartesian, lat-lon, cubed-sphere (exch2), and LLC, including exch2 blank tiles.
- **Each tile keeps only its own target cells** (see section 4).
- **Starting points:** the NetCDF reading and point-to-tile logic in `pkg/profiles` and `pkg/obsfit`.
- **Cell ids:** each target cell is a unique **global integer index**. At init, each tile converts the indices that fall on it to local `(i,j,k,bi,bj)` and stores them for each runoff id. `k` is stored even in phase 1, where it is always 1.
- **Units:** volume flux is in **m³/s** per source. The model converts each cell's share to exf's m/s by dividing by the cell area (`rA`).
- **Time axis:** stored in the file as a CF-style `time` variable (units such as `days since ...`, plus a `calendar` attribute; numpy `datetime64` writes this directly). Runtime timing settings (start date, period, repeat cycle, ...) can come from the file's attributes or from `data.exf`. **`data.exf` overrides the file.**
- **Tracers:** tracer variables in the file are matched to ptracers **by name**. Stop with an error at init if a name has no matching ptracer.
- **Number of files:** eventually any number of runoff files (rivers, glaciers, anything else). **Phase 1 supports one file**, but don't hard-code a single file into the data structures.
- **Sparse and dense are mutually exclusive.** Stop with an error if the sparse runoff file and a dense `runoffFile` are both set.
- **Missing temperature:** runoff enters at the surface water temperature, as exf does now.
- **Target cell on land:** stop with an error that names the source id. Each runoff file is built for one specific grid and its coastline, so moving runoff onto ocean cells happens offline, not in the model.
- **Fraction-sum tolerance:** 1e-6.
- **Precision:** runoff data may be stored as single precision (`float32`) in the file.
- **Adjoint:** write TAF-friendly code now; adjoint tests come later.
- **Python tool:** write a converter from dense MITgcm runoff binaries to the new NetCDF format. It's needed to build the oracle tests.
- **Global cell index:** **0-based**, and the same as a cell's position in the flattened global 2D layout of a dense `runoffFile` on that grid (exch2/LLC included). For phase 1 this position is also the unique cell id.
- **Yearly files:** follow exf's `useExfYearlyFields` convention. A file name ending in `_YYYY` is chosen by model year, with the logic in `pkg/exf/exf_getyearlyfieldname.F`. This lets 50 years of 2 km daily data be split into one file per year.
- **Time interpolation:** chosen at run time in `data.exf`. Either interpolate linearly between the bracketing records (the exf default), or hold each record's value exactly for its interval.
- **Test grids:** use grids from existing verification experiments for now. Add a lat-lon oracle built from `lab_sea` (section 9).
- **Upstream:** the work will eventually be a PR to MITgcm/MITgcm, so follow the MITgcm contribution rules from the start (section 7).

**Working copy:**

- `MITgcm/` is a clone of the user's fork `ifenty/MITgcm`, made with `gh repo clone`, on the branch `new_runoff`. `origin` is the fork; `upstream` is MITgcm/MITgcm, with its push URL set to `no_push`. At clone time, fork `master` was even with upstream plus 3 docs-only commits (`doc/outp_pkgs/outp_pkgs.rst`).
- **Commit to `new_runoff` often, and push to `origin new_runoff` (the fork) after each commit.** Never commit or push to MITgcm/MITgcm. Don't commit to the fork's `master` either; it should stay a copy of upstream.
- The project folder (`MITgcm_new_runoff/`) is its own local git repo holding `CLAUDE.md`, `draft_plan.md` and other plan files. It ignores `MITgcm/`, which is a separate repo. Commit plan changes there too, and push to `origin main` (github.com/ifenty/MITgcm_new_runoff).
- `../MITgcm` (sibling of this project) is an unrelated upstream checkout; don't edit it.
- `MITgcm/verification/{docker_build,experiment_compile,experiment_run_no_compile,compare_results,docker_run_interactive}.sh` are symlinks into `../MITgcm_verification_docker`. They, and the `build_docker*/` and `output_docker*/` directories, are listed in `.git/info/exclude`, so they never show up in commits.

## 2. Background: why

Add a new, sparse way to specify **runoff forcing** in MITgcm.

**Runoff** means a volumetric flux of water. Each source can optionally carry:

- a temperature
- a salinity (default: freshwater, S = 0)
- any number of arbitrary passive tracer concentrations

MITgcm currently takes river runoff as a dense, "flat" MITgcm binary file (`runoffFile` in `data.exf`). The file has one value per surface (k=1) grid cell for every forcing record. At high resolution this is very wasteful: nearly every cell is far from the coast and holds zero. The dense files are also opaque, because you can't tell which river or glacier feeds which cell.

## 3. NetCDF input specification

The input is organized by **source**:

- **id**: an alphanumeric code, such as a river name, a glacier name, or anything else.
- **target cells**: one or more ocean grid cells, which are surface cells in phase 1.
- **fraction** for each (source, cell) pair. Each source's fractions must add up to **exactly 1.0 across the whole domain**.
- **time series** on the shared time axis:
  - volume flux (required)
  - temperature (optional)
  - salinity (optional, default 0)
  - tracer concentrations (optional, any number)
  - The time axis can be constant, repeating (climatological), or non-repeating, at hourly, daily, monthly or yearly intervals. Monthly means calendar months: exf uses `period = -12` with `pkg/cal` for this.

Model memory and I/O should scale with the number of sources and target cells, not with the number of grid cells.

### Target scale

The main use case is **daily runoff for 50 years at every coastal cell of a global model with 2 km grid spacing**.

- That's about 18,260 time records. Coastal cells are roughly 10⁵–10⁶, an estimate that still needs checking against the real grid.
- The flux variable alone is then tens of GB in `float32`, and each of T, S and every tracer adds about the same again.

Consequences:

- **Never read whole time series.** Like dense exf fields, read only the records that bracket the current model time, and refresh them as time advances.
- **Store records so one time level is one contiguous read.** Time is the slowest, unlimited dimension (e.g. `flux(time, source)`), with NetCDF chunking set to one record.
- **Static arrays can be read at init.** The cell index and fraction arrays (~10⁶ entries each) are small enough to read once.
- **(open)** Per-record reads across many processes need a choice between two approaches. In one, every process reads the full record (a few MB) and keeps only its own sources. In the other, one process reads and hands out the data (e.g. through MITgcm's global I/O routines). At thousands of processes, the first could hammer the file system.

## 4. Tile decomposition

- A single source can feed cells on **several tiles and processes**.
- At init, each tile works out:
  - which source ids have target cells on it
  - which local cells `(i,j,bi,bj)` those are
  - each cell's fraction
- Each tile then stores only that local list. At every time step it applies `flux(source, t) × fraction` to its own cells.
- The fraction check must be **global**:
  - Sum each source's fractions over all tiles and processes, using MITgcm's `GLOBAL_SUM_*` routines.
  - Stop with an error if any source is off from 1.0 by more than a tolerance.
  - This also catches cells that point to land, to a blank exch2 tile, or outside the grid. Those cells silently drop out, so the fractions come up short.
- File reads and `NF_*` calls should be done by the master thread only. Use `_BEGIN_MASTER` / `_END_MASTER`, and follow `pkg/profiles` and `pkg/obsfit` for MPI.

## 5. Open questions

- **NetCDF schema:** dimension and variable names, the string type for ids, the attribute names for runtime timing settings, and how the file records which grid it was built for, so the model can refuse a mismatched file.
- **Per-record parallel I/O** at the 2 km scale (see "Target scale").
- **Salinity and tracers:** exf has no existing runoff field for either, so they will need new plumbing.

## 6. Existing MITgcm machinery to build on or match

Paths are relative to `MITgcm/`.

- **2D runoff in exf**:
  - `pkg/exf` reads `runoffFile` into `runoff` (m/s) under `ALLOW_RUNOFF`. `ALLOW_RUNOFTEMP` with `runoftempFile` adds runoff temperature.
  - The heat-content treatment is in `pkg/exf/exf_mapfields.F`. By default, runoff enters at the surface water temperature.
  - Namelist parameters (`runofffile`, `runoffperiod`, `runoffStartTime`, `runoffRepCycle`, `exf_inscal_runoff`, `runoffconst`, ...) are set in `exf_readparms.F` and `EXF_PARAM.h`.
  - Record timing is in `exf_set_gen.F`, `exf_getffieldrec.F` and `exf_getmonthsrec.F`.
  - Fields are in `EXF_FIELDS.h` and CPP switches in `EXF_OPTIONS.h`. Diagnostics, monitoring and checks live in `exf_diagnostics_*.F`, `exf_monitor.F`, `exf_check*.F` and `exf_summary.F`.
  - The simplest integration fills the existing 2D `runoff` (and `runoftemp`) arrays from the sparse source list, so everything downstream stays unchanged.
  - Docs for exf are in `doc/phys_pkgs/exf.rst`.
- **NetCDF, sparse points**:
  - `pkg/profiles` (`profiles_init_fixed.F`) and `pkg/obsfit` read per-point NetCDF with `NF_OPEN` / `NF_GET_VAR*` and `#include "netcdf.inc"`.
  - They assign points to the tiles that own them.
  - These are the templates for reading the file and building each tile's local list.
- **3D volume sources (later phase)**: the core model's `addMass`, enabled with `selectAddFluid`, is used in `model/src/apply_forcing.F` and `integr_continuity.F`. It currently supports only one T and S (`temp_addMass`, `salt_addMass`) for the whole domain.
- **Passive tracers**: `pkg/ptracers` needs to take per-source tracer concentrations. Its current handling of freshwater and `addMass` sources is the place to hook in.

## 7. MITgcm coding conventions

- The source is Fortran 77, fixed-form `.F`, run through CPP. Include `*_OPTIONS.h` first. Use `_RL`/`_RS` types, `myThid`, and `bi,bj` tile loops.
- Wrap new code in `#ifdef ALLOW_<FEATURE>` inside exf, and add a run-time switch. Existing configurations must stay bit-for-bit unchanged.
- Keep code compatible with the adjoint (TAF/Tapenade) where practical. exf runoff is a control variable in ECCO-style setups; see `pkg/exf/exf_ad_*` and `pkg/autodiff/check_lev1_dir_forcing.h`.
- New run-time parameters belong in the `data.exf` namelists. Document them in `exf_summary.F`.

**MITgcm contribution rules** (`doc/contributing/contributing.rst`, `.github/PULL_REQUEST_TEMPLATE.md`):

- **testreport before and after:** run `testreport` on all experiments on unmodified `master`, save `tr_out.txt` as `tr_out_master.txt`, repeat on the branch, then `diff` the two. Because this work calls `GLOBAL_SUM_*`, also run `testreport -mpi`.
- **`tools/do_tst_2+2`** is required for algorithmic changes or pickup-related changes. Run it on both branches and compare `tst_2+2_out.txt`.
- **Documentation:** update `doc/` (at least `doc/phys_pkgs/exf.rst`). GitHub Actions builds the docs, so RST errors fail CI.
- **PR template:** fill it in, including a *suggested* `doc/tag-index` entry. Don't edit `tag-index` directly.
- **New verification experiment:** add one (or a new `input.<X>`) with `results/` reference output that uses the sparse runoff path.

## 8. Build and test workflow

The workflow uses Docker; the image `mitgcm:latest` is already built. Run the scripts from `MITgcm/verification/`. They compile with `testreport -norun` inside the container, so every compile is a full rebuild. Source edits don't require rebuilding the Docker image.

```bash
cd MITgcm/verification
./experiment_compile.sh <experiment> -j 8 [-mpi] [-mods /abs/path/to/code_dir] [-build <dir>]
./experiment_run_no_compile.sh <experiment> [input_dir] [-mpi N] [-build <dir>] [-output <dir>]
./compare_results.sh <experiment> [output_dir]     # testreport-style digit match vs results/output*.txt
```

Tips for using the scripts:

- Changing only input, such as a new NetCDF file or a namelist, needs no recompile. Put each variant in `<experiment>/input.<X>/`, where files layer on top of `input/`, and run it with `-output output_<X>`.
- The run script exits non-zero unless the log says `Execution ended Normally`. The model log is `<experiment>/<output_dir>/output.txt`.
- Use `-build <dir>` to keep a baseline and a modified build side by side.

## 9. Verification oracles

To test, convert an experiment's dense runoff file to the new sparse NetCDF form, rerun it, and match `results/output.<X>.txt` to round-off.

All exf runoff in `verification/` is in **`global_ocean.cs32x15`**, a cubed sphere with exch2:

- 6 faces of 32×32 cells
- `code/SIZE.h`: 12 tiles of 32×16 on 1 process
- `code/SIZE.h_mpi`: 4 processes × 3 tiles

That makes it a good test of sources that span tiles and processes.

| Input dir | Build | Runoff forcing | Reference output |
| --- | --- | --- | --- |
| `input.icedyn` | `code/` (forward) | `runoffFile = core_rnof_1_cs32.bin`, `runoffperiod = 2592000` (30 d), `runoffStartTime = 1296000` | `results/output.icedyn.txt` |
| `input.seaice` | `code/` (forward, `ALLOW_RUNOFTEMP` on) | same `core_rnof_1_cs32.bin`, linked from `input.icedyn` by `prepare_run`, **plus `runoftempFile = runoff_temperature.bin`** | `results/output.seaice.txt` |
| `input_ad.seaice` | `code_ad/` (adjoint, `ALLOW_RUNOFTEMP` off) | same runoff file and timing | `results/output_adm.seaice.txt`, `output_tlm.seaice.txt.gz` |
| `input_ad.seaice_dynmix` | `code_ad/` | same | `results/output_adm.seaice_dynmix.txt`, `output_tlm.seaice_dynmix.txt.gz` |
| `input_ad.thsice` | `code_ad/` | same | `results/output_adm.thsice.txt`, `output_tlm.thsice.txt.gz` |

Other cs32 variants have no runoff: `input`, `input.thsice` (uses `pkg/bulk_force` with a blank `RunoffFile`), `input.in_p`, `input.viscA4`, `input_ad`, and `input_tap`.

**No-change checks.** These experiments use exf with `runoffFile = ' '`. They must still pass unchanged with the new code compiled in:

- `1D_ocean_ice_column` (fast smoke test)
- `lab_sea`
- `seaice_itd`
- `seaice_obcs`
- `offline_exf_seaice`

**Runoff outside exf (not oracles for this project):**

- `global_oce_latlon/input.ebm`: `pkg/ebm` reads its own `RunoffFile`.
- `isomip/input.icefront`: `pkg/icefront` has `SGRunOff*` settings, but they're commented out.
- `cpl_aim+ocn` and `aim.5l_cs`: coupler and land-model runoff.

**Gap:** no verification experiment has exf runoff on a lat-lon, Cartesian or LLC grid. There are also no LLC experiments in `verification/` at all.

**New lat-lon oracle from `lab_sea`** (planned; `lab_sea/input/data.exf` currently has `runoffFile = ' '`)

`lab_sea` setup:

- Spherical-polar grid, 20×16 cells at 2°, starting at 280°E, 46°N, with 23 levels.
- `code/SIZE.h`: 4 tiles of 10×8 on 1 process.
- `code/SIZE.h_mpi`: 2 processes × 2 tiles.
- `dt` = 1 h, and the standard run is 9 steps. Gregorian calendar from `startDate_1 = 19790101`.
- The forward build has no `code/EXF_OPTIONS.h`, so it uses the `pkg/exf` default: `ALLOW_RUNOFF` on, `ALLOW_RUNOFTEMP` off. Testing runoff temperature needs a `-mods` code directory that turns on `ALLOW_RUNOFTEMP`.
- `input/data.exf_YearlyFields` and `input/data_YearlyFields` already show a `useExfYearlyFields` setup to copy from.

Steps:

1. Read `lab_sea/input/bathy.labsea1979` and pick a reasonable set of coastal ocean cells as river and glacier sources. Include at least one source that spreads over several cells **across a tile boundary**, and across the process boundary in the MPI layout.
2. For each case below, write the dense `runoffFile` (and optionally `runoftempFile`) with the current method.
3. Run each case through the existing dense path, about 1 month or longer where the case needs it. Save `output.txt` as the reference `results/output.<X>.txt` for a new `input.<X>`.
4. Convert each dense file with the Python tool and rerun through the sparse path. Match the reference to round-off, for both the single-process and the MPI (`-mpi`, 2 processes) builds.

Test matrix (one `input.<X>` each, or combined where it's cheap):

| Case | Record spacing | What it checks |
| --- | --- | --- |
| constant | one record | time-invariant runoff |
| daily | 1 day, non-repeating | reading and interpolating many records |
| monthly | calendar months (`period = -12`), non-repeating | calendar-month timing |
| monthly-repeating | 12 records, climatology (`RepCycle` = 1 year) | wrapping from the last record back to the first |
| yearly files | daily or monthly, split into `_YYYY` files | switching files at the year boundary. The run must cross 31 Dec → 1 Jan, so it needs a later start date or a run longer than one year. |
| hold-exact | any of the above, with hold-exact set in `data.exf` | step-wise values with no interpolation. There's no dense-path oracle for this; check it directly against the input values, e.g. with diagnostics of `runoff`. |

Keep the scripts that generate these inputs (e.g. `gendata.py`) in the experiment's input directory, as other experiments do.
