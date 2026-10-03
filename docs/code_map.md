# Developer code map

Complete the routes below with actual paths and qualified Python symbols before
activation. For a non-Python source file, append `::<module>` to its path. Python AST locations
come from `python3 tools/esx/orient.py --outline path/to/file.py`; they do not prove
a dynamic call graph. Use a language-aware outline or bounded source search for
Fortran, Julia, C/C++, R or other languages.

## Pipeline

Paths are under `MITgcm/`, the fork clone on the branch `new_runoff`. Sparse-runoff
routines don't exist yet. The **Planned** rows name where they will attach, and
their owners are TBD until RUNOFF-004 and RUNOFF-005 land. The planned package
`rnf`, its routines and its hooks into existing source are specified in
[the package design](package_design.md), which is a proposal awaiting review.
Resolve line numbers from live source.

| Stage | Source and owning symbol | Input → output | Contract / nearest test |
| --- | --- | --- | --- |
| Namelist | `MITgcm/pkg/exf/exf_readparms.F::<module>` (`EXF_READPARMS`) | `data.exf` → `runofffile`, `runoffperiod`, `runoffStartTime`, `runoffRepCycle`, `useExfYearlyFields` in `EXF_PARAM.h` | [model contract](model_contract.md) §Time axis; `tests/mitgcm_oracle.sh` |
| Parameter report | `MITgcm/pkg/exf/exf_summary.F::<module>` (`EXF_SUMMARY`) | parameters → `STDOUT` | contribution rule: new parameters are reported here |
| Consistency checks | `MITgcm/pkg/exf/exf_check.F::<module>` (`EXF_CHECK`) | parameters → stop on invalid setup | planned: the check that sparse and dense runoff are mutually exclusive goes into the planned routine `RNF_CHECK`, not into exf ([package design](package_design.md), decision 2) |
| Dense field read and time interpolation | `MITgcm/pkg/exf/exf_getffields.F::<module>` (`EXF_GETFFIELDS`) → `MITgcm/pkg/exf/exf_set_gen.F::<module>` (`EXF_SET_GEN`) | `runofffile` records → `runoff`, `runoff0`, `runoff1` (m/s) | `global_ocean.cs32x15/input.icedyn` and `lab_sea/input.rnof_*` via `tests/mitgcm_oracle.sh` |
| Constant field (`runoffperiod = 0`) | `MITgcm/pkg/exf/exf_init_fld.F::<module>` (`EXF_INIT_FLD`), called from `MITgcm/pkg/exf/exf_init_varia.F::<module>` | record 1 of `runofffile`, read once → `runoff` | `lab_sea/input.rnof_const` |
| Record selection | `MITgcm/pkg/exf/exf_set_fld.F::<module>` (`EXF_SET_FLD`) chooses by period: `MITgcm/pkg/exf/exf_getffieldrec.F::<module>` (`EXF_GetFFieldRec`) for a positive period, `MITgcm/pkg/cal/cal_getmonthsrec.F::<module>` (`cal_GetMonthsRec`) for `-12`, `MITgcm/pkg/exf/exf_getmonthsrec.F::<module>` (`EXF_GetMonthsRec`) for `-1`; start time from `MITgcm/pkg/exf/exf_getffield_start.F::<module>` (`EXF_GETFFIELD_START`) | time, period, repeat cycle → record indices and weights | `lab_sea/input.rnof_daily`, `input.rnof_clim`, `input.rnof_month` (`-12`), `input.rnof_month1` (`-1`); conventions with line references in `MITgcm/verification/lab_sea/README.md::<module>` |
| Yearly file names | `MITgcm/pkg/exf/exf_getyearlyfieldname.F::<module>` (`exf_GetYearlyFieldName`) | base name + year → `name_YYYY` | `lab_sea/input.rnof_yearly` |
| Range check | `MITgcm/pkg/exf/exf_check_range.F::<module>` (`EXF_CHECK_RANGE`), run at the first step when `useExfCheckRange` is set | `runoff` → stop if negative or above 1e-6 m/s on a wet cell | all `lab_sea/input.rnof_*` cases keep it on |
| Dense lab_sea runoff generator | `MITgcm/verification/lab_sea/input.rnof_const/gendata.py::main` (the same script is kept in every `input.rnof_<X>`; the case comes from the directory name) | `bathy.labsea1979` + source table → dense float32 runoff records and `runoff_sources.txt` | the six `lab_sea/input.rnof_*` oracle runs |
| Dense runoff timing check | `tests/runoff/lab_sea_runoff_timing_check.py::main`: settings and records per case in `tests/runoff/lab_sea_runoff_timing_check.py::Case` (`tests/runoff/lab_sea_runoff_timing_check.py::Case.bracket` applies the exf timing conventions and returns the two records held and the weight of the later one; `Case.field` combines them), monitor values from `tests/runoff/lab_sea_runoff_timing_check.py::monitor_series`, comparison in `tests/runoff/lab_sea_runoff_timing_check.py::check_case` | `input.rnof_*/data.exf`, runoff records and `output_esx_input.rnof_*[_mpiN]/output.txt` → one PASS/FAIL line per case with the weight range seen at the monitor times (records held and weighted in the `--json` output), exit 1 on a mismatch above 1e-12 or a missing run | [verification matrix](verification_matrix.md) direct timing check; run after the oracle commands |
| Heat content of runoff | `MITgcm/pkg/exf/exf_mapfields.F::<module>` (`EXF_MAPFIELDS`) | `runoff`, `runoftemp` (`ALLOW_RUNOFTEMP`) → surface fluxes | `global_ocean.cs32x15/input.seaice` via `tests/mitgcm_oracle.sh` |
| Diagnostics | `MITgcm/pkg/exf/exf_diagnostics_fill.F::<module>` (`EXF_DIAGNOSTICS_FILL`) | `runoff` → diagnostics output | planned hold-exact direct check |
| Driver order | `MITgcm/pkg/exf/exf_getforcing.F::<module>` (`EXF_GETFORCING`) | calls `EXF_GETFFIELDS`, then `EXF_MAPFIELDS` | — |
| Template: sparse NetCDF read and point-to-tile | `MITgcm/pkg/profiles/profiles_init_fixed.F::<module>` (`PROFILES_INIT_FIXED`), `MITgcm/pkg/obsfit/obsfit_init_fixed.F::<module>` (`OBSFIT_INIT_FIXED`), `MITgcm/pkg/obsfit/obsfit_read_obs.F::<module>` (`OBSFIT_READ_OBS`) | NetCDF points → per-tile lists | reference only |
| **Planned:** sparse file init | planned routine `RNF_INIT_FIXED` of the package `rnf` (RUNOFF-004); tile placement follows `MITgcm/pkg/mdsio/mdsio_read_field.F::<module>` | NetCDF static arrays → per-tile `(i,j,k,bi,bj)`, fractions, global fraction check | [package design](package_design.md) decision 6; lab_sea / cs32 sparse cases |
| **Planned:** sparse record read and apply | planned routines `RNF_FIELDS_LOAD` (called from `MITgcm/model/src/load_fields_driver.F::<module>` before exf) and `RNF_EXF_RUNOFF` (called from `MITgcm/pkg/exf/exf_getffields.F::<module>` after the runoff read) (RUNOFF-004, RUNOFF-005) | `flux(time,source)` records → `runoff` (m/s) = Σ flux·frac/rA | [package design](package_design.md) decisions 2 and 7; dense-vs-sparse oracles |
| **Planned:** temperature, salinity and tracer input | planned routines `RNF_TENDENCY_APPLY_T`, `_S` (called from `MITgcm/model/src/apply_forcing.F::<module>` after the `ICEFRONT` calls) and `_PTR` (called from `MITgcm/pkg/ptracers/ptracers_apply_forcing.F::<module>`) (RUNOFF-013) | per-cell mass flux and mass-weighted T, S, tracers → tendencies at the target level | [package design](package_design.md) decisions 3 to 5; budget checks (RUNOFF-016) |
| Runoff file schema and integrity checker | Package `MITgcmutils.runoff` (`MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/`), whose `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/__init__.py::__getattr__` imports `check_files`, `Finding`, `Report`, `write_example`, `build_targets` and `write_targets` lazily so `python -m MITgcmutils.runoff.check` (or `.targets`) runs without runpy's double-import RuntimeWarning: constants `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/schema.py::<module>`; checker `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::check_files` → `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::Report` of `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::Finding`, CLI `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::main` (`python -m MITgcmutils.runoff.check`); `tables_only=True` / `--tables-only` skips the time and time-series rules for a file holding only the tables and reports them in S10 from `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::_check_tables_only`; example writer `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/example.py::write_example` with grid helper `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/example.py::lab_sea_grid`; grid checks read MITgcm output through `MITgcm/utils/python/MITgcmutils/MITgcmutils/mds.py::rdmds`; S08 reads stored attribute types (NC_CHAR vs NC_STRING) with `nc_inq_atttype` from libnetcdf via ctypes in `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::_attr_types` | sparse runoff NetCDF (+ optional grid dir) → rule findings (E/W/I), exit code 0/1/2, optional JSON | [runoff schema](runoff_schema.md) §9; `tests/runoff/test_runoff_check.py::<module>` and `tests/runoff/test_docstring_rules.py::<module>` (each rule function's docstring names the rule ids it emits) (fixtures in `tests/runoff/conftest.py::<module>`), run with `/home/ifenty/miniforge3/envs/ecco/bin/python -m pytest -q tests/runoff` |
| Target-table builder | `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::build_targets`: sources from `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::read_sources` (CSV or schema-1.0 NetCDF), grid from `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::read_grid` (through `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/check.py::_read_grid_field`); nearest wet cell `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_snap`; edge-neighbour graph `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::wet_graph` → `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_build_graph` for the declared grid kind (`connectivity`, resolved by `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_resolve_connectivity`: default `exch2` only when the grid directory holds `data.exch2`, else an error): `latlon` uses `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_latlon_pairs` (array neighbours with a row-by-row zonal wrap) after `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_latlon_check` confirms a regular lat-lon block and says whether it closes; `exch2` uses `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_corner_pairs` (cubed sphere/LLC and other grids, from corner vertices; at face edges, blank tiles and open boundaries the corners come from `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_geometric_corners` and `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_predicted_pair`; a wet cell that is a triangle, such as a lat-lon row touching a pole, is refused by `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_triangle_cell`); bounded path search `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_dijkstra`; kernels `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::kernel_weight` → `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::TargetTables`; writer `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::write_targets` (new tables-only file, or into an existing runoff file via `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::_write_into`); CLI `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/targets.py::main` (`python -m MITgcmutils.runoff.targets`) | source table + MITgcm grid output (`hFacC`, `XC`, `YC`, `XG`, `YG`, `RAC`) → source/alias/target tables with provenance (`target_distance`, `source_snap_distance`, `source_emission`, `source_spread_*`, `source_cutoff`) in NetCDF | [runoff schema](runoff_schema.md) §13; `tests/runoff/test_targets.py::<module>` (analytic channel/fjord oracles; cs32 graph proof on `MITgcm/verification/global_ocean.cs32x15/output_esx_input.icedyn`, skipped when absent), run with `/home/ifenty/miniforge3/envs/ecco/bin/python -m pytest -q tests/runoff` |
| **Planned:** converter | `tools/runoff/` (RUNOFF-002) | dense MITgcm binary + grid → sparse NetCDF | pytest round-trip (planned) |
| 3D (later) | `MITgcm/model/src/apply_forcing.F::<module>` (`APPLY_FORCING_T`), `MITgcm/model/src/integr_continuity.F::<module>` (`INTEGR_CONTINUITY`) | `addMass`, `temp_addMass`, `salt_addMass` | planned volume path for interior levels and for targets under an ice shelf ([package design](package_design.md) decision 5; RUNOFF-025) |

