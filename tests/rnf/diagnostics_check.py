#!/usr/bin/env python3
"""Direct oracle of RUNOFF-015: the input-field diagnostics and the monitor.

RUNOFF-031 registered and filled the three surface-flux diagnostics
(``RNFqnet``, ``RNFsflx``, ``RNFtfNN``); ``tests/rnf/budget_check.py``
measures those by inversion, because the only thing that is dumped on
that side is the term the model applies. RUNOFF-015 adds the five
input-field diagnostics (``RNFvflx``, ``RNFmflx``, ``RNFtemp``,
``RNFsaln``, ``RNFnsrc``) and ``RNF_MONITOR``, and this check measures
*those* directly: each one is itself dumped, so the oracle is a plain
reconstruction from the file and the grid, not an inversion of a term
that depends on them.

Two lab_sea sparse cases
=========================

Both reuse the committed target table of ``lab_sea/input.rnof_const``
(4 sources, 7 target cells; ``tests/rnf/budget_check.read_table``), with
their own short, interpolated flux series (``tests/rnf/budget_check.series``):

* ``lab_sea_ts`` carries a runoff temperature and salinity, so
  ``RNFtemp``/``RNFsaln`` are exercised at a defined (non-zero) value
  on every target cell;
* ``lab_sea_novar`` carries neither variable at all (``RNF_hasTemp`` and
  ``RNF_hasSalt`` both false), so every target cell is the "runoff
  present, no temperature anywhere" case this package's own convention
  calls undefined (0), and ``RNFsaln`` is 0 by the ``S = 0`` convention
  (model contract) rather than by the undefined-value rule -- the two
  are numerically the same (0) but mean different things, which is
  exactly why a single case could not stand for the other.

Every other cell of the grid (313 of 320) has no runoff at all, so both
cases also exercise the "no runoff" undefined case on every dump, for
free.

What is compared, and to what tolerance
========================================

Per dump, per cell, against :func:`tests/rnf/budget_check.dense_fields`,
built from the file's own source series combined with the weight
``RNF_FIELDS_LOAD`` reported for that step (:func:`record_trace`, as
``applied_field_check`` already does) and the run's own ``RAC.data``:

* ``RNFvflx`` against ``EXFroff``, bitwise (decision 8: "equals EXFroff
  before controls", and no control is active in any of these runs);
* ``RNFmflx`` against ``rhoConstFresh*RNFvflx_oracle``, 1e-12 relative;
* ``RNFtemp`` against ``(mT)/m_T`` where ``m_T > 0``, else 0, 1e-12
  relative (the ``rA`` factor of ``(mT)`` and ``m_T`` cancels in the
  ratio, so this comparison does not depend on the grid at all, only
  the undefined-cell convention does);
* ``RNFsaln`` against ``(mS)/m`` where ``m > 0``, else 0, 1e-12
  relative, same cancellation;
* ``RNFnsrc`` against the number of target entries owning the cell
  (schema rule T03: no duplicate ``(source, cell)`` pair, so this is
  also the number of distinct sources), exact equality -- not a
  tolerance, because it is a count.

The monitor is compared at every dump (``RNF_monFreq`` is left at its
default, ``monitorFreq``, which both cases set equal to the time step,
so the monitor fires at every step the diagnostics are dumped at)
against the same file's source sums, built the same way
(:func:`tests/rnf/budget_check.source_series`), to 1e-12 relative. On 1
and 2 processes alike, and the printed ``%MON rnf_*`` text itself (the
name and the value field, with the per-process ``(PID.TID ...)`` tag
stripped, which is the part no two process counts could be asked to
agree on) is required to be bitwise identical between the two runs, so
"the sums are independent of tiling and MPI layout" is checked on the
actual text and not only on a value parsed from it.

Must-fail demonstrations
=========================

Two mutant builds, each a one-line change made with a regex
substitution asserted to match exactly once, so this check's own
mutant cannot silently fail to compile the fault in:

* ``--mutant temp``: ``RNF_DIAGNOSTICS_FILL`` divides ``(mT)`` by
  ``RNF_mflx`` (the whole mass flux) instead of ``RNF_mflxT`` (the
  valid-temperature share), i.e. the issue's own example. On
  ``lab_sea_ts`` every source has a temperature, so ``RNF_mflxT`` equals
  ``RNF_mflx`` there and the mutant is invisible; on ``lab_sea_novar``
  ``RNF_mflxT`` is 0 while ``RNF_mflx`` is not, so the mutant divides by
  the wrong, non-zero denominator at every target cell and must be
  caught.
* ``--mutant monitor``: ``RNF_MONITOR`` drops the ``rA`` weight from the
  salt sum (``Sum (mS)`` instead of ``Sum (mS)*rA``), which is wrong
  whenever ``rA`` is not uniformly 1 -- true on every target cell of
  lab_sea's lat-lon grid -- and must be caught by the monitor-sum
  comparison.

Each mutant is run on exactly one case (``lab_sea_novar`` for ``temp``,
``lab_sea_ts`` for ``monitor``) through ``--use-build``-style binary
substitution and must fail the comparison the plain run passes.

No-change
=========

This check never edits ``pkg/rnf`` or ``pkg/exf`` source and the model
state it reads (``RAC.data``, the state dumps the oracle does not even
open) is produced by the committed binary and compared with nothing;
it adds a diagnostics stream and reads ``STDOUT``, neither of which
``tests/mitgcm_oracle.sh`` compares (``docs/verification_matrix.md``).

Usage
=====

    python3 tests/rnf/diagnostics_check.py [--case NAME ...] [--mpi N]
                                           [--mutant temp|monitor]
                                           [--build] [--keep] [--json PATH]
                                           [--timeout S]

Exit status: 0 if every selected run met its own expectations (a must-fail
mutant passing counts as a failure), 1 if one did not or none ran, 2 if a
binary is missing, could not be built, or a selection does not exist.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (ROOT, VERIF, add_to_namelist,  # noqa: E402
                           kill_run, read_file, replace_line)
from applied_field_check import (dump_name, dump_iteration,  # noqa: E402
                                 record_trace, set_namelist, time_step)
from budget_check import dense_fields, read_table, series, source_series  # noqa: E402,E501
from tendency_term_check import (build_if_stale, exf_options,  # noqa: E402
                                 param, report_build, write_mods_code,
                                 BUILD as ROFT_BUILD)

#: The scratch input directories this check writes, one per run.
PREFIX = "input.rnfdiag_"
#: The ordinary binary. Neither case needs ALLOW_RUNOFTEMP: RNFtemp is
#: this package's own diagnostic, filled by RNF_DIAGNOSTICS_FILL (no
#: ALLOW_RUNOFTEMP guard), not by the ALLOW_RUNOFTEMP block of
#: RNF_EXF_RUNOFF that fills the exf runoftemp field. So the plain
#: lab_sea binary that tests/mitgcm_oracle.sh builds is enough.
BUILD = "build_esx"
#: Committed sparse file whose target table every case reuses (as
#: tests/rnf/budget_check.CASES do): 4 sources, 7 target cells.
TABLE_FROM = ("lab_sea", "input.rnof_const", "runoff_sparse.nc")
#: Mods-code directories of the two mutant builds, and the builds
#: compiled from them.
MUTANT_CODE = {"temp": "code_rnfdiag_mut_temp",
              "monitor": "code_rnfdiag_mut_monitor"}
MUTANT_BUILD = {"temp": "build_esx_mut_rnfdiag_temp",
                "monitor": "build_esx_mut_rnfdiag_monitor"}
#: Diagnostic stream names, one file per field.
STREAMS = {"vflx": "rnfDgVfl", "roff": "rnfDgRof", "mflx": "rnfDgMfl",
          "temp": "rnfDgTmp", "saln": "rnfDgSln", "nsrc": "rnfDgNsr"}
#: Relative tolerance of RNFmflx, RNFtemp and RNFsaln against the
#: reconstruction, and of the monitor sums (RUNOFF-015 acceptance).
RTOL = 1.0e-12

DATA_DIAGNOSTICS = """# Direct diagnostics oracle of tests/rnf/diagnostics_check.py.
# One snapshot stream per field (frequency < 0), at every time step,
# through MDS (diag_mnc = .FALSE.) in float64 (fileFlags 'D'):
#   EXFroff  :: the exf runoff field (RNF_vflx, before controls)
#   RNFvflx  :: the package's own diagnostic of the same field
#   RNFmflx  :: mass flux, rhoConstFresh*RNFvflx
#   RNFtemp  :: (mT)/m_T where m_T > 0, else 0
#   RNFsaln  :: (mS)/m where m > 0, else 0
#   RNFnsrc  :: number of sources feeding the cell
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
  fields(1,1) = 'EXFroff ',
  fileName(1) = '{roff}',
  frequency(1) = -{dt!r},
  fileFlags(1) = 'D       ',
  fields(1,2) = 'RNFvflx ',
  fileName(2) = '{vflx}',
  frequency(2) = -{dt!r},
  fileFlags(2) = 'D       ',
  fields(1,3) = 'RNFmflx ',
  fileName(3) = '{mflx}',
  frequency(3) = -{dt!r},
  fileFlags(3) = 'D       ',
  fields(1,4) = 'RNFtemp ',
  fileName(4) = '{temp}',
  frequency(4) = -{dt!r},
  fileFlags(4) = 'D       ',
  fields(1,5) = 'RNFsaln ',
  fileName(5) = '{saln}',
  frequency(5) = -{dt!r},
  fileFlags(5) = 'D       ',
  fields(1,6) = 'RNFnsrc ',
  fileName(6) = '{nsrc}',
  frequency(6) = -{dt!r},
  fileFlags(6) = 'D       ',
 &

 &DIAG_STATIS_PARMS
 &
