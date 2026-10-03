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
| No-change: `pkg/rnf` compiled in and switched off leaves results unchanged (**configured**) | `lab_sea` and `global_ocean.cs32x15` list `rnf` in `code/packages.conf`; no `data.pkg` sets `useRNF`. `lab_sea/input` (exf with `runoffFile = ' '`), the six `lab_sea/input.rnof_*` dense cases, `global_ocean.cs32x15/input.seaice` and `input.icedyn`; single-process, `lab_sea -mpi 2` and cs32 `input.seaice -mpi 4` | committed `results/output*.txt`. The run log reports the state as `pkg/rnf compiled but not used`; no command checks that line | testreport digit threshold; expected identical | `tests/mitgcm_oracle.sh lab_sea input [-mpi 2]`, `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.seaice [-mpi 4]`, `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.icedyn` and the dense rows below | local Docker | yes, every code change |
| No-change: `pkg/rnf` compiled out leaves results unchanged; the edited hook files in `model/src`, `pkg/exf` and `pkg/ptracers` still compile without it (**configured**) | Six experiments without `rnf`; all compile the edited `model/src` files. `isomip/input` (`pkg/shelfice`; no exf, no ptracers). `1D_ocean_ice_column/input`, `seaice_obcs/input`, `offline_exf_seaice/input`, `seaice_itd/input` (exf with `runoffFile = ' '`): these four compile the edited `exf_getffields.F`. `tutorial_advection_in_gyre/input` (ptracers in use, no exf): the one that compiles and runs the edited `pkg/ptracers/ptracers_apply_forcing.F` | committed `results/output.txt` | testreport digit threshold; expected identical | `tests/mitgcm_oracle.sh <exp> input` | local Docker | yes, every code change |
| Configuration refusals of `pkg/rnf`, and the stop of the package skeleton (**configured**) | scratch inputs layered on `lab_sea/input`, each with `useRNF=.TRUE.`, a `data.rnf` and one violation: `runofffile` set, `runoffconst` ≠ 0, `exf_outscal_sflux` = 2, those three together, blank `RNF_file`, `useEXF=.FALSE.`; and a valid configuration as positive control; single-process and on 2 MPI processes | a run that does not end normally, with each process judged on its own files: the expected `RNF_CHECK` or `RNF_READPARMS` error text in every `STDERR.*`, and one `STOP` line of the expected routine per process (in `output.txt`, or in `mpirun.log` for an MPI run). A refusal case must not show, in any log, the lines printed after the checks pass. The control must show in the standard output of every process "configuration checks passed", the summary banner and `RNF_file` on the summary's own value line (the echo of `data.rnf` is not accepted), then the stop "reader not implemented", with no refusal message. The three-violation case must report all three and count 3 errors | exact substring match per file; exact value on the summary line | `{python} tests/rnf/refusal_check.py`, after `tests/mitgcm_oracle.sh lab_sea input` has built the binary; `{python} tests/rnf/refusal_check.py --mpi 2`, after `tests/mitgcm_oracle.sh lab_sea input -mpi 2` | local Docker | yes |
| Dense runoff baseline, cubed sphere (**configured**) | `global_ocean.cs32x15/input.icedyn`: 30-day records, 12 tiles | `results/output.icedyn.txt` | digit threshold | `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.icedyn` | local | yes |
| Dense runoff + runoff temperature, cubed sphere (**configured**) | `global_ocean.cs32x15/input.seaice` (`ALLOW_RUNOFTEMP`) | `results/output.seaice.txt` | digit threshold | `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.seaice` (and `-mpi 4`) | local | yes |
| Sparse = dense, cubed sphere, exch2 multi-tile/multi-process | converted `core_rnof_1_cs32.bin` (+ `runoff_temperature.bin`); `SIZE.h` 12 tiles and `SIZE.h_mpi` 4 processes × 3 tiles | the two rows above | round-off from flux·frac/rA vs precomputed m/s | new `input.<X>` via `tests/mitgcm_oracle.sh … [-mpi 4]` | local | yes |
| Dense runoff baseline, lat-lon, constant runoff (**configured**) | `lab_sea/input.rnof_const`: `runoffperiod = 0`, 48 steps; seven coastal source cells, one group spanning the tile and MPI process boundary between columns 9 and 10 | `results/output.rnof_const.txt` (single-process dense run) | digit threshold; the `-mpi 2` run must match the single-process reference | `tests/mitgcm_oracle.sh lab_sea input.rnof_const` and `tests/mitgcm_oracle.sh lab_sea input.rnof_const -mpi 2` | local | yes |
| Dense runoff baseline, daily records, non-repeating (**configured**) | `lab_sea/input.rnof_daily`: `runoffperiod = 86400`, `runoffRepCycle = 0`, 32 days, monitor every 12 h; records 1 to 34 read, 1 to 33 with non-zero weight | `results/output.rnof_daily.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_daily` and `tests/mitgcm_oracle.sh lab_sea input.rnof_daily -mpi 2` | local | yes |
| Dense runoff baseline, repeating monthly climatology (12 calendar-month records repeated every year) (**configured**) | `lab_sea/input.rnof_month`: `runoffperiod = -12`, 61 days from 1 January, crossing two month boundaries and two mid-month record changes; records 12, 1, 2, 3 read, all with non-zero weight | `results/output.rnof_month.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_month` and `tests/mitgcm_oracle.sh lab_sea input.rnof_month -mpi 2` | local | yes |
| Dense runoff baseline, calendar-month records, non-repeating (**configured**) | `lab_sea/input.rnof_month1`: `runoffperiod = -1`, `runoffstartdate1 = 19781201`, 61 days from 1 January, crossing two month boundaries; records 1 (December 1978) to 4 (March 1979) read, all with non-zero weight | `results/output.rnof_month1.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_month1` and `tests/mitgcm_oracle.sh lab_sea input.rnof_month1 -mpi 2` | local | yes |
| Dense runoff baseline, 12 equally spaced records with a repeat cycle (**configured**) | `lab_sea/input.rnof_clim`: `runoffperiod = 2628000`, `runoffRepCycle = 31536000` (365 days), 50 days from 1 December, wrapping from record 12 to record 1; records 11, 12, 1, 2 read, all with non-zero weight | `results/output.rnof_clim.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_clim` and `tests/mitgcm_oracle.sh lab_sea input.rnof_clim -mpi 2` | local | yes |
| Dense runoff baseline, yearly `_YYYY` files (**configured**) | `lab_sea/input.rnof_yearly`: `useExfYearlyFields`, daily records, 26 days from 20 December, monitor every 12 h; records 354 to 365 of `runoff_yearly_1978` and 1 to 16 of `runoff_yearly_1979` read, of which 354 to 365 and 1 to 15 have non-zero weight | `results/output.rnof_yearly.txt` | as above | `tests/mitgcm_oracle.sh lab_sea input.rnof_yearly` and `tests/mitgcm_oracle.sh lab_sea input.rnof_yearly -mpi 2` | local | yes |
| Dense runoff timing, direct check (**configured**) | the run directories of the six `lab_sea/input.rnof_*` cases, single-process and `-mpi 2`; needs the oracle runs above to have been made | monitor statistics `exf_runoff_max`, `_min`, `_mean`, `_sd` versus the field interpolated from the input records under the exf timing conventions, at every monitor time | ≤ 1e-12 relative to the largest runoff value (real*8 interpolation of float32 records) | `{python} tests/runoff/lab_sea_runoff_timing_check.py` and `{python} tests/runoff/lab_sea_runoff_timing_check.py --mpi 2` | local | yes |
| Sparse = dense, lat-lon, constant runoff | the `input.rnof_const` runoff converted to sparse form; sources include one spanning a tile boundary and the MPI process boundary | `results/output.rnof_const.txt` | digit threshold | new `lab_sea/input.<X>` via `tests/mitgcm_oracle.sh lab_sea input.<X> [-mpi 2]` | local | yes |
| Sparse = dense, daily records, non-repeating | the `input.rnof_daily` runoff, ≥ 1 month | `results/output.rnof_daily.txt` | digit threshold | as above | local | yes |
| Sparse = dense, repeating monthly climatology (`period = -12`) | the `input.rnof_month` runoff, spanning ≥ 2 month boundaries | `results/output.rnof_month.txt` | digit threshold | as above | local | yes |
| Sparse = dense, calendar-month records, non-repeating (`period = -1`; schema `monthly` sampling with repeat `none`) | the `input.rnof_month1` runoff, spanning ≥ 2 month boundaries | `results/output.rnof_month1.txt` | digit threshold | as above | local | yes |
| Sparse = dense, climatology wrap (`RepCycle` = 1 year) | the `input.rnof_clim` runoff, crossing Dec → Jan | `results/output.rnof_clim.txt` | digit threshold | as above | local | yes |
| Sparse = dense, yearly `_YYYY` files | the `input.rnof_yearly` runoff, run crossing 31 Dec → 1 Jan | `results/output.rnof_yearly.txt` (`useExfYearlyFields`) | digit threshold | as above | local | yes |
| Hold-exact interpolation mode | lab_sea, daily or monthly | input values themselves: `runoff` diagnostic = Σ flux·frac/rA of the current record; no dense oracle exists | ≤ 1e-12 relative (real*8 arithmetic on float32 inputs) | new check script (RUNOFF-005) | local | yes |
| Fraction-sum and refusals that need the file | invalid files: sum ≠ 1, land cell, off-grid index, unknown tracer, target beyond an open boundary or under an ice shelf | expected fatal `RNF` error text in the run logs | exact message match | more cases in `tests/rnf/refusal_check.py` (RUNOFF-004) | local | yes |
| Volume conservation | any sparse case | Σ runoff·rA = Σ flux_s(t) | ≤ 1e-12 relative | new check script | local | yes |
| Converter round-trip | cs32 and lab_sea dense files | dense → sparse → dense regenerates the original array | exact for float32 inputs | pytest under `tests/` (RUNOFF-002) | local | yes |
| Upstream contribution | all verification experiments, master vs branch, plus `-mpi` | `tr_out_master.txt` | no diff beyond timestamps | `MITgcm/verification/testreport` (Docker) and `tools/do_tst_2+2` | local | before the PR |
| 2 km scale I/O | 10⁵–10⁶ sources, 50 years daily, thousands of processes | wall-clock and I/O profile | owner-defined | cluster | remote | no (phase 1) |

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
- Five `pkg/rnf` refusals are in the code and no configured test runs them:
  - `runoftempfile` set: the lab_sea build has no `ALLOW_RUNOFTEMP`, so
    `EXF_CHECK` stops the run before `RNF_CHECK` is reached. It needs a build
    with that option, such as cs32.
  - `ALLOW_RUNOFF` undefined, `HAVE_NETCDF` undefined and
    `USE_OLD_EXTERNAL_FORCING` defined: each needs a build of its own.
  - `SHI_update_kTopC` with `useShelfIce`: no experiment compiles both `rnf`
    and `shelfice`.
- The references of `lab_sea/input` and of the cs32 cases come from another
  platform. On the local Docker platform they agree to 11 to 13 digits on
  `cg2d_init_res`, so these oracles show agreement to the testreport
  threshold and cannot show that a result is unchanged in every bit. The
  references of the dense lab_sea cases were made on the local platform.

**Sensitivity:** a dropped fraction, off-by-one global index, or wrong tile mapping
changes the runoff in at least one cell by O(1). That perturbs `theta`/`salt`
statistics well above round-off within a few steps, so the digit-match oracles
detect it. The negative tests confirm that the refusal paths trigger.