## Verification routes

- **Single experiment:** `tests/mitgcm_oracle.sh <experiment> <input_dir> [-mpi N] [-j N]`
  compiles into `build_esx[_mpiN]`, runs into `output_esx_<input>[_mpiN]`, and
  compares against `results/`. It exits non-zero on build failure, abnormal run
  end or FAIL.
- **Suites** (configured in [project.json](../esx/project.json)):
  - `focused`: cs32 `input.seaice` and lab_sea `input`.
  - `scientific`: adds MPI variants, the no-change experiments and the six
    lab_sea dense runoff cases `input.rnof_{const,daily,month,month1,clim,yearly}`,
    each single-process and with `-mpi 2`, followed by
    `tests/runoff/lab_sea_runoff_timing_check.py` (and `--mpi 2`), which reads
    the run directories those commands leave behind.
- **New reference output:** `compare_results.sh` pairs `input.<X>` with
  `results/output.<X>.txt`. For a new case, run it once single-process and copy
  `output_esx_input.<X>/output.txt` to that name.
  - Run them with `/home/ifenty/miniforge3/envs/ecco/bin/python tools/esx/verify.py --suite <name> --owner <role>`.
- **Oracles and planned cases:** [verification_matrix.md](verification_matrix.md).
- **Underlying Docker scripts:** `MITgcm/verification/{experiment_compile,experiment_run_no_compile,compare_results}.sh`
  are symlinks to `../MITgcm_verification_docker/scripts`. Only Fortran changes
  need a recompile. Input variants go in `<experiment>/input.<X>/`, layered on
  `input/`.
