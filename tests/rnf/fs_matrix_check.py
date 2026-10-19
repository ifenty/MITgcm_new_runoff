"""Generalized runoff route over the freshwater and free-surface axis (RUNOFF-014, part 1).

What this checks
================

``tests/rnf/level_check.py`` (RUNOFF-046) runs the generalized route
(``RNF_applyAsRain = .FALSE.``) in one formulation. That formulation is a
linear free surface with ``useRealFreshWaterFlux = .FALSE.``. Its
``write_input`` sets both. The lab_sea file ``input/data`` sets neither, so
the model default is the same.

This module runs the same kind of oracle on eight lab_sea configurations.
Each has one source in one column, ``selectAddFluid = 1`` and
``staggerTimeStep``:

* ``lin_virt``: linear free surface, virtual salt flux (branch U).
* ``lin_real``: linear free surface, real flux, ``convertFW2Salt = -1``
  (branch L).
* ``nl0_virt`` and ``nl0_real``: ``nonlinFreeSurf = 4``, ``select_rStar = 0``.
* ``nl1_virt`` and ``nl1_real``: the same with ``select_rStar = 1`` (z*).
* ``nl2_virt`` and ``nl2_real``: the same with ``select_rStar = 2`` (r*).

The branch letters are those of ``docs/package_design.md`` decision 3.
Branch N needs a real flux and a nonlinear free surface. So only the
``nl*_real`` configurations are branch N. The ``nl*_virt`` configurations
have a nonlinear grid and a virtual salt flux. They use the
``nonlinFreeSurf > 0`` test of the generic ``addMass`` term
(``apply_forcing.F:506``).

Which combinations the model accepts
====================================

All eight run. The model refuses three nearby combinations. ``--probes`` runs
them and prints the model message:

* ``nonlinFreeSurf = 4`` on a binary without ``NONLIN_FRSURF``. The message
  is ``CONFIG_CHECK: #undef NONLIN_FRSURF and nonlinFreeSurf is non-zero``.
* ``nonlinFreeSurf = 4`` without ``exactConserv``. The message is
  ``CONFIG_CHECK: nonlinFreeSurf cannot be used without exactConserv``.
* A real flux with ``nonlinFreeSurf = 4`` and ``LS_whenToSample = 0``. The
  message is ``LONGSTEP: staggerTimeStep with useRealFreshWaterFlux and
  nonlinFreeSurf or PCoords requires LS_whenToSample=2``.

``level_check`` writes ``data.longstep`` with 0. This module writes 2 for
every nonlinear configuration. With a virtual salt flux the model accepts 0.
But then the passive tracer takes its step before the model knows the free
surface of the step. It misses the thickness rescale. Measured on the source
cell: the state change was ``deltaT*g`` and not ``deltaT*g*h0/h1``. The
difference is 4.5e-5 relative.

Oracles
=======

Each configuration runs the cases ``zero``, ``surf``, ``deep``, ``deep_set``
and ``multi`` for 24 steps with a source of 2e5 m^3/s.

* **First step, linear grids.** The module imports
  ``level_check.judge_placement``.
* **First step, nonlinear grids** (:func:`judge_step1_nlfs`). ``RNFaddM`` and
  the three tendency diagnostics follow ``level_check``. The state change
  differs, because the cell thickness changes in the step. The model update
  is ``dX = deltaT*g*h0/h1``. Here ``h1`` is the thickness at the end of the
  step. So the run minus the zero run is ``(Xz1 - X0)*(h1z/h1r - 1)`` in
  every ocean cell. At a target level it also has the term
  ``deltaT*m*(Xs - X0)*mass2r/(drF*h1r)``. The thicknesses are the model
  ``hFactorC`` diagnostic. Its one-step average file ``n+1`` is the thickness
  of state ``n``. File 1 is the static ``hFacC``. The cell-wise residual
  against the largest term is allowed up to 1e-12 and measured at 5.2e-13.
* **Content.** The content is ``sum X*hFacC*drF*rA`` with the dynamic
  ``hFacC``. On a linear grid it adds ``Eta*rA`` with the level-1 value. At
  step 1 the run minus the zero run must equal
  ``X0*(Vr - Vz) + Vinj*(Xs - X0)``. The noise is the larger of two values.
  One is the residual of a 1 m^3/s run. The other is ``eps*(|Cr| + |Cz|)``,
  the storage round-off of the two states. A residual passes up to
  ``NOISE_FACTOR`` = 20 times the noise. The largest measured residual is
  0.19 of the noise and 1.4e-9 of the injected amount.
* **Definition proved on the zero run** (:func:`judge_zero`). The volume
  change of the zero run must equal ``deltaT*sum(oceFWflx*rA)/rhoConst``.
  The measured difference is at most 7.4e-17 of the volume. With a virtual salt flux
  the volume does not change. The salt content change must equal
  ``deltaT*sum(SFLUX*rA)/rhoConst``. On a nonlinear grid the difference is
  6e-13 to 1.2e-11 of the content. ``TOL_ZERO_S`` is 1e-10. On a linear grid
  with a real flux the same closure is 1.0e-6, with no runoff in the run. The
  model does not conserve the salt of that grid with the free-surface layer
  included. So no multi-step salt or tracer budget is asserted on a linear
  grid.
* **Volume budget over 24 steps** (:func:`closure`). The change of volume,
  minus the surface part from ``oceFWflx`` in the real case, must equal
  ``n*deltaT*flux*rhoConstFresh/rhoConst``. The tolerance is 23 m^3. It is 20
  times the largest of the zero-run residual, ``eps*V`` and 1e-3 m^3. The
  injected volume is 1.7e10 m^3. The largest measured residual is 0.64 m^3.
* **Salt, heat and tracer over 24 steps: reported, not asserted.** After
  step 1 the content does not follow the injected amount. The residuals are
  between 2e-4 and 3e-2 of the injected amount. The cause is the model and
  not the package. :func:`native_run` replaces the runoff file by the model
  ``addMass`` file. On the nonlinear grids the two runs then give the same
  ``T``, ``S`` and ``Eta`` at step 24, bit for bit. The module asserts this
  equality (``TOL_NATIVE``).
* **Must-fail.** The option ``--use-nlfs-build build_esx_nlfs_addm_mut`` runs
  the nonlinear configurations on a mutant binary. In
  ``rnf_tendency_apply.F`` the mutant does not cancel the generic
  ``temp_addMass`` term when ``nonlinFreeSurf > 0``
  (:func:`write_mutant_code`). The case ``deep_set`` fails in all six
  configurations. There ``temp_addMass`` is 7 and ``THETA0`` is 2. The
  cell-wise error is 0.5 of the term. The heat content is wrong by 0.4 of the
  injected heat. The case ``deep`` passes, as it must, because it sets no
  ``temp_addMass``.

Builds
======

``build_esx_nlfs_addm`` is the lab_sea ``code/`` with ``ALLOW_ADDFLUID`` and
``NONLIN_FRSURF``. Its code directory is ``code_rnffs_nlfs_addm``. The
linear configurations use ``build_esx_addm`` of ``level_check``. The option
``--build`` compiles what is missing or stale. The exit code is 0 when every
selected configuration passes, 1 when one fails and 2 when a binary is
missing.

Not covered
===========

The module does not cover cs32 or any other grid. It does not cover more
than one source. It does not cover sea ice. It does not cover
``staggerTimeStep = .FALSE.``, because the model refuses
``selectAddFluid >= 1`` without it. It does not close the multi-step salt,
heat and tracer budgets to round-off, because the model ``addMass`` does not
close them either.
"""
import argparse
import json
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import level_check as lc  # noqa: E402
from applied_field_check import set_namelist  # noqa: E402
from restart_check import sync_cpp  # noqa: E402
from refusal_check import VERIF, read_logs, sparse_info  # noqa: E402
from tendency_term_check import (SALT0, THETA0, TRC0, build_if_stale,  # noqa: E402
                                 param, read_mds, report_build, run_model,
                                 write_mods_code)

