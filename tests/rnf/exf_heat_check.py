#!/usr/bin/env python3
"""The package heat term against the exf runoff-temperature term, cell by cell.

What this checks
================

``pkg/exf`` already has one way to give runoff a temperature: with
``ALLOW_RUNOFTEMP`` and a ``runoftempfile`` it adds
``Cp*(theta - runoftemp)*runoff*rhoConstFresh`` to ``Qnet``
(``pkg/exf/exf_mapfields.F:199-211``), which the model turns into a
temperature tendency through ``surfaceForcingT -= Qnet*mu/Cp``. In
tendency form that is

    rhoConstFresh*runoff*(runoftemp - theta)*mass2rUnit*D

``pkg/rnf`` applies ``[(mT) - m_T*theta]*mass2rUnit*D`` instead
(decision 3 of ``docs/package_design.md``). Where every source of a
cell carries a temperature, the two are the same number computed by
different code on different inputs -- a dense field of per-cell
temperatures against a per-source table -- so comparing them cell by
cell is the cross-path check RUNOFF-013's acceptance asks for.

This is not a check of one formula against a copy of itself: the dense
side is read out of ``EXFroff`` and ``EXFroft``, the two fields pkg/exf
itself applied, and the sparse side out of ``RNFgT``, the term pkg/rnf
itself applied, from two runs of the same experiment.

How the two runs are set up
---------------------------

Both runs use a lab_sea binary built with ``ALLOW_RUNOFTEMP`` defined,
which the committed ``pkg/exf/EXF_OPTIONS.h`` leaves undefined; the code
directory is written by this script and the compile command is printed
when the binary is missing. ``RNF_CHECK`` refuses a non-blank
``runoftempfile`` together with ``useRNF`` (decision 2), which is why
the comparison needs two runs rather than one: the dense run has
``useRNF`` false and the file, the sparse run has the file blank and
``pkg/rnf``.

The source temperatures differ from source to source, so the
comparison is over a field with structure and not over one constant:
the dense ``runoftemp`` file is built from the same per-source values
as the sparse file, at the cells the sparse file's targets name.

**Ice-free by construction.** The exf term is part of ``Qnet``, which
``pkg/seaice`` and ``pkg/thsice`` scale by the open-water fraction
while the package term is not scaled, so the two agree only where
there is no ice (decision 3, "Comparison with exf runoftemp"). Rather
than look for ice-free cells in a sea-ice run, both runs here have
``pkg/seaice`` switched off, which makes every cell ice-free. What this
check therefore does not establish is the under-ice behaviour; that
difference is inherited from the dense path and is RUNOFF-024's.

The control
-----------

``--control`` adds a run whose sparse file has one source's temperature
moved by 1 K while the dense ``runoftemp`` file is left alone, and
requires the comparison to **fail**. Without it a comparison that comes
out equal for the wrong reason -- both sides zero, no cell compared, the
same field read twice -- would pass.

Usage
=====

    tests/mitgcm_oracle.sh lab_sea input      # once, for the harness
    python3 tests/rnf/exf_heat_check.py [--control] [--keep]

Exit status: 0 if the comparison passes, 1 if it fails, 2 if the binary
is missing.
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (CELLS, ROOT, VERIF, add_to_namelist,  # noqa: E402
                           read_file, replace_line)
from applied_field_check import set_namelist  # noqa: E402
from tendency_term_check import (FIRST_DUMP, SALT0, STEPS,  # noqa: E402
                                 THETA0, build_if_stale, dump_at,
                                 layer_thickness, param, read_mds,
                                 report_build, run_model, state_at,
                                 write_state, THETA_FILE, SALT_FILE)

EXPERIMENT = "lab_sea"
#: Scratch input directories, one per run.
PREFIX = "input.rnfterm_exf"
#: Build with ALLOW_RUNOFTEMP defined, and the code directory of it.
BUILD = "build_esx_roft"
CODE = "code_rnfterm_roft"
#: The sparse file this check writes, and the dense pair it writes beside it.
SPARSE_FILE = "runoff_exf.nc"
DENSE_RUNOFF = "runoff_exf_dense.bin"
DENSE_TEMP = "runoftemp_exf_dense.bin"
#: Source temperatures [degC], one per source of the per-cell file, so
#: that the comparison is over a field with structure. The list is cycled
#: if the file has more sources than this.
TEMPERATURES = (30.0, 25.0, 20.0, 12.5, 7.0, 3.0, -1.0)
#: Tolerance of the cell-by-cell comparison (RUNOFF-013 acceptance).
RTOL = 1.0e-12
#: Fewest cells the comparison must cover to count as one.
MIN_CELLS = 5
#: Grid of lab_sea.
NX, NY = 20, 16

DATA_DIAGNOSTICS = """# Cross-path heat check of tests/rnf/exf_heat_check.py:
# snapshots (frequency < 0) through MDS, in float64, of the two fields
# pkg/exf applied (EXFroff, EXFroft) and of the term pkg/rnf applied
# (RNFgT, level 1). A run has the streams of its own path only.
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
{streams} &

 &DIAG_STATIS_PARMS
 &
