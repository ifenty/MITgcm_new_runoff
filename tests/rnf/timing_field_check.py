#!/usr/bin/env python
"""Sparse = dense runoff, cell by cell and step by step, for each time mode.

**Why this check and not the digit oracle.** Each
``lab_sea/input.rnof_sp_<X>`` case is the dense ``input.rnof_<X>`` with
the runoff taken from ``pkg/rnf`` instead of from a dense exf
``runoffFile``, so the dense reference in ``results/`` looks like the
natural oracle. Measured, it is not one for the timed cases: with
interpolation the sparse path forms
``(fac*flux0 + (1-fac)*flux1)/rA`` where the dense path forms
``fac*v0 + (1-fac)*v1`` on the same values, and those differ by about
one unit in the last place. Over the 48 steps of ``input.rnof_const``
that stays invisible (16 matching digits), but over the 768 steps of
``input.rnof_daily`` lab_sea amplifies it: measured on 2026-10-05,
the applied runoff agreed to 1e-16 while ``cg2d_init_res`` had drifted
to 4 matching digits of the 10 required, and the solution monitors to
3 to 13. A digit threshold on a chaotic 32-day run therefore cannot
tell a round-off difference from a wrong record, in either direction.

This check compares the quantity the issue is actually about -- the
runoff field the model applies -- between a dense run and a sparse run
of the same case, at every time step:

1. both runs dump the exf ``runoff`` array as one global float64 array
   per step, through an ``EXFroff`` diagnostic stream (the same
   mechanism as ``tests/rnf/applied_field_check.py``, which documents
   why that dump is the field the model goes on to apply);
2. the two sets of dumps are compared cell by cell at every iteration.
   A wrong record, a wrong weight, a wrong repeat wrap or a wrong
   yearly file changes the field by a sizeable fraction of the runoff,
   while the round-off above is 1e-16 relative, so ``--rtol 1e-12``
   separates them by four orders of magnitude;
3. the comparison is refused unless it is sensitive: the case has to
   show at least ``--min-distinct`` distinct applied fields over its
   dumps. A mode whose records never changed during the run would
   compare a constant field and prove nothing about timing.

``--control`` adds, per case, a sparse run with ``RNF_holdRecord``
switched on. Holding each record over its interval is a different
field from interpolating between two, so the control **must** fail the
comparison; a case whose control passes is not measuring anything.
That is the demonstration this check works, and it also measures how
far hold-exact is from interpolation.

**The long climatology case** (``clim_long``) is the one the committed
oracles cannot do. ``input.rnof_clim`` is a 12-record 2628000 s
climatology with a 365-day repeat cycle whose record 1 is dated
16 January 1978 12:00. pkg/exf wraps the elapsed time modulo the cycle
from that real date, so the cycle slips against the calendar by a day
at every leap year. A reader that anchored the cycle on the model's own
calendar year instead -- the obvious "nominal year" reading of a
climatology -- agrees with exf exactly until a leap day has
intervened. Measured on this file, the span of the
committed case, 1978-12-01 plus 50 days, cannot tell exf's reading from
**any** of the four nominal-year readings of
:func:`_nominal_fields`: all four are exactly equal to it there.
``clim_long`` therefore runs the same case from 1981-12-01 for 75
days, where all four differ by 2.247404e-02 of the peak runoff, and
reports both the
dense-versus-sparse deviation and, computed in Python from the dense
records alone, how far each nominal reading would be from exf over the
dates the model actually dumped (``nominal_discrimination``). The case
fails if any of those figures is below ``--min-discrimination``,
because then the span does not separate that anchoring from the right
one and a pass would again be worthless.

That guard earns its keep: this case first used 1980-12-01, on which
three of the four readings differ by about 2.2e-2 and the fourth --
re-dating record 1 into the model's **start** year, which is the one
``RNF_TIME_SETUP``'s once-at-init resolution makes most likely to be
got wrong -- is **exactly 0.000000e+00**, because 1980-01-16 12:00 is
exactly two 365-day cycles after the file's record 1. The case passed
while being blind to it (review B of RUNOFF-005, correction round 1).
The list of readings is measured, not complete: a fifth would need its
own measurement, and :func:`_nominal_fields` says so.

Each case runs the existing binary of lab_sea through
``experiment_run_no_compile.sh``; nothing is compiled here. Build it
first with ``tests/mitgcm_oracle.sh lab_sea input`` (or ``-mpi N``).

The scratch input and run directories are removed afterwards
(``--keep`` leaves the run directories). Exit status: 0 if every case
passes, 1 if any fails or none ran, 2 if the binary is missing or a
``--case`` selection does not exist.

Usage::

    python tests/rnf/timing_field_check.py [--mpi N] [--case NAME ...]
                                           [--control] [--keep] [--json]
                                           [--rtol R] [--timeout S]
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import stat
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runoff"))
from refusal_check import (ROOT, VERIF, kill_run, read_file,  # noqa: E402
                           replace_line)
from applied_field_check import dumps, read_mds, set_namelist  # noqa: E402

EXPERIMENT = "lab_sea"
LAB = os.path.join(VERIF, EXPERIMENT)
PREFIX = "input.rnftime_"
BUILD = "build_esx"
STREAM = "rnfTime"

#: The cases, named explicitly: this check never discovers an experiment.
#: ``mode`` names the pair ``input.rnof_<mode>`` (dense) and
#: ``input.rnof_sp_<mode>`` (sparse). ``cal_start`` and ``days``
#: override the calendar start date and the run length of both runs of
#: the pair, which is how ``clim_long`` reaches a leap day without a
#: run of several model years.
CASES = (
    {"name": "daily", "mode": "daily"},
    {"name": "month", "mode": "month"},
    {"name": "month1", "mode": "month1"},
    {"name": "clim", "mode": "clim"},
    {"name": "yearly", "mode": "yearly"},
    # The span is chosen by measurement, not by taste, and the first
    # choice was wrong: on 1980-12-01 plus 75 days the ``start_year``
    # reading of :func:`_nominal_fields` is exactly 0.000000e+00,
    # because 1980-01-16 12:00 is exactly two 365-day cycles after the
    # file's record 1, so that span could not tell the right anchoring
    # from the one this reader is most likely to have got wrong
    # (review B of RUNOFF-005). 1981-12-01 plus 75 days separates all
    # four at 2.247404e-02 of the peak, for the same run cost.
    {"name": "clim_long", "mode": "clim", "cal_start": 19811201, "days": 75,
     "nominal": True},
)

DATA_DIAGNOSTICS = """# Sparse = dense applied-runoff oracle of
# tests/rnf/timing_field_check.py: dump the exf runoff field the model
# applies, as one global float64 array per time step.
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