EXPERIMENT = lc.EXPERIMENT
PREFIX = "input.rnffs_"
NLFS_BUILD = "build_esx_nlfs_addm"
NLFS_CODE = "code_rnffs_nlfs_addm"
NSTEPS = 24
FS_FLUX = 2.0e5

CONFIGS = {
    "lin_virt": dict(build=lc.BUILD, real=False, nl=0, rstar=0),
    "lin_real": dict(build=lc.BUILD, real=True, nl=0, rstar=0),
    "nl0_virt": dict(build=NLFS_BUILD, real=False, nl=4, rstar=0),
    "nl0_real": dict(build=NLFS_BUILD, real=True, nl=4, rstar=0),
    "nl1_virt": dict(build=NLFS_BUILD, real=False, nl=4, rstar=1),
    "nl1_real": dict(build=NLFS_BUILD, real=True, nl=4, rstar=1),
    "nl2_virt": dict(build=NLFS_BUILD, real=False, nl=4, rstar=2),
    "nl2_real": dict(build=NLFS_BUILD, real=True, nl=4, rstar=2),
}

CASES = (
    {"name": "zero", "entries": ((1, 1.0),), "flux": 0.0},
    {"name": "surf", "entries": ((1, 1.0),), "flux": FS_FLUX},
    {"name": "deep", "entries": ((lc.K_DEEP, 1.0),), "flux": FS_FLUX},
    {"name": "deep_set", "entries": ((lc.K_DEEP, 1.0),), "flux": FS_FLUX,
     "temp_addMass": 7.0, "salt_addMass": 10.0},
    {"name": "multi", "entries": None, "flux": FS_FLUX},
)


def write_nlfs_addm_code():
    path = os.path.join(VERIF, EXPERIMENT, "code", "CPP_OPTIONS.h")
    with open(path) as fh:
        text = fh.read()
    text, count = re.subn(r"(?m)^#undef ALLOW_ADDFLUID\s*$",
                          "#define ALLOW_ADDFLUID", text)
    if count != 1:
        raise ValueError(f"{path} has {count} '#undef ALLOW_ADDFLUID' lines")
    return write_mods_code(NLFS_CODE, {"CPP_OPTIONS.h": sync_cpp(text)})


