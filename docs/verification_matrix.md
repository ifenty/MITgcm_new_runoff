# Scientific qualification matrix

Oracles are the existing dense `runoffFile` path. The same runoff is converted to
sparse NetCDF and must reproduce the dense-path `output.txt` to the
`compare_results.sh` threshold, which is testreport's matching-digit criterion.
All commands run from the project root. `tests/mitgcm_oracle.sh` compiles, runs
and compares, and exits non-zero on any failure. Status: **planned** unless
marked **configured**, meaning it is in [project.json](../esx/project.json) and
runs on the unmodified code today.

| Mechanism / hypothesis | Input classes and configurations | Oracle / independent reference | Tolerance and justification | Command | Local or remote | Required to close? |
| --- | --- | --- | --- | --- | --- | --- |
| No-change: `pkg/rnf` compiled in and switched off leaves results unchanged (**configured**) | `lab_sea` and `global_ocean.cs32x15` list `rnf` in `code/packages.conf`; no `data.pkg` sets `useRNF`. `lab_sea/input` (exf with `runoffFile = ' '`), the six `lab_sea/input.rnof_*` dense cases, `global_ocean.cs32x15/input.seaice` and `input.icedyn`; single-process, `lab_sea -mpi 2` and cs32 `input.seaice -mpi 4` | committed `results/output*.txt`. The run log reports the state as `pkg/rnf compiled but not used`; no command checks that line | testreport digit threshold; expected identical | `tests/mitgcm_oracle.sh lab_sea input [-mpi 2]`, `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.seaice [-mpi 4]`, `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.icedyn` and the dense rows below | local container | yes, every code change |
| No-change: `pkg/rnf` compiled out leaves results unchanged; the edited hook files in `model/src`, `pkg/exf` and `pkg/ptracers` still compile without it (**configured**) | Six experiments without `rnf`; all compile the edited `model/src` files. `isomip/input` (`pkg/shelfice`; no exf, no ptracers). `1D_ocean_ice_column/input`, `seaice_obcs/input`, `offline_exf_seaice/input`, `seaice_itd/input` (exf with `runoffFile = ' '`): these four compile the edited `exf_getffields.F`. `tutorial_advection_in_gyre/input` (ptracers in use, no exf): the one that compiles and runs the edited `pkg/ptracers/ptracers_apply_forcing.F` | committed `results/output.txt` | testreport digit threshold; expected identical | `tests/mitgcm_oracle.sh <exp> input` | local container | yes, every code change |
| Configuration refusals of `pkg/rnf`, and a valid configuration (**configured**) | scratch inputs layered on `lab_sea/input`, each with `useRNF=.TRUE.`, a `data.rnf` naming the valid file `input.rnof_const/runoff_sparse.nc` and one violation: `runofffile` set, `runoffconst` ≠ 0, `exf_outscal_sflux` = 2, those three together, blank `RNF_file`, `useEXF=.FALSE.`; and the valid configuration as positive control; single-process and on 2 MPI processes | a run that does not end normally, with each process judged on its own files: the expected `RNF_CHECK` or `RNF_READPARMS` error text in every `STDERR.*`, and one `STOP` line of the expected routine per process (in `output.txt`, or in `mpirun.log` for an MPI run). A refusal case must not show, in any log, the lines printed after the checks pass. The three-violation case must report all three and count 3 errors. The control must end normally and show in the standard output of every process "configuration checks passed", the summary banner, `RNF_file`, `RNF_nSrcFile` = 4 and `RNF_nTgtOwned` = 7 on the summary's own value lines (the echo of `data.rnf` is not accepted), and the two flux sums of `RNF_INIT_VARIA`, with no refusal message | exact substring match per file; exact value on the summary line; flux summed over the sources equal to the sum computed from the file within 1e-12 relative, and summed over the targets of all tiles within 1e-6 (the fraction tolerance) | `{python} tests/rnf/refusal_check.py`, after `tests/mitgcm_oracle.sh lab_sea input` has built the binary; `{python} tests/rnf/refusal_check.py --mpi 2`, after `tests/mitgcm_oracle.sh lab_sea input -mpi 2` | local container | yes |
| Dense runoff baseline, cubed sphere (**configured**) | `global_ocean.cs32x15/input.icedyn`: 30-day records, 12 tiles | `results/output.icedyn.txt` | digit threshold | `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.icedyn` | local | yes |
| Dense runoff + runoff temperature, cubed sphere (**configured**) | `global_ocean.cs32x15/input.seaice` (`ALLOW_RUNOFTEMP`) | `results/output.seaice.txt` | digit threshold | `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.seaice` (and `-mpi 4`) | local | yes |
| Sparse = dense, cubed sphere, exch2 multi-tile/multi-process, volume flux of one constant record (**configured**) | `global_ocean.cs32x15/input.rnof_sp_icedyn`: the set-up of `input.icedyn` (its `prepare_run` links the files of `input.icedyn`) with `useRNF`, no dense `runoffFile`, and `runoff_sparse_const.nc`, record 1 of `core_rnof_1_cs32.bin` as one constant record, 1189 one-cell sources; `SIZE.h` 12 tiles and `SIZE.h_mpi` 4 processes × 3 tiles; `W2_mapIO = -1` (192 × 32 layout). The target table (1189 entries) and the flux record are each read in two chunks (`RNF_nBuf` = 1000) | `results/output.rnof_sp_icedyn.txt`, a copy of the dense `results/output.icedyn.txt` (the 12 dense records are identical, so the dense run applies this field at every step) | digit threshold (10 on `cg2d_init_res`). Measured: 11 digits single-process and `-mpi 4`, the same as the dense `input.icedyn` run of the same binary against that reference (see coverage limits). This threshold does not see a one-cell move of the weakest targets (coverage limits). The placement probe row below checks where the reader places 80 fixed cells per layout; it does not read this file and is not a check of its targets | `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.rnof_sp_icedyn` and `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.rnof_sp_icedyn -mpi 4` | local | yes |
| Sparse = dense, cubed sphere, runoff temperature and time records | converted `core_rnof_1_cs32.bin` + `runoff_temperature.bin` (`input.rnof_sparse/runoff_sparse.nc`, 12 records) | `results/output.seaice.txt`, `results/output.icedyn.txt` | round-off from flux·frac/rA vs precomputed m/s | new `input.<X>` via `tests/mitgcm_oracle.sh … [-mpi 4]` (RUNOFF-005, RUNOFF-006, RUNOFF-013) | local | yes |
| Dense runoff baseline, lat-lon, constant runoff (**configured**) | `lab_sea/input.rnof_const`: `runoffperiod = 0`, 48 steps; seven coastal source cells, one group spanning the tile and MPI process boundary between columns 9 and 10 | `results/output.rnof_const.txt` (single-process dense run) | digit threshold; the `-mpi 2` run must match the single-process reference | `tests/mitgcm_oracle.sh lab_sea input.rnof_const` and `tests/mitgcm_oracle.sh lab_sea input.rnof_const -mpi 2` | local | yes |
| Dense runoff baseline, daily records, non-repeating (**configured**) | `lab_sea/input.rnof_daily`: `runoffperiod = 86400`, `runoffRepCycle = 0`, 32 days, monitor every 12 h; records 1 to 34 read, 1 to 33 with non-zero weight | `results/output.rnof_daily.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_daily` and `tests/mitgcm_oracle.sh lab_sea input.rnof_daily -mpi 2` | local | yes |
| Dense runoff baseline, repeating monthly climatology (12 calendar-month records repeated every year) (**configured**) | `lab_sea/input.rnof_month`: `runoffperiod = -12`, 61 days from 1 January, crossing two month boundaries and two mid-month record changes; records 12, 1, 2, 3 read, all with non-zero weight | `results/output.rnof_month.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_month` and `tests/mitgcm_oracle.sh lab_sea input.rnof_month -mpi 2` | local | yes |
| Dense runoff baseline, calendar-month records, non-repeating (**configured**) | `lab_sea/input.rnof_month1`: `runoffperiod = -1`, `runoffstartdate1 = 19781201`, 61 days from 1 January, crossing two month boundaries; records 1 (December 1978) to 4 (March 1979) read, all with non-zero weight | `results/output.rnof_month1.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_month1` and `tests/mitgcm_oracle.sh lab_sea input.rnof_month1 -mpi 2` | local | yes |
| Dense runoff baseline, 12 equally spaced records with a repeat cycle (**configured**) | `lab_sea/input.rnof_clim`: `runoffperiod = 2628000`, `runoffRepCycle = 31536000` (365 days), 50 days from 1 December, wrapping from record 12 to record 1; records 11, 12, 1, 2 read, all with non-zero weight | `results/output.rnof_clim.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_clim` and `tests/mitgcm_oracle.sh lab_sea input.rnof_clim -mpi 2` | local | yes |
| Dense runoff baseline, yearly `_YYYY` files (**configured**) | `lab_sea/input.rnof_yearly`: `useExfYearlyFields`, daily records, 26 days from 20 December, monitor every 12 h; records 354 to 365 of `runoff_yearly_1978` and 1 to 16 of `runoff_yearly_1979` read, of which 354 to 365 and 1 to 15 have non-zero weight | `results/output.rnof_yearly.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_yearly` and `tests/mitgcm_oracle.sh lab_sea input.rnof_yearly -mpi 2` | local | yes |
| Dense runoff timing, direct check (**configured**) | the run directories of the six `lab_sea/input.rnof_*` cases, single-process and `-mpi 2`; needs the oracle runs above to have been made | monitor statistics `exf_runoff_max`, `_min`, `_mean`, `_sd` versus the field interpolated from the input records under the exf timing conventions, at every monitor time | ≤ 1e-12 relative to the largest runoff value (real*8 interpolation of float32 records) | `{python} tests/runoff/lab_sea_runoff_timing_check.py` and `{python} tests/runoff/lab_sea_runoff_timing_check.py --mpi 2` | local | yes |
| Sparse = dense, lat-lon, constant runoff (**configured**) | `lab_sea/input.rnof_sp_const`: the set-up of `input.rnof_const` with `useRNF`, no dense `runoffFile`, and `../input.rnof_const/runoff_sparse.nc` (4 grouped sources, 7 targets; `baffin` spans the tile and MPI process boundary, `labrador` a tile boundary); single-process (4 tiles) and `-mpi 2`. The one-source-per-cell file `runoff_sparse_cells.nc` runs as case `cells_equal_dense` of `tests/rnf/refusal_check.py`, and the same run with every flux set to zero as case `zero_flux_differs` | `results/output.rnof_sp_const.txt`, a copy of the dense `results/output.rnof_const.txt`; the two cases of the check script use the dense reference itself | digit threshold (10 on `cg2d_init_res`). Measured: 16 digits on every checked variable, single-process and `-mpi 2`, for the grouped and the per-cell file. Negative control: with zero flux only 2 digits match, so the comparison is sensitive to the runoff | `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_const` and `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_const -mpi 2`; `{python} tests/rnf/refusal_check.py [--mpi 2]` | local | yes |
| Sparse = dense, daily records, non-repeating | the `input.rnof_daily` runoff, ≥ 1 month | `results/output.rnof_daily.txt` | digit threshold | as above | local | yes |
| Sparse = dense, repeating monthly climatology (`period = -12`) | the `input.rnof_month` runoff, spanning ≥ 2 month boundaries | `results/output.rnof_month.txt` | digit threshold | as above | local | yes |
| Sparse = dense, calendar-month records, non-repeating (`period = -1`; schema `monthly` sampling with repeat `none`) | the `input.rnof_month1` runoff, spanning ≥ 2 month boundaries | `results/output.rnof_month1.txt` | digit threshold | as above | local | yes |
| Sparse = dense, climatology wrap (`RepCycle` = 1 year) | the `input.rnof_clim` runoff, crossing Dec → Jan | `results/output.rnof_clim.txt` | digit threshold | as above | local | yes |
| Sparse = dense, yearly `_YYYY` files | the `input.rnof_yearly` runoff, run crossing 31 Dec → 1 Jan | `results/output.rnof_yearly.txt` (`useExfYearlyFields`) | digit threshold | as above | local | yes |
| Hold-exact interpolation mode | lab_sea, daily or monthly | input values themselves: `runoff` diagnostic = Σ flux·frac/rA of the current record; no dense oracle exists | ≤ 1e-12 relative (real*8 arithmetic on float32 inputs) | new check script (RUNOFF-005) | local | yes |
| Refusals that need the file (**configured**) | scratch inputs layered on `lab_sea/input`, each with a copy of `input.rnof_const/runoff_sparse.nc` that has one violation. Table entries: `target_cell` = -3 and = nx·ny; `target_source` = -1 and = number of sources; `target_level` = 2; a fraction of -0.25 and one that is not a number; a fraction of -0.25 hidden by two others in a sum of exactly 1. Targets: one moved to a land cell of the western half of the grid; `target_cell_area` off by 1 %; a fraction sum of 0.999. The file: `mitgcm_grid_nx` = 21; no `mitgcm_grid_nx`; `mitgcm_time_sampling` = `fixed`; no `target_fraction` variable. The flux: not a number, infinite, 1e31, equal to a numeric `missing_value` of -9999, equal to the `_FillValue` of a float32 variable, and 9999 with `missing_value` stored as the text "9999.". Array bounds: synthetic files with `RNF_nSrcTile` + 1 = 2001 sources on one cell (target table read in three chunks) and with `RNF_nTgtTile` + 1 = 10001 entries on one cell. Single-process and on 2 MPI processes | a run that does not end normally: the expected `RNF_INIT_FIXED`, `RNF_NC_ERROR`, `RNF_NC_READ_FLUX` or `RNF_NC_ATT_REAL` error text, naming the source id where a source is concerned, the table entry for `target_source`, and RUNOFF-005 for the time sampling; one `STOP` line per process. Land, cell area and array bounds are seen by the process that owns the tile only: its message must be in the `STDERR.*` of at least one process, the summed count in that of every process, and every process must stop within the timeout (no hang). The hidden negative fraction must be refused by its range and not reach the fraction sum. In the six flux cases the flux sums of `RNF_INIT_VARIA` must not be printed. The text `missing_value` case fails on the code before the round-1 correction, where the run ended normally with 9999 m³/s applied | exact substring match per file; one `STOP` line per process; run time below `--timeout` (default 600 s) | `{python} tests/rnf/refusal_check.py` and `{python} tests/rnf/refusal_check.py --mpi 2` | local | yes |
| Refusals that need the file, not yet run | every file refusal listed under "Refusals in the code that no configured test runs" in the coverage limits, among them a target beyond an open boundary (`maskInC` = 0) or under an ice shelf (`kTopC` ≠ 0): no experiment that compiles `rnf` has open boundaries or `pkg/shelfice`. Also an unknown tracer, which is not in the code yet (tracers are not read) | expected fatal `RNF` error text in the run logs | exact message match | more cases (RUNOFF-017, RUNOFF-019, RUNOFF-020) | local | yes |
| Placement of 80 fixed probe cells per layout on exch2 tiles (**configured**) | `global_ocean.cs32x15` on 4 MPI processes, the set-up of `input.rnof_sp_icedyn` with a `data.exch2` that sets `W2_mapIO` = -1 (192 × 32), 0 (6144 × 1, one long line) and 1 (32 × 192, compact). 80 probe cells per layout, 20 per process: the 4 corners of each of the 12 tiles and 32 interior cells at fixed positions. The cells are chosen without regard to any runoff file, which the probe does not read; they are not the runoff targets (coverage limits). Each probe is a target with `target_cell_area` = 1 m², so the model refuses it and prints the cell index of the file with the `i,j,bi,bj` where it placed it. With `W2_mapIO` = 0 the long-line branch of the placement runs, which no other test executes | a placement computed in the test from exch2's own topology log of the same run (`w2_tile_topology.NNNN.log`: map size, facets, each tile's facet, offset and position on the map, the tiles of each process) with the definition of the layouts, not the record arithmetic of the model; the layout rule is first checked against exch2's "on Glob.Map" position of every tile. Second, the model's dense reader: a probe must be reported "on land" exactly where the bathymetry file holds a land value at that cell index. Control: with every index of the file raised by one, no probe may be reported on the cell predicted for the original index | the reported set of (cell, process, i, j, bi, bj) equals the predicted set, nothing missing and nothing extra; every process prints the count of 80 and stops; no timeout. Measured: 80 of 80 in each layout; land at 20, 22 and 22 probes, equal to the bathymetry file; control 0 of 80 | `{python} tests/rnf/placement_probe.py`, after `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.rnof_sp_icedyn -mpi 4` has built the binary | local | yes |
| Volume conservation | at initialization (**configured**): the flux summed over the sources of the file and over the targets of all tiles, printed by `RNF_INIT_VARIA`, in the control cases of `tests/rnf/refusal_check.py`. During the run (planned): Σ runoff·rA from diagnostics | Σ flux·frac over the targets = Σ flux_s | initialization: ≤ 1e-6 relative (the fraction tolerance); measured equal in every printed digit for lab_sea and cs32. During the run: ≤ 1e-12 relative | `{python} tests/rnf/refusal_check.py`; new check script (RUNOFF-015, RUNOFF-016) | local | yes |
| Converter round-trip and converted inputs (**configured**) | the dense runoff files of the six `lab_sea/input.rnof_*` cases (float32) and of cs32 (`core_rnof_1_cs32.bin`, `runoff_temperature.bin`, float64, converted twice: all 12 records with temperature, and record 1 alone as one constant record; needs the grid output of a cs32 run, else skipped); synthetic lat-lon and exch2-shaped grids with land, a blank tile and grouped sources; a hand-built file with two sources feeding one cell | dense → sparse → dense gives back every dense record; fractions, fluxes and temperatures computed in the test from the inputs; for two sources on one cell, runoff as the sum of flux·fraction/rA and temperature as the flux-weighted mean, worked out by hand, including a record without flux and the fill value; time axes worked out by hand per exf timing mode; at every forcing time of the six lab_sea oracle runs, the sparse file read by the schema's rules against the field exf applies from the dense file (`lab_sea_runoff_timing_check.Case`, the emulation the direct timing check compares with the model), with a one-record shift as negative control; the integrity checker with grid checks on every converted file; each committed sparse file of the table below equals its regeneration: the lab_sea files in every variable, global attribute and type, and the two cs32 files (`input.rnof_sparse/runoff_sparse.nc` and `input.rnof_sp_icedyn/runoff_sparse_const.nc`) in every variable; for the constant cs32 file also one `constant` float64 record without temperature that gives back record 1 of the dense file | exact for float32 inputs and for the cs32 temperature; cs32 runoff (float64) exact at float32 and within one unit in the last place at float64, because (d·rA)/rA is not always d; total flux per record ≤ 1e-12 relative; field at forcing times ≤ 1e-12 of the largest runoff value; checker: no error, no warning | `{python} -m pytest -q tests/runoff` (`tests/runoff/test_convert.py`) | local | yes |
| Upstream contribution | all verification experiments, master vs branch, plus `-mpi` | `tr_out_master.txt` | no diff beyond timestamps | `MITgcm/verification/testreport` (in the container) and `tools/do_tst_2+2` | local | before the PR |
| 2 km scale I/O | 10⁵–10⁶ sources, 50 years daily, thousands of processes | wall-clock and I/O profile | owner-defined | cluster | remote | no (phase 1) |

