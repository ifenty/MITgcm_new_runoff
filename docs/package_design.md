# Runoff package design: architecture and MITgcm integration

> **Status: reviewed design (RUNOFF-010, two independent reviews, approved
> 2026-10-03); implementation in progress (skeleton: RUNOFF-012; static read,
> placement, file checks and the volume flux of a constant record:
> RUNOFF-004; time handling: RUNOFF-005; the temperature, salinity and
> tracer tendency terms and the reads they need: RUNOFF-013).** This is
> the decision record for RUNOFF-010. Every statement about existing MITgcm
> behavior was read from the live source in `MITgcm/` (branch `new_runoff`) and
> carries a `file:line` citation. Nothing here was established by running the
> model; statements about the planned package are design, not measurement.
> Where the implementation differs from a decision, the section
> [Implementation notes](#implementation-notes) says how and why.
> The file format is [the runoff schema](runoff_schema.md), and the behavior the
> package must deliver is [the model contract](model_contract.md).

Paths are relative to `MITgcm/`.

## Summary of decisions

| # | Topic | Choice |
|---|---|---|
| 1 | Package identity | New package `pkg/rnf` (`ALLOW_RNF`, `useRNF`, `data.rnf`). The name `runoff` is unusable. |
| 2 | Volume flux | The package fills the exf `runoff` field (option A). It needs `useEXF` and `ALLOW_RUNOFF`. `exf_mapfields.F` is unchanged. |
| 3 | Temperature, salinity | Tendency terms in `APPLY_FORCING_T/S`, each of the form mass flux × (source property − property the freshwater formulation already assigned). |
| 4 | Passive tracers | The same term, added in `PTRACERS_APPLY_FORCING`; names matched to `PTRACERS_names` at init. |
| 5 | Target level | Surface targets use the model's own surface-level rule (`1`, `Nr` or `kSurfC`). Targets under an ice shelf or beyond an open boundary are refused; so is a moving shelf edge (`SHI_update_kTopC`) until the `addMass` path exists. |
| 6 | Reading, decomposition | NetCDF `NF_*` calls under `HAVE_NETCDF`, master thread, every process reads; index range checked in the model; cell placement by the `mdsio` arithmetic. |
| 7 | Time handling | exf record routines for fixed and monthly sampling; own code for hold-exact, yearly sampling and the source-vector read. One set of record weights for all series. |
| 8 | Diagnostics, monitor, pickup | Nine diagnostics plus one per tracer; a monitor block; no pickup. |
| 9 | TAF | Fixed-size arrays from `RNF_SIZE.h` with runtime counts; state enters only through dense loops. |
| 10 | Namelist | `data.rnf`, namelist `RNF_PARM01`. |

## Notation

For one target cell `(i,j)` on a tile, at the time level of the current step:

- `flux_s` is the volume flux of source `s` in m³/s, `frac_{s,c}` its fraction for
  this cell, `rA` the cell area in m².
- `m = rhoConstFresh · Σ_s flux_s · frac_{s,c} / rA` is the runoff mass flux in
  kg m⁻² s⁻¹, summed over all sources that feed the cell.
- `m_T` is the same sum restricted to sources whose temperature is present.
- `(mT) = Σ_s m_s · T_s` over sources with a temperature, `(mS) = Σ_s m_s · S_s`
  over all sources, and `(mC_n) = Σ_s m_s · C_{s,n}` for tracer `n`.
- `μ = mass2rUnit`, which is `1/rhoConst` in z coordinates and `gravity` in
  pressure coordinates (`model/src/ini_parms.F:1570-1574`).
- `D = recip_drF(k) · recip_hFacC(i,j,k,bi,bj)` converts a surface flux in
  r-units per second into a tendency of the cell at level `k`.
- `θ`, `S` and `C_n` are the model temperature, salinity and tracer `n` in the
  target cell.

## How runoff travels through the model today

The package has to fit this path, so it is traced first.

### Call order within one time step

```
FORWARD_STEP
 |- LOAD_FIELDS_DRIVER                  forward_step.F:540
 |   |- (reset addMass)                 load_fields_driver.F:109-127
 |   |- EXF_GETFORCING                  load_fields_driver.F:214
 |   |   |- EXF_GETFFIELDS              exf_getforcing.F:199
 |   |   |   |- EXF_SET_FLD(runoff)     exf_getffields.F:422-435
 |   |   |   |- EXF_SET_FLD(runoftemp)  exf_getffields.F:437-450
 |   |   |   `- + xx_runoff control     exf_getffields.F:485-559
 |   |   |- sflux = evap - precip       exf_getforcing.F:304
 |   |   |- sflux = sflux - runoff      exf_getforcing.F:310-318
 |   |   |- EXF_DIAGNOSTICS_FILL        exf_getforcing.F:377
 |   |   |- EXF_MONITOR                 exf_getforcing.F:380
 |   |   `- EXF_MAPFIELDS (EmPmR, Qnet) exf_getforcing.F:383
 |   `- EXTERNAL_FIELDS_LOAD, GCHEM, RBCS   load_fields_driver.F:229-251
 |- DO_OCEANIC_PHYS                     forward_step.F:657
 |   |- THSICE_MAIN                     do_oceanic_phys.F:402
 |   |- SEAICE_MODEL                    do_oceanic_phys.F:453
 |   |- SHELFICE_/ICEFRONT_THERMODYNAMICS  do_oceanic_phys.F:523, 539
 |   |- EXTERNAL_FORCING_SURF           do_oceanic_phys.F:579
 |   |   |- PTRACERS_FORCING_SURF       external_forcing_surf.F:188-197
 |   |   `- SHELFICE_FORCING_SURF       external_forcing_surf.F:394-400
 |   `- KPP_CALC                        do_oceanic_phys.F:956
 |- THERMODYNAMICS                      forward_step.F:733 or 1005
 |   |- TEMP_INTEGRATE -> APPLY_FORCING_T   thermodynamics.F:321, temp_integrate.F:322
 |   |- SALT_INTEGRATE -> APPLY_FORCING_S   thermodynamics.F:332, salt_integrate.F:320
 |   `- PTRACERS_INTEGRATE -> PTRACERS_APPLY_FORCING
 |                                      thermodynamics.F:348, ptracers_integrate.F:301
 |- SOLVE_FOR_PRESSURE                  forward_step.F:904
 `- INTEGR_CONTINUITY                   forward_step.F:928
```

### Volume

- exf reads `runoff` in m/s (`pkg/exf/exf_getffields.F:422-435`) and subtracts it
  from `sflux` (`pkg/exf/exf_getforcing.F:310-318`).
- `EXF_MAPFIELDS` turns `sflux` into a mass flux:
  `EmPmR = exf_outscal_sflux · sflux · rhoConstFresh`
  (`pkg/exf/exf_mapfields.F:116-121`). `EmPmR` is in kg m⁻² s⁻¹.
- With `useRealFreshWaterFlux`, `EmPmR` enters the surface pressure solver as
  `cg2d_b = freeSurfFac · mass2rUnit · implicDiv2DFlow · rA · EmPmR / deltaTMom`
  (`model/src/solve_for_pressure.F:142-150`) and the free-surface tendency as
  `dEtaHdt = … − facEmP · EmPmR` (`model/src/integr_continuity.F:180-187`).
  Without it, `EmPmR` changes no volume: the solver term is skipped and
  `facEmP` is zero (`model/src/integr_continuity.F:92-93`).
- `PmEpR` is the copy used for tracer forcing. It is `−EmPmR` of the same step
  with `staggerTimeStep` (`model/src/external_forcing_surf.F:158-166`) and lags
  one step otherwise (`model/src/integr_continuity.F:172-179`).

Because `EmPmR` is a mass flux built with `rhoConstFresh` and the model converts
it back with `mass2rUnit = 1/rhoConst`, a runoff of `F` m³/s raises the model
volume by `F · rhoConstFresh / rhoConst`. In `global_ocean.cs32x15` this ratio is
1000/1035 (`verification/global_ocean.cs32x15/input.seaice/data:16-17`).

### Temperature and salinity of the freshwater

`EXTERNAL_FORCING_SURF` has three branches. `temp_EvPrRn` defaults to unset and
`salt_EvPrRn` to 0 (`model/src/set_defaults.F:264-265`); unset means "use the
local value" (`model/src/config_summary.F:407-412`). `convertFW2Salt` defaults to
35, or to −1 with `useRealFreshWaterFlux` or `selectAddFluid ≥ 1`
(`model/src/ini_parms.F:648-651`); −1 means "use local salinity"
(`model/src/config_summary.F:424-426`).

| Branch | Condition | Term added to `surfaceForcingT` | Term added to `surfaceForcingS` | Lines |
|---|---|---|---|---|
| N | (`nonlinFreeSurf > 0` or pressure coordinates) and `useRealFreshWaterFlux` | `PmEpR·(temp_EvPrRn − θ)·μ` if `temp_EvPrRn` is set | `PmEpR·(salt_EvPrRn − S)·μ` if `salt_EvPrRn` is set | `external_forcing_surf.F:261-288` |
| L | otherwise, `convertFW2Salt = −1` | `EmPmR·(θ − temp_EvPrRn)·μ` if set | `EmPmR·(S − salt_EvPrRn)·μ` if set | `external_forcing_surf.F:296-320` |
| U | otherwise | `EmPmR·(tRef(ks) − temp_EvPrRn)·μ` if set | `EmPmR·(convertFW2Salt − salt_EvPrRn)·μ` if set | `external_forcing_surf.F:322-349` |

Branch N covers z*, r* and the other nonlinear free-surface settings, because
its condition tests only `nonlinFreeSurf` and the coordinate. Branch L is the
linear free surface with a real freshwater flux. Branch U is the virtual salt
flux with a uniform reference salinity.

`surfaceForcingT` and `surfaceForcingS` are applied to the surface level as
`gT += surfaceForcingT · D` (`model/src/apply_forcing.F:617-636`) and the same
for salt (`model/src/apply_forcing.F:903-922`). The surface level is `kSurface`:
1 in z coordinates, `Nr` in pressure coordinates, and `kSurfC(i,j)` in
z coordinates with `useShelfIce` (`model/src/apply_forcing.F:466-474`).

### Heat content of exf runoff

- When `temp_EvPrRn` is set and `ALLOW_ATM_TEMP` is defined, exf adds
  `−Cp·(θ − temp_EvPrRn)·runoff·rhoConstFresh` to `Qnet`
  (`pkg/exf/exf_mapfields.F:175-185`). After
  `surfaceForcingT −= Qnet·μ/Cp` (`model/src/external_forcing_surf.F:225-231`)
  this cancels the branch-N term for the runoff part, so runoff enters at the
  surface water temperature (`pkg/exf/exf_mapfields.F:139-140`).
- With `ALLOW_RUNOFTEMP` and a `runoftempfile`, exf adds
  `Cp·(θ − runoftemp)·runoff·rhoConstFresh` to `Qnet`
  (`pkg/exf/exf_mapfields.F:199-211`). In tendency form this is
  `gT += rhoConstFresh·runoff·(runoftemp − θ)·μ·D` at the surface level.

### What sea ice and ice shelves do to these fields

- `pkg/seaice` rebuilds `EmPmR` from the exf fields:
  `EmPmR = HEFFM·((EVAP − PRECIP)·(1 − AREApreTH) − RUNOFF + …)·rhoConstFresh`
  (`pkg/seaice/seaice_growth.F:2381-2388`). Runoff is taken from the exf array
  and is not weighted by the open-water fraction.
- `pkg/seaice`, when built with `SEAICE_EXTERNAL_FLUXES`, takes the exf `Qnet`
  as the open-water heat flux
  (`pkg/seaice/seaice_budget_ocean.F:107-109`, called at
  `pkg/seaice/seaice_growth.F:738-742`), multiplies it by `1 − AREApreTH`
  (`pkg/seaice/seaice_growth.F:956-957`) and rebuilds `QNET` from the result
  (`pkg/seaice/seaice_growth.F:2209`, `2234`). The exf runoff heat terms are part
  of that `Qnet`, so under ice they are scaled by the open-water fraction while
  the runoff volume is not. Without that option `pkg/seaice` computes the
  open-water flux itself (`pkg/seaice/seaice_budget_ocean.F:110-149`) and does
  not use the exf `Qnet`.
- `pkg/thsice` also reads the exf array. `THSICE_MAP_EXF` adds
  `runoff·rhoConstFresh` to the precipitation it hands to the ice model
  (`pkg/thsice/thsice_map_exf.F:71-72`, called at
  `pkg/thsice/thsice_main.F:157-162`), and the liquid part, rain plus runoff, is
  passed to the ocean under the ice (`pkg/thsice/thsice_calc_thickn.F:1048-1049`).
  The ocean fields are then combined by ice fraction:
  `EmPmR = −icFrac·frw2oc + opFrac·EmPmR` and
  `Qnet = −icFrac·flx2oc + opFrac·Qnet`
  (`pkg/thsice/thsice_step_fwd.F:273-275`). Runoff reaches the ocean through
  both shares. The exf `Qnet`, with its runoff heat terms, keeps only the
  open-water share; for the ice-covered share `pkg/thsice` accounts for runoff
  heat itself, at the surface water temperature
  (`pkg/thsice/thsice_map_exf.F:104-121`).
- `pkg/shelfice` sets `surfaceForcingT`, `surfaceForcingS`, `EmPmR`, `Qsw` and
  `Qnet` to zero wherever `kTopC ≠ 0`
  (`pkg/shelfice/shelfice_forcing_surf.F:57-69`), then adds its own freshwater
  flux (`pkg/shelfice/shelfice_forcing_surf.F:101-112`).

## Decision 1: package identity

**Alternatives.**

- `runoff`. genmake2 defines `ALLOW_<PKG>` in upper case for every enabled
  package (`tools/genmake2:2741-2748`), so this package would define
  `ALLOW_RUNOFF`. That macro already selects the exf runoff code
  (`pkg/exf/EXF_FIELDS.h:273-278`, `pkg/exf/exf_getforcing.F:312-314`,
  `pkg/seaice/seaice_growth.F:2335-2337`). The package name would silently switch
  exf options on and off. Not usable.
- `rnf`. Three letters, in the style of `exf`, `kpp`, `flt`, `cal`.
- `discharge`. Descriptive and covers rivers, glaciers and later subglacial
  input, but long as a routine prefix.

**Choice.** `rnf`: directory `pkg/rnf`, macro `ALLOW_RNF`, switch `useRNF`,
parameter file `data.rnf`, routine prefix `RNF_`, diagnostics prefix `RNF`.

**Reason.** No directory `pkg/rnf` exists and a search of `*.F`, `*.h`, `*.rst`
and `genmake2` for `ALLOW_RNF`, `useRNF`, `RNF_` and `data.rnf` returned no
match.

**Files.**

| File | Content |
|---|---|
| `RNF_OPTIONS.h` | CPP options; includes `PACKAGES_CONFIG.h` and `CPP_OPTIONS.h` first |
| `RNF_SIZE.h` | array bounds (decision 9) |
| `RNF.h` | parameters and fields in common blocks |
| `rnf_readparms.F` | reads `data.rnf` (decision 10); returns at once if `useRNF` is false; refuses a blank `RNF_file` and a build without NetCDF, because these guard the static read (decision 6) |
| `rnf_check.F` | the remaining configuration refusals (decisions 2 and 5) |
| `rnf_init_fixed.F` | static read, cell placement, fraction check; calls summary and diagnostics init |
| `rnf_init_varia.F` | zeroes fields, loads the first records |
| `rnf_summary.F` | prints parameters and per-process counts |
| `rnf_diagnostics_init.F` | registers diagnostics |
| `rnf_nc_utils.F` | NetCDF helpers and error reporting |
| `rnf_getrec.F` | record indices and weights (decision 7) |
| `rnf_fields_load.F` | per step: read records, interpolate, build the dense fields |
| `rnf_exf_runoff.F` | copies the volume flux into exf `runoff` |
| `rnf_tendency_apply.F` | `RNF_TENDENCY_APPLY_T`, `_S`, `_PTR` |
| `rnf_diagnostics_fill.F`, `rnf_monitor.F` | output (decision 8) |
| `rnf_ad_diff.list`, `rnf_ad.flow` | TAF lists, as `pkg/mypackage/mypackage_ad_diff.list` and `mypackage_ad.flow` |

**Registration.** The sites in `PARAMS.h`, the `packages_*` routines and
`apply_forcing.F` copy the existing `ICEFRONT` entries. The Pattern column gives
the lines to follow or the insertion point.

| Site | Edit | Pattern |
|---|---|---|
| `model/inc/PARAMS.h` | `LOGICAL useRNF`, added to `COMMON /PARM_PACKAGES/` | `PARAMS.h:1079`, `1094-1108` |
| `model/src/packages_boot.F` | `useRNF` in `NAMELIST /PACKAGES/`, default `.FALSE.`, `PACKAGES_PRINT_MSG` | `packages_boot.F:46-98`, `113-164`, `388-390` |
| `model/src/packages_readparms.F` | `CALL RNF_READPARMS` under `ALLOW_RNF` | `packages_readparms.F:289-292` |
| `model/src/packages_init_fixed.F` | `CALL RNF_INIT_FIXED`, after `SHELFICE` and `PTRACERS` | `packages_init_fixed.F:491-498` |
| `model/src/packages_init_variables.F` | `CALL RNF_INIT_VARIA` | `packages_init_variables.F:408-415` |
| `model/src/packages_check.F` | `CALL RNF_CHECK`, with `PACKAGES_ERROR_MSG` when not compiled | `packages_check.F:372-377` |
| `model/src/load_fields_driver.F` | `CALL RNF_FIELDS_LOAD` before the exf block | `load_fields_driver.F:208-217` |
| `pkg/exf/exf_getffields.F` | `CALL RNF_EXF_RUNOFF` between the runoff read and the control block | `exf_getffields.F:450`, `485` |
| `model/src/apply_forcing.F` | `CALL RNF_TENDENCY_APPLY_T` and `_S` after the `ICEFRONT` calls | `apply_forcing.F:711-716`, `943-948` |
| `pkg/ptracers/ptracers_apply_forcing.F` | `CALL RNF_TENDENCY_APPLY_PTR` beside `GCHEM_ADD_TENDENCY` | `ptracers_apply_forcing.F:71-78` |
| inside the package, end of `RNF_FIELDS_LOAD` | `CALL RNF_DIAGNOSTICS_FILL` and `CALL RNF_MONITOR`, for the fields that do not depend on the model state | `exf_getforcing.F:377`, `380` |
| inside the package, `RNF_TENDENCY_APPLY_*` | diagnostics fill of the state-dependent terms, at the level where they are computed | `apply_forcing.F:607-613` |
| `pkg/pkg_depend` | `rnf +exf` | `pkg_depend:37-39` |

- `data.pkg` gains `useRNF=.TRUE.` only in experiments that use the package.
- `pkg/pkg_groups` is not changed. The default group is `gfd`, and forcing
  packages such as `exf` are not in any group.
- genmake2 needs no edit. It finds the package through `packages.conf`, applies
  `pkg_depend`, and writes `ALLOW_RNF` into `PACKAGES_CONFIG.h`
  (`tools/genmake2:2409`, `2723`, `2741-2748`).
- `model/src/external_forcing.F` holds the same `ICEFRONT` hooks for the build
  option `USE_OLD_EXTERNAL_FORCING` (`external_forcing.F:569-574`, `773-778`;
  selected at `apply_forcing.F:448-462`). The package does not add hooks there,
  and `RNF_CHECK` stops if that option is defined.

**Feature off.** Every hook that computes or assigns a field is inside
`#ifdef ALLOW_RNF` and `IF ( useRNF )`. Three files change in every build:
`PARAMS.h` and `packages_boot.F` gain the `useRNF` switch, and
`packages_check.F` gains the `#else` branch that reports a switch set without
the package compiled. None of them touches a model field. Results are therefore
bit-for-bit unchanged, both with the package left out of `packages.conf` and
with it compiled and `useRNF=.FALSE.`.

**Consequence for issues.** RUNOFF-012 builds this skeleton and registration.
RUNOFF-026 documents the package under `doc/phys_pkgs/`. RUNOFF-027 lints these
files. RUNOFF-004 moves from "exf routines" to `pkg/rnf`.

## Decision 2: volume flux path

**Alternatives.**

- **A. Fill exf `runoff`.** The package computes `Σ_s flux_s·frac_{s,c}/rA` in
  m/s and assigns it to the exf array before exf uses it.
- **B. Own contribution to `EmPmR`.** The package subtracts `m` from `EmPmR`
  through its own hook and needs no exf.
- **C. `addMass`.** The package adds `rhoConstFresh·flux·frac` in kg/s to the
  3D mass source `addMass`, which the model resets each step for packages to
  fill (`model/src/load_fields_driver.F:109-127`) and uses in the continuity
  equation (`model/src/integr_continuity.F:129-131`) and the pressure solver
  (`model/src/calc_div_ghat.F:126-134`).

**Choice.** A for every surface target. C is reserved for targets that are not
at the open sea surface (decision 5). B is specified below as the route for a
build without exf and is not scheduled.

**Reason.**

1. *A is correct in every freshwater formulation by construction.* With A, the
   dense and the sparse path differ only in how the numbers in `runoff(i,j)` are
   produced. Everything downstream (the three branches above, both free-surface
   options, sea ice) is the same code.
2. *Other code reads `runoff` directly.* `pkg/seaice` uses it to rebuild `EmPmR`
   and its freshwater and heat diagnostics
   (`pkg/seaice/seaice_growth.F:2332-2339`, `2381-2388`, `2396-2402`);
   `pkg/thsice` uses it for the water and heat it passes under the ice
   (`pkg/thsice/thsice_map_exf.F:71-72`, `104-121`);
   `pkg/bling` uses it for river nutrients (`pkg/bling/bling_main.F:225-229`);
   the runoff control variable is added to it
   (`pkg/exf/exf_getffields.F:522-524`); exf stores it for the adjoint
   (`pkg/exf/exf_getforcing.F:243-245`) and writes it as `EXFroff`
   (`pkg/exf/exf_diagnostics_fill.F:72-73`). With B or C none of these would see
   sparse runoff.
3. *B loses mass unless its hook sits after both ice packages.* A contribution
   added to `EmPmR` before `SEAICE_MODEL` is overwritten
   (`pkg/seaice/seaice_growth.F:2381-2388`). One added before `THSICE_MAIN` keeps
   only its open-water share (`pkg/thsice/thsice_step_fwd.F:273-275`), because
   the ice-covered share comes from the exf array, which would not hold it. A
   hook after both delivers the volume, and the terms of point 2 are still
   missing.
4. *C changes the physics seen by the surface schemes.* `addMass` is not part of
   `EmPmR`, so the virtual salt flux, `selectBalanceEmPmR`
   (`model/src/external_forcing_surf.F:98-109`) and the freshwater part of the
   KPP surface buoyancy flux (`pkg/kpp/kpp_calc.F:419-421`) would not include
   surface runoff. It also needs `selectAddFluid ≥ 1`, which is an error with a
   rigid lid (`model/src/config_check.F:837-845`) and, without
   `staggerTimeStep`, draws a warning of a one-step mismatch in its effect on
   temperature and salinity (`model/src/config_check.F:846-855`).

**Mechanism.**

- `RNF_FIELDS_LOAD` runs in `LOAD_FIELDS_DRIVER` before `EXF_GETFORCING`
  (`model/src/load_fields_driver.F:208-217`), at the same `myTime` exf uses. It
  fills the dense per-tile fields of the notation section.
- `RNF_EXF_RUNOFF` runs inside `EXF_GETFFIELDS`, after the runoff and runoff
  temperature reads (`pkg/exf/exf_getffields.F:422-450`) and before the control
  block (`pkg/exf/exf_getffields.F:485-559`). It assigns
  `runoff(i,j,bi,bj) = m / rhoConstFresh` over the tile interior, including zero
  where no source discharges. Assignment is needed because `EXF_SET_FLD` does
  nothing when `runofffile` is blank (`pkg/exf/exf_set_fld.F:117-121`), so
  nothing else resets the array, and the control block adds to it each step.
  It then enforces the per-cell magnitude bound `RNF_cellVolMax` on the field
  it has just assigned (RUNOFF-040, "The per-cell aggregate bound" below).
  Both halves are in this routine for the same reason: it is where the applied
  field exists and where `rA`, the top-layer thickness and the time step are
  all available.
- This call is **one of the two** changes to exf code; the other is the pair of
  tests conditioned on `useRNF` in `EXF_CHECK_RANGE`, described under "Known
  effects inherited from the dense path" below. Those two are the whole exf
  footprint. `exf_mapfields.F` is not edited.

**Mutual exclusion and other refusals in `RNF_CHECK`** (each a fatal error
through `PRINT_ERROR` and the package error count):

- `useRNF` without `useEXF`, or with `ALLOW_RUNOFF` undefined. The array does
  not exist without the macro (`pkg/exf/EXF_FIELDS.h:273-278`).
- `runofffile` not blank: a dense file and the sparse file are mutually
  exclusive. exf itself only checks the macro (`pkg/exf/exf_check.F:322-329`).
- `runoftempfile` not blank. Otherwise `EXF_MAPFIELDS` would apply the dense
  runoff temperature to the sparse volume (`pkg/exf/exf_mapfields.F:199-211`).
- `runoffconst ≠ 0`. exf initializes `runoff` to this constant
  (`pkg/exf/exf_init_varia.F:357-366`, `pkg/exf/exf_init_fld.F:90-92`) and the
  package would overwrite it without notice.
- `exf_outscal_sflux ≠ 1`. exf multiplies the whole `sflux`, runoff included,
  by this factor when it builds `EmPmR` (`pkg/exf/exf_mapfields.F:118`; default
  1, `pkg/exf/exf_readparms.F:717`). The exf runoff heat terms
  (`pkg/exf/exf_mapfields.F:175-185`, `199-211`) and the sea-ice packages use
  the unscaled array. The alternative, carrying the factor in the package
  terms, was rejected: those other readers would still disagree with `EmPmR`,
  so no choice of factor makes heat and salt consistent. With the factor at 1,
  runoff contributes exactly `m` to `EmPmR`, which decisions 3 and 4 assume.
- `SHI_update_kTopC` true (decision 5).

Two refusals guard the static read and cannot wait for `RNF_CHECK`, because
`PACKAGES_INIT_FIXED` runs before `PACKAGES_CHECK`
(`model/src/initialise_fixed.F:211`, `267`): a blank `RNF_file` and a build
without NetCDF. `RNF_READPARMS`, called from `PACKAGES_READPARMS`
(`model/src/initialise_fixed.F:133`), stops for these.

**exf input scaling is not applied.** `exf_inscal_runoff` and
`runoff_exfremo_*` are arguments of the `EXF_SET_FLD` call for the dense file
(`pkg/exf/exf_getffields.F:422-435`), which does nothing with a blank
`runofffile`. The sparse flux is used as stored, in m³/s.

**Known effects inherited from the dense path.**

- **`EXF_CHECK_RANGE`: two tests are conditioned on `useRNF`, and it takes
  both** (RUNOFF-030, implemented; the second half was added in correction
  round 1 after measurement showed the first was not sufficient). Before the
  change the routine stopped the run at the first step if `runoff` exceeded
  10⁻⁶ m/s on a wet cell, with `useExfCheckRange` defaulting to true
  (`pkg/exf/exf_readparms.F:307`), and a river of 1000 m³/s into one 2 km cell
  is 2.5·10⁻⁴ m/s — so every realistic point-source configuration on a fine
  grid stopped at its first step, and the only workaround was
  `useExfCheckRange=.FALSE.`, which disables the range checks of *every* exf
  field. Two conditions changed, in two `IF`s of
  `pkg/exf/exf_check_range.F`:
  - **the runoff upper bound** (the `ALLOW_RUNOFF` block, `:215-261`) now
    carries `.AND. .NOT.useRNF`;
  - **the `sflux` bound** (the freshwater-flux block, `:84-109`) is applied to
    `sflux + runoff` instead of to `sflux` when `useRNF`, re-adding what
    `EXF_GETFORCING` subtracted at `exf_getforcing.F:313` immediately before
    calling the routine at `:346-349`. Without this, relaxing the runoff bound
    achieves nothing: `sflux = evap - precip - runoff`, so any wet cell above
    10⁻⁶ m/s of runoff breaches `ABS(sflux) > 10⁻⁶` whatever the runoff test
    says. **It is a restore and not a removal:** what is tested with `useRNF`
    is `evap - precip`, which is the part of `sflux` this bound exists for,
    and an out-of-range `evap - precip` is still refused. The restore is
    written as a one-line `IF ( useRNF )` inside `#ifdef ALLOW_RUNOFF`,
    because the `runoff` array exists only under that option while the
    `sflux` test does not. The message literal is unchanged and now prints the
    quantity tested, which equals `sflux` itself on every non-`useRNF` run.
  - the **negative-runoff** test is unchanged and fires with `useRNF` true or
    false, so the sign of the applied field is still guarded per cell;
  - the four-line m/yr advisory of the runoff block is printed only when
    `.NOT.useRNF`. Its text is unchanged. With `useRNF` the only trigger left
    in the block is a negative value, and `exf_inscal_runoff` — the parameter
    the advisory names — is an argument of the `EXF_SET_FLD` call for the dense
    file and does not touch the sparse field at all, so printing it would name
    an unrelated setting;
  - every range check of every field other than those two is untouched — the
    two above are the whole exf footprint of this change — and **nothing
    changes at all with `useRNF` false**, the dense `runoffFile` path included. A dense
    `runoffFile` above 10⁻⁶ m/s is still refused twice over, by the runoff
    bound and by the `sflux` bound, and still needs
    `useExfCheckRange=.FALSE.`. That is a deliberate decision of correction
    round 1, not an oversight: the same pair has always fired for the dense
    path, so the defect is wider than `pkg/rnf` and belongs to the eventual
    upstream discussion.
  - `useRNF` is declared unconditionally in `model/inc/PARAMS.h:1080`, which
    `exf_check_range.F` already includes, so this pulls no new include into a
    routine compiled without `pkg/rnf` (`pkg/exf/exf_getffields.F:455` already
    tests `useRNF` the same way).

  **Why this relaxation is safe: it is strictly narrower than the status quo
  it replaces** (review B of correction round 2; this framing is its
  reasoning, and it is the justification the decision was missing). The
  question for a guard relaxation is not "is the guard weaker?" but "is the
  configuration better guarded than it was?", and here it demonstrably is:
  - **Before.** Every sparse configuration above 10⁻⁶ m/s had to set
    `useExfCheckRange=.FALSE.` and so lost the range check of *every* exf
    field — `hflux`, `sflux`, both wind stresses, the wind speeds, `atemp`,
    `aqh`, `precip`, `snowprecip`, `swflux` and `runoff` alike. That is not
    hypothetical: both enrolled tendency instruments did exactly that, and it
    was the only documented workaround.
  - **After.** Such a run keeps all of them. One test is skipped (the runoff
    upper bound) and one is narrowed to the quantity it is actually about
    (`sflux` to `evap - precip`); every other field is still checked, and the
    negative-runoff test still applies per cell.
  - **And the coverage of the magnitude check improves.** `EXF_CHECK_RANGE`
    runs at `nIter0` only, unless `exf_debugLev` ≥ `debLevC`
    (`exf_getforcing.F:346-349`), so the bound it replaced was tested once per
    run. `RNF_NC_READ_ONE` tests `RNF_srcFluxMax` on **every record as it is
    read**, for the whole run. A file whose later records are bad was not
    caught before and is now.

  Net: the sparse path is better guarded after this patch than before it, and
  it also gains an input bound that `pkg/exf` never had.

  **One asymmetry, stated in the right direction because it is easy to invert**
  (corrected 2026-10-06; an earlier framing had it backwards). The surviving
  negative-runoff test lives in `EXF_CHECK_RANGE`, so it is checked at
  `nIter0` only — magnitude is now checked on every record, sign once per run.
  That asymmetry is **pre-existing and unchanged by this patch**: the upper
  bound this change skips sat under the same `IF` and the same call gate, so it
  too was first-step-only. What the patch did was *add* per-record coverage of
  the magnitude, not remove per-record coverage of the sign, which never
  existed. Closing the sign gap would need a per-record sign test, which is a
  different check and not part of this issue.

  **Why a volume bound is the right *shape*, not merely a convenient number**
  (review B, same round). 10⁻⁶ m/s is a bound on a *rate*, and a rate bound on
  a point source is a statement about the grid rather than about the water: the
  same river is 2.5·10⁻⁴ m/s in a 2 km cell and 2.5·10⁻⁸ m/s in a 2° one, so no
  single value of a rate bound can serve both, and `pkg/rnf` must work on every
  MITgcm grid. The grid-independent quantity is the source volume flux in m³/s
  — which is what a river *is*, and what the file actually carries. That is why
  `RNF_srcFluxMax` is in m³/s and why it needs no retuning between grids or
  resolutions, and it is a stronger argument for the design than the
  "generous enough, tight enough" one it supersedes.

  **Measured, and each condition attributed separately** (2026-10-06, lab_sea,
  `tests/rnf/refusal_check.py`):
  - With both relaxations, `flux_at_source_max` — one source of 10⁷ m³/s on
    the lab_sea target cell, 3.21·10⁻⁴ m/s applied, 321 times the exf bound —
    **ends normally with `useExfCheckRange` at the lab_sea default `.TRUE.`**,
    on 1 and on 2 processes, printing neither warning and no m/yr advisory.
    This is the acceptance of the issue and it is an enrolled case.
  - Revert the `sflux` restore alone (`IF ( .FALSE. )`) and that case fails on
    the **`sflux`** warning; revert the runoff skip alone (`.AND. .TRUE.`) and
    it fails on the **runoff** warning, `0.321307089844219D-03`, which is the
    model's own print of the applied field and agrees with the 3.213071·10⁻⁴
    m/s computed from the file. So each condition is necessary and the two are
    attributed independently.
  - Replace the restore by a removal (`.AND. .NOT.useRNF` on the whole `sflux`
    test) and `sflux_out_of_range` fails on exactly the missing `sflux`
    warning while `flux_at_source_max` still passes. That pair is what
    separates "restore" from "remove".
  - `sflux_out_of_range` is the positive control of the restore: `useRNF`
    true, every flux of the file zeroed so the restored term is identically
    zero, `precipfile` blanked and `precipconst = 1·10⁻⁴` m/s, which is out of
    range on every wet cell of every tile — so every process stops with its
    own `STOP` line and the case is judgeable under `--mpi 2` as well.

  **The replacement bound.** With the exf upper bound skipped, the package
  bounds the *input* instead: `RNF_srcFluxMax` = 10⁷ m³/s on the volume flux of
  one source, enforced in `RNF_NC_READ_ONE` as each record is read and reported
  by `RNF_SUMMARY`. The number comes from the physics: the Amazon, the largest
  river on Earth, carries about 2.1·10⁵ m³/s and all the world's rivers
  together about 1.2·10⁶ m³/s, so one source id may hold 48 Amazons, or every
  river on Earth with a factor of 8 to spare, while a flux given per year
  rather than per second (3.2·10⁷ times too large) is refused above
  0.32 m³/s and a factor of 1000 (mm, or kg/s read as m³/s) above
  10⁴ m³/s, i.e. for any source the size of a real river. What the *applied*
  field may then reach depends on the grid, because the package applies
  `flux·frac/rA` with `frac` in [0,1]: 10⁷ m³/s is 3.2·10⁻⁴ m/s into the
  lab_sea target cell (`rA` = 3.112287·10¹⁰ m², measured) and 2.5 m/s into a
  2 km cell (4.0·10⁶ m²); a per-cell value of 10⁹ m/s, the kind of figure a
  unit error produces, would need a cell smaller than 10⁻² m² to get past the
  bound. **`RNF_srcFluxMax` is a file-scale unit-error filter, not a per-cell
  safety bound, and the record should not be read as implying otherwise**
  (sharpened by review B of correction round 2, whose measured counterexample
  this is). It does not see the cell, and the consequence is larger than "N
  sources may add up":
  - **Measured, not argued.** Review B built four sources each carrying
    exactly `RNF_srcFluxMax` and collapsed every target onto one lab_sea cell:
    **1.285228·10⁻³ m/s applied, 1285 times the bound that was relaxed, and
    the run ended normally with zero `EXF WARNING` lines**, the volume
    confirmed by the model's own `RNF_INIT_VARIA` flux sums. Its control at
    twice the bound per source *is* refused, so the guard was live and the
    aggregate simply is not what it bounds. That figure reproduces exactly
    from the cell area measured here: 4·10⁷ m³/s over
    `rA` = 3.112287377·10¹⁰ m² is 1.285228·10⁻³ m/s.
    The file was rebuilt from this description and re-measured on RUNOFF-040
    against the committed RUNOFF-030 build: exit 0, `Execution ended
    Normally`, **0** `EXF WARNING` lines, flux sums both 4.0·10⁷ m³/s, and an
    `EXFroff` dump with exactly one non-zero cell holding 1.2852284·10⁻³ m/s
    at `(i,j) = (12,2)` — the description reproduces to every digit it
    states. It is now the enrolled refusal case `cell_above_vol_max`, and
    what refuses it is `RNF_cellVolMax` (below); nothing in `RNF_srcFluxMax`
    changed.
  - **N is not small in the intended use case.** It is 10⁵–10⁶ sources (the
    global 2 km daily case of the model contract), so the aggregate headroom
    is five to six orders of magnitude, not a factor of a few.
  - **And the aggregate is reachable by a plausible fault, not only by a
    malicious file:** a converter index bug that collapses many sources onto
    one cell. Wrong tile/process mapping and silently dropped fractions are on
    this project's own highest-risk list, and this is the same family.
  - **At the intended resolution the bound sits above the operable per-cell
    value entirely.** `RNF_srcFluxMax` admits 2.5 m/s into a 2 km cell, while
    a physically correct Amazon in one 2 km cell is 5.25·10⁻² m/s — so even
    for a *single* source the bound is 48 times any real per-cell rate, and it
    constrains the file rather than the applied field.
  - A grid with cells far smaller than the ones quoted admits proportionally
    more still.

  **The gap is not closable by a different number, which is why no parameter
  was added.** Review B's judgment, accepted: a fixed header constant is the
  right mechanism and a `data.rnf` scalar would be cost without benefit,
  because the missing check is a different *shape* — a meaningful per-cell
  bound needs `rA`, the top-layer thickness and `deltaT` (it is a statement
  about how much water a column can take in one step), not a larger or smaller
  m³/s threshold. It was filed as its own follow-up rather than grown into
  this issue, and **RUNOFF-040 implemented it**: `RNF_cellVolMax`, the
  per-cell aggregate bound below. The mechanism is the one judged right here —
  a fixed header constant, not a `data.rnf` parameter.

  **The per-cell aggregate bound: `RNF_cellVolMax` = 0.2** (RUNOFF-040,
  `RNF_EXF_RUNOFF`, reported by `RNF_SUMMARY`). It is the companion of
  `RNF_srcFluxMax` and not a replacement for it: the one bounds the file per
  source, the other bounds the field per cell, and only together do they cover
  the error classes above.
  - **The quantity.** `|RNF_vflx(c)|·deltaTFreeSurf / (drF(ks)·hFacC(c,ks))`:
    the depth of water one step of runoff puts on the cell over the thickness
    of the cell it goes into. With a real freshwater flux that is the
    fractional change of the top-cell volume in that step — the runoff reaches
    `etaN` through `EmPmR` and `dEtaHdt`, integrated with `deltaTFreeSurf`
    (`model/src/integr_continuity.F:221`). With a linear free surface no
    volume moves and it is instead the fractional freshwater dilution the
    surface tracer forcing applies, where the model linearises the exact
    `1/(1+f)` to `1-f` with relative error exactly `f²` — the linear term
    being `EmPmR·(salt − salt_EvPrRn)·mass2rUnit`
    (`model/src/external_forcing_surf.F:310-316`).
    **That second reading holds only where `dTtracerLev(ks)` =
    `deltaTFreeSurf`.** They are equal in both test experiments but need not
    be: `deltaTFreeSurf` defaults to `deltaTMom`, *not* to `deltaTtracer`
    (`model/src/ini_parms.F:1068`, whose own comment calls that default
    "inappropriate" and advises `deltaTFreeSurf = deltaTtracer` under
    asynchronous stepping). cs32 has `deltaTMom` = 1200 against
    `deltaTtracer` = 86400 and escapes the trap only by setting
    `deltaTFreeSurf` = 86400 explicitly; on that ratio an asynchronously
    stepped set-up that left the default would make the **dilution** reading
    wrong by 72× while the **volume** reading stayed right. No enrolled case
    can see a mismatch. Whether to bound with
    `MAX(deltaTFreeSurf, dTtracerLev(ks))` is an open design question and is
    deliberately not settled here. Being dimensionless
    is the whole point: **one** number serves every grid, resolution and time
    step, which is precisely what the exf rate bound of 10⁻⁶ m/s could not do.
    It belongs in `RNF_EXF_RUNOFF` because that is where `rA` (through
    `RNF_vflx`), the thickness and the step are all available and where the
    applied field exists.
  - **Where 0.2 comes from — read this before raising the constant.** Two
    legs, both properties of `f` itself, and neither of them a threshold the
    model enforces:
    - **CFL.** The injected water has to leave the cell, and `f` is exactly
      the Courant number of the top-layer outflow the injection requires:
      `f ≤ 0.2` is `U·dt/dx ≤ 0.2` for the horizontal outflow `U` that
      carries the added volume away. 0.2 is a standard advective-CFL safety
      factor, a fifth of the stability limit.
    - **Linearisation.** The surface tracer forcing is first order in `f`
      with relative error exactly `f²`, so 0.2 is the share at which that
      error is 4%; beyond it the model's own dilution term is no longer a
      linearisation of anything.

    Both legs say *deliberate share*, not *edge*. For scale, MITgcm's own
    band on the surface-cell fraction is `hFacInf` = 0.2 to `hFacSup` = 2.0
    (`model/src/set_defaults.F:258-259`, documented at
    `model/inc/PARAMS.h:762` as "Threshold (inf and sup) for fraction size of
    surface cell"). **Note what that band is and is not:** it bounds the
    fraction itself, not its per-step change, and runoff *thickens* the
    surface cell, so from a full cell — `hFacC` = 1.0, measured at every
    target of both test grids — the band is first crossed at **+1.0**, at
    `hFacSup`. **`f` = 0.2 crosses nothing**; it is 4–5× inside the band,
    which is the margin the constant buys. An earlier version of this
    paragraph read `hFacInf` as a bound on the per-step change and called 0.2
    the edge of the band: wrong in both parts, caught independently by both
    reviewers, and corrected here without changing the value.

    Outside the band the model does not merely warn, and the two routines
    differ: `CALC_R_STAR` warns and then **stops** on the thin side
    (`model/src/calc_r_star.F:201-242`), while `CALC_SURF_DR`'s thin-side
    `STOP` is commented out (`model/src/calc_surf_dr.F:105-108`) and it
    clamps the surface to `Rmin_surf` instead.
  - **What it is on each grid** (measured). **The limit is not a constant of
    the grid:** it tracks the live `hFacC`, so on an r\* grid it moves with
    the state (see "the thickness is the live one" below). Each figure says
    which basis it is on.
    - lab_sea: 5.5556·10⁻⁴ m/s on the target cell
      (`rA` = 3.112287·10¹⁰ m², `drF(1)` = 10 m,
      `deltaTFreeSurf` = 3600 s), i.e. 1.729·10⁷ m³/s or 82 Amazons.
      Reference and live agree exactly, for all time: lab_sea is a **linear**
      free surface (`nonlinFreeSurf` = 0, `select_rStar` = 0, as its own run
      reports), so nothing updates `hFacC` after initialisation.
    - cs32 (`drF(1)` = 50 m, `deltaTFreeSurf` = 86400 s) is an r\* grid
      (`nonlinFreeSurf` = 4, `select_rStar` = 2), so it needs two figures.
      **Reference basis:** 1.1574·10⁻⁴ m/s at every one of the 1189 target
      cells of `input.rnof_sp_icedyn`, `h0FacC` being 1.0 at all of them in
      the init dump (its `hFacMinDr` of 20 m would allow a thinner surface
      cell but no target has one); in m³/s, 1.62·10⁶ (7.7 Amazons) on the
      smallest target cell, `rA` = 1.4019·10¹⁰ m², and 1.03·10⁷ (49 Amazons)
      on the median, `rA` = 8.8743·10¹⁰ m².
      **Live basis, which is what is actually enforced**, and which applies
      from `nIter0` because `INITIALISE_VARIA` updates r\* before the first
      step (`initialise_varia.F:302,307`): `rStarFacC` over those targets
      spans **0.8787 to 0.99956**, the thickness 43.94 to 49.98 m and the
      enforced limit **1.0171·10⁻⁴ to 1.1569·10⁻⁴ m/s**. **309 of the 1189
      targets (26%)** sit more than 1% below the reference figure and **18
      (1.5%)** more than 10% below. Measured from the committed run's own
      `Depth.data` and `Eta.0000036010.data` with `CALC_R_STAR`'s own formula
      (`calc_r_star.F:103-105`), agreeing with review B's independent
      measurement and with review A's executed cs32 refusal, which printed
      `top-layer thickness 4.69852227E+01 m` and `limit 1.08762090E-04`.
    - a 2 km cell (`rA` = 4·10⁶ m², `drF(1)` = 10 m,
      `deltaTFreeSurf` = 1200 s): 1.6667·10⁻³ m/s, i.e. 6.67·10³ m³/s or
      0.032 Amazons.
  - **A physically correct large river, for comparison.** The Amazon's
    2.1·10⁵ m³/s is `f` = 2.43·10⁻³ on the lab_sea cell (82 times under the
    bound) and `f` = 4.09·10⁻³ on the median cs32 cell (49 times under; 7.7
    times under on the smallest cs32 target cell), but `f` = 6.3
    in **one** 2 km cell at `deltaTFreeSurf` = 1200 s — 31 times **over**.
    That refusal is correct and not a false positive: 6.3 top-layer volumes in
    one step is past `hFacSup` within the first step and is not a
    configuration the model can integrate. What it says is that a 2 km grid
    must spread the Amazon over at least 32 cells, which its ~200 km mouth is
    (about 100; review A's note, recorded: that is defensible for the full
    estuary but thin on the narrowest reading, a ~50 km north channel being
    only ~25 cells, below the 32 needed), and spreading a source over its real
    cells is what `target_fraction` exists for.
    Every committed sparse oracle is far below:
    the largest per-cell `f` over every record of every one of them is
    6.72·10⁻⁴, on cs32 — a margin of 297 — but **that pair is on the
    reference basis**. On the live thickness the same cs32 cell (5903) is
    `f` = 7.16·10⁻⁴ and the margin **279.5** (measured here, and the figure
    review A measured at the decisive cell at `nIter0`). The lab_sea files
    reach 3.42·10⁻⁴, a margin of 585, on both bases at once, that grid being a
    linear free surface.
  - **Every step, not only `nIter0`.** The target table is static, so a
    collapse of targets is already visible at `nIter0`; the flux series is
    not, so a file whose record 1 is innocent and whose record 500 is not
    would pass a check made once — the same reason `RNF_srcFluxMax` is tested
    on every record. Cost: a second pass over the same tile interior — one
    compare per cell, with the thickness lookup and the two multiplies only
    on the cells that carry runoff, the assignment loop being left a plain
    vectorisable copy — plus one `GLOBAL_SUM_INT`, which is what lets a
    refusal seen on one tile stop every process (`ALL_PROC_DIE` hangs unless
    all of them reach it; the same idiom as the one-tile refusals of
    `RNF_INIT_FIXED`) and is the only part that does not scale down with the
    tile. Measured on
    `lab_sea/input.rnof_sp_const`, 48 steps, serial: the `EXF_GETFORCING`
    timer section that contains the routine is 4.52·10⁻² s on the RUNOFF-030
    build and 4.56–4.80·10⁻² s over four samples of the RUNOFF-040 build,
    while `MAIN LOOP` is 3.999 s and 3.962–4.047 s — the section is 1.1% of
    `MAIN LOOP` and the added cost is inside the run-to-run scatter, with an
    upper bound of ≈ 60 µs per step on this grid.
  - **What it does not cover.** It is per cell and per *step*, so it refuses
    the absurd and does not certify the plausible: a flux just under the bound,
    sustained, still adds 0.2 of the surface layer every step. It sees the
    sparse field only — under `ALLOW_CTRL` with `ALLOW_GENTIM2D_CONTROL`,
    `xx_runoff` is added to the exf `runoff` array at
    `pkg/exf/exf_getffields.F:531-534`, **after** the `RNF_EXF_RUNOFF` call at
    `:456`, so neither package bound sees the controlled field.
    `EXF_CHECK_RANGE` *does* run after that addition
    (`exf_getforcing.F:199` then `:348`), but of its tests on the runoff
    array the upper bound is skipped with `useRNF` and the `sflux` one adds
    the runoff back. That leaves the negative test — the **sign**, at
    `nIter0` — and, only where `ALLOW_RUNOFTEMP` is compiled (cs32 defines
    it, lab_sea does not), a 36 m/s ceiling that the runoff-**temperature**
    test reads from the `runoff` array where it means `runoftemp`: an
    upstream misnaming, not conditioned on `useRNF`, and 6.5·10⁴ times above
    `RNF_cellVolMax` on the lab_sea cell, so it constrains nothing in
    practice. Nothing therefore bounds the magnitude of `xx_runoff`; that is
    a `pkg/ctrl` question, deliberately not in this issue's scope.
    It bounds magnitude only, not the temperature, salinity or tracer
    concentrations the water carries, and not the sign. It cannot tell one
    wrong source from N collapsed ones; it names the **cell**, which is what
    locates a collapsed target. It is blind in proportion to
    `drF(ks)·hFacC/deltaTFreeSurf`, so a collapse onto a thick top layer with
    a short step gets further. `RNF.h` carries the same list beside the
    constant.
  - **The thickness is the live one, in every regime** — a strength, not a
    caveat. `_hFacC` resolves to `hFacC`
    (`model/inc/HFACC_MACROS.h:37-39`, the macro also adapting to the
    reduced-memory `HFACC_*` options), and the surface-level `hFacC` the
    guard divides by is **maintained at run time in every regime**: by
    `UPDATE_R_STAR` when `select_rStar` > 0 (`update_r_star.F:55` and `:90`,
    `hFacC = h0FacC·rStarFacC`) and by `UPDATE_SURF_DR` when
    `select_rStar` = 0 (`update_surf_dr.F:56` and `:92`,
    `hFacC = hFac_surfC` / `hFac_surfNm1C`) — the two being the two arms of
    one `IF` in `model/src/forward_step.F` (`:832`, installs at `:839` and
    `:852`). That is deliberately a claim about the **surface level in the
    regimes that apply**, not a claim that nothing else writes the array:
    `UPDATE_SIGMA`, `UPDATE_MASKS_ETC` and `pkg/shelfice`'s remesh also
    assign `hFacC`, 11 assignment statements over 5 run-time routines as
    measured here. An earlier version of this item said
    `update_r_star.F:55-57` was the *only* run-time writer, which is false.

    What the guard reads is therefore not quite the current state: it is the
    thickness installed by the **previous step's end-of-step update**, i.e.
    the state at the end of step n−1, and with `doResetHFactors` the
    begin-of-step install of the `Nm1` fields puts it a further step back.
    Either way it lags by at least one step and is never current.
    - **The limit is not clipped under r\***: `calc_r_star.F:185-198` only
      *counts*
      cells outside `[hFacInf, hFacSup]`, so the limit drifts with the state
      and **one file can pass at `nIter0` and be refused later**. That
      mid-run abort is deliberate: an init-only check would be unsound in the
      numerator (the flux series is not static) *and* in the denominator (the
      thickness is not either), and bounding by `h0FacC·hFacInf` instead
      would be 5× stricter than the physics above and would refuse
      legitimate configurations at init.
    - **The two nonlinear regimes differ, and not in the direction an earlier
      version of this item claimed.** It said the `select_rStar` = 0 regime
      uses the reference thickness and *under*-states the departure, on the
      strength of `CALC_SURF_DR` writing only `hFac_surfC`. That is wrong —
      `UPDATE_SURF_DR` installs it into `hFacC` immediately afterwards — and
      acting on it would invite multiplying in a stretch factor that `hFacC`
      already contains, i.e. double-counting. The real difference is that
      under `select_rStar` = 0 the live thickness has a thin-side **floor**
      (`calc_surf_dr.F:105-108` has its `STOP` commented out and `:109-116`
      clamps `rSurftmp` to `Rmin_surf`), whereas under r\* nothing clamps. So
      the drift above is **bounded below in the surf_dr regime and unbounded
      in the r\* one**. No experiment here runs `nonlinFreeSurf` > 0 with
      `select_rStar` = 0, so that regime is unmeasured in this project.
    - Under a linear free surface nothing updates `hFacC` at run time at all
      (`update_surf_dr.F:125` resets it to `h0FacC`) and live
      equals reference for the whole run. That is lab_sea, and it is the
      premise the 0.99-of-the-bound control case relies on.
  - **Open points, recorded rather than closed** (review A and review B,
    correction round 2):
    - The NaN arm is correct but **unreachable on a supported input**:
      `RNF_NC_READ_FLUX` refuses a non-finite flux first and `rA` > 0, so
      nothing can deliver a NaN to the comparison. It is defence in depth
      whose validity rests on the optfile — `-ffinite-math-only` would
      silently void it *and* the pre-existing `rnf_init_fixed.F:728-737`
      tests of the same shape. The build measured here is `-O0` with no
      fast-math.
    - **Granularity:** neither enrolled case separates `RNF_cellVolMax` from
      any value in `(0.99·limit, limit]`, so a mutant that tightened the
      bound by under 1% would pass both. The tenfold-weakening mutant is
      what the cases do catch.
    - The `GLOBAL_SUM_INT` is now unconditional for every `useRNF` run,
      including one with no target on any tile, and is unmeasured beyond 2
      processes.
    - `RNF_tgtK` is fixed at init while the guard re-evaluates `kSurfC` each
      step; the two could diverge under `pkg/shelfice` remeshing. Not
      reachable today, since a shelfice target is refused at init — and
      `pkg/shelfice/shelfice_remesh_c_mask.F:226-227` is itself a run-time
      writer of `hFacC`, which is the mechanism that would make them diverge.
    - **`doResetHFactors` is not uniformly off in this project**, which is
      worth recording because the correction-round-3 analysis assumed it was.
      It defaults to `.FALSE.` (`set_defaults.F:185`) and both experiments
      that exercise `pkg/rnf` report `F` (`lab_sea/input` and
      `cs32/input.rnof_sp_icedyn`, read from their own runs) — but
      `global_ocean.cs32x15/input.seaice/data:31` sets it `.TRUE.`, and that
      run reports `T` with `nonlinFreeSurf` = 4 and `select_rStar` = 2. It is
      in the focused suite as a no-change experiment, so it runs with `useRNF`
      false and the guard never executes there. The begin-of-step reset block
      (`forward_step.F:465-486`) is therefore reachable in this project's test
      set, just never in a run that uses the package.
  - **Measured, both directions** (`tests/rnf/refusal_check.py`):
    `cell_above_vol_max` is the witness above and is refused, naming the cell
    `(i,j,bi,bj) = (3,3,2,1)` with `XC,YC` = 305°E, 51°N, `value`
    1.28522836·10⁻³, `limit` 5.55555556·10⁻⁴ m/s, with a `forbid` list that
    excludes the per-source bound and every init check the collapse walks
    past; it **fails** on a mutant with `RNF_cellVolMax` ten times too large,
    where the run ends normally again. `cell_at_vol_max`, the same collapse at
    0.99 of the bound, must and does end normally; it applies 0.99 of the
    5.5556·10⁻⁴ m/s allowed on that cell where `flux_at_source_max` applies
    3.21·10⁻⁴ m/s, i.e. 0.578 of it, so it sits **1.7** times nearer the
    bound — while the witness is 2.31 times *over* it and a factor of 4 above
    `flux_at_source_max`.
    **The 0.99 margin, and `cell_above_vol_max`'s asserted
    `top-layer thickness 1.00000000E+01 m`, are safe only because lab_sea is
    a linear free surface**, so `hFacC` is never updated at run time and the
    live thickness is the reference one for the whole run. On an r\* grid the
    same control would not be sound: 26% of cs32's target cells have
    `rStarFacC` below 0.99 (measured), so a 0.99-of-the-reference-limit
    control placed there would be **refused**. Any future per-cell control on
    an r\* grid has to be sized from the live thickness, not the reference.
    What `cell_at_vol_max` does **not** do is pin the `.LE.` against
    a `.LT.`, the way `ptracer_name_max` pins its length test: a control
    exactly at the bound would have to land on the last bit of a product of
    three reals and would measure the compiler's rounding, and the direction
    carries no promise here — `RNF_cellVolMax` is a round safety share, not a
    value a file may sit on, which is what `RNF_srcFluxMax` is.

  **How the second relaxation came to be in scope, kept because the reasoning
  is the useful part.** Round 0 implemented only the runoff skip, as the issue
  recommended, and then measured that it achieves nothing on its own: the
  `sflux` bound refused the same cell, so a point-source user would still have
  had to set `useExfCheckRange=.FALSE.`, which is the outcome the issue exists
  to prevent. Round 0 refused to relax a second field's check unasked and
  escalated instead; the coordinator verified the three source sites
  independently and widened the scope. Closing on the half change would have
  shipped something that does not work.

  **One `STOP` per process, now measured rather than inferred.**
  `EXF_CHECK_RANGE` calls `STOP` without `ALL_PROC_DIE`, so a refusal that
  only one tile can see would leave the other processes waiting and could not
  be enrolled (`judge` requires one `STOP` line per process). Round 0 recorded
  that as a permanent limit on any case asserting an `EXF_CHECK_RANGE` stop.
  Correction round 1 removes the limit for the case that matters, in two ways:
  `flux_at_source_max` now ends **normally**, so it asserts no stop at all;
  and `sflux_out_of_range` is built so that every process has out-of-range
  cells of its own (a uniform `precipconst`), so each prints its own `STOP`
  line. Both pass on 1 and on 2 processes. The general limit still holds for
  any hypothetical case whose breach is confined to one tile.

  **What the two tendency instruments do and do not measure.** The enrolled
  case above is what carries the relaxation; the instruments the issue
  expected to carry it do **not**: `tests/rnf/tendency_term_check.py`
  presents *zero* runoff to `EXF_CHECK_RANGE`, because the check is called
  only at `nIter0` (or at every step with `exf_debugLev` ≥ `debLevC`), and
  under `RNF_holdRecord` the case's first record is dry by construction — the
  10⁶ m³/s arrives at the second step, when the check is no longer called.
  Measured on a retained `L_set` run: `nIter0 = 0`, `exf_debugLev = 2`, the
  `RNF_FIELDS_LOAD` trace at `it= 0` selects `rec0 = 1` with `fac = 1.0`
  (the dry record), and the log holds 0 occurrences of `EXF WARNING`. So the
  override that case used to carry was never needed for the runoff bound
  either, and removing it is correct but measures nothing about the skip.
  `tests/rnf/exf_heat_check.py` likewise applies 4.0·10⁻⁷ to 7.6·10⁻⁷ m/s,
  under the bound on both paths, so its override was also unnecessary; what
  it does now measure is that the **dense** path is still held to both exf
  bounds in full, since it runs with `useRNF` false. Both are re-measured
  unchanged with the check at its default: 8 of 8 cases over 10 of 10
  decision-3 rows, and 7 cells at 3.559·10⁻¹⁶ with the control at
  3.446·10⁻².

  **Why the bound is enforced at the record read and not in `RNF_CHECK`.**
  `RNF_CHECK` runs from `PACKAGES_CHECK`, before `RNF_INIT_VARIA` reads the
  first record, so no flux value exists when it is called. Checking at the read
  also covers a file whose *later* records are the bad ones, which an
  init-time check could not. The read is the only place where all three
  conditions hold at once: the file is open (so `RNF_NC_SOURCE_ID` can name the
  source), every process examines every value of the record (so a refusal is
  reached by all processes and `ALL_PROC_DIE` is sound, with no global
  reduction and no per-step cost), and the value is still the file's own.
- The model volume grows by `flux · rhoConstFresh / rhoConst` (see "Volume"
  above). The invariant "applied volume equals source flux" holds for the
  `runoff` field in m/s times `rA`.

**Option B, for a build without exf.** Place the hook in `DO_OCEANIC_PHYS` after
`SEAICE_MODEL` and before `EXTERNAL_FORCING_SURF`
(`model/src/do_oceanic_phys.F:453`, `579`) and subtract `m` from `EmPmR`. No
exf compensation exists on that route. When `temp_EvPrRn` is set, the package
temperature term of decision 3 becomes
`[(mT) + (m − m_T)·θ − m·temp_EvPrRn]·μ·D`, so that sources without a
temperature still enter at `θ`.

**Consequence for issues.** RUNOFF-004 implements `RNF_EXF_RUNOFF` and the
refusals; RUNOFF-040 adds the per-cell magnitude refusal to that same routine. RUNOFF-014 tests branches N, L and U with unchanged downstream code.
RUNOFF-016 must use the `rhoConstFresh/rhoConst` factor when it compares model
volume with source flux. `tests/rnf/budget_check.py` does not need it, because it
compares the **applied volume flux field** (`RNF_vflx`, dumped as `EXFroff`,
m/s) with the source flux rather than the model's volume, and that comparison is
in volume units on both sides: `Σ_c RNF_vflx(c)·rA(c) = Σ_s flux_s`, measured at
0.0 relative. The factor does enter its three property closures, as a single
`rhoConstFresh` (the mass flux the properties are weighted by); `rhoConst`
enters only through `mass2rUnit`, which it reads from the run's parameter dump.
A budget against the model's **volume** -- i.e. against the free surface -- is
still unwritten and is where this factor would apply. RUNOFF-017 gains the refusals above, the scale-factor
one included. RUNOFF-026 states that exf input scaling is not applied. RUNOFF-024
tests that both ice packages receive sparse runoff through the exf array.
RUNOFF-011 must give every testbed an exf build: `isomip` and
`global_ocean.90x40x15` do not compile exf
(`verification/isomip/code/packages.conf`,
`verification/global_ocean.90x40x15/code/packages.conf`) and need it added in a
test variant. RUNOFF-026 documents `useExfCheckRange`: that **two** of its tests are
conditioned on `useRNF` — the runoff upper bound skipped, and the `sflux` bound
applied to `sflux + runoff` so an out-of-range `evap - precip` is still refused
— that `RNF_srcFluxMax` and `RNF_cellVolMax` apply instead, and that the
negative-runoff test and every range check of every *other* field are
unaffected. This candidate's own `doc/phys_pkgs/exf.rst` and
`pkg/rnf/README.md` already state all of that, so RUNOFF-026 inherits a
complete description rather than half of one; both gained the per-cell bound
with RUNOFF-040, `exf.rst` without naming the constant, since that page
documents exf and not the internals of `pkg/rnf`.

## Decision 3: temperature and salinity contributions

**Alternatives.**

- **Fill exf `runoftemp`**, as the earlier contract assumed. `EXF_MAPFIELDS`
  applies that field only when `runoftempfile` is not blank
  (`pkg/exf/exf_mapfields.F:200`), and a non-blank name makes `EXF_SET_FLD` read
  that file (`pkg/exf/exf_getffields.F:437-450`, `pkg/exf/exf_set_fld.F:117-121`).
  The package cannot drive `runoftemp` without editing `exf_mapfields.F`. It
  also has no counterpart for salinity or tracers.
- **Add to `surfaceForcingT/S`** in a hook at the end of `EXTERNAL_FORCING_SURF`,
  as `SHELFICE_FORCING_SURF` does
  (`model/src/external_forcing_surf.F:394-400`). KPP would see the terms, but
  the hook serves the surface level only.
- **Tendency terms** in `APPLY_FORCING_T/S`, the pattern of
  `ICEFRONT_TENDENCY_APPLY_T/S` (`model/src/apply_forcing.F:711-716`, `943-948`;
  `pkg/icefront/icefront_tendency_apply.F:44-54`) and of `SHELFICE_FORCING_T/S`
  (`model/src/apply_forcing.F:703-709`, `935-941`;
  `pkg/shelfice/shelfice_forcing.F:73-100`).

**Choice.** Tendency terms, as the owner directed. The same routine later serves
interior levels.

**What is added.** At a target cell, at the level given by decision 5:

$$
g_T \mathrel{+}= \left[(mT) - m_T\,T_{\mathrm{ref}}\right]\mu D ,
\qquad
g_S \mathrel{+}= \left[(mS) - m\,S_{\mathrm{ref}}\right]\mu D .
$$

`T_ref` and `S_ref` are the temperature and salinity that the model's own
freshwater formulation has already given to this water. Each term is the mass
flux times the difference between the source property and that reference. The
form is the one the model uses for `addMass`
(`model/src/apply_forcing.F:504-531`, `874-901`).

| Quantity | Value | Why |
|---|---|---|
| `T_ref` | `θ(i,j,k)` | `temp_EvPrRn` unset: the model adds nothing, so the water arrives at `θ` (`config_summary.F:407-409`). `temp_EvPrRn` set with `ALLOW_ATM_TEMP`: exf cancels the model term for runoff (`exf_mapfields.F:175-185`), so it again arrives at `θ`. |
| `T_ref` | `temp_EvPrRn` | `temp_EvPrRn` set and `ALLOW_ATM_TEMP` undefined: the exf cancellation is not compiled (`exf_mapfields.F:132-198`), so the model term stands and the dense path also delivers runoff at `temp_EvPrRn`. |
| `S_ref` | `salt_EvPrRn` | `salt_EvPrRn` set (default 0, `set_defaults.F:265`): every branch gives the water this salinity. |
| `S_ref` | `S(i,j,k)` | `salt_EvPrRn` unset, branch N or L: the model adds nothing. |
| `S_ref` | `convertFW2Salt` | `salt_EvPrRn` unset, branch U. |

The package includes `EXF_OPTIONS.h` to see `ALLOW_ATM_TEMP`, as `pkg/seaice`
does (`pkg/seaice/seaice_growth.F:1-4`).

**Algebra for each formulation.** Runoff contributes `+m` to `PmEpR` and `−m` to
`EmPmR`. This assumes `exf_outscal_sflux = 1`, because exf multiplies `sflux` by
that factor (`pkg/exf/exf_mapfields.F:118`); `RNF_CHECK` refuses any other value
(decision 2). The "model" column is the runoff part of the term in the branch
table; "exf" is the cancellation; "package" is the term above; "total" is their
sum.

*Temperature, all sources carrying a temperature (`m_T = m`).*

| Case | Model | exf | Package | Total |
|---|---|---|---|---|
| N or L, `temp_EvPrRn` unset | 0 | 0 | `[(mT) − mθ]μ` | `[(mT) − mθ]μ` |
| N or L, set, `ALLOW_ATM_TEMP` | `m(temp_EvPrRn − θ)μ` | `m(θ − temp_EvPrRn)μ` | `[(mT) − mθ]μ` | `[(mT) − mθ]μ` |
| N or L, set, no `ALLOW_ATM_TEMP` | `m(temp_EvPrRn − θ)μ` | 0 | `[(mT) − m·temp_EvPrRn]μ` | `[(mT) − mθ]μ` |
| U, `temp_EvPrRn` unset | 0 | 0 | `[(mT) − mθ]μ` | `[(mT) − mθ]μ` |
| U, set, `ALLOW_ATM_TEMP` | `m(temp_EvPrRn − tRef)μ` | `m(θ − temp_EvPrRn)μ` | `[(mT) − mθ]μ` | `[(mT) − m·tRef]μ` |
| U, set, no `ALLOW_ATM_TEMP` | `m(temp_EvPrRn − tRef)μ` | 0 | `[(mT) − m·temp_EvPrRn]μ` | `[(mT) − m·tRef]μ` |

In branch U with `temp_EvPrRn` set, both builds end at `[(mT) − m·tRef]μ`,
because the model writes its term against `tRef(ks)`. With `ALLOW_ATM_TEMP`
this is the mix of `θ` and `tRef(ks)` that exf already has in that branch.

The exf column is part of `Qnet`; under sea ice it is scaled like the other
heat terms (see the comparison below), so the cancellation is complete only in
ice-free cells. With an ice fraction `a` and `temp_EvPrRn` set, the branch-N
total becomes `[(mT) − mθ]μ + a·m(temp_EvPrRn − θ)μ`. The second part is a
residual of the dense path, which has it too; the package does not remove it.

In branch N the cell also gains the volume `mμ` at temperature `θ`, so its heat
content changes by `mμθ + [(mT) − mθ]μ = (mT)μ`. Multiplied by `rhoConst·Cp·rA`
and summed over cells this is `Cp · rhoConstFresh · Σ_s flux_s·frac·T_s`: the heat
carried by the source mass flux, in W relative to 0 °C. In branch L the cell
volume is fixed and the total is the dilution tendency
`mμ(T_c − θ)` with `T_c = (mT)/m`.

*Missing temperature.* A source without a temperature is left out of `(mT)` and
`m_T`. It contributes nothing to the package term and enters at `T_ref`. That is
the ambient temperature `θ`, except in a build without `ALLOW_ATM_TEMP` that
sets `temp_EvPrRn`. With `T_ref = θ` the cell's effective inflow temperature is
`T_c = [(mT) + (m − m_T)θ]/m`, the flux-weighted mean of the contract with `θ`
standing in for a missing value. No division by `m` is
performed, so a cell with zero flux needs no special case.

*Salinity.*

| Case | Model | Package | Total |
|---|---|---|---|
| N or L, `salt_EvPrRn` set | `m(salt_EvPrRn − S)μ` | `[(mS) − m·salt_EvPrRn]μ` | `[(mS) − mS]μ` |
| N or L, unset | 0 | `[(mS) − mS]μ` | `[(mS) − mS]μ` |
| U, set | `m(salt_EvPrRn − convertFW2Salt)μ` | `[(mS) − m·salt_EvPrRn]μ` | `[(mS) − m·convertFW2Salt]μ` |
| U, unset | 0 | `[(mS) − m·convertFW2Salt]μ` | `[(mS) − m·convertFW2Salt]μ` |

In branch N the salt content changes by `mμS + [(mS) − mS]μ = (mS)μ`. Times
`rA` and summed over cells this is
`(rhoConstFresh/rhoConst) · Σ_s flux_s·frac·S_s` in model volume units, the salt
carried by the source mass flux. In branch U the total
is the virtual salt flux of water with salinity `S_c = (mS)/m` against the
uniform reference.

*S = 0.* Without a salinity variable `(mS) = 0`. With the default
`salt_EvPrRn = 0` the package term is identically zero, the routine returns
without touching `gS`, and the result equals the dense path. With a non-default
`salt_EvPrRn` the package still delivers salinity 0, which is what the contract
states, and then differs from the dense path, where runoff takes `salt_EvPrRn`.

**Time level.** The package fields must belong to the same step as the
freshwater flux that the model uses for its own temperature, salinity and
tracer terms. The rule below also applies to decision 4. `deltaT` is
`deltaTClock`, the step by which `myTime` advances.

| Case | Flux the model uses | Fields the package term uses |
|---|---|---|
| Branches L and U | `EmPmR` of the current step (`external_forcing_surf.F:296-349`) | at `myTime` |
| Branch N with `staggerTimeStep` | `PmEpR = −EmPmR` of the current step (`external_forcing_surf.F:158-166`) | at `myTime` |
| Branch N without `staggerTimeStep`, first step of a run that starts at iteration 0 (`myIter = nIter0 = 0`) | `PmEpR = 0` (`ini_nlfs_vars.F:59`; `integr_continuity.F:163-171`, called from `initialise_varia.F:334`) | none: the term is zero |
| Branch N without `staggerTimeStep`, first step after a restart (`myIter = nIter0 ≠ 0`) | `PmEpR` rebuilt from the pickup, which is the flux of the step before it (`integr_continuity.F:141-162`) | at `myTime − deltaT`, evaluated from the records |
| Branch N without `staggerTimeStep`, later steps | `PmEpR = −EmPmR` of the previous step (`integr_continuity.F:172-179`) | at `myTime − deltaT`, kept from the previous step |

- *Premise.* The branch-N rows without `staggerTimeStep` assume
  `exactConserv`: the model sets `PmEpR` only in the `exactConserv` branch of
  `INTEGR_CONTINUITY` (`model/src/integr_continuity.F:90`, `141-179`). A
  nonlinear free surface always has it, because the model stops otherwise
  (`model/src/config_check.F:725-732`).
- *Why.* With current-step fields in the last two rows, the heat budget of
  each step would be off by `(m_previous − m_current)μθ`. With a term at the
  cold-start step, one step of `[(mT) − m_T·θ]μ` would be added with no volume
  to carry it.
- *How.* `RNF_FIELDS_LOAD` copies the dense fields to a previous-step set
  before it loads the new ones. At the first step it sets that set to zero for
  a start at iteration 0, or evaluates it at `myTime − deltaT` for a restart. The fields
  depend on model time only, so a restart reproduces them without a pickup.
- *Time before the first record.* A start at iteration 0 never needs a time earlier than
  the start: the first lagged use, at the second step, is the start time
  itself. A restart in the fourth row needs `myTime − deltaT`. If a
  non-repeating series does not reach back that far, the run stops with an
  `RNF` message that names the time and the cause. `EXF_GetFFieldRec` would
  stop there anyway, with a message about the field start time only
  (`pkg/exf/exf_getffieldrec.F:121-129`, `233-259`). The alternative, taking
  the fields as zero at that time, was rejected: the rebuilt `PmEpR` may carry
  runoff that an earlier run segment applied from another file, and the
  package cannot know its temperature or salinity. The user's remedy is a file
  whose first record is at least one step earlier.

**Adams-Bashforth.** When tracer forcing is inside the Adams-Bashforth step
(`tracForcingOutAB ≠ 1`, `model/src/temp_integrate.F:367-372`), the package
term is extrapolated in time like the model's own forcing. A budget then closes
in the sum over time and not step by step.

**Comparison with exf `runoftemp`.** In an ice-free cell with every source
carrying a temperature, the package term `[(mT) − mθ]μD` equals the exf term
`rhoConstFresh·runoff·(runoftemp − θ)·μ·D` when `runoftemp = T_c`. The two paths
differ in five ways:

1. The exf term is part of `Qnet`. Under `pkg/seaice` built with
   `SEAICE_EXTERNAL_FLUXES`, as cs32 is
   (`verification/global_ocean.cs32x15/code/SEAICE_OPTIONS.h:25`), it is scaled
   by the open-water fraction (`pkg/seaice/seaice_growth.F:956-957`), and under
   `pkg/thsice` by `opFrac` (`pkg/thsice/thsice_step_fwd.F:273`). The package
   term is not scaled. `global_ocean.cs32x15/input.seaice` runs `pkg/seaice`
   (`verification/global_ocean.cs32x15/input.seaice/data.pkg`), so a sparse run
   with tendency-based temperature cannot be expected to match
   `results/output.seaice.txt` wherever a runoff cell holds ice. Whether such
   cells exist in the ten steps of that experiment was not measured.
2. The exf term is in `surfaceForcingT`, which KPP reads
   (`pkg/kpp/kpp_calc.F:419-421`, `pkg/kpp/kpp_transport_t.F:79`). The package
   term goes straight to `gT`, so KPP's surface buoyancy flux and non-local
   transport do not include it. The freshwater buoyancy of the volume itself
   still reaches KPP through `EmPmR`.
3. The diagnostics `TFLUX` and `SFLUX` are built from `surfaceForcingT/S` and
   `PmEpR` (`model/src/diags_oceanic_surf_flux.F:116-152`, `162-190`) and do not include
   the package terms. The package diagnostics of decision 8 report them.
4. The order of floating-point operations differs, so agreement is to round-off
   where it holds.
5. In a build without `ALLOW_ATM_TEMP` that sets `temp_EvPrRn`, the dense path
   totals `m(temp_EvPrRn + T_c − 2θ)μ`: the model term `m(temp_EvPrRn − θ)μ`
   stands, and the exf `runoftemp` term `m(T_c − θ)μ` assumes arrival at `θ`.
   The package total is `[(mT) − mθ]μ`, the heat of the source.

A cell-by-cell check that does not depend on ice: from `EXFroff`, `EXFroft` and
`THETA` of a dense run compute `Cp·rhoConstFresh·runoff·(runoftemp − θ)` and
compare it with the package heat diagnostic of the sparse run.

**Consequence for issues.** RUNOFF-013 implements these terms; its acceptance
against the cs32 `input.seaice` oracle has to be restricted to ice-free runoff
cells or replaced by the cell-by-cell check. RUNOFF-014 tests each table row.
RUNOFF-016 checks `(mT)` and `(mS)` against `rhoConstFresh·Σ flux·frac·X`.
It does **not** need the sum over time that this paragraph expected for forcing
inside Adams-Bashforth: `tests/rnf/budget_check.py` reads the `RNFgT`/`RNFgS`
diagnostics where `RNF_TENDENCY_APPLY_*` fills them, upstream of `gtForc` and of
the extrapolation, so the closure is per record and independent of the scheme.
Measured: two runs differing only in `tracForcingOutAB` (1 against 0) give
bitwise identical volume, salt and tracer residuals. Its heat sum runs over the
sources whose temperature is **present** in every record used, which is the
restriction the "Missing temperature" paragraph states; omitting it breaks the
closure by 1.9e-1. RUNOFF-022 adds a
restart in synchronous branch N across a record boundary. RUNOFF-024 records
the unscaled heat under ice and the inherited `temp_EvPrRn` residual.
RUNOFF-017 gains the refusal of a synchronous restart before the first record.
RUNOFF-008 is superseded for salinity. RUNOFF-006 keeps the volume oracle and
loses the `runoftemp` fill.

## Decision 4: passive tracers

**Where ptracers handles freshwater.** `PTRACERS_FORCING_SURF`, called from
`EXTERNAL_FORCING_SURF` (`model/src/external_forcing_surf.F:188-197`), builds
`surfaceForcingPTr` with the same three branches as temperature and salinity,
using `PTRACERS_EvPrRn(iTr)` (`pkg/ptracers/ptracers_forcing_surf.F:114-136`,
`144-189`). That parameter is described as the concentration "in Rain, Evap &
RunOff" (`pkg/ptracers/PTRACERS_PARAMS.h:17`) and defaults to unset
(`pkg/ptracers/ptracers_readparms.F:125`), which leaves the tracer undiluted.
`PTRACERS_APPLY_FORCING` adds `surfaceForcingPTr` at the surface level and calls
`GCHEM_ADD_TENDENCY` and `RBCS_ADD_TENDENCY`
(`pkg/ptracers/ptracers_apply_forcing.F:71-78`, `80-100`, `114-121`).

**Alternatives.** Add to `surfaceForcingPTr` in `PTRACERS_FORCING_SURF`; or add a
tendency in `PTRACERS_APPLY_FORCING`.

**Choice.** `CALL RNF_TENDENCY_APPLY_PTR( gPtracer, iMin, iMax, jMin, jMax, k, bi, bj, iTracer, … )` in
`PTRACERS_APPLY_FORCING`, beside the `GCHEM` call, under `ALLOW_RNF` and
`useRNF`. For a tracer `n` that has a file variable:

$$
g_{C_n} \mathrel{+}= \left[(mC_n) - m\,C_{\mathrm{ref},n}\right]\mu D ,
$$

with `C_ref,n = PTRACERS_EvPrRn(n)` if set; otherwise `pTracer(i,j,k,n)` in
branches N and L and `PTRACERS_ref(ks,n)` in branch U
(`pkg/ptracers/ptracers_forcing_surf.F:175-183`). A tracer without a file
variable gets no term and behaves as in the dense path. The time-level rule of
decision 3 applies unchanged, because `PTRACERS_FORCING_SURF` uses the same
`PmEpR` in branch N (`pkg/ptracers/ptracers_forcing_surf.F:123-134`).

**Reason.** It matches decision 3, works at any level, and keeps the package out
of the `surfaceForcingPTr` logic that KPP shares
(`pkg/kpp/kpp_transport_ptr.F:89`).

**Name matching.** In `RNF_INIT_FIXED`, each variable `runoff_ptracer_<NAME>` is
compared with `PTRACERS_names(iTr)` for `iTr = 1 … PTRACERS_numInUse`
(`pkg/ptracers/PTRACERS_PARAMS.h:60`, `128`), exactly and with trailing blanks
removed. No match, two matches, or tracer variables in the file while ptracers
is not in use, stop the run with the variable name. Setting
`RNF_usePtracers=.FALSE.` ignores the variables.

**Units.** The schema defines a concentration per unit volume. The term carries
it with the mass flux, so the tracer input in model units is
`(rhoConstFresh/rhoConst) · Σ_s flux_s·frac·C_s`, consistent with the volume the
model adds.

**Double counting.** `pkg/bling` multiplies `runoff` by a constant river
phosphate concentration (`pkg/bling/bling_main.F:225-229`). With option A it
applies to sparse runoff as well. A file that also supplies that tracer would
count it twice; `RNF_CHECK` warns when both are active.

**Consequence for issues.** RUNOFF-008 is replaced by this decision and can be
closed into RUNOFF-013 or a tracer issue of its own. The tracer term has **two**
oracles (RUNOFF-008):

- `tests/rnf/tendency_term_check.py` has an analytic single-cell row for each
  of the four linear-free-surface reference arms (`PTRACERS_EvPrRn` set or
  unset, in branch L or U): the `RNFtr01` diagnostic against
  `[(mC) − m·C_ref]·mass2rUnit·D` (measured 0.00e+00), and the two-run
  difference of the tracer's own state change `Tp_gTr01` against package plus
  model term (at most 1.68e-15). On lab_sea the model's term is
  `LONGSTEP_FORCING_SURF`'s, not `PTRACERS_FORCING_SURF`'s, because
  pkg/longstep takes the ptracer step over; the arms are the same, with
  `EmPmR` replaced by its long-step average.
- `tests/rnf/budget_check.py` (RUNOFF-016) closes
  `Σ_c (mC_n)(c)·rA(c) = rhoConstFresh·Σ_s flux_s·C_{s,n}` at 1.962e-16
  relative on a non-degenerate series, per runoff tracer from `RNFtrNN` and per
  ptracer from `ForcTrNN`. The second is the one that sees the `RNF_trPtr`
  mapping, measured on a `PTRACERS_num = 2` lab_sea build with the file's
  variables in the opposite order to `PTRACERS_names`; a swap of the two
  fails it at 5.0e-01 and 3.3e-01. A ptracer the file does not feed is
  measured to receive exactly nothing.

Neither runs on cs32, which does not compile pkg/ptracers, nor in branch N
(RUNOFF-014). RUNOFF-017 gains the unmatched-name and ptracers-off refusals.
RUNOFF-029 covers tracer series in every time mode.

## Decision 5: target level and cavities

**Surface level.** `RNF_TENDENCY_APPLY_*` receives `k` from the caller and
applies a surface target when `k` equals the model's surface level for that
column, evaluated at call time with the rule of
`model/src/apply_forcing.F:466-474` and `617-636`:

- z coordinates without `useShelfIce`: `k = 1`;
- pressure coordinates: `k = Nr`, as exf uses for its surface index
  (`pkg/exf/exf_mapfields.F:89-90`);
- z coordinates with `useShelfIce`: `k = kSurfC(i,j,bi,bj)`
  (`model/inc/GRID.h:522-531`).

`target_level = 1` in schema 1.0 therefore means "the surface cell of the
column", which is level 1 only in the first case. Evaluating at call time keeps
the rule valid when ice-shelf remeshing reassigns `kSurfC` during a run
(`pkg/shelfice/shelfice_remesh_c_mask.F:98`, `156`).

**Land.** A target whose surface cell is dry (`kSurfC = Nr+1`,
`model/inc/GRID.h:526`, or `maskC = 0` at the surface level) is a fatal error
naming the source.

**Beyond an open boundary.** A target with `maskInC = 0` is a fatal error
naming the source, like a land target. `maskInC` is the interior mask, zero
beyond an open boundary (`model/inc/GRID.h:359`). `pkg/obcs` sets it
(`pkg/obcs/obcs_init_fixed.F:375-379`) before the package's init runs
(`model/src/packages_init_fixed.F:223`). With `useRealFreshWaterFlux` the model
multiplies `EmPmR` by this mask (`model/src/external_forcing_surf.F:149-156`),
so such a target would lose its volume and keep its tendency terms. The
alternative, accepting these targets and reporting a count, was rejected
because the volume invariant would fail without stopping the run. The refusal
applies in every freshwater formulation, so that one file behaves the same way
with and without `useRealFreshWaterFlux`. Whether the boundary row itself has
`maskInC = 0` was not read from `pkg/obcs` here and is left to the open-boundary
tests.

**Under an ice shelf.** The brief defines the surface as the top wet cell, also
under `pkg/shelfice`. The volume cannot follow that definition through the
surface flux: `SHELFICE_FORCING_SURF` sets `EmPmR` and the surface forcing to
zero wherever `kTopC ≠ 0` (`pkg/shelfice/shelfice_forcing_surf.F:57-69`), after
exf and before the solver. A target there would keep its tendency terms and
lose its volume without any message.

**Alternatives for those cells.**

- Refuse them.
- Route their volume through `addMass` at `k = kSurfC` (option C of decision 2).
  `addMass` is applied at any level and is not zeroed by `pkg/shelfice`.
- Re-add the package flux to `EmPmR` after the zeroing, as `pkg/shelfice` does
  with its own freshwater (`pkg/shelfice/shelfice_forcing_surf.F:101-112`).

**Choice.** `addMass` at `kSurfC`, built together with interior levels, because
schema 1.1 needs the same mechanism. Until then `RNF_INIT_FIXED` refuses a target
with `kTopC ≠ 0`, naming the source. For `addMass` cells the references of
decision 3 become `temp_addMass` and `salt_addMass` when set, the local value
otherwise (`model/src/apply_forcing.F:504-531`, `874-901`); both default to the
`EvPrRn` values (`model/src/ini_parms.F:1577-1580`).

**A shelf edge that moves during the run.** The init-time refusal is enough
only while `kTopC` stays fixed.

- `kTopC` is set in `SHELFICE_INIT_FIXED`
  (`pkg/shelfice/shelfice_init_fixed.F:121-138`), before the package's init.
- With `SHI_update_kTopC` it is set again after the pickup is read
  (`pkg/shelfice/shelfice_init_varia.F:118-131`) and at every step
  (`pkg/shelfice/shelfice_thermodynamics.F:239-256`, called at
  `model/src/do_oceanic_phys.F:523`). A target that was open at init can then
  come under the shelf, lose its volume and keep its tendency terms.
- The flag is true only when `ALLOW_SHELFICE_REMESHING` is compiled and
  `SHELFICEMassStepping` is set
  (`pkg/shelfice/shelfice_readparms.F:103-107`, `230`).
- Remeshing by itself moves the top level only in columns that are already
  under the shelf: both its split and its merge branch require `kTopC ≠ 0`
  (`pkg/shelfice/shelfice_remesh_c_mask.F:87-89`, `149`, `223-231`).

*Alternatives.* Refuse `useRNF` together with `SHI_update_kTopC`; or check
`kTopC` again at every step where the volume is applied.

*Choice.* `RNF_CHECK` refuses `useRNF` with `SHI_update_kTopC` until the
`addMass` path exists.

*Reason.* The per-step update of `kTopC` happens inside `DO_OCEANIC_PHYS`,
after the package has loaded its fields and filled exf `runoff` for that step
(`model/src/forward_step.F:540` precedes `657`). A check in the load routine
would see the `kTopC` of the previous step, so one step of volume would already
be lost when it fires. An exact check needs one more hook between
`do_oceanic_phys.F:523` and `579`. The refusal needs no hook and affects only
runs with an evolving shelf edge. The `addMass` path makes under-shelf targets
legal, and the refusal is lifted with it.

**Interior levels (schema 1.1).** Each per-tile target entry stores its level.
A value above 1 selects a fixed model level and the `addMass` path. The dense
fields then need a level dimension or a per-level sparse loop; that choice
belongs to the implementation issue.

**Consequence for issues.** RUNOFF-020: sources at the ice front in open water
work with the surface path; sources under the shelf need the `addMass` path and
are refused before it exists. RUNOFF-025 implements `addMass` for interior and
under-shelf targets and the schema 1.1 meaning of `target_level`, and lifts the
`SHI_update_kTopC` refusal. RUNOFF-020 also tests that refusal. RUNOFF-017
gains three refusals: a target under a shelf, a target with `maskInC = 0`, and
`useRNF` with `SHI_update_kTopC`. RUNOFF-019 tests a source in the first
interior cell and the refusal beyond the boundary, and establishes the mask
value on the boundary row. RUNOFF-011 should include the pressure-coordinate
case `global_ocean.cs32x15/input.in_p`. The schema text for `target_level`
("1-based model level `k`") now states the surface meaning.

## Decision 6: reading and decomposition

**Build guards.** genmake2 tests for NetCDF and passes `-DHAVE_NETCDF` to the
compiler (`tools/genmake2:1182-1220`, `2243-2244`). There is no `ALLOW_NETCDF`
macro in the packages. `pkg/profiles` and `pkg/obsfit` include `netcdf.inc`
without a guard (`pkg/profiles/profiles_init_fixed.F:26-28`,
`pkg/obsfit/obsfit_init_fixed.F:27-29`) and rely on genmake2 removing them from
the build when the test fails (`tools/genmake2:2534-2567`). If they are still
requested at run time, `PACKAGES_BOOT` resets their switch to false with a
warning (`model/src/packages_boot.F:192-223`).

**Alternatives.** Add `rnf` to that genmake2 list and to the `PACKAGES_BOOT`
reset; or guard the NetCDF code in the package itself.

**Choice.** All `NF_*` calls and the `netcdf.inc` include sit inside
`#ifdef HAVE_NETCDF` in `pkg/rnf`. Without NetCDF the package still compiles,
and `RNF_READPARMS` stops the run if `useRNF` is true. The stop is there, and
not in `RNF_CHECK`, because the static read in `RNF_INIT_FIXED` comes before
`PACKAGES_CHECK` (`model/src/initialise_fixed.F:211`, `267`).

**Reason.** Resetting the switch to false would drop all runoff with only a
warning. A fatal error is the required behavior for missing input. The choice
also leaves genmake2 untouched.

**Threads and processes.** NetCDF reads are done by the master thread inside
`_BEGIN_MASTER`/`_END_MASTER`, looping over all tiles of the process, followed
by `_BARRIER`, as `PROFILES_INIT_FIXED` does
(`pkg/profiles/profiles_init_fixed.F:146-151`). Every MPI process opens the file
read-only and reads the same data; each keeps only what its tiles need. This is
the phase-1 default recorded in RUNOFF-007.

**Static read (`RNF_INIT_FIXED`).**

1. Read and check the global attributes: schema major version, and
   `mitgcm_grid_nx`, `mitgcm_grid_ny` against the model's global layout.
2. Read `target_source`, `target_cell`, `target_fraction` (and `target_level`,
   `target_cell_area` when present) in chunks of `RNF_nBuf` entries.
3. Check the index ranges before any placement, and stop with the source id on
   a failure: `0 ≤ target_cell < xSize·ySize`, with `xSize` and `ySize` the
   global layout of step 1, and `0 ≤ target_source < n_source`. The model must
   do this itself. Fortran integer division truncates toward zero, so in step 4
   an index `g` in `(−sNx, 0)` gives `g/sNx = 0`, matches record 0 with
   `i = mod(g,sNx)+1 ≤ 0`, is counted in the fraction sum of step 6, and puts
   its flux outside the tile interior that `RNF_EXF_RUNOFF` copies. The schema
   rule for this range exists only in the Python checker. Every process reads
   the whole table, so every process stops on the same entry. A
   `target_source` out of range has no source to name: its message gives the
   value and the index of the entry in the table.
4. Place each target on a tile with the arithmetic `pkg/mdsio` uses to read a
   global file, as RUNOFF-004 requires
   (`pkg/mdsio/mdsio_read_field.F:399-430`; the write side is
   `pkg/mdsio/mdsio_write_field.F:437-480`). For tile `(bi,bj)`:
   - `tBx = myXGlobalLo − 1 + (bi−1)·sNx`, `tBy = myYGlobalLo − 1 + (bj−1)·sNy`,
     `iGjLoc = 0`, `jGjLoc = 1`, global width `xSize = Nx`;
   - with the exch2 I/O layout, `tBx = exch2_txGlobalo(tN) − 1`,
     `tBy = exch2_tyGlobalo(tN) − 1`, `xSize = exch2_global_Nx`, and the fold
     cases `iGjLoc`, `jGjLoc` of `mdsio_read_field.F:411-423`;
   - row `j` of the tile is global record
     `r(j) = (tBx + (j−1)·iGjLoc)/sNx + (tBy + (j−1)·jGjLoc)·(xSize/sNx)`,
     and cell `(i,j)` has the 0-based global index `r(j)·sNx + i − 1`.

   A target with index `g` belongs to the tile if `g/sNx` equals `r(j)` for
   some `j` in `1 … sNy`; then `i = mod(g, sNx) + 1`. The grid kind is never
   inferred from geometry; only these variables are used.
5. Store, per tile, the local source list and the target entries
   `(i, j, level, fraction, local source)`.
6. Sum each source's fractions over tiles and processes with
   `GLOBAL_SUM_VECTOR_RL` (`eesupp/src/global_sum_vector.F:165-196`), one chunk
   of sources at a time, and stop if a sum differs from 1 by more than 10⁻⁶. A
   target on a blank exch2 tile is owned by no tile and shows up here, when
   its fraction is more than that tolerance. So does a target whose index is
   in range but on a cell of the global layout that no facet uses: facets of
   unequal size laid side by side (`W2_mapIO = −1`) leave such cells. A land
   target is owned by its tile and is caught in step 7; an index off the grid
   is caught in step 3.
7. Check each owned target, and stop with the source id on a failure
   (decision 5): land; `maskInC = 0`, beyond an open boundary; `kTopC ≠ 0`,
   under an ice shelf; and, when `target_cell_area` is present, agreement with
   `rA` within 10⁻⁴.

**Consequence for issues.** RUNOFF-004 implements steps 1 to 7 in `pkg/rnf`.
RUNOFF-007 stays open for the scatter design. RUNOFF-017 gains the "NetCDF not
available", blank-file and index-range refusals. RUNOFF-021 and RUNOFF-023 test
step 4 on exch2 layouts.

## Decision 7: time handling

**What exf provides.** `EXF_SET_FLD` selects records with one of three routines
(`pkg/exf/exf_set_fld.F:133-170`), reads two dense records
(`pkg/exf/exf_set_fld.F:184-297`) and interpolates
`fld = fac·fld0 + (1 − fac)·fld1` (`pkg/exf/exf_set_fld.F:299-314`).

**Callable directly.**

| Routine | Use | Source |
|---|---|---|
| `EXF_GETFFIELD_START` | start time from start dates | call at `pkg/exf/exf_init_fixed.F:306-317` |
| `EXF_GetFFieldRec` | fixed period, with repeat cycle and yearly files: `fac, first, changed, count0, count1, year0, year1` | `pkg/exf/exf_getffieldrec.F:6-11` |
| `cal_GetMonthsRec` | twelve-month climatology (period −12) | call at `pkg/exf/exf_set_fld.F:137-140` |
| `EXF_GetMonthsRec` | monthly records (period −1) | call at `pkg/exf/exf_set_fld.F:148-152` |
| `exf_GetYearlyFieldName` | `_YYYY` file name | call at `pkg/exf/exf_set_fld.F:185-189` |

**Not reusable.** `EXF_SET_FLD` itself, which reads dense binary records
(`pkg/exf/exf_set_fld.F:230-231`), and `exf_SwapFFields`, which swaps tiled 2D
arrays.

**Choice.** `RNF_GETREC` wraps the routines above for `fixed` and `monthly`
sampling with linear interpolation and returns one set
`(count0, count1, year0, year1, fac, first, changed)`. Own code covers:

- the record read and swap of per-tile source vectors;
- hold-exact, which selects the record whose interval contains the model time.
  For monthly records this is the calendar month, which is not the same as the
  nearer of two mid-month times;
- `yearly` sampling (one record per calendar year), for which exf has no
  mode: refused by `RNF_TIME_SETUP` rather than approximated, since schema 1.0
  puts its `time` at the midpoint of the year and mapping that needs its own
  code (RUNOFF-005, with an enrolled refusal case);
- the `constant` case, read once in `RNF_INIT_VARIA`.

**One set of weights.** `RNF_FIELDS_LOAD` calls `RNF_GETREC` once per step and
uses the result for flux, temperature, salinity and every tracer. The mass-
weighted sums are formed from the interpolated flux and interpolated properties:
`m_s(t)` and `X_s(t)` are each interpolated, then multiplied.

**Timing settings.** Start time, period and repeat cycle come from the file's
time axis and attributes and are overridden by `data.rnf` (decision 10).
Converting a CF date needs `pkg/cal`; without `useCAL` the namelist values in
seconds are required.

**Consequence for issues.** RUNOFF-005 implemented this as `RNF_TIME_SETUP`
(the file's time axis and the `data.rnf` overrides, resolved into exf's
period, start time and repeat cycle), `RNF_GETREC` (which calls the exf
routine of each mode, and hold-exact) and `RNF_FILE_NAME` (the `_YYYY` name).
Yearly *sampling* is refused instead of mapped, as above; yearly
*files* of a fixed-period series work, through exf's own wrap. RUNOFF-029 follows from the single set of weights and tests it.
RUNOFF-022 relies on `first` being true at the first step of a run: with
`useCAL` it is set from the model start time (`pkg/exf/exf_getffieldrec.F:94`,
`101`), and without `pkg/cal` from `myIter = nIter0`
(`pkg/exf/exf_getffieldrec.F:211`, `228`).

## Decision 8: diagnostics, monitor, pickup

**Pickup.** None. The package has no prognostic state. Its record buffers and
dense fields are a function of model time, and both bracketing records are read
when `first` is true at the start of a run (`pkg/exf/exf_getffieldrec.F:94`,
`101` with `useCAL`; `211`, `228` without), as for exf fields, which have no
pickup either. The previous-step fields that synchronous branch N needs follow
the time-level rule of decision 3: they are zero at the first step of a cold
start, and at the first step of a restart they are evaluated from the records
at `myTime − deltaT`. Neither case reads a stored field. `addMass`, when used,
is written by the model's own pickup (`model/src/write_pickup.F:314`).

**Diagnostics** (registered with `DIAGNOSTICS_ADDTOLIST` as in
`pkg/exf/exf_diagnostics_init.F:204-216`, filled once per step). The fields
that depend only on the input are filled by `RNF_DIAGNOSTICS_FILL` at the end of
`RNF_FIELDS_LOAD`. `RNFheat`, `RNFsalt`, `RNFgT`, `RNFgS` and `RNFtrNN` depend
on the model state through the reference value, and `DO_OCEANIC_PHYS` can still
change that state after the load (`FREEZE_SURFACE`,
`model/src/do_oceanic_phys.F:552-558`). They are filled inside
`RNF_TENDENCY_APPLY_*`, where the term is computed, as `APPLY_FORCING_T` does
for one of its own terms (`model/src/apply_forcing.F:607-613`).

| Name | Units | Content |
|---|---|---|
| `RNFvflx ` | m/s | volume flux per area, `m / rhoConstFresh`; equals `EXFroff` before controls |
| `RNFmflx ` | kg/m²/s | mass flux `m` |
| `RNFheat ` | W/m² | `Cp·[(mT) − m_T·T_ref]`, the applied heat term |
| `RNFsalt ` | g/m²/s | `(mS) − m·S_ref`, the applied salt term |
| `RNFtemp ` | °C | `(mT)/m_T` where `m_T > 0` |
| `RNFsaln ` | g/kg | `(mS)/m` where `m > 0` |
| `RNFnsrc ` | 1 | number of sources feeding the cell |
| `RNFgT   `, `RNFgS   ` | °C/s, g/kg/s | tendencies at the target level (3D) |
| `RNFtrNN ` | tracer units·kg/m²/s | `(mC_n) − m·C_ref,n` for runoff tracer `NN`, i.e. the `NN`-th `runoff_ptracer_*` variable of the file, not ptracer `NN` |

**Monitor** (`RNF_MONITOR`, at `monitorFreq`, in the style of
`pkg/exf/exf_monitor.F:189-198`):

- `MON_WRITESTATS_RL` statistics of the volume-flux field;
- the global sums `Σ m·rA/rhoConstFresh` (m³/s), `Σ Cp·(mT)·rA` (W) and
  `Σ (mS)·rA` (g/s), which the budget checks compare with the file;
- the number of sources and target entries in use.

exf keeps writing its own `runoff` statistics only when `runofffile` is set
(`pkg/exf/exf_monitor.F:189-192`), so the package monitor is the only runoff
output in the monitor block.

**Consequence for issues.** RUNOFF-015 implements this list. RUNOFF-016 reads
the **diagnostics** of the applied terms (`RNFgT`, `RNFgS`, `RNFtrNN`, the three
RUNOFF-013 registered) and the exf `EXFroff`; it does **not** read the monitor
sums, which do not exist yet, and it did not need them. `RNFtrNN` is read by
`tests/rnf/budget_check.py` and, since RUNOFF-008, by
`tests/rnf/tendency_term_check.py` (`RNFtr01` against the analytic term), so
its fill is observed by both. Because it is numbered by runoff tracer and filled
from that runoff tracer's sums whichever ptracer it is added to, it cannot see
the runoff-tracer-to-ptracer mapping; `budget_check` reads the ptracers' own
`ForcTrNN` for that (RUNOFF-008). RUNOFF-022 needs no pickup file and tests the
restart of the record state.

## Decision 9: TAF and adjoint

**Patterns.**

- No dynamic allocation. Arrays live in common blocks with bounds from
  `RNF_SIZE.h`, as `pkg/profiles/PROFILES_SIZE.h:9-17` does.
- The sparse lists are used only in `RNF_FIELDS_LOAD`, which turns them into
  dense per-tile fields (`m`, `m_T`, `(mT)`, `(mS)`, `(mC_n)`). That routine
  depends on input data, not on the model state.
- The model state enters only in `RNF_TENDENCY_APPLY_*`, in dense `i,j` loops of
  the same shape as the `addMass` lines (`model/src/apply_forcing.F:508-517`).
  TAF needs no special treatment of indirect addressing there.
- Store directives for the dense fields follow exf, which stores `runoff` after
  reading it (`pkg/exf/exf_getforcing.F:243-245`). If the source flux becomes a
  control variable, the record buffers need level directives like
  `pkg/exf/exf_ad_check_lev1_dir.h:85-87`.
- `rnf_ad_diff.list` names `rnf_exf_runoff.f` and `rnf_tendency_apply.f`;
  `rnf_ad.flow` declares the I/O routines, as in `pkg/mypackage`.

**Array sizing: alternatives.** Compile-time maxima with runtime counts inside
them; or one global source vector on every process.

**Choice.** Compile-time maxima per tile, runtime counts, and chunked I/O:

| Parameter | Meaning |
|---|---|
| `RNF_nSrcTile` | maximum number of sources on one tile |
| `RNF_nTgtTile` | maximum number of target entries on one tile |
| `RNF_nBuf` | chunk length for NetCDF reads and for the fraction sum |
| `RNF_nTr` | maximum number of runoff tracers |
| `RNF_nFile` | number of files, 1 for now; arrays carry the dimension |

A count that exceeds its bound stops the run and prints the value needed.

**Reason.** Per-tile bounds keep memory proportional to what a tile owns, which
is the purpose of the sparse format. Chunked reads avoid any array of global
source length.

**Limit.** Adjoint behavior is untested. This decision only keeps the code in a
form TAF accepts.

**Consequence for issues.** RUNOFF-004 defines `RNF_SIZE.h` and the overflow
errors. RUNOFF-027 checks these patterns. RUNOFF-007 can replace the chunked
read without changing the per-tile arrays. RUNOFF-025 decides the level
dimension of the dense fields.

## Decision 10: namelist

File `data.rnf`, namelist `RNF_PARM01`, read by `RNF_READPARMS` and printed by
`RNF_SUMMARY`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `RNF_file` | character | `' '` | NetCDF file, or base name with `RNF_useYearlyFiles`. Blank with `useRNF` true is fatal. |
| `RNF_holdRecord` | logical | `.FALSE.` | false: linear interpolation as exf; true: hold each record over its interval |
| `RNF_startDate1`, `RNF_startDate2` | integer | 0 | start date override (`YYYYMMDD`, `HHMMSS`) |
| `RNF_startTime` | real | unset | start time override in seconds |
| `RNF_period` | real | unset | period override: 0 constant, > 0 seconds, −12 monthly climatology, −1 monthly |
| `RNF_repCycle` | real | unset | repeat cycle override in seconds |
| `RNF_useYearlyFiles` | logical | `.FALSE.` | append `_YYYY` to `RNF_file` by model year |
| `RNF_useTemp` | logical | `.TRUE.` | apply `runoff_temperature` if the file has it |
| `RNF_useSalt` | logical | `.TRUE.` | apply `runoff_salinity` if the file has it |
| `RNF_usePtracers` | logical | `.TRUE.` | apply `runoff_ptracer_*` if the file has them |
| `RNF_monFreq` | real | `monitorFreq` | monitor interval |
| `RNF_debugLev` | integer | `debugLevel` | message level |

An unset override means the value from the file is used. The fraction tolerance
(10⁻⁶) and the cell-area tolerance (10⁻⁴) are constants in `RNF.h`, because the
contract fixes them. The package is switched on by `useRNF` in `data.pkg`; there
is no second switch.

**Consequence for issues.** RUNOFF-012 creates `RNF_READPARMS` and `RNF_SUMMARY`.
RUNOFF-005 uses the timing overrides. RUNOFF-026 documents the table.
RUNOFF-017 covers the blank-file refusal.

## Implementation notes

What RUNOFF-004 built, where it differs from the decisions above. The routines
are listed in [the code map](code_map.md).

1. **The volume flux is kept in m/s as its own field (decision 2).**
   `RNF_FIELDS_LOAD` builds `RNF_vflx` = Σ (flux·frac)/rA and
   `RNF_mflx` = `rhoConstFresh`·`RNF_vflx`, and `RNF_EXF_RUNOFF` copies
   `RNF_vflx`. Computing `runoff = m / rhoConstFresh` would multiply and
   divide by `rhoConstFresh`, which does not give back the same number when
   `rhoConstFresh` is not a power of two (999.8 in `lab_sea`). Each target
   adds `(flux·frac)/rA` in real*8, the order of `sparse_to_dense` in the
   converter. For a cell fed by one target the result is within one unit in
   the last place of the dense value, because `(d·rA)/rA` is not always `d`.
2. **The checks of step 7 are made when an entry is placed (decision 6).**
   The master thread has the file open and the target in hand at that point,
   so the cell area needs no per-target storage. The errors are counted and
   reported after step 6 with those of the fraction sums. The index ranges of
   step 3 are tested entry by entry before each entry is placed, not in a
   pass of their own.
3. **More is checked in step 3 than the index ranges.** `target_level` must be
   1 (schema §12) and `target_fraction` must lie in [0, 1] (profile invariant
   "fractions are ≥ 0"; schema rule T04). A negative fraction can hide in a
   sum that is still 1.
4. **Errors that one tile sees stop every process (decisions 5, 6, 9).** A
   refused target and an array bound that is too small are counted on the
   process that owns the tile, the count is summed with `GLOBAL_SUM_INT`, and
   every process then stops. `ALL_PROC_DIE` ends MPI on the calling process
   only (`eesupp/src/all_proc_die.F:15-17`). The number of sources reported
   as needed is exact for a file sorted by source and an upper bound
   otherwise. A process prints at most `RNF_maxErrMsg` (20) messages per error
   counter; the checks of a table entry share one counter and the refused
   targets another.
5. **A missing flux stops the run where the record is read** (model contract,
   "Scale requirement"): not a number, above 1e30 in absolute value, or equal
   to `_FillValue` or `missing_value`. The two attributes are read by
   `RNF_NC_ATT_REAL`, for which only "no such attribute" means absent. One
   that exists and is not one number (text, or a list) stops the run. Treating
   it as absent would apply a flux equal to the marker as runoff: review B of
   RUNOFF-004 showed 9999 m³/s applied that way before this was corrected.
   The same routine reads `mitgcm_grid_nx` and `mitgcm_grid_ny`.
6. **The file is opened and closed by each routine that reads it**
   (`RNF_INIT_FIXED`, `RNF_NC_READ_FLUX`), so that `RNF_INIT_VARIA` can be
   called more than once. RUNOFF-005 kept that: a record read opens and
   closes the file it needs, which is also what lets a yearly set be read
   without holding several files open. The cost is one open per record
   change, not per step, because the two record buffers are tagged with
   what they hold.
7. **Source ids are read from the file when a message needs one**, so no
   array has the length of the source dimension and none stores ids per tile.
8. **Time handling** (RUNOFF-005): `RNF_TIME_SETUP` resolves the file's time
   axis and the `data.rnf` overrides into `RNF_recPeriod`, `RNF_recStart` and
   `RNF_recCycle`, and `RNF_GETREC` hands those to the pkg/exf routine of the
   mode. A `constant` file's time axis is not read at all, because its
   reference date (`0001-01-01`) precedes pkg/cal's own (`15821015`).
9. **Defaults of `RNF_SIZE.h` (decision 9):** `RNF_nSrcTile` 2000,
   `RNF_nTgtTile` 10000, `RNF_nBuf` 1000.
10. **The fraction sums are computed only when every table entry was
    accepted (decision 6, steps 3 and 6).** An entry that step 3 refuses is
    not placed, so its fraction is missing from the sum of its source and
    step 6 would report the same broken entry a second time, as a source
    that does not sum to 1. `RNF_INIT_FIXED` therefore skips step 6 when
    step 3 counted an error (`RNF_tableRead` in `RNF.h`) and says so in the
    log. A negative fraction hidden in a sum of exactly 1 is still caught,
    because step 3 tests the range of each fraction. The same holds for a
    wrong header: nothing is placed and the sums are not computed.
    *Why the gate cannot hide a fraction error:* it opens only when
    `nErrEnt = 0`, and `nErrEnt ≥ 1` is itself fatal — it raises `errCount`
    at `rnf_init_fixed.F:699`, and `errCount ≥ 1` stops every process at
    `rnf_init_fixed.F:808-813`. So the run never continues on a path where
    the sums were skipped: a skipped check is always accompanied by a stop
    for the entry that caused it.
11. **The time series of the file are found once, at init (decisions 3
    and 4).** `RNF_NC_SERIES`, called by `RNF_INIT_FIXED` with the file
    open, walks the variables and records which of `runoff_temperature`,
    `runoff_salinity` and `runoff_ptracer_*` the file has and this run
    uses (`RNF_hasTemp`, `RNF_hasSalt`, `RNF_nTrUse`, `RNF_trNam`,
    `RNF_trPtr` in `RNF.h`), matching each tracer name to
    `PTRACERS_names`. It raises the `RNF_INIT_FIXED` error count for a
    name that matches none, for one that matches more than one, for
    tracer variables in a run without pkg/ptracers, for a name longer
    than `RNF_idLen` or empty, and for more tracers than `RNF_nTr`;
    `RNF_useTemp`, `RNF_useSalt` and `RNF_usePtracers` of `data.rnf`
    make a series be treated as absent, with a line in the log per
    variable. `RNF_SUMMARY` reports all of it, so a run never looks as
    if it carried a property it did not. This replaces the warning-only
    walk of RUNOFF-004, which named this issue.
12. **One reader per series, one open per record (decisions 3, 4
    and 7).** `RNF_NC_READ_FLUX` keeps its name and its messages but now
    fills a whole record buffer — flux, temperature, salinity and every
    tracer — in one open of the file, and takes the buffer index instead
    of an array. Each series is read by `RNF_NC_READ_ONE`, which carries
    the per-series missing-value policy: a missing value is refused for
    every series except the temperature, where it is recorded in
    `RNF_bufTvld` and leaves that source out of `(mT)` and `m_T`. A
    missing value is also stored as 0, so that a fill value cannot
    propagate as a NaN through a sum that is multiplied by a zero flag.
13. **The dense property fields are accumulated beside the volume flux,
    in the same loop and the same order (decision 3).** `RNF_LOAD_AT`
    (the renamed body of `RNF_FIELDS_LOAD`) adds `w = flux·frac/rA` to
    `RNF_vflx` exactly as before — the statement is unchanged, because
    `tests/rnf/applied_field_check.py` compares that sum bitwise — and
    the property sums `m_T`, `(mT)`, `(mS)` and `(mC_n)` use a second
    expression of the same value. They are accumulated in volume-flux
    units and scaled by `rhoConstFresh` in one pass at the end, as
    `RNF_mflx` is. No division by the total flux is made anywhere: the
    tendency terms use the sums, so a cell with zero flux needs no
    special case.
14. **The time level is decided in one place (decision 3, "Time
    level").** The tendency routines read a second set of dense fields,
    `RNF_ap*`, and need not know which time level they hold.
    `RNF_FIELDS_LOAD` keeps that set at the current step, except in
    branch N without `staggerTimeStep` (`RNF_lagFlds`), where it holds
    the previous step: zero at the first step of a run from iteration 0,
    the previous call's fields at a later step, and, at the first step of
    a restart, fields evaluated from the records at `myTime − deltaTClock`
    by a second call of `RNF_LOAD_AT` that prints no record trace. Which
    level each set holds is tracked by iteration number and not by model
    time, because `myTime − deltaTClock` of one step need not be bitwise
    the `myTime` of the step before it. **No verification experiment runs
    that branch** (cs32 has `staggerTimeStep`, lab_sea a linear free
    surface), so the lagged path, including its refusal of a restart
    whose previous step precedes the first record, has no enrolled case
    (RUNOFF-017).
15. **Only the diagnostics of the applied terms are registered
    (decision 8).** RUNOFF-013's acceptance needs the package's own
    record of what it added, so `rnf_diagnostics_init.F` registers
    `RNFgT`, `RNFgS` and `RNFtrNN`, filled inside
    `RNF_TENDENCY_APPLY_T`, `_S` and `_PTR` at the level and with the
    reference each term used. The input-only fields, `RNFheat`,
    `RNFsalt` and the monitor are left to RUNOFF-015. Decision 8 lists
    `RNFheat` and `RNFsalt` as two-dimensional, which has to be settled
    with their fill: a 2-D diagnostic may be filled once per step and
    tile, while these terms are computed at one level per column and
    that level is `kSurfC(i,j)` under an ice shelf. The three registered
    here are three-dimensional, which is how decision 8 lists `RNFgT`
    and `RNFgS`, so the question does not arise for them.
16. **`RNF_nTr` is 5, not 1.** One runoff tracer was enough while none
    was read. Each one costs two record buffers of `RNF_nSrcTile` per
    tile and two dense per-tile fields, so the bound is not free; a file
    with more stops the run and the message prints the number it has.
17. **The exf cancellation does not depend on `exf_outscal_hflux`
    (decision 3).** `RNF_CHECK` refuses `exf_outscal_sflux ≠ 1` because
    exf multiplies the whole `sflux`, runoff included, by it when it
    builds `EmPmR` (decision 2). The heat side needs no such refusal:
    `EXF_MAPFIELDS` scales `Qnet` by `exf_outscal_hflux` first
    (`pkg/exf/exf_mapfields.F:100-114`) and adds the heat content of
    precipitation, runoff and evaporation to the result afterwards
    (`175-195`), so the runoff term that cancels the model's own
    `temp_EvPrRn` term is unscaled whatever that factor is. Read from
    the source, not measured.

## Points that differ from earlier project records

1. The profile and the model contract place the feature inside `pkg/exf` with
   parameters in `data.exf`. This design is a package that feeds exf, with
   parameters in `data.rnf`.
2. The contract says `runoftemp` is filled when temperature is present. That is
   not possible without editing `exf_mapfields.F` (decision 3).
3. The profile invariant "heat, salt and tracer input equals `Σ flux·X`" holds
   in mass terms, `rhoConstFresh·Σ flux·X`. In model volume units the factor
   `rhoConstFresh/rhoConst` appears (decisions 2 and 4).
4. Equivalence with exf `runoftemp` holds only in ice-free cells (decision 3).
5. A surface target under an ice shelf cannot receive its volume through the
   surface flux (decision 5).
6. The source lines named in the issue for the `ICEFRONT` and `SHELFICE` hooks
   are, in the live source, `apply_forcing.F:703-709`, `711-716`, `935-941` and
   `943-948`.

## Questions for the owner

None blocks the next issues. Each has a recommended answer above.

1. **exf as a prerequisite.** The package needs `useEXF`. Configurations without
   exf need exf added to their build, or the option-B path. Recommended: keep
   exf as a prerequisite.
2. **Runoff heat under sea ice.** The tendency term delivers the full heat under
   ice; exf `runoftemp` delivers the open-water share. Recommended: keep the
   full heat, and test equivalence in ice-free cells.
3. **Package name.** `rnf` is proposed; `discharge` is the alternative.
4. **Temperature oracle in KPP configurations.** `lab_sea` runs KPP
   (`verification/lab_sea/input/data.pkg:4`). A sparse run with tendency-based
   temperature cannot match a dense `runoftemp` run to round-off there, because
   KPP reads the dense term and not the package term (decision 3, difference
   2). Recommended: decide RUNOFF-031 before RUNOFF-013 is accepted in a KPP
   configuration, and until then test temperature in `lab_sea` with the
   cell-by-cell check and the budgets.

## Citations index

All paths under `MITgcm/`. Line numbers are those of branch `new_runoff` when
this document was written and should be re-resolved from live source.

| File | Lines | Fact |
|---|---|---|
| `model/src/forward_step.F` | 540, 657, 733, 904, 928, 1005 | step order |
| `model/src/load_fields_driver.F` | 109-127, 208-217, 229-251 | `addMass` reset; exf call; other loads |
| `model/src/do_oceanic_phys.F` | 402, 453, 523, 539, 552-558, 579, 956 | ice, shelf, surface freezing, surface forcing, KPP order |
| `model/src/external_forcing_surf.F` | 98-109, 149-156, 158-166, 188-197, 225-231, 261-288, 296-320, 322-349, 394-400 | balance; `maskInC` on `EmPmR`; `PmEpR`; ptracers; `Qnet`; branches N, L, U; shelfice |
| `model/src/apply_forcing.F` | 448-462, 466-474, 504-531, 607-613, 617-636, 703-709, 711-716, 874-901, 903-922, 935-941, 943-948 | old forcing; `kSurface`; `addMass`; diagnostics fill; surface forcing; hooks |
| `model/src/initialise_fixed.F` | 133, 211, 267 | readparms, init-fixed and check order |
| `model/src/initialise_varia.F`, `model/src/ini_nlfs_vars.F` | 334; 59 | `PmEpR = 0` at a start at iteration 0 |
| `model/src/temp_integrate.F` | 367-372 | forcing inside Adams-Bashforth |
| `model/src/packages_init_fixed.F` | 223 | `OBCS_INIT_FIXED` before the package slot |
| `pkg/obcs/obcs_init_fixed.F`, `model/inc/GRID.h` | 375-379; 359 | `maskInC` zero beyond an open boundary |
| `pkg/shelfice/shelfice_init_fixed.F`, `shelfice_init_varia.F`, `shelfice_thermodynamics.F`, `shelfice_readparms.F` | 121-138; 118-131; 239-256; 103-107, 230 | where `kTopC` is set and when it is updated |
| `verification/lab_sea/input/data.pkg` | 4 | `useKPP` |
| `model/src/external_forcing.F` | 569-574, 773-778 | legacy hooks |
| `model/src/solve_for_pressure.F` | 142-150 | `EmPmR` in `cg2d_b` |
| `model/src/integr_continuity.F` | 90, 92-93, 129-131, 141-162, 163-171, 172-187 | the `exactConserv` branch; `facEmP`; `addMass`; `PmEpR` at a restart, at a start at iteration 0 and at later steps; `dEtaHdt` |
| `model/src/calc_div_ghat.F` | 126-134 | `addMass` in `cg2d_b` |
| `model/src/set_defaults.F` | 264-265 | `EvPrRn` defaults |
| `model/src/ini_parms.F` | 648-651, 1570-1574, 1577-1580 | `convertFW2Salt`; `mass2rUnit`; `addMass` defaults |
| `model/src/config_summary.F` | 407-412, 424-426 | meaning of unset and −1 |
| `model/src/config_check.F` | 837-845, 846-855 | `selectAddFluid`: rigid-lid error; synchronous-step warning |
| `model/src/diags_oceanic_surf_flux.F` | 116-152, 162-190 | `TFLUX`, `SFLUX` |
| `model/src/write_pickup.F` | 314 | `addMass` in pickup |
| `model/src/thermodynamics.F` | 321, 332, 348 | integrate calls |
| `model/src/temp_integrate.F`, `salt_integrate.F` | 322; 320 | `APPLY_FORCING_T/S` calls |
| `model/src/packages_boot.F` | 46-98, 113-164, 192-223, 388-390 | registration; NetCDF reset |
| `model/src/packages_readparms.F`, `packages_init_fixed.F`, `packages_init_variables.F`, `packages_check.F` | 289-292; 491-498; 408-415; 372-377 | registration |
| `model/inc/PARAMS.h` | 1079, 1094-1108 | package switches |
| `model/inc/GRID.h` | 522-531 | `kSurfC` |
| `pkg/exf/exf_getforcing.F` | 199, 243-245, 304, 310-318, 377, 380, 383 | exf step |
| `pkg/exf/exf_getffields.F` | 422-450, 485-559, 522-524 | runoff reads; control block |
| `pkg/exf/exf_set_fld.F` | 117-121, 133-170, 184-297, 230-231, 299-314 | record machinery |
| `pkg/exf/exf_getffieldrec.F` | 6-11; 94, 101; 211, 228; 121-129, 233-259 | interface; `first` with `useCAL`; `first` without `pkg/cal`; stop before the first record |
| `pkg/exf/exf_mapfields.F` | 89-90, 116-121, 132-198, 139-140, 175-185, 199-211 | `EmPmR`; heat of runoff |
| `pkg/exf/exf_init_varia.F`, `exf_init_fld.F`, `exf_init_fixed.F` | 357-366; 90-92; 306-317 | runoff init; start time |
| `pkg/exf/exf_check.F` | 322-329 | runoff macro check |
| `pkg/exf/exf_check_range.F`, `exf_readparms.F` | 215-261, 280-285; 307, 717 | range stop (the runoff block, whose upper bound carries `.AND. .NOT.useRNF` since RUNOFF-030, and the stop that ends the routine); default of `useExfCheckRange`; default of `exf_outscal_sflux` |
| `pkg/exf/exf_diagnostics_fill.F`, `exf_diagnostics_init.F`, `exf_monitor.F` | 72-73; 204-216; 189-198 | output |
| `pkg/exf/EXF_FIELDS.h` | 273-278 | `runoff` under `ALLOW_RUNOFF` |
| `pkg/exf/exf_ad_check_lev1_dir.h` | 85-87 | adjoint stores |
| `pkg/seaice/seaice_growth.F` | 1-4, 738-742, 956-957, 2209, 2234, 2332-2339, 2381-2388, 2396-2402 | options include; `Qnet` scaling; `EmPmR` rebuild |
| `pkg/seaice/seaice_budget_ocean.F` | 107-109, 110-149 | exf `Qnet` as open-water flux; own flux otherwise |
| `verification/global_ocean.cs32x15/code/SEAICE_OPTIONS.h` | 25 | `SEAICE_EXTERNAL_FLUXES` defined |
| `pkg/thsice/thsice_map_exf.F`, `thsice_main.F`, `thsice_calc_thickn.F` | 71-72, 104-121; 157-162, 199-203; 1048-1049 | runoff taken from the exf array and passed under the ice |
| `pkg/thsice/thsice_step_fwd.F` | 273-275 | combination by ice fraction |
| `pkg/shelfice/shelfice_forcing_surf.F` | 57-69, 101-112 | zeroing; own freshwater |
| `pkg/shelfice/shelfice_forcing.F` | 73-100 | tendency pattern |
| `pkg/shelfice/shelfice_remesh_c_mask.F` | 87-89, 98, 149, 156, 223-231 | remeshing acts on under-shelf columns and reassigns `kSurfC` and `kTopC` there |
| `pkg/icefront/icefront_tendency_apply.F` | 44-54 | tendency pattern |
| `pkg/ptracers/ptracers_forcing_surf.F` | 114-136, 144-189 | tracer freshwater branches |
| `pkg/ptracers/ptracers_apply_forcing.F` | 71-78, 80-100, 114-121 | tendency hooks |
| `pkg/ptracers/ptracers_integrate.F`, `PTRACERS_PARAMS.h`, `ptracers_readparms.F` | 301; 17, 60, 128; 125 | call; names; default |
| `pkg/kpp/kpp_calc.F`, `kpp_transport_t.F`, `kpp_transport_ptr.F` | 419-421; 79; 89 | KPP inputs |
| `verification/isomip/code/packages.conf`, `verification/global_ocean.90x40x15/code/packages.conf` | whole file | exf not compiled in these experiments |
| `pkg/bling/bling_main.F` | 225-229 | river nutrients from `runoff` |
| `pkg/mdsio/mdsio_read_field.F`, `mdsio_write_field.F` | 399-430; 437-480 | tile placement |
| `pkg/profiles/profiles_init_fixed.F`, `PROFILES_SIZE.h` | 26-28, 146-151; 9-17 | NetCDF, master thread, sizes |
| `pkg/obsfit/obsfit_init_fixed.F` | 27-29 | NetCDF include |
| `eesupp/src/global_sum_vector.F` | 165-196 | vector sum |
| `tools/genmake2` | 1182-1220, 2243-2244, 2409, 2534-2567, 2723, 2741-2748 | NetCDF test; package macros |
| `pkg/pkg_depend` | 37-39 | dependency format |
| `verification/global_ocean.cs32x15/input.seaice/data`, `data.pkg` | 16-17 | densities; packages |
