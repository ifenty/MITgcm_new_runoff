#!/usr/bin/env python
"""Check the runoff field pkg/rnf applies, cell by cell, against the file.

Every configured sparse = dense oracle judges the monitor digits of
``output.txt``, and that criterion cannot see a misplaced target. Measured
on cs32 on 4 processes (RUNOFF-033): moving one target entry one cell in x
across the facet 2/3 boundary, where the two cells' ``rA`` is **bitwise
equal** so the area check is blind and the fractions still sum to 1, is
accepted silently, the run ends normally and ``compare_results.sh`` reports
10 matching digits against the 10 required -- a pass with no margin at all.
Global mass is still conserved; the water is not lost, only delivered to
the wrong cell, which is why a digit threshold cannot see it.

This check has margin, because it compares the field the model applies
with the field the file asks for, cell by cell, in float64:

1. the model is made to dump what it applies. An ``EXFroff`` diagnostic
   stream (``diag_mnc = .FALSE.``, ``fileFlags = 'D'`` for float64, with
   the ``useSingleCpuIO`` the experiments already set) writes the exf
   ``runoff`` array as one global array per time step. ``EXFroff`` is
   filled by ``EXF_DIAGNOSTICS_FILL``, which ``EXF_GETFORCING`` calls
   after ``EXF_GETFFIELDS`` -- and so after ``RNF_EXF_RUNOFF`` has put
   ``RNF_vflx`` into ``runoff`` -- and before ``EXF_MAPFIELDS``. The dump
   is therefore the field the model goes on to apply;
2. the expected field is rebuilt here, independently of the model, as
   ``sum_s flux_s * frac_{s,c} / rA(c)`` from the sparse NetCDF file and
   the ``RAC.data`` of that same run. The terms are summed in the file's
   own table order, which is the order ``RNF_FIELDS_LOAD`` accumulates
   them in, so the two agree to the last bit and not merely to a
   tolerance;
3. the two are compared on every cell of the global layout. The check
   reports extra cells (the model applies runoff where the file asks for
   none), missing cells (the file asks for runoff the model does not
   apply) and the largest relative deviation, and fails on any non-zero
   extra or missing count.

A one-cell move shows up at once as one extra cell and one missing cell,
with a relative deviation of 1, while the total ``sum(applied * rA)``
still equals ``sum(flux)`` exactly.

**What the enrolled cases do not exercise.** The bitwise criterion rests
on the accumulation order: where several target entries feed one cell,
the reconstruction has to add the terms in the file's table order, which
is the order ``RNF_FIELDS_LOAD`` adds them in. Both committed sparse
files have at most **one** entry per cell (lab_sea 7 entries on 7 cells,
cs32 1189 on 1189), so no enrolled case ever sums more than one term and
none of them would notice if the order were wrong. The premise was
measured separately instead: on a file with three entries on one cell
whose smallest term is 0.3 ulp of the running sum, the model reproduces
the file-order sum bitwise while the reverse-order sum differs by exactly
1 ulp, with no extra and no missing cell (review A of RUNOFF-033,
lab_sea serial, 2026-10-05). So the order premise is true and
``--rtol 0`` is necessary rather than merely safe -- a tolerance would
hide precisely that 1 ulp. The nearest enrolled coverage is
``refusal_check.py``'s ``two_sources_one_cell``, at two terms, and
two-term addition is order-insensitive anyway.

That measurement was a scratch file that **nothing re-runs**, so what it
closed is the correctness question, not the regression coverage. If a
later change reordered how ``RNF_INIT_FIXED`` builds the per-tile
lists, the premise licensing ``--rtol 0`` would be void and all four
enrolled cases would still pass bitwise, because none of them sums two
terms into one cell. A permanent multi-entry case is filed against
RUNOFF-005; ``refusal_check.py::split_file`` already generates
multi-entry files at run time, so it needs no new committed input.

Each case runs the existing binary of its experiment through
``experiment_run_no_compile.sh``; nothing is compiled here. Build it first
with ``tests/mitgcm_oracle.sh <experiment> <input> [-mpi N]``. The scratch
input directory is layered on the experiment's sparse input and differs
from it only in output settings: ``data.diagnostics`` (the stream above),
and in ``data`` a ``writeBinaryPrec`` of 64, so that the dump and
``RAC.data`` are float64, and ``outputTypesInclusive`` so that the grid
files are written through MDS even where the set-up uses MNC. None of
these touches the solution.

The precision is checked, not assumed: a ``.meta`` that does not say
``float64`` fails the case rather than being read at a lower precision.

The number of dumps is checked too. A comparison over no cells, or over a
single dump, is not evidence, so a case needs at least ``--min-dumps``
dumps and at least one non-zero cell in each.

The scratch input and run directories are removed afterwards (``--keep``
leaves the run directories). Exit status: 0 if every case passes, 1 if any
fails or none ran, 2 if a binary is missing or a ``--case`` / ``--mpi``
selection does not exist.

Usage::

    python tests/rnf/applied_field_check.py [--mpi N] [--case NAME ...]
                                            [--keep] [--json] [--timeout S]
                                            [--rtol R] [--min-dumps N]
"""
import argparse
import glob
import json
import os
import re
import shutil
import stat
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (ROOT, VERIF, add_to_namelist, kill_run,  # noqa: E402
                           read_file, replace_line)

