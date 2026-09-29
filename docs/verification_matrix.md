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
| No-change: feature compiled in but unused leaves results unchanged (**configured**) | `1D_ocean_ice_column/input`, `lab_sea/input`, `seaice_obcs/input`, `offline_exf_seaice/input`, `seaice_itd/input`; all exf with `runoffFile = ' '` | committed `results/output.txt` | testreport digit threshold; expected identical | `tests/mitgcm_oracle.sh <exp> input` | local Docker | yes, every code change |
| Dense runoff baseline, cubed sphere (**configured**) | `global_ocean.cs32x15/input.icedyn`: 30-day records, 12 tiles | `results/output.icedyn.txt` | digit threshold | `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.icedyn` | local | yes |
| Dense runoff + runoff temperature, cubed sphere (**configured**) | `global_ocean.cs32x15/input.seaice` (`ALLOW_RUNOFTEMP`) | `results/output.seaice.txt` | digit threshold | `tests/mitgcm_oracle.sh global_ocean.cs32x15 input.seaice` (and `-mpi 4`) | local | yes |
| Sparse = dense, cubed sphere, exch2 multi-tile/multi-process | converted `core_rnof_1_cs32.bin` (+ `runoff_temperature.bin`); `SIZE.h` 12 tiles and `SIZE.h_mpi` 4 processes × 3 tiles | the two rows above | round-off from flux·frac/rA vs precomputed m/s | new `input.<X>` via `tests/mitgcm_oracle.sh … [-mpi 4]` | local | yes |
| Sparse = dense, lat-lon, constant runoff | new `lab_sea/input.<X>`; sources include one spanning a tile boundary and the MPI process boundary | dense-path reference run saved as `results/output.<X>.txt` | digit threshold | `tests/mitgcm_oracle.sh lab_sea input.<X> [-mpi 2]` | local | yes |
| Daily records, non-repeating | lab_sea, ≥ 1 month | dense daily reference | digit threshold | as above | local | yes |
| Calendar-monthly records (`period = -12`) | lab_sea, spanning ≥ 2 month boundaries | dense monthly reference | digit threshold | as above | local | yes |
| Monthly climatology wrap (`RepCycle` = 1 year) | lab_sea, crossing Dec → Jan | dense climatology reference | digit threshold | as above | local | yes |
| Yearly `_YYYY` files | lab_sea, run crossing 31 Dec → 1 Jan | dense yearly-field reference (`useExfYearlyFields`) | digit threshold | as above | local | yes |
| Hold-exact interpolation mode | lab_sea, daily or monthly | input values themselves: `runoff` diagnostic = Σ flux·frac/rA of the current record; no dense oracle exists | ≤ 1e-12 relative (real*8 arithmetic on float32 inputs) | new check script (RUNOFF-005) | local | yes |
| Fraction-sum and refusal behavior | invalid files: sum ≠ 1, land cell, off-grid index, unknown tracer, sparse + dense both set | expected fatal `EXF` error text in `STDOUT` | exact message match | new negative-test script (RUNOFF-004) | local | yes |
| Volume conservation | any sparse case | Σ runoff·rA = Σ flux_s(t) | ≤ 1e-12 relative | new check script | local | yes |
| Converter round-trip | cs32 and lab_sea dense files | dense → sparse → dense regenerates the original array | exact for float32 inputs | pytest under `tests/` (RUNOFF-002) | local | yes |
| Upstream contribution | all verification experiments, master vs branch, plus `-mpi` | `tr_out_master.txt` | no diff beyond timestamps | `MITgcm/verification/testreport` (Docker) and `tools/do_tst_2+2` | local | before the PR |
| 2 km scale I/O | 10⁵–10⁶ sources, 50 years daily, thousands of processes | wall-clock and I/O profile | owner-defined | cluster | remote | no (phase 1) |

**Other experiments (not oracles):**

- The other cs32 variants have no exf runoff: `input`, `input.thsice` (which uses
  `pkg/bulk_force` with a blank `RunoffFile`), `input.in_p`, `input.viscA4`,
  `input_ad` and `input_tap`.
- Runoff outside exf:
  - `global_oce_latlon/input.ebm`: `pkg/ebm` reads its own `RunoffFile`.
  - `isomip/input.icefront`: the `pkg/icefront` `SGRunOff*` settings are commented
    out.
  - `cpl_aim+ocn` and `aim.5l_cs`: coupler and land-model runoff.
- For the lab_sea yearly-file case, `lab_sea/input/data.exf_YearlyFields` and
  `data_YearlyFields` show a `useExfYearlyFields` setup to copy from.
- The lab_sea runoff-temperature case needs a `-mods` code directory with
  `ALLOW_RUNOFTEMP` defined, because the forward build uses the default
  `EXF_OPTIONS.h`.

**Coverage limits:**

- No LLC experiment exists in `verification/`.
- Adjoint builds (`input_ad.*` of cs32) are not run in phase 1.
- A local pass supports only the exercised grids and layouts.

**Sensitivity:** a dropped fraction, off-by-one global index, or wrong tile mapping
changes the runoff in at least one cell by O(1). That perturbs `theta`/`salt`
statistics well above round-off within a few steps, so the digit-match oracles
detect it. The negative tests confirm that the refusal paths trigger.
