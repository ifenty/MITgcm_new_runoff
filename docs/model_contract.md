# Sparse runoff forcing: model contract

> **Status: design contract, not yet implemented.** It describes the intended
> behavior of the sparse-runoff extension to `pkg/exf`. Open design points are
> tracked as issues in [open_issues.md](../open_issues.md) (`RUNOFF-*`). Once code
> lands, update each section to describe the implemented behavior, and link the
> source and tests.

Paths below are relative to `MITgcm/`, a clone of the fork `ifenty/MITgcm` on the
branch `new_runoff`.

## Purpose

Replace the dense exf `runoffFile`, which holds one value per surface cell per
record, with NetCDF input organized by **source**, such as a river, a glacier or
any other id. Model memory and I/O scale with the number of sources and target
cells, not with the grid size.

## Input: one NetCDF file per run (phase 1)

For each source:

- **id:** an alphanumeric code, such as a river name or glacier name.
- **target cells:** one or more ocean cells, given as 0-based global indices. A
  cell's index is its position in the flattened global 2D layout of a dense
  `runoffFile` on that grid, including exch2/LLC layouts. Phase 1 uses only
  surface cells.
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

The file is built offline for one specific grid and its coastline. Moving runoff
onto ocean cells is done offline. The Python converter
(dense MITgcm binary → NetCDF) produces files for the oracle tests.

### Time axis

- **Format:** a CF-style `time` variable (`units = "days since …"`, with a
  `calendar` attribute), as numpy `datetime64` writes.
- **Sampling:** constant, repeating (climatology) or non-repeating, at hourly,
  daily, monthly (calendar months) or yearly intervals.
- **Timing settings:** runtime settings (start date, period, repeat cycle) come
  from file attributes or from `data.exf`. **`data.exf` overrides the file.**
- **Yearly files:** a name ending in `_YYYY` is chosen by model year, following
  exf `useExfYearlyFields` (`pkg/exf/exf_getyearlyfieldname.F`).
- **Interpolation:** set in `data.exf`, either exf-style linear interpolation
  between the bracketing records or holding each record's value exactly for its
  interval.

### Scale requirement

The main use case is daily runoff for 50 years (about 18,260 records) at every
coastal cell of a global 2 km model (roughly 10⁵–10⁶ cells, an estimate). The flux
alone is tens of GB in `float32`, and T, S and each tracer add about the same.

- Never read whole time series. Read only the records that bracket the current
  time, as dense exf fields do.
- Store time as the slowest (unlimited) dimension, e.g. `flux(time, source)`,
  with one-record chunks, so one record is one contiguous read.
- Read the static index and fraction arrays (~10⁶ entries) once at init.

## Model behavior

### Initialization: tile decomposition

1. The master thread reads the static arrays with `NF_*` calls, following
   `pkg/profiles/profiles_init_fixed.F` and `pkg/obsfit`.
2. Each tile maps the global indices that fall on it to local `(i,j,k,bi,bj)` and
   stores, for each source present on the tile, its local cells and fractions.
   `k` is stored even though it is always 1 in phase 1.
3. Each source's fractions are summed over all tiles and processes with
   `GLOBAL_SUM_*`. If any source differs from 1.0 by more than 1e-6, the run stops.
   This also catches cells on land, on blank exch2 tiles or off the grid, because
   those drop out and the sum comes up short.
4. A target cell with surface `maskC = 0` is a fatal error that names the source
   id.
5. Setting both the sparse file and a dense `runoffFile` is a fatal error; they
   are mutually exclusive.

### Each time step

- `runoff(i,j,bi,bj) = Σ_s flux_s(t) · frac_{s,c} / rA(i,j,bi,bj)`, in m/s. This
  fills the existing exf `runoff` field, so `exf_mapfields.F` and everything
  downstream are unchanged.
- **Several sources feeding one cell** (owner decision, 2026-09-29): combine
  them in a physically consistent way.
  - Volume fluxes add: `F_c = Σ_s flux_s·frac_{s,c}`.
  - Temperature, salinity and every tracer are **flux-weighted means**:
    `X_c = Σ_s flux_s·frac_{s,c}·X_s / F_c`. This conserves heat content, salt
    and tracer mass.
  - A source without a temperature contributes at the surface water temperature.
  - A source without a salinity contributes S = 0.
  - Where `F_c = 0`, `X_c` is unused.
- If temperature is present, `runoftemp` is filled with the cell's flux-weighted
  temperature.
- Salinity and tracers have no existing exf runoff field. Their plumbing is open
  (RUNOFF-008).

### Invariants

- Total applied volume flux, `Σ runoff·rA`, equals `Σ_s flux_s(t)`.
- Results are independent of the tile/process layout to the oracle threshold.
- With the feature compiled in but unused, results are bit-for-bit unchanged.

## Implementation constraints

- Fortran 77 fixed-form with CPP. `#ifdef ALLOW_<FEATURE>` inside exf, plus a
  runtime switch in `data.exf` (read in `exf_readparms.F`, reported in
  `exf_summary.F`).
- TAF-friendly code, because exf runoff is a control variable in ECCO setups
  (`pkg/exf/exf_ad_*`, `pkg/autodiff/check_lev1_dir_forcing.h`). Adjoint tests
  come later.
- Phase 1 supports one file, but the data structures must not assume a single
  file.

## Verification

See [the qualification matrix](verification_matrix.md).
