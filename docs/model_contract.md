# Sparse runoff forcing: model contract

> **Status: design contract, partly implemented.** It describes the intended
> behavior of sparse runoff, delivered by a new package `pkg/rnf` that feeds
> `pkg/exf`. The integration choices and their source citations are in
> [the package design](package_design.md). Open design points are tracked as
> issues in [open_issues.md](../open_issues.md) (`RUNOFF-*`).
>
> **Implemented (RUNOFF-004):** the initialization of "Model behavior" below
> (items 1 to 8, in `pkg/rnf/rnf_init_fixed.F`, `rnf_readparms.F` and
> `rnf_check.F`) and the volume flux of "Each time step"
> (`rnf_init_varia.F`, `rnf_fields_load.F`, `rnf_exf_runoff.F`).
> **Implemented (RUNOFF-005):** the time handling of that volume flux
> (`rnf_time_setup.F`, `rnf_getrec.F`) — constant, a fixed period with or
> without a repeat cycle, a monthly climatology, consecutive calendar
> months, `_YYYY` yearly files, exf-style interpolation and hold-exact —
> with record selection delegated to the `pkg/exf` routine of each mode.
> **Implemented (RUNOFF-013):** the temperature, the salinity and the
> passive tracers — read with the flux (`rnf_nc_utils.F`), spread over the
> target cells as flux-weighted sums (`rnf_fields_load.F`) and applied as
> tendency terms at the target level (`rnf_tendency_apply.F`), with the
> diagnostics of those terms (`rnf_diagnostics_init.F`) and the refusal of
> a tracer name that matches no ptracer.
> Not implemented: `yearly` *sampling*
> (one record per calendar year) is refused rather than mapped, because exf
> has no such mode; the budget checks over time and over the domain
> (RUNOFF-016); the input-only diagnostics and the monitor (RUNOFF-015);
> and the `addMass` path for interior and under-shelf targets (RUNOFF-025).
> The source routines and their tests are
> listed in [the code map](code_map.md), the tests and their limits in
> [the qualification matrix](verification_matrix.md).

Paths below are relative to `MITgcm/`, a clone of the fork `ifenty/MITgcm` on the
branch `new_runoff`.

## Purpose

Replace the dense exf `runoffFile`, which holds one value per surface cell per
record, with NetCDF input organized by **source**, such as a river, a glacier or
any other id. The stored tables and the I/O scale with the number of sources and
target cells, not with the grid size. On each tile the package adds a small,
fixed number of 2D work fields.

## Input: one NetCDF file per run (phase 1)

For each source:

- **id:** an alphanumeric code, such as a river name or glacier name.
- **target cells:** one or more ocean cells, given as 0-based global indices. A
  cell's index is its position in the flattened global 2D layout of a dense
  `runoffFile` on that grid, including exch2/LLC layouts. Phase 1 uses only
  surface cells. "Surface" is the model's surface level of the column: level 1
  in z coordinates, level `Nr` in pressure coordinates.
- **fraction:** one per (source, cell) pair, ≥ 0. Each source's fractions sum to
  1.0 across the whole domain, within 1e-6.
- **time series** on the single time axis shared by all sources:
  - `flux`: volume flux in m³/s (required)
  - temperature in °C (optional): if absent, runoff enters at the surface water
    temperature, as exf does now
  - salinity (optional, default 0)
  - passive tracer concentrations (optional, any number), matched to ptracers
    **by name**; an unmatched name is a fatal error
- **Precision:** data may be stored as `float32`.

The exact layout (names, types, units, metadata and integrity rules) is
[the runoff schema](runoff_schema.md).

The file is built offline for one specific grid and its coastline. Moving runoff
onto ocean cells is done offline. The Python converter
(dense MITgcm binary → NetCDF) produces files for the oracle tests.

### Time axis

- **Format:** a CF-style `time` variable (`units = "days since …"`, with a
  `calendar` attribute), as numpy `datetime64` writes.
- **Sampling:** constant, repeating (climatology) or non-repeating, at hourly,
  daily or monthly (calendar months) intervals. Yearly *intervals* — one record
  per calendar year — are **refused**: exf has no such mode and schema 1.0 puts
  a yearly record's `time` at the midpoint of its year, so mapping it needs its
  own code, which is not written (`rnf_time_setup.F`).
- **Timing settings:** runtime settings (start date, period, repeat cycle) come
  from file attributes or from the package namelist `data.rnf`. **`data.rnf`
  overrides the file.** The file's side is the normative CF axis
  (`mitgcm_time_sampling`, `mitgcm_time_period`, `mitgcm_time_repeat`,
  `time:units`, `time:calendar`, `time`, `time_bnds`), not the converter's
  `exf_*` provenance attributes, which the reader does not read.