def prepare(cfg_name, case, cell, entries, steps, out_ab=False):
    cfg = CONFIGS[cfg_name]
    name = f"{PREFIX}{cfg_name}_{case['name']}{'_ab' if out_ab else ''}"
    input_dir = os.path.join(VERIF, EXPERIMENT, name)
    shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir)
    c = dict(case, steps=steps,
             convertFW2Salt=(-1.0 if cfg["real"] else 35.0))
    dt = lc.write_input(c, input_dir, cell, entries)
    path = os.path.join(input_dir, "data")
    with open(path) as fh:
        data = fh.read()
    lines = [("useRealFreshWaterFlux",
              " useRealFreshWaterFlux=.%s.," % ("TRUE" if cfg["real"] else "FALSE")),
             ("nonlinFreeSurf", f" nonlinFreeSurf={cfg['nl']},")]
    if cfg["nl"]:
        lines += [("exactConserv", " exactConserv=.TRUE.,"),
                  ("select_rStar", f" select_rStar={cfg['rstar']},"),
                  ("hFacInf", " hFacInf=0.2,"), ("hFacSup", " hFacSup=2.0,")]
    for key, line in lines:
        data = set_namelist(data, "PARM01", key, line)
    if out_ab:
        data = set_namelist(data, "PARM03", "tracForcingOutAB",
                            " tracForcingOutAB=1,")
    with open(path, "w") as fh:
        fh.write(data)
    if cfg["nl"]:
        # LONGSTEP_INIT_FIXED refuses staggerTimeStep + useRealFreshWaterFlux
        # + nonlinFreeSurf with LS_whenToSample = 0 (level_check's value).
        # With a virtual salt flux the model accepts 0, but then the
        # passive tracer is stepped before the free surface of the step is
        # known and misses the thickness rescale (measured, RUNOFF-014),
        # so 2 is used for every nonlinear configuration.
        lpath = os.path.join(input_dir, "data.longstep")
        with open(lpath) as fh:
            ls = fh.read()
        with open(lpath, "w") as fh:
            fh.write(ls.replace("LS_whenToSample = 0", "LS_whenToSample = 2"))
    dpath = os.path.join(input_dir, "data.diagnostics")
    with open(dpath) as fh:
        diag = fh.read()
    names = ([("hFactorC", "hfacAvg")] if cfg["nl"] else []) + [
        ("oceFWflx", "fwFlux"), ("SFLUX   ", "sFlux"), ("TFLUX   ", "tFlux")]
    extra = "  fileFlags(4) = 'D       ',\n"
    for num, (field_name, fname) in enumerate(names, start=5):
        extra += (f"  fields(1,{num}) = '{field_name:8s}',\n"
                  f"  fileName({num}) = '{fname}',\n"
                  f"  frequency({num}) = {dt!r},\n"
                  f"  fileFlags({num}) = 'D       ',\n")
    diag = diag.replace("  fileFlags(4) = 'D       ',\n", extra)
    with open(dpath, "w") as fh:
        fh.write(diag)
    return name, input_dir, dt


# ---------------------------------------------------------------- content
def geometry(rd):
    """Static grid of a run: area, layer thickness, static hFacC, mask."""
    import numpy as np
    rac, _ = lc.field(rd, "RAC")
    drf, _ = lc.field(rd, "DRF")
    hf0, sizes = lc.field(rd, "hFacC")
    nx, ny, nr = sizes[0], sizes[1], sizes[2]
    plane = nx * ny
    vol3 = np.tile(rac, nr) * np.repeat(drf, plane)
    return dict(rac=rac, drf=drf, hf0=hf0, plane=plane, nr=nr, vol3=vol3,
                mask=hf0 > 0.0)


def thickness(cfg, rd, g, n):
    """The model's own hFacC at the END of step ``n`` (state ``n``).

    NLFS: the ``hFactorC`` diagnostic. Its one-step average file ``n+1``
    holds the value filled during step ``n+1``, i.e. before that step
    updates it, so it is the thickness belonging to the state after step
    ``n`` (measured: file 1 is the static ``hFacC``; file 2 equals
    ``h0FacC*(1+Eta^1/H)``). Linear: the static ``hFacC``.
    """
    if not cfg["nl"]:
        return g["hf0"]
    return lc.field(rd, "hfacAvg.%010d" % (n + 1))[0]


def content(cfg, rd, g, n, label):
    """``sum X*hFacC*drF*rA`` of state ``n`` with the dynamic hFacC; for the
    linear free surface plus the free-surface layer, ``Eta*rA`` of volume
    carrying the level-1 value."""
    import numpy as np
    x = lc.field(rd, "%s.%010d" % (label, n))[0]
    h = thickness(cfg, rd, g, n)
    total = math.fsum((x * h * g["vol3"]).tolist())
    if not cfg["nl"]:
        eta = lc.field(rd, "Eta.%010d" % n)[0]
        total += math.fsum((eta * g["rac"] * x[:g["plane"]]).tolist())
    return total


def volume(cfg, rd, g, n):
    h = thickness(cfg, rd, g, n)
    total = math.fsum((h * g["vol3"]).tolist())
    if not cfg["nl"]:
        eta = lc.field(rd, "Eta.%010d" % n)[0]
        total += math.fsum((eta * g["rac"]).tolist())
    return total


