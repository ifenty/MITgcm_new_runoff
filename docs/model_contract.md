# Sparse runoff forcing: model contract

> **Status: design contract, not yet implemented.** It describes the intended
> behavior of sparse runoff, delivered by a new package `pkg/rnf` that feeds
> `pkg/exf`. The integration choices and their source citations are in
> [the package design](package_design.md), which is proposed and awaits review.
> Open design points are tracked as issues in
> [open_issues.md](../open_issues.md) (`RUNOFF-*`). Once code lands, update each
> section to describe the implemented behavior, and link the source and tests.

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
  daily, monthly (calendar months) or yearly intervals.
- **Timing settings:** runtime settings (start date, period, repeat cycle) come
  from file attributes or from the package namelist `data.rnf`. **`data.rnf`
  overrides the file.**
- **Yearly files:** with `RNF_useYearlyFiles`, a name ending in `_YYYY` is chosen
  by model year with the exf naming routine
  (`pkg/exf/exf_getyearlyfieldname.F`).
- **Interpolation:** set in `data.rnf` (`RNF_holdRecord`), either exf-style
  linear interpolation between the bracketing records or holding each record's
  value exactly for its interval.
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
  sources. The converter picks chunk shape and compression from a measured read
  benchmark and documents the choice (RUNOFF-001 / RUNOFF-002).
- A missing or fill value in the flux stops the run with an error naming the
  source and time (owner decision, 2026-09-29).
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
   the source id. The fraction sum of item 4 does not catch a negative index,
   because integer division would place it on a tile.
3. Each tile maps the global indices that fall on it to local `(i,j,k,bi,bj)` and
   stores, for each source present on the tile, its local cells and fractions.
   The placement uses the arithmetic `pkg/mdsio` uses for a global file, never
   the grid geometry. The level is stored with each target; schema 1.0 allows
   only the surface.
4. Each source's fractions are summed over all tiles and processes with
   `GLOBAL_SUM_*`. If any source differs from 1.0 by more than 1e-6, the run stops.
   This also catches a target on a blank exch2 tile, which no tile owns, so the
   sum comes up short. Land targets and off-grid indices are caught by items 5
   and 2.
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
  - A source without a temperature contributes at the surface water temperature.
  - A source without a salinity contributes S = 0.
  - Where `F_c = 0`, `X_c` is unused.
- **Temperature, salinity and tracers enter as tendency terms** at the target
  cell, added in `APPLY_FORCING_T`, `APPLY_FORCING_S` and
  `PTRACERS_APPLY_FORCING`. With `m = rhoConstFresh · F_c / rA` the runoff mass
  flux in kg m⁻² s⁻¹, each term is

  `g_X += [ Σ_s m_s·X_s − m·X_ref ] · mass2rUnit / (drF · hFacC)`,

  where `X_ref` is the value the model's freshwater formulation has already
  given to that water. For temperature the sums run only over sources that
  carry one. "Uniform reference" below is branch U of the package design: the
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
  (read in `rnf_readparms.F`, reported in `rnf_summary.F`). The only edit inside
  exf is one guarded call in `exf_getffields.F`.
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
