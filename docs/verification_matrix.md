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
| Sparse = dense, cubed sphere, runoff temperature and time records | converted `core_rnof_1_cs32.bin` + `runoff_temperature.bin` (`input.rnof_sparse/runoff_sparse.nc`, 12 records) | `results/output.seaice.txt`, `results/output.icedyn.txt` | round-off from flux·frac/rA vs precomputed m/s | new `input.<X>` via `tests/mitgcm_oracle.sh … [-mpi 4]` (RUNOFF-006, RUNOFF-013). The time handling it needs exists (RUNOFF-005); what is left is the cs32 input directory and the runoff-temperature term. Note the recorded limit that all 12 cs32 records are identical in time, so this oracle cannot detect a timing error | local | yes |
| Dense runoff baseline, lat-lon, constant runoff (**configured**) | `lab_sea/input.rnof_const`: `runoffperiod = 0`, 48 steps; seven coastal source cells, one group spanning the tile and MPI process boundary between columns 9 and 10 | `results/output.rnof_const.txt` (single-process dense run) | digit threshold; the `-mpi 2` run must match the single-process reference | `tests/mitgcm_oracle.sh lab_sea input.rnof_const` and `tests/mitgcm_oracle.sh lab_sea input.rnof_const -mpi 2` | local | yes |
| Dense runoff baseline, daily records, non-repeating (**configured**) | `lab_sea/input.rnof_daily`: `runoffperiod = 86400`, `runoffRepCycle = 0`, 32 days, monitor every 12 h; records 1 to 34 read, 1 to 33 with non-zero weight | `results/output.rnof_daily.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_daily` and `tests/mitgcm_oracle.sh lab_sea input.rnof_daily -mpi 2` | local | yes |
| Dense runoff baseline, repeating monthly climatology (12 calendar-month records repeated every year) (**configured**) | `lab_sea/input.rnof_month`: `runoffperiod = -12`, 61 days from 1 January, crossing two month boundaries and two mid-month record changes; records 12, 1, 2, 3 read, all with non-zero weight | `results/output.rnof_month.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_month` and `tests/mitgcm_oracle.sh lab_sea input.rnof_month -mpi 2` | local | yes |
| Dense runoff baseline, calendar-month records, non-repeating (**configured**) | `lab_sea/input.rnof_month1`: `runoffperiod = -1`, `runoffstartdate1 = 19781201`, 61 days from 1 January, crossing two month boundaries; records 1 (December 1978) to 4 (March 1979) read, all with non-zero weight | `results/output.rnof_month1.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_month1` and `tests/mitgcm_oracle.sh lab_sea input.rnof_month1 -mpi 2` | local | yes |
| Dense runoff baseline, 12 equally spaced records with a repeat cycle (**configured**) | `lab_sea/input.rnof_clim`: `runoffperiod = 2628000`, `runoffRepCycle = 31536000` (365 days), 50 days from 1 December, wrapping from record 12 to record 1; records 11, 12, 1, 2 read, all with non-zero weight | `results/output.rnof_clim.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_clim` and `tests/mitgcm_oracle.sh lab_sea input.rnof_clim -mpi 2` | local | yes |
| Dense runoff baseline, yearly `_YYYY` files (**configured**) | `lab_sea/input.rnof_yearly`: `useExfYearlyFields`, daily records, 26 days from 20 December, monitor every 12 h; records 354 to 365 of `runoff_yearly_1978` and 1 to 16 of `runoff_yearly_1979` read, of which 354 to 365 and 1 to 15 have non-zero weight | `results/output.rnof_yearly.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_yearly` and `tests/mitgcm_oracle.sh lab_sea input.rnof_yearly -mpi 2` | local | yes |
| Runoff timing, direct check, dense and sparse (**configured**) | the run directories of the **six dense** `lab_sea/input.rnof_*` cases (`clim`, `const`, `daily`, `month`, `month1`, `yearly`) and of the **six sparse** `input.rnof_sp_*` ones, single-process and `-mpi 2`; needs the oracle runs above to have been made. Every sparse case sets `RNF_debugLev = 3`, so its run leaves one `RNF_FIELDS_LOAD` trace line per forcing step naming the two records, their file years and the weight, printed with 17 significant digits | **dense:** the four `exf_runoff_*` monitor statistics at every monitor time, against the field predicted here from the case's `data.exf` under the pkg/exf timing conventions; this is what qualifies the model of those conventions. **sparse:** the records and the weight of the trace, at every forcing step, against what the same conventions give for the same model time taken from the case's **dense twin** (`input.rnof_sp_daily` against `input.rnof_daily`). A sparse case has no `exf_runoff_*` monitor to compare — exf writes those only for a dense file and `pkg/rnf` has no monitor of its own yet (RUNOFF-015) — so what is judged is the record selection itself, which is the question this issue is about. `input.rnof_sp_const` is judged too (record 1, weight 1, at every step); a sparse case with no dense twin would be a `SKIP`, neither a pass nor a failure, and there is none today | dense: 1e-12 relative to the largest runoff value. sparse: the records must be equal and the weight within `WEIGHT_TOLERANCE` = 1e-12, far below the 1/24 a one-hour error in a daily record gives. A sparse run with fewer than `MIN_TRACE` = 10 trace lines fails rather than passing over no samples, and a run with no dense or no sparse case fails. Measured 2026-10-05, single-process and `-mpi 2`: 0 of 49, 769, 1465, 1465, 1201 and 625 steps disagree for const, daily, month, month1, clim and yearly, largest weight error 0.0e+00. Negative control, measured on the same day: `RNF_startDate1 = 19781231` added to `input.rnof_sp_daily/data.rnf` (record 1 one day early) gives 769 of 769 steps disagreeing, the first with model records (2, 3) against exf's (1, 2), and exit 1; the same shift one day *late* is refused by exf's own `EXF_GetFFieldRec` before the run starts. What a sparse verdict does not cover is the field those records produce: the two rows below | `{python} tests/runoff/lab_sea_runoff_timing_check.py` and `... --mpi 2` | local | yes |
| Sparse = dense, lat-lon, constant runoff (**configured**) | `lab_sea/input.rnof_sp_const`: the set-up of `input.rnof_const` with `useRNF`, no dense `runoffFile`, and `../input.rnof_const/runoff_sparse.nc` (4 grouped sources, 7 targets; `baffin` spans the tile and MPI process boundary, `labrador` a tile boundary); single-process (4 tiles) and `-mpi 2`. The one-source-per-cell file `runoff_sparse_cells.nc` runs as case `cells_equal_dense` of `tests/rnf/refusal_check.py`, the same run with every flux set to zero as case `zero_flux_differs`, and that file with every source split into two that share its cell (a third and two thirds of its flux, 14 sources and 14 target entries on 7 cells) as case `two_sources_one_cell`, the only case in which the model adds two contributions into one cell | `results/output.rnof_sp_const.txt`, a copy of the dense `results/output.rnof_const.txt`; the three cases of the check script use the dense reference itself | digit threshold (10 on `cg2d_init_res`). Measured: 16 digits on every checked variable, single-process and `-mpi 2`, for the grouped and the per-cell file; 16 digits for the two-sources-on-one-cell file. Negative control: with zero flux only 2 digits match, so the comparison is sensitive to the runoff | `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_const` and `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_const -mpi 2`; `{python} tests/rnf/refusal_check.py [--mpi 2]` | local | yes |
| Sparse = dense, lat-lon, daily records, non-repeating (**configured**) | `lab_sea/input.rnof_sp_daily`: the set-up of `input.rnof_daily` with `useRNF`, no dense `runoffFile` and none of its four dense `runoff*` timing settings, reading `../input.rnof_daily/runoff_sparse.nc`: 40 daily records from 1 January 1979 00:00, `mitgcm_time_sampling = "fixed"` with `mitgcm_time_period = 86400` and repeat `none`; 32 days, 768 forcing steps. Every timing value comes from the file's own time axis, except `RNF_useYearlyFiles`, which no file can carry. Single-process and `-mpi 2` | **its own** `results/output.rnof_sp_daily.txt`, taken from its own single-process run, **not** the dense reference. Measured 2026-10-05: the applied runoff field agrees with the dense one to 4.3e-16 at every forcing step of all five cases (row "Sparse = dense applied field per time mode"), and lab_sea still amplifies that round-off over the run into 4 matching digits of `cg2d_init_res` against the dense reference (daily 4, month 16, month1 3, clim 16, yearly 4 of the 10 required), so a digit threshold on a chaotic month of sea ice cannot be the sparse = dense oracle in either direction. The own reference is the regression guard; the sparse = dense property is carried by the applied-field and record-selection rows | digit threshold against its own reference, which the `-mpi 2` run has to match as well: measured 16 digits on 1 and on 2 processes | `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_%s` and `... -mpi 2` | local | yes |
| Sparse = dense, repeating monthly climatology (`period = -12`) (**configured**) | `lab_sea/input.rnof_sp_month`: the set-up of `input.rnof_month` with `useRNF`, no dense `runoffFile` and none of its four dense `runoff*` timing settings, reading `../input.rnof_month/runoff_sparse.nc`: 12 calendar-month records, `monthly` sampling with `mitgcm_time_repeat = "annual"`, which the reader maps to exf's `runoffperiod = -12`; 61 days from 1 January, 1464 forcing steps. Every timing value comes from the file's own time axis, except `RNF_useYearlyFiles`, which no file can carry. Single-process and `-mpi 2` | **its own** `results/output.rnof_sp_month.txt`, taken from its own single-process run, **not** the dense reference. Measured 2026-10-05: the applied runoff field agrees with the dense one to 4.3e-16 at every forcing step of all five cases (row "Sparse = dense applied field per time mode"), and lab_sea still amplifies that round-off over the run into 16 matching digits of `cg2d_init_res` against the dense reference (daily 4, month 16, month1 3, clim 16, yearly 4 of the 10 required), so a digit threshold on a chaotic month of sea ice cannot be the sparse = dense oracle in either direction. The own reference is the regression guard; the sparse = dense property is carried by the applied-field and record-selection rows | digit threshold against its own reference, which the `-mpi 2` run has to match as well: measured 16 digits on 1 and on 2 processes | `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_%s` and `... -mpi 2` | local | yes |
| Sparse = dense, calendar-month records, non-repeating (`period = -1`) (**configured**) | `lab_sea/input.rnof_sp_month1`: the set-up of `input.rnof_month1` with `useRNF`, no dense `runoffFile` and none of its four dense `runoff*` timing settings, reading `../input.rnof_month1/runoff_sparse.nc`: 6 consecutive calendar months from December 1978, `monthly` sampling with repeat `none`, mapped to exf's `runoffperiod = -1`; 61 days, 1464 forcing steps. Every timing value comes from the file's own time axis, except `RNF_useYearlyFiles`, which no file can carry. Single-process and `-mpi 2` | **its own** `results/output.rnof_sp_month1.txt`, taken from its own single-process run, **not** the dense reference. Measured 2026-10-05: the applied runoff field agrees with the dense one to 4.3e-16 at every forcing step of all five cases (row "Sparse = dense applied field per time mode"), and lab_sea still amplifies that round-off over the run into 3 matching digits of `cg2d_init_res` against the dense reference (daily 4, month 16, month1 3, clim 16, yearly 4 of the 10 required), so a digit threshold on a chaotic month of sea ice cannot be the sparse = dense oracle in either direction. The own reference is the regression guard; the sparse = dense property is carried by the applied-field and record-selection rows | digit threshold against its own reference, which the `-mpi 2` run has to match as well: measured 16 digits on 1 and on 2 processes | `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_%s` and `... -mpi 2` | local | yes |
| Sparse = dense, fixed-period climatology with a repeat cycle (**configured**) | `lab_sea/input.rnof_sp_clim`: the set-up of `input.rnof_clim` with `useRNF`, no dense `runoffFile` and none of its four dense `runoff*` timing settings, reading `../input.rnof_clim/runoff_sparse.nc`: 12 records of 2628000 s from 16 January 1978 12:00, `fixed` sampling with repeat `annual`, whose cycle the reader takes from the span of `time_bnds` (365 days) and anchors on the real date of record 1; 50 days from 1 December, wrapping record 12 to record 1, 1200 forcing steps. Every timing value comes from the file's own time axis, except `RNF_useYearlyFiles`, which no file can carry. Single-process and `-mpi 2` | **its own** `results/output.rnof_sp_clim.txt`, taken from its own single-process run, **not** the dense reference. Measured 2026-10-05: the applied runoff field agrees with the dense one to 4.3e-16 at every forcing step of all five cases (row "Sparse = dense applied field per time mode"), and lab_sea still amplifies that round-off over the run into 16 matching digits of `cg2d_init_res` against the dense reference (daily 4, month 16, month1 3, clim 16, yearly 4 of the 10 required), so a digit threshold on a chaotic month of sea ice cannot be the sparse = dense oracle in either direction. The own reference is the regression guard; the sparse = dense property is carried by the applied-field and record-selection rows | digit threshold against its own reference, which the `-mpi 2` run has to match as well: measured 16 digits on 1 and on 2 processes | `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_%s` and `... -mpi 2` | local | yes |
| Sparse = dense, yearly `_YYYY` files (**configured**) | `lab_sea/input.rnof_sp_yearly`: the set-up of `input.rnof_yearly` with `useRNF`, no dense `runoffFile` and none of its four dense `runoff*` timing settings, reading `../input.rnof_yearly/runoff_sparse.nc`: `runoff_sparse_1978.nc` and `runoff_sparse_1979.nc`, 365 daily records each at 1 January 00:00 + k days, read through `RNF_useYearlyFiles` as `<base>_YYYY.nc`; 26 days from 20 December, crossing into the next year's file, 624 forcing steps. Every timing value comes from the file's own time axis, except `RNF_useYearlyFiles`, which no file can carry. Single-process and `-mpi 2` | **its own** `results/output.rnof_sp_yearly.txt`, taken from its own single-process run, **not** the dense reference. Measured 2026-10-05: the applied runoff field agrees with the dense one to 4.3e-16 at every forcing step of all five cases (row "Sparse = dense applied field per time mode"), and lab_sea still amplifies that round-off over the run into 4 matching digits of `cg2d_init_res` against the dense reference (daily 4, month 16, month1 3, clim 16, yearly 4 of the 10 required), so a digit threshold on a chaotic month of sea ice cannot be the sparse = dense oracle in either direction. The own reference is the regression guard; the sparse = dense property is carried by the applied-field and record-selection rows | digit threshold against its own reference, which the `-mpi 2` run has to match as well: measured 16 digits on 1 and on 2 processes | `tests/mitgcm_oracle.sh lab_sea input.rnof_sp_%s` and `... -mpi 2` | local | yes |
| Hold-exact mode, direct check (**configured**) | the `lab_sea_hold` case of `tests/rnf/applied_field_check.py`, single-process and `-mpi 2`: `lab_sea/input.rnof_sp_daily` (40 daily records, 768 forcing steps) with `RNF_holdRecord = .TRUE.` added to `data.rnf`, dumping the applied `EXFroff` every step | the input values themselves: each dump must equal `Σ flux·frac/rA` of **one** record of the file, the one `RNF_FIELDS_LOAD` reported it held, with no combination of two. No dense oracle exists, because exf has no hold-exact mode | **bitwise** (`--rtol 0`): with a weight of exactly 1 or exactly 0 the model copies a record rather than combining two, so the reconstruction is exact and not merely close. Measured 2026-10-05: 768 dumps bitwise equal, 0 extra, 0 missing, on 1 and on 2 processes. Sensitivity measured independently: the same case run against the **dense interpolating** path differs by 5.1e-1 relative (daily) and 3.3e+0 (clim_long), which is what the `--control` of `tests/rnf/timing_field_check.py` asserts, so hold-exact is a different field by tens of per cent and not a rounding of interpolation | `{python} tests/rnf/applied_field_check.py --case lab_sea_hold` (and `--mpi 2`) | local | yes |
| Refusals that need the file (**configured**) | scratch inputs layered on `lab_sea/input`, each with a copy of `input.rnof_const/runoff_sparse.nc` that has one violation. Table entries: `target_cell` = -3 and = nx·ny; `target_source` = -1 and = number of sources; `target_level` = 2; a fraction of -0.25 and one that is not a number; a fraction of -0.25 hidden by two others in a sum of exactly 1. Targets: one moved to a land cell of the western half of the grid; `target_cell_area` off by 1 %; a fraction sum of 0.999. The file: `mitgcm_grid_nx` = 21; no `mitgcm_grid_nx`; no `target_fraction` variable. The time axis, seventeen cases built on the valid daily axis of `refusal_check.timed_axis` except the first (the eighteenth enrolled time guard, `yearly_repcycle`, is counted apart at the end of this column: it breaks a `data.rnf` combination and not the axis): `mitgcm_time_sampling` = `yearly` (no pkg/exf mode); `mitgcm_time_repeat` = `biennial`; `fixed` without `mitgcm_time_period`; `time:units` in fortnights; a reference date of `0001-01-01`, which precedes pkg/cal's own and must not be handed to it (carry-forward of RUNOFF-002); `calendar` = `360_day`, which is not this run's; `calendar` = `julian`, which is not a calendar pkg/cal has; a `fixed` climatology with no `time_bnds` to take the cycle from; a repeat cycle of 4 days over 3 daily records; a monthly climatology with 3 records instead of 12; a monthly climatology whose record 1 is in February; `RNF_startTime` set with pkg/cal; no `mitgcm_time_sampling` attribute at all, which the schema marks required; `constant` sampling with 3 records, which would apply record 1 for ever and ignore the rest; a `time` variable with no `units` attribute (distinct from units that cannot be parsed); a reference date with a seventh number, which is a fraction of a second or a time-zone offset and is refused rather than dropped; and a `time_bnds` that is one-dimensional, so it has no first and last bound pair to take the cycle from. The series too short for the run: one `fixed` record with no repeat, so the first step already needs record 2. A data.rnf combination on the committed yearly set: `RNF_useYearlyFiles` with a repeat cycle, which round 0 wrongly recorded as unreachable. The flux: not a number, infinite, 1e31, equal to a numeric `missing_value` of -9999, equal to the `_FillValue` of a float32 variable, 9999 with `missing_value` stored as the text "9999.", and 2e7 m³/s, twice `RNF_srcFluxMax`, which is present and finite and refused for its magnitude alone (`flux_above_source_max`, RUNOFF-030). The per-cell **aggregate** of the applied field (`cell_above_vol_max`, RUNOFF-040): four sources each carrying *exactly* `RNF_srcFluxMax` with every target collapsed onto one cell, `target_cell_area`/`target_lon`/`target_lat` moved with them and the fractions left alone, so every init check sees a consistent file and the aggregate — 1.285228e-3 m/s, 2.31 times `RNF_cellVolMax` of that cell's top-layer volume per step — is the only thing wrong with it. Built from its description and measured on the RUNOFF-030 build first: it ended normally, exit 0, zero `EXF WARNING` lines, flux sums both 4.0e7 m³/s, one non-zero cell holding 1.2852284e-3 m/s. The exf freshwater bound with `useRNF` on and no runoff at all: `precipfile` blanked, `precipconst` = 1e-4 m/s and every flux of the file zeroed, so the quantity the relaxed `sflux` test sees is exactly `evap - precip` and must still be refused (`sflux_out_of_range`, RUNOFF-030 correction round 1). Array bounds: synthetic files with `RNF_nSrcTile` + 1 = 2001 sources on one cell (target table read in three chunks) and with `RNF_nTgtTile` + 1 = 10001 entries on one cell. The runoff tracers (RUNOFF-013): a `runoff_ptracer_ghost` variable in a run whose one ptracer is called `dye`, which matches no `PTRACERS_names` entry (`ptracer_unknown`), and a `runoff_ptracer_dye` variable in a run that does not use pkg/ptracers (`ptracer_off`); and, added in correction round 1 after review B fired them by hand, a variable called exactly `runoff_ptracer_` with no name after the prefix (`ptracer_name_empty`), one whose name is 65 characters, one more than `RNF_idLen` (`ptracer_name_long`), and six `runoff_ptracer_*` variables, one more than `RNF_nTr` (`ptracer_too_many`); and, added in correction round 2 from review B's measurements, the three at-the-bound companions of those, in which the guard must stay **silent** and the run is refused by the `usePTRACERS` test that follows it — a 1-character name (`ptracer_name_min`), a name of exactly `RNF_idLen` = 64 characters (`ptracer_name_max`) and exactly `RNF_nTr` = 5 tracer variables (`ptracer_count_max`), the first two differing from their over-the-bound twin in one character of the variable name. Single-process and on 2 MPI processes | a run that does not end normally: the expected `RNF_INIT_FIXED`, `RNF_NC_ERROR`, `RNF_NC_READ_FLUX` or `RNF_NC_ATT_REAL` error text, naming the source id where a source is concerned, the table entry for `target_source`, and, for the seventeen time-axis cases, the `RNF_TIME_SETUP` text that names the rule broken; one `STOP` line per process. The too-short-series case is refused in `RNF_NC_READ_FLUX`, where the record is read, and not at init, because its header is valid. Land, cell area and array bounds are seen by the process that owns the tile only: its message must be in the `STDERR.*` of at least one process, the summed count in that of every process, and every process must stop within the timeout (no hang). The hidden negative fraction must be refused by its range and not reach the fraction sum. In the seven flux cases the flux sums of `RNF_INIT_VARIA` must not be printed. `flux_above_source_max` additionally forbids both missing-value messages and the `EXF WARNING: runoff out of range` line, so it cannot pass because the value was taken as missing or because the exf check — whose runoff upper bound is skipped here — was what stopped the run. `sflux_out_of_range` is the one case judged on `pkg/exf` output instead: `EXF_CHECK_RANGE` writes to standard output, not through `PRINT_ERROR`, so its three expected lines (`sflux out of range`, `precip out of range`, `then set useExfCheckRange=.FALSE.`) are standard-output expectations and its `STOP` is `ABNORMAL END: S/R EXF_CHECK_RANGE`; it forbids the runoff warning, the m/yr advisory and the pkg/rnf magnitude refusal, so it cannot pass for any of those reasons. The `precip` warning fires too at 1e-4 m/s and is asserted so it cannot vanish unnoticed; what makes the case decisive for `sflux` is the **presence** of the `sflux` line, because a removed `sflux` test would leave the `precip` line and the stop exactly as they are. **Every normal-end case also asserts the five `RNF_SUMMARY` "which bounds applied" lines, `flux_at_source_max` the `RNF_srcFluxMax` parameter line and `cell_at_vol_max` the `RNF_cellVolMax` one** (the first four lines in correction round 3 of RUNOFF-030, review B; the fifth with RUNOFF-040): until then nothing observed that report, so deleting it would have failed no case — the same reasoning this matrix applies to every other claim. `cell_above_vol_max` is judged on `PRINT_ERROR` output and `ABNORMAL END: S/R RNF_EXF_RUNOFF`, with the cell line, the applied value, the limit and the cell's `XC,YC` in the `STDERR` of the owning process (`stderr_any`, because the local `bi` differs between the serial and the `-mpi 2` layouts) and the reduced tally in that of **every** process; it forbids the per-source refusal, every init check the collapse walks past and every `EXF WARNING`, so it cannot pass for an adjacent reason. Measured on `-mpi 2`: two `STOP` lines, the cell named by process 0001 as `(i,j,bi,bj) = (3,3,1,1)` and both processes printing the tally, with no hang — which is what the `GLOBAL_SUM_INT` before the stop is for. Its control `cell_at_vol_max` runs the same collapse at 0.99 of the bound and must end normally; it does **not** pin the guard's `.LE.` against a `.LT.`, because a control on the last bit of a product of three reals would measure the compiler's rounding, and unlike `RNF_srcFluxMax` this bound carries no promise that a file may sit exactly on it. `cell_above_vol_max` was measured **failing** on a mutant with `RNF_cellVolMax` ten times too large, where the run ends normally and none of the six expected lines appears. The text `missing_value` case fails on the code before the round-1 correction, where the run ended normally with 9999 m³/s applied | exact substring match per file; one `STOP` line per process; run time below `--timeout` (default 600 s). **The two tracer refusals have two controls that must end normally**, because a refusal that fired on any tracer variable at all would pass without them: `ptracer_match`, the same file with the name the ptracer really has, which must run, report `runoff tracer 1 is runoff_ptracer_dye, applied to ptracer 1` and `RNF_nTrUse = 1` in the summary, and is the only configured run that reaches `RNF_TENDENCY_APPLY_PTR`; and `ptracer_ignored`, the unmatched name with `RNF_usePtracers = .FALSE.`, which must run with `RNF_nTrUse = 0` and say per variable what it did not apply -- the counterfactual of the guard, and the measurement that the switch has an effect, which it did not before RUNOFF-013. **The three at-the-bound cases are judged by the error they do raise and the tally**, not by silence alone: each expects the `usePTRACERS` message naming its own variable -- printed at a site reachable only past the guard under test -- and forbids all three guard messages, with `ptracer_count_max` asserting 5 fatal errors where `ptracer_too_many` asserts 7. **`flux_above_source_max` has an at-the-bound companion among the normal-end runs**, `flux_at_source_max`: the same source carrying exactly `RNF_srcFluxMax`, which must get past the guard (holding its `.GT.` back from a `.GE.`, the direction a weakened-bound mutant cannot measure) and must then be applied, which the flux sums assert. **It is also the enrolled acceptance of the exf relaxation**: the applied field is 3.21e-4 m/s, 321 times what pkg/exf allows, and the run must end normally with `useExfCheckRange` at the lab_sea default `.TRUE.`, printing neither the runoff nor the `sflux` warning and no m/yr advisory. That needs **both** conditioned tests, and each was attributed by reverting it alone: with the `sflux` restore disabled (`IF ( .FALSE. )`) the case fails on the `sflux` warning, and with the runoff skip reverted (`.AND. .TRUE.`) it fails on `EXF WARNING: runoff out of range ... 0.321307089844219D-03`, the model's own print of the applied field. It runs one time step, from a `data` with `endTime=7200.` (lab_sea/input starts at 3600, so 3600 would be *zero* steps and would never reach `EXF_CHECK_RANGE` — measured, and it made the case pass vacuously once). `sflux_out_of_range` is the companion that holds the `sflux` change to being a restore: replacing it by a removal (`.AND. .NOT.useRNF` on the whole test) leaves `flux_at_source_max` passing and fails `sflux_out_of_range` on exactly the missing `sflux` warning | `{python} tests/rnf/refusal_check.py` and `{python} tests/rnf/refusal_check.py --mpi 2`. Measured 2026-10-06 (RUNOFF-040): **69 of 69 cases pass, single-process in 90.8 s and on `-mpi 2` in 114.7 s**, the single-process figure repeated inside the sealed focused pass, whose preceding command (`mitgcm_oracle.sh lab_sea input`) compiles `build_esx`, so the binary postdates every compiled source by construction (LL-011). The `-mpi 2` figure needed `mitgcm_oracle.sh lab_sea input -mpi 2` first, which is how the two-process binary is built. Previously 67 of 67, single-process (86 s) and `-mpi 2` (110 s), RUNOFF-030 correction round 1; and 64 of 64 (85.3 s and 106.3 s), correction round 2 of RUNOFF-013. **One process error worth keeping:** a `-mpi 2` rebuild does not rebuild `build_esx`, so a single-process run right after it can silently use a stale single-process binary — that is how a mutant binary briefly produced a spurious `flux_at_source_max` failure here (LL-011 again, in the one direction the staleness rule of `tendency_term_check.py` does not cover, because `refusal_check.py` has no such rule and relies on the suite ordering) | local | yes |
| Refusals that need the file, not yet run | every file refusal listed under "Refusals in the code that no configured test runs" in the coverage limits, among them a target beyond an open boundary (`maskInC` = 0) or under an ice shelf (`kTopC` ≠ 0): no experiment that compiles `rnf` has open boundaries or `pkg/shelfice`. An unknown tracer name is no longer here: RUNOFF-013 added the refusal and the row above runs it | expected fatal `RNF` error text in the run logs | exact message match | more cases (RUNOFF-017, RUNOFF-019, RUNOFF-020) | local | yes |
| Placement of 80 fixed probe cells per layout on exch2 tiles (**configured**) | `global_ocean.cs32x15` on 4 MPI processes, the set-up of `input.rnof_sp_icedyn` with a `data.exch2` that sets `W2_mapIO` = -1 (192 × 32), 0 (6144 × 1, one long line) and 1 (32 × 192, compact). 80 probe cells per layout, 20 per process: the 4 corners of each of the 12 tiles and 32 interior cells at fixed positions. The cells are chosen without regard to any runoff file, which the probe does not read; they are not the runoff targets (coverage limits). Each probe is a target with `target_cell_area` = 1 m², so the model refuses it and prints the cell index of the file with the `i,j,bi,bj` where it placed it. With `W2_mapIO` = 0 the long-line branch of the placement runs, which no other test executes | a placement computed in the test from exch2's own topology log of the same run (`w2_tile_topology.NNNN.log`: map size, facets, each tile's facet, offset and position on the map, the tiles of each process) with the definition of the layouts, not the record arithmetic of the model; the layout rule is first checked against exch2's "on Glob.Map" position of every tile. Second, the model's dense reader: a probe must be reported "on land" exactly where the bathymetry file holds a land value at that cell index. Control: with every index of the file raised by one, no probe may be reported on the cell predicted for the original index | the reported set of (cell, process, i, j, bi, bj) equals the predicted set, nothing missing and nothing extra; every process prints the count of 80 and stops; no timeout. Measured: 80 of 80 in each layout; land at 20, 22 and 22 probes, equal to the bathymetry file; control 0 of 80 | `{python} tests/rnf/placement_probe.py`, after `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.rnof_sp_icedyn -mpi 4` has built the binary | local | yes |
| Applied runoff field, cell by cell (**configured**) | `lab_sea/input.rnof_sp_const` on 1 and 2 processes and `global_ocean.cs32x15/input.rnof_sp_icedyn` on 1 and 4 processes, each as a scratch input that differs from the committed one only in output settings: a `data.diagnostics` with an `EXFroff` snapshot stream (`diag_mnc = .FALSE.`, `fileFlags = 'D'`, with the `useSingleCpuIO` the set-ups already have), and in `data` a `writeBinaryPrec` of 64 and `outputTypesInclusive`, so the dump and `RAC.data` are float64. `EXFroff` is filled by `EXF_DIAGNOSTICS_FILL`, which `EXF_GETFORCING` calls after `EXF_GETFFIELDS` (so after `RNF_EXF_RUNOFF` has copied `RNF_vflx` into the exf `runoff`) and before `EXF_MAPFIELDS`, so the dump is the field the model goes on to apply. One dump per time step: 48 for lab_sea, 10 for cs32 | an independent reconstruction of `Σ_s flux_s·frac_{s,c}/rA(c)` computed here in float64 from the sparse NetCDF file and the `RAC.data` of that same run, accumulated in the file's own table order, which is the order `RNF_FIELDS_LOAD` adds the terms in. This is what the digit oracle cannot do: it compares placement, not a norm, so a move that conserves mass is still a difference | extra cells, missing cells and the largest relative deviation; any non-zero extra or missing count fails, and the default `--rtol` of 0 requires the applied field to be **bitwise** the reconstruction. The `.meta` must say `float64`, a case needs at least 2 dumps (`--min-dumps` is itself range-checked, so a zero-sample PASS is unreachable) and every dump at least one non-zero cell, and a non-finite applied value is counted and turned into an infinite relative deviation rather than losing the `>` comparison. **The accumulation order the bitwise criterion rests on is held by an enrolled case** (RUNOFF-005). Neither committed file can hold it — both have at most one entry per cell (lab_sea 7 on 7, cs32 1189 on 1189) — so the `order_sensitive_sum` case generates a file that can, with `refusal_check.split_file(..., ulp=ULP_SHARE)`: every source of the per-cell file becomes three that share its cell, the two smaller ones sized at 0.35 ulp of the first term each, which is inside the window (0.25, 0.5) where one such term rounds away and the pair does not. The file-order and reversed sums then differ by exactly one ulp, and the case **asserts that difference on every run** before it accepts the forward comparison, so it cannot decay into a vacuous pass; two sub-sources could not do this at all, because a two-term floating-point sum is commutative. Measured 2026-10-05: `order_sensitive_ulps` = 1 and the applied field bitwise equal, on 1 and on 2 processes. This is also why `--rtol` must stay 0: a tolerance would hide that ulp. **Coverage limit:** the records themselves come from the model's own `RNF_FIELDS_LOAD` trace, so this row cannot see a wrong *choice* of record — only a wrong use of the records chosen; the choice is covered by the two timing rows above. The applied-volume invariant uses `VOLUME_RTOL` = 1e-12 and not bitwise equality, because dividing by a cell area and multiplying it back is not exact: it held exactly on the two constant files and is off by one ulp on the daily one. Measured 2026-10-05, every case bitwise equal with 0 extra and 0 missing: `lab_sea` 48 dumps × 320 cells and `cs32` 10 dumps × 6144 cells (1189 with runoff) as before, plus the timed cases `lab_sea_daily` (768 dumps over 33 distinct record brackets, the whole 40-record file's reach in a 32-day run) and `lab_sea_hold` (768 dumps, hold-exact), and `order_sensitive_sum` (48 dumps), each on 1 and on 2 processes. A timed case must make at least `min_records` distinct record selections (30 for the daily cases), so one that applied one record for ever could not pass. Control (run every time, verdict inverted): one target moved one cell in x with the coordinates dropped, lab_sea entry 0 (cell 52 → 53) and cs32 entry 1035 (cell 5247 → 5248, across the facet 2/3 boundary — the move the digit oracle passes at 10 of 10 digits) is detected on every dump as 1 extra and 1 missing cell with a relative deviation of 1 | `{python} tests/rnf/applied_field_check.py --case lab_sea` (and `--mpi 2`), `--case cs32` (and `--mpi 4`), `--case lab_sea_daily`, `--case lab_sea_hold` and `--case order_sensitive_sum` (each and `--mpi 2`), after the oracle run that built the binary | local | yes |
| Sparse = dense applied field per time mode (**configured**) | per case of `tests/rnf/timing_field_check.py`, a dense run of `lab_sea/input.rnof_<X>` and a sparse run of `input.rnof_sp_<X>` of the same case, both with an `EXFroff` snapshot stream dumping the applied runoff every step in float64; cases `daily`, `month`, `month1`, `clim`, `yearly` and `clim_long`, single-process, with `daily` and `clim_long` also on `-mpi 2` | the dense run itself, cell by cell at every step. This is the sparse = dense instrument for the timed modes, because the digit threshold is not one (see the five sparse rows above): it compares the quantity the issue is about, the applied field, where a wrong record, weight, repeat wrap or yearly file is a sizeable fraction of the runoff | `--rtol 1e-12`, four orders of magnitude above the 1e-16 round-off of `flux/rA` against the dense value and far below any wrong record. A case is refused unless it saw at least `--min-distinct` = 5 distinct applied fields, so a forcing that never changes cannot pass as a timing test. Measured 2026-10-05: 0 extra, 0 missing and a largest relative deviation of 4.156e-16 (daily, 768 dumps), 4.237e-16 (month, 1464), 4.189e-16 (month1, 1464), 4.241e-16 (clim, 1200), 3.712e-16 (yearly, 624) and 4.253e-16 (clim_long, 1800), each with as many distinct fields as dumps; daily and clim_long identical on `-mpi 2`. Control (`--control`, verdict inverted): the sparse run with `RNF_holdRecord = .TRUE.` must be **detected** as a difference, because holding a record is not interpolating between two — measured 5.104e-01 (daily) and 3.269e+00 (clim_long) relative, 15 orders of magnitude above the round-off | `{python} tests/rnf/timing_field_check.py --case daily --case month --case month1`, `... --case clim --case yearly`, `... --case daily --case clim_long --control` and `... --mpi 2 --case daily --case clim_long` (four commands, because all six cases in one took close to the 3600 s a suite command is allowed), after `tests/mitgcm_oracle.sh lab_sea input [-mpi 2]` has built the binary | local | yes |
| Gregorian anchoring of a fixed-period climatology (**configured**) | the `clim_long` case of `tests/rnf/timing_field_check.py`: `lab_sea/input.rnof_clim` and `input.rnof_sp_clim` restarted on 1 December 1981 for 75 days (1800 forcing steps), single-process and `-mpi 2` | two oracles. First the dense run, cell by cell at every step, as in the row above. Second, computed in Python from the dense records alone, the **four** nominal-year readings of `timing_field_check._nominal_fields`: `day_of_year` (the cycle stays the span of the bounds but the phase is the day of the model year), `record_dates` (each record at its own offset in seconds after 1 January of the model's year), `month_day` (each record at the same month, day and time of day in the model's year) and `start_year` (record 1 re-dated into the model's **start** year, the cycle wrapping from there — the one the once-at-init resolution of `RNF_TIME_SETUP` makes most likely to be got wrong). **That list is measured, not complete:** a fifth reading would need its own measurement, and nothing here argues there is none. pkg/exf anchors the cycle on the real date record 1 carries and wraps the elapsed time from there, so the cycle slips against the calendar at every leap year | **the span has to discriminate, and two spans did not.** Measured over hourly dates on `input.rnof_clim`: over the committed span (1 December 1978 plus 50 days) **all four** readings are exactly equal to exf's, so that case cannot tell a correct reader from any of them. Over 1 December 1980 plus 75 days, which this case used until correction round 1 of RUNOFF-005, three of the four differ by 2.247404e-02, 2.175868e-02 and 2.247404e-02 of the peak and `start_year` is **exactly 0.000000e+00**, because 1980-01-16 12:00 is exactly two 365-day cycles after the file's record 1 — the case passed while blind to it (review B). Over 1 December 1981 plus 75 days all four differ by 2.247404e-02, and the case fails unless each figure is at least `--min-discrimination` = 5e-3 of the peak. Scanning 43825 hourly dates from 1978-12-01 to 1983-12-01, the first date at which each parts from exf is 1981-01-01 00:00, 1980-12-16 03:00 and 1980-02-15 23:00, and `start_year` anchored on 1980 never differs over those five years at all. The model agrees with the dense run to 4.3e-16 over the 1800 steps of the new span, so the reader tracks exf across a leap day and a year boundary, and the case would now catch any of the four | `{python} tests/rnf/timing_field_check.py --case clim_long` (and `--mpi 2`) | local | yes |
| Runoff tendency terms, analytic single cell | the 8 cases of `tests/rnf/tendency_term_check.py`, which between them cover **every** row of the two tables of [package design](package_design.md) decision 3: the temperature table (6 rows: branch N/L and branch U, each with `temp_EvPrRn` unset, set with `ALLOW_ATM_TEMP` and set without it) and the salinity table (4 rows: branch N/L and branch U, each with `salt_EvPrRn` set and unset), plus two cases that are not rows of either — two sources on one cell with different fluxes and properties, and the same with the larger source's temperature missing. Each case is two runs of lab_sea of two time steps from iteration 0 with a uniform initial state, the **second** step measured, `pkg/seaice`/`pkg/kpp`/`pkg/gmredi` off and `implicitDiffusion=.FALSE.`; the second run has the same file with a zero flux. **`useExfCheckRange` is at the lab_sea default `.TRUE.`** since RUNOFF-030, where these cases used to switch it off. The applied field is 3.21e-5 m/s, 32 times the 1e-6 m/s pkg/exf allows (1e6 m³/s into the cell of `sparse_info()["wet_cell"]`, `rA` = 3.112287e10 m²), **but `EXF_CHECK_RANGE` never sees it**: it is called only at `nIter0`, and under `RNF_holdRecord` record 1 of each case's file is dry by construction, so the flux arrives at the second step when the check is no longer called. Measured on a retained `L_set` run: `nIter0 = 0`, `exf_debugLev = 2`, the `it= 0` trace selects `rec0 = 1` with `fac = 1.0`, and the log holds 0 `EXF WARNING` lines. So the override was never needed and these cases carry **no** evidence about the RUNOFF-030 skip; what they do establish is that removing it changes none of the 16 figures below. The bound that does apply to the flux is `RNF_srcFluxMax` = 1e7 m³/s, ten times this one. Branch N is **not** covered: it needs a nonlinear free surface, which is RUNOFF-014's, and the temperature and salinity tables group N with L | two oracles per case, which are the two columns of the tables. The **Package** column against the package's own `RNFgT`/`RNFgS` diagnostic, and the **Total** column against the difference of the two runs' `TOTTTEND`/`TOTSTEND`, which are the model's own state tendencies. **The measured step is the second, not the first** (corrected in correction round 1; the row and four places in the script had said the first). Each run writes one snapshot, labelled `0000000001` because MITgcm labels a snapshot by its write slot, and the tendency in it is `(θ²−θ¹)/Δt`: measured on a retained `L_set` pair, the snapshot is `8.313059890300034e-05` degC/s against that run's own `(θ²−θ¹)/Δt` of `8.313059890300037e-05`, equal to 1 ulp, while `(θ¹−θ⁰)/Δt` is `−4.5143400080746266e-06` and does not match. The second step is also the only one that could be measured: record 1 of every case's file is dry in **both** runs, so the first step is bitwise identical and its difference is exactly 0.0 by construction. The two runs therefore enter the measured step in the same state, so every other term is bitwise identical there and the difference is the sum of the model's term, pkg/exf's cancellation and the package's. The expected values are built from the run's own `RAC.data`, `hFacC.data`, `delR` and parameter dump, and the state the term was evaluated with from the run's own state dump, so a case cannot pass against a setting or a state it did not have | 1e-12 relative (the issue's acceptance). **Measured 2026-10-05 and re-measured 2026-10-06 with `useExfCheckRange` at its default (RUNOFF-030), identical both times: 8 of 8 cases passing and 10 of 10 table rows covered:** every Package figure **bitwise equal** (relative 0.00e+00, 16 of 16), and the Totals from 0.00e+00 to 1.43e-14 relative, i.e. at the round-off of the state difference the diagnostic is built from. Three premises are measured per case rather than assumed, and fail it: the iteration-0 state is the uniform one written (else the reference temperature is not the one the oracle used), the two runs are in a **bitwise identical** state when the measured step starts (0 of 7360 values differing — `state_at` returns the whole 3-D field, 20×16×23, not the 320-cell surface; the figure was wrongly given as 320 until correction round 1, which understated the claim by a factor of 23), and the run reports `tracForcingOutAB = 1`, `nonlinFreeSurf = 0`, `implicitDiffusion = F` and the `temp_EvPrRn`/`salt_EvPrRn`/`convertFW2Salt` the case asked for — the implicit solve was found to keep only 1 − 5.2e-4 of the term, 9 orders above the tolerance, so that premise is not cosmetic. A term below 1e-9 in absolute value fails the case as vacuous, and **where a row's two columns differ analytically the measured ones must differ too**: measured 1.75e-2 (branch L, `temp_EvPrRn` set, no `ALLOW_ATM_TEMP`), 7.86e-1 and 7.90e-1 (branch U with `temp_EvPrRn` set, where the total is against `tRef(1)` and not θ) and 1.17 to 1.35 for the salinity rows, so a case cannot pass by confusing the Package column with the Total. **Coverage limit:** one cell, one level, one step, linear free surface. Two rows need a binary with `ALLOW_ATM_TEMP` undefined, which `--build` now compiles: it writes the mods directory and runs `experiment_compile.sh` for `build_esx` and `build_esx_noatm` whenever the binary is missing **or older than the newest file of `BUILD_SOURCES` or of the experiment's `code/`** (LL-011: a binary predating its own source would make every figure here a figure of the old code). `BUILD_SOURCES` is every path the project declares as a source and compiles: `MITgcm/pkg/rnf`, `MITgcm/pkg/exf`, `MITgcm/model/src`, `MITgcm/model/inc`, `MITgcm/pkg/ptracers` and the plain file `MITgcm/pkg/pkg_depend`. The last three were added in correction round 2: review A measured the hole, and the fix was measured the same way — with `MITgcm/model/inc/PARAMS.h` (where `temp_EvPrRn`, `salt_EvPrRn`, `convertFW2Salt` and `UNSET_RL` are declared), `MITgcm/pkg/ptracers/ptracers_apply_forcing.F` (the `_PTR` call site) or `MITgcm/pkg/pkg_depend` stamped to the current time, the old three-entry scan reported all three of `build_esx`, `build_esx_noatm` and `build_esx_roft` as `reused` while the new six-entry scan reports all three stale, and both scans report `reused` again once the original mtime is restored (content never touched). `pkg_depend` needed the walk itself fixed: `os.walk` of a plain file yields nothing, so a file entry is now stat'ed directly. Without `--build` the behaviour is unchanged — the mods directory is written, the compile command printed, and the run exits 2. There is no longer any flag that lets a run report success with a table row no case exercised: the deleted `--allow-missing-rows` suppressed both the missing-binary exit 2 and the uncovered-row failure, so a command carrying it would have passed with two rows unexercised and no binary (review A, correction round 1). `--case` is exempt from the coverage failure only, and a missing binary is exit 2 even then (measured on both selection shapes) | `{python} tests/rnf/tendency_term_check.py --build`, which is self-contained; `--case L_set --case U_set` in the focused suite, which needs `build_esx` from `tests/mitgcm_oracle.sh lab_sea input` earlier in that suite. **Measured 2026-10-05:** one build costs 69.7–70.3 s (four compiles), so `--build` is 155.7 s when both are stale, 86.7 s when one is, and 16.6 s when neither is; the 8-case battery alone is 16.0–16.6 s and the focused pair 4.2 s. The staleness rule was witnessed on a real source edit, not only on a touched mtime: after a comment edit to `rnf_nc_utils.F` it reported `build_esx` as `reused` — the focused suite had already rebuilt it — while recompiling `build_esx_noatm`, so it distinguishes a current binary from a stale one rather than rebuilding everything | local | yes |
| Runoff heat term against the exf runoff temperature | one dense run and one sparse run of lab_sea with the same runoff: the dense one through `runoffFile` + `runoftempfile`, the sparse one through `pkg/rnf` with a `runoff_temperature` per source. Seven cells, one source each, with seven different temperatures from −1 to 30 °C, so the comparison is over a field with structure and not over one constant. Both runs use a binary built with `ALLOW_RUNOFTEMP` defined, which the committed `pkg/exf/EXF_OPTIONS.h` leaves undefined; `pkg/seaice` is off, which is how "ice-free cells" is realised, because the exf term is part of `Qnet` and would otherwise be scaled by the open-water fraction. **`useExfCheckRange` is at the lab_sea default `.TRUE.` in both runs** since RUNOFF-030: the runoff of the committed per-cell file is 4.0e-7 to 7.6e-7 m/s, under the 1e-6 m/s bound, so these runs never needed the override they carried (it had been copied from `tendency_term_check.py`), and the dense run — which has `useRNF` false and is therefore held to the exf runoff bound in full, with the field present from the first step — is now also a check that the dense path is unchanged. It is **not** a check of the sparse skip, because the sparse run is under the bound too | the dense path itself: `Cp·rhoConstFresh·EXFroff·(EXFroft − θ)` in tendency form, built from the two fields pkg/exf applied and the dense run's own `THETA`, against the `RNFgT` the package applied. The two are the same number computed by different code from different inputs — a dense per-cell field against a per-source table — which is the cross-path evidence for the heat term that no analytic check can give | 1e-12 relative. **Measured 2026-10-05 and re-measured 2026-10-06 with `useExfCheckRange` at its default (RUNOFF-030), identical both times: 7 cells compared, largest relative deviation 3.559e-16, 0 extra and 0 missing cells**, and the two runs' θ at the dump the measured step starts from bitwise identical in all 7360 values (the whole 3-D field, 20×16×23; the figure was wrongly given as 320, the surface-cell count, until correction round 1). Control (`--control`, verdict inverted): one source's temperature moved 1 K in the sparse file only is detected at 3.446e-02 relative, 14 orders above the agreement. **Coverage limits:** ice-free only, as above — the unscaled heat under ice is RUNOFF-024's; one constant record, so this row says nothing about timing; and the dense `runoftemp` path it compares against is itself a configuration no committed experiment runs | `{python} tests/rnf/exf_heat_check.py --control --build`, which compiles `build_esx_roft` under the same staleness rule as the row above. **Ordering dependency, unchanged by this patch:** the dense runoff field is built from the model's own `RAC.data`, which the script takes from any earlier `output_esx_*` run directory of lab_sea, so this command needs one to exist — `tests/mitgcm_oracle.sh lab_sea input` supplies it earlier in the scientific suite, and without it the command reports the reason and exits 2 rather than comparing anything. **Measured 2026-10-05:** 70.2 s to compile, 74.5 s cold and 4.3 s warm, with the comparison itself 7 cells at 3.559e-16 and the control at 3.446e-02 on both the cold and the warm run | local | yes |
| Target cell centres: `target_lon`/`target_lat` against `XC`,`YC` (**configured**) | the refusal case `target_coords` of `tests/rnf/refusal_check.py` (single-process and `-mpi 2`): a copy of `input.rnof_const/runoff_sparse.nc` with one target moved one cell in x while its `target_lon`/`target_lat` still name the cell it came from. The cell it lands on is wet, the fractions still sum to 1 and on this lat-lon grid its `rA` is bitwise equal, so the land, fraction and area checks are all blind to it; the case asserts that their messages do **not** appear. `target_coords_nan` is the same check against a `target_lon` that is not a number, which the natural "distance greater than the tolerance" form accepts, because every comparison with a NaN is false. Review B of RUNOFF-033 measured that on the unfixed code: the run ended normally with exit 0, no `RNF` line at all and the summary still reporting `RNF_lonLatChk = T` — it claimed the check had run — and the verdict was build-dependent, refused at `-O3` and accepted at `-O0` — and `-O0` is this project's own `FOPTIM` (`build_esx/Makefile` for both lab_sea and cs32), so the accepting branch was the shipping configuration, not a hypothetical one. Such a file used to be fully schema-valid as well, so nothing upstream caught it either: `MITgcmutils.runoff.check` returned 0 errors, 0 warnings, exit 0 on it. Rule `T09` now flags it (1 error, exit 1, naming the source, the cell and the variable), so the checker and the model agree. The check is therefore written as a negated `.LE.`, the form `target_fraction` has always used, and this case is what holds it there. The positive control asserts the other direction, that the check *ran* (`RNF_lonLatChk = T` in the summary). Not covered: a packed `target_lon`, and a grid whose `XC`,`YC` are not degrees — both skip the check by design | the great-circle distance between the stored centre and the owning cell's own `XC`,`YC`, against that cell's own grid spacing `MIN(dxF, dyF)` | `RNF_lonLatTol` = 0.5, i.e. the stored centre has to lie inside the owning cell. Justified by the grid, not chosen: over all 1189 cs32 and 7 lab_sea committed targets the stored centre is **bitwise equal** to `XC`,`YC` (max offset exactly 0.0), so the threshold absorbs no real deviation. The margin of a corrupted `target_cell` is **not** a uniform factor 2: `1 + spacing(from)/spacing(to)` holds only where the spacing is locally uniform, and at the cs32 facet corner `dxF` jumps 120208 → 156359 m, giving 1.78. What holds is that the margin is strictly above 1 on any grid with positive cell sizes (two distinct centres are at least `0.5*(s_from + s_to)` apart along the move and `MIN(dxF,dyF)` of the destination is at most `s_to`), and the **measured floor over every ordered pair of distinct cells is 1.779673 on cs32** (37,742,592 pairs, cells 0 → 1 and 0 → 192 tied at the facet corner) **and 1.999904 on lab_sea** (cells 300 → 301). The margin does **not** depend on `rSphere`: it is a ratio of two lengths that both scale with it, so a consistent change cancels — measured on the cs32 metrics, 6370 km and 6371 km both give 1.779673381, a ratio of 1.000000000000. What moves it is a **mismatch** between the radius used for the distance and the radius the spacing already embodies: distance at 6371 km against spacing at 6370 km gives 1.779952764, a ratio of 1.000156985871 = 6371/6370. The requirement is therefore that the distance and the spacing come from the same grid — on LLC or the 2 km grid, `DXF` comes from a dump that already embodies the model's radius, so take the coordinates from that same dump. (That mismatch is also what made a first lab_sea measurement read 1.999590: 6370 km assumed against a grid built with the 6371 km that `lab_sea/input/data` sets, and 1.999904/1.999590 = 1.000157.) For a one-cell zonal move on a uniform row the margin is twice the ratio of the great-circle distance to the along-parallel spacing, and that ratio is slightly below 1 — 0.99995 at lab_sea's 77 °N with a 2° step — which is exactly why lab_sea measures 1.999904 and not 2. So no corruption of a single `target_cell`, by one cell or by any other amount, can evade the check on either grid. `MIN(dxF,dyF)` is necessary and not merely cautious: under `MAX` the margin of a one-cell zonal move on a 1° global lat-lon grid is `2·cos(lat)`, i.e. 0.347 at 80 °N and 0.035 at 89 °N, so `MAX` would defeat the guard on every high-latitude row. Because both sides scale with the local cell, the one constant holds from lab_sea's 2° to the 2 km production grid. Measured on the two refusal cases: lab_sea 1.3995e5 m apart against 6.9977e4 m allowed; cs32 entry 1035 1.2424e7 m against 1.1092e5 m (factor 112). One tile sees it, the count is `GLOBAL_SUM_INT`-ed and all 4 ranks stop | `{python} tests/rnf/refusal_check.py` (and `--mpi 2`) | local | yes |
| Volume conservation | at initialization (**configured**): the flux summed over the sources of the file and over the targets of all tiles, printed by `RNF_INIT_VARIA` with their relative difference, in the control cases of `tests/rnf/refusal_check.py`. During the run (planned): Σ runoff·rA from diagnostics | Σ flux·frac over the targets = Σ flux_s | initialization: ≤ 1e-6 relative (the fraction tolerance), which the model itself warns about; measured equal in every printed digit for lab_sea and cs32, with the printed relative difference 0.00000000E+00 for lab_sea (4 or 7 sources) and -3.93454799E-16 for cs32 (1189 sources, where the two sums add in a different order). During the run: ≤ 1e-12 relative | `{python} tests/rnf/refusal_check.py`; new check script (RUNOFF-015, RUNOFF-016) | local | yes |
| Converter round-trip and converted inputs (**configured**) | the dense runoff files of the six `lab_sea/input.rnof_*` cases (float32) and of cs32 (`core_rnof_1_cs32.bin`, `runoff_temperature.bin`, float64, converted twice: all 12 records with temperature, and record 1 alone as one constant record; needs the grid output of a cs32 run, else skipped); synthetic lat-lon and exch2-shaped grids with land, a blank tile and grouped sources; a hand-built file with two sources feeding one cell | dense → sparse → dense gives back every dense record; fractions, fluxes and temperatures computed in the test from the inputs; for two sources on one cell, runoff as the sum of flux·fraction/rA and temperature as the flux-weighted mean, worked out by hand, including a record without flux and the fill value; time axes worked out by hand per exf timing mode; at every forcing time of the six lab_sea oracle runs, the sparse file read by the schema's rules against the field exf applies from the dense file (`lab_sea_runoff_timing_check.Case`, the emulation the direct timing check compares with the model), with a one-record shift as negative control; the integrity checker with grid checks on every converted file; each committed sparse file of the table below equals its regeneration: the lab_sea files in every variable, global attribute and type, and the two cs32 files (`input.rnof_sparse/runoff_sparse.nc` and `input.rnof_sp_icedyn/runoff_sparse_const.nc`) in every variable; for the constant cs32 file also one `constant` float64 record without temperature that gives back record 1 of the dense file | exact for float32 inputs and for the cs32 temperature; cs32 runoff (float64) exact at float32 and within one unit in the last place at float64, because (d·rA)/rA is not always d; total flux per record ≤ 1e-12 relative; field at forcing times ≤ 1e-12 of the largest runoff value; checker: no error, no warning | `{python} -m pytest -q tests/runoff` (`tests/runoff/test_convert.py`) | local | yes |
| Message formats of `pkg/rnf` (**configured**) | every `WRITE(msgBuf,'(...)')` of `MITgcm/pkg/rnf/*.F` (140 statements), with the item types read from the declarations of the routine the statement is in and of `RNF.h` / `RNF_SIZE.h` | the format itself: an `A` descriptor must get a character item, `I` an integer one and `E`/`F`/`G`/`D` a real one, after expanding repeat counts, groups and Fortran format reversion. A mismatch is a runtime error that the compiler cannot see and that only a refusal path reaches, so no model run finds it. Self-tested on three mutants: the two formats that really were wrong in RUNOFF-004 and an `I` descriptor with a `_RL` item, which a two-class checker accepts | no finding, and no item of unknown type (the check must cover every statement it counts). Measured: 140 statements, 0 findings | `{python} -m pytest -q tests/runoff` (`tests/runoff/test_write_formats.py`) | local | yes |
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
  treats the file's own time axis in such a run is decided (RUNOFF-005): without pkg/cal the axis is model time in seconds counted from the reference date of its units, no date is converted and the file's calendar is not compared, because the model has none. That path is **not exercised by any configured command**: the only no-cal experiment with runoff is cs32, whose sparse case has one constant record, for which the time axis is not read at all.

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
- Runoff in these cases stays below 1e-6 m/s (measured 4.0e-7 to 7.6e-7 m/s),
  because `useExfCheckRange` stopped a run above that value on every path when
  they were built. Since RUNOFF-030 that limit no longer binds a **sparse**
  run: `EXF_CHECK_RANGE` skips its runoff upper bound and tests `sflux +
  runoff` instead of `sflux` when `useRNF` is true, which together are what a
  point source needs (either one alone still stops it — measured). The
  figures of these cases are nevertheless unchanged, because each sparse twin
  has to stay comparable with its dense one, and the dense `input.rnof_<X>`
  cases are still held to 1e-6 m/s on both bounds. A sparse run above the
  limit is exercised by `tests/rnf/refusal_check.py --case
  flux_at_source_max` (3.21e-4 m/s, 321 times the bound, ending normally with
  `useExfCheckRange` at its default on 1 and on 2 processes). The package
  applies **two** bounds of its own to a sparse run in place of the skipped
  one: `RNF_srcFluxMax` = 1e7 m³/s on the flux of one source, per record
  (`--case flux_above_source_max`), and `RNF_cellVolMax` = 0.2 on the share
  of a target cell's top-layer volume that one step of the applied field may
  add, per cell and per step (`--case cell_above_vol_max`, RUNOFF-040). The
  first bounds the file and cannot see an aggregate; the second is what
  refuses several sources adding up on one cell.
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

- **Provenance of the measured figures (2026-10-04).** The `pkg/rnf` reader
  was written a second time after the machine move, because the first
  implementation was never pushed to the fork and was lost with the old
  host; the records of it (this matrix, the code map and the design's
  implementation notes) survived. The figures re-measured on the rebuilt
  code and this host are: the lab_sea and cs32 sparse = dense digits
  (single-process and MPI), the two `RNF_INIT_VARIA` flux sums, every case
  of `tests/rnf/refusal_check.py` (single-process and `--mpi 2`), every run
  of `tests/rnf/placement_probe.py`, and the no-change and dense runs of
  `lab_sea input`, `lab_sea input.rnof_const`,
  `global_ocean.cs32x15 input.icedyn` and `input.seaice`. In correction
  round 1 review A added the first measurement of a one-cell move on the
  **current** code (the cross-facet move in the item on the 10-digit oracle
  below) and the cell-exact reconstruction of the applied field; review B
  added the cross-rank reduction case. The figures **not** re-measured, and
  therefore describing the first implementation only, are the in-tile
  one-cell-move samples and the round-off response of the cs32 experiment in
  the items below, together with the count of shifts the area check would
  refuse. Those were measured during the first RUNOFF-004 attempt, partly by
  its implementer (the single-process round-off figures) and partly by its
  review A (the 4-process round-off figures and the move samples); the code
  they describe no longer exists. The current code refuses an in-tile move
  through the same area check, which the configured probe and the
  `cell_area` case run, but those digit figures have not been reproduced
  here.
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
  targets, and a move **across a facet boundary** is not resolved by the
  area check either. One target entry is moved by one cell, with the area of
  the new cell written in the file, and the run is compared either with the
  unmoved sparse run or with the committed reference. "Seen" means that
  `cg2d_init_res` changes by more than 1e-10.

  **Measured on the current code** (commit `b8251cd1c`, 4 processes,
  correction round 1, review A; no configured test repeats it): target entry
  1035 moved from global cell 5247 to 5248, one cell in x **across the facet
  2/3 boundary** of the 192 × 32 layout, flux 3.714e-2 m³/s (about the 1st
  percentile), the fractions still summing to 1. The two cells' `rA` are
  bitwise equal, so `RNF_areaTol` is blind to the move: `RNF_INIT_FIXED`
  accepts it with no `RNF` message, the run ends normally, and
  `compare_results.sh` reports **10 matching digits against the 10
  required** — a pass with zero margin. `cg2d_init_res` moves by 1.062e-10
  in absolute terms, 4.103e-11 relative. A cross-facet move of a
  1st-percentile target is therefore neither refused by the file checks nor
  failed by the digit oracle, and the one "not seen" datum of the historical
  table below (the 3rd-percentile target of round 3, an in-tile move of a
  comparably weak target) understates it: the change is at the edge of the
  "seen" threshold and still passes.

  **Resolved by RUNOFF-033,** in the two ways the move is now caught:
  - `RNF_INIT_FIXED` refuses it at init, from `target_lon`/`target_lat`
    against the owning cell's `XC`,`YC` (row "Target cell centres" above).
    Measured on this move, cs32 on 4 processes: the stored centre is
    1.242e7 m from cell 5248's centre against 1.109e5 m allowed, so it is
    refused by a factor of 112, while the area check stays silent.
  - the cell-exact applied-field check (row "Applied runoff field, cell by
    cell") sees it even when the file carries no coordinates to check, as
    one extra and one missing cell per dump with a relative deviation of 1.

  **Historical samples**, measured during the first RUNOFF-004 attempt by
  its review A on the 4-process binary of code that no longer exists. They
  are in-tile moves; no configured test repeats them:

  | Sample | Targets moved | Seen | Change of `cg2d_init_res` |
  |---|---|---|---|
  | round 1 | 10th percentile (9.6 m³/s), median (279 m³/s) and largest (35,420 m³/s) | 3 of 3 | 3.4e-9, 4.9e-8 and 2.7e-6 |
  | round 3 | 8 targets from the 2nd to the 9th percentile (0.26 to 7.4 m³/s) | 7 of 8 | seen: 2.7e-10 to 4.9e-9; not seen: the 3rd-percentile target (0.61 m³/s), 8.8e-11 |
  | round 3 | 23 targets from the 10th to the 98th percentile (9.6 to 6454 m³/s) | 23 of 23 | 3.5e-9 to 1.6e-6 |

  Each sample is one move per target, not every target or every direction.
  What follows for the tests:
  - No comparison of model output detects a one-cell move of the weakest
    targets. The oracle does not fail on it: the cross-facet move measured
    on the current code passes at exactly the required 10 digits. A direct
    comparison of two runs cannot tell such a move from round-off either: a
    one-ulp change of the input flux leaves `cg2d_init_res` unchanged or
    moves it by 1.1e-11 to 2.1e-11 (nine patterns, in the item on round-off
    below), the same order as the 4.103e-11 relative change of that move.
  - The placement probe is not a check of the runoff targets. It checks where
    the reader places 80 fixed cells per layout, the four corners of every
    tile and fixed interior positions, and it does not read the runoff file.
    In the 192 × 32 layout, 16 of those 80 cells are also cells of the 1189
    cs32 targets and the other 1173 target cells are not probed (computed in
    RUNOFF-004 round 2 from the probe's cell selection and the target table;
    not a configured test). A misplacement confined to cells that the probe
    does not sample, of targets that carry only weak flux, is seen by neither
    the probe nor the digit-match oracle.
  - Since RUNOFF-033 the real targets are covered cell by cell, on every
    cell and independently of flux magnitude, by the applied-field check
    (row "Applied runoff field, cell by cell"), and a move that leaves
    `target_lon`/`target_lat` behind is refused at init. The two paragraphs
    below describe what the area check alone did and did not cover, and
    remain the reason neither guard is the only one.
  - What partly protects the real targets is the area check of
    `RNF_INIT_FIXED`, when the file has `target_cell_area`. Every committed
    sparse file has it; the schema makes it optional. Configured tests run
    that check on lab_sea (case `cell_area`, an area off by 1 %) and on the
    probe cells. For the cs32 targets there is no configured test. Two
    different counts bound the gap, and they are not the same quantity:
    - **In-tile shifts, first implementation** (its review A, code that no
      longer exists): with the area left as written for the original cell,
      the moves of the weakest targets were refused and all 4 processes
      stopped. Of the **4516 one-cell shifts of the 1189 targets inside
      their tile**, the check would refuse 4458, those where the two cells
      differ in area by more than 1e-4; the other **58 in-tile shifts** have
      no such protection.
    - **Shifts the check cannot see at all, current code** (correction round
      1, review A's census on `b8251cd1c`): **47** target entries have a
      wet, non-target neighbour in the global index whose `rA` differs by
      less than `RNF_areaTol`, and that census **includes cross-facet
      neighbours**, which the in-tile count above excludes. The cross-facet
      move measured above is one of them, and it is accepted silently.
    A file without `target_cell_area` has no protection of either kind.
    RUNOFF-033 covers the cell-exact check that closes this gap.
- **Temperature, salinity and tracers in the model**, corrected in
  RUNOFF-013 correction round 1 — this entry used to say "no test has"
  them, which three enrolled instruments now contradict:
  - `tests/rnf/tendency_term_check.py` runs 8 cases with both
    temperature and salinity in the model, covering all 10 rows of the
    two tables of decision 3, against the package's own `RNFgT`/`RNFgS`
    and against the two-run `TOTTTEND`/`TOTSTEND` difference.
  - `tests/rnf/exf_heat_check.py` compares the package heat term
    against the dense `runoftemp` path over a 7-cell field of 7
    different temperatures.
  - `tests/rnf/refusal_check.py --case ptracer_match` runs a matched
    runoff tracer through `RNF_TENDENCY_APPLY_PTR`, and six sibling
    cases cover the name matching and its refusals.

  What genuinely remains:
  - **budget closure over many steps and many cells** (RUNOFF-016). The
    two instruments above measure one cell and one step, and seven
    cells at one step; neither closes `Σ F_c·X_c = Σ_s flux_s·X_s`
    over a run.
  - **MPI.** Every case of both instruments is single-process.
  - **branch N** (RUNOFF-014): it needs a nonlinear free surface, which
    no configured case has, and the temperature and salinity tables
    group N with L.
  - **the lagged time level.** See the `RNF_FIELDS_LOAD` entry below;
    `RNF_lagFlds = T` is code read but never executed.
  - **the tracer term's value** (RUNOFF-008). `ptracer_match` shows the
    routine runs and reports its match; nothing compares the number it
    applies against an oracle, as `tendency_term_check.py` does for T
    and S.

  Time records are covered as of RUNOFF-005: all five modes have a
  sparse case and a cell-by-cell comparison against the dense path, and
  the reader no longer refuses a file that is not `constant`.
- **What the sparse timing check covers, and what the sparse = dense
  evidence is in each mode.** Since RUNOFF-005 every sparse case is
  judged by `tests/runoff/lab_sea_runoff_timing_check.py`, including
  `input.rnof_sp_const`: the check no longer compares an `exf_runoff_*`
  monitor for a sparse case (exf writes none for a blank `runoffFile`, and
  `pkg/rnf` has no monitor of its own yet, RUNOFF-015) but the records,
  file years and weight that `RNF_FIELDS_LOAD` printed, against what the
  exf conventions give at the same model time. A `SKIP` is now reserved for
  a sparse case with no dense twin to take those conventions from, and there
  is none today. **The named weakness is what the cross-path evidence is
  about** (review A of RUNOFF-005): in the five timed modes it is the
  applied forcing field, cell by cell at every step, plus the record
  choice — **not** the whole model response, because each timed sparse
  case is compared with its own reference rather than with the dense
  one. Whole-model-response cross-path evidence survives only in the two
  constant cases, `lab_sea/input.rnof_sp_const` and
  `global_ocean.cs32x15/input.rnof_sp_icedyn`, whose references are byte
  copies of the dense ones and which therefore still compare every monitor
  variable as a time series over every monitor line of `output.txt`. The
  reason the timed cases cannot do that is measured, not assumed: the
  applied fields agree to 4.3e-16 and lab_sea amplifies that into 4, 16, 3,
  16 and 4 matching digits of `cg2d_init_res` for daily, month, month1, clim
  and yearly — so `month` and `clim` do meet the 10-digit criterion against
  the dense reference, and the other three do not. Review A capped the input
  difference at one unit in the last place offline (max 2.0e-16, about 88%
  of values bitwise identical, identical non-zero cell sets in every record)
  and then reproduced the 4-digit figure by moving every `runoff_flux` of
  the daily file exactly one ulp, which is what establishes amplification
  rather than a defect.
- **Two sources feeding one cell.** None of the committed oracle files makes
  the model add two contributions into one cell: `lab_sea` has one target
  entry per cell in both its files (4 grouped sources over 7 one-source
  cells, or 7 one-cell sources) and the cs32 file is 1189 one-cell sources
  with `target_fraction` exactly 1.0, so the accumulation
  `RNF_vflx(i,j) = RNF_vflx(i,j) + flux*frac/rA` of
  `MITgcm/pkg/rnf/rnf_fields_load.F:74-76`, which implements the profile
  invariant "where several sources feed one cell, volumes add", ran with one
  term per cell only. The gap was found in correction round 1 and closed by
  the configured case `two_sources_one_cell` of
  `tests/rnf/refusal_check.py`, which splits every source of
  `runoff_sparse_cells.nc` into two carrying a third and two thirds of its
  flux on the same cell: 14 sources, 14 target entries, 7 cells, measured 16
  matching digits against `results/output.rnof_const.txt` (a reader that
  overwrote instead of adding would apply a third or two thirds of the
  runoff, which that comparison resolves: the zero-flux control matches to 2
  digits). What is still Python-only is the **flux-weighted mean** of
  temperature, salinity and tracers for overlapping sources
  (`tests/runoff/test_convert.py`, the hand-built two-source file); it needs
  RUNOFF-013 to exist in the model at all.
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
- **A test that greps a runtime message is coupled to its wording, and the
  focused suite cannot see it.** `tests/rnf/placement_probe.py` detects step 1
  of each probe run -- the run without a probe file, which must stop while
  opening it -- from the error the model prints. RUNOFF-005 reworded that
  message to name the file (necessary once `RNF_FILE_NAME` can resolve
  `<base>_YYYY.nc`), and the fixed sentence the probe matched stopped
  occurring, so all four probe runs returned at step 1 with 0 probes and
  `map None` and reported FAIL, the negative control included. It was caught
  by the final scientific run and could not have been caught earlier: the
  probe is scientific-only, because it needs three cs32 MPI builds. The
  detection is now a pattern naming the file
  (`placement_probe.OPEN_FAILED`), and restoring only the old literal
  reproduces the failure exactly, which is what identifies the pattern as the
  whole defect. Two things were checked across the rest of the suite rather
  than assumed: every `forbid` literal of `refusal_check.py` -- the class that
  would weaken *silently* rather than fail -- is either witnessed in a
  retained log (8 of 14) or asserted positively by another case in the same
  file (the other 6), so none is vacuous; and the remaining greps
  (`stderr`/`stdout` expectations, the `RNF_FIELDS_LOAD` trace patterns, the
  `RNF_INIT_VARIA` flux-sum pattern, `placement_probe.REPORT`) all fail loudly
  on a rewording.
- Refusals in the code that no configured test runs. The lists below were
  made by reading every stop of `rnf_readparms.F`, `rnf_check.F`,
  `rnf_init_fixed.F`, `rnf_nc_utils.F`, `rnf_time_setup.F`,
  `rnf_getrec.F` and `rnf_fields_load.F` against the cases of
  `tests/rnf/refusal_check.py` and the runs of `tests/rnf/placement_probe.py`.
  Every stop of those six files is either run by a configured case (rows
  "Configuration refusals of `pkg/rnf`" and "Refusals that need the file") or
  listed here. `rnf_time_setup.F` raises `errCount` in **21** places, of
  which **18 are enrolled and 3 are not** (lines 491, 497 and 579, all three
  needing a build without `pkg/cal`); `rnf_getrec.F` has 2 stops, neither
  enrolled. Both counts were made by listing every site with its line
  number and naming the case that drives it, one site at a time, after
  correction round 1 of RUNOFF-005 found the first census had understated
  the gap.
  On a clean per-site basis the arithmetic closes: **12 enrolled and 9
  unenrolled** before round 1, **plus the 6 cases round 1 added**, gives
  18 and 3. An intermediate count of "13 enrolled and 8 unenrolled" mixed
  two bases, because the record-range guard that
  `record_out_of_range` drives is in `RNF_NC_READ_FLUX`
  (`rnf_nc_utils.F:606-619`) and is not one of these 21 sites; both reviews and
  this document now agree on 18 and 3, each having recounted all 21 lines
  independently.
  - Time-handling refusals that no case runs (`rnf_time_setup.F`):
    - `RNF_startDate1`/`RNF_startDate2` set without `pkg/cal` (491) and a
      monthly period (-12 or -1) without `pkg/cal` (497). Both need a build
      without `pkg/cal`; the only such experiment with runoff is cs32, whose
      sparse case has one constant record, and `refusal_check.py` runs on
      lab_sea, which has `pkg/cal`.
    - `RNF_useYearlyFiles=.TRUE.` without `pkg/cal` (579): same reason.
      Its companion, `RNF_useYearlyFiles` **with** a repeat cycle (585), was
      recorded here in round 0 as unreachable because the `_YYYY` file is
      opened first. That was wrong — the file of the start year exists, so it
      opens normally and the guard fires in about a second — and the case
      `yearly_repcycle` now runs it.
  - Stops of `rnf_getrec.F` that no case runs:
    - `RNF_GETREC` (204), when the calendar month of the model time is
      neither bracket in hold-exact. It is a defensive stop on a state
      `cal_GetMonthsRec` cannot produce (its two brackets are the current
      month and one of its neighbours), so no input reaches it; it exists so
      that a future change to that routine cannot apply a record silently.
    - `RNF_FILE_NAME` (277), when `RNF_file` is too long to append
      `_YYYY.nc` to. It needs an `RNF_file` within 8 characters of
      `MAX_LEN_FNAM`, which no case has.
  - Configuration refusals (eight):
    - `runoftempfile` set: the lab_sea build has no `ALLOW_RUNOFTEMP`, so
      `EXF_CHECK` stops the run before `RNF_CHECK` is reached. It needs a
      build with that option, such as cs32.
    - `ALLOW_RUNOFF` undefined, `pkg/exf` not compiled, `HAVE_NETCDF`
      undefined and `USE_OLD_EXTERNAL_FORCING` defined: each needs a build of
      its own.
    - `SHI_update_kTopC` with `useShelfIce`: no experiment compiles both
      `rnf` and `shelfice`.
    (Until RUNOFF-005 this list also held `RNF_useYearlyFiles=.TRUE.`
    and an `RNF_period` other than 0, which that issue removed: both are
    now read rather than refused. What replaced them are the
    time-handling refusals listed below, of which 18 of 21 are enrolled.)
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
      an optional variable, the dimensions of a time series or a record of
      one is read, or while the file is closed.
    - Of the series refusals RUNOFF-013 added (`RNF_NC_SERIES`), **five
      of seven are enrolled** and run on the committed build: a tracer
      name that matches no ptracer (`ptracer_unknown`), tracer variables
      in a run that does not use pkg/ptracers (`ptracer_off`), and, as
      of correction round 1, a name that is empty
      (`ptracer_name_empty`), a name longer than `RNF_idLen` = 64
      (`ptracer_name_long`) and more tracer variables than `RNF_nTr` = 5
      (`ptracer_too_many`). The last three had been recorded here as
      unenrolled with their reachability "read from the source and not
      measured"; review B fired all three by hand with a NetCDF file
      edit alone, in seconds per run, and they are now cases. The two
      name checks precede the ptracer matching in `RNF_NC_SERIES`, so
      neither needs a second ptracer or a second build. `ptracer_too_many`
      cannot be driven in isolation — with `PTRACERS_num` = 1 six
      *matching* names are impossible, so its six variables also raise
      the "not in use" error and the tally is 6 + 1 = 7, which the case
      asserts so those companions cannot change unnoticed. **Both halves
      of each new case are measured** (LL-009): all three pass on the
      committed build, and on a mutant binary whose three guards were
      weakened the way a careless edit would weaken them
      (`nTrLen .LT. 1` → `.LT. 0`, `nTrLen .GT. RNF_idLen` → `.GT. 999`,
      `nTrFile .GT. RNF_nTr` → `.GT. 999`, the mutated source confirmed
      present in the preprocessed file the build compiled) all three
      fail while `ptracer_unknown` and `ptracer_off` still pass, so the
      witness is specific to the guards under test.
      **The other direction is covered by three at-the-bound
      counterfactuals**, added in correction round 2 from review B's
      measurements: `ptracer_name_min` (one character after the prefix),
      `ptracer_name_max` (exactly `RNF_idLen` = 64 characters) and
      `ptracer_count_max` (exactly `RNF_nTr` = 5 tracer variables). A
      mutant can only weaken a guard; these are what hold a `.GT.` back
      from becoming a `.GE.`. Each must get **past** its guard, which the
      case measures by the error it does raise: with pkg/ptracers off, a
      name that passes both name checks reaches the `usePTRACERS` test
      (`rnf_nc_utils.F:637`, after the checks at `:618` and `:626`) and is
      refused there naming the variable, so the expected message is itself
      the proof that control went past the guard under test — a `forbid`
      list alone would also be satisfied by a run that never reached the
      matching. The first two differ from `ptracer_name_empty` and
      `ptracer_name_long` in exactly one character of the variable name,
      and the error tally separates `ptracer_count_max` from
      `ptracer_too_many` by one error (5 against 6 + 1). Measured
      2026-10-05 on the committed build: all three pass, with tallies of
      1, 1 and 5 fatal errors. These three are **not** new refusal
      coverage — five of seven remains the enrolled count — and they need
      no mutant of their own: the over-the-bound half of each pair fires
      the very message its companion forbids, on the same build.
      **Two gaps remain, and both genuinely need another build:** a name
      that matches more than one `PTRACERS_names` entry, which needs two
      ptracers with the same name and so `PTRACERS_num` ≥ 2, and the
      `#else /* ALLOW_PTRACERS */` branch for a model compiled without
      pkg/ptracers at all.
    - A missing value of `runoff_salinity` or of a tracer: the per-series
      refusal is the same code path as the flux's, which six cases run,
      but no case drives it through one of those two series, so the
      per-series naming of the message is unmeasured for them.
    - `RNF_FIELDS_LOAD`: a restart whose previous step precedes the first
      record of a non-repeating series, which only the lagged time level
      needs (branch N without `staggerTimeStep`). **No verification
      experiment configures that branch at all**, so neither the refusal
      nor the lagged path itself has a case: cs32 has `staggerTimeStep`
      and lab_sea a linear free surface. The whole of RNF_lagFlds = T is
      therefore code read but never executed (RUNOFF-014, RUNOFF-017,
      RUNOFF-022).

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
    lab_sea references, made on the previous host, were re-measured here
    during RUNOFF-004: `lab_sea input.rnof_const` gives 16 digits on
    `cg2d_init_res`, and the `-mpi` and cs32 runs agree as closely as the
    single-process ones — `lab_sea input -mpi 2` 11 digits,
    `global_ocean.cs32x15 input.icedyn` 11 and `input.seaice` 13. The band
    11 to 16 digits therefore holds on this host for every oracle the
    package uses.

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
- **What does close it (RUNOFF-033):** the cell-exact applied-field check
  compares the field the model applies with the field the file asks for on
  **every** cell of the global layout, so its sensitivity does not depend on
  how much flux a target carries, on whether the target is one of the cells
  the probe samples, or on the digit threshold. It is the configured test
  with margin that placement lacked: a one-cell move shows up as a relative
  deviation of 1 where the digit oracle moves `cg2d_init_res` by 4.1e-11.
  Its limit is what it compares: it checks the model against its own file,
  so it catches an error in the reader's placement or accumulation, not a
  file that asks for the wrong cell consistently. The init-time cell-centre
  check covers that other direction, for a file carrying `target_lon` and
  `target_lat`.
- **Refusals:** the negative tests confirm the refusal paths that they run,
  those of the rows "Configuration refusals of `pkg/rnf`" and "Refusals that
  need the file". The refusals that no configured test runs are listed in the
  coverage limits under "Refusals in the code that no configured test runs".