def summed(rd, base, g, first, last):
    """Sum over the steps first..last of the sum over cells of a 2-D
    one-step-average diagnostic times rA."""
    total = 0.0
    for it in range(first, last + 1):
        f = lc.field(rd, "%s.%010d" % (base, it))[0]
        total += math.fsum((f * g["rac"]).tolist())
    return total


def judge_zero(cfg, rd, g, n, dt, text):
    """Definition of the content, proved on the zero-flux run.

    Volume: ``V(n) - V(0)`` against ``deltaT * mass2r * sum oceFWflx*rA``
    (real freshwater flux; with a virtual salt flux the volume must not
    change in the nonlinear case). Salt: ``S`` content change against
    ``deltaT * sum SFLUX*rA / rhoConst``. Returns (problems, figures)."""
    rho_c = param(text, "rhoConst")
    cp = param(text, "HeatCapacity_Cp")
    figs = {}
    v0, vn = volume(cfg, rd, g, 0), volume(cfg, rd, g, n)
    fw = summed(rd, "fwFlux", g, 1, n)
    pred_v = dt * fw / rho_c
    figs["V change"] = vn - v0
    figs["V pred (oceFWflx)"] = pred_v
    figs["V total"] = v0
    s0, sn = content(cfg, rd, g, 0, "S"), content(cfg, rd, g, n, "S")
    pred_s = dt * summed(rd, "sFlux", g, 1, n) / rho_c
    figs["S change"] = sn - s0
    figs["S pred (SFLUX)"] = pred_s
    figs["S total"] = s0
    t0, tn = content(cfg, rd, g, 0, "T"), content(cfg, rd, g, n, "T")
    pred_t = dt * summed(rd, "tFlux", g, 1, n) / (rho_c * cp)
    figs["T change"] = tn - t0
    figs["T pred (TFLUX)"] = pred_t
    figs["T total"] = t0
    return figs


#: The cell-wise state change, against the largest term of the case.
TOL_CELL = 1.0e-12
EPS = 2.220446049250313e-16
#: Multiplier on a measured noise: a residual is accepted up to 20 times it.
NOISE_FACTOR = 20.0

SOURCE = {"T": ("T", lc.T_SRC, THETA0), "S": ("S", lc.S_SRC, SALT0),
          "C": ("PTRACER01", lc.C_SRC, TRC0)}


