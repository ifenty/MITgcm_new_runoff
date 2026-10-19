#!/usr/bin/env python
"""A restarted run reproduces the continuous run with sparse runoff (RUNOFF-022).

**Question.** With ``useRNF`` on, does a run that is stopped at step K,
writes a pickup and is restarted from it give the answer of the same run
done straight through? ``pkg/rnf`` writes no pickup (package design,
decision 8): its record buffers, its dense fields and the time level of
its salt and tracer terms are a function of model time and are re-derived
at the first step (``RNF_INIT_VARIA`` empties the buffers,
``RNF_FIELDS_BUILD`` builds the start time and, in the synchronous mode
``RNF_lagFlds``, the level one step before it). This check measures
whether that re-derivation is right.

**What each case runs.** For each path (``sparse``: ``input.rnof_sp_<mode>``;
``dense``: the exf ``runoffFile`` twin ``input.rnof_<mode>``, which the
restart of pkg/exf alone must reproduce too, so that a failure of the
sparse path is not blamed on the model's restart) three runs of
``N`` steps:

1. ``cont``: the continuous run, a permanent pickup at its last step (``pChkptFreq``
equal to the end time);
2. ``seg1``: the same run stopped after ``K`` steps, with the same pickup;
3. ``seg2``: a restart from the pickup of ``seg1`` (``nIter0`` and
   ``startTime`` moved by ``K`` steps, ``startDate`` unchanged) to step N.

``writeBinaryPrec`` is 64, so the pickups are float64 (the ``.meta``
says so, and a pickup that is not is refused) and the restart reads back
exactly what ``seg1`` wrote. What ``seg2`` produced from step K on is
then compared with what ``cont`` produced:

* the exf ``runoff`` field the model applies, cell by cell, at every
  dumped step (an ``EXFroff`` snapshot stream, as
  ``tests/rnf/timing_field_check.py`` and ``applied_field_check.py``),
  **bitwise** -- the field is a function of model time only;
* the ocean state in the final pickup, field by field (every field of
  the pickup; ``Theta``, ``Salt`` and the free surface ``EtaN`` are
  reported by name), **bitwise**; where it is not, the number of matching
  digits of the largest relative difference is reported and the case
  fails, because with pickups of 64 bits nothing in the model makes a
  restart non-bitwise (a threshold of 10 digits is the oracle's, not
  this check's).

**Sensitivity.** A comparison that cannot fail proves nothing, so each
case is refused unless the compared window holds at least
``--min-distinct`` distinct applied fields, and ``--control`` adds, per
case, a restart from the **wrong** pickup (the one of the lab_sea start,
step 1, renamed to step K) which must differ in the ocean state. The
applied field does not depend on the pickup, so that control is a
control of the state comparison only; the control of the runoff
comparison is the mutant build below.

**The mutant.** ``--use-build`` runs the cases on another binary.
``build_esx_nlfs_mut`` (``--build-mutant``) is the synchronous build
with ``RNF_FIELDS_BUILD`` told the time since the start of its own
segment, plus the lab_sea start time: the package then counts its
records from the run it was started in instead of re-deriving the record
from the model time of the restart, and every restart begins again at
record 1. That is the failure the check exists for -- state that
survives in the process and is not reconstructed from ``myTime`` and
``nIter0`` -- and it is identical to the real code in a continuous run,
where the segment start is the run start, so the mutant differs from
the code only at a restart.

**Cases** (the restart weight and record changes are asserted from the
record-selection trace of the restarted run, not assumed). ``daily``
(restart 6 h into a day record, then the record changes), ``month``
(restart on 30 January, then a calendar-month change that is not a record
change, then the mid-month record change of 15 February), ``yearly`` and
``yearly_after`` (restart before and after the 1 January change of the
``_YYYY`` file), and ``sync``: the synchronous case, nonlinear free surface
(``nonlinFreeSurf=4``), real freshwater flux, no ``staggerTimeStep``, with
a temperature **and a salinity** series in the file (``RNF_lagFlds`` is
true, the first step after the restart needs the package fields at
``myTime - deltaT``; without the salinity, or a tracer, those fields hold
nothing the model uses and the ``lag`` mutant passes). ``sync`` needs a
binary compiled with ``NONLIN_FRSURF`` and ``ALLOW_RUNOFTEMP``
(``build_esx_nlfs``, ``--build``). Its dense twin is the daily dense case in
the same configuration, with no package fields: it is the model's own
baseline, not a comparison of values. ``sync_stagger`` is ``sync`` with
``staggerTimeStep`` (``RNF_lagFlds`` false).

**The refusal case** (RUNOFF-050). ``sync_refuse`` is the one case that
must stop. At the first step of a synchronous restart ``RNF_FIELDS_LOAD``
needs the fields at ``t - deltaT``; a series that is not repeated and whose
first record is later than that cannot give them, and the package stops
with ``RNF_FIELDS_LOAD: RNF: the runoff series does not reach t =`` and
``ABNORMAL END: S/R RNF_FIELDS_LOAD``. A file with such a first record
also stops a run that starts earlier (``EXF_GetFFieldRec``), so the run
that reaches the guard is a restart whose pickup comes from another file.
The case runs: ``cont`` and ``seg1`` on the ``sync`` file (both must end
normally; ``seg1`` gives the pickup); the restart with the **late** file
(its first record exactly at the restart time: the time axis is moved and
the records stay), which must stop with the two texts above; control (i),
the restart with the ``sync`` file, which must run; and control (ii), the
restart with the late file and a repeat cycle (``RNF_repCycle``, the 40
records), which must run. No comparison with the continuous run is made:
the check is that the run stops or runs. With ``--mutant guard``
(``build_esx_nlfs_mut_guard``, the code with the test of the guard never
true) the restart must not stop with the ``RNF`` text, so the case fails
and the mutant is caught. (The older build ``build_esx_nlfs_mut_first``
does not remove this guard: it changes the time of the first load, so it is
not used.)

**Why ``sync`` is judged by digits and not bitwise.** In that
configuration the model itself does not restart bitwise: the dense twin,
which has no ``pkg/rnf`` in the loop, differs from its continuous run in
every pickup field (11.6 digits at the least of the judged state, measured),
and ``sync_stagger`` is bitwise. The cause is the model's own: at the
first step of a restart ``INTEGR_CONTINUITY`` rebuilds ``PmEpR`` from the
pickup's ``dEtaHdt`` and the horizontal divergence
(``model/src/integr_continuity.F``, ``PmEpR = dEtaHdt + hDivFlow*...``),
where the running model had ``-EmPmR``: the same number to round-off,
which a chaotic run amplifies. So the state of ``sync`` is judged to the
10 digits of the existing oracles on the prognostic fields (``Uvel Vvel
Theta Salt EtaN EtaH``); the applied runoff is still bitwise. The ``lag``
mutant, which breaks the one thing ``pkg/rnf`` adds there, is at about 5
digits, so the floor separates a package error from the model's
round-off by five digits.

Each case runs the existing binary through ``experiment_run_no_compile.sh``;
the scratch input and run directories are removed afterwards (``--keep``
leaves the run directories). Exit status: 0 if every case passes, 1 if
any fails or none ran, 2 if a binary is missing or stale or a ``--case``
selection does not exist.

Usage::

    python tests/rnf/restart_check.py [--mpi N] [--case NAME ...]
        [--control] [--build] [--mutant time|lag|guard] [--use-build DIR]
        [--keep] [--json] [--timeout S]
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
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runoff"))
from refusal_check import (ROOT, VERIF, check_build_fresh,  # noqa: E402
                           kill_run, read_file, replace_line)
from applied_field_check import dumps, read_mds, set_namelist  # noqa: E402
from timing_field_check import (STREAM, start_time,  # noqa: E402
                                time_step, write_input)
from tendency_term_check import (build_if_stale, exf_options,  # noqa: E402
                                 report_build, write_mods_code)

EXPERIMENT = "lab_sea"
LAB = os.path.join(VERIF, EXPERIMENT)
PREFIX = "input.rnrst_"
BUILD = "build_esx"
#: Synchronous build: NONLIN_FRSURF and ALLOW_RUNOFTEMP defined.
NLFS_BUILD = "build_esx_nlfs"
NLFS_CODE = "code_rnfsync_nlfs"
#: The sparse file of the synchronous case, written into its scratch input.
SYNC_FILE = "runoff_sync.nc"

#: The cases. ``K`` steps are run before the restart and ``N`` in all;
#: iteration 1 is the lab_sea start (``startTime`` 3600 s, the pickup
#: ``pickup.0000000001`` of ``input/``), so the restart is at iteration
#: ``1 + K``. The record change each case restarts in front of is in the
#: comment. ``cal_start`` moves ``startDate_1`` of both runs.
CASES = (
    # day records at 1 January 00:00 + k days; iteration 1 is 01:00, so
    # the record changes at iteration 24 and 48; iteration 31 is 06:00 into
    # record 2 (weight 0.75), and the run reaches the change at iteration 48
    {"name": "daily", "mode": "daily", "K": 30, "N": 54},
    # monthly climatology, records at mid-month (15 Feb 00:00 = day 45),
    # file in 1979; start 30 Jan 01:00. Iteration 41 is 17:00 of 30 Jan, the
    # weight of the earlier record 0.48. The window holds two month
    # boundaries of different kinds: 1 Feb 00:00 (iteration 49), where the
    # calendar month changes but the bracket does not, and 15 Feb 00:00
    # (iteration 385), where the bracket moves to the next pair of records
    {"name": "month", "mode": "month", "cal_start": 19790130,
     "K": 40, "N": 392},
    # start 20 Dec 1978 01:00; the 1979 file takes over at iteration 288
    {"name": "yearly", "mode": "yearly", "K": 283, "N": 299},
    # restart on 1 Jan 1979 03:00 (weight 0.875 of the 1979 file's
    # first record), over the day-record change at iteration 312
    {"name": "yearly_after", "mode": "yearly", "K": 290, "N": 315},
    # synchronous: sparse file with a temperature series, nonlinear free
    # surface, real freshwater flux, no staggerTimeStep
    {"name": "sync", "mode": "daily", "K": 30, "N": 54, "sync": True,
     "state_digits": 10},
    # the same configuration with staggerTimeStep (RNF_lagFlds false): the
    # control that says where the non-bitwise restart of "sync" comes from
    {"name": "sync_stagger", "mode": "daily", "K": 30, "N": 54,
     "sync": True, "stagger": True},
    # refusal (RUNOFF-050): restart at iteration 31 (2 Jan 07:00) from the
    # pickup of the sync file, with a file whose first record is at 07:00
    {"name": "sync_refuse", "mode": "daily", "K": 30, "N": 54, "sync": True,
     "refuse": True, "dense": False},
)

#: The text the refusal prints (``RNF_FIELDS_LOAD``) and the stop it ends in.
REFUSAL_TEXT = "RNF_FIELDS_LOAD: RNF: the runoff series does not reach t ="
REFUSAL_STOP = "ABNORMAL END: S/R RNF_FIELDS_LOAD"

#: The prognostic state judged against a digit floor (``state_digits``).
STATE_FIELDS = {"Uvel", "Vvel", "Theta", "Salt", "EtaN", "EtaH"}

#: Pickup fields that are not 3-D, to split a pickup into its fields.
#: Every other field has ``Nr`` levels.
TWO_D = {"EtaN", "dEtaHdt", "EtaH", "etaHnm1", "PmEpR", "PmEpRnm1"}


def sync_cpp(text):
    """Return CPP_OPTIONS.h with NONLIN_FRSURF defined (exactly one line)."""
    new, count = re.subn(r"(?m)^#undef\s+NONLIN_FRSURF\s*$",
                         "#define NONLIN_FRSURF", text)
    if count != 1:
        raise ValueError("CPP_OPTIONS.h has %d '#undef NONLIN_FRSURF' lines, "
                         "expected 1" % count)
    return new


def write_nlfs_code():
    """Write ``code_rnfsync_nlfs``: lab_sea code with NLFS and RUNOFTEMP."""
    with open(os.path.join(LAB, "code", "CPP_OPTIONS.h")) as fh:
        cpp = fh.read()
    return write_mods_code(NLFS_CODE, {"CPP_OPTIONS.h": sync_cpp(cpp),
                                       "EXF_OPTIONS.h": exf_options(True)})


#: The mutants, name -> (build, code directory, [(old, new), ...]) edits
#: of ``pkg/rnf/rnf_fields_load.F``; each ``old`` must occur exactly once.
#:
#: ``time``: the time handed to RNF_LOAD_AT is measured from the start of
#: the segment (``startTime``) plus the lab_sea start (3600 s). In a
#: continuous run that is the model time; in a restart the package counts
#: its records from the run it was started in.
#:
#: ``lag``: at the first step of a restart in the synchronous mode the
#: lagged level (the fields at ``myTime - deltaT``) is not evaluated from
#: the records: ``RNF_LOAD_AT`` for it is skipped, so the salt and tracer
#: terms of that one step are applied from the cleared fields. That is
#: the failure a package would have that kept the lagged fields only in
#: memory (taking them as zero was the alternative the design rejected,
#: ``RNF_FIELDS_BUILD``).
MUTANTS = {
    "time": ("build_esx_nlfs_mut_time", "code_rnfsync_mut_time", [
        ("      CALL RNF_LOAD_AT( myTime, myIter, .TRUE., myThid )\n",
         "      CALL RNF_LOAD_AT( myTime-startTime+3600. _d 0, myIter,\n"
         "     &                 .TRUE., myThid )\n"),
        ("            CALL RNF_LOAD_AT( tApply, iApply, .FALSE., myThid )\n",
         "            CALL RNF_LOAD_AT( tApply-startTime+3600. _d 0,\n"
         "     &                 iApply, .FALSE., myThid )\n")]),
    "lag": ("build_esx_nlfs_mut_lag", "code_rnfsync_mut_lag", [
        ("            CALL RNF_LOAD_AT( tApply, iApply, .FALSE., myThid )\n",
         "C           mutant: the lagged level is not evaluated\n")]),
    # ``guard``: the test of the first-record refusal is never true, so the
    # package goes on to RNF_LOAD_AT at a time before the first record
    "guard": ("build_esx_nlfs_mut_guard", "code_rnfsync_mut_guard", [
        ("     &           tApply.LT.RNF_recStart ) THEN\n",
         "     &           tApply.LT.RNF_recStart .AND. .FALSE. ) THEN\n")]),
}


def write_mutant_code(name):
    """Write the code directory of mutant ``name``: NLFS code plus edits."""
    build, code, edits = MUTANTS[name]
    path = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "rnf_fields_load.F")
    with open(path) as fh:
        text = fh.read()
    for old, new in edits:
        if text.count(old) != 1:
            raise ValueError("%r occurs %d times in %s, expected 1"
                             % (old, text.count(old), path))
        text = text.replace(old, new)
    with open(os.path.join(LAB, "code", "CPP_OPTIONS.h")) as fh:
        cpp = fh.read()
    return write_mods_code(code, {"CPP_OPTIONS.h": sync_cpp(cpp),
                                  "EXF_OPTIONS.h": exf_options(True),
                                  "rnf_fields_load.F": text})


def write_sync_file(path, source):
    """Copy the daily sparse file and add a temperature and a salinity.

    Both differ by source and by record, so that a wrong record or a wrong
    weight changes the heat and the salt. The salinity is what makes the
    lagged level matter: without a ``runoff_salinity`` (or a passive
    tracer) ``RNF_applyS`` is false, the lagged fields hold nothing the
    model uses, and a restart that lost them would pass (measured: the
    ``lag`` mutant passed on a file with the temperature alone).
    """
    import netCDF4
    import numpy as np
    shutil.copyfile(source, path)
    with netCDF4.Dataset(path, "a") as ds:
        ds.set_auto_maskandscale(False)
        nt, ns = ds.dimensions["time"].size, ds.dimensions["source"].size
        temp = ds.createVariable("runoff_temperature", "f8",
                                 ("time", "source"),
                                 fill_value=np.float64(-9999.0))
        temp.units = "degC"
        salt = ds.createVariable("runoff_salinity", "f8", ("time", "source"))
        salt.units = "g kg-1"
        for k in range(nt):
            temp[k, :] = [3.0 + 0.5 * s + 0.35 * k for s in range(ns)]
            salt[k, :] = [1.0 + 0.25 * s + 0.15 * k for s in range(ns)]


def make_late(path, seconds):
    """Move the time axis of the sparse file ``path`` so that record 1 is at
    ``seconds`` after 1979-01-01 00:00 (the records and their spacing stay).
    """
    import datetime
    import netCDF4
    import numpy as np
    when = datetime.datetime(1979, 1, 1) + datetime.timedelta(seconds=seconds)
    with netCDF4.Dataset(path, "a") as ds:
        ds.set_auto_maskandscale(False)
        nt = ds.dimensions["time"].size
        ds["time"].units = "seconds since " + when.strftime("%Y-%m-%d %H:%M:%S")
        ds["time"][:] = 86400.0 * np.arange(nt)
        ds["time_bnds"][:, 0] = 86400.0 * np.arange(nt) - 43200.0
        ds["time_bnds"][:, 1] = 86400.0 * np.arange(nt) + 43200.0


def set_pickup_namelist(data, start, delta, steps, restart_iter=None):
    """Return ``data`` set for a segment of ``steps`` steps.

    ``restart_iter`` moves ``startTime`` and ``nIter0`` to that
    iteration (the run starts from the pickup of that iteration);
    otherwise the run begins at the case's own start.
    """
    first = start if restart_iter is None else start + delta * restart_iter
    data = set_namelist(data, "PARM03", "endTime",
                        " endTime=%r," % (start + delta * steps))
    # a permanent pickup (named by iteration) at the one time that is a
    # multiple of pChkptFreq: the end of the segment. writePickupAtEnd
    # would write the rolling pickup.ckptA instead.
    data = set_namelist(data, "PARM03", "pChkptFreq",
                        " pChkptFreq=%r," % (start + delta * steps))
    if restart_iter is not None:
        data = set_namelist(data, "PARM03", "startTime",
                            " startTime=%r," % first)
        data = set_namelist(data, "PARM03", "nIter0",
                            " nIter0=%d," % (round(start / delta)
                                             + restart_iter))
    return data


def make_input(case, path, name, steps, restart_from=None, pickup_iter=None,
               wrong=False, late=None):
    """Build the scratch input of one run; return ``(delta, start)``.

    ``steps`` is where the run ends, counted from the case's start.
    ``restart_from`` is a run directory whose final pickup is copied in
    (the segment restarts at ``steps_done = restart_iter``); with
    ``wrong`` the pickup of the lab_sea start is renamed to the restart
    iteration instead -- the control. ``late`` (``"plain"`` or ``"cycle"``)
    moves the first record of the sync file to the restart time, with the
    repeat cycle of the 40 records for ``"cycle"``.
    """
    source = os.path.join(LAB, "input.rnof_%s%s" % (
        "sp_" if path == "sparse" else "", case["mode"]))
    if not os.path.isdir(source):
        raise ValueError("missing input directory %s" % source)
    scratch = os.path.join(LAB, name)
    shutil.rmtree(scratch, ignore_errors=True)
    os.makedirs(scratch)
    delta, start = write_input(
        {"cal_start": case.get("cal_start")}, source, scratch)
    n_iter0 = int(round(start / delta))
    with open(os.path.join(scratch, "data")) as fh:
        data = fh.read()
    # float64 pickups and dumps; nothing else of lab_sea's data changes
    data = set_namelist(data, "PARM01", "writeBinaryPrec",
                        " writeBinaryPrec=64,")
    if case.get("sync"):
        for line in (" useRealFreshWaterFlux=.TRUE.,",
                     " exactConserv=.TRUE.,",
                     " staggerTimeStep=.%s.," % ("TRUE" if case.get("stagger")
                                                 else "FALSE"),
                     " nonlinFreeSurf=4,", " hFacInf=0.2,",
                     " hFacSup=2.0,"):
            data = set_namelist(data, "PARM01", line.split("=")[0].strip(),
                                line)
    data = set_pickup_namelist(
        data, start, delta, steps,
        None if restart_from is None and not wrong else case["K"])
    with open(os.path.join(scratch, "data"), "w") as fh:
        fh.write(data)
    if case.get("sync") and path == "sparse":
        with open(os.path.join(scratch, "data.rnf")) as fh:
            text = fh.read()
        text = replace_line(text, "RNF_file", "  RNF_file = '%s'," % SYNC_FILE)
        if late == "cycle":
            text = text.replace("  RNF_file =", "  RNF_repCycle = 3456000.0,\n"
                                "  RNF_file =", 1)
        with open(os.path.join(scratch, "data.rnf"), "w") as fh:
            fh.write(text)
        write_sync_file(os.path.join(scratch, SYNC_FILE),
                        os.path.join(LAB, "input.rnof_daily",
                                     "runoff_sparse.nc"))
        if late:
            make_late(os.path.join(scratch, SYNC_FILE),
                      start + delta * case["K"])
    restart_iter = n_iter0 + case["K"]
    if restart_from is not None:
        for entry in sorted(os.listdir(restart_from)):
            if re.match(r"pickup.*\.%010d\.(data|meta)$" % restart_iter,
                        entry):
                shutil.copyfile(os.path.join(restart_from, entry),
                                os.path.join(scratch, entry))
    if wrong:
        # the pickup of the lab_sea start, filed under the restart iteration
        for entry in sorted(os.listdir(os.path.join(LAB, "input"))):
            match = re.match(r"(pickup.*)\.%010d\.(data|meta)$" % n_iter0,
                             entry)
            if not match:
                continue
            target = "%s.%010d.%s" % (match.group(1), restart_iter,
                                      match.group(2))
            with open(os.path.join(LAB, "input", entry), "rb") as fh:
                body = fh.read()
            if match.group(2) == "meta":
                # the reader takes a fixed-width integer: keep the width
                body = re.sub(
                    rb"(timeStepNumber\s*=\s*\[)(\s*\d+)",
                    lambda m: m.group(1) + b"%*d" % (len(m.group(2)),
                                                     restart_iter), body)
            with open(os.path.join(scratch, target), "wb") as fh:
                fh.write(body)
    return delta, start


def run_model(input_name, nproc, build, timeout):
    """Run one scratch input; return ``(run dir, exit status, timed out)``."""
    output_name = "output_esx_" + input_name
    mpi_args = []
    if nproc:
        output_name += "_mpi%d" % nproc
        build += "_mpi%d" % nproc
        mpi_args = ["-mpi", str(nproc)]
    run_dir = os.path.join(LAB, output_name)
    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        proc = subprocess.run(
            ["./experiment_run_no_compile.sh", EXPERIMENT, input_name]
            + mpi_args + ["-build", build, "-output", output_name],
            cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return run_dir, proc.returncode, False
    except subprocess.TimeoutExpired:
        kill_run(output_name)
        return run_dir, -1, True


def read_pickup(run_dir, iteration):
    """Return ``{file: (fields, array)}`` for the pickups of ``iteration``.

    ``fields`` is the list of ``(name, first record, number of records)``
    of the file's ``.meta``. A pickup that is not float64 is refused.
    """
    import numpy as np
    out = {}
    for entry in sorted(os.listdir(run_dir)):
        match = re.match(r"(pickup[A-Za-z_]*)\.%010d\.meta$" % iteration,
                         entry)
        if not match:
            continue
        meta = read_file(run_dir, entry)
        prec = re.search(r"dataprec\s*=\s*\[\s*'([^']+)'", meta)
        if not prec or prec.group(1) != "float64":
            raise ValueError("%s says dataprec %r, not 'float64'"
                             % (entry, prec and prec.group(1)))
        dims = [int(v) for v in re.findall(
            r"-?\d+", re.search(r"dimList\s*=\s*\[(.*?)\]", meta,
                                re.DOTALL).group(1))]
        nrec = int(re.search(r"nrecords\s*=\s*\[\s*(\d+)", meta).group(1))
        listing = re.search(r"fldList\s*=\s*\{(.*?)\}", meta, re.DOTALL)
        names = re.findall(r"'([^']+?)\s*'", listing.group(1)) \
            if listing else []
        array = np.fromfile(os.path.join(run_dir, match.group(0)[:-5]
                                         + ".data"), dtype=">f8")
        nx, ny = dims[0], dims[3]
        if array.size != nx * ny * nrec:
            raise ValueError("%s holds %d values, not %d*%d*%d"
                             % (entry, array.size, nx, ny, nrec))
        n3d = sum(1 for n in names if n not in TWO_D)
        n2d = len(names) - n3d
        if names and n3d and (nrec - n2d) % n3d == 0 and \
                (nrec - n2d) // n3d > 1:
            nr = (nrec - n2d) // n3d
            fields, at = [], 0
            for n in names:
                size = 1 if n in TWO_D else nr
                fields.append((n, at, size))
                at += size
        else:
            # no field list, or one whose levels cannot be told apart
            # (pickup_cd, pickup_seaice): the file is compared whole
            fields = [("all", 0, nrec)]
        out[match.group(1)] = (fields, array.reshape(nrec, ny * nx))
    return out


def digits(a, b):
    """Number of matching significant digits of two arrays (16 if equal)."""
    import numpy as np
    if np.array_equal(a, b):
        return 16.0
    scale = float(np.abs(a).max())
    worst = float(np.abs(a - b).max())
    if scale == 0.0:
        return 0.0
    return max(0.0, -math.log10(worst / scale))


def compare_state(cont_dir, other_dir, iteration):
    """Compare the final pickups field by field; return a result dict."""
    import numpy as np
    out = {"fields": {}, "differing": [], "problems": []}
    a = read_pickup(cont_dir, iteration)
    b = read_pickup(other_dir, iteration)
    if not a or set(a) != set(b):
        out["problems"].append("the same pickup files at iteration %d in both"
                               " runs (found %s and %s)"
                               % (iteration, sorted(a), sorted(b)))
        return out
    for fname in sorted(a):
        fields, arr = a[fname]
        fields_b, brr = b[fname]
        if fields != fields_b:
            out["problems"].append("the same fields in %s" % fname)
            continue
        for name, first, size in fields:
            x, y = arr[first:first + size], brr[first:first + size]
            equal = bool(np.array_equal(x, y))
            key = "%s:%s" % (fname, name)
            out["fields"][key] = 16.0 if equal else digits(x, y)
            if not equal:
                out["differing"].append(key)
    return out


def compare_fields(cont_dir, seg_dir, first_iter):
    """Compare the applied runoff dumps of the restart with the continuous."""
    import numpy as np
    out = {"problems": []}
    c_iters, c_stray = dumps(cont_dir, STREAM)
    s_iters, s_stray = dumps(seg_dir, STREAM)
    if c_stray or s_stray:
        out["problems"].append("only dumps of the %s stream: %s"
                               % (STREAM, (c_stray + s_stray)[:5]))
        return out
    wanted = [i for i in c_iters if int(i) >= first_iter]
    if not wanted or s_iters != wanted:
        out["problems"].append(
            "the restart to dump the iterations %s..%s of the continuous run "
            "(it dumped %s..%s)" % (wanted[:1], wanted[-1:], s_iters[:1],
                                    s_iters[-1:]))
        return out
    differ, distinct = [], set()
    for iteration in wanted:
        a, _ = read_mds(cont_dir, STREAM, iteration)
        b, _ = read_mds(seg_dir, STREAM, iteration)
        distinct.add(round(float(a.max()), 18))
        if not np.array_equal(a, b):
            differ.append(int(iteration))
    out.update(dumps=len(wanted), differing_dumps=len(differ),
               first_differing=differ[:1], distinct=len(distinct))
    if differ:
        out["problems"].append(
            "the applied runoff of the restart to equal the continuous run "
            "bitwise (%d of %d dumps differ, the first at iteration %d)"
            % (len(differ), len(wanted), differ[0]))
    return out


def window_trace(log, first_iter):
    """Read the record-selection trace of the restarted run.

    ``RNF_FIELDS_LOAD`` prints, at ``RNF_debugLev`` 3, one line per step
    with the two records it bracketed, their file years and the weight of
    the earlier one (the cases' ``data.rnf`` set that level). Returns the
    weight at the restart step, the number of distinct brackets
    ``(rec0, yr0, rec1, yr1)`` in the segment, and the lines read.
    """
    rows = re.findall(
        r"RNF_FIELDS_LOAD: it=\s*(\d+), rec0=\s*(\d+), yr0=\s*(-?\d+), "
        r"rec1=\s*(\d+), yr1=\s*(-?\d+), t=\s*(\S+), fac=\s*(\S+)", log)
    rows = [r for r in rows if int(r[0]) >= first_iter]
    if not rows:
        return {"lines": 0, "brackets": 0}
    return {"lines": len(rows), "first_it": int(rows[0][0]),
            "first_fac": float(rows[0][6]),
            "brackets": len({r[1:5] for r in rows})}


def run_checked(input_name, nproc, build, timeout, result, label):
    """Run one input; return its run directory or ``None`` with a problem."""
    run_dir, code, timed_out = run_model(input_name, nproc, build, timeout)
    logs = "\n".join(filter(None, (read_file(run_dir, n) for n in
                                   ("output.txt", "mpirun.log"))))
    if timed_out:
        result["problems"].append("%s to finish (it timed out)" % label)
        return None
    if code != 0 or "Execution ended Normally" not in logs:
        result["problems"].append("%s to end normally (exit %s)"
                                  % (label, code))
        return None
    return run_dir


def check_path(case, path, nproc, build, timeout, keep, min_distinct,
               control):
    """Run cont, seg1, seg2 (and the wrong-pickup control) of one path."""
    tag = "%s_%s%s%s" % (case["name"], path, "_mpi%d" % nproc if nproc
                         else "", "_" + build[build.index("mut"):] if "mut" in build
                         else "")
    result = {"case": case["name"], "path": path, "processes": nproc,
              "build": build, "problems": []}
    names = {k: PREFIX + tag + "_" + k for k in
             ("cont", "seg1", "seg2", "wrong")}
    runs = []
    try:
        delta, start = make_input(case, path, names["cont"], case["N"])
        n_iter0 = int(round(start / delta))
        first = n_iter0 + case["K"]
        last = n_iter0 + case["N"]
        make_input(case, path, names["seg1"], case["K"])
        d_cont = run_checked(names["cont"], nproc, build, timeout, result,
                             "the continuous run")
        runs.append(os.path.join(LAB, "output_esx_" + names["cont"]
                                 + ("_mpi%d" % nproc if nproc else "")))
        if d_cont is None:
            return result
        d_seg1 = run_checked(names["seg1"], nproc, build, timeout, result,
                             "the first segment")
        runs.append(os.path.join(LAB, "output_esx_" + names["seg1"]
                                 + ("_mpi%d" % nproc if nproc else "")))
        if d_seg1 is None:
            return result
        make_input(case, path, names["seg2"], case["N"], restart_from=d_seg1)
        d_seg2 = run_checked(names["seg2"], nproc, build, timeout, result,
                             "the restarted run")
        runs.append(os.path.join(LAB, "output_esx_" + names["seg2"]
                                 + ("_mpi%d" % nproc if nproc else "")))
        if d_seg2 is None:
            return result
        log = read_file(d_seg2, "output.txt") or ""
        if "pickup" not in log.lower():
            result["problems"].append("the restart to read a pickup")
        if path == "sparse":
            trace = window_trace(log, first)
            result["window"] = trace
            if not (0.0 < trace.get("first_fac", 0.0) < 1.0):
                result["problems"].append(
                    "a restart point inside a record (weight strictly "
                    "between 0 and 1; found %r)" % trace.get("first_fac"))
            if trace.get("brackets", 0) < 2:
                result["problems"].append(
                    "the compared window to cross a record change (found %d "
                    "bracket(s))" % trace.get("brackets", 0))
        field = compare_fields(d_cont, d_seg2, first)
        result["field"] = {k: v for k, v in field.items() if k != "problems"}
        result["problems"] += field["problems"]
        if field.get("distinct", 0) < min_distinct and not field["problems"]:
            result["problems"].append(
                "at least %d distinct applied fields in the compared window "
                "(found %d)" % (min_distinct, field["distinct"]))
        state = compare_state(d_cont, d_seg2, last)
        result["state"] = {"digits": state["fields"],
                           "differing": state["differing"]}
        result["problems"] += state["problems"]
        floor = case.get("state_digits")
        # With a floor, only the prognostic state is judged; the
        # Adams-Bashforth tendencies (G*Nm1), the solver's dEtaHdt and the
        # CD-scheme and sea-ice pickups are reported (their digits are
        # relative to their own, much smaller, maximum, and the dense twin
        # sits at the same level: 10.1 digits for GtNm1 against 9.8)
        judged = {k: v for k, v in state["fields"].items()
                  if floor is None or k.split(":")[1] in STATE_FIELDS}
        worst = min(judged.values()) if judged else 0.0
        result["state"]["min_digits"] = worst
        if worst < 16.0 and (floor is None or worst < floor):
            result["problems"].append(
                "the ocean state of the restart to equal the continuous run "
                "%s (differs: %s, matching digits %s)"
                % ("bitwise" if floor is None else "to %d digits" % floor,
                   ", ".join(state["differing"][:6]),
                   ", ".join("%.1f" % state["fields"][k]
                             for k in state["differing"][:6])))
        if control:
            result["control"] = run_control(case, path, names["wrong"], nproc,
                                            build, timeout, d_cont, last,
                                            runs)
            if not result["control"].get("detected"):
                result["problems"].append(
                    "the wrong-pickup control to differ in the ocean state "
                    "(%s)" % "; ".join(result["control"]["problems"]
                                       or ["it ran and matched"]))
        return result
    except (ValueError, OSError) as err:
        result["problems"].append(str(err))
        result["unusable"] = True
        return result
    finally:
        for name in names.values():
            shutil.rmtree(os.path.join(LAB, name), ignore_errors=True)
        if not keep:
            for run in runs:
                shutil.rmtree(run, ignore_errors=True)


def check_refusal(case, nproc, build, timeout, keep):
    """Run the refusal case (RUNOFF-050) on ``build``; return a result dict.

    ``cont`` and ``seg1`` on the sync file must end normally. The restart
    with the late file must stop with the refusal text; the restart with
    the sync file (control i) and the one with the late file and a repeat
    cycle (control ii) must end normally. The restart is run with the
    pickup of ``seg1`` in all three.
    """
    tag = "%s%s%s" % (case["name"], "_mpi%d" % nproc if nproc else "",
                      "_" + build[build.index("mut"):] if "mut" in build
                      else "")
    result = {"case": case["name"], "path": "sparse", "processes": nproc,
              "build": build, "problems": [], "refusal": {}}
    names = {k: PREFIX + tag + "_" + k for k in
             ("cont", "seg1", "late", "early", "cycle")}
    sfx = "_mpi%d" % nproc if nproc else ""
    runs = [os.path.join(LAB, "output_esx_" + n + sfx) for n in names.values()]
    try:
        make_input(case, "sparse", names["cont"], case["N"])
        make_input(case, "sparse", names["seg1"], case["K"])
        if run_checked(names["cont"], nproc, build, timeout, result,
                       "the continuous run") is None:
            return result
        d_seg1 = run_checked(names["seg1"], nproc, build, timeout, result,
                             "the first segment")
        if d_seg1 is None:
            return result
        for key, late, label in (("late", "plain", "the restart"),
                                 ("early", None, "control (i)"),
                                 ("cycle", "cycle", "control (ii)")):
            make_input(case, "sparse", names[key], case["N"],
                       restart_from=d_seg1, late=late)
            if key != "late":
                if run_checked(names[key], nproc, build, timeout, result,
                               label + ", a restart that runs") is None:
                    result["refusal"][key] = "did not run"
                else:
                    result["refusal"][key] = "ran"
                continue
            run_dir, code, timed_out = run_model(names[key], nproc, build,
                                                 timeout)
            logs = "\n".join(filter(None, (read_file(run_dir, n) for n in
                                           ("output.txt", "mpirun.log",
                                            "STDERR.0000"))))
            has_text = REFUSAL_TEXT in logs
            has_stop = REFUSAL_STOP in logs
            ended = "Execution ended Normally" in logs
            stray = re.findall(r"ABNORMAL END: S/R \w+", logs)
            result["refusal"][key] = {
                "exit": code, "timed_out": timed_out, "text": has_text,
                "stop": has_stop, "ended_normally": ended,
                "other_stop": [s for s in stray if s != REFUSAL_STOP][:2]}
            if timed_out:
                result["problems"].append("the restart to finish (it timed "
                                          "out)")
            elif ended or code == 0:
                result["problems"].append(
                    "the restart with a first record after t - deltaT to stop"
                    " (it ended normally)")
            elif not (has_text and has_stop):
                result["problems"].append(
                    "the restart to stop with %r and %r (text %s, stop %s, "
                    "other stop %s)" % (REFUSAL_TEXT, REFUSAL_STOP,
                                        "found" if has_text else "missing",
                                        "found" if has_stop else "missing",
                                        result["refusal"][key]["other_stop"]
                                        or "none"))
        return result
    except (ValueError, OSError) as err:
        result["problems"].append(str(err))
        result["unusable"] = True
        return result
    finally:
        for name in names.values():
            shutil.rmtree(os.path.join(LAB, name), ignore_errors=True)
        if not keep:
            for run in runs:
                shutil.rmtree(run, ignore_errors=True)


def run_control(case, path, name, nproc, build, timeout, d_cont, last, runs):
    """Restart from the wrong pickup; the state comparison must see it."""
    out = {"problems": []}
    make_input(case, path, name, case["N"], wrong=True)
    d_run = run_checked(name, nproc, build, timeout, out,
                        "the control restart")
    runs.append(os.path.join(LAB, "output_esx_" + name
                             + ("_mpi%d" % nproc if nproc else "")))
    if d_run is None:
        out["detected"] = False
        return out
    state = compare_state(d_cont, d_run, last)
    out["detected"] = bool(state["differing"])
    out["digits"] = {k: v for k, v in state["fields"].items()
                     if k.split(":")[1] in ("Theta", "Salt", "EtaN")}
    return out


def main(argv=None):
    """Check the selected cases and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mpi", type=int, default=0, metavar="N")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--control", action="store_true",
                        help="also restart from the wrong pickup, which "
                             "the state comparison must see")
    parser.add_argument("--build", action="store_true",
                        help="compile build_esx_nlfs[_mpiN] when missing or "
                             "older than its sources")
    parser.add_argument("--mutant", choices=sorted(MUTANTS), default=None,
                        help="compile (when stale) and run on the named "
                             "mutant build, which the check must fail")
    parser.add_argument("--use-build", default=None, metavar="DIR",
                        help="run every case on this build directory")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=1800.0, metavar="S")
    parser.add_argument("--min-distinct", type=int, default=5, metavar="N")
    args = parser.parse_args(argv)
    if args.mpi < 0:
        parser.error("--mpi needs a positive process count")
    selected = list(CASES)
    if args.case:
        unknown = set(args.case) - {c["name"] for c in CASES}
        if unknown:
            print("unknown case(s): %s" % sorted(unknown), file=sys.stderr)
            return 2
        selected = [c for c in CASES if c["name"] in args.case]
    if args.mutant:
        args.use_build = MUTANTS[args.mutant][0]
        if not build_ok(args.use_build, lambda: write_mutant_code(
                args.mutant), args.mpi):
            return 2
    elif args.build and any(c.get("sync") for c in selected):
        if not build_ok(NLFS_BUILD, write_nlfs_code, args.mpi):
            return 2
    results = []
    for case in selected:
        build = args.use_build or (NLFS_BUILD if case.get("sync") else BUILD)
        binary = os.path.join(LAB, build + ("_mpi%d" % args.mpi
                                            if args.mpi else ""), "mitgcmuv")
        if not os.path.isfile(binary):
            print("missing %s: build it (tests/mitgcm_oracle.sh lab_sea "
                  "input%s, or --build for the synchronous build)"
                  % (binary, " -mpi %d" % args.mpi if args.mpi else ""),
                  file=sys.stderr)
            return 2
        if not args.use_build:
            stale = check_build_fresh(binary, os.path.join(LAB, "code"))
            if stale:
                print(stale, file=sys.stderr)
                return 2
        if case.get("refuse"):
            res = check_refusal(case, args.mpi, build, args.timeout, args.keep)
            results.append(res)
            print_result(res)
            continue
        for path in ("sparse", "dense"):
            if path == "dense" and case.get("dense") is False:
                continue
            res = check_path(case, path, args.mpi, build, args.timeout,
                             args.keep, args.min_distinct, args.control)
            results.append(res)
            print_result(res)
    if args.json:
        print(json.dumps(results, indent=1))
    failed = [r for r in results if r["problems"]]
    print("%d of %d runs passed" % (len(results) - len(failed), len(results)))
    if any(r.get("unusable") for r in results):
        return 2
    return 1 if failed or not results else 0