- **Repeating series:** the cycle of a fixed-period climatology is the span of
  `time_bnds`, and it is anchored on the real date record 1 carries, so it
  wraps exactly as a dense run with the same `runoffRepCycle` does and drifts
  against calendar years at every leap year. Anchoring on a nominal calendar
  year instead is a different answer once a leap day has intervened.
- **Yearly files:** with `RNF_useYearlyFiles`, `RNF_file` is the base name of a
  `<base>_YYYY.nc` set (a trailing `.nc` of the name given is replaced), chosen
  by the model year exf's own record selection returns. This differs from exf's
  dense naming, which appends `_YYYY` to a name without an extension
  (`pkg/exf/exf_getyearlyfieldname.F`). Yearly files need `pkg/cal`.
- **Interpolation:** set in `data.rnf` (`RNF_holdRecord`), either exf-style
  linear interpolation between the bracketing records or holding each record's
  value exactly for its interval. The interval of hold-exact is the record's
  own time up to the next record's for a fixed period — so a yearly-file
  record at 1 January 00:00, which is the start of its bounds, is held over
  that day — and the calendar month for the two monthly modes, which is not
  the nearer of the two mid-month times the interpolation brackets with.
- **One set of record weights:** flux, temperature, salinity and every tracer
  use the same records and the same weights at each step.

### Scale requirement

The main use case is daily runoff for 50 years (about 18,260 records) at every
coastal cell of a global 2 km model (roughly 10⁵–10⁶ cells, an estimate). The flux
alone is tens of GB in `float32`, and T, S and each tracer add about the same.

- Never read whole time series. Read only the records that bracket the current
  time, as dense exf fields do.
- Store time as the slowest (unlimited) dimension, e.g. `flux(time, source)`.
  **Chunking** (owner decision, 2026-09-29): use whatever layout is most efficient
  for the model's access pattern, which reads the bracketing records for all
  sources. The current default is the layout of
  [runoff schema](runoff_schema.md) §8, which the converter writes: one record
  per chunk along time, with deflate compression. A measured read benchmark at
  high resolution settles the final chunk shape and compression (RUNOFF-007).
- A missing or fill value in the flux stops the run with an error naming the
  source and time (owner decision, 2026-09-29). A `_FillValue` or
  `missing_value` attribute of the flux that cannot be read as one number
  (text, for instance) also stops the run: it is not treated as absent.
- A flux that is present but larger in absolute value than `RNF_srcFluxMax`
  = 10⁷ m³/s also stops the run, naming the source, the record and the value
  (`RNF_NC_READ_ONE`, RUNOFF-030). That is the package's own sanity bound on
  the input, and it is the reason `EXF_CHECK_RANGE` may skip its runoff upper
  bound of 10⁻⁶ m/s when `useRNF` is true: see
  [package design](package_design.md) decision 2 for the derivation of the
  number and for what a per-source bound does and does not cover. The
  per-cell *sign* is still guarded by exf, whose negative-runoff test is not
  skipped — but note the coverage, because it is easy to state backwards: that
  sign test is inside `EXF_CHECK_RANGE`, which runs at `nIter0` only unless
  `exf_debugLev` ≥ `debLevC` (`exf_getforcing.F:346-349`), so it is checked
  once per run. So was the upper bound it sits beside, before this change;
  `RNF_srcFluxMax` in `RNF_NC_READ_ONE` is the one with per-record coverage.
  The asymmetry — magnitude every record, sign once — is therefore real but
  pre-existing, and this change does not alter it. The skip alone is not
  sufficient, so the exf `sflux` bound is
  conditioned on `useRNF` as well — it is applied to `sflux + runoff`, since
  `exf_getforcing.F:313` subtracts runoff into `sflux` before the check — and
  with both conditions a point source runs with `useExfCheckRange=.TRUE.`
  while an out-of-range `evap - precip` is still refused. The dense
  `runoffFile` path is untouched by both.
- Read the static index and fraction arrays (~10⁶ entries) once at init.

## Model behavior

### Initialization: tile decomposition

1. The master thread reads the static arrays with `NF_*` calls, following
   `pkg/profiles/profiles_init_fixed.F` and `pkg/obsfit`. Every process reads
   the file. The NetCDF code is compiled only when the build has NetCDF
   (`HAVE_NETCDF`); switching the package on in a build without it is a fatal
   error. This refusal and the one for a blank file name are raised when the
   parameters are read, before the static read.