def judge_step1_nlfs(cfg, case, rd, zd, g, cell, entries, dt, text,
                     noise=None):
    """First-step placement of the generalized route on the NLFS grid.

    ``RNFaddM`` and the three tendency diagnostics are the ones of
    ``level_check`` (the tendency uses the thickness of the START of the
    step, which is the static ``hFacC`` at iteration 0). The state change
    differs from ``level_check``'s because the cell thickness changes in
    the step: with the same tendency ``g`` in the run and the zero run
    (uniform start state, same surface forcing, no advection of a uniform
    field) the model's update is ``dX = deltaT * g * h0 / h1`` with ``h1``
    the thickness at the end of the step, so
    ``(dX_run - dX_zero)(cell) = (Xz1 - X0)*(h1z/h1r - 1)`` in every
    ocean cell plus, at a target level, ``deltaT*m*(Xs - X0)*mass2r /
    (drF*h1r)``. The thicknesses are the model's own (``hFactorC``).
    Content: ``sum (Xr1*h1r - Xz1*h1z)*drF*rA`` against
    ``X0*(Vr - Vz) + Vinj*(Xs - X0)``; volume ``Vr - Vz`` against ``Vinj``.
    """
    import numpy as np
    problems, figs = [], {}
    rho_c, rho_f = param(text, "rhoConst"), param(text, "rhoConstFresh")
    mass2r = 1.0 / rho_c
    plane, nr = g["plane"], g["nr"]
    area = float(g["rac"][cell])
    flux = case["flux"]
    levels = {lev: fr for lev, fr in entries}
    mask = g["mask"]

    def idx(k):
        return cell + plane * (k - 1)

    addm, _ = lc.field(rd, "rnfAddM.0000000001")
    for lev in range(1, nr + 1):
        want = rho_f * flux * levels.get(lev, 0.0)
        got = float(addm[idx(lev)])
        if lev in levels:
            figs[f"RNFaddM k={lev}"] = lc.rel(got, want)
            if not lc.rel(got, want) <= lc.RTOL:
                problems.append(f"RNFaddM at level {lev}: {got!r}, "
                                f"expected {want!r}")
        elif got != 0.0:
            problems.append(f"RNFaddM at level {lev} (no entry): {got!r}")
    if np.any(np.delete(addm, [idx(lev) for lev in levels]) != 0.0):
        problems.append("RNFaddM: another cell not 0")

    h0 = thickness(cfg, rd, g, 0)
    if np.any(h0 != g["hf0"]):
        problems.append("hFactorC at the start of step 1 is not the static "
                        "hFacC")
    h1r, h1z = thickness(cfg, rd, g, 1), thickness(cfg, zd, g, 1)
    v_inj = dt * flux * rho_f * mass2r
    dvol = math.fsum(((h1r - h1z) * g["vol3"]).tolist())
    figs["volume step 1"] = lc.rel(dvol, v_inj) if v_inj else None
    figs["_volume_abs"] = dvol - v_inj
    ratio = np.ones_like(h1r)
    ratio[mask] = h1z[mask] / h1r[mask]
    for name, (label, src, x0) in SOURCE.items():
        a0 = lc.field(rd, f"{label}.0000000000")[0]
        a1 = lc.field(rd, f"{label}.0000000001")[0]
        z0 = lc.field(zd, f"{label}.0000000000")[0]
        z1 = lc.field(zd, f"{label}.0000000001")[0]
        if np.any(a0 != z0) or np.any(a0[mask] != x0):
            problems.append(f"{name}: the start state is not the uniform one")
        diag = {"T": "rnfGT", "S": "rnfGS", "C": "rnfGC"}[name]
        gt = lc.field(rd, f"{diag}.0000000001")[0]
        pred = np.zeros_like(a1)
        pred[mask] = (z1[mask] - x0) * (ratio[mask] - 1.0)
        biggest = 0.0
        for lev, fr in levels.items():
            m = rho_f * flux * fr / area
            term0 = m * (src - x0) * mass2r / (g["drf"][lev - 1]
                                               * g["hf0"][idx(lev)])
            if not abs(term0) > lc.FLOOR:
                problems.append(f"{name} term at level {lev} is {term0!r}")
            figs[f"diag {name} k={lev}"] = lc.rel(float(gt[idx(lev)]), term0)
            if not figs[f"diag {name} k={lev}"] <= lc.RTOL:
                problems.append(f"diag {name} at level {lev}: "
                                f"{float(gt[idx(lev)])!r}, expected {term0!r}")
            add = dt * m * (src - x0) * mass2r / (g["drf"][lev - 1]
                                                   * h1r[idx(lev)])
            pred[idx(lev)] += add
            biggest = max(biggest, abs(add))
        othr = np.ones(gt.size, bool)
        othr[[idx(lev) for lev in levels]] = False
        if np.any(gt[othr] != 0.0):
            problems.append(f"diag {name}: another cell not 0")
        dx = (a1 - a0) - (z1 - z0)
        worst = float(np.max(np.abs(dx - pred)))
        figs[f"total {name} (cell-wise, vs biggest)"] = worst / biggest
        if not worst <= TOL_CELL * biggest:
            problems.append(f"total {name}: largest cell difference "
                            f"{worst!r} against {biggest!r}")
        figs[f"_stray {name} (run-zero, vs biggest)"] = \
            float(np.max(np.abs(dx[othr]))) / biggest
        cdiff = (content(cfg, rd, g, 1, label) - content(cfg, zd, g, 1, label))
        want = x0 * dvol + v_inj * (src - x0)
        figs[f"_budget {name} step 1 abs"] = abs(cdiff - want)
        figs[f"budget {name} step 1"] = abs(cdiff - want) / (abs(v_inj * src))
        # noise: the larger of the measured one (the 1 m^3/s run) and the
        # storage round-off of the two states, eps*(|Cr| + |Cz|)
        crz = abs(content(cfg, rd, g, 1, label)) + abs(content(cfg, zd, g, 1,
                                                                label))
        floor = max(noise[name] if noise else 0.0, EPS * crz)
        figs[f"_budget {name} step 1 noise"] = floor
        if noise is not None and not abs(cdiff - want) <= NOISE_FACTOR * floor:
            problems.append(f"budget {name} step 1: {cdiff!r} against {want!r}"
                            f" (noise {floor!r})")
    return problems, figs


def closure(cfg, rd, g, n, dt, flux, text):
    """Closure of one run over ``n`` steps, against the model's own surface
    diagnostics: ``C(n) - C(0) - [surface part] - n*Vinj*Xs`` in the units of
    the content, for the volume (real freshwater flux: ``oceFWflx``), salt
    (``SFLUX``), heat (``TFLUX``) and the tracer (no surface flux).
    ``Vinj = deltaT*flux*rhoConstFresh/rhoConst``. Returns a dict with the
    residual, the injected amount and the content."""
    rho_c, rho_f = param(text, "rhoConst"), param(text, "rhoConstFresh")
    cp = param(text, "HeatCapacity_Cp")
    v_inj = n * dt * flux * rho_f / rho_c
    out = {}
    d_v = volume(cfg, rd, g, n) - volume(cfg, rd, g, 0)
    fw = dt * summed(rd, "fwFlux", g, 1, n) / rho_c if cfg["real"] else 0.0
    out["V"] = dict(res=d_v - fw - v_inj, inj=v_inj, tot=volume(cfg, rd, g, 0))
    for name, (label, src, x0) in SOURCE.items():
        c0, cn = content(cfg, rd, g, 0, label), content(cfg, rd, g, n, label)
        surf = {"T": dt * summed(rd, "tFlux", g, 1, n) / (rho_c * cp),
                "S": dt * summed(rd, "sFlux", g, 1, n) / rho_c,
                "C": 0.0}[name]
        out[name] = dict(res=cn - c0 - surf - v_inj * src,
                         inj=abs(v_inj * src), tot=c0)
    return out