PREFIX = "input.rnfapply_"
BUILD = "build_esx"
STREAM = "rnfApply"
# Only this name, with a 10-digit iteration, is in scope for the dumps of
# the stream below. Anything else matching the glob is reported, never
# silently taken as a dump (LL-008).
DUMP_NAME = re.compile(r"^" + STREAM + r"\.(\d{10})\.data$")

#: The cases, named explicitly: this check never discovers an experiment.
#: ``data_from`` is the input directory holding the ``data`` the case runs
#: (for cs32 that is ``input.icedyn``, which its ``prepare_run`` links in,
#: not its own sparse input directory). ``mpi`` lists the process counts
#: the case is defined for; 0 is the single-process binary.
#: ``control_entry`` is the target entry the control moves one cell in x.
#: Both were measured on the committed files: the cell it lands on is wet,
#: is not already a target of the file, and has a ``rA`` that is bitwise
#: equal to the one it came from, so neither the land check nor the area
#: check of ``RNF_INIT_FIXED`` can see the move. For cs32 that is entry
#: 1035, cell 5247 -> 5248, which crosses the facet 2/3 boundary: the very
#: move the digit oracle accepts with 10 of 10 digits (RUNOFF-033).
CASES = (
    {"name": "lab_sea", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "mpi": (0, 2), "control_entry": 0},
    {"name": "cs32", "experiment": "global_ocean.cs32x15",
     "input": "input.rnof_sp_icedyn", "data_from": "input.icedyn",
     "mpi": (0, 4), "control_entry": 1035},
)

#: Name of the perturbed file the control makes the model read.
CONTROL_FILE = "moved_target.nc"

DATA_DIAGNOSTICS = """# Cell-exact applied-runoff oracle of
# tests/rnf/applied_field_check.py: dump the exf runoff field the model
# actually applies, as one global float64 array per time step.
#   diag_mnc = .FALSE. : through MDS, so the dump is a plain binary array
#   frequency < 0      : a snapshot, not a time average
#   fileFlags = 'D'    : float64 whatever writeBinaryPrec says
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
  fields(1,1) = 'EXFroff ',
  fileName(1) = '{stream}',
  frequency(1) = -{dt!r},
  fileFlags(1) = 'D       ',
 &

 &DIAG_STATIS_PARMS
 &
"""