def build_ok(build, write_code, nproc):
    """Compile ``build`` (and its MPI variant) when stale; report it."""
    ok = True
    for mpi in ([False, True] if nproc else [False]):
        name = build + ("_mpi%d" % nproc if mpi else "")
        info = build_if_stale(name, write_code=write_code, jobs=4,
                              mpi=mpi)
        ok = report_build(info) and ok
    return ok


def print_result(res):
    """Print the verdict line of one result and what is missing."""
    verdict = "FAIL" if res["problems"] else "PASS"
    if "refusal" in res:
        print("%s %s on %s, build %s: refusal %s" % (
            verdict, res["case"], "%d processes" % res["processes"]
            if res["processes"] else "1 process", res["build"],
            res["refusal"]))
        for msg in res["problems"]:
            print("     missing: %s" % msg)
        return
    field = res.get("field", {})
    state = res.get("state", {})
    digit = state.get("digits", {})
    key = [k for k in digit if k.endswith(":EtaN")]
    print("%s %s/%s on %s, build %s: %s of %s dumps differ (%s distinct "
          "fields), %d of %d state fields differ%s"
          % (verdict, res["case"], res["path"],
             "%d processes" % res["processes"] if res["processes"]
             else "1 process", res["build"], field.get("differing_dumps", "?"),
             field.get("dumps", "?"), field.get("distinct", "?"),
             len(state.get("differing", [])), len(digit),
             ", EtaN digits %.1f" % digit[key[0]] if key else ""))
    if "min_digits" in state:
        print("     least matching digits of the judged state: %s"
              % ("bitwise" if state["min_digits"] >= 16.0
                 else "%.1f" % state["min_digits"]))
    win = res.get("window")
    if win:
        print("     restart at iteration %s, weight of the earlier record "
              "%.4f, %d brackets over the segment"
              % (win.get("first_it"), win.get("first_fac", float("nan")),
                 win["brackets"]))
    ctrl = res.get("control")
    if ctrl is not None:
        print("     control (wrong pickup): %s; digits %s"
              % ("detected" if ctrl.get("detected") else "NOT DETECTED",
                 {k: round(v, 1) for k, v in ctrl.get("digits", {}).items()}))
    for msg in res["problems"]:
        print("     missing: %s" % msg)


if __name__ == "__main__":
    sys.exit(main())
