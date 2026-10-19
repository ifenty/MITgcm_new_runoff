#!/usr/bin/env python3
"""Heat budget of the default runoff route with pkg/seaice on (RUNOFF-024, part 1).

What this checks
================

On the default route (``RNF_applyAsRain = .FALSE.``) the heat of the runoff
does not go through ``Qnet``. The package adds it as a temperature tendency
at the target level (``RNF_TENDENCY_APPLY_T``, diagnostic ``RNFgT``).
pkg/seaice sees none of the runoff volume on this route. The owner's budget
(``open_issues.md``, RUNOFF-024, clarification of 2026-10-18) is then::

    delivered heat = d(ocean heat content) + melt heat of ice
                     + melt heat of snow + d(ice heat content)

It holds for the difference of two runs. Run *warm* has 25 degC runoff at a
target cell that is ice covered. Run *none* has the same volume and no
temperature variable, so its water enters at the cell temperature and has no
heat of its own. Some of the heat melts ice instead of warming the ocean.
The owner expects this.

Result in one paragraph
=======================

**The budget closes to about 2.5 percent of the delivered heat, not
exactly.** The residual is -0.011 to -0.023 along the run and -0.0154 at the
end. It is systematic: it has the same sign in every run and it is 1e10
times larger than the noise. **It is not explained.** Two candidate causes
failed to explain it (see "Residual"). The tolerance is
0.03.

Definitions (constants come from the parameter dump of the run)
---------------------------------------------------------------

* **Delivered heat.** The sum over the steps of
  ``dt * rhoConst * Cp * sum(RNFgT * hFacC * drF * rA)`` in the *warm* run.
  ``RNFgT`` is ``m*(T_r - theta)*mass2rUnit/(drF*hFacC)`` with
  ``m = rhoConstFresh*flux*frac/rA`` (``rnf_tendency_apply.F``, decision 3).
  **The reference temperature is the local theta of the target cell.** It is
  not 0 degC and it is not the freezing point. The check compares ``RNFgT``
  of step 1 with this formula from the file and the start theta. The
  agreement is 1.9e-16 and the field is 0 at every other cell.
* **Ocean heat content.** ``rhoConst*Cp*sum(theta*hFacC*drF*rA)`` with the
  static ``hFacC``. lab_sea has a linear free surface. Mass from ``addMass``
  changes the free surface and not the grid. A source at the local
  temperature changes no theta by itself (the *none* run).
* **Melt heat.** The energy of ocean plus ice, counted from liquid water, is
  ``OHC - L*V``. Ice that is lost took up heat, so the term is ``-L*dV``.
  ``L_ice`` is ``SEAICE_rhoIce*SEAICE_lhFusion`` on ``sum(SIheff*rA)``.
  ``L_snow`` is ``SEAICE_rhoSnow*SEAICE_lhFusion`` on ``sum(SIhsnow*rA)``.
  The brief wrote ``+L*dV``. That sign fails by 131 percent, and it is the
  first control. ``pkg/seaice`` of this build has no ice enthalpy state
  (zero-layer thermodynamics, ``SEAICE_ITD`` undefined). So ``d(ice heat
  content)`` is 0.
* **Residual.** Delivered heat minus the three terms, as a share of the
  delivered heat. ``d`` is *warm* minus *none*, end minus start.

Start state and target cell
---------------------------

The runs start at iteration 0 with no pickup. The pickup of lab_sea has no
``AddMass`` field, and the ``ALLOW_ADDFLUID`` build refuses to restart
without it. The ocean and the ice start from the year-end state files of
``lab_sea/input``. The default start has no ice. Cell 52 of ``sparse_info()``
has no ice in the year-end file either. So :func:`ice_cell` picks the fully
covered cell with the thickest ice (cell 261, 1.63 m of ice, 0.135 m of
snow). A source of 1e5 m^3/s at 25 degC runs for 72 steps of 3600 s.

Measured (default call, delivered heat 2.6457e18 J)
---------------------------------------------------

d(OHC) is 0.3523, ice melt is 0.6631, the snow term is +4.1e-6, residual
is -0.0154. The quantity ``L*d(snow volume)`` is -4.15e-6. It is a
different quantity from the snow term, which is its negative.
At ``--t-runoff`` 10 and 40 the residual is -0.0233 and -0.0067. With
``--steps 24`` it is -0.0188.

Residual
--------

* **Noise.** A third run (*eps*) has ``T_r`` raised by 1e-12 degC. Its
  terms are at most 3e-13 of the delivered heat. The runs do not diverge by
  chaos in three days. The noise sets no tolerance.
* **Sensible heat of the meltwater** (a reference figure with no verdict, from
  the review hypothesis). The extra meltwater leaves the ice at the freezing point
  ``T_f = SEAICE_tempFrz0 + S*SEAICE_dTempFrz_dS``. Its sensible heat is
  ``Cp*M*(T_f - T_ref)`` with ``M = rhoIce*dV`` per cell. With ``T_ref`` the
  theta of the surface layer the term is -0.0100 of the delivered heat and
  the residual after it is -0.0054. With ``T_ref`` the theta of the top three
  layers the term is -0.0013 and the residual after it is -0.0142. The result
  depends on the reference, and neither value brings the residual to the
  noise. The hypothesis does not explain the residual.
* **Pair with pkg/seaice off** (a reference figure with no verdict). The same two runs
  without ice give (delivered - dOHC)/delivered = -0.0159 with no ice at all.
  With the response of ``TFLUX`` plus ``oceQsw`` the figure is -0.0793. This
  pair does not bound the error of the ice term. It has no ice term and its
  surface flux regime differs. It shows only that an offset of the same size
  exists without ice. So the residual is not evidently caused by the ice. The command is
  ``python3 tests/rnf/ice_heat_check.py``, run on 2026-10-19. The pair is
  part of the default call and ``--no-iceoff`` skips it.
* **Atmospheric flux.** The response of ``SIatmQnt`` is -0.0007 at 12 h and
  -0.0268 at 72 h. It does not follow the residual.

Tolerance
---------

:data:`TOL_FLOOR` is 0.03. The largest residual measured is 0.0233 (cell
261 at 10 degC) and the ice-off offset is 0.0159. The tolerance is below
every control. It is a choice and not a property of the noise. The check
uses the larger of it and ``K_NOISE`` times the noise.

**Sensitivity.** The residual share is linear in each term, so
:func:`sensitivity` solves for the errors that pass. The default call
prints them. At tolerance 0.03 an error of the ice term passes from -6.9
percent to +2.2 percent. An error of d(OHC) passes from -12.9 percent to
+4.1 percent. At the earlier tolerance 0.05 the limits were -9.9 and +5.2
percent for the ice term and -18.6 and +9.8 percent for d(OHC). **Errors of
the ice term inside these limits pass.** A 5 percent error of d(OHC) in the
positive direction fails now. The same error in the negative direction
passes.

Start checks
------------

The check stops with a message in two cases. In the first, no cell has
``AREA >= 0.99`` and ``HEFF > 0`` at the start. In the second, the delivered
heat is 0. It fails if the
target cell has no ice at the start. It fails if the ice volume of *warm* and
*none* differs by less than ten times the noise of the *eps* pair.

Controls (must fail the same tolerance)
---------------------------------------

* ``no_ice_term``: ice and snow terms set to 0. Residual 0.648. The share
  of the heat that goes to ice is 0.66, so the discrimination is large.
* ``ice_sign_flipped``: ``+L*dV``. Residual 1.311.
* ``ice_density_of_snow``: the ice term with ``rhoSnow``. Residual 0.407.

**L_snow is not verified.** The control ``snow_dropped`` passes the
tolerance, so it is a reference figure and does not count. At cell 261 the snow
term is +4.1e-6 of the delivered heat. Trials with ``--cell 301`` and
``--cell 285`` (snow 0.40 m and 0.35 m at the start) give snow shares of
0.026 and 0.036. That is below the tolerance. The residual is 0.0228 with
the snow term and 0.0030 without it at cell 301. It is 0.0156 and 0.0205 at
cell 285. No cell gives a snow control that fails, and the snow term does
not improve the closure consistently. At cell 301 the closure is 0.0228
with the snow term and 0.0030 without it, so the snow term makes it worse
there. The acceptance "ice and snow" is met for ice only. The check makes no claim about ``L_snow``.

The work did not build a code mutant of ``pkg/rnf``.

What this does not cover
------------------------

The legacy route (``RNF_applyAsRain = .TRUE.``), a build without
``SEAICE_EXTERNAL_FLUXES``, pkg/thsice, multi-layer ice, ``L_snow``, the
cause of the residual and cs32. It is one source in one cell over three
days.

Usage
=====

    python3 tests/rnf/ice_heat_check.py [--build] [--steps N] [--cell C]
        [--no-iceoff] [--keep] [--json PATH]

The build is ``build_esx_addm`` of ``tests/rnf/level_check.py``. Exit 0 means
the budget passes and the controls fail as they must. Exit 1 means a
failure. Exit 2 means the binary is missing.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (VERIF, add_to_namelist,  # noqa: E402
                           read_file, replace_line, sparse_info)
from applied_field_check import set_namelist  # noqa: E402
from tendency_term_check import (build_if_stale, param,  # noqa: E402
                                 read_mds, report_build, run_model)
from level_check import BUILD, write_addm_code  # noqa: E402

EXPERIMENT = "lab_sea"
PREFIX = "input.rnfice_"
SPARSE_FILE = "runoff_ice.nc"
#: Volume flux of the one source [m^3/s]: as tests/rnf/kpp_heat_check.py.
FLUX = 1.0e5
#: Temperature of the warm source [degC], and the 1e-12 raise of the noise run.
T_RUNOFF = 25.0
T_EPS = 1.0e-12
#: Steps of each run (deltaT = 3600 s): three days.
STEPS = 72
#: State and ice dump interval [steps].
DUMP_STEPS = 12
#: Relative tolerance of the analytic comparison of RNFgT at step 1.
RTOL_ANALYTIC = 1.0e-12
#: Floor of the budget tolerance (share of the delivered heat). The next
#: constant multiplies the measured noise.
TOL_FLOOR = 0.03
K_NOISE = 10.0
NX, NY = 20, 16
#: Label of the state files of lab_sea/input (ocean and ice) the run starts from.
STATE_LABEL = "0000008760"
UNSET_RL = 1.234567e5

DATA_DIAGNOSTICS = """# tests/rnf/ice_heat_check.py: averages of every step
# (frequency = deltaT), MDS, float64. They hold the runoff temperature
# tendency, the surface heat flux and the net atmospheric heat flux.
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
  fields(1,1) = 'RNFgT   ',
  fileName(1) = 'iceGT',
  frequency(1) = {dt!r},
  fileFlags(1) = 'D       ',
  fields(1,2) = 'TFLUX   ',
  fileName(2) = 'iceTflux',
  frequency(2) = {dt!r},
  fileFlags(2) = 'D       ',
  fields(1,3) = '{atm}',
  fileName(3) = 'iceAtmQ',
  frequency(3) = {dt!r},
  fileFlags(3) = 'D       ',
  fields(1,4) = 'oceQsw  ',
  fileName(4) = 'iceQsw',
  frequency(4) = {dt!r},
  fileFlags(4) = 'D       ',
 &

 &DIAG_STATIS_PARMS
 &
