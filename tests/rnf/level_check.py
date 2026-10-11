#!/usr/bin/env python3
"""Oracles of the generalized multi-level runoff route (RUNOFF-046).

What this checks
================

With ``RNF_applyAsRain = .FALSE.`` (the default) ``pkg/rnf`` puts the runoff
volume into the model's ``addMass`` at each target entry's own level
(``RNF_ADD_MASS``) and the heat, salt and tracers in as tendencies at that
level (``RNF_TENDENCY_APPLY_T/S/PTR``), the physical term

    g_X += [ (mX) - m_X*X(i,j,k) ] * mass2rUnit * recip_drF(k) * recip_hFacC

with the model's own generic ``temp_addMass``/``salt_addMass`` term on the
runoff share cancelled (package design, decision 3). Every case runs one
lab_sea column, cell ``sparse_info()["wet_cell"]`` (185 m deep, levels 1-8
full), from a uniform initial state (``THETA0``, ``SALT0``, ``TRC0`` of
``tests/rnf/tendency_term_check.py``) and measures the **first** time step:

* **Placement, analytic, per level** (cases ``deep``, ``multi``,
  ``deep_L_set``, ``deep_U_set``). At the target level ``K`` of each entry:
  ``RNFaddM`` is ``rhoConstFresh*flux*frac`` [kg/s]; ``RNFgT``, ``RNFgS`` and
  ``RNFtr01`` are ``m*(X_s - X0)*mass2rUnit/(drF(K)*hFacC)`` with
  ``m = rhoConstFresh*flux*frac/rA``; and the **total**, the state change
  ``(X^1 - X^0)`` of the run at ``(cell, K)`` minus that of the zero-flux run,
  is ``deltaT`` times that term. Every other level and cell holds 0 in
  ``RNFaddM`` and the three tendency diagnostics, exactly, and a state change
  difference below the tolerance. On a uniform state nothing but the runoff
  can tell the runs apart over that step: advection of a uniform field is
  zero in MITgcm's advective form (``gad_calc_rhs.F``, the ``-localT*div``
  term), diffusion is explicit and zero, and the surface forcing is the same.
  The total is what catches a wrong cancellation of the generic term
  (``deep_U_set`` has ``temp_addMass`` set in the virtual-flux branch,
  ``deep_L_set`` both set in the ``convertFW2Salt = -1`` branch; ``deep``
  runs the default, where ``salt_addMass`` is 0 by inheritance and the
  salinity cancellation is the normal case).
* **Budget closure across levels.** The domain sum of the content change,
  ``sum (X^1_run - X^1_zero)*rA*drF*hFacC``, against
  ``deltaT*flux*rhoConstFresh*mass2rUnit*(X_s - X0)`` for heat, salt and the
  tracer, on every placement case, the ``multi`` one spreading the source
  over four levels.
* **Level independence of the free surface.** ``surf`` (level 1), ``deep``
  (level 5) and ``multi`` (levels 2-5) inject the same volume; ``Eta`` after
  the first step must be the same field to ``RTOL`` relative to the
  response ``Eta_surf - Eta_zero`` (``addMass`` is summed over depth into one
  ``cg2d_b`` per column, ``model/src/calc_div_ghat.F``), while the vertical
  velocity ``W`` of the target column must differ between them (the check
  is not vacuous). Later steps are **measured and reported, not asserted**:
  the different vertical profile of T and S changes the density and so the
  flow from the second step on.
* **The per-level volume bound.** ``vol_level2`` (three sources of 1e7 m^3/s
  on level 2, 10 m thick) must be refused by ``RNF_ADD_MASS``, while
  ``vol_level8`` (the same on level 8, 50 m thick) must run: the bound uses
  the target level's own thickness, which a surface-based guard would not.
* **Refusals of the route's configuration**: ``addMassFile`` set,
  ``selectAddFluid = -1``.

The ``multi`` source is built by ``MITgcmutils.runoff.targets``: a pointwise
source on the target cell, spread by ``distribute_levels`` over 12-60 m of
the zero run's own grid output, which on lab_sea's ``delZ`` must give levels
2-5 with shares 8/48, 15/48, 20/48 and 5/48 (asserted).

The build is ``build_esx_addm``: lab_sea's ``code/`` with ``ALLOW_ADDFLUID``
defined, written by :func:`write_addm_code` (``--build`` compiles it when it
is missing or stale). ``--use-build`` runs the cases on a mutant binary for a
must-fail demonstration. Exit 0 when every selected case passes, 1 when one
fails, 2 when a binary is missing or a build failed.
"""