def set_namelist(text, namelist, name, line):
    """Return ``text`` with namelist variable ``name`` set to ``line``.

    The variable is replaced where the file already sets it and inserted
    into ``&namelist`` where it does not, so that the result never holds
    two settings of one name.
    """
    active = [ln for ln in text.splitlines()
              if not ln.lstrip().startswith("#")
              and "=" in ln and ln.split("=")[0].strip().lower() == name.lower()]
    if active:
        return replace_line(text, name, line)
    return add_to_namelist(text, namelist, line)


def time_step(text):
    """Return ``deltaTClock`` of a ``data`` file, as a float.

    The dump frequency is this value, so that the model writes the applied
    field at every time step. Raises ``ValueError`` if it is not set.
    """
    match = re.search(r"^\s*deltaTClock\s*=\s*([-+0-9.DdEe]+)", text,
                      re.MULTILINE)
    if not match:
        raise ValueError("data does not set deltaTClock")
    return float(match.group(1).replace("D", "E").replace("d", "e"))


def rnf_file(text):
    """Return ``RNF_file`` of a ``data.rnf`` text, relative to the run dir."""
    match = re.search(r"^\s*RNF_file\s*=\s*'([^']+)'", text, re.MULTILINE)
    if not match:
        raise ValueError("data.rnf does not set RNF_file")
    return match.group(1)


def read_mds(run_dir, name, iteration=None):
    """Return an MDS 2-D field written by the model, as a flat float64 array.

    ``name`` is the file prefix and ``iteration`` the 10-digit suffix of a
    time-stamped file (``None`` for a grid file). The ``.meta`` gives the
    shape and the precision; a precision other than float64 raises
    ``ValueError`` instead of being read at face value, because the whole
    point of the comparison is that it is exact.
    """
    import numpy as np
    base = name if iteration is None else f"{name}.{iteration}"
    meta = read_file(run_dir, base + ".meta")
    if meta is None:
        raise ValueError(f"{base}.meta is missing from {run_dir}")
    prec = re.search(r"dataprec\s*=\s*\[\s*'([^']+)'", meta)
    if not prec or prec.group(1) != "float64":
        raise ValueError(f"{base}.meta says dataprec "
                         f"{prec and prec.group(1)!r}, not 'float64'")
    dims = re.search(r"dimList\s*=\s*\[(.*?)\]", meta, re.DOTALL)
    if not dims:
        raise ValueError(f"{base}.meta has no dimList")
    numbers = [int(v) for v in re.findall(r"-?\d+", dims.group(1))]
    if len(numbers) != 6:
        raise ValueError(f"{base}.meta is not a 2-D field: dimList has "
                         f"{len(numbers)} numbers")
    nx, ny = numbers[0], numbers[3]
    path = os.path.join(run_dir, base + ".data")
    field = np.fromfile(path, dtype=">f8")
    if field.size != nx * ny:
        raise ValueError(f"{base}.data holds {field.size} values, not "
                         f"nx*ny = {nx * ny}")
    return field.astype(np.float64), (nx, ny)


def dumps(run_dir):
    """Return the iterations of the stream's dumps, and anything unexpected.

    The glob is deliberately wider than the name the stream writes: a file
    that matches it without being a dump of this stream is returned in
    ``strays`` and fails the case, rather than being skipped unnoticed.

    A ``.meta`` is accepted as the companion of its own ``.data`` only
    when that ``.data`` is actually there. A half-written dump -- a
    ``.meta`` on its own -- would otherwise be neither counted nor
    reported, which would quietly lower the number of dumps compared.
    """
    iterations, strays = [], []
    for path in sorted(glob.glob(os.path.join(run_dir, STREAM + "*"))):
        base = os.path.basename(path)
        if base.endswith(".meta") and DUMP_NAME.match(base[:-5] + ".data"):
            if os.path.isfile(path[:-5] + ".data"):
                continue
            strays.append(base + " (no matching .data)")
            continue
        match = DUMP_NAME.match(base)
        if match:
            iterations.append(match.group(1))
        else:
            strays.append(base)
    return iterations, strays