2. Index ranges are checked in the model before any placement:
   `0 ≤ target_cell < nx·ny` of the model's global layout, and
   `0 ≤ target_source < n_source`. A value outside is a fatal error that names
   the source id; a `target_source` outside has no source to name, and its
   error gives the index of the table entry. The fraction sum of item 4 does
   not catch a negative index, because integer division would place it on a
   tile.
3. Each tile maps the global indices that fall on it to local `(i,j,k,bi,bj)` and
   stores, for each source present on the tile, its local cells and fractions.
   The placement uses the arithmetic `pkg/mdsio` uses for a global file, never
   the grid geometry. The level is stored with each target; schema 1.0 allows
   only the surface.
4. Each source's fractions are summed over all tiles and processes with
   `GLOBAL_SUM_*`. If any source differs from 1.0 by more than 1e-6, the run stops.
   This also catches a target that no tile owns, when its fraction is more
   than that tolerance, because the sum comes up short: one on a blank exch2
   tile, or one whose index is in range but on a cell of the global layout
   that no facet uses. Land targets and off-grid
   indices are caught by items 5 and 2.
5. A target cell with surface `maskC = 0` is a fatal error that names the source
   id.
6. A target with `maskInC = 0`, beyond an open boundary, is a fatal error that
   names the source id. With `useRealFreshWaterFlux` the model multiplies the
   freshwater flux by this mask (`model/src/external_forcing_surf.F`), so the
   volume would be lost.
7. A surface target under an ice shelf is a fatal error that names the source
   id. `pkg/shelfice` sets the surface freshwater flux to zero there
   (`pkg/shelfice/shelfice_forcing_surf.F`), so the volume would be lost. These
   targets need the interior-level path planned with schema 1.1. Until that
   path exists the package also refuses to run with `SHI_update_kTopC`, the
   `pkg/shelfice` option that lets the shelf edge move over a target during
   the run.
8. Setting both the sparse file and a dense `runoffFile` is a fatal error; they
   are mutually exclusive. The same holds for a dense `runoftempfile`, for a
   non-zero `runoffconst` and for `exf_outscal_sflux ≠ 1`: exf applies that
   factor to the freshwater flux but not to its runoff heat terms, so the heat
   and salt terms below are exact only for a factor of 1. The package needs
   `useEXF` and exf compiled with `ALLOW_RUNOFF`. `exf_inscal_runoff` and
   `runoff_exfremo_*` are not applied to the sparse flux.

### Each time step

- `runoff(i,j,bi,bj) = Σ_s flux_s(t) · frac_{s,c} / rA(i,j,bi,bj)`, in m/s. The
  package assigns this to the existing exf `runoff` field each step, so
  `exf_mapfields.F` and everything downstream (free surface, virtual salt flux,
  sea ice) are unchanged.
- **Several sources feeding one cell** (owner decision, 2026-09-29): combine
  them in a physically consistent way.
  - Volume fluxes add: `F_c = Σ_s flux_s·frac_{s,c}`.
  - Temperature, salinity and every tracer are **flux-weighted means**:
    `X_c = Σ_s flux_s·frac_{s,c}·X_s / F_c`. This conserves heat content, salt
    and tracer mass.
  - A source without a temperature contributes at the surface water
    temperature, except in a build without exf `ALLOW_ATM_TEMP` that sets
    `temp_EvPrRn`, where it enters at `temp_EvPrRn`
    ([package design](package_design.md), decision 3, "Missing temperature").
  - A source without a salinity contributes S = 0.
  - Where `F_c = 0`, `X_c` is unused.
- **Temperature, salinity and tracers enter as tendency terms** at the target
  cell, added in `APPLY_FORCING_T`, `APPLY_FORCING_S` and
  `PTRACERS_APPLY_FORCING`. With `m = rhoConstFresh · F_c / rA` the runoff mass
  flux in kg m⁻² s⁻¹, each term is

  `g_X += [ Σ_s m_s·X_s − m·X_ref ] · mass2rUnit / (drF · hFacC)`,

  where `X_ref` is the value the model's freshwater formulation has already
  given to that water. For temperature **both** sums run only over the sources
  that carry one, i.e. `[ Σ_s m_s·T_s − m_T·T_ref ]` with
  `m_T = Σ_{s: T present} m_s`: a source without a temperature then
  contributes nothing to the term and enters at `X_ref`, which is what makes
  the missing value mean "the same as absent".
  "Uniform reference" below is branch U of the package design: the
  model uses one reference value for the whole surface, which happens when
  `convertFW2Salt ≠ −1` and the run does not combine a real freshwater flux
  with a nonlinear free surface or pressure coordinates. Every other
  formulation uses the local value. The derivation for each case is in
  [the package design](package_design.md), decisions 3 and 4, which this table
  restates.

  | Quantity | `X_ref` | When |
  |---|---|---|
  | Temperature | local `θ` | `temp_EvPrRn` unset; or set in a build with exf `ALLOW_ATM_TEMP` |
  | Temperature | `temp_EvPrRn` | set in a build without `ALLOW_ATM_TEMP` |
  | Salinity | `salt_EvPrRn` | set (default 0) |
  | Salinity | local `S` | `salt_EvPrRn` unset, local-value formulations |
  | Salinity | `convertFW2Salt` | `salt_EvPrRn` unset, uniform reference |
  | Tracer `n` | `PTRACERS_EvPrRn(n)` | set |
  | Tracer `n` | local tracer value | unset, local-value formulations |
  | Tracer `n` | `PTRACERS_ref(ks,n)` | unset, uniform reference |

  - With no salinity variable and the default `salt_EvPrRn = 0` the salinity
    term is zero and the result equals the dense path.
  - A tracer without a file variable gets no term.
  - The exf `runoftemp` field is not used: exf applies it only when a dense
    `runoftempfile` is named.