"""

STREAM = """  fields(1,{n}) = '{field}',
  fileName({n}) = '{name}',
  frequency({n}) = -{dt!r},
  levels(1,{n}) = 1.,
  fileFlags({n}) = 'D       ',
"""


def write_code():
    """Write the code directory of the build with ALLOW_RUNOFTEMP defined."""
    code = os.path.join(VERIF, EXPERIMENT, CODE)
    shutil.rmtree(code, ignore_errors=True)
    os.makedirs(code)
    base = os.path.join(VERIF, EXPERIMENT, "code")
    for name in sorted(os.listdir(base)):
        src = os.path.join(base, name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(code, name))
    with open(os.path.join(ROOT, "MITgcm", "pkg", "exf",
                           "EXF_OPTIONS.h")) as fh:
        options = fh.read()
    new, count = re.subn(r"(?m)^#undef\s+ALLOW_RUNOFTEMP\s*$",
                         "#define ALLOW_RUNOFTEMP", options)
    if count != 1:
        raise ValueError(f"pkg/exf/EXF_OPTIONS.h has {count} "
                         f"'#undef ALLOW_RUNOFTEMP' lines, expected 1")
    with open(os.path.join(code, "EXF_OPTIONS.h"), "w") as fh:
        fh.write(new)
    return code


def compile_command(code):
    return ("./experiment_compile.sh %s -mods %s -build %s -j 8"
            % (EXPERIMENT, code, BUILD))


def source_temperatures(nsrc):
    """Return one temperature per source, cycling ``TEMPERATURES``."""
    return [TEMPERATURES[k % len(TEMPERATURES)] for k in range(nsrc)]


def write_files(input_dir, perturb=None):
    """Write the sparse file and the dense runoff/temperature pair.

    Both are built from the committed per-cell sparse file
    (``input.rnof_const/runoff_sparse_cells.nc``), in which every source
    feeds one cell, so that one per-source temperature is also one
    per-cell temperature and the dense field is exactly what the sparse
    table says. Returns the cells, their fluxes per unit area and their
    temperatures.

    ``perturb`` is the index of a source whose temperature is moved by
    1 K in the **sparse** file only: the control.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(CELLS) as src:
        src.set_auto_maskandscale(False)
        nsrc = len(src.dimensions["source"])
        cells = np.asarray(src["target_cell"][:]).astype(int)
        tsrc = np.asarray(src["target_source"][:]).astype(int)
        frac = np.asarray(src["target_fraction"][:], dtype=np.float64)
        flux = np.asarray(src["runoff_flux"][0], dtype=np.float64)
        temps = source_temperatures(nsrc)
        with netCDF4.Dataset(os.path.join(input_dir, SPARSE_FILE),
                             "w") as dst:
            dst.set_auto_maskandscale(False)
            dst.setncatts({k: src.getncattr(k) for k in src.ncattrs()})
            for name, dim in src.dimensions.items():
                dst.createDimension(name,
                                    None if dim.isunlimited() else len(dim))
            for name, var in src.variables.items():
                atts = {k: var.getncattr(k) for k in var.ncattrs()}
                fill = atts.pop("_FillValue", None)
                out = dst.createVariable(name, var.dtype, var.dimensions,
                                         fill_value=fill)
                out.setncatts(atts)
                out[:] = var[:]
            series = list(temps)
            if perturb is not None:
                series[perturb] += 1.0
            temp = dst.createVariable("runoff_temperature", "f8",
                                      ("time", "source"))
            temp.units = "degC"
            temp[0, :] = series
    # the per-cell temperature field of the dense path: with one source
    # per cell, the source's temperature IS the cell's
    dense_temp = np.zeros(NX*NY, dtype=np.float64)
    for k, cell in enumerate(cells):
        dense_temp[cell] = temps[tsrc[k]]
    return {"cells": cells, "source": tsrc, "frac": frac, "flux": flux,
            "temps": temps, "dense_temp": dense_temp}