def expected_field(path, rac, ncells):
    """Return the runoff field the sparse file asks for, in m/s.

    ``sum_s flux_s * frac_{s,c} / rA(c)``, accumulated over the target
    entries in the file's own order, which is the order the per-tile lists
    of ``RNF_INIT_FIXED`` are built in and therefore the order
    ``RNF_FIELDS_LOAD`` adds the terms in. Each term is
    ``(flux * frac) / rA`` in float64, as the Fortran writes it, so a
    correct model reproduces this array to the last bit.

    That the order matters is measured, not assumed: on a file with three
    entries on one cell, the model reproduces the file-order sum bitwise
    while the reverse-order sum differs by exactly 1 ulp with no extra
    and no missing cell (review A of RUNOFF-033, lab_sea serial,
    2026-10-05). It is also the reason ``--rtol`` defaults to 0: a
    tolerance would hide exactly that. Neither committed file exercises
    it -- both have at most one entry per cell -- so no enrolled case
    sums more than one term; see the module docstring.

    **One record only.** The reconstruction reads ``runoff_flux[0]`` and
    the caller compares every dump against it. That is correct while the
    reader accepts a single constant record, which is what
    ``RNF_INIT_FIXED`` enforces today, and it is fail-safe: a model that
    applied a different record would disagree. Time records arrive with
    RUNOFF-005 and this function then has to select per dump.

    Returns the field and the sum of the fluxes of the file, which the
    applied volume ``sum(applied * rA)`` has to equal.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(path) as ds:
        ds.set_auto_maskandscale(False)
        source = np.asarray(ds["target_source"][:]).astype(int)
        cell = np.asarray(ds["target_cell"][:]).astype(int)
        frac = np.asarray(ds["target_fraction"][:]).astype(np.float64)
        flux = np.asarray(ds["runoff_flux"][0], dtype=np.float64)
    if cell.min() < 0 or cell.max() >= ncells:
        raise ValueError(f"{path}: target_cell outside 0..{ncells - 1}")
    field = np.zeros(ncells, dtype=np.float64)
    for k in range(cell.size):
        field[cell[k]] += flux[source[k]] * frac[k] / rac[cell[k]]
    return field, float(flux.sum())


def move_one_target(source_path, path, entry):
    """Write a copy of the sparse file with one target moved one cell in x.

    Every dimension, variable and attribute is copied except
    ``target_lon`` and ``target_lat``, and ``target_cell[entry]`` is
    raised by one. This is the control's perturbation: the model is given
    this file while the comparison keeps asking for the committed one, so
    a correct model places one cell of runoff where the committed file
    does not ask for it and leaves the cell it does ask for empty.

    The two coordinate variables are dropped on purpose. They are
    optional in schema 1.0, and with them in place the cell-centre check
    of ``RNF_INIT_FIXED`` refuses this file at init, so the model would
    never run far enough to apply anything. Dropping them is also the
    honest statement of what this oracle is for: it is the check that
    still has margin when the file carries no coordinates to check
    against.

    Returns the id of the moved source and the two cells, for the report.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(source_path) as src, netCDF4.Dataset(path, "w") as dst:
        src.set_auto_maskandscale(False)
        dst.set_auto_maskandscale(False)
        dst.setncatts({k: src.getncattr(k) for k in src.ncattrs()})
        n = len(src.dimensions["target"])
        if not 0 <= entry < n:
            raise ValueError(f"{source_path}: control entry {entry} is "
                             f"outside the {n} target entries of the file")
        for name, dim in src.dimensions.items():
            dst.createDimension(name, None if dim.isunlimited() else len(dim))
        for name, var in src.variables.items():
            if name in ("target_lon", "target_lat"):
                continue
            atts = {k: var.getncattr(k) for k in var.ncattrs()}
            fill = atts.pop("_FillValue", None)
            out = dst.createVariable(name, var.dtype, var.dimensions,
                                     fill_value=fill)
            out.setncatts(atts)
            out[:] = var[:]
        was = int(dst["target_cell"][entry])
        dst["target_cell"][entry] = was + 1
        ids = [str(s) for s in netCDF4.chartostring(src["source_id"][:])]
        source = int(np.asarray(src["target_source"][:])[entry])
    return {"entry": entry, "source": ids[source], "from": was, "to": was + 1}