"""


#: Set by ``--cell`` to override :func:`ice_cell`.
CELL_OVERRIDE = None


def ice_cell():
    """Return the target cell.

    It is the ocean cell with the thickest ice among the fully covered
    cells (``AREA`` >= 0.99) of the start state. That cell has snow too.
    ``CELL_OVERRIDE`` replaces it."""
    import numpy as np
    if CELL_OVERRIDE is not None:
        return CELL_OVERRIDE
    base = os.path.join(VERIF, EXPERIMENT, "input")
    area, heff = (np.fromfile(os.path.join(base, f"{n}.{STATE_LABEL}"),
                              dtype=">f4")[:NX*NY] for n in ("AREA", "HEFF"))
    covered = np.where((area >= 0.99) & (heff > 0.0), heff, -1.0)
    if covered.max() <= 0.0:
        raise SystemExit("ice_cell: no cell has AREA >= 0.99 and HEFF > 0 "
                         "in the start state")
    return int(np.argmax(covered))


def write_sparse(path, cell, dt, nrec, warm, t_runoff):
    """One source on ``cell``, constant flux in every record."""
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(path, "w") as ds:
        ds.set_auto_maskandscale(False)
        ds.setncatts({"mitgcm_runoff_schema_version": "1.0",
                      "mitgcm_grid_nx": np.int32(NX),
                      "mitgcm_grid_ny": np.int32(NY),
                      "mitgcm_time_sampling": "fixed",
                      "mitgcm_time_period": np.float64(dt),
                      "mitgcm_time_repeat": "none",
                      "title": "tests/rnf/ice_heat_check.py"})
        ds.createDimension("time", nrec)
        ds.createDimension("nv", 2)
        ds.createDimension("source", 1)
        ds.createDimension("target", 1)
        ds.createDimension("id_strlen", 8)
        time = ds.createVariable("time", "f8", ("time",))
        time.units = "seconds since 1979-01-01 00:00:00"
        time.calendar = "gregorian"
        time.axis = "T"
        time.bounds = "time_bnds"
        time[:] = dt*np.arange(nrec)
        bnds = ds.createVariable("time_bnds", "f8", ("time", "nv"))
        bnds.units = time.units
        bnds.calendar = time.calendar
        bnds[:, 0] = dt*np.arange(nrec)
        bnds[:, 1] = dt*np.arange(1, nrec + 1)
        ds.createVariable("source_id", "S1", ("source", "id_strlen"))[:] = \
            np.array([list("warmrivr")], dtype="S1")
        ds.createVariable("target_source", "i4", ("target",))[:] = [0]
        ds.createVariable("target_cell", "i4", ("target",))[:] = [cell]
        frac = ds.createVariable("target_fraction", "f8", ("target",))
        frac.units = "1"
        frac[:] = 1.0
        flux = ds.createVariable("runoff_flux", "f8", ("time", "source"))
        flux.units = "m3 s-1"
        flux[:] = FLUX
        if warm:
            temp = ds.createVariable("runoff_temperature", "f8",
                                     ("time", "source"))
            temp.units = "degC"
            temp[:] = t_runoff


def write_input(input_dir, warm, t_runoff, steps, ice=True):
    """The scratch input of one run, layered on lab_sea/input.

    The run starts at iteration 0 with no pickup (the pickup of lab_sea
    has no ``AddMass`` field, which the ``ALLOW_ADDFLUID`` build needs to
    restart). The ocean and the ice start from the end-of-year state files
    of lab_sea's own input (:data:`STATE_LABEL`): measured, the default
    start has no ice at all and the cell of ``sparse_info()`` has none in
    that state either, so the target is :func:`ice_cell`. With ``ice``
    false, pkg/seaice is off (the ice-off pair, reported only)."""
    base = os.path.join(VERIF, EXPERIMENT, "input")
    cell = ice_cell()
    dt = 3600.0
    start = 0.0
    write_sparse(os.path.join(input_dir, SPARSE_FILE), cell, dt, steps + 4,
                 warm, t_runoff)
    with open(os.path.join(base, "data")) as fh:
        data = fh.read()
    settings = [
        ("PARM03", "startTime", " startTime=0.0,"),
        ("PARM03", "endTime", f" endTime={start + steps*dt!r},"),
        ("PARM03", "monitorFreq", " monitorFreq=1.,"),
        ("PARM03", "pChkptFreq", " pChkptFreq=0.,"),
        ("PARM03", "dumpFreq", f" dumpFreq={DUMP_STEPS*dt!r},"),
        ("PARM03", "dumpInitAndLast", " dumpInitAndLast=.TRUE.,"),
        ("PARM01", "writeBinaryPrec", " writeBinaryPrec=64,"),
        ("PARM03", "outputTypesInclusive", " outputTypesInclusive=.TRUE."
         ","),
        # the generalized route needs addMass with a real volume, a linear
        # free surface and T, S stepped after the flow (level_check.py)
        ("PARM05", "hydrogThetaFile",
         f" hydrogThetaFile='T.{STATE_LABEL}',"),
        ("PARM05", "hydrogSaltFile", f" hydrogSaltFile='S.{STATE_LABEL}',"),
        ("PARM01", "useRealFreshWaterFlux", " useRealFreshWaterFlux=.FALSE.,"),
        ("PARM01", "nonlinFreeSurf", " nonlinFreeSurf=0,"),
        ("PARM01", "selectAddFluid", " selectAddFluid=1,"),
        ("PARM01", "staggerTimeStep", " staggerTimeStep=.TRUE.,"),
        ("PARM01", "convertFW2Salt", " convertFW2Salt=35.0,"),
        ("PARM01", "temp_addMass", f" temp_addMass={UNSET_RL!r},"),
        ("PARM01", "salt_addMass", f" salt_addMass={UNSET_RL!r},"),
    ]
    for namelist, name, line in settings:
        data = set_namelist(data, namelist, name, line)
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)
    with open(os.path.join(base, "data.seaice")) as fh:
        sea = fh.read()
    for line in (f" AreaFile = 'AREA.{STATE_LABEL}',",
                 f" HeffFile = 'HEFF.{STATE_LABEL}',",
                 f" HsnowFile = 'HSNOW.{STATE_LABEL}',"):
        sea = add_to_namelist(sea, "SEAICE_PARM01", line)
    with open(os.path.join(input_dir, "data.seaice"), "w") as fh:
        fh.write(sea)
    with open(os.path.join(base, "data.pkg")) as fh:
        pkg = fh.read()
    for name, value in (("useSEAICE", ".TRUE." if ice else ".FALSE."), ("useMNC", ".FALSE."),
                        ("useDiagnostics", ".TRUE."), ("useRNF", ".TRUE.")):
        line = f"  {name} = {value},"
        pkg = (replace_line(pkg, name, line)
               if re.search(r"(?mi)^\s*%s\s*=" % re.escape(name), pkg)
               else add_to_namelist(pkg, "PACKAGES", line))
    with open(os.path.join(input_dir, "data.pkg"), "w") as fh:
        fh.write(pkg)
    with open(os.path.join(base, "data.exf")) as fh:
        exf = fh.read()
    exf = set_namelist(exf, "EXF_NML_02", "runoffFile",
                       " runoffFile        = ' ',")
    with open(os.path.join(input_dir, "data.exf"), "w") as fh:
        fh.write(exf)
    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(DATA_DIAGNOSTICS.format(
            dt=dt, atm="SIatmQnt" if ice else "TFLUX   "))
    with open(os.path.join(input_dir, "data.longstep"), "w") as fh:
        fh.write(" &LONGSTEP_PARM01\n  LS_nIter = 1,\n"
                 "  LS_whenToSample = 0,\n &\n")
    with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
        fh.write("# Written by tests/rnf/ice_heat_check.py: the default\n"
                 "# (generalized) route, RNF_applyAsRain left at .FALSE.\n"
                 " &RNF_PARM01\n"
                 f"  RNF_file = '{SPARSE_FILE}',\n"
                 " &\n")
    return cell, dt


def field(run_dir, base):
    import numpy as np
    values, sizes = read_mds(run_dir, base)
    return np.asarray(values), sizes


def labels(run_dir, stem):
    return sorted(os.path.basename(p).split(".")[1] for p in
                  glob.glob(os.path.join(run_dir, stem + ".*.data")))


def run_state(run_dir, grid, text, ice=True):
    """Integrals of one run: the start and end state and the flux sums."""
    import numpy as np
    vol, rac, rho_c, cp = grid
    dumps = labels(run_dir, "T")
    first, last = dumps[0], dumps[-1]
    out = {"labels": dumps}
    series = []
    for lab in dumps:
        t, _ = field(run_dir, "T." + lab)
        row = {"label": lab, "OHC": rho_c*cp*float(np.sum(t*vol))}
        for key, stem in ((("ice", "HEFF"), ("snow", "HSNOW")) if ice
                          else ()):
            x, _ = field(run_dir, stem + "." + lab)
            row[key] = float(np.sum(x*rac))
        series.append(row)
    out["series"] = series
    out["first"], out["last"] = first, last
    step_labels = labels(run_dir, "iceGT")
    out["steps"] = len(step_labels)
    return out, step_labels


def flux_sums(run_dir, step_labels, vol, rac, rho_c, cp, dt):
    """Sums over the steps [J] of the delivered heat and the surface flux."""
    import numpy as np
    sums = {"delivered": 0.0, "TFLUX": 0.0, "SIatmQnt": 0.0,
            "delivered_cum": [], "TFLUX_cum": [], "Qsw": 0.0,
            "SIatmQnt_cum": []}
    plane = NX*NY
    for lab in step_labels:
        g, _ = field(run_dir, "iceGT." + lab)
        sums["delivered"] += dt*rho_c*cp*float(np.sum(g*vol))
        sums["delivered_cum"].append(sums["delivered"])
        tf, _ = field(run_dir, "iceTflux." + lab)
        sums["TFLUX"] += dt*float(np.sum(tf[:plane]*rac))
        aq, _ = field(run_dir, "iceAtmQ." + lab)
        # SIatmQnt is positive when it decreases theta
        sums["SIatmQnt"] += -dt*float(np.sum(aq[:plane]*rac))
        qs, _ = field(run_dir, "iceQsw." + lab)
        sums["Qsw"] += dt*float(np.sum(qs[:plane]*rac))
        sums["TFLUX_cum"].append(sums["TFLUX"])
        sums["SIatmQnt_cum"].append(sums["SIatmQnt"])
    return sums


def budget(a, b, sums_a, ice_sign=1.0, snow_on=True, ice_on=True,
           consts=None, dump=-1, l_ice=None):
    """Terms of ``a`` minus ``b`` [J] at dump index ``dump`` (default: the
    end); ``delivered`` is that of ``a`` up to then. The heat of melting is
    ``-L*dV``: the energy of ocean plus ice, counted from liquid water, is
    ``OHC - L*V``, so it is ice that is *lost* that took up heat."""
    l_ice = consts["L_ice"] if l_ice is None else l_ice
    l_snow = consts["L_snow"]
    steps = (len(sums_a["delivered_cum"]) if dump == -1
             else dump*DUMP_STEPS)
    dump = len(a["series"]) - 1 if dump == -1 else dump
    d_ohc = a["series"][dump]["OHC"] - a["series"][0]["OHC"] - (
        b["series"][dump]["OHC"] - b["series"][0]["OHC"])
    d_ice = (a["series"][dump]["ice"] - a["series"][0]["ice"]) - (
        b["series"][dump]["ice"] - b["series"][0]["ice"])
    d_snow = (a["series"][dump]["snow"] - a["series"][0]["snow"]) - (
        b["series"][dump]["snow"] - b["series"][0]["snow"])
    delivered = sums_a["delivered_cum"][steps - 1] if steps else 0.0
    # heat that melted (+) or was released by freezing (-): minus L dV
    ice_term = -ice_sign*l_ice*d_ice if ice_on else 0.0
    snow_term = -l_snow*d_snow if (ice_on and snow_on) else 0.0
    return {"d_OHC": d_ohc, "L_ice_dVice": ice_term,
            "L_snow_dVsnow": snow_term,
            "d_ice_heat": 0.0,
            "delivered": delivered,
            "residual": delivered - (d_ohc + ice_term + snow_term),
            "raw_d_ice": d_ice, "raw_d_snow": d_snow}


def meltwater_sensible(warm_dir, none_dir, last, vol, rac, drf, hfac, consts):
    """Report the sensible heat of the extra meltwater (hypothesis of review).

    The mass is ``M_c = rhoIce*(HEFF_none - HEFF_warm)*rA`` per cell at the
    end of the run. Its heat is ``Cp*M_c*(T_f - T_ref)``. ``T_f`` is the
    freezing point of the surface water of the warm run,
    ``SEAICE_tempFrz0 + S*SEAICE_dTempFrz_dS``. Two references ``T_ref``
    are used. The first is theta of the surface layer of the same cell
    (the layer that receives the water). The second is theta of the top
    three layers (the mixed layer, 35 m) of the same cell. The result is a
    reported figure and enters no verdict."""
    import numpy as np
    plane = NX*NY
    heff_w, _ = field(warm_dir, "HEFF." + last)
    heff_n, _ = field(none_dir, "HEFF." + last)
    mass = consts["SEAICE_rhoIce"]*(heff_n - heff_w)*rac
    theta, _ = field(warm_dir, "T." + last)
    salt, _ = field(warm_dir, "S." + last)
    t_freeze = (consts["SEAICE_tempFrz0"]
                + salt[:plane]*consts["SEAICE_dTempFrz_dS"])
    top = np.zeros(plane)
    thick = np.zeros(plane)
    for k in range(3):
        w = drf[k]*hfac[k*plane:(k + 1)*plane]
        top += theta[k*plane:(k + 1)*plane]*w
        thick += w
    t_mixed = top/np.where(thick > 0, thick, 1.0)
    cp = consts["HeatCapacity_Cp"]
    return {"melt_mass_kg": float(mass.sum()),
            "heat_J_ref_surface_layer": float(
                cp*np.sum(mass*(t_freeze - theta[:plane]))),
            "heat_J_ref_mixed_layer": float(
                cp*np.sum(mass*(t_freeze - t_mixed))),
            "mean_T_freeze": float(np.sum(mass*t_freeze)/mass.sum())
            if mass.sum() else 0.0}


def iceoff_report(warm_dir, none_dir, steps):
    """Report the closure of the pair with pkg/seaice off (no verdict).

    There is no ice term. The share ``(delivered - dOHC)/delivered`` is the
    part of the heat that the content of the ocean does not show. The
    second share adds the response of the model's own surface flux,
    ``TFLUX`` plus ``oceQsw``."""
    import numpy as np
    text = read_file(warm_dir, "output.txt") or ""
    cp = param(text, "HeatCapacity_Cp")
    rho_c = param(text, "rhoConst")
    rac, _ = field(warm_dir, "RAC")
    drf, _ = field(warm_dir, "DRF")
    hfac, sizes = field(warm_dir, "hFacC")
    vol = np.tile(rac, sizes[2])*np.repeat(drf, NX*NY)*hfac
    grid = (vol, rac, rho_c, cp)
    out = {}
    states, sums = {}, {}
    for tag, d in (("warm", warm_dir), ("none", none_dir)):
        states[tag], step_labels = run_state(d, grid, text, ice=False)
        sums[tag] = flux_sums(d, step_labels, vol, rac, rho_c, cp, 3600.0)
    delivered = sums["warm"]["delivered"]
    d_ohc = (states["warm"]["series"][-1]["OHC"]
             - states["warm"]["series"][0]["OHC"]
             - states["none"]["series"][-1]["OHC"]
             + states["none"]["series"][0]["OHC"])
    flux = (sums["warm"]["TFLUX"] + sums["warm"]["Qsw"]
            - sums["none"]["TFLUX"] - sums["none"]["Qsw"])
    out["delivered_J"] = delivered
    out["dOHC_share"] = d_ohc/delivered
    out["share_without_flux_response"] = (delivered - d_ohc)/delivered
    out["share_with_flux_response"] = (delivered + flux - d_ohc)/delivered
    out["flux_response_share"] = flux/delivered
    return out


def sensitivity(main, tol):
    """Return the scale errors of a budget term that the tolerance lets pass.

    The residual share is linear in each term. A relative error ``x`` of
    the ice term (melt heat of ice) moves it by ``-x*ice_share``. A relative
    error ``y`` of d(OHC) moves it by ``-y*ohc_share``. The function solves
    ``|r0 - x*share| = tol`` for both ends. An error inside the returned
    interval passes the check."""
    delivered = main["delivered"]
    r0 = main["residual"]/delivered
    out = {}
    for name, key in (("ice_term", "L_ice_dVice"), ("d_OHC", "d_OHC")):
        share = main[key]/delivered
        ends = sorted(((r0 - sign*tol)/share) for sign in (1.0, -1.0))
        out[name] = {"share": share, "lowest_passing_error": ends[0],
                     "highest_passing_error": ends[1]}
    return out


def judge(dirs, cell, steps, t_runoff, tol_floor=TOL_FLOOR, k_noise=K_NOISE):
    import numpy as np
    problems = []
    warm_dir, none_dir, eps_dir = dirs
    text = read_file(warm_dir, "output.txt") or ""
    cp = param(text, "HeatCapacity_Cp")
    rho_c = param(text, "rhoConst")
    rho_f = param(text, "rhoConstFresh")
    consts = {"HeatCapacity_Cp": cp, "rhoConst": rho_c, "rhoConstFresh": rho_f}
    rho_i = param(text, "SEAICE_rhoIce")
    rho_s = param(text, "SEAICE_rhoSnow")
    lh = param(text, "SEAICE_lhFusion")
    consts.update(SEAICE_tempFrz0=param(text, "SEAICE_tempFrz0"),
                  SEAICE_dTempFrz_dS=param(text, "SEAICE_dTempFrz_dS"))
    consts.update(SEAICE_rhoIce=rho_i, SEAICE_rhoSnow=rho_s,
                  SEAICE_lhFusion=lh, L_ice=rho_i*lh, L_snow=rho_s*lh)
    rac, _ = field(warm_dir, "RAC")
    drf, _ = field(warm_dir, "DRF")
    hfac, sizes = field(warm_dir, "hFacC")
    nr = sizes[2]
    plane = NX*NY
    vol = np.tile(rac, nr)*np.repeat(drf, plane)*hfac
    for d in (none_dir, eps_dir):
        h2, _ = field(d, "hFacC")
        if not np.array_equal(h2, hfac):
            problems.append("hFacC differs between the runs")
    grid = (vol, rac, rho_c, cp)
    dt = 3600.0

    states, sums = {}, {}
    for tag, d in (("warm", warm_dir), ("none", none_dir), ("eps", eps_dir)):
        st, step_labels = run_state(d, grid, text)
        if st["steps"] != steps:
            problems.append(f"{tag}: {st['steps']} step files, not {steps}")
        states[tag] = st
        sums[tag] = flux_sums(d, step_labels, vol, rac, rho_c, cp, dt)
    if [r["label"] for r in states["warm"]["series"]] != \
            [r["label"] for r in states["none"]["series"]]:
        problems.append("the runs dump at different iterations")
    for tag in ("none",):
        if sums[tag]["delivered"] != 0.0:
            problems.append("RNFgT is not 0 in the run without temperature "
                            f"({sums[tag]['delivered']!r})")
    # the start of the two runs is the same state
    for stem in ("T", "HEFF", "HSNOW"):
        a, _ = field(warm_dir, stem + "." + states["warm"]["first"])
        b, _ = field(none_dir, stem + "." + states["none"]["first"])
        if not np.array_equal(a, b):
            problems.append(f"{stem} at the start differs between the runs")

    # analytic RNFgT at step 1 (the target cell, level 1)
    g1, _ = field(warm_dir, "iceGT." + labels(warm_dir, "iceGT")[0])
    t0, _ = field(warm_dir, "T." + states["warm"]["first"])
    m = rho_f*FLUX/float(rac[cell])
    want = m*(t_runoff - float(t0[cell]))/rho_c/(
        float(drf[0])*float(hfac[cell]))
    got = float(g1[cell])
    rel_an = abs(got - want)/abs(want)
    elsewhere = int(np.count_nonzero(np.delete(g1, cell)))
    if not rel_an <= RTOL_ANALYTIC:
        problems.append(f"RNFgT at step 1: {got!r}, analytic {want!r}, "
                        f"relative {rel_an:.3e}")
    if elsewhere:
        problems.append(f"RNFgT is not 0 at {elsewhere} other cells")

    main = budget(states["warm"], states["none"], sums["warm"], consts=consts)
    noise_b = budget(states["warm"], states["eps"], sums["eps"], consts=consts)
    delivered = main["delivered"]
    if delivered == 0.0:
        raise SystemExit("judge: the delivered heat is 0, so no share can "
                         "be formed. RNFgT is 0 in the warm run.")
    # the target cell has ice at the start, and the ice of the pair differs
    area0, _ = field(warm_dir, "AREA." + states["warm"]["first"])
    heff0, _ = field(warm_dir, "HEFF." + states["warm"]["first"])
    if not (area0[cell] >= 0.99 and heff0[cell] > 0.0):
        problems.append(f"the target cell {cell} has AREA {area0[cell]!r} "
                        f"and HEFF {heff0[cell]!r} at the start: no ice")
    ice_noise = abs(noise_b["raw_d_ice"])
    if not abs(main["raw_d_ice"]) > 10.0*ice_noise:
        problems.append(f"the ice volume of warm and none differs by "
                        f"{main['raw_d_ice']!r} m^3, not more than ten "
                        f"times the noise {ice_noise!r}")
    if delivered != sums["warm"]["delivered"]:
        problems.append("delivered heat of the budget is not the run's sum")
    noise_terms = {k: abs(noise_b[k]) for k in
                   ("d_OHC", "L_ice_dVice", "L_snow_dVsnow")}
    noise = max(noise_terms.values())/abs(delivered)
    tol = max(tol_floor, k_noise*noise)
    share = abs(main["residual"])/abs(delivered)
    if share > tol:
        problems.append(f"residual {share:.4f} of the delivered heat > "
                        f"tolerance {tol:.4f}")
    # controls
    controls = {}
    for name, kw in (("no_ice_term", {"ice_on": False}),
                     ("ice_sign_flipped", {"ice_sign": -1.0}),
                     ("ice_density_of_snow",
                      {"l_ice": consts["L_snow"]})):
        c = budget(states["warm"], states["none"], sums["warm"],
                   consts=consts, **kw)
        c_share = abs(c["residual"])/abs(delivered)
        controls[name] = {"residual_share": c_share, "fails": c_share > tol}
        if c_share <= tol:
            problems.append(f"control {name} passes the tolerance "
                            f"({c_share:.4f} <= {tol:.4f}): the check cannot "
                            f"tell it from the full budget")
    # Reported, not asserted. The snow volume hardly changes in the pair.
    c = budget(states["warm"], states["none"], sums["warm"], consts=consts,
               snow_on=False)
    controls["snow_dropped (reported only)"] = {
        "residual_share": abs(c["residual"])/abs(delivered),
        "fails": abs(c["residual"])/abs(delivered) > tol}
    sens = sensitivity(main, tol)
    # residual along the run
    along = []
    for k in range(1, len(states["warm"]["series"])):
        bk = budget(states["warm"], states["none"], sums["warm"],
                    consts=consts, dump=k)
        along.append({"step": k*DUMP_STEPS,
                      "delivered": bk["delivered"],
                      "dOHC_share": bk["d_OHC"]/bk["delivered"],
                      "ice_share": bk["L_ice_dVice"]/bk["delivered"],
                      "residual_share": bk["residual"]/bk["delivered"],
                      # reported: the response of the atmospheric flux
                      "dSIatmQnt_share": (
                          sums["warm"]["SIatmQnt_cum"][k*DUMP_STEPS - 1]
                          - sums["none"]["SIatmQnt_cum"][k*DUMP_STEPS - 1])
                      / bk["delivered"]})
    last = states["warm"]["last"]
    sensible = meltwater_sensible(warm_dir, none_dir, last, vol, rac, drf,
                                  hfac, consts)
    for key in ("heat_J_ref_surface_layer", "heat_J_ref_mixed_layer"):
        sensible[key.replace("heat_J", "share")] = sensible[key]/delivered
        sensible[key.replace("heat_J", "residual_share_after")] = (
            main["residual"] - sensible[key])/delivered
    snow_cell = {"HSNOW_start": float(field(
        warm_dir, "HSNOW." + states["warm"]["first"])[0][cell]),
        "L_dV_snow_share": main["raw_d_snow"]*consts["L_snow"] / delivered,
        "snow_term_share": main["L_snow_dVsnow"]/delivered}
    ice_share = (main["L_ice_dVice"] + main["L_snow_dVsnow"])/delivered
    extra = {}
    for tag, ref in (("main", "none"), ("noise", "eps")):
        extra[tag] = {
            "dTFLUX": sums["warm"]["TFLUX"] - sums[ref]["TFLUX"],
            "dTFLUX_plus_Qsw": (sums["warm"]["TFLUX"] + sums["warm"]["Qsw"]
                                - sums[ref]["TFLUX"] - sums[ref]["Qsw"]),
            "dSIatmQnt": sums["warm"]["SIatmQnt"] - sums[ref]["SIatmQnt"]}
    result = {"cell": cell, "steps": steps, "T_runoff": t_runoff,
              "constants": consts, "delivered_J": delivered,
              "analytic_RNFgT": {"got": got, "want": want, "relative": rel_an,
                                 "theta_start": float(t0[cell])},
              "main": main, "noise_budget": noise_b, "noise_share": noise,
              "tolerance": tol, "residual_share": share,
              "ice_snow_share_of_delivered": ice_share,
              "ohc_share_of_delivered": main["d_OHC"]/delivered,
              "controls": controls, "along_the_run": along,
              "sensitivity": sens,
              "start_cell": {"AREA": float(area0[cell]),
                             "HEFF": float(heff0[cell])},
              "surface_flux_response_J": extra,
              "meltwater_sensible_heat": sensible, "snow_at_cell": snow_cell,
              "series": {t: states[t]["series"] for t in states},
              "problems": problems}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true",
                        help="compile build_esx_addm when it is missing or "
                             "stale")
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--t-runoff", type=float, default=T_RUNOFF)
    parser.add_argument("--cell", type=int, default=None,
                        help="target cell (default: ice_cell)")
    parser.add_argument("--no-iceoff", action="store_true",
                        help="skip the reported pair with pkg/seaice off")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json")
    args = parser.parse_args(argv)
    global CELL_OVERRIDE
    CELL_OVERRIDE = args.cell
    if args.steps % DUMP_STEPS:
        parser.error(f"--steps must be a multiple of {DUMP_STEPS}")
    if args.build and not report_build(
            build_if_stale(BUILD, write_addm_code, timeout=args.timeout*2)):
        return 2
    if not os.path.isfile(os.path.join(VERIF, EXPERIMENT, BUILD, "mitgcmuv")):
        print(f"MISSING: no binary {BUILD}; rerun with --build")
        return 2
    runs, dirs = {}, []
    cases = [("warm", True, args.t_runoff, True), ("none", False, None, True),
             ("eps", True, args.t_runoff + T_EPS, True)]
    if not args.no_iceoff:
        cases += [("warm_iceoff", True, args.t_runoff, False),
                  ("none_iceoff", False, None, False)]
    for tag, warm, t_r, ice in cases:
        name = PREFIX + tag
        input_dir = os.path.join(VERIF, EXPERIMENT, name)
        shutil.rmtree(input_dir, ignore_errors=True)
        os.makedirs(input_dir)
        dirs.append(input_dir)
        cell, _dt = write_input(input_dir, warm, t_r, args.steps, ice)
        run_dir, status, timed_out = run_model(name, BUILD, args.timeout)
        ended = "Execution ended Normally" in (read_file(run_dir,
                                                         "output.txt") or "")
        runs[tag] = (run_dir, status, timed_out, ended)
    bad = [f"{t} run exit {s}" + (" (timed out)" if to else "")
           + ("" if e else ", no normal end")
           for t, (_, s, to, e) in runs.items() if s or to or not e]
    if bad:
        print("FAIL ice_heat: " + "; ".join(bad))
        return 1
    result = judge([runs[t][0] for t in ("warm", "none", "eps")], cell,
                   args.steps, args.t_runoff)
    if not args.no_iceoff:
        result["ice_off_pair"] = iceoff_report(
            runs["warm_iceoff"][0], runs["none_iceoff"][0], args.steps)
    ok = not result["problems"]
    m = result["main"]
    d = result["delivered_J"]
    print(f"{'PASS' if ok else 'FAIL'} ice_heat: delivered {d:.6e} J; "
          f"dOHC {m['d_OHC']/d:.4f}, ice {m['L_ice_dVice']/d:.4f}, snow "
          f"{m['L_snow_dVsnow']/d:.4f}, residual {result['residual_share']:.4f}"
          f" of delivered (tolerance {result['tolerance']:.4f}, noise "
          f"{result['noise_share']:.2e})")
    for name, c in result["controls"].items():
        print(f"     control {name}: residual {c['residual_share']:.4f} -> "
              f"{'fails' if c['fails'] else 'passes'} the tolerance")
    print("     residual share along the run: " + ", ".join(
        f"{r['step']}h {r['residual_share']:+.4f} "
        f"(atm {r['dSIatmQnt_share']:+.4f})"
        for r in result["along_the_run"]))
    resp = {k: round(v/d, 4) for k, v in
            result["surface_flux_response_J"]["main"].items()}
    print(f"     RNFgT step 1 relative "
          f"{result['analytic_RNFgT']['relative']:.3e}; surface flux "
          f"response (share of delivered) {resp}")
    sens = result["meltwater_sensible_heat"]
    print("     reported, no verdict: sensible heat of the extra meltwater "
          f"{sens['share_ref_surface_layer']:+.4f} (surface layer) and "
          f"{sens['share_ref_mixed_layer']:+.4f} (mixed layer) of the "
          "delivered heat. Residual after it "
          f"{sens['residual_share_after_ref_surface_layer']:+.4f} and "
          f"{sens['residual_share_after_ref_mixed_layer']:+.4f}.")
    if "ice_off_pair" in result:
        off = result["ice_off_pair"]
        print("     reported, no verdict: pair with pkg/seaice off, "
              f"(delivered - dOHC)/delivered "
              f"{off['share_without_flux_response']:+.4f}, with the surface "
              f"flux response {off['share_with_flux_response']:+.4f}.")
    print("     snow at the cell: start "
          f"{result['snow_at_cell']['HSNOW_start']:.3f} m, snow term "
          f"{result['snow_at_cell']['snow_term_share']:+.2e} of the "
          "delivered heat. L_snow is not verified.")
    sens = result["sensitivity"]
    print("     sensitivity at tolerance "
          f"{result['tolerance']:.3f}: an error of the ice term passes "
          f"from {sens['ice_term']['lowest_passing_error']:+.3f} to "
          f"{sens['ice_term']['highest_passing_error']:+.3f}, an error of "
          f"d(OHC) from {sens['d_OHC']['lowest_passing_error']:+.3f} to "
          f"{sens['d_OHC']['highest_passing_error']:+.3f} (relative)")
    for problem in result["problems"]:
        print(f"     {problem}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=1)
    if not args.keep:
        for path in dirs + [runs[t][0] for t in runs]:
            shutil.rmtree(path, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