def time_step(text):
    """Return ``deltaTClock`` of a ``data`` file, as a float."""
    match = re.search(r"^\s*deltaTClock\s*=\s*([-+0-9.DdEe]+)", text,
                      re.MULTILINE)
    if not match:
        raise ValueError("data does not set deltaTClock")
    return float(match.group(1).replace("D", "E").replace("d", "e"))


def start_time(text):
    """Return ``startTime`` of a ``data`` file, as a float."""
    match = re.search(r"^\s*startTime\s*=\s*([-+0-9.DdEe]+)", text,
                      re.MULTILINE)
    if not match:
        raise ValueError("data does not set startTime")
    return float(match.group(1).replace("D", "E").replace("d", "e"))


def write_input(case, source, input_dir, hold=False):
    """Build one scratch input directory from ``source``; return its facts.

    Every regular file of ``source`` is copied, then ``data`` is given
    the two output settings the dump needs and, where the case asks for
    them, a new ``endTime``; ``data.cal`` is given a new start date; and
    ``data.diagnostics`` is written. With ``hold``, ``data.rnf`` is given
    ``RNF_holdRecord = .TRUE.`` -- the control's perturbation.

    Returns ``(deltaT, startTime)`` of the run, which turn a dump's
    iteration label into the model time its field was loaded at.
    """
    for name in sorted(os.listdir(source)):
        src = os.path.join(source, name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(input_dir, name))
    with open(os.path.join(input_dir, "data")) as fh:
        data = fh.read()
    delta = time_step(data)
    begin = start_time(data)
    # float64 for the dump and for RAC.data, and MDS output even when the
    # set-up uses MNC. Output settings only.
    data = set_namelist(data, "PARM01", "writeBinaryPrec",
                        " writeBinaryPrec=64,")
    data = set_namelist(data, "PARM03", "outputTypesInclusive",
                        " outputTypesInclusive=.TRUE.,")
    if case.get("days"):
        data = set_namelist(data, "PARM03", "endTime",
                            " endTime=%r," % (begin + case["days"] * 86400.0))
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)
    if case.get("cal_start"):
        path = os.path.join(input_dir, "data.cal")
        if not os.path.isfile(path):
            shutil.copyfile(os.path.join(LAB, "input", "data.cal"), path)
        with open(path) as fh:
            text = replace_line(fh.read(), "startDate_1",
                                " startDate_1=%d," % case["cal_start"])
        with open(path, "w") as fh:
            fh.write(text)
    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(DATA_DIAGNOSTICS.format(stream=STREAM, dt=delta))
    if hold:
        path = os.path.join(input_dir, "data.rnf")
        with open(path) as fh:
            text = fh.read()
        if "RNF_holdRecord" in text:
            text = replace_line(text, "RNF_holdRecord",
                                "  RNF_holdRecord = .TRUE.,")
        else:
            text = text.replace(" &RNF_PARM01\n",
                                " &RNF_PARM01\n  RNF_holdRecord = .TRUE.,\n")
        with open(path, "w") as fh:
            fh.write(text)
    prep = os.path.join(input_dir, "prepare_run")
    if os.path.isfile(prep):
        # A prepare_run that links files of another input directory in
        # must not link over the three files this case rewrote. The
        # lab_sea runoff cases' script only makes symlinks of forcing
        # files under other names and has no skipList at all, which is
        # left alone; a script with one gets the three names added; more
        # than one is refused rather than half-patched.
        with open(prep) as fh:
            text = fh.read()
        new, count = re.subn(r'skipList="([^"]*)"',
                             r'skipList="\1 data data.cal data.diagnostics"',
                             text)
        if count > 1:
            raise ValueError("%s/prepare_run has %d skipList assignments, "
                             "expected at most 1: it would link over the "
                             "case's own data files" % (source, count))
        for name in ("data", "data.cal", "data.diagnostics"):
            if re.search(r"^[^#\n]*\b%s\b" % re.escape(name), text,
                         re.MULTILINE) and not count:
                raise ValueError("%s/prepare_run names %s but has no "
                                 "skipList: it may link over the case's own "
                                 "copy" % (source, name))
        with open(prep, "w") as fh:
            fh.write(new)
        os.chmod(prep, os.stat(prep).st_mode | stat.S_IXUSR | stat.S_IXGRP
                 | stat.S_IXOTH)
    return delta, begin