def run_model(experiment, input_name, nproc, timeout):
    """Run the scratch input; return ``(run dir, exit status, timed out)``."""
    output_name = "output_esx_" + input_name
    build, mpi_args = BUILD, []
    if nproc:
        output_name += f"_mpi{nproc}"
        build += f"_mpi{nproc}"
        mpi_args = ["-mpi", str(nproc)]
    run_dir = os.path.join(VERIF, experiment, output_name)
    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        proc = subprocess.run(
            ["./experiment_run_no_compile.sh", experiment, input_name]
            + mpi_args + ["-build", build, "-output", output_name],
            cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return run_dir, proc.returncode, False
    except subprocess.TimeoutExpired:
        kill_run(output_name)
        return run_dir, -1, True


def write_input(case, input_dir):
    """Build the scratch input directory of ``case``; return its ``data.rnf``.

    Every regular file of the case's sparse input directory is copied, then
    ``data`` is taken from ``data_from`` and given the two output settings
    the dump needs, and ``data.diagnostics`` is written. A ``prepare_run``
    is copied with ``data`` and ``data.diagnostics`` added to its skip
    list, so that it cannot link the originals over them.
    """
    exp_dir = os.path.join(VERIF, case["experiment"])
    base = os.path.join(exp_dir, case["input"])
    for name in sorted(os.listdir(base)):
        src = os.path.join(base, name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(input_dir, name))
    with open(os.path.join(exp_dir, case["data_from"], "data")) as fh:
        data = fh.read()
    dt = time_step(data)
    # float64 for the dump and for RAC.data, and MDS output even when the
    # set-up uses MNC (WRITE_GRID writes MDS grid files only when
    # outputTypesInclusive is set or MNC is off). Output settings only.
    data = set_namelist(data, "PARM01", "writeBinaryPrec",
                        " writeBinaryPrec=64,")
    data = set_namelist(data, "PARM03", "outputTypesInclusive",
                        " outputTypesInclusive=.TRUE.,")
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)
    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(DATA_DIAGNOSTICS.format(stream=STREAM, dt=dt))
    prep = os.path.join(input_dir, "prepare_run")
    if os.path.isfile(prep):
        with open(prep) as fh:
            text = fh.read()
        new, count = re.subn(r'skipList="([^"]*)"',
                             r'skipList="\1 data data.diagnostics"', text)
        if count != 1:
            raise ValueError(f"{case['input']}/prepare_run has {count} "
                             f"skipList assignments, expected 1: it would "
                             f"link over the case's own data files")
        with open(prep, "w") as fh:
            fh.write(new)
        os.chmod(prep, os.stat(prep).st_mode | stat.S_IXUSR | stat.S_IXGRP
                 | stat.S_IXOTH)
    with open(os.path.join(input_dir, "data.rnf")) as fh:
        return rnf_file(fh.read())