import argparse
import json
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (ROOT, VERIF, add_to_namelist,  # noqa: E402
                           read_file, read_logs, replace_line, sparse_info)
from applied_field_check import set_namelist  # noqa: E402
from tendency_term_check import (SALT0, THETA0, TRC0, TRACER_NAME,  # noqa: E402
                                 THETA_FILE, SALT_FILE, TRC_FILE,
                                 build_if_stale, data_ptracers, param,
                                 read_mds, report_build, run_model,
                                 write_mods_code, write_state)

sys.path.insert(0, os.path.join(ROOT, "MITgcm", "utils", "python", "MITgcmutils"))

EXPERIMENT = "lab_sea"
PREFIX = "input.rnflev_"
BUILD = "build_esx_addm"
CODE = "code_rnflev_addm"
SPARSE_FILE = "runoff_level.nc"
#: Source flux of every placement case [m^3/s], as tendency_term_check's.
FLUX = 1.0e6
#: The single-level target of ``deep``.
K_DEEP = 5
#: Depth range of ``multi`` [m] and the levels and shares it must give on
#: lab_sea (delZ 10, 10, 15, 20, 20, ...: tops 0, 10, 20, 35, 55, 75).
DEPTH_RANGE = (12.0, 60.0)
MULTI_LEVELS = (2, 3, 4, 5)
MULTI_SHARES = (8.0 / 48.0, 15.0 / 48.0, 20.0 / 48.0, 5.0 / 48.0)
#: Source properties, all distinct from the initial state and from
#: tRef(K)/sRef(K) and temp_addMass/salt_addMass of the set cases.
T_SRC = 12.0
S_SRC = 5.0
C_SRC = 3.0
UNSET_RL = 1.234567e5
STEPS = 3
RTOL = 1.0e-12
#: A term below this is not a measurement [property units/s].
FLOOR = 1.0e-9
#: ``W`` of the target column must differ between surf and deep by at
#: least this share of the injection velocity flux/rA.
W_SHARE = 1.0e-3

DATA_DIAGNOSTICS = """# tests/rnf/level_check.py: one-step averages (frequency =
# deltaT) of the generalized route's diagnostics, every level, MDS,
# float64.
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
  fields(1,1) = 'RNFaddM ',
  fileName(1) = 'rnfAddM',
  frequency(1) = {dt!r},
  fileFlags(1) = 'D       ',
  fields(1,2) = 'RNFgT   ',
  fileName(2) = 'rnfGT',
  frequency(2) = {dt!r},
  fileFlags(2) = 'D       ',
  fields(1,3) = 'RNFgS   ',
  fileName(3) = 'rnfGS',
  frequency(3) = {dt!r},
  fileFlags(3) = 'D       ',
  fields(1,4) = 'RNFtr01 ',
  fileName(4) = 'rnfGC',
  frequency(4) = {dt!r},
  fileFlags(4) = 'D       ',
 &

 &DIAG_STATIS_PARMS
 &
"""