def write_dense_fields(input_dir, info, rac):
    """Write the dense runoff (m/s) and runoff-temperature binaries.

    The runoff field is rebuilt from the sparse table and the model's own
    cell areas, in the table order, so that the two paths are given the
    same numbers to within the round-off of one division.
    """
    import numpy as np
    flux = np.zeros(NX*NY, dtype=np.float64)
    for k, cell in enumerate(info["cells"]):
        flux[cell] += info["flux"][info["source"][k]]*info["frac"][k]/rac[cell]
    flux.astype(">f4").tofile(os.path.join(input_dir, DENSE_RUNOFF))
    info["dense_temp"].astype(">f4").tofile(
        os.path.join(input_dir, DENSE_TEMP))
    return flux


def write_input(input_dir, sparse, dt=3600.0):
    """Write the input files of one run; ``sparse`` selects the path."""
    base = os.path.join(VERIF, EXPERIMENT, "input")
    write_state(input_dir)
    with open(os.path.join(base, "data")) as fh:
        data = fh.read()
    settings = [
        ("PARM03", "startTime", " startTime=0.0,"),
        ("PARM03", "endTime", f" endTime={STEPS*dt!r},"),
        ("PARM03", "monitorFreq", " monitorFreq=1.,"),
        ("PARM03", "pChkptFreq", " pChkptFreq=0.,"),
        ("PARM03", "dumpFreq", f" dumpFreq={dt!r},"),
        ("PARM03", "dumpInitAndLast", " dumpInitAndLast=.TRUE.,"),
        ("PARM01", "writeBinaryPrec", " writeBinaryPrec=64,"),
        ("PARM03", "outputTypesInclusive", " outputTypesInclusive=.TRUE.,"),
        ("PARM05", "hydrogThetaFile", f" hydrogThetaFile='{THETA_FILE}',"),
        ("PARM05", "hydrogSaltFile", f" hydrogSaltFile='{SALT_FILE}',"),
        ("PARM01", "useRealFreshWaterFlux",
         " useRealFreshWaterFlux=.FALSE.,"),
        ("PARM01", "nonlinFreeSurf", " nonlinFreeSurf=0,"),
        ("PARM01", "implicitDiffusion", " implicitDiffusion=.FALSE.,"),
        # temp_EvPrRn unset, so the model adds no term of its own and
        # pkg/exf's own cancellation of it is not compiled in either;
        # what is compared is the runoftemp term against the package one
        ("PARM01", "temp_EvPrRn", " temp_EvPrRn=1.234567E5,"),
    ]
    for namelist, name, line in settings:
        data = set_namelist(data, namelist, name, line)
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)

    with open(os.path.join(base, "data.pkg")) as fh:
        pkg = fh.read()
    for name, value in (("useGMRedi", ".FALSE."), ("useKPP", ".FALSE."),
                        ("useSEAICE", ".FALSE."), ("useMNC", ".FALSE."),
                        ("useEXF", ".TRUE."), ("useCAL", ".TRUE."),
                        ("useDiagnostics", ".TRUE."),
                        ("useRNF", ".TRUE." if sparse else ".FALSE.")):
        line = f"  {name} = {value},"
        pkg = (replace_line(pkg, name, line)
               if re.search(r"(?mi)^\s*%s\s*=" % re.escape(name), pkg)
               else add_to_namelist(pkg, "PACKAGES", line))
    with open(os.path.join(input_dir, "data.pkg"), "w") as fh:
        fh.write(pkg)

    # useExfCheckRange is left at the setting of lab_sea/input
    # (.TRUE.) in both runs. It used to be switched off here, copied
    # from tests/rnf/tendency_term_check.py, but these runs never
    # needed it: the runoff of the committed per-cell file is 4.0e-7
    # to 7.6e-7 m/s, under the 1e-6 m/s pkg/exf allows, on both paths
    # (measured from input.rnof_const/runoff_sparse_cells.nc). The
    # dense run has useRNF false and so is held to the exf bound in
    # full, which is what makes it a check of the unchanged dense path
    # as well as of the heat term (RUNOFF-030). It is not a check of
    # the skip: the sparse run is under the bound too.
    with open(os.path.join(base, "data.exf")) as fh:
        exf = fh.read()
    for name, value in (("runoffFile", "' '" if sparse
                         else f"'{DENSE_RUNOFF}'"),
                        ("runoftempfile", "' '" if sparse
                         else f"'{DENSE_TEMP}'")):
        exf = set_namelist(exf, "EXF_NML_02", name,
                           f" {name} = {value},")
    # One record, read once at initialisation. pkg/exf gives runoftemp
    # the runoff timing (pkg/exf/exf_getffields.F:437-450 passes
    # runoffStartTime, runoffperiod, runoffRepCycle), so there is one
    # setting for both fields.
    exf = set_namelist(exf, "EXF_NML_02", "runoffperiod",
                       " runoffperiod = 0.0,")
    with open(os.path.join(input_dir, "data.exf"), "w") as fh:
        fh.write(exf)

    fields = ([("RNFgT   ", "rnfGT")] if sparse
              else [("EXFroff ", "exfRoff"), ("EXFroft ", "exfRoft")])
    streams = "".join(STREAM.format(n=k+1, field=f, name=name, dt=dt)
                      for k, (f, name) in enumerate(fields))
    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(DATA_DIAGNOSTICS.format(streams=streams))

    if sparse:
        with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
            fh.write("# Written by tests/rnf/exf_heat_check.py\n"
                     " &RNF_PARM01\n"
                     f"  RNF_file = '{SPARSE_FILE}',\n"
                     "  RNF_debugLev = 3,\n"
                     " &\n")
    return dt