def compare(run_dir, sparse_path, iterations):
    """Compare every dump in ``run_dir`` with the field the file asks for.

    Returns a dictionary with one entry per dumped iteration plus the
    totals: ``extra`` and ``missing`` cell counts, the largest relative
    deviation, whether every dump was bitwise equal, how many applied
    values were not finite, and the applied volume against the sum of the
    fluxes.

    A non-finite applied value is turned into an infinite relative
    deviation before the maximum is taken. Left as a NaN it would lose
    every ``>`` comparison, so the reported maximum would stay 0.000e+00
    and hide a real deviation elsewhere in the same dump -- the same
    shape of mistake as a NaN-blind refusal in the model.
    """
    import numpy as np
    rac, shape = read_mds(run_dir, "RAC")
    ncells = rac.size
    expect, flux_sum = expected_field(sparse_path, rac, ncells)
    want_nonzero = int(np.count_nonzero(expect))
    result = {"cells": ncells, "shape": list(shape), "dumps": len(iterations),
              "nonzero_expected": want_nonzero, "flux_sum": flux_sum,
              "extra": 0, "missing": 0, "max_rel": 0.0, "bitwise": True,
              "nonfinite": 0, "worst": None, "volume": [], "per_dump": []}
    for iteration in iterations:
        applied, got_shape = read_mds(run_dir, STREAM, iteration)
        if got_shape != shape:
            raise ValueError(f"{STREAM}.{iteration} has shape {got_shape}, "
                             f"RAC.data has {shape}")
        extra = int(np.count_nonzero((applied != 0.0) & (expect == 0.0)))
        missing = int(np.count_nonzero((applied == 0.0) & (expect != 0.0)))
        bitwise = bool((applied == expect).all())
        nonfinite = int(np.count_nonzero(~np.isfinite(applied)))
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(expect != 0.0,
                           np.abs(applied - expect) / np.abs(expect),
                           np.where(applied != 0.0, 1.0, 0.0))
        rel = np.where(np.isfinite(rel), rel, np.inf)
        worst = int(np.argmax(rel))
        volume = float((applied * rac).sum())
        result["extra"] += extra
        result["missing"] += missing
        result["nonfinite"] += nonfinite
        result["bitwise"] = result["bitwise"] and bitwise
        result["volume"].append(volume)
        if float(rel[worst]) > result["max_rel"]:
            result["max_rel"] = float(rel[worst])
            result["worst"] = {"iteration": iteration, "cell": worst,
                               "applied": float(applied[worst]),
                               "expected": float(expect[worst])}
        result["per_dump"].append(
            {"iteration": iteration, "extra": extra, "missing": missing,
             "bitwise": bitwise, "nonfinite": nonfinite,
             "nonzero_applied": int(np.count_nonzero(applied)),
             "volume": volume})
    return result