#: ``entries``: (level, fraction) of the one source on the target cell;
#: "multi" is filled in from MITgcmutils at run time. ``flux``: per source
#: [m^3/s]; ``nsrc`` sources, each carrying all the entries.
PLACEMENT = ("deep", "multi", "deep_L_set", "deep_U_set")
#: ``zero`` names the zero-flux run a case is differenced against, which
#: must share its freshwater formulation: convertFW2Salt = -1 changes the
#: surface salt forcing of every cell (it uses the local salinity), so a
#: branch-L case differenced against a branch-U zero run shows that
#: change everywhere (measured: 1.8e-4 of the term per surface cell).
CASES = (
    {"name": "zero", "entries": ((1, 1.0),), "flux": 0.0},
    {"name": "zero_L", "entries": ((1, 1.0),), "flux": 0.0,
     "convertFW2Salt": -1.0, "temp_addMass": 7.0, "salt_addMass": 10.0},
    {"name": "surf", "entries": ((1, 1.0),), "flux": FLUX},
    {"name": "deep", "entries": ((K_DEEP, 1.0),), "flux": FLUX},
    {"name": "multi", "entries": None, "flux": FLUX},
    {"name": "deep_L_set", "entries": ((K_DEEP, 1.0),), "flux": FLUX,
     "convertFW2Salt": -1.0, "temp_addMass": 7.0, "salt_addMass": 10.0,
     "zero": "zero_L"},
    {"name": "deep_U_set", "entries": ((K_DEEP, 1.0),), "flux": FLUX,
     "temp_addMass": 7.0},
    {"name": "vol_level2", "entries": ((2, 1.0),), "flux": 1.0e7, "nsrc": 3,
     "steps": 1, "stderr": "RNF_ADD_MASS: RNF: runoff out of range: cell "
                           "(i,j,k,bi,bj) ="},
    {"name": "vol_level8", "entries": ((8, 1.0),), "flux": 1.0e7, "nsrc": 3,
     "steps": 1, "normal_only": True},
    {"name": "addmassfile", "entries": ((K_DEEP, 1.0),), "flux": FLUX,
     "addMassFile": "addmass_zero.bin",
     "stderr": "RNF_CHECK: RNF_applyAsRain=.FALSE. needs addMassFile blank"},
    {"name": "select_m1", "entries": ((K_DEEP, 1.0),), "flux": FLUX,
     "selectAddFluid": -1,
     "stderr": "RNF_CHECK: RNF_applyAsRain=.FALSE. needs selectAddFluid = 1 "
               "or 2 (it is  -1)"},
)


def write_addm_code():
    """Write the mods directory of ``build_esx_addm``: lab_sea ``code/``
    with ``ALLOW_ADDFLUID`` defined (it is ``#undef`` there)."""
    path = os.path.join(VERIF, EXPERIMENT, "code", "CPP_OPTIONS.h")
    with open(path) as fh:
        text = fh.read()
    text, count = re.subn(r"(?m)^#undef ALLOW_ADDFLUID\s*$",
                          "#define ALLOW_ADDFLUID", text)
    if count != 1:
        raise ValueError(f"{path} has {count} '#undef ALLOW_ADDFLUID' lines")
    return write_mods_code(CODE, {"CPP_OPTIONS.h": text})


def write_sparse(path, cell, entries, flux, nsrc=1):
    """A schema-1.1 constant file: ``nsrc`` sources, each with the
    ``entries`` (level, fraction) on ``cell``, all with the source
    properties of this module."""
    import netCDF4
    import numpy as np
    ns, ne = nsrc, len(entries)
    with netCDF4.Dataset(path, "w") as ds:
        ds.setncatts({"mitgcm_runoff_schema_version": "1.1",
                      "mitgcm_grid_nx": np.int32(20),
                      "mitgcm_grid_ny": np.int32(16),
                      "mitgcm_time_sampling": "constant",
                      "title": "tests/rnf/level_check.py"})
        ds.createDimension("time", 1)
        ds.createDimension("source", ns)
        ds.createDimension("target", ns * ne)
        ds.createDimension("id_strlen", 8)
        time = ds.createVariable("time", "f8", ("time",))
        time.units = "days since 1979-01-01 00:00:00"
        time.calendar = "gregorian"
        time[:] = [0.0]
        ds.createVariable("source_id", "S1", ("source", "id_strlen"))[:] = \
            np.array([list(f"lev{k:05d}") for k in range(ns)], dtype="S1")
        ds.createVariable("target_source", "i4", ("target",))[:] = \
            np.repeat(np.arange(ns), ne)
        ds.createVariable("target_cell", "i4", ("target",))[:] = cell
        ds.createVariable("target_level", "i4", ("target",))[:] = \
            [lev for _ in range(ns) for lev, _f in entries]
        frac = ds.createVariable("target_fraction", "f8", ("target",))
        frac.units = "1"
        frac[:] = [f for _ in range(ns) for _lev, f in entries]
        for name, units, value in (("runoff_flux", "m3 s-1", flux),
                                   ("runoff_temperature", "degC", T_SRC),
                                   ("runoff_salinity", "g kg-1", S_SRC),
                                   (f"runoff_ptracer_{TRACER_NAME}", "1",
                                    C_SRC)):
            var = ds.createVariable(name, "f8", ("time", "source"))
            var.units = units
            var[:] = value