# ---------------------------------------------------------------- mutant
MUTANT_BUILD = "build_esx_nlfs_addm_mut"
MUTANT_CODE = "code_rnffs_nlfs_addm_mut"
#: The cancellation of the model's generic ``temp_addMass`` term on the
#: runoff share is left out when the free surface is nonlinear (``gLoc``
#: is cleared before it is subtracted): the failure of a package that
#: forgets the nonlinear branch of the cancellation. Applies to
#: ``RNF_TENDENCY_APPLY_T`` only (the first occurrence).
MUTANT_OLD = ("      DO j = 1, sNy\n       DO i = 1, sNx\n"
              "        tLoc(i,j) = tLoc(i,j)*mass2rUnit\n")
MUTANT_NEW = ("      IF ( nonlinFreeSurf.GT.0 ) THEN\n"
              "C       mutant: the generic term is not cancelled\n"
              "       DO j = 1-OLy, sNy+OLy\n        DO i = 1-OLx, sNx+OLx\n"
              "         gLoc(i,j) = 0. _d 0\n        ENDDO\n       ENDDO\n"
              "      ENDIF\n") + MUTANT_OLD


def write_mutant_code():
    """Mods directory of the mutant: the NLFS+ADDM code and a copy of
    ``rnf_tendency_apply.F`` with :data:`MUTANT_NEW` in its T routine."""
    path = os.path.join(lc.ROOT, "MITgcm", "pkg", "rnf", "rnf_tendency_apply.F")
    with open(path) as fh:
        text = fh.read()
    if text.count(MUTANT_OLD) < 1:
        raise ValueError(f"{path}: mutant anchor not found")
    text = text.replace(MUTANT_OLD, MUTANT_NEW, 1)
    cpp = os.path.join(VERIF, EXPERIMENT, "code", "CPP_OPTIONS.h")
    with open(cpp) as fh:
        base = fh.read()
    base = re.sub(r"(?m)^#undef ALLOW_ADDFLUID\s*$", "#define ALLOW_ADDFLUID",
                  base)
    return write_mods_code(MUTANT_CODE, {"CPP_OPTIONS.h": sync_cpp(base),
                                         "rnf_tendency_apply.F": text})


# ---------------------------------------------------------------- driver
#: The zero-run closure of the salt content (nonlinear grid), relative to
#: the total content; the measured maximum is 1.2e-11.
TOL_ZERO_S = 1.0e-10
#: Final-state difference between the RNF run and the same run with the
#: model's own addMass, relative to the largest response of the run.
TOL_NATIVE = 1.0e-9


def run_one(cfg_name, case, cell, entries, steps, build, timeout, out_ab=False):
    name, input_dir, dt = prepare(cfg_name, case, cell, entries, steps, out_ab)
    rd, status, timed_out = run_model(name, build, timeout)
    text = read_logs(rd)
    ok = status == 0 and not timed_out and "Execution ended Normally" in text
    return dict(dir=rd, input=input_dir, dt=dt, text=text, ok=ok,
                status=status)


def errors_of(text):
    return [ln.split(") ", 1)[-1].strip() for ln in text.splitlines()
            if "*** ERROR ***" in ln or "ABNORMAL END" in ln][:4]


def native_run(cfg_name, case, cell, steps, build, timeout):
    """The same source with the model's own ``addMass`` (``useRNF`` off):
    ``addMassFile`` holds ``rhoConstFresh*flux`` [kg/s] in the target cell,
    ``temp_addMass``/``salt_addMass`` the source values."""
    import numpy as np
    name, d, dt = prepare(cfg_name, dict(case, name="native"), cell,
                          case["entries"], steps)
    arr = np.zeros((23, 16, 20), dtype=">f4")
    level = case["entries"][0][0]
    arr.flat[cell + 320 * (level - 1)] = 999.8 * case["flux"]
    arr.tofile(os.path.join(d, "addmass.bin"))
    path = os.path.join(d, "data")
    with open(path) as fh:
        data = fh.read()
    for nl, key, line in (("PARM05", "addMassFile", " addMassFile='addmass.bin',"),
                          ("PARM01", "temp_addMass",
                           f" temp_addMass={lc.T_SRC!r},"),
                          ("PARM01", "salt_addMass",
                           f" salt_addMass={lc.S_SRC!r},")):
        data = set_namelist(data, nl, key, line)
    with open(path, "w") as fh:
        fh.write(data)
    path = os.path.join(d, "data.pkg")
    with open(path) as fh:
        pkg = fh.read()
    pkg = re.sub(r"useRNF\s*=\s*\.TRUE\.", "useRNF = .FALSE.", pkg)
    with open(path, "w") as fh:
        fh.write(pkg)
    path = os.path.join(d, "data.diagnostics")
    with open(path) as fh:
        diag = fh.read()
    out = []
    for ln in diag.splitlines():
        m = re.search(r"\((?:1,)?(\d+)\)", ln)
        if m and 1 <= int(m.group(1)) <= 4:
            continue
        out.append(re.sub(r"\((1,)?(\d+)\)", lambda mm: "(%s%d)" % (
            mm.group(1) or "", int(mm.group(2)) - 4), ln))
    with open(path, "w") as fh:
        fh.write("\n".join(out) + "\n")
    rd, status, timed_out = run_model(name, build, timeout)
    text = read_logs(rd)
    return dict(dir=rd, input=d, dt=dt, text=text,
                ok=status == 0 and "Execution ended Normally" in text)


