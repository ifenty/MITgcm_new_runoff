# Runoff package design: architecture and MITgcm integration

> **Status: reviewed design (RUNOFF-010, two independent reviews, approved
> 2026-10-03); implementation in progress (skeleton: RUNOFF-012; static read,
> placement, file checks and the volume flux of a constant record:
> RUNOFF-004).** This is
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
- This call is the only change to exf code. `exf_mapfields.F` is not edited.

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

- `EXF_CHECK_RANGE` stops the run at the first step if `runoff` exceeds
  10⁻⁶ m/s on a wet cell (`pkg/exf/exf_check_range.F:175-191`, `211-216`), and
  `useExfCheckRange` defaults to true (`pkg/exf/exf_readparms.F:307`). A river
  of 1000 m³/s into one 2 km cell is 2.5·10⁻⁴ m/s. Users of point sources on
  fine grids must set `useExfCheckRange=.FALSE.`, or the upper bound must be
  skipped when `useRNF` is true. The second needs one more guarded line in exf.
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
refusals. RUNOFF-014 tests branches N, L and U with unchanged downstream code.
RUNOFF-016 must use the `rhoConstFresh/rhoConst` factor when it compares model
volume with source flux. RUNOFF-017 gains the refusals above, the scale-factor
one included. RUNOFF-026 states that exf input scaling is not applied. RUNOFF-024
tests that both ice packages receive sparse runoff through the exf array.
RUNOFF-011 must give every testbed an exf build: `isomip` and
`global_ocean.90x40x15` do not compile exf
(`verification/isomip/code/packages.conf`,
`verification/global_ocean.90x40x15/code/packages.conf`) and need it added in a
test variant. RUNOFF-026 documents `useExfCheckRange`.

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
RUNOFF-016 checks `(mT)` and `(mS)` against `rhoConstFresh·Σ flux·frac·X`, in
the sum over time when forcing is inside Adams-Bashforth. RUNOFF-022 adds a
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
closed into RUNOFF-013 or a tracer issue of its own. RUNOFF-016 checks tracer
budgets with the density factor. RUNOFF-017 gains the unmatched-name and
ptracers-off refusals. RUNOFF-029 covers tracer series in every time mode.

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
| `RNFtrNN ` | tracer units·kg/m²/s | `(mC_n) − m·C_ref,n` for runoff tracer `NN` |

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
the monitor sums and diagnostics. RUNOFF-022 needs no pickup file and tests the
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
11. **A property in the file that is not applied yet is reported, not
    dropped silently (decisions 3 and 4).** `RNF_INIT_FIXED` walks the
    variables of the file and prints a warning for each
    `runoff_temperature`, `runoff_salinity` and `runoff_ptracer_*` it finds,
    naming RUNOFF-013. Without it the volume would enter at the ambient
    temperature and at salinity 0 with no word in the log. The ptracer
    names are therefore not matched to `PTRACERS_names` yet, and
    `RNF_useTemp`, `RNF_useSalt` and `RNF_usePtracers` have no effect.

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
| `pkg/exf/exf_check_range.F`, `exf_readparms.F` | 175-191, 211-216; 307, 717 | range stop; default of `useExfCheckRange`; default of `exf_outscal_sflux` |
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