def write_input(case, input_dir, cell, entries):
    """The scratch input of one case; everything else comes from
    ``lab_sea/input`` through the harness."""
    base = os.path.join(VERIF, EXPERIMENT, "input")
    dt = 3600.0
    steps = case.get("steps", STEPS)
    write_sparse(os.path.join(input_dir, SPARSE_FILE), cell, entries,
                 case["flux"], case.get("nsrc", 1))
    write_state(input_dir, tracer=True)
    with open(os.path.join(base, "data")) as fh:
        data = fh.read()
    settings = [
        ("PARM03", "startTime", " startTime=0.0,"),
        ("PARM03", "endTime", f" endTime={steps*dt!r},"),
        ("PARM03", "monitorFreq", " monitorFreq=1.,"),
        ("PARM03", "pChkptFreq", " pChkptFreq=0.,"),
        ("PARM03", "dumpFreq", f" dumpFreq={dt!r},"),
        ("PARM03", "dumpInitAndLast", " dumpInitAndLast=.TRUE.,"),
        ("PARM01", "writeBinaryPrec", " writeBinaryPrec=64,"),
        ("PARM03", "outputTypesInclusive", " outputTypesInclusive=.TRUE.,"),
        ("PARM05", "hydrogThetaFile", f" hydrogThetaFile='{THETA_FILE}',"),
        ("PARM05", "hydrogSaltFile", f" hydrogSaltFile='{SALT_FILE}',"),
        # the volume only through addMass, a linear free surface, and an
        # explicit vertical diffusion so that a step is deltaT*tendency
        # (tendency_term_check.write_input measures why)
        ("PARM01", "useRealFreshWaterFlux", " useRealFreshWaterFlux=.FALSE.,"),
        ("PARM01", "implicitDiffusion", " implicitDiffusion=.FALSE.,"),
        ("PARM01", "nonlinFreeSurf", " nonlinFreeSurf=0,"),
        # the generalized route: addMass with a real volume, and the
        # T and S step after the flow it changes (config_check.F:846-854)
        ("PARM01", "selectAddFluid",
         f" selectAddFluid={case.get('selectAddFluid', 1)},"),
        ("PARM01", "staggerTimeStep", " staggerTimeStep=.TRUE.,"),
        ("PARM01", "convertFW2Salt",
         f" convertFW2Salt={case.get('convertFW2Salt', 35.0)!r},"),
        ("PARM01", "temp_addMass",
         f" temp_addMass={case.get('temp_addMass', UNSET_RL)!r},"),
        ("PARM01", "salt_addMass",
         f" salt_addMass={case.get('salt_addMass', UNSET_RL)!r},"),
    ]
    if case.get("addMassFile"):
        import numpy as np
        np.zeros((23, 16, 20), dtype=">f4").tofile(
            os.path.join(input_dir, case["addMassFile"]))
        settings.append(("PARM05", "addMassFile",
                         f" addMassFile='{case['addMassFile']}',"))
    for namelist, name, line in settings:
        data = set_namelist(data, namelist, name, line)
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)

    with open(os.path.join(base, "data.pkg")) as fh:
        pkg = fh.read()
    for name, value in (("useGMRedi", ".FALSE."), ("useKPP", ".FALSE."),
                        ("useSEAICE", ".FALSE."), ("useMNC", ".FALSE."),
                        ("useEXF", ".TRUE."), ("useCAL", ".TRUE."),
                        ("useDiagnostics", ".TRUE."), ("useRNF", ".TRUE."),
                        ("usePTRACERS", ".TRUE.")):
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
        fh.write(DATA_DIAGNOSTICS.format(dt=dt))
    with open(os.path.join(input_dir, "data.ptracers"), "w") as fh:
        fh.write(data_ptracers(None))
    with open(os.path.join(input_dir, "data.longstep"), "w") as fh:
        fh.write(" &LONGSTEP_PARM01\n  LS_nIter = 1,\n"
                 "  LS_whenToSample = 0,\n &\n")
    # The generalized route is the default: data.rnf does not name it
    with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
        fh.write("# Written by tests/rnf/level_check.py: the generalized\n"
                 "# route, RNF_applyAsRain left at its default .FALSE.\n"
                 " &RNF_PARM01\n"
                 f"  RNF_file = '{SPARSE_FILE}',\n"
                 " &\n")
    return dt