def compare(dense_dir, sparse_dir, info, dt):
    """Compare the two paths cell by cell at the measured step."""
    import numpy as np
    text = read_file(dense_dir, "output.txt") or ""
    rho = param(text, "rhoConst")
    rho_fresh = param(text, "rhoConstFresh")
    mu = 1.0/rho
    rac, _ = read_mds(dense_dir, "RAC")
    hfac, _ = read_mds(dense_dir, "hFacC")
    drf1 = layer_thickness(dense_dir)

    roff, label_roff = dump_at(dense_dir, "exfRoff", 0, whole=True)
    roft, label_roft = dump_at(dense_dir, "exfRoft", 0, whole=True)
    gt, label_gt = dump_at(sparse_dir, "rnfGT", 0, whole=True)
    theta_d = state_at(dense_dir, FIRST_DUMP, 0)["theta_field"]
    theta_s = state_at(sparse_dir, FIRST_DUMP, 0)["theta_field"]

    cells = sorted({int(c) for c in info["cells"]})
    worst, worst_cell = 0.0, None
    per_cell = {}
    for cell in cells:
        dense = (rho_fresh*roff[cell]*(roft[cell] - theta_d[cell])
                 * mu/(drf1*hfac[cell]))
        got = gt[cell]
        scale = max(abs(dense), abs(got))
        rel = 0.0 if scale == 0.0 else abs(got - dense)/scale
        per_cell[cell] = {"dense": dense, "sparse": got, "relative": rel,
                          "runoff": roff[cell], "runoftemp": roft[cell],
                          "theta": theta_d[cell]}
        if rel > worst:
            worst, worst_cell = rel, cell
    # cells where one path acts and the other does not
    nonzero_dense = {int(c) for c in np.nonzero(roff)[0]}
    nonzero_sparse = {int(c) for c in np.nonzero(gt)[0]}
    return {"cells": len(cells), "worst": worst, "worst_cell": worst_cell,
            "per_cell": per_cell,
            "extra": sorted(nonzero_sparse - nonzero_dense),
            "missing": sorted(nonzero_dense - nonzero_sparse),
            "theta_differs": int(np.count_nonzero(theta_d != theta_s)),
            "labels": [label_roff, label_roft, label_gt],
            "rhoConstFresh": rho_fresh, "mu": mu, "drF": drf1}