def probes(cell, timeout):
    """Combinations that the model refuses, with its own message."""
    out = []
    case = CASES[0]
    # (a) a nonlinear free surface on a build without NONLIN_FRSURF
    name, d, dt = prepare("nl2_virt", case, cell, case["entries"], 2)
    r = run_model(name, lc.BUILD, timeout)
    out.append(("nonlinFreeSurf=4, select_rStar=2 on build_esx_addm "
                "(no NONLIN_FRSURF)", r[1], errors_of(read_logs(r[0]))))
    # (b) real freshwater flux + nonlinear free surface, LS_whenToSample = 0
    name, d, dt = prepare("nl2_real", case, cell, case["entries"], 2)
    p = os.path.join(d, "data.longstep")
    with open(p) as fh:
        t = fh.read()
    with open(p, "w") as fh:
        fh.write(t.replace("LS_whenToSample = 2", "LS_whenToSample = 0"))
    r = run_model(name, NLFS_BUILD, timeout)
    out.append(("useRealFreshWaterFlux with nonlinFreeSurf=4 and "
                "LS_whenToSample=0", r[1], errors_of(read_logs(r[0]))))
    # (c) nonlinear free surface without exactConserv
    name, d, dt = prepare("nl2_virt", case, cell, case["entries"], 2)
    p = os.path.join(d, "data")
    with open(p) as fh:
        t = fh.read()
    with open(p, "w") as fh:
        fh.write(set_namelist(t, "PARM01", "exactConserv",
                              " exactConserv=.FALSE.,"))
    r = run_model(name, NLFS_BUILD, timeout)
    out.append(("nonlinFreeSurf=4 with exactConserv=.FALSE.", r[1],
                errors_of(read_logs(r[0]))))
    return out