def multi_entries(zero_dir, cell):
    """The ``multi`` entries, from MITgcmutils on the zero run's grid."""
    import numpy as np
    from MITgcmutils.runoff.targets import build_targets, distribute_levels
    xc, _ = read_mds(zero_dir, "XC")
    yc, _ = read_mds(zero_dir, "YC")
    t = build_targets([{"source_id": "multi", "lon": float(xc[cell]),
                        "lat": float(yc[cell])}], zero_dir)
    d = distribute_levels(t, zero_dir, {"multi": DEPTH_RANGE})
    if d.target_cell.tolist() != [cell] * len(MULTI_LEVELS):
        raise ValueError(f"multi: targets on cells {d.target_cell.tolist()}")
    if d.target_level.tolist() != list(MULTI_LEVELS):
        raise ValueError(f"multi: levels {d.target_level.tolist()}, "
                         f"expected {list(MULTI_LEVELS)}")
    if not np.allclose(d.target_fraction, MULTI_SHARES, rtol=0, atol=1e-15):
        raise ValueError(f"multi: shares {d.target_fraction.tolist()}")
    return tuple(zip(d.target_level.tolist(), d.target_fraction.tolist()))


def field(run_dir, base):
    import numpy as np
    values, sizes = read_mds(run_dir, base)
    return np.asarray(values), sizes


def rel(a, b):
    scale = max(abs(a), abs(b))
    return 0.0 if scale == 0.0 else abs(a - b) / scale


def judge_placement(case, run_dir, zero_dir, cell, entries, dt, text):
    """Placement, totals and budget of one case; returns (problems, figures)."""
    import numpy as np
    problems, figs = [], {}
    rho_c = param(text, "rhoConst")
    rho_f = param(text, "rhoConstFresh")
    mass2r = 1.0 / rho_c
    rac, _ = field(run_dir, "RAC")
    drf, _ = field(run_dir, "DRF")
    hfac, sizes = field(run_dir, "hFacC")
    nx, ny, nr = sizes[0], sizes[1], sizes[2]
    plane = nx * ny
    area = float(rac[cell])

    def idx(k):
        return cell + plane * (k - 1)

    flux = case["flux"]
    levels = {lev: f for lev, f in entries}
    # diagnostics: averages over the first step
    addm, _ = field(run_dir, "rnfAddM.0000000001")
    for lev in range(1, nr + 1):
        want = rho_f * flux * levels.get(lev, 0.0)
        got = float(addm[idx(lev)])
        if lev in levels:
            figs[f"RNFaddM k={lev}"] = rel(got, want)
            if not rel(got, want) <= RTOL:
                problems.append(f"RNFaddM at level {lev}: {got!r}, "
                                f"expected {want!r}")
        elif got != 0.0:
            problems.append(f"RNFaddM at level {lev} (no entry): {got!r}")
    others = np.delete(addm, [idx(lev) for lev in levels])
    if np.any(others != 0.0):
        problems.append(f"RNFaddM: {int(np.count_nonzero(others))} other "
                        f"cell(s) not 0")

    state = {}
    for name, label in (("T", "T"), ("S", "S"), ("C", "PTRACER01")):
        x0, _ = field(run_dir, f"{label}.0000000000")
        x1, _ = field(run_dir, f"{label}.0000000001")
        z0, _ = field(zero_dir, f"{label}.0000000000")
        z1, _ = field(zero_dir, f"{label}.0000000001")
        if np.any(x0 != z0):
            problems.append(f"{name}: the two runs do not start in the same "
                            f"state")
        state[name] = ((x1 - x0) - (z1 - z0), x0)

    vol = rac[None, :].repeat(nr, 0).ravel() * np.repeat(drf, plane) * hfac
    for name, diag, src, x0 in (("T", "rnfGT", T_SRC, THETA0),
                                ("S", "rnfGS", S_SRC, SALT0),
                                ("C", "rnfGC", C_SRC, TRC0)):
        dx, start = state[name]
        g, _ = field(run_dir, f"{diag}.0000000001")
        biggest = 0.0
        for lev in range(1, nr + 1):
            f = levels.get(lev, 0.0)
            m = rho_f * flux * f / area
            want = m * (src - x0) * mass2r / (drf[lev - 1] * hfac[idx(lev)]) \
                if f else 0.0
            if f:
                if not abs(want) > FLOOR:
                    problems.append(f"{name} term at level {lev} is "
                                    f"{want!r}: not a measurement")
                if float(start[idx(lev)]) != x0:
                    problems.append(f"{name}^0 at level {lev} is "
                                    f"{float(start[idx(lev)])!r}, not {x0!r}")
                figs[f"diag {name} k={lev}"] = rel(float(g[idx(lev)]), want)
                figs[f"total {name} k={lev}"] = rel(float(dx[idx(lev)]),
                                                    dt * want)
                if not figs[f"diag {name} k={lev}"] <= RTOL:
                    problems.append(f"diag {name} at level {lev}: "
                                    f"{float(g[idx(lev)])!r}, expected "
                                    f"{want!r}")
                if not figs[f"total {name} k={lev}"] <= RTOL:
                    problems.append(f"total {name} at level {lev}: "
                                    f"{float(dx[idx(lev)])!r}, expected "
                                    f"{dt*want!r}")
                biggest = max(biggest, abs(dt * want))
        mask = np.ones(dx.size, bool)
        mask[[idx(lev) for lev in levels]] = False
        if np.any(g[mask] != 0.0):
            problems.append(f"diag {name}: {int(np.count_nonzero(g[mask]))} "
                            f"other cell(s) not 0")
        stray = float(np.max(np.abs(dx[mask]))) if mask.any() else 0.0
        figs[f"stray {name}"] = stray / biggest if biggest else None
        if not stray <= RTOL * biggest:
            problems.append(f"total {name}: largest change off the target "
                            f"levels {stray!r} against {biggest!r}")
        content = math.fsum((dx * vol).tolist())
        want = dt * flux * rho_f * mass2r * (src - x0)
        figs[f"budget {name}"] = rel(content, want)
        if not rel(content, want) <= RTOL:
            problems.append(f"budget {name}: content change {content!r}, "
                            f"expected {want!r}")
    return problems, figs