def run_pair(args, perturb=None):
    """Run the dense and the sparse case; return the comparison."""
    tag = "" if perturb is None else "_control"
    dirs = {}
    for sparse in (False, True):
        name = PREFIX + ("sparse" if sparse else "dense") + tag
        input_dir = os.path.join(VERIF, EXPERIMENT, name)
        shutil.rmtree(input_dir, ignore_errors=True)
        os.makedirs(input_dir)
        info = write_files(input_dir, perturb=perturb if sparse else None)
        dt = write_input(input_dir, sparse)
        dirs[sparse] = (name, input_dir, info, dt)
    # the dense runoff field needs the model's own cell areas, so it is
    # written after a first run has produced RAC.data... which it has,
    # from any earlier run of this experiment
    rac_source = None
    for candidate in sorted(os.listdir(os.path.join(VERIF, EXPERIMENT))):
        if candidate.startswith("output_esx_") and os.path.isfile(
                os.path.join(VERIF, EXPERIMENT, candidate, "RAC.data")):
            rac_source = os.path.join(VERIF, EXPERIMENT, candidate)
            break
    if rac_source is None:
        print("no run directory of this experiment holds RAC.data; run "
              "tests/mitgcm_oracle.sh lab_sea input first")
        return None, 2
    rac, _ = read_mds(rac_source, "RAC")
    name, input_dir, info, dt = dirs[False]
    write_dense_fields(input_dir, info, rac)
    runs = {}
    for sparse in (False, True):
        name, input_dir, info, dt = dirs[sparse]
        run_dir, status, timed_out = run_model(name, BUILD, args.timeout)
        runs[sparse] = (run_dir, status, timed_out)
    bad = [f"{'sparse' if s else 'dense'} run exit {st}"
           + (" (timed out)" if t else "")
           for s, (_, st, t) in runs.items() if st != 0]
    if bad:
        return {"problems": bad}, 1
    result = compare(runs[False][0], runs[True][0], dirs[True][2], dt)
    if not args.keep:
        for sparse in (False, True):
            shutil.rmtree(dirs[sparse][1], ignore_errors=True)
    return result, 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--control", action="store_true",
                        help="also run the control, which must fail")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json")
    parser.add_argument("--build", action="store_true",
                        help="compile the ALLOW_RUNOFTEMP binary when it "
                             "is missing or older than its sources; "
                             "without it a missing binary is reported "
                             "with its compile command and the run "
                             "exits 2")
    args = parser.parse_args(argv)

    if args.build and not report_build(
            build_if_stale(BUILD, write_code, timeout=args.timeout*2)):
        return 2

    binary = os.path.join(VERIF, EXPERIMENT, BUILD, "mitgcmuv")
    if not os.path.isfile(binary):
        code = write_code()
        print(f"MISSING: no binary at {binary}")
        print(f"  the code directory is written at {code}; build it from "
              f"{VERIF} with")
        print(f"    {compile_command(code)}")
        print("  or rerun this check with --build, which compiles it")
        return 2

    out = {}
    result, status = run_pair(args)
    out["comparison"] = result
    if status == 2:
        return 2
    problems = list(result.get("problems", []))
    if not problems:
        if result["cells"] < MIN_CELLS:
            problems.append(f"{result['cells']} cell(s) compared, fewer "
                            f"than {MIN_CELLS}")
        if result["extra"] or result["missing"]:
            problems.append(f"the two paths act on different cells: "
                            f"{len(result['extra'])} extra, "
                            f"{len(result['missing'])} missing")
        if result["worst"] > RTOL:
            problems.append(f"largest relative deviation "
                            f"{result['worst']:.3e} at cell "
                            f"{result['worst_cell']} > {RTOL!r}")
    verdict = "PASS" if not problems else "FAIL"
    print(f"{verdict} exf_vs_package: {result.get('cells', 0)} cells, "
          f"largest relative deviation {result.get('worst', float('nan')):.3e}"
          f", theta fields differing in "
          f"{result.get('theta_differs', '?')} values")
    for problem in problems:
        print(f"     {problem}")

    control = None
    if args.control and not problems:
        control, cstatus = run_pair(args, perturb=0)
        out["control"] = control
        caught = cstatus != 0 or control.get("worst", 0.0) > RTOL
        print(f"{'PASS' if caught else 'FAIL'} control: one source's "
              f"temperature moved 1 K in the sparse file only, largest "
              f"relative deviation {control.get('worst', 0.0):.3e}")
        if not caught:
            problems.append("the control was not detected: a 1 K error in "
                            "one source's temperature left the comparison "
                            "inside the tolerance")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=1, default=str)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