def check_case(case, nproc, timeout, keep, rtol, min_dumps, control=False):
    """Run and judge one case; return the result dictionary.

    ``problems`` lists every unmet expectation, so an empty list is a pass.

    With ``control`` the model is given a file with one target moved one
    cell in x while the comparison still asks for the committed file. The
    verdict is then inverted: the control passes only when the check sees
    the move, as at least one extra and one missing cell. It is the
    evidence that a pass of this check means something.
    """
    name = f"{case['name']}" + (f"_mpi{nproc}" if nproc else "") \
        + ("_control" if control else "")
    input_name = PREFIX + name
    exp_dir = os.path.join(VERIF, case["experiment"])
    input_dir = os.path.join(exp_dir, input_name)
    shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir)
    result = {"case": case["name"], "processes": nproc, "control": control,
              "problems": []}
    problems = result["problems"]
    run_dir = None
    try:
        rnf_name = write_input(case, input_dir)
        # The committed file the case asks for. The model resolves
        # RNF_file from the run directory; the input directories and the
        # run directory are all siblings of the experiment directory, and
        # a bare name lives in the input directory, so resolving from
        # there names the same file without needing the run to exist yet.
        committed = os.path.normpath(
            os.path.join(exp_dir, case["input"], rnf_name))
        if not os.path.isfile(committed):
            raise ValueError(f"RNF_file {rnf_name!r} of "
                             f"{case['input']}/data.rnf does not resolve to "
                             f"a file ({committed})")
        if control:
            # The model reads the perturbed file; the comparison keeps
            # asking for the committed one.
            result["moved"] = move_one_target(
                committed, os.path.join(input_dir, CONTROL_FILE),
                case["control_entry"])
            path = os.path.join(input_dir, "data.rnf")
            with open(path) as fh:
                text = replace_line(fh.read(), "RNF_file",
                                    f"  RNF_file = '{CONTROL_FILE}',")
            with open(path, "w") as fh:
                fh.write(text)
        run_dir, run_exit, timed_out = run_model(
            case["experiment"], input_name, nproc, timeout)
        logs = "\n".join(filter(None, (
            read_file(run_dir, n) for n in ("output.txt", "mpirun.log"))))
        result["ended_normally"] = "Execution ended Normally" in logs
        result["run_exit"] = run_exit
        if timed_out:
            problems.append("the run to finish (it timed out: a process hangs)")
            return result
        if not result["ended_normally"] or run_exit != 0:
            problems.append(f"the run to end normally (exit {run_exit})")
            return result
        iterations, strays = dumps(run_dir)
        result["dumps"] = len(iterations)
        if strays:
            problems.append(f"only dumps of the {STREAM} stream to match "
                            f"{STREAM}*: {strays[:5]} are out of scope")
            return result
        if len(iterations) < min_dumps:
            problems.append(f"at least {min_dumps} dumps of the applied "
                            f"field (found {len(iterations)}); fewer is not "
                            f"evidence")
            return result
        result.update(compare(run_dir, committed, iterations))
        result["sparse_file"] = os.path.relpath(committed, ROOT)
        if result["nonzero_expected"] == 0:
            problems.append("the file to ask for runoff on at least one "
                            "cell (it asks for none: nothing is compared)")
        for dump in result["per_dump"]:
            if dump["nonzero_applied"] == 0:
                problems.append(f"every dump to apply runoff somewhere "
                                f"(dump {dump['iteration']} is all zero)")
                break
        # Before the control branch returns: a dump holding a value that is
        # not a number is a failure either way. A control run would
        # otherwise satisfy its inverted verdict on the extra and missing
        # counts while the field it compared was partly garbage.
        if result["nonfinite"]:
            problems.append(f"every applied value to be finite (found "
                            f"{result['nonfinite']} that are not, over "
                            f"{result['dumps']} dumps)")
        if control:
            # Inverted: the move has to be seen, on every dump, as the one
            # cell gained and the one cell lost. Mass is still conserved,
            # which is exactly why the digit oracle cannot see this.
            if not all(d["extra"] >= 1 and d["missing"] >= 1
                       for d in result["per_dump"]):
                problems.append(
                    f"the moved target to show up on every dump as an "
                    f"extra and a missing cell (found "
                    f"{result['extra']} extra and {result['missing']} "
                    f"missing over {result['dumps']} dumps): the check "
                    f"cannot see a one-cell move, so a pass of it means "
                    f"nothing")
            if result["max_rel"] <= rtol:
                problems.append(f"a relative deviation above {rtol:g} "
                                f"(found {result['max_rel']:.3e})")
            return result
        if result["extra"] or result["missing"]:
            problems.append(f"no cell to differ in placement (found "
                            f"{result['extra']} extra and "
                            f"{result['missing']} missing)")
        if result["max_rel"] > rtol:
            problems.append(f"a relative deviation of at most {rtol:g} "
                            f"(found {result['max_rel']:.3e} at "
                            f"{result['worst']})")
        for volume in result["volume"]:
            if volume != result["flux_sum"]:
                problems.append(f"the applied volume to equal the sum of "
                                f"the fluxes ({result['flux_sum']!r}); "
                                f"found {volume!r}")
                break
        return result
    except ValueError as err:
        problems.append(str(err))
        result["unusable"] = True
        return result
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)
        if run_dir and not keep:
            shutil.rmtree(run_dir, ignore_errors=True)