def judge_levels(dirs, cell, flux):
    """Level independence of the first-step free surface; later steps
    measured. ``dirs``: case name -> run dir (zero, surf, deep, multi)."""
    import numpy as np
    problems, figs = [], {}
    zero = dirs["zero"]
    eta = {n: field(d, "Eta.0000000001")[0] for n, d in dirs.items()}
    resp = float(np.max(np.abs(eta["surf"] - eta["zero"])))
    if not resp > 0.0:
        problems.append("Eta: the surf run does not differ from the zero run")
        return problems, figs
    for name in ("deep", "multi"):
        if name not in eta:
            continue
        d = float(np.max(np.abs(eta[name] - eta["surf"])))
        figs[f"Eta step 1 {name}"] = d / resp
        if not d <= RTOL * resp:
            problems.append(f"Eta after step 1, {name} vs surf: {d!r} "
                            f"against a response of {resp!r}")
    rac, _ = field(zero, "RAC")
    area = float(rac[cell])
    w_s, sizes = field(dirs["surf"], "W.0000000001")
    w_d, _ = field(dirs["deep"], "W.0000000001")
    plane = sizes[0] * sizes[1]
    col = [cell + plane * k for k in range(sizes[2])]
    dw = float(np.max(np.abs(w_d[col] - w_s[col])))
    figs["W column deep vs surf / (flux/rA)"] = dw / (flux / area)
    if not dw >= W_SHARE * flux / area:
        problems.append(f"W of the target column: deep and surf differ by "
                        f"{dw!r}, under {W_SHARE} of flux/rA")
    # measured, not asserted: what the later steps do
    for step in range(2, STEPS + 1):
        label = f"{step:010d}"
        e = {n: field(d, f"Eta.{label}")[0] for n, d in dirs.items()}
        r = float(np.max(np.abs(e["surf"] - e["zero"])))
        for name in ("deep", "multi"):
            if name in e:
                figs[f"Eta step {step} {name} (measured)"] = \
                    float(np.max(np.abs(e[name] - e["surf"]))) / r
        vol = {n: math.fsum(((e[n] - e["zero"]) * rac).tolist())
               for n in e if n != "zero"}
        for name in ("deep", "multi"):
            if name in vol:
                figs[f"volume step {step} {name} (measured)"] = \
                    rel(vol[name], vol["surf"])
    return problems, figs


