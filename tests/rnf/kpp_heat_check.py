#!/usr/bin/env python3
"""KPP and the surface heat diagnostics see the sparse runoff heat (RUNOFF-031).

What this checks
================

Since RUNOFF-031 the heat of sparse runoff reaches the model through the
surface flux fields, as every other surface heat flux does:
``RNF_EXF_RUNOFF`` sets the exf ``runoftemp`` field and ``EXF_MAPFIELDS``
adds ``Cp*(theta - runoftemp)*runoff*rhoConstFresh`` to ``Qnet``
(``pkg/exf/exf_mapfields.F``, the ``ALLOW_RUNOFTEMP`` block), which
``EXTERNAL_FORCING_SURF`` turns into ``surfaceForcingT``
(``model/src/external_forcing_surf.F:226-231``). ``surfaceForcingT`` is
what KPP builds its surface buoyancy forcing from
(``pkg/kpp/kpp_calc.F:421``) and what the model's ``TFLUX`` diagnostic
reports (``model/src/diags_oceanic_surf_flux.F``). Before RUNOFF-031 the
heat was a tendency term added to ``gT`` and neither saw it, which is
what RUNOFF-031 was filed for.

The check runs lab_sea **with KPP on** twice, with the same sparse
runoff volume, once with a warm ``runoff_temperature`` and once with no
temperature variable at all (the runoff then enters at the surface
temperature and adds no heat of its own):

* **Exact leg.** Record 1 of the file is dry and every later record is
  wet, held exactly (``RNF_holdRecord``), so the first step of the two
  runs is the same and they enter the second step in a bitwise identical
  state, which :func:`judge` asserts on the state dumps. At that step
  every surface heat flux except the runoff's is therefore bitwise the
  same in the two runs, and the difference of their ``TFLUX`` at the
  target cell must equal the analytic heat of the runoff,
  ``HeatCapacity_Cp*rhoConstFresh*m_v*(T_r - theta)`` with ``m_v`` the
  volume flux per area and ``theta`` the run's own surface temperature at
  the start of that step, to :data:`RTOL`; it must be exactly 0 at every
  other cell; and the package's own ``RNFqnet`` must be minus the same
  number (``Qnet`` is positive upward). ``KPPbo``, the turbulent surface
  buoyancy forcing KPP computes from ``surfaceForcingT`` and
  ``surfaceForcingS``, must differ between the runs at the target cell at
  that same step and nowhere else, which is the statement that KPP's
  input contains the heat.
* **Evidence leg** (reported, no threshold, as the issue asks): the
  difference of the KPP boundary-layer depth ``KPPhbl`` and of the
  surface temperature at the target cell, over the run.

``pkg/seaice`` is switched off in both runs: with it the exf ``Qnet`` is
scaled by the open-water fraction (``SEAICE_EXTERNAL_FLUXES``), for the
dense ``runoftempfile`` path and the sparse one alike, and the analytic
heat would need the ice concentration. That scaling is inherited from
the dense path and is RUNOFF-024's.

**Must-fail.** ``--use-build`` runs both cases on a named binary; on the
sign-flip mutant of RUNOFF-031 (``runoftemp`` mirrored about ``theta``
after ``RNFqnet`` is computed, so ``EXF_MAPFIELDS`` applies minus the
heat) the exact leg must fail.

Usage
=====

    python3 tests/rnf/kpp_heat_check.py [--build] [--keep] [--json PATH]

Exit status: 0 if the exact leg passes, 1 if it fails, 2 if the binary
is missing or could not be built.
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (VERIF, add_to_namelist,  # noqa: E402
                           read_file, replace_line, sparse_info)
from applied_field_check import set_namelist  # noqa: E402
from tendency_term_check import (BUILD, build_if_stale, param,  # noqa: E402
                                 read_mds, report_build, run_model,
                                 write_roft_code)

EXPERIMENT = "lab_sea"
PREFIX = "input.rnfkpp_"
SPARSE_FILE = "runoff_kpp.nc"
#: Volume flux of the one source [m^3/s]. With the lab_sea target cell
#: (3.112287e10 m^2) this is 3.21e-6 m/s, a tenth of the flux
#: tests/rnf/tendency_term_check.py uses and 173 times inside
#: RNF_cellVolMax on that cell; strong enough that a 25 degC source
#: changes the surface heat flux there by about 3.5e2 W/m^2.
FLUX = 1.0e5
#: Temperature of the warm source [degC].
T_RUNOFF = 25.0
#: Steps of each run: the dry first one, then STEPS - 1 wet ones.
STEPS = 25
#: Relative tolerance of the exact leg.
RTOL = 1.0e-12
#: Label of the snapshot that carries the first wet (second) step: a
#: snapshot is labelled by its write slot, so this one holds step 2
#: (tests/rnf/tendency_term_check.dump_at records the measurement).
WET_DUMP = "0000000001"
NX, NY = 20, 16

DATA_DIAGNOSTICS = """# tests/rnf/kpp_heat_check.py: snapshots of every step
# (frequency < 0), MDS, float64, of the model's surface heat flux, the
# runoff heat pkg/rnf hands to Qnet, and two KPP fields.
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
  fields(1,1) = 'TFLUX   ',
  fileName(1) = 'kppTflux',
  frequency(1) = -{dt!r},
  fileFlags(1) = 'D       ',
  fields(1,2) = 'RNFqnet ',
  fileName(2) = 'kppRnfQ',
  frequency(2) = -{dt!r},
  fileFlags(2) = 'D       ',
  fields(1,3) = 'KPPhbl  ',
  fileName(3) = 'kppHbl',
  frequency(3) = -{dt!r},
  fileFlags(3) = 'D       ',
  fields(1,4) = 'KPPbo   ',
  fileName(4) = 'kppBo',
  frequency(4) = -{dt!r},
  fileFlags(4) = 'D       ',
 &

 &DIAG_STATIS_PARMS
 &