"""

#: The two cases. ``with_ts`` controls whether :func:`write_sparse` writes
#: runoff_temperature/runoff_salinity at all; ``records``/``period`` are
#: the time axis of tests/rnf/budget_check.series (a fixed period of
#: ``period`` time steps, so the model moves through records and
#: interpolates); ``steps`` the run length; ``min_records`` the number of
#: distinct record selections the run must make, as a guard against a
#: run that never changes record and so cannot show the comparison holds
#: at more than one.
CASES = (
    # The file carries runoff_temperature, so RNF_CHECK requires
    # ALLOW_RUNOFTEMP whether or not the heat term itself is used
    # (rnf_check.F): this case runs on ROFT_BUILD, the lab_sea binary
    # tests/rnf/tendency_term_check and tests/rnf/budget_check already
    # build with it defined.
    {"name": "lab_sea_ts", "with_ts": True, "build": ROFT_BUILD,
     "records": 5, "period": 2, "steps": 6, "min_records": 2,
     "mpi": (0, 2)},
    # No runoff_temperature or runoff_salinity variable at all, so the
    # plain binary (no ALLOW_RUNOFTEMP needed) is enough.
    {"name": "lab_sea_novar", "with_ts": False, "build": BUILD,
     "records": 5, "period": 2, "steps": 6, "min_records": 2,
     "mpi": (0, 2)},
    # Two sources sharing one target cell, one of them always missing
    # its temperature (:func:`mixed_table`): the one configuration
    # where RNF_mflxT and RNF_mflx genuinely differ at a target cell
    # (0 < m_T < m), so RNFtemp has a defined, non-degenerate value
    # there. This is what the "temp" mutant needs: on every other case
    # here every target cell is single-source, so m_T is either 0 or
    # exactly m and (mT)/m_T and (mT)/m cannot be told apart.
    {"name": "lab_sea_mixed", "with_ts": True, "build": ROFT_BUILD,
     "custom_table": True, "missing": {0: "all"},
     "records": 5, "period": 2, "steps": 6, "min_records": 2,
     "mpi": (0, 2)},
)
#: Which case each mutant is run on, and the field the mutant is
#: supposed to corrupt (named for the report only).
MUTANT_CASE = {"temp": "lab_sea_mixed", "monitor": "lab_sea_ts"}


def mutant_series_case(case):
    """Return a ``tests/rnf/budget_check.series``-compatible case dict.

    ``series``/``source_series`` read ``case["ptracers"]`` and
    ``case["file_tracers"]`` (empty here: these cases carry no runoff
    tracer) besides ``records``, ``period`` and ``missing``.
    """
    return dict(case, ptracers=(), file_tracers=(), missing=case.get("missing"))


def mixed_table(table):
    """Return a two-source, one-cell table built for the "mixed" case.

    The committed table has at most one source per target cell (no two
    rows share a ``target_cell``), so ``RNF_mflxT`` of any one cell is
    either exactly 0 (its one source lacks a temperature) or exactly
    ``RNF_mflx`` (it has one): the two denominators of the ``RNFtemp``
    ratio, ``m_T`` and ``m``, never actually differ at a single-source
    cell, so a mutant dividing by the wrong one cannot be told apart
    there. Two sources sharing one cell -- here, cell 52, confirmed wet
    by the committed table's own "newfound" entry -- gives
    ``0 < m_T < m`` whenever one source has a temperature and the
    other does not (``case["missing"] = {0: "all"}`` on this table),
    which is what the mutant check needs. Grid size and the flux scale
    (``flux1``) are taken from the committed table, which is otherwise
    unused by this case.
    """
    import numpy as np
    return {
        "ids": ["mixedA", "mixedB"],
        "target_source": np.array([0, 1], dtype=int),
        "target_cell": np.array([52, 52], dtype=int),
        "target_fraction": np.array([1.0, 1.0]),
        "nx": table["nx"], "ny": table["ny"],
        "flux1": np.array([table["flux1"][0], table["flux1"][0]]),
        "nsrc": 2,
    }


def write_sparse(path, table, case, dt):
    """Write the sparse runoff file of one case: flux, and T/S if asked.

    The target table and its fractions are the committed one, unperturbed
    (unlike ``tests/rnf/budget_check.write_sparse``, this check runs no
    fraction control). The flux, temperature and salinity series are
    ``tests/rnf/budget_check.series``'s, written over a fixed period of
    ``case["period"]`` time steps anchored on the model's own calendar
    start (``lab_sea/input/data.cal``: 1979-01-01), as
    ``tests/rnf/budget_check.write_sparse`` and
    ``tests/rnf/tendency_term_check.write_sparse`` both do, for the same
    reason: the record the model selects for a step is then a function
    of the step alone.
    """
    import netCDF4
    import numpy as np
    value = series(table, mutant_series_case(case))
    nrec, nsrc = value["flux"].shape
    with netCDF4.Dataset(path, "w") as ds:
        ds.set_auto_maskandscale(False)
        ds.setncatts({
            "mitgcm_runoff_schema_version": "1.0",
            "mitgcm_grid_nx": np.int32(table["nx"]),
            "mitgcm_grid_ny": np.int32(table["ny"]),
            "mitgcm_time_sampling": "fixed",
            "mitgcm_time_period": np.float64(case["period"] * dt),
            "mitgcm_time_repeat": "none",
            "title": "sparse runoff for tests/rnf/diagnostics_check.py"
                     + ("" if case["with_ts"] else " (no temperature or "
                        "salinity)")})
        ds.createDimension("time", nrec)
        ds.createDimension("source", nsrc)
        ds.createDimension("target", table["target_cell"].size)
        width = max(len(s) for s in table["ids"])
        ds.createDimension("id_strlen", width)
        ds.createDimension("nv", 2)
        time = ds.createVariable("time", "f8", ("time",))
        time.units = "seconds since 1979-01-01 00:00:00"
        time.calendar = "gregorian"
        time.axis = "T"
        time.bounds = "time_bnds"
        period = case["period"] * dt
        time[:] = period * np.arange(nrec, dtype=np.float64)
        bnds = ds.createVariable("time_bnds", "f8", ("time", "nv"))
        bnds.units = time.units
        bnds.calendar = time.calendar
        bnds[:] = np.stack([time[:], time[:] + period], axis=1)
        ids = np.array([list(s.ljust(width)) for s in table["ids"]],
                       dtype="S1")
        ds.createVariable("source_id", "S1", ("source", "id_strlen"))[:] = ids
        ds.createVariable("target_source", "i4",
                          ("target",))[:] = table["target_source"]
        ds.createVariable("target_cell", "i4",
                          ("target",))[:] = table["target_cell"]
        out = ds.createVariable("target_fraction", "f8", ("target",))
        out.units = "1"
        out[:] = table["target_fraction"]
        for name, units in (("target_cell_area", "m2"),
                            ("target_lon", "degrees_east"),
                            ("target_lat", "degrees_north")):
            if name in table:
                out = ds.createVariable(name, "f8", ("target",))
                out.units = units
                out[:] = table[name]
        out = ds.createVariable("runoff_flux", "f8", ("time", "source"))
        out.units = "m3 s-1"
        out[:] = value["flux"]
        if case["with_ts"]:
            fill = np.float64(-9999.0)
            out = ds.createVariable("runoff_temperature", "f8",
                                    ("time", "source"), fill_value=fill)
            out.units = "degC"
            # A source listed in case["missing"] stores the fill value
            # at the records series() marks invalid for it (tvld == 0),
            # as tests/rnf/budget_check.write_sparse does: without this,
            # the file would carry a real (if make-believe) temperature
            # for a source this case means to have none, and the model
            # would use it instead of the surface reference, which is
            # not what oracle_at (and series' own tvld) assume.
            out[:] = np.where(value["tvld"] > 0.0, value["temp"], fill)
            out = ds.createVariable("runoff_salinity", "f8",
                                    ("time", "source"))
            out.units = "g kg-1"
            out[:] = value["salt"]


def write_input(case, input_dir, table, dt_hint=None):
    """Build the scratch input directory of one case; return the step size.

    Layered on ``lab_sea/input.rnof_sp_const`` exactly as
    ``tests/rnf/budget_check.write_input`` is on its own ``data_from``:
    every regular file is copied, then ``data``, ``data.diagnostics``
    and ``data.rnf`` are written or rewritten. ``RNF_monFreq`` is left
    unset (default ``monitorFreq``), and ``monitorFreq`` itself is set
    to the time step, so ``RNF_MONITOR`` fires at every step the
    diagnostics streams are dumped at.
    """
    exp_dir = os.path.join(VERIF, "lab_sea")
    base = os.path.join(exp_dir, "input.rnof_sp_const")
    for name in sorted(os.listdir(base)):
        src = os.path.join(base, name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(input_dir, name))
    with open(os.path.join(base, "data")) as fh:
        data = fh.read()
    dt = time_step(data)
    settings = [
        ("PARM01", "writeBinaryPrec", " writeBinaryPrec=64,"),
        ("PARM03", "outputTypesInclusive", " outputTypesInclusive=.TRUE.,"),
        ("PARM03", "dumpFreq", f" dumpFreq={dt!r},"),
        ("PARM03", "dumpInitAndLast", " dumpInitAndLast=.TRUE.,"),
        ("PARM03", "pChkptFreq", " pChkptFreq=0.,"),
        ("PARM03", "chkptFreq", " chkptFreq=0.,"),
        ("PARM03", "monitorFreq", f" monitorFreq={dt!r},"),
    ]
    # The run length. Both forms are set where the base `data` uses
    # them (tests/rnf/budget_check.write_input does the same), so the
    # one the set-up actually reads is the one that is shortened.
    if re.search(r"(?m)^\s*nTimeSteps\s*=", data):
        settings.append(("PARM03", "nTimeSteps",
                         f" nTimeSteps={case['steps']},"))
    start = re.search(r"(?m)^\s*startTime\s*=\s*([-+0-9.DdEe]+)", data)
    if start and not re.search(r"(?m)^\s*nTimeSteps\s*=", data):
        t0 = float(start.group(1).replace("D", "E").replace("d", "e"))
        settings.append(("PARM03", "endTime",
                         f" endTime={t0 + case['steps'] * dt!r},"))
    for namelist, name, line in settings:
        data = set_namelist(data, namelist, name, line)
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)
    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(DATA_DIAGNOSTICS.format(dt=dt, **STREAMS))
    pkg = read_file(input_dir, "data.pkg")
    if pkg is None:
        raise ValueError("input.rnof_sp_const has no data.pkg")
    for name, value in (("useDiagnostics", ".TRUE."), ("useRNF", ".TRUE."),
                        ("useMNC", ".FALSE.")):
        line = f"  {name} = {value},"
        pkg = (replace_line(pkg, name, line)
               if re.search(r"(?mi)^\s*%s\s*=" % re.escape(name), pkg)
               else add_to_namelist(pkg, "PACKAGES", line))
    with open(os.path.join(input_dir, "data.pkg"), "w") as fh:
        fh.write(pkg)
    prep = os.path.join(input_dir, "prepare_run")
    if os.path.isfile(prep):
        with open(prep) as fh:
            text = fh.read()
        new, count = re.subn(
            r'skipList="([^"]*)"',
            r'skipList="\1 data data.diagnostics data.pkg"', text)
        if count != 1:
            raise ValueError(f"input.rnof_sp_const/prepare_run has {count} "
                             f"skipList assignments, expected 1")
        with open(prep, "w") as fh:
            fh.write(new)
        os.chmod(prep, os.stat(prep).st_mode | 0o111)
    write_sparse(os.path.join(input_dir, "runoff_diag.nc"), table, case, dt)
    with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
        fh.write("# Written by tests/rnf/diagnostics_check.py.\n"
                 "# RNF_debugLev = 3 (debLevC) makes RNF_FIELDS_LOAD print,\n"
                 "# at every step, the records it bracketed and the weight\n"
                 "# of the earlier one, which this check reads to rebuild\n"
                 "# the source series of that step. It only prints and\n"
                 "# changes no value.\n"
                 " &RNF_PARM01\n"
                 "  RNF_file = 'runoff_diag.nc',\n"
                 "  RNF_debugLev = 3,\n"
                 " &\n")
    return dt


def run_model(input_name, nproc, timeout, build=BUILD):
    """Run one scratch input; return ``(run dir, exit status, timed out)``."""
    output_name = "output_esx_" + input_name
    mpi_args = []
    if nproc:
        output_name += f"_mpi{nproc}"
        build += f"_mpi{nproc}"
        mpi_args = ["-mpi", str(nproc)]
    run_dir = os.path.join(VERIF, "lab_sea", output_name)
    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        proc = subprocess.run(
            ["./experiment_run_no_compile.sh", "lab_sea", input_name]
            + mpi_args + ["-build", build, "-output", output_name],
            cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return run_dir, proc.returncode, False
    except subprocess.TimeoutExpired:
        kill_run(output_name)
        return run_dir, -1, True


def read_mds(run_dir, name):
    """Return a 2-D float64 MDS field, as ``tests/rnf/applied_field_check``
    reads one -- imported locally to avoid a name clash with
    ``tests/rnf/tendency_term_check.read_mds``, which reads a 3-D field."""
    import applied_field_check
    return applied_field_check.read_mds(run_dir, name)


def dumps_of(run_dir, stream):
    """Return the sorted dump iterations of one stream, and any strays."""
    import glob
    pattern = dump_name(stream)
    iterations, strays = [], []
    for path in sorted(glob.glob(os.path.join(run_dir, stream + "*"))):
        base = os.path.basename(path)
        if base.endswith(".meta") and pattern.match(base[:-5] + ".data"):
            if os.path.isfile(path[:-5] + ".data"):
                continue
            strays.append(base + " (no matching .data)")
            continue
        match = pattern.match(base)
        if match:
            iterations.append(match.group(1))
        else:
            strays.append(base)
    return iterations, strays


def monitor_blocks(text):
    """Return the parsed ``%MON rnf_*`` blocks of ``output.txt``, in order.

    Each block starts at ``rnf_tsnumber`` (``RNF_MONITOR``'s first line)
    and holds every ``rnf_*`` name seen before the next one, as
    ``{"iter": int, "lines": [(name, raw_value_text), ...], "values":
    {name: float}}``. ``lines`` keeps the raw printed text (name and
    value, with the leading ``(PID.TID ...)`` tag and the ``%MON``
    marker stripped) so two runs can be compared on the text itself and
    not only on the parsed numbers.
    """
    blocks = []
    current = None
    for line in text.splitlines():
        match = re.search(r"%MON\s+(rnf_\S+)\s*=\s*(\S+)", line)
        if not match:
            continue
        name, raw = match.group(1), match.group(2)
        value = float(raw.replace("D", "E").replace("d", "e"))
        if name == "rnf_tsnumber":
            if current is not None:
                blocks.append(current)
            current = {"iter": int(round(value)), "lines": [], "values": {}}
        if current is None:
            continue
        current["lines"].append(f"{name}={raw}")
        current["values"][name] = value
    if current is not None:
        blocks.append(current)
    return blocks


def oracle_at(table, case, rac, ncells, records):
    """Return the oracle's five fields at one dump, from the file alone.

    ``records`` is ``(rec0, year0, rec1, year1, fac)`` as
    ``RNF_FIELDS_LOAD`` reported it (:func:`applied_field_check.record_trace`).
    Built from ``tests/rnf/budget_check.source_series`` and
    ``tests/rnf/budget_check.dense_fields``, which do the interpolation
    and the per-cell accumulation the way ``RNF_LOAD_AT`` does
    (rnf_fields_load.F:325-392, :446-471). ``RNFtemp``/``RNFsaln`` do not
    depend on ``rA``: it is the same factor of ``(mT)``/``m_T`` (and of
    ``(mS)``/``m``) and cancels in the ratio.

    ``case["with_ts"]`` false (``lab_sea_novar``) means the file carries
    no ``runoff_temperature``/``runoff_salinity`` variable at all, so
    the model never accumulates ``RNF_mflxT``/``RNF_mXT``/``RNF_mXS``
    for any source (``RNF_hasTemp``/``RNF_hasSalt`` both false,
    ``rnf_fields_load.F:340`` and ``:365``); ``series`` computes a
    temperature and salinity series unconditionally (it is shared with
    ``tests/rnf/budget_check``, where every case has them), so this
    routine, and not ``series``, is where "the file does not carry
    this at all" is applied, by zeroing those sums before the ratio.

    Returns ``{"vflx": .., "mflx": .., "temp": .., "saln": ..,
    "nsrc": ..}``, each a float64 array of length ``ncells``, plus the
    monitor's own global sums over sources, ``{"volsum": .., "heatsum":
    .., "saltsum": ..}`` in the file's own units (no ``Cp``: the monitor
    multiplies by it, so the caller does too before comparing).
    """
    import numpy as np
    oracle_case = mutant_series_case(case)
    source = source_series(table, oracle_case, records)
    want = dense_fields(table, source, rac, ncells)
    mflxt = want["mflxT"]
    mXT = want["mXT"]
    mXS = want["mXS"]
    tvld = source["tvld"]
    salt = source["salt"]
    if not case["with_ts"]:
        mflxt = np.zeros_like(mflxt)
        mXT = np.zeros_like(mXT)
        mXS = np.zeros_like(mXS)
        tvld = np.zeros_like(tvld)
        salt = np.zeros_like(salt)
    mflxt_pos = mflxt > 0.0
    vflx_pos = want["vflx"] > 0.0
    temp = np.where(mflxt_pos, mXT / np.where(mflxt_pos, mflxt, 1.0), 0.0)
    saln = np.where(vflx_pos, mXS / np.where(vflx_pos, want["vflx"], 1.0),
                    0.0)
    nsrc = np.zeros(ncells, dtype=np.float64)
    for c in table["target_cell"]:
        nsrc[int(c)] += 1.0
    sums = {"volsum": float(math.fsum(source["flux"].tolist())),
           "heatsum": float(math.fsum(
               (source["flux"] * tvld * source["temp"]).tolist())),
           "saltsum": float(math.fsum((source["flux"] * salt).tolist()))}
    return {"vflx": want["vflx"], "mflx": want["vflx"], "temp": temp,
           "saln": saln, "nsrc": nsrc}, sums


def write_mutant_temp():
    """Write a mods directory with RNFtemp divided by RNF_mflx, not RNF_mflxT.

    The issue's own example: ``(mT)/m`` instead of ``(mT)/m_T``. The
    substitution is on the committed, just-written source, matched by
    the exact statement it replaces so that an unrelated later edit to
    the file fails loudly (``ValueError``) instead of silently compiling
    the wrong mutant or none at all.
    """
    path = os.path.join(ROOT, "MITgcm", "pkg", "rnf",
                        "rnf_diagnostics_fill.F")
    with open(path) as fh:
        text = fh.read()
    old = ("            tLoc(i,j) = RNF_mXT(i,j,bi,bj)/RNF_mflxT(i,j,bi,bj)")
    new = ("            tLoc(i,j) = RNF_mXT(i,j,bi,bj)/RNF_mflx(i,j,bi,bj)")
    count = text.count(old)
    if count != 1:
        raise ValueError(f"rnf_diagnostics_fill.F has {count} occurrences of "
                         f"the RNFtemp statement, expected 1")
    mutant = text.replace(old, new, 1)
    # The temp mutant runs on lab_sea_mixed, which carries a runoff
    # temperature and so needs ALLOW_RUNOFTEMP (RNF_CHECK), as the
    # monitor mutant's mods directory does.
    return write_mods_code(MUTANT_CODE["temp"],
                           {"rnf_diagnostics_fill.F": mutant,
                            "EXF_OPTIONS.h": exf_options(True)})


def write_mutant_monitor():
    """Write a mods directory with the ``rA`` weight dropped from the salt sum.

    ``Sum (mS)`` instead of ``Sum (mS)*rA``: still correct on a
    hypothetical grid of unit cell area, wrong on lab_sea's, where no
    target cell's ``rA`` is 1.
    """
    path = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "rnf_monitor.F")
    with open(path) as fh:
        text = fh.read()
    old = ("            tileSalt(bi,bj) = tileSalt(bi,bj)\n"
          "     &        + RNF_mXS(i,j,bi,bj)*rA(i,j,bi,bj)")
    new = ("            tileSalt(bi,bj) = tileSalt(bi,bj)\n"
          "     &        + RNF_mXS(i,j,bi,bj)")
    count = text.count(old)
    if count != 1:
        raise ValueError(f"rnf_monitor.F has {count} occurrences of the "
                         f"salt-sum statement, expected 1")
    mutant = text.replace(old, new, 1)
    # The monitor mutant runs on lab_sea_ts, which needs ALLOW_RUNOFTEMP
    # (RNF_CHECK refuses a file with runoff_temperature otherwise), so
    # this mods directory carries the same EXF_OPTIONS.h override as
    # tendency_term_check.write_roft_code.
    return write_mods_code(MUTANT_CODE["monitor"],
                           {"rnf_monitor.F": mutant,
                            "EXF_OPTIONS.h": exf_options(True)})


WRITE_MUTANT = {"temp": write_mutant_temp, "monitor": write_mutant_monitor}


def check_case(case, nproc, args, mutant=None):
    """Run and judge one case; return the result dictionary."""
    name = case["name"] + (f"_mpi{nproc}" if nproc else "") \
        + (f"_mutant_{mutant}" if mutant else "")
    input_name = PREFIX + name
    exp_dir = os.path.join(VERIF, "lab_sea")
    input_dir = os.path.join(exp_dir, input_name)
    build = MUTANT_BUILD[mutant] if mutant else case.get("build", BUILD)
    build_run = build + (f"_mpi{nproc}" if nproc else "")
    binary = os.path.join(exp_dir, build_run, "mitgcmuv")
    result = {"case": case["name"], "processes": nproc, "mutant": mutant,
              "problems": []}
    if not os.path.isfile(binary):
        print(f"MISSING {name}: no binary at {binary}")
        if mutant:
            print("     rerun this check with --build, which compiles it")
        elif build == BUILD:
            print(f"     build it with tests/mitgcm_oracle.sh lab_sea input"
                  + (f" -mpi {nproc}" if nproc else ""))
        else:
            print(f"     build it with tests/rnf/tendency_term_check.py "
                 f"--build or tests/rnf/budget_check.py --build")
        return None
    shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir)
    run_dir = None
    try:
        table = read_table(os.path.join(
            VERIF, *TABLE_FROM))
        if case.get("custom_table"):
            table = mixed_table(table)
        result["sources"] = table["nsrc"]
        result["target_entries"] = int(table["target_cell"].size)
        dt = write_input(case, input_dir, table)
        run_dir, run_exit, timed_out = run_model(
            input_name, nproc, args.timeout, build=build)
        logs = read_file(run_dir, "output.txt") or ""
        result["ended_normally"] = "Execution ended Normally" in logs
        result["run_exit"] = run_exit
        if timed_out:
            result["problems"].append("the run to finish (it timed out)")
            return result
        if not result["ended_normally"] or run_exit != 0:
            result["problems"].append(
                f"the run to end normally (exit {run_exit})")
            result["log_tail"] = "\n".join(logs.splitlines()[-25:])
            return result

        iterations = None
        for key, stream in STREAMS.items():
            found, strays = dumps_of(run_dir, stream)
            if strays:
                result["problems"].append(
                    f"only dumps of {stream} to match {stream}*: "
                    f"{strays[:5]} are out of scope")
                return result
            if iterations is None:
                iterations = found
            elif found != iterations:
                result["problems"].append(
                    f"the {stream} stream to be dumped at the same "
                    f"iterations as {STREAMS['roff']} ({found[:4]} against "
                    f"{iterations[:4]})")
                return result
        if not iterations:
            result["problems"].append("at least one dump (found none)")
            return result

        rac, _rac_sizes = read_mds(run_dir, "RAC")
        ncells = rac.size
        trace = record_trace(run_dir)

        per_dump = []
        records_seen = []
        for iteration in iterations:
            step = dump_iteration(iteration)
            if step not in trace:
                raise ValueError(f"no RNF_FIELDS_LOAD trace for iteration "
                                 f"{step} (needs RNF_debugLev >= 3)")
            records = trace[step]
            key = list(records[:4])
            if key not in records_seen:
                records_seen.append(key)
            oracle, _sums = oracle_at(table, case, rac, ncells, records)

            roff, _sz = read_mds(run_dir, f"{STREAMS['roff']}.{iteration}")
            vflx, _sz = read_mds(run_dir, f"{STREAMS['vflx']}.{iteration}")
            mflx, _sz = read_mds(run_dir, f"{STREAMS['mflx']}.{iteration}")
            temp, _sz = read_mds(run_dir, f"{STREAMS['temp']}.{iteration}")
            saln, _sz = read_mds(run_dir, f"{STREAMS['saln']}.{iteration}")
            nsrc, _sz = read_mds(run_dir, f"{STREAMS['nsrc']}.{iteration}")

            params_rho = param(logs, "rhoConstFresh")
            entry = {"iteration": iteration}
            entry["vflx_vs_roff_max"] = float(abs(vflx - roff).max())
            mflx_oracle = params_rho * oracle["mflx"]
            temp_oracle = oracle["temp"]
            saln_oracle = oracle["saln"]
            nsrc_oracle = oracle["nsrc"]

            def rel(got, want):
                import numpy as np
                with __import__("numpy").errstate(divide="ignore",
                                                   invalid="ignore"):
                    r = np.where(want != 0.0, np.abs(got - want)
                                 / np.abs(want),
                                 np.where(got != 0.0, 1.0, 0.0))
                return float(np.nanmax(r)) if r.size else 0.0

            entry["mflx_max_rel"] = rel(mflx, mflx_oracle)
            entry["temp_max_rel"] = rel(temp, temp_oracle)
            entry["saln_max_rel"] = rel(saln, saln_oracle)
            entry["nsrc_mismatches"] = int((nsrc != nsrc_oracle).sum())
            per_dump.append(entry)

        result["per_dump"] = per_dump
        result["records_seen"] = records_seen
        result["dumps"] = len(iterations)

        monitor = monitor_blocks(logs)
        result["monitor_blocks"] = len(monitor)
        monitor_rows = []
        for block in monitor:
            step = block["iter"]
            if step not in trace:
                continue
            oracle, sums = oracle_at(table, case, rac, ncells, trace[step])
            cp = param(logs, "HeatCapacity_Cp")
            rho_fresh = param(logs, "rhoConstFresh")
            # The monitor's own volsum is Sum RNF_vflx*rA = Sum m*rA
            # /rhoConstFresh (RUNOFF-015 decision 8), which is exactly
            # the file's own flux sum with no further scaling, as
            # tests/rnf/budget_check's volume closure also reads it.
            # heatsum and saltsum are Cp*Sum(mT)*rA and Sum(mS)*rA, and
            # (mT) = rhoConstFresh*Sum_s flux_s*tvld_s*T_s (likewise
            # (mS)), so the oracle's own flux-weighted sums (no
            # rhoConstFresh baked in) need that factor to compare.
            oracle_heat = cp * rho_fresh * sums["heatsum"]
            oracle_salt = rho_fresh * sums["saltsum"]
            vol_rel = (abs(block["values"].get("rnf_volsum", float("nan"))
                          - sums["volsum"]) / abs(sums["volsum"])
                      if sums["volsum"] else None)
            heat_rel = (abs(block["values"].get("rnf_heatsum", float("nan"))
                           - oracle_heat) / abs(oracle_heat)
                       if oracle_heat else None)
            salt_rel = (abs(block["values"].get("rnf_saltsum", float("nan"))
                           - oracle_salt) / abs(oracle_salt)
                       if oracle_salt else None)
            monitor_rows.append({
                "iter": step, "vol_rel": vol_rel, "heat_rel": heat_rel,
                "salt_rel": salt_rel,
                "nsrc": block["values"].get("rnf_nsrc"),
                "ntgt": block["values"].get("rnf_ntgt"),
                "lines": block["lines"]})
        result["monitor_rows"] = monitor_rows

        judge(case, result, mutant=mutant)
        return result
    except ValueError as err:
        result["problems"].append(str(err))
        result["unusable"] = True
        return result
    finally:
        if not args.keep:
            shutil.rmtree(input_dir, ignore_errors=True)
            if run_dir:
                shutil.rmtree(run_dir, ignore_errors=True)


def judge(case, result, mutant=None):
    """Compare the measurement with what the case (or mutant) asks for."""
    problems = result["problems"]
    per_dump = result.get("per_dump") or []
    if not per_dump:
        problems.append("at least one judged dump (found none)")
        return
    if len(result.get("records_seen") or []) < case["min_records"]:
        problems.append(
            f"at least {case['min_records']} distinct record selections "
            f"over the judged dumps (found "
            f"{len(result.get('records_seen') or [])})")

    worst = {k: max(d[k] for d in per_dump)
            for k in ("vflx_vs_roff_max", "mflx_max_rel", "temp_max_rel",
                      "saln_max_rel")}
    worst_nsrc = max(d["nsrc_mismatches"] for d in per_dump)
    result["worst"] = worst
    result["worst_nsrc_mismatches"] = worst_nsrc

    direct_fail = []
    if worst["vflx_vs_roff_max"] != 0.0:
        direct_fail.append(
            f"RNFvflx to equal EXFroff bitwise (worst abs diff "
            f"{worst['vflx_vs_roff_max']:.3e})")
    if worst["mflx_max_rel"] > RTOL:
        direct_fail.append(f"RNFmflx to match the reconstruction to "
                           f"{RTOL:g} relative (worst "
                           f"{worst['mflx_max_rel']:.3e})")
    if worst["temp_max_rel"] > RTOL:
        direct_fail.append(f"RNFtemp to match the reconstruction to "
                           f"{RTOL:g} relative (worst "
                           f"{worst['temp_max_rel']:.3e})")
    if worst["saln_max_rel"] > RTOL:
        direct_fail.append(f"RNFsaln to match the reconstruction to "
                           f"{RTOL:g} relative (worst "
                           f"{worst['saln_max_rel']:.3e})")
    if worst_nsrc:
        direct_fail.append(f"RNFnsrc to match the reconstruction exactly "
                           f"(worst {worst_nsrc} mismatching cell(s))")
    result["direct_fail"] = direct_fail

    monitor_rows = result.get("monitor_rows") or []
    monitor_fail = []
    for row in monitor_rows:
        for leg in ("vol_rel", "heat_rel", "salt_rel"):
            value = row[leg]
            if value is not None and value > RTOL:
                monitor_fail.append(
                    f"monitor {leg} at iteration {row['iter']} to hold to "
                    f"{RTOL:g} relative (it is {value:.3e})")
    result["monitor_fail"] = monitor_fail
    expected_nsrc = result.get("sources")
    expected_ntgt = result.get("target_entries")
    for row in monitor_rows:
        if row["nsrc"] != expected_nsrc:
            monitor_fail.append(
                f"monitor rnf_nsrc at iteration {row['iter']} to equal "
                f"{expected_nsrc} (it is {row['nsrc']})")
        if row["ntgt"] != expected_ntgt:
            monitor_fail.append(
                f"monitor rnf_ntgt at iteration {row['iter']} to equal "
                f"{expected_ntgt} (it is {row['ntgt']})")

    if mutant == "temp":
        if "RNFtemp to match the reconstruction to %g relative" % RTOL \
                not in direct_fail and not any(
                    "RNFtemp" in p for p in direct_fail):
            problems.append(
                "the temp mutant (dividing (mT) by m instead of m_T) to be "
                "caught by the RNFtemp comparison (it was not)")
        return
    if mutant == "monitor":
        if not any(f.startswith("monitor salt_rel") for f in monitor_fail):
            problems.append(
                "the monitor mutant (dropping rA from the salt sum) to be "
                "caught by the monitor salt-sum comparison (it was not)")
        return

    problems.extend(direct_fail)
    problems.extend(monitor_fail)


def report(result):
    """Print one case's verdict; return its pass."""
    name = result["case"] + (f"_mpi{result['processes']}"
                             if result["processes"] else "") \
        + (f"_mutant_{result['mutant']}" if result["mutant"] else "")
    ok = not result["problems"]
    worst = result.get("worst") or {}
    parts = ", ".join(f"{k} {v:.3e}" for k, v in sorted(worst.items()))
    print(f"{'PASS' if ok else 'FAIL'} {name}: {result.get('dumps', 0)} "
         f"dump(s), {len(result.get('monitor_rows') or [])} monitor "
         f"block(s); {parts or 'no measurement'}")
    for problem in result["problems"]:
        print(f"     expected {problem}")
    return ok