- **Time level of these terms.** They use the runoff fields of the same step as
  the freshwater flux the model uses for its own temperature and salinity
  terms.
  - A run that combines a real freshwater flux with a nonlinear free surface or
    pressure coordinates, and does not use `staggerTimeStep`: the fields one
    time step earlier, because the model's flux lags by one step. At the first
    step of a run that starts at iteration 0 the model's lagged flux is zero
    and the terms are zero. At the first step after a restart the fields are
    evaluated one step before the restart time; if a non-repeating series does
    not reach back that far, the run stops with an error that names the time.
  - Every other case, including all runs with `staggerTimeStep`: the fields at
    the current time.
  - This rule assumes `exactConserv`: the model sets its lagged flux `PmEpR`
    only in the `exactConserv` branch of `model/src/integr_continuity.F`. A
    nonlinear free surface always has it, because the model stops otherwise
    (`model/src/config_check.F`, the `nonlinFreeSurf` test).
- **Known differences from exf `runoftemp`:** the tendency term is not scaled by
  the open-water fraction under sea ice, is not part of the surface flux that
  KPP reads, and is not included in the `TFLUX`/`SFLUX` diagnostics. In a build
  without `ALLOW_ATM_TEMP` that sets `temp_EvPrRn`, the dense path assumes
  runoff arrives at `θ` although the model delivers it at `temp_EvPrRn`; the
  package delivers the source heat.

### Invariants

- Total applied volume flux, `Σ runoff·rA`, equals `Σ_s flux_s(t)` to the fraction
  tolerance (1e-6 relative). The reader does not renormalize fractions; the file's
  fractions are used as stored, and the checker and the init check bound the error.
- The model carries runoff as a mass flux, `rhoConstFresh · runoff`, and converts
  it back to volume with `rhoConst`. The model volume therefore grows by
  `Σ_s flux_s · rhoConstFresh / rhoConst`, and heat, salt and tracer input are
  `rhoConstFresh · Σ_s flux_s · frac · X_s` in mass terms. Budget checks use
  these forms.
- Results are independent of the tile/process layout to the oracle threshold.
- With the feature compiled in but unused, results are bit-for-bit unchanged.

## Implementation constraints

- Fortran 77 fixed-form with CPP, in a package `pkg/rnf`: compile switch
  `ALLOW_RNF`, runtime switch `useRNF` in `data.pkg`, parameters in `data.rnf`
  (read in `rnf_readparms.F`, reported in `rnf_summary.F`). The edits inside exf
  are **two**, and this is the footprint the upstream PR carries: one guarded
  call in `exf_getffields.F` (`RNF_EXF_RUNOFF`), and two tests conditioned on
  `useRNF` in `EXF_CHECK_RANGE` (`exf_check_range.F`) — the runoff upper bound
  skipped, and the `sflux` bound applied to `sflux + runoff` so an out-of-range
  `evap - precip` is still refused. Both exf conditions are guarded by `useRNF`
  alone, so a build without `pkg/rnf` in use behaves exactly as before, the
  dense `runoffFile` path included. Nothing else in `pkg/exf` changed. See
  [package design](package_design.md) decision 2.
- No pickup file: the record state is a function of model time. The
  previous-step fields of the time-level rule are zero at a start from
  iteration 0 and are evaluated from the records at a restart.
- TAF-friendly code, because exf runoff is a control variable in ECCO setups
  (`pkg/exf/exf_ad_*`, `pkg/autodiff/check_lev1_dir_forcing.h`). Adjoint tests
  come later.
- Phase 1 supports one file, but the data structures must not assume a single
  file.

## Verification

See [the qualification matrix](verification_matrix.md).