"""


def write_sparse(path, cell, dt, warm, t_runoff=None):
    """One source on ``cell``: dry record 1, then wet records."""
    import netCDF4
    import numpy as np
    nrec = STEPS + 1
    with netCDF4.Dataset(path, "w") as ds:
        ds.set_auto_maskandscale(False)
        ds.setncatts({"mitgcm_runoff_schema_version": "1.0",
                      "mitgcm_grid_nx": np.int32(NX),
                      "mitgcm_grid_ny": np.int32(NY),
                      "mitgcm_time_sampling": "fixed",
                      "mitgcm_time_period": np.float64(dt),
                      "mitgcm_time_repeat": "none",
                      "title": "tests/rnf/kpp_heat_check.py"})
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
        flux[0, :] = 0.0
        if warm:
            temp = ds.createVariable("runoff_temperature", "f8",
                                     ("time", "source"))
            temp.units = "degC"
            temp[:] = T_RUNOFF if t_runoff is None else t_runoff


def write_input(input_dir, warm, t_runoff=None):
    """The scratch input of one run, layered on lab_sea/input."""
    base = os.path.join(VERIF, EXPERIMENT, "input")
    cell = sparse_info()["wet_cell"]
    dt = 3600.0
    write_sparse(os.path.join(input_dir, SPARSE_FILE), cell, dt, warm,
                 t_runoff)
    with open(os.path.join(base, "data")) as fh:
        data = fh.read()
    # From iteration 0 (no pickup: the initial state is lab_sea's own
    # hydrography), with a state dump at every step.
    for namelist, name, line in (
            ("PARM03", "startTime", " startTime=0.0,"),
            ("PARM03", "endTime", f" endTime={STEPS*dt!r},"),
            ("PARM03", "monitorFreq", " monitorFreq=1.,"),
            ("PARM03", "pChkptFreq", " pChkptFreq=0.,"),
            ("PARM03", "dumpFreq", f" dumpFreq={dt!r},"),
            ("PARM03", "dumpInitAndLast", " dumpInitAndLast=.TRUE.,"),
            ("PARM01", "writeBinaryPrec", " writeBinaryPrec=64,"),
            ("PARM03", "outputTypesInclusive",
             " outputTypesInclusive=.TRUE.,")):
        data = set_namelist(data, namelist, name, line)
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)
    with open(os.path.join(base, "data.pkg")) as fh:
        pkg = fh.read()
    for name, value in (("useKPP", ".TRUE."), ("useSEAICE", ".FALSE."),
                        ("useMNC", ".FALSE."), ("useDiagnostics", ".TRUE."),
                        ("useRNF", ".TRUE.")):
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
    with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
        fh.write("# Written by tests/rnf/kpp_heat_check.py\n"
                 " &RNF_PARM01\n"
                 f"  RNF_file = '{SPARSE_FILE}',\n"
                 "  RNF_holdRecord = .TRUE.,\n"
                 "  RNF_debugLev = 3,\n"
                 " &\n")
    return cell, dt


def field(run_dir, base):
    values, sizes = read_mds(run_dir, base)
    return values[:NX*NY], sizes


def judge(warm_dir, none_dir, cell, t_runoff=T_RUNOFF):
    """The exact leg at the first wet step, and the evidence leg."""
    import numpy as np
    problems = []
    text = read_file(warm_dir, "output.txt") or ""
    cp = param(text, "HeatCapacity_Cp")
    rho_fresh = param(text, "rhoConstFresh")
    rac, _ = field(warm_dir, "RAC")
    m_v = FLUX*1.0/float(rac[cell])

    theta_w, _ = field(warm_dir, "T." + WET_DUMP)
    theta_n, _ = field(none_dir, "T." + WET_DUMP)
    full_w, _ = read_mds(warm_dir, "T." + WET_DUMP)
    full_n, _ = read_mds(none_dir, "T." + WET_DUMP)
    if not np.array_equal(full_w, full_n):
        problems.append(f"the two runs enter the first wet step in "
                        f"different states ({int((full_w != full_n).sum())}"
                        f" theta values differ): the difference of their "
                        f"surface fluxes is then not the runoff heat")
    theta = float(theta_w[cell])
    analytic = cp*rho_fresh*m_v*(t_runoff - theta)

    tw, _ = field(warm_dir, "kppTflux." + WET_DUMP)
    tn, _ = field(none_dir, "kppTflux." + WET_DUMP)
    qw, _ = field(warm_dir, "kppRnfQ." + WET_DUMP)
    bw, _ = field(warm_dir, "kppBo." + WET_DUMP)
    bn, _ = field(none_dir, "kppBo." + WET_DUMP)
    dtflux = tw - tn
    measured = float(dtflux[cell])
    rel_tflux = abs(measured - analytic)/abs(analytic)
    rel_qnet = abs(-float(qw[cell]) - analytic)/abs(analytic)
    elsewhere = int(np.count_nonzero(np.delete(dtflux, cell)))
    dbo = bw - bn
    bo_elsewhere = int(np.count_nonzero(np.delete(dbo, cell)))
    if rel_tflux > RTOL:
        problems.append(f"TFLUX difference {measured!r} against the analytic "
                        f"{analytic!r}: relative {rel_tflux:.3e} > {RTOL!r}")
    if rel_qnet > RTOL:
        problems.append(f"-RNFqnet {-float(qw[cell])!r} against the analytic "
                        f"{analytic!r}: relative {rel_qnet:.3e} > {RTOL!r}")
    if elsewhere:
        problems.append(f"TFLUX differs at {elsewhere} cells other than the "
                        f"target at the first wet step")
    if float(dbo[cell]) == 0.0:
        problems.append("KPPbo is the same in the two runs at the target "
                        "cell: KPP's surface buoyancy forcing does not see "
                        "the runoff heat")
    if bo_elsewhere:
        problems.append(f"KPPbo differs at {bo_elsewhere} cells other than "
                        f"the target at the first wet step")

    # Evidence leg: every later snapshot, at the target cell.
    import glob
    labels = sorted(os.path.basename(p).split(".")[1] for p in
                    glob.glob(os.path.join(warm_dir, "kppHbl.*.data")))
    history = []
    for label in labels:
        hw, _ = field(warm_dir, "kppHbl." + label)
        hn, _ = field(none_dir, "kppHbl." + label)
        row = {"snapshot": label, "KPPhbl_warm": float(hw[cell]),
               "KPPhbl_none": float(hn[cell]),
               "dKPPhbl": float(hw[cell] - hn[cell])}
        state = "T.%010d" % (int(label) + 1)
        if os.path.isfile(os.path.join(warm_dir, state + ".data")):
            sw, _ = field(warm_dir, state)
            sn, _ = field(none_dir, state)
            row.update(SST_warm=float(sw[cell]), SST_none=float(sn[cell]),
                       dSST=float(sw[cell] - sn[cell]))
        history.append(row)
    return {"cell": cell, "HeatCapacity_Cp": cp, "rhoConstFresh": rho_fresh,
            "volume_flux": m_v, "theta": theta, "T_runoff": t_runoff,
            "analytic": analytic, "dTFLUX": measured,
            "RNFqnet": float(qw[cell]), "relative_TFLUX": rel_tflux,
            "relative_RNFqnet": rel_qnet, "TFLUX_elsewhere": elsewhere,
            "dKPPbo": float(dbo[cell]), "KPPbo_elsewhere": bo_elsewhere,
            "history": history, "problems": problems}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true",
                        help="compile the ALLOW_RUNOFTEMP binary when it is "
                             "missing or older than its sources")
    parser.add_argument("--use-build", default=None, metavar="NAME",
                        help="run both cases on this build (the must-fail "
                             "demonstration on a mutant)")
    parser.add_argument("--t-runoff", type=float, default=T_RUNOFF,
                        help="source temperature in degC (default "
                             f"{T_RUNOFF}); a cold one shows the mixed-layer "
                             "response, which a warm source on a layer "
                             "already at its shallowest does not")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json")
    args = parser.parse_args(argv)
    if args.use_build and args.build:
        parser.error("--use-build does not combine with --build")
    build = args.use_build or BUILD
    if args.build and not report_build(
            build_if_stale(BUILD, write_roft_code, timeout=args.timeout*2)):
        return 2
    if not os.path.isfile(os.path.join(VERIF, EXPERIMENT, build,
                                       "mitgcmuv")):
        print(f"MISSING: no binary {build}; rerun with --build")
        return 2
    runs, dirs = {}, []
    for warm in (True, False):
        name = PREFIX + ("warm" if warm else "none")
        input_dir = os.path.join(VERIF, EXPERIMENT, name)
        shutil.rmtree(input_dir, ignore_errors=True)
        os.makedirs(input_dir)
        dirs.append(input_dir)
        cell, _dt = write_input(input_dir, warm, args.t_runoff)
        run_dir, status, timed_out = run_model(name, build, args.timeout)
        ended = "Execution ended Normally" in (read_file(run_dir,
                                                         "output.txt") or "")
        runs[warm] = (run_dir, status, timed_out, ended)
    bad = [f"{'warm' if w else 'none'} run exit {s}"
           + (" (timed out)" if t else "") + ("" if e else ", no normal end")
           for w, (_, s, t, e) in runs.items() if s or t or not e]
    if bad:
        print("FAIL kpp_heat: " + "; ".join(bad))
        return 1
    result = judge(runs[True][0], runs[False][0], cell, args.t_runoff)
    ok = not result["problems"]
    print(f"{'PASS' if ok else 'FAIL'} kpp_heat: dTFLUX {result['dTFLUX']:.6e}"
          f" W/m^2 against analytic {result['analytic']:.6e} (relative "
          f"{result['relative_TFLUX']:.3e}), -RNFqnet relative "
          f"{result['relative_RNFqnet']:.3e}; TFLUX differs elsewhere at "
          f"{result['TFLUX_elsewhere']} cells; dKPPbo {result['dKPPbo']:.3e}"
          f" (elsewhere {result['KPPbo_elsewhere']})")
    last = result["history"][-1] if result["history"] else {}
    if last:
        big = max(result["history"], key=lambda r: abs(r["dKPPhbl"]))
        print(f"     evidence: after {len(result['history'])} snapshots "
              f"dKPPhbl {last['dKPPhbl']:+.4f} m "
              f"({last['KPPhbl_none']:.4f} -> {last['KPPhbl_warm']:.4f}),"
              f" largest {big['dKPPhbl']:+.4f} m at snapshot "
              f"{big['snapshot']}; dSST {last.get('dSST', float('nan')):+.4f}"
              f" degC")
    for problem in result["problems"]:
        print(f"     {problem}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=1)
    if not args.keep:
        for path in dirs:
            shutil.rmtree(path, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