def compare_monitor_lines(result_a, result_b):
    """Return the monitor lines that differ between two process counts.

    ``result_a``/``result_b`` are a case's results on different process
    counts; each monitor block's text (name=value pairs, the per-process
    tag already stripped by :func:`monitor_blocks`) must be identical at
    every matching iteration.
    """
    rows_a = {r["iter"]: r["lines"] for r in result_a.get("monitor_rows")
             or []}
    rows_b = {r["iter"]: r["lines"] for r in result_b.get("monitor_rows")
             or []}
    common = sorted(set(rows_a) & set(rows_b))
    diffs = []
    for it in common:
        if rows_a[it] != rows_b[it]:
            diffs.append((it, rows_a[it], rows_b[it]))
    return common, diffs


def main(argv=None):
    """Run the selected cases (or mutant) and judge the whole selection."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", action="append", default=None,
                        help="run only this case (may be repeated)")
    parser.add_argument("--mpi", type=int, default=None,
                        help="run only this process count (0: serial)")
    parser.add_argument("--mutant", choices=("temp", "monitor"),
                        help="run the named must-fail mutant instead of the "
                             "plain cases, on its own fixed case")
    parser.add_argument("--build", action="store_true",
                        help="compile the mutant binary --mutant needs, "
                             "when missing or older than its sources")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--json", help="write the measurements here")
    args = parser.parse_args(argv)

    if args.mutant:
        case = next(c for c in CASES if c["name"] == MUTANT_CASE[args.mutant])
        selected = (case,)
    else:
        selected = CASES
        if args.case:
            names = {c["name"] for c in CASES}
            unknown = sorted(set(args.case) - names)
            if unknown:
                print(f"no such case: {', '.join(unknown)}")
                return 2
            selected = tuple(c for c in CASES if c["name"] in args.case)

    runs = []
    for case in selected:
        counts = case["mpi"] if args.mpi is None else (
            (args.mpi,) if args.mpi in case["mpi"] else ())
        for nproc in counts:
            runs.append((case, nproc))
    if not runs:
        print(f"no selected case runs on {args.mpi} process(es)")
        return 2

    if args.mutant and args.build:
        wanted = []
        for case, nproc in runs:
            key = (MUTANT_BUILD[args.mutant] + (f"_mpi{nproc}" if nproc
                                                else ""), bool(nproc))
            if key not in wanted:
                wanted.append(key)
        for build, mpi in wanted:
            info = build_if_stale(build, WRITE_MUTANT[args.mutant], mpi=mpi,
                                  timeout=args.timeout)
            if not report_build(info):
                return 2

    results, missing = [], False
    for case, nproc in runs:
        result = check_case(case, nproc, args, mutant=args.mutant)
        if result is None:
            missing = True
            continue
        report(result)
        results.append(result)

    if not args.mutant:
        by_case = {}
        for r in results:
            by_case.setdefault(r["case"], {})[r["processes"]] = r
        for case_name, by_proc in by_case.items():
            procs = sorted(p for p in by_proc if p)
            if 0 in by_proc and procs:
                common, diffs = compare_monitor_lines(by_proc[0],
                                                       by_proc[procs[0]])
                print(f"MONITOR {case_name}: {len(common)} iteration(s) "
                     f"compared between 1 and {procs[0]} processes, "
                     f"{len(diffs)} differing")
                if diffs:
                    by_proc[0]["problems"].append(
                        f"the monitor line to match between 1 and "
                        f"{procs[0]} processes at every common iteration "
                        f"(it did not at {len(diffs)} of {len(common)})")

    passing = sum(1 for r in results if not r["problems"])
    print(f"{len(results)} run(s), {passing} passing")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"runs": results, "rtol": RTOL}, fh, indent=1,
                      default=str)
    if missing:
        return 2
    if not results or any(r["problems"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
