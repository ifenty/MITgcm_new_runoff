# Developer code map

Complete the routes below with actual paths and qualified Python symbols before
activation. For a non-Python source file, append `::<module>` to its path. Python AST locations
come from `python3 tools/esx/orient.py --outline path/to/file.py`; they do not prove
a dynamic call graph. Use a language-aware outline or bounded source search for
Fortran, Julia, C/C++, R or other languages.

## Pipeline

Paths are under `MITgcm/`, the fork clone on the branch `new_runoff`. Sparse-runoff
routines don't exist yet. The **Planned** rows name where they will attach, and
their owners are TBD until RUNOFF-004 and RUNOFF-005 land. Resolve line numbers
from live source.

| Stage | Source and owning symbol | Input → output | Contract / nearest test |
| --- | --- | --- | --- |
| Namelist | `MITgcm/pkg/exf/exf_readparms.F::<module>` (`EXF_READPARMS`) | `data.exf` → `runofffile`, `runoffperiod`, `runoffStartTime`, `runoffRepCycle`, `useExfYearlyFields` in `EXF_PARAM.h` | [model contract](model_contract.md) §Time axis; `tests/mitgcm_oracle.sh` |
| Parameter report | `MITgcm/pkg/exf/exf_summary.F::<module>` (`EXF_SUMMARY`) | parameters → `STDOUT` | contribution rule: new parameters are reported here |
| Consistency checks | `MITgcm/pkg/exf/exf_check.F::<module>` (`EXF_CHECK`) | parameters → stop on invalid setup | planned: sparse and dense are mutually exclusive |
| Dense field read and time interpolation | `MITgcm/pkg/exf/exf_getffields.F::<module>` (`EXF_GETFFIELDS`) → `MITgcm/pkg/exf/exf_set_gen.F::<module>` (`EXF_SET_GEN`) | `runofffile` records → `runoff`, `runoff0`, `runoff1` (m/s) | `global_ocean.cs32x15/input.icedyn` via `tests/mitgcm_oracle.sh` |
| Record selection | `MITgcm/pkg/exf/exf_getffieldrec.F::<module>` (`EXF_GetFFieldRec`), `MITgcm/pkg/exf/exf_getmonthsrec.F::<module>` (`EXF_GetMonthsRec`) | time, period, repeat cycle → record indices and weights | [verification matrix](verification_matrix.md) timing cases |
| Yearly file names | `MITgcm/pkg/exf/exf_getyearlyfieldname.F::<module>` (`exf_GetYearlyFieldName`) | base name + year → `name_YYYY` | lab_sea yearly case (planned) |
| Heat content of runoff | `MITgcm/pkg/exf/exf_mapfields.F::<module>` (`EXF_MAPFIELDS`) | `runoff`, `runoftemp` (`ALLOW_RUNOFTEMP`) → surface fluxes | `global_ocean.cs32x15/input.seaice` via `tests/mitgcm_oracle.sh` |
| Diagnostics | `MITgcm/pkg/exf/exf_diagnostics_fill.F::<module>` (`EXF_DIAGNOSTICS_FILL`) | `runoff` → diagnostics output | planned hold-exact direct check |
| Driver order | `MITgcm/pkg/exf/exf_getforcing.F::<module>` (`EXF_GETFORCING`) | calls `EXF_GETFFIELDS`, then `EXF_MAPFIELDS` | — |
| Template: sparse NetCDF read and point-to-tile | `MITgcm/pkg/profiles/profiles_init_fixed.F::<module>` (`PROFILES_INIT_FIXED`), `MITgcm/pkg/obsfit/obsfit_init_fixed.F::<module>` (`OBSFIT_INIT_FIXED`), `MITgcm/pkg/obsfit/obsfit_read_obs.F::<module>` (`OBSFIT_READ_OBS`) | NetCDF points → per-tile lists | reference only |
| **Planned:** sparse file init | new exf routine(s) (RUNOFF-004) | NetCDF static arrays → per-tile `(i,j,k,bi,bj)`, fractions, global fraction check | lab_sea / cs32 sparse cases |
| **Planned:** sparse record read and apply | new exf routine(s) (RUNOFF-004, RUNOFF-005) | `flux(time,source)` records → `runoff` (m/s) = Σ flux·frac/rA | dense-vs-sparse oracles |
| Runoff file schema and integrity checker | `MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/__init__.py::<module>` (package `MITgcmutils.runoff`; planned modules `schema`, `check` (CLI), `example`, RUNOFF-001) | sparse runoff NetCDF → rule findings (E/W/I), exit code | [runoff schema](runoff_schema.md) §9; planned `tests/runoff/` |
| **Planned:** converter | `tools/runoff/` (RUNOFF-002) | dense MITgcm binary + grid → sparse NetCDF | pytest round-trip (planned) |
| 3D (later) | `MITgcm/model/src/apply_forcing.F::<module>` (`APPLY_FORCING_T`), `MITgcm/model/src/integr_continuity.F::<module>` (`INTEGR_CONTINUITY`) | `addMass`, `temp_addMass`, `salt_addMass` | out of phase 1 scope |

## Verification routes

- **Single experiment:** `tests/mitgcm_oracle.sh <experiment> <input_dir> [-mpi N] [-j N]`
  compiles into `build_esx[_mpiN]`, runs into `output_esx_<input>[_mpiN]`, and
  compares against `results/`. It exits non-zero on build failure, abnormal run
  end or FAIL.
- **Suites** (configured in [project.json](../esx/project.json)):
  - `focused`: cs32 `input.seaice` and lab_sea `input`.
  - `scientific`: adds MPI variants and the no-change experiments.
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