def run_model(input_name, nproc, timeout):
    """Run one scratch input; return ``(run dir, exit status, timed out)``."""
    output_name = "output_esx_" + input_name
    build, mpi_args = BUILD, []
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


def forcing_time(iteration, delta, begin, n_iter0):
    """Model time the forcing of the dump labelled ``iteration`` was loaded at.

    ``FORWARD_STEP`` loads the forcing at ``myTime = startTime +
    deltaTClock*(iLoop-1)`` and then raises the counters by one step
    before ``DO_THE_MODEL_IO`` writes the dump, so the label could have
    been one step ahead of the field. It is not, for a snapshot stream:
    ``DIAGNOSTICS_WRITE`` labels a stream of negative frequency with
    ``wrIter = myIter - 1`` and ``wrTime = myTime - deltaTClock``
    precisely "to be consistent with state-variable time-step"
    (``pkg/diagnostics/diagnostics_write.F``, the ``freqSec.LT.0``
    branch). The two offsets cancel, so the dump labelled N carries the
    field loaded at iteration N, i.e. at ``startTime + deltaTClock*(N -
    nIter0)``.
    """
    return begin + delta * (iteration - n_iter0)


def compare_runs(dense_dir, sparse_dir, rtol):
    """Compare the dumps of a dense and a sparse run of the same case."""
    import numpy as np
    out = {"problems": []}
    rac, shape = read_mds(dense_dir, "RAC")
    d_iters, d_stray = dumps(dense_dir, STREAM)
    s_iters, s_stray = dumps(sparse_dir, STREAM)
    out["dumps"] = len(d_iters)
    if d_stray or s_stray:
        out["problems"].append(
            "only dumps of the %s stream to match %s*: %s are out of scope"
            % (STREAM, STREAM, (d_stray + s_stray)[:5]))
        return out
    if not d_iters or d_iters != s_iters:
        out["problems"].append(
            "the two runs to dump the same iterations (dense %d, sparse %d)"
            % (len(d_iters), len(s_iters)))
        return out
    worst, worst_at = 0.0, None
    extra = missing = nonfinite = 0
    distinct, volumes = set(), []
    for iteration in d_iters:
        dense, d_shape = read_mds(dense_dir, STREAM, iteration)
        sparse, s_shape = read_mds(sparse_dir, STREAM, iteration)
        if d_shape != shape or s_shape != shape:
            raise ValueError("%s.%s has shape %s/%s, RAC.data has %s"
                             % (STREAM, iteration, d_shape, s_shape, shape))
        extra += int(np.count_nonzero((sparse != 0.0) & (dense == 0.0)))
        missing += int(np.count_nonzero((sparse == 0.0) & (dense != 0.0)))
        nonfinite += int(np.count_nonzero(~np.isfinite(sparse)))
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(dense != 0.0,
                           np.abs(sparse - dense) / np.abs(dense),
                           np.where(sparse != 0.0, 1.0, 0.0))
        # A non-finite deviation must not lose the comparison for the
        # maximum: left as a NaN it would make every ">" false.
        rel = np.where(np.isfinite(rel), rel, np.inf)
        k = int(np.argmax(rel))
        if float(rel[k]) > worst:
            worst = float(rel[k])
            worst_at = {"iteration": iteration, "cell": k,
                        "dense": float(dense[k]), "sparse": float(sparse[k])}
        distinct.add(round(float(dense.max()), 18))
        volumes.append((float((dense * rac).sum()),
                        float((sparse * rac).sum())))
    out.update(cells=rac.size, extra=extra, missing=missing,
               nonfinite=nonfinite, max_rel=worst, worst=worst_at,
               distinct_dense_fields=len(distinct),
               volume_rel=max(abs(s - d) / abs(d) if d else 0.0
                              for d, s in volumes))
    if extra or missing:
        out["problems"].append("no cell to differ in placement (found %d "
                               "extra and %d missing)" % (extra, missing))
    if nonfinite:
        out["problems"].append("every applied value to be finite (found %d "
                               "that are not)" % nonfinite)
    if worst > rtol:
        out["problems"].append("the sparse field to equal the dense field to "
                               "%g relative (found %.3e at %s)"
                               % (rtol, worst, worst_at))
    return out