def run_case(case, build, args, cell, entries):
    name = PREFIX + case["name"]
    input_dir = os.path.join(VERIF, EXPERIMENT, name)
    shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir)
    dt = write_input(case, input_dir, cell, entries)
    run_dir, status, timed_out = run_model(name, build, args.timeout)
    return run_dir, status, timed_out, input_dir, dt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", action="append", default=None)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json", help="write the measurements here")
    parser.add_argument("--build", action="store_true",
                        help="compile build_esx_addm when missing or stale")
    parser.add_argument("--use-build", default=None, metavar="NAME",
                        help="run on this build (a mutant) instead")
    args = parser.parse_args(argv)
    if args.use_build and args.build:
        parser.error("--use-build does not combine with --build")
    names = [c["name"] for c in CASES]
    wanted = args.case or names
    unknown = sorted(set(wanted) - set(names))
    if unknown:
        print("no such case: " + ", ".join(unknown))
        return 2
    build = args.use_build or BUILD
    if args.build and not report_build(
            build_if_stale(BUILD, write_addm_code, timeout=args.timeout * 2)):
        return 2
    if not os.path.isfile(os.path.join(VERIF, EXPERIMENT, build, "mitgcmuv")):
        print(f"MISSING: no binary {build}; rerun with --build")
        return 2
    cell = sparse_info()["wet_cell"]
    # the zero run is needed by every judged case and by "multi"
    by_name = {c["name"]: c for c in CASES}
    needed = set(wanted) | {"zero"} | {by_name[n].get("zero", "zero")
                                      for n in wanted}
    order = ["zero"] + [n for n in names if n != "zero" and n in needed]
    dirs, results, inputs = {}, [], []
    for n in order:
        case = by_name[n]
        entries = case["entries"]
        if n == "multi":
            entries = multi_entries(dirs["zero"], cell)
            print(f"MULTI levels/shares from MITgcmutils: {entries}")
        run_dir, status, timed_out, input_dir, dt = run_case(
            case, build, args, cell, entries)
        inputs.append(input_dir)
        text = read_logs(run_dir)
        res = {"name": n, "problems": [], "figures": {}}
        if "stderr" in case:
            ok = status != 0 and case["stderr"] in text \
                and "Execution ended Normally" not in text
            if not ok:
                res["problems"].append(f"expected a stop with {case['stderr']!r}"
                                       f" (exit {status})")
        else:
            if status != 0 or timed_out or \
                    "Execution ended Normally" not in text:
                res["problems"].append(f"run did not end normally (exit "
                                       f"{status}{', timed out' if timed_out else ''})")
            elif n in PLACEMENT:
                p, f = judge_placement(case, run_dir,
                                       dirs[case.get("zero", "zero")], cell,
                                       entries, dt, text)
                res["problems"] += p
                res["figures"].update(f)
        dirs[n] = run_dir
        if n in wanted:
            results.append(res)
    if all(k in dirs for k in ("zero", "surf", "deep")):
        p, f = judge_levels({k: dirs[k] for k in ("zero", "surf", "deep",
                                                  "multi") if k in dirs},
                            cell, FLUX)
        results.append({"name": "level_independence", "problems": p,
                        "figures": f})
    for res in results:
        verdict = "PASS" if not res["problems"] else "FAIL"
        resid = [v for k, v in res["figures"].items()
                 if v is not None and "measured" not in k and "W " not in k]
        print(f"{verdict} {res['name']}"
              + (f": largest relative residual {max(resid):.2e}"
                 if resid else ""))
        for k, v in res["figures"].items():
            if v is not None and ("measured" in k or "W " in k):
                print(f"     {k}: {v:.3e}")
        for problem in res["problems"]:
            print(f"     {problem}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=1, default=str)
    if not args.keep:
        for d in inputs:
            shutil.rmtree(d, ignore_errors=True)
    return 1 if any(r["problems"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