def run_config(cfg_name, args, cell, build):
    cfg = CONFIGS[cfg_name]
    res = dict(name=cfg_name, config=cfg, problems=[], figures={}, notes=[])
    by = {c["name"]: c for c in CASES}
    wanted = args.cases or [c["name"] for c in CASES]
    wanted = [w for w in wanted if w != "zero"]
    runs = {}
    case = by["zero"]
    runs["zero"] = run_one(cfg_name, case, cell, case["entries"], NSTEPS + 1,
                           build, args.timeout)
    res["accepted"] = runs["zero"]["ok"]
    if not runs["zero"]["ok"]:
        res["refusal"] = errors_of(runs["zero"]["text"])
        res["problems"].append("zero-flux run refused: "
                               + "; ".join(res["refusal"]))
        return res
    zero = runs["zero"]
    g = geometry(zero["dir"])
    dt = zero["dt"]
    text = zero["text"]
    # noise: a deep source of 1 m^3/s, the answer known to round-off
    tiny = dict(by["deep"], name="tiny", flux=1.0)
    noise = None
    if cfg["nl"]:
        runs["tiny"] = run_one(cfg_name, tiny, cell, tiny["entries"], 2,
                               build, args.timeout)
        if not runs["tiny"]["ok"]:
            res["problems"].append("noise run did not end normally")
            return res
        p, f = judge_step1_nlfs(cfg, tiny, runs["tiny"]["dir"], zero["dir"],
                                g, cell, tiny["entries"], dt, text)
        noise = {n: f[f"_budget {n} step 1 abs"] for n in "TSC"}
        res["figures"]["noise step-1 budget (abs) T/S/C"] = noise
    # zero-run definition of the content
    if True:
        z = judge_zero(cfg, zero["dir"], g, NSTEPS, dt, text)
        res["zero_run"] = z
        res["figures"]["zero run S closure / total"] = \
            (z["S change"] - z["S pred (SFLUX)"]) / z["S total"]
        if cfg["nl"]:
            vexp = z["V pred (oceFWflx)"] if cfg["real"] else 0.0
            res["figures"]["zero run V residual (m3)"] = z["V change"] - vexp
            if not abs((z["S change"] - z["S pred (SFLUX)"]) / z["S total"]) \
                    <= TOL_ZERO_S:
                res["problems"].append("zero run: the salt content does not "
                                       "follow SFLUX")
    zc = closure(cfg, zero["dir"], g, NSTEPS, dt, 0.0, text)
    vtol = NOISE_FACTOR * max(abs(zc["V"]["res"]),
                              2.2e-16 * zc["V"]["tot"], 1.0e-3)
    res["figures"]["volume tolerance (m3)"] = vtol
    ent = {}
    for cn in wanted:
        case = dict(by[cn])
        entries = case["entries"]
        if cn == "multi":
            entries = lc.multi_entries(zero["dir"], cell)
        ent[cn] = entries
        runs[cn] = run_one(cfg_name, case, cell, entries, NSTEPS + 1, build,
                           args.timeout)
        r = runs[cn]
        fig = {}
        if not r["ok"]:
            res["problems"].append(f"{cn}: run did not end normally "
                                   + "; ".join(errors_of(r["text"])))
            continue
        if cfg["nl"]:
            p, f = judge_step1_nlfs(cfg, case, r["dir"], zero["dir"], g, cell,
                                    entries, dt, r["text"], noise)
        else:
            p, f = lc.judge_placement(case, r["dir"], zero["dir"], cell,
                                      entries, dt, r["text"])
        res["problems"] += [f"{cn} step 1: {x}" for x in p]
        fig.update({f"step1 {k}": v for k, v in f.items() if v is not None})
        c = closure(cfg, r["dir"], g, NSTEPS, dt, case["flux"], r["text"])
        fig["V residual (m3)"] = c["V"]["res"]
        fig["V residual / injected"] = c["V"]["res"] / c["V"]["inj"]
        if not abs(c["V"]["res"]) <= vtol:
            res["problems"].append(f"{cn}: volume closure {c['V']['res']!r} "
                                   f"m3 over {NSTEPS} steps, tolerance {vtol!r}")
        for n in "TSC":
            d = c[n]["res"] - zc[n]["res"]
            fig[f"{n} content residual / injected (reported)"] = \
                d / c[n]["inj"]
        res["figures"][cn] = fig
    # native addMass of the model: the same state in the nonlinear grid
    if cfg["nl"] and "deep" in runs and runs["deep"]["ok"]:
        nat = native_run(cfg_name, dict(by["deep"]), cell, NSTEPS + 1, build,
                         args.timeout)
        if not nat["ok"]:
            res["problems"].append("native addMass run did not end normally")
        else:
            import numpy as np
            diffs = {}
            for label in ("T", "S", "Eta"):
                a = lc.field(runs["deep"]["dir"], "%s.%010d" % (label, NSTEPS))[0]
                b = lc.field(nat["dir"], "%s.%010d" % (label, NSTEPS))[0]
                z0 = lc.field(zero["dir"], "%s.%010d" % (label, NSTEPS))[0]
                resp = float(np.max(np.abs(a - z0)))
                diffs[label] = float(np.max(np.abs(a - b))) / resp
            res["figures"]["RNF vs native addMass, step %d (max diff / "
                           "response)" % NSTEPS] = diffs
            if not max(diffs.values()) <= TOL_NATIVE:
                res["problems"].append(f"RNF and native addMass differ: "
                                       f"{diffs!r}")
            shutil.rmtree(nat["input"], ignore_errors=True)
            shutil.rmtree(nat["dir"], ignore_errors=True)
    if not args.keep:
        for r in runs.values():
            shutil.rmtree(r["input"], ignore_errors=True)
    return res


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", action="append", default=None,
                        choices=sorted(CONFIGS))
    parser.add_argument("--cases", action="append", default=None)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json")
    parser.add_argument("--build", action="store_true",
                        help="compile the NLFS+ADDM and linear builds when "
                             "missing or stale")
    parser.add_argument("--use-nlfs-build", default=None, metavar="NAME",
                        help="run the nonlinear configurations on this "
                             "build (the mutant)")
    parser.add_argument("--probes", action="store_true",
                        help="also run the refused combinations")
    args = parser.parse_args(argv)
    if args.build:
        for b, w in ((lc.BUILD, lc.write_addm_code),
                     (NLFS_BUILD, write_nlfs_addm_code)):
            if not report_build(build_if_stale(b, w, jobs=4,
                                               timeout=args.timeout * 2)):
                return 2
    nlfs = args.use_nlfs_build or NLFS_BUILD
    for b in {lc.BUILD, nlfs}:
        if not os.path.isfile(os.path.join(VERIF, EXPERIMENT, b, "mitgcmuv")):
            print(f"MISSING: no binary {b}; rerun with --build")
            return 2
    cell = sparse_info()["wet_cell"]
    names = args.config or list(CONFIGS)
    results = []
    for n in names:
        cfg = CONFIGS[n]
        if args.use_nlfs_build and not cfg["nl"]:
            continue
        build = nlfs if cfg["nl"] else cfg["build"]
        results.append(run_config(n, args, cell, build))
    for r in results:
        print(("PASS " if not r["problems"] else "FAIL ") + r["name"],
              r["config"])
        for k, v in r["figures"].items():
            if not isinstance(v, dict) or "step1 RNFaddM k=1" in v \
                    or any(x.startswith("step1 ") for x in v):
                continue
            print(f"     {k}: " + ", ".join(f"{a} {b:.2e}"
                                            for a, b in v.items()))
        for k, v in r["figures"].items():
            if isinstance(v, dict) and any(x.startswith("step1 ") for x in v):
                step1 = max(b for a, b in v.items() if a.startswith("step1 ")
                            and not a.startswith("step1 _") and "stray" not in a
                            and "volume" not in a)
                cont = {a.split()[0]: b for a, b in v.items()
                        if a.endswith("(reported)")}
                print(f"     {k}: step-1 largest relative residual "
                      f"{step1:.2e}; volume residual {v['V residual (m3)']:.3e}"
                      f" m3 ({v['V residual / injected']:.2e} of injected); "
                      f"content residual / injected after {NSTEPS} steps "
                      + ", ".join(f"{a} {b:.2e}" for a, b in cont.items()))
            elif not isinstance(v, dict):
                print(f"     {k}: {v}")
        for p in r["problems"]:
            print(f"     {p}")
    if args.probes:
        for what, status, msgs in probes(cell, args.timeout):
            print(f"PROBE exit {status}: {what}")
            for m in msgs:
                print(f"     {m}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=1, default=str)
    return 1 if any(r["problems"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