def _nominal_fields(case, start_year=None):
    """Return the nominal-year readings of a fixed climatology.

    Each is a function of a date returning the dense field that reading
    would apply, built from the records and the nominal record times of
    the file and from no model output. Each anchors a repeating
    climatology on the model's own calendar year instead of on the real
    date of record 1, which is what pkg/exf does.

    **This is a measured list, not a complete one.** There is no
    argument here that a reader could go wrong in no other way; these
    are the four that have been written down and measured, and a fifth
    would need its own measurement. An earlier version of this
    docstring claimed the first three were "the three ways", and review
    B of RUNOFF-005 falsified that by finding the fourth -- which the
    case was then blind to.

    ``day_of_year``
        the cycle stays the span of the bounds (365 days here) but the
        phase is the day of the model year instead of the time elapsed
        since record 1;
    ``record_dates``
        every record is placed at its own offset in seconds after
        1 January of the model's year, and the bracket is taken between
        those times;
    ``month_day``
        every record is placed at the same month, day and time of day
        in the model's year, so a leap day stretches the interval that
        contains it;
    ``start_year`` (only with ``start_year`` given)
        record 1 is re-dated into the model's **start** year and the
        fixed cycle wraps from there. This is the one the shape of
        ``RNF_TIME_SETUP`` makes most likely to be got wrong, because
        that routine resolves the date of record 1 once at
        initialization, so a reader that resolved it against the start
        year rather than against the file's own year would look right.

    Measured on ``lab_sea/input.rnof_clim`` over hourly dates
    (2026-10-05, correction round 1), against the exf reading of
    ``lab_sea_runoff_timing_check.Case``. Scanning 43825 hourly dates
    from 1978-12-01 to 1983-12-01, the first date at which each parts
    from exf is 1981-01-01 00:00 (``day_of_year``), 1980-12-16 03:00
    (``record_dates``) and 1980-02-15 23:00 (``month_day``), each
    reaching 2.247404e-02 of the peak; ``start_year`` anchored on 1980
    **never differs over those five years at all**, and anchored on
    1981 differs from the first date scanned. Over the spans the cases
    use:

    * on the span of the committed case, 1978-12-01 plus 50 days, **all
      four are exactly equal to the exf reading** (0.000000e+00), which
      is why that case cannot qualify this reader at all and
      ``clim_long`` exists;
    * on 1980-12-01 plus 75 days, the first three differ by 2.247404e-02,
      2.175868e-02 and 2.247404e-02 of the peak runoff, and
      ``start_year`` is **exactly 0.000000e+00**: 1980-01-16 12:00 is
      730 days after the file's 1978-01-16 12:00, which is exactly two
      365-day cycles, so that anchoring lands on the same phase -- for
      ever, not just over this span. That
      span is what ``clim_long`` used before this correction;
    * on 1981-12-01 plus 75 days, all four differ by 2.247404e-02,
      because 1981-01-16 12:00 is 1096 days after record 1, which is
      3.0027 cycles. That is the span ``clim_long`` now uses.
    """
    records = case.records()
    nrec = records.shape[0]
    period, cycle = case.period, case.cycle
    year = case.start.year
    offset = (case.start - dt.datetime(year, 1, 1)).total_seconds()
    offsets = [offset + k * period for k in range(nrec)]
    month_day = []
    for k, off in enumerate(offsets):
        when = dt.datetime(year, 1, 1) + dt.timedelta(seconds=off)
        month_day.append((when.month, when.day, when.hour * 3600
                          + when.minute * 60 + when.second, k))

    def day_of_year(date):
        day = (date - dt.datetime(date.year, 1, 1)).total_seconds()
        t = (day - offset) % cycle
        k0 = int(t // period)
        weight = (t - k0 * period) / period
        return ((1 - weight) * records[k0 % nrec]
                + weight * records[(k0 + 1) % nrec])

    def _between(times, date):
        times.sort()
        for i in range(len(times) - 1):
            if times[i][0] <= date < times[i + 1][0]:
                (t0, k0), (t1, k1) = times[i], times[i + 1]
                weight = (date - t0).total_seconds() \
                    / (t1 - t0).total_seconds()
                return (1 - weight) * records[k0] + weight * records[k1]
        raise ValueError("no nominal bracket for %s" % date)

    def record_dates(date):
        return _between([(dt.datetime(y, 1, 1) + dt.timedelta(seconds=off), k)
                         for y in (date.year - 1, date.year, date.year + 1)
                         for k, off in enumerate(offsets)], date)

    def by_month_day(date):
        return _between([(dt.datetime(y, m, d) + dt.timedelta(seconds=s), k)
                         for y in (date.year - 1, date.year, date.year + 1)
                         for m, d, s, k in month_day], date)

    out = [("day_of_year", day_of_year), ("record_dates", record_dates),
           ("month_day", by_month_day)]
    if start_year is not None:
        anchor = case.start.replace(year=start_year)

        def from_start_year(date):
            t = (date - anchor).total_seconds() % cycle
            k0 = int(t // period)
            weight = (t - k0 * period) / period
            return ((1 - weight) * records[k0 % nrec]
                    + weight * records[(k0 + 1) % nrec])

        out.append(("start_year", from_start_year))
    return tuple(out)


def nominal_discrimination(case_dir, dates, start_year):
    """How far each nominal-year reading of a climatology is from exf's.

    pkg/exf anchors the repeat cycle on the real date record 1 carries
    and wraps the elapsed time from there, so the cycle slips against
    the calendar at every leap year. :func:`_nominal_fields` gives the
    readings that anchor on the model's calendar year instead;
    ``start_year`` is the model's first year, which the fourth of them
    needs.
    This returns, per reading, the largest relative difference of the
    applied field over ``dates`` and the first date at which it differs
    at all -- computed from the dense records and from nothing the
    model did.

    A span on which any of them is 0 cannot tell a correct reader from
    that one, so the caller requires every figure to be above a
    threshold before it accepts a pass. That is not a formality: the
    ``start_year`` reading is exactly 0 over the span this case used
    before correction round 1 of RUNOFF-005 (:func:`_nominal_fields`).
    """
    import numpy as np
    sys.path.insert(0, os.path.join(ROOT, "tests", "runoff"))
    from lab_sea_runoff_timing_check import Case
    case = Case(case_dir)
    if not (case.period > 0 and case.cycle > 0):
        raise ValueError("%s is not a fixed-period climatology" % case_dir)
    peak = float(np.abs(case.records()).max())
    out = {}
    for name, nominal in _nominal_fields(case, start_year):
        worst, first = 0.0, None
        for date in dates:
            rel = float(np.abs(nominal(date) - case.field(date)).max() / peak)
            if rel > 0.0 and first is None:
                first = str(date)
            worst = max(worst, rel)
        out[name] = {"max_relative": worst, "first_difference": first}
    return out


def check_case(case, nproc, timeout, keep, rtol, min_distinct,
               min_discrimination, control=False):
    """Run and judge one case; return the result dictionary."""
    name = case["name"] + ("_mpi%d" % nproc if nproc else "") \
        + ("_control" if control else "")
    result = {"case": case["name"], "processes": nproc, "control": control,
              "problems": []}
    dense_name = PREFIX + name + "_dense"
    sparse_name = PREFIX + name + "_sparse"
    dirs = [os.path.join(LAB, dense_name), os.path.join(LAB, sparse_name)]
    runs = []
    try:
        for path in dirs:
            shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path)
        dense_src = os.path.join(LAB, "input.rnof_" + case["mode"])
        sparse_src = os.path.join(LAB, "input.rnof_sp_" + case["mode"])
        for src in (dense_src, sparse_src):
            if not os.path.isdir(src):
                raise ValueError("missing input directory %s" % src)
        delta, begin = write_input(case, dense_src, dirs[0])
        write_input(case, sparse_src, dirs[1], hold=control)
        for input_name in (dense_name, sparse_name):
            run_dir, exit_code, timed_out = run_model(input_name, nproc,
                                                      timeout)
            runs.append(run_dir)
            logs = "\n".join(filter(None, (
                read_file(run_dir, n) for n in ("output.txt", "mpirun.log"))))
            if timed_out:
                result["problems"].append("%s to finish (it timed out)"
                                          % input_name)
                return result
            if exit_code != 0 or "Execution ended Normally" not in logs:
                result["problems"].append("%s to end normally (exit %s)"
                                          % (input_name, exit_code))
                return result
        result.update(compare_runs(runs[0], runs[1], rtol))
        if result["distinct_dense_fields"] < min_distinct:
            result["problems"].append(
                "at least %d distinct applied fields over the run (found %d):"
                " a forcing that does not change in time says nothing about"
                " record selection" % (min_distinct,
                                       result["distinct_dense_fields"]))
        if case.get("nominal"):
            n_iter0 = int(round(begin / delta))
            iters, _ = dumps(runs[0], STREAM)
            base = None
            with open(os.path.join(dirs[0], "data.cal")) as fh:
                text = fh.read()
            match = re.search(r"startDate_1\s*=\s*(\d+)", text)
            base = dt.datetime.strptime(match.group(1), "%Y%m%d")
            dates = [base + dt.timedelta(
                seconds=forcing_time(int(i), delta, begin, n_iter0))
                for i in iters]
            result["nominal_discrimination"] = nominal_discrimination(
                dirs[0], dates, base.year)
            for variant, got in sorted(
                    result["nominal_discrimination"].items()):
                if got["max_relative"] < min_discrimination:
                    result["problems"].append(
                        "a span on which the %s nominal-year anchoring of"
                        " the repeat cycle would differ from pkg/exf by at"
                        " least %g of the peak (found %.3e): on this span"
                        " this case cannot tell that anchoring from the"
                        " right one and passing it proves nothing"
                        % (variant, min_discrimination,
                           got["max_relative"]))
        if control:
            # Inverted: holding each record over its interval is a
            # different field from interpolating between two records, so
            # the comparison has to see it.
            seen = [p for p in result["problems"] if "to equal the dense" in p]
            result["problems"] = [p for p in result["problems"]
                                  if "to equal the dense" not in p
                                  and "to differ in placement" not in p]
            if not seen:
                result["problems"].append(
                    "the comparison to see hold-exact as a difference from"
                    " interpolation (largest relative deviation %.3e, at or"
                    " below the tolerance %g): a check that cannot see this"
                    " cannot see a wrong record either"
                    % (result.get("max_rel", 0.0), rtol))
        return result
    except (ValueError, OSError) as err:
        result["problems"].append(str(err))
        result["unusable"] = True
        return result
    finally:
        for path in dirs:
            shutil.rmtree(path, ignore_errors=True)
        if not keep:
            for path in runs:
                shutil.rmtree(path, ignore_errors=True)


def main(argv=None):
    """Check the selected cases and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mpi", type=int, default=0, metavar="N",
                        help="run on N MPI processes with build_esx_mpiN")
    parser.add_argument("--case", action="append", default=[],
                        help="check only this case (repeatable)")
    parser.add_argument("--control", action="store_true",
                        help="also run, per case, a sparse run with "
                             "RNF_holdRecord on, which must be detected as a "
                             "difference; without it the check is unproven "
                             "on this run")
    parser.add_argument("--keep", action="store_true",
                        help="keep the run directories")
    parser.add_argument("--json", action="store_true",
                        help="print the full results as JSON")
    parser.add_argument("--timeout", type=float, default=2400.0, metavar="S",
                        help="seconds after which a run counts as hanging")
    parser.add_argument("--rtol", type=float, default=1.0e-12, metavar="R",
                        help="largest relative deviation of the applied "
                             "field that still passes (default 1e-12: four "
                             "orders of magnitude above the 1e-16 round-off "
                             "of flux/rA against the dense value, and far "
                             "below any wrong record)")
    parser.add_argument("--min-distinct", type=int, default=5, metavar="N",
                        help="distinct applied fields a case needs (default "
                             "5): a constant forcing is not a timing test")
    parser.add_argument("--min-discrimination", type=float, default=5.0e-3,
                        metavar="R",
                        help="for clim_long, how far a nominal-year "
                             "anchoring must be from pkg/exf over the span "
                             "(default 5e-3 of the peak)")
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
    build = BUILD + ("_mpi%d" % args.mpi if args.mpi else "")
    binary = os.path.join(LAB, build, "mitgcmuv")
    if not os.path.isfile(binary):
        mpi = " -mpi %d" % args.mpi if args.mpi else ""
        print("missing %s: run tests/mitgcm_oracle.sh lab_sea input%s"
              % (binary, mpi), file=sys.stderr)
        return 2

    results = []
    for case in selected:
        results.append(check_case(case, args.mpi, args.timeout, args.keep,
                                  args.rtol, args.min_distinct,
                                  args.min_discrimination))
        if args.control:
            results.append(check_case(case, args.mpi, args.timeout, args.keep,
                                      args.rtol, args.min_distinct,
                                      args.min_discrimination, control=True))
    for res in results:
        verdict = "FAIL" if res["problems"] else "PASS"
        where = res["case"] + (" on %d processes" % res["processes"]
                               if res["processes"] else " on 1 process") \
            + (", control: RNF_holdRecord" if res["control"] else "")
        line = ("%s %s: %d dumps of %d cells, %d distinct dense fields, "
                "%d extra, %d missing, max relative deviation %.3e"
                % (verdict, where, res.get("dumps", 0), res.get("cells", 0),
                   res.get("distinct_dense_fields", 0), res.get("extra", 0),
                   res.get("missing", 0), res.get("max_rel", float("nan"))))
        print(line)
        for variant, got in sorted(
                res.get("nominal_discrimination", {}).items()):
            print("     a %s nominal-year anchoring would differ by %.3e of "
                  "the peak, first at %s"
                  % (variant, got["max_relative"], got["first_difference"]))
        for msg in res["problems"]:
            print("     missing: %s" % msg)
    if args.json:
        print(json.dumps(results, indent=1))
    failed = [r["case"] for r in results if r["problems"]]
    print("%d of %d cases passed" % (len(results) - len(failed), len(results)))
    if any(r.get("unusable") for r in results):
        return 2
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