def main(argv=None):
    """Check the selected cases and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mpi", type=int, default=0, metavar="N",
                        help="run on N MPI processes with build_esx_mpiN "
                             "(default 0: the single-process binary)")
    parser.add_argument("--case", action="append", default=[],
                        help="check only this case (repeatable)")
    parser.add_argument("--keep", action="store_true",
                        help="keep the run directories")
    parser.add_argument("--json", action="store_true",
                        help="print the full results as JSON")
    parser.add_argument("--timeout", type=float, default=1200.0, metavar="S",
                        help="seconds after which a run counts as hanging")
    parser.add_argument("--rtol", type=float, default=0.0, metavar="R",
                        help="largest relative deviation that still passes "
                             "(default 0: the applied field must be bitwise "
                             "the field the file asks for; a non-zero value "
                             "weakens the check)")
    parser.add_argument("--min-dumps", type=int, default=2, metavar="N",
                        help="dumps a case needs (default 2)")
    parser.add_argument("--no-control", action="store_true",
                        help="skip the control run of each case, the one "
                             "that moves a target by one cell and must be "
                             "detected; it halves the runtime and leaves "
                             "the check unproven on this run")
    args = parser.parse_args(argv)

    if args.mpi < 0:
        parser.error("--mpi needs a positive process count")
    if args.min_dumps < 1:
        # With 0 a case that dumped nothing would report PASS with nothing
        # compared, which is the one verdict this check must never give.
        parser.error("--min-dumps needs at least 1 dump: a case that "
                     "compares no dump is not evidence")
    selected = list(CASES)
    if args.case:
        unknown = set(args.case) - {c["name"] for c in CASES}
        if unknown:
            print(f"unknown case(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        selected = [c for c in CASES if c["name"] in args.case]
    undefined = [c["name"] for c in selected if args.mpi not in c["mpi"]]
    if undefined:
        print(f"case(s) {undefined} are not defined for --mpi {args.mpi}; "
              f"defined: "
              + ", ".join(f"{c['name']}: {list(c['mpi'])}" for c in CASES),
              file=sys.stderr)
        return 2
    for case in selected:
        build = BUILD + (f"_mpi{args.mpi}" if args.mpi else "")
        binary = os.path.join(VERIF, case["experiment"], build, "mitgcmuv")
        if not os.path.isfile(binary):
            mpi = f" -mpi {args.mpi}" if args.mpi else ""
            print(f"missing {binary}: run tests/mitgcm_oracle.sh "
                  f"{case['experiment']} {case['input']}{mpi}",
                  file=sys.stderr)
            return 2

    results = []
    for case in selected:
        results.append(check_case(case, args.mpi, args.timeout, args.keep,
                                  args.rtol, args.min_dumps))
        if not args.no_control:
            results.append(check_case(case, args.mpi, args.timeout,
                                      args.keep, args.rtol, args.min_dumps,
                                      control=True))
    for res in results:
        verdict = "FAIL" if res["problems"] else "PASS"
        where = res["case"] + (f" on {res['processes']} processes"
                               if res["processes"] else " on 1 process")
        if res["control"]:
            moved = res.get("moved") or {}
            where += (f", control: entry {moved.get('entry')} "
                      f"({moved.get('source')}) moved "
                      f"{moved.get('from')} -> {moved.get('to')}")
        print(f"{verdict} {where}: {res.get('dumps', 0)} dumps of "
              f"{res.get('cells', 0)} cells, "
              f"{res.get('nonzero_expected', 0)} with runoff, "
              f"{res.get('extra', 0)} extra, {res.get('missing', 0)} missing, "
              f"max relative deviation {res.get('max_rel', float('nan')):.3e}"
              + (f", {res['nonfinite']} not finite"
                 if res.get("nonfinite") else "")
              + (", bitwise equal" if res.get("bitwise") else ""))
        for msg in res["problems"]:
            print(f"     missing: {msg}")
    if args.json:
        print(json.dumps(results, indent=1))
    failed = [r["case"] for r in results if r["problems"]]
    print(f"{len(results) - len(failed)} of {len(results)} cases passed")
    if any(r.get("unusable") for r in results):
        return 2
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