**Sparse inputs of the dense cases (RUNOFF-002, RUNOFF-004):** the
"Sparse = dense" rows above use these files. The two configured rows read
`lab_sea/input.rnof_const/runoff_sparse.nc` and the constant cs32 file; the
planned rows will read the others. The files are written by
`MITgcm/verification/lab_sea/input.rnof_const/gen_sparse.py` with the converter
of [runoff schema](runoff_schema.md) §14. Each stores `runoff_flux` in float64
and has `target_cell_area`. `tests/runoff/test_convert.py` regenerates each
one, compares it with the committed file and runs the integrity checker with
the grid checks on it, with no error and no warning (row "Converter
round-trip and converted inputs"); the tests of the two cs32 files are
skipped when no cs32 run directory with grid output exists.

| Dense case | Sparse file or files | Sources | Time axis |
| --- | --- | --- | --- |
| `lab_sea/input.rnof_const` | `runoff_sparse.nc`; `runoff_sparse_cells.nc` | 4 (the groups of `runoff_sources.txt`: `baffin` 3 cells, `labrador` 2, `greenland`, `newfound`); 7 (one per cell) | 1 record, `constant` |
| `lab_sea/input.rnof_daily` | `runoff_sparse.nc` | 7 (one per cell) | 40 records, `fixed` 86400 s from 1979-01-01 00:00 |
| `lab_sea/input.rnof_month` | `runoff_sparse.nc` | 7 | 12 records, `monthly`, repeat `annual`, nominal year 1979 |
| `lab_sea/input.rnof_month1` | `runoff_sparse.nc` | 7 | 6 records, `monthly`, December 1978 to May 1979 |
| `lab_sea/input.rnof_clim` | `runoff_sparse.nc` | 7 | 12 records, `fixed` 2628000 s from 1978-01-16 12:00, repeat `annual` (365 days) |
| `lab_sea/input.rnof_yearly` | `runoff_sparse_1978.nc`, `runoff_sparse_1979.nc` | 7 | 365 records each, `fixed` 86400 s from 1 January 00:00 |
| `global_ocean.cs32x15/input.icedyn`, `input.seaice` | `input.rnof_sparse/runoff_sparse.nc` (runoff and runoff temperature; no namelists yet, RUNOFF-006) | 1189 (one per cell) | 12 records, `fixed` 2592000 s from model time 1296000 s, repeat `annual` on the `360_day` calendar |
| `global_ocean.cs32x15/input.icedyn`, record 1 only | `input.rnof_sp_icedyn/runoff_sparse_const.nc` (runoff, no temperature; `gen_sparse.py cs32const`) | 1189 (one per cell) | 1 record, `constant` |

- In the five timed lab_sea cases the cells of `baffin` and `labrador` vary
  differently in time, so their shares of the group's flux are not constant
  and each cell is its own source (`baffin_288` and so on). Only `const` tests
  a source that spans a tile and process boundary.
- The cs32 runoff and runoff temperature are constant in time: the 12 records
  of `core_rnof_1_cs32.bin`, and of `runoff_temperature.bin`, are identical.
  - The configured cs32 oracle (`input.rnof_sp_icedyn`, one constant record)
    tests the volume path, and the exch2 mapping within the coverage limits
    below: in one layout, and not for the weakest targets. Its file has no
    temperature. The temperature path is tested by no run yet.
  - The planned 12-record oracle (row "Sparse = dense, cubed sphere, runoff
    temperature and time records") is meant to test the volume and
    temperature paths with the same mapping. Because its records are
    identical, it will not detect a record chosen or weighted wrongly.
    Timing without `pkg/cal` needs a case with records that differ.
- The cs32 build has no `pkg/cal` (`-cal` in `code/packages.conf`), so its
  file's time is model time in seconds from the reference date of the time
  units, and the `360_day` calendar is the one in which its 360-day repeat
  cycle is one year. A run without `useCAL` takes start time, period and
  repeat cycle in seconds from `data.rnf` ([package design](package_design.md),
  decision 7): 1296000, 2592000 and 31104000 for this file. How the reader
  treats the file's own time axis in such a run is decided in RUNOFF-005.

**Other experiments (not oracles):**

- `global_ocean.cs32x15/input.in_p` is a pressure-coordinate case with dense exf
  runoff and runoff temperature. Its `data.pkg` sets `useEXF` and `useSEAICE`,
  and its `prepare_run` links `data.exf` and `runoff_temperature.bin` from
  `../input.seaice` and `core_rnof_1_cs32.bin` from `../input.icedyn`. It has a
  reference, `results/output.in_p.txt`, and is in no configured suite.
- These cs32 variants have no exf runoff: `input`, `input.thsice` (which uses
  `pkg/bulk_force` with a blank `RunoffFile`), `input.viscA4`, `input_ad` and
  `input_tap`.
- Five experiments keep their own copy of an edited routine in `code/`, which
  the build uses in place of the package file, so they do not compile the
  `pkg/rnf` hook in it:
  - `tutorial_global_oce_latlon` (`ptracers_apply_forcing.F`). It runs ptracers
    without `rnf`, and it is no test of the edited
    `pkg/ptracers/ptracers_apply_forcing.F`.
  - `hs94.1x64x5`, `hs94.cs-32x32x5`, `tutorial_held_suarez_cs` and
    `tutorial_rotating_tank` (`apply_forcing.F`).
- Runoff outside exf:
  - `global_oce_latlon/input.ebm`: `pkg/ebm` reads its own `RunoffFile`.
  - `isomip/input.icefront`: the `pkg/icefront` `SGRunOff*` settings are commented
    out.
  - `cpl_aim+ocn` and `aim.5l_cs`: coupler and land-model runoff.
- The lab_sea dense runoff cases, their source cells and the exf timing
  conventions they rely on (with source line references) are described in the
  "Runoff forcing tests" section of `MITgcm/verification/lab_sea/README.md`.
  `gendata.py` in each `input.rnof_<X>` writes the runoff files and
  `runoff_sources.txt`, the list of source cells to convert to sparse form.
- Runoff in these cases stays below 1e-6 m/s, because `useExfCheckRange` stops
  the run at the first step above that value (`exf_check_range.F`).
- `runoffperiod = -12` is a 12-record calendar-month climatology that repeats
  every year (`input.rnof_month`). Calendar-month records that do not repeat
  use `runoffperiod = -1` (`exf_set_fld.F`, `exf_getmonthsrec.F`), with
  record 1 the month of the runoff start date (`input.rnof_month1`).
- `useExfYearlyFields` applies to every exf field and excludes a non-zero
  `repeatPeriod`, so `input.rnof_yearly` follows
  `lab_sea/input/data.exf_YearlyFields` for the other forcing fields and links
  their files under `_1978` and `_1979` names in `prepare_run`.
- The lab_sea runoff-temperature case needs a `-mods` code directory with
  `ALLOW_RUNOFTEMP` defined, because the forward build uses the default
  `EXF_OPTIONS.h`.

**Coverage limits:**

- No LLC experiment exists in `verification/`.
- Adjoint builds (`input_ad.*` of cs32) are not run in phase 1.
- A local pass supports only the exercised grids and layouts.
- Target placement (`RNF_INIT_FIXED`) and the layouts it has run on:
  - The sparse = dense oracles cover lab_sea (lat-lon, no exch2) and cs32
    with `W2_mapIO = -1`, where every tile fits the global I/O array.
  - The placement probe checks 80 fixed cells per layout on cs32 with
    `W2_mapIO` = -1, 0 and 1. With 0 it executes the branch for a tile taller
    than the global array (one long line). In the runs with 0 and 1 the dense
    inputs of cs32 are read in a layout they were not written for, so those
    runs test the placement only and are not model runs to compare.
  - The branch for a facet wider than the global array (the fold of a
    compact LLC layout) cannot be reached on cs32. It is compiled and has
    never run. A sparse = dense run in a compact layout needs every binary
    input of an experiment rewritten in that layout. Both are left to
    RUNOFF-023.
  - No test has a blank exch2 tile or facets of unequal size.
- The 10-digit cs32 oracle does not resolve a one-cell move of the weakest
  targets. The figures of this item were measured during RUNOFF-004 by
  review A on the 4-process binary; no configured test repeats them. One
  target was moved by one cell, with the area of the new cell written in the
  file, and the run was compared with the unmoved sparse run. "Seen" means
  that `cg2d_init_res` changes by more than 1e-10. It is a comparison of two
  runs, not a run of the oracle against its reference.

  | Sample | Targets moved | Seen | Change of `cg2d_init_res` |
  |---|---|---|---|
  | round 1 | smallest flux (1.5e-7 m³/s) | no | 9.3e-12 |
  | round 1 | 1st percentile (0.031 m³/s) | no | 2.1e-11 |
  | round 1 | 10th percentile (9.6 m³/s), median (279 m³/s) and largest (35,420 m³/s) | 3 of 3 | 3.4e-9, 4.9e-8 and 2.7e-6 |
  | round 3 | 8 targets from the 2nd to the 9th percentile (0.26 to 7.4 m³/s) | 7 of 8 | seen: 2.7e-10 to 4.9e-9; not seen: the 3rd-percentile target (0.61 m³/s), 8.8e-11 |
  | round 3 | 23 targets from the 10th to the 98th percentile (9.6 to 6454 m³/s) | 23 of 23 | 3.5e-9 to 1.6e-6 |

  Each sample is one move per target, not every target or every direction.
  What follows for the tests:
  - No comparison of model output detects a one-cell move of the weakest
    targets. The oracle does not see it at 10 digits. A direct comparison of
    two runs cannot tell it from round-off: a one-ulp change of the input
    flux leaves `cg2d_init_res` unchanged or moves it by 1.1e-11 to 2.1e-11
    (nine patterns, in the item on round-off below), which is as much as the
    move of the smallest or of the 1st-percentile target.
  - The placement probe is not a check of the runoff targets. It checks where
    the reader places 80 fixed cells per layout, the four corners of every
    tile and fixed interior positions, and it does not read the runoff file.
    In the 192 × 32 layout, 16 of those 80 cells are also cells of the 1189
    cs32 targets and the other 1173 target cells are not probed (computed in
    RUNOFF-004 round 2 from the probe's cell selection and the target table;
    not a configured test). A misplacement confined to cells that the probe
    does not sample, of targets that carry only weak flux, is seen by neither
    the probe nor the digit-match oracle.
  - What protects the real targets is the area check of `RNF_INIT_FIXED`,
    when the file has `target_cell_area`. Every committed sparse file has it;
    the schema makes it optional. Configured tests run that check on
    lab_sea (case `cell_area`, an area off by 1 %) and on the probe cells.
    For the cs32 targets the evidence is review A's and not a configured
    test. With the area left as written for the original cell, the moves of
    the smallest and of the 1st-percentile target were refused and all 4
    processes stopped. Of the 4516 one-cell shifts of the 1189 targets inside
    their tile, the check would refuse 4458, those where the two cells differ
    in area by more than 1e-4. The other 58 shifts, and any file without
    `target_cell_area`, have no such protection.
- Only a file with one constant record can be read. No test has time records,
  temperature, salinity or tracers in the model.
- The code under `#ifdef ALLOW_SHELFICE` in `RNF_INIT_FIXED` (the `kTopC`
  refusal) is not compiled in any tested build: no experiment compiles both
  `rnf` and `shelfice`.
- Multi-threaded runs (`eedata.mth`) of the package are not tested.
- Response of the cs32 experiment to round-off, measured during RUNOFF-004 by
  the implementer (single-process) and by review A (4 processes); no
  configured test repeats these measurements:
  - Sparse against dense. Single-process: 200 of 207 monitor quantities are
    equal in every printed digit; `cg2d_init_res` is equal for nine steps and
    differs by 5.4e-13 at the tenth. On 4 processes: 9 of 1458 monitor lines
    differ, `cg2d_init_res` by 5.4e-13.
  - Computed offline from the files and the grid, not in the model: the
    sparse field (flux·fraction)/rA is within one unit in the last place of
    the dense record (146 of 1189 cells differ, by at most 1.8e-16 relative),
    and so is fac·d + (1 − fac)·d, the interpolation exf makes between two
    identical records d.
  - One-ulp changes of the input flux, the sparse run against the unchanged
    sparse run. Each pattern changes the flux of every eighth source (148 or
    149 sources).
    - Single-process, one pattern moved up: `cg2d_init_res` changes by
      1.7e-11, and 44 of 207 quantities differ.
    - On 4 processes, nine patterns. Eight disjoint patterns moved up change
      `cg2d_init_res` by 1.66e-11, 0, 1.11e-11, 0, 0, 0, 2.02e-11 and 0. One
      pattern moved down changes it by 2.05e-11.
    - So five of the nine leave `cg2d_init_res` unchanged, and four move it
      by 1.1e-11 to 2.1e-11. Of the five, four leave every printed monitor
      digit unchanged and one changes 2 monitor lines.

  The sparse-against-dense difference of 5.4e-13 is therefore no larger than
  round-off in the input can produce, which is nothing or 1.1e-11 to 2.1e-11
  on `cg2d_init_res`. A difference of up to 2.1e-11 between two runs of this
  experiment can come from round-off alone.
- Refusals in the code that no configured test runs. The two lists below were
  made by reading every stop of `rnf_readparms.F`, `rnf_check.F`,
  `rnf_init_fixed.F` and `rnf_nc_utils.F` against the cases of
  `tests/rnf/refusal_check.py` and the runs of `tests/rnf/placement_probe.py`.
  Every stop of those four files is either run by a configured case (rows
  "Configuration refusals of `pkg/rnf`" and "Refusals that need the file") or
  listed here.
  - Configuration refusals (eight):
    - `runoftempfile` set: the lab_sea build has no `ALLOW_RUNOFTEMP`, so
      `EXF_CHECK` stops the run before `RNF_CHECK` is reached. It needs a
      build with that option, such as cs32.
    - `ALLOW_RUNOFF` undefined, `pkg/exf` not compiled, `HAVE_NETCDF`
      undefined and `USE_OLD_EXTERNAL_FORCING` defined: each needs a build of
      its own.
    - `SHI_update_kTopC` with `useShelfIce`: no experiment compiles both
      `rnf` and `shelfice`.
    - `RNF_useYearlyFiles=.TRUE.` and an `RNF_period` other than 0 in
      `data.rnf`.
  - File refusals:
    - A file that cannot be opened, in `RNF_INIT_FIXED` or in
      `RNF_NC_READ_FLUX`. No case of `refusal_check.py` has one. The first
      run of each placement probe relies on the stop in `RNF_INIT_FIXED` and
      checks its message in the log of process 0 only.
    - The file as a whole: a missing dimension (`time`, `source` or
      `target`); a missing `mitgcm_runoff_schema_version`,
      `mitgcm_time_sampling` or `mitgcm_grid_ny` (a missing `mitgcm_grid_nx`
      is run); a schema major version other than 1; `constant` sampling with
      a number of records other than 1; a file with no source or no target;
      `runoff_flux` without the dimensions `(time, source)`; a missing
      required variable other than `target_fraction` (`source_id`,
      `target_source`, `target_cell`, `runoff_flux`).
    - Attributes: a text attribute that is not of type char or is longer
      than 80 characters; `mitgcm_grid_nx` or `mitgcm_grid_ny` stored as text
      or with several values; `_FillValue` or `missing_value` of the flux
      with several values, or refused by NetCDF when read (the text
      `missing_value` is run).
    - Targets: one beyond an open boundary (`maskInC` = 0) or under an ice
      shelf (`kTopC` ≠ 0); one on no tile, which the fraction sum catches (a
      blank exch2 tile, or a cell of the global layout that no facet uses).
    - A NetCDF error while the length of a dimension, an attribute, a table,
      an optional variable, the dimensions of the flux or a flux record is
      read, or while the file is closed.

  Review A ran three of the file refusals by hand on cs32 in round 1, and
  they refused as written: a grid size attribute stored as text, one with two
  values, and a missing `mitgcm_grid_ny`. They are in no configured test.
- The references of `lab_sea/input` and of the cs32 cases come from another
  platform. On the local container platform they agree to 11 to 13 digits on
  `cg2d_init_res`, so these oracles show agreement to the testreport
  threshold and cannot show that a result is unchanged in every bit. The
  references of the dense lab_sea cases were made on the local platform.
  - This band was measured on the previous host (Docker on WSL2). Re-measured on
    the current host (podman on Oracle Linux 9) on 2026-10-04, `lab_sea input`
    gives 11 digits on `cg2d_init_res` against the required 10, and 16 digits on
    most monitor fields (13 on `dynstat_uvel_mean` and `dynstat_vvel_mean`), so
    the band still holds and the threshold needs no recalibration. The dense
    lab_sea references, made on the previous host, have not yet been re-measured
    here; the first `-mpi` and cs32 runs on this host will say whether they
    agree as closely.

**Sensitivity:** a dropped fraction, off-by-one global index or wrong tile
mapping changes the runoff in at least one cell by O(1). The digit-match oracles
detect such an error only when it moves enough flux.

- **lab_sea:** the configured control with every flux set to zero matches the
  dense reference to 2 digits. Review B of RUNOFF-004 moved each of the seven
  targets by one cell (6144 to 17,429 m³/s to the cell) and found 1 or 2
  matching digits each time; that is not a configured test.
- **cs32:** in review A's samples (coverage limits) a one-cell move was seen
  at 10 digits for the three targets measured in round 1 at and above the
  10th percentile, and for all 23 measured in round 3 from the 10th to the
  98th percentile. Below the 10th percentile, 7 of 8 were seen in round 3,
  and the smallest and the 1st-percentile target of round 1 were not. A move
  confined to those weakest targets stays within the response of the
  experiment to round-off (nothing, or 1.1e-11 to 2.1e-11 on
  `cg2d_init_res`), and no comparison of model output detects it.
- **Placement probe:** `tests/rnf/placement_probe.py` does not close that
  gap. It checks where the reader places 80 fixed cells per layout and does
  not read the runoff file. A misplacement confined to cells that it does not
  sample, of targets that carry only weak flux, is seen by neither the probe
  nor the digit-match oracle. The area check refuses most such misplacements
  when the file has `target_cell_area` (coverage limits).
- **Refusals:** the negative tests confirm the refusal paths that they run,
  those of the rows "Configuration refusals of `pkg/rnf`" and "Refusals that
  need the file". The refusals that no configured test runs are listed in the
  coverage limits under "Refusals in the code that no configured test runs".