- **Upstream contribution checks:** full `testreport` (and `-mpi`) on master versus
  the branch, and `tools/do_tst_2+2`. See the
  [project profile](../esx/project_profile.md).

## Framework routes

| Responsibility | Owning operation |
|---|---|
| Project configuration and source signatures | `tools/esx/project.py::config`, `tools/esx/project.py::source_signature` |
| Issue selection and acceptance | `tools/esx/loop_gate.py::Gate.prepare`, `tools/esx/loop_gate.py::Gate.check_done` |
| Verification and reuse | `tools/esx/verify.py::run`, `tools/esx/verify.py::load_evidence` |
| Map navigation and documentation coverage | `tools/esx/doc_contract.py::navigate`, `tools/esx/doc_contract.py::validate_report` |
| Commit, notification and iteration history | `tools/esx/records.py::save_history` |
| Hook completion receipts | `tools/esx/hooks.py::capture` |

## Maintenance

Update stage ownership, input/output contracts and check routes when their source
changes. Keep line numbers out of manual tables; resolve them from live source.
A MAP-OK disposition explains which routes remain accurate for the actual patch.

## Review packet and runtime recovery

- `tools/esx/workflow_handoff.py::assemble` constructs explicit candidate/report/brief handoffs.
- `tools/esx/workflow_handoff.py::readiness` collects prerequisite failures without dispatching agents.
- `tools/esx/closeout_doctor.py::diagnose` lists every unmet closeout requirement, then replays the strict gate read-only.
- `tools/esx/workflow_records.py::locate_prior` and `replacement_skeleton` draft reiteration continuity without judging it.
- `tools/esx/runtime_recovery.py::compatibility` checks canonical configuration and assessed transitions.
- `tools/esx/runtime_recovery.py::hook_doctor` attributes configured hooks without executing them.
- `tools/esx/doc_contract.py::validate_orientation` diagnoses the changed dependency slice.

The owning procedure is [Evidence handoff and recovery](../devel-loop/recovery.md).
