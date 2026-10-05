#!/usr/bin/env python3
"""Check the runoff timing of the lab_sea ``input.rnof_*`` runs, dense and sparse.

The model of this script is the pkg/exf record machinery: it reads the
``runoff*`` settings of a case's ``data.exf`` and predicts which records
of a dense ``runoffFile`` exf holds at a given date and with which
weights. It judges two kinds of case with it.

**Dense cases** (a ``runoffFile``, no ``pkg/rnf``) are judged on the
``exf_runoff_*`` monitor statistics: the predicted field is compared with
the four statistics the model printed, at every monitor time. This is
what qualifies the model of the conventions itself.

**Sparse cases** (``data.rnf`` and ``useRNF``, with a blank
``runoffFile``) have no such monitor to compare: exf writes
``exf_runoff_*`` only for a dense file (``exf_monitor.F``) and
``pkg/rnf`` publishes no monitor of its own yet (RUNOFF-015). They are
judged instead on the record selection itself, which is the question
RUNOFF-005 is about: at every forcing step, the two records and the
weight that ``RNF_FIELDS_LOAD`` reported in its trace are compared with
the two records and the weight the exf conventions give for the same
model time, taken from the **dense twin** of the case
(``input.rnof_sp_daily`` against ``input.rnof_daily``;
:func:`check_sparse_case`). So a sparse case passes when the sparse
reader chooses what pkg/exf would choose, step by step, over the whole
run. A sparse case with no dense twin is reported as ``SKIP``, with the
reason, and counts as neither a pass nor a failure --
``lab_sea/input.rnof_sp_const`` is the one skipped, a constant record
converted from ``input.rnof_const``, whose dense case has no timing to
compare.

What a sparse verdict here does **not** cover is the field those records
produce. That is ``tests/rnf/applied_field_check.py``, which compares the
applied field with the one the file asks for, bitwise, and
``tests/rnf/timing_field_check.py``, which compares it cell by cell with
a dense run of the same case.

For every dense ``MITgcm/verification/lab_sea/input.rnof_<X>`` case the
script reads

* the runoff timing settings from the case's ``data.exf`` and the calendar
  start date from its ``data.cal`` (or from ``input/data.cal``),
* the dense runoff records (big-endian float32, shape (nrec, 16, 20), m/s),
* the monitor output of an existing run directory
  ``output_esx_input.rnof_<X>`` (``output_esx_input.rnof_<X>_mpi<N>`` with
  ``--mpi N``), written by ``tests/mitgcm_oracle.sh``.

At each monitor time it interpolates the records to that time under the
pkg/exf timing conventions and compares four monitor statistics of the result
with the values the model printed: ``exf_runoff_max``, ``exf_runoff_min``,
``exf_runoff_mean`` and ``exf_runoff_sd``. All four are taken over the wet
cells (negative depth in ``input/bathy.labsea1979``), and the mean and the
standard deviation are area weighted, as in ``MON_CALC_STATS_RL`` called with
``maskInC`` from ``EXF_MONITOR``; on this spherical-polar grid the cell area
is proportional to sin(north edge latitude) - sin(south edge latitude).

The conventions, with the routines that define them (see also the "Runoff
forcing tests" section of ``MITgcm/verification/lab_sea/README.md``):

* the date at model time ``t`` is the ``data.cal`` start date plus ``t``
  (``pkg/cal/cal_set.F``);
* ``runoffperiod = 0``: record 1 at all times (``exf_init_fld.F``);
* ``runoffperiod > 0``: record 1 is at the runoff start date, records are
  ``runoffperiod`` apart and the field is linear between them; a positive
  ``runoffRepCycle`` (default ``repeatPeriod``) wraps the time since record 1
  (``exf_getffieldrec.F``);
* ``useExfYearlyFields``: one file ``<name>_YYYY`` per year, records counted
  from the start date's offset within the year, the record after the last one
  of a year being record 1 of the next file (``exf_getffieldrec.F``,
  ``exf_getyearlyfieldname.F``);
* ``runoffperiod = -12``: 12 records, January to December, at the middle of
  each calendar month, repeated every year (``pkg/cal/cal_getmonthsrec.F``);
* ``runoffperiod = -1``: records at the middle of consecutive calendar months,
  record 1 being the month of the runoff start date (``exf_getmonthsrec.F``).

One line is printed per case, ending with the range of the interpolation
weight of the later record over the times judged (``--json`` also lists the
records held and the records with non-zero weight at those times, and for a
sparse case the first few disagreements). The
``input.rnof_daily`` and ``input.rnof_yearly`` runs print the monitor every
12 h, so the weights 0, 0.5 and (in the yearly case) the year-wrap weight all
occur; a sparse case is judged at every forcing step, so its weights cover
the whole interval. The exit status is non-zero when a dense statistic
differs by more than the tolerance (1e-12 relative to the largest runoff
value), when a sparse case disagrees with pkg/exf about a record or by more
than ``WEIGHT_TOLERANCE`` about a weight, when a run directory or its output
is missing, when a sparse run left no usable record trace, or when no dense
or no sparse case is found; a skipped case alone cannot make the run pass.

Usage (numpy is the only dependency)::

    python tests/runoff/lab_sea_runoff_timing_check.py [--mpi N] [--json FILE]
"""
import argparse
import datetime as dt
import glob
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.normpath(os.path.join(
    HERE, "..", "..", "MITgcm", "verification", "lab_sea"))

NX, NY = 20, 16            # global grid (code/SIZE.h)
YG0, DY = 46.0, 2.0        # ygOrigin and delY in degrees (input/data)
TOLERANCE = 1.0e-12        # relative to the largest expected runoff value
STATS = ("max", "min", "mean", "sd")
# The sparse verdict compares the interpolation weight pkg/rnf reported
# with the one the exf conventions give. The model prints 17 significant
# digits, so the only error left is how the two compute the same ratio of
# calendar intervals; 1e-12 is far below the 1/24 a one-hour error in a
# daily record would give, and below the 2e-4 of a one-minute error.
WEIGHT_TOLERANCE = 1.0e-12
# A sparse case that reported fewer record lines than this did not leave a
# usable trace (RNF_debugLev below 3), which is a failure and not a pass
# over no samples.
MIN_TRACE = 10
# Disagreeing steps reported in detail; the count is kept separately.
EXAMPLES = 5


def namelist_value(text, key, default=None):
    """Last value given to ``key`` in namelist text, comment lines skipped."""
    value = default
    pattern = re.compile(r"^\s*%s\s*=\s*([^,\n]+)" % re.escape(key), re.I)
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = pattern.match(line)
        if m:
            value = m.group(1).strip().strip("'").strip()
    return value


def to_date(date1, date2):
    """Datetime from pkg/cal integers YYYYMMDD and HHMMSS."""
    d1, d2 = int(date1), int(date2)
    return dt.datetime(d1 // 10000, d1 // 100 % 100, d1 % 100,
                       d2 // 10000, d2 // 100 % 100, d2 % 100)


def calendar_start(directory):
    """Calendar start date of a case: its ``data.cal``, or ``input``'s."""
    path = os.path.join(directory, "data.cal")
    if not os.path.exists(path):
        path = os.path.join(LAB, "input", "data.cal")
    text = open(path).read()
    return to_date(namelist_value(text, "startDate_1"),
                   namelist_value(text, "startDate_2", "0"))


def month_middle(year, month):
    """Middle of a calendar month."""
    start = dt.datetime(year, month, 1)
    end = dt.datetime(year + (month == 12), month % 12 + 1, 1)
    return start + (end - start) / 2


def month_bracket(date):
    """((year0, month0), (year1, month1), weight of the later month)."""
    y, m = date.year, date.month
    if date < month_middle(y, m):
        y0, m0 = (y, m - 1) if m > 1 else (y - 1, 12)
        y1, m1 = y, m
    else:
        y0, m0 = y, m
        y1, m1 = (y, m + 1) if m < 12 else (y + 1, 1)
    t0, t1 = month_middle(y0, m0), month_middle(y1, m1)
    return (y0, m0), (y1, m1), (date - t0) / (t1 - t0)


class Case:
    """Runoff settings and records of one input.rnof_<X> directory."""

    def __init__(self, directory):
        """Read the runoff settings from data.exf and the start date from
        data.cal (``input/data.cal`` when the case has none)."""
        self.dir = directory
        exf = open(os.path.join(directory, "data.exf")).read()
        cal_path = os.path.join(directory, "data.cal")
        if not os.path.exists(cal_path):
            cal_path = os.path.join(LAB, "input", "data.cal")
        cal = open(cal_path).read()
        self.base = to_date(namelist_value(cal, "startDate_1"),
                            namelist_value(cal, "startDate_2", "0"))
        self.file = namelist_value(exf, "runoffFile")
        self.period = float(namelist_value(exf, "runoffperiod", "0."))
        repeat = float(namelist_value(exf, "repeatPeriod", "0."))
        self.cycle = float(namelist_value(exf, "runoffRepCycle", repeat))
        self.yearly = "true" in namelist_value(
            exf, "useExfYearlyFields", ".FALSE.").lower()
        self.start = to_date(namelist_value(exf, "runoffstartdate1", "101"),
                             namelist_value(exf, "runoffstartdate2", "0")) \
            if self.period > 0 or self.period == -1 else None
        self._records = {}

    def records(self, year=None):
        """Records of the runoff file, or of the file of one year."""
        name = self.file if year is None else "%s_%04d" % (self.file, year)
        if name not in self._records:
            self._records[name] = np.fromfile(
                os.path.join(self.dir, name), dtype=">f4"
            ).reshape(-1, NY, NX).astype(np.float64)
        return self._records[name]

    def mode(self):
        """Name of the timing mode the settings select, for the report."""
        if self.period == 0:
            return "constant"
        if self.period == -12:
            return "month climatology (-12)"
        if self.period == -1:
            return "monthly (-1)"
        if self.yearly:
            return "yearly files"
        return "repeat cycle" if self.cycle > 0 else "no repeat"

    def bracket(self, date):
        """The two records pkg/exf holds at ``date`` and the weight of the
        later one: ``((year0, rec0), (year1, rec1), weight)``.

        Record numbers are 1-based as in the model output, and the year is
        0 unless yearly files are used. The weight is 0 exactly on a record
        time, where the later record is read but does not contribute.
        """
        if self.period == 0:
            return (0, 1), (0, 1), 0.0
        if self.period == -12:
            (_, m0), (_, m1), w = month_bracket(date)
            return (0, m0), (0, m1), w
        if self.period == -1:
            (y0, m0), (y1, m1), w = month_bracket(date)
            first = 12 * self.start.year + self.start.month
            return ((0, 12 * y0 + m0 - first + 1),
                    (0, 12 * y1 + m1 - first + 1), w)
        if self.period < 0:
            raise ValueError("unsupported runoffperiod %g" % self.period)
        p = self.period
        if self.yearly:
            year = date.year
            sec = (date - dt.datetime(year, 1, 1)).total_seconds()
            offset = (self.start - dt.datetime(self.start.year, 1, 1)
                      ).total_seconds()
            if sec < offset:
                year -= 1
            in_year = (dt.datetime(year + 1, 1, 1) - dt.datetime(year, 1, 1)
                       ).total_seconds()
            if sec < offset:
                sec += in_year
            t = sec - offset
            k = int((t + 0.5) // p)
            if offset + (k + 1) * p >= in_year:
                return (year, k + 1), (year + 1, 1), (t % p) / (in_year - k * p)
            return (year, k + 1), (year, k + 2), (t % p) / p
        t = (date - self.start).total_seconds()
        if self.cycle > 0:
            t0 = t % self.cycle
            k0 = int((t0 + 0.5) // p)
            k1 = int(((t + p) % self.cycle + 0.5) // p)
            return (0, k0 + 1), (0, k1 + 1), (t0 % p) / p
        if t < 0:
            raise ValueError("time before the first runoff record")
        k = int((t + 0.5) // p)
        return (0, k + 1), (0, k + 2), (t % p) / p

    def field(self, date):
        """Runoff (m/s) that pkg/exf applies at ``date``: the linear
        combination of the two bracketing records."""
        (y0, k0), (y1, k1), w = self.bracket(date)
        r0 = self.records(y0 or None)[k0 - 1]
        if w == 0.0:
            return r0
        return (1 - w) * r0 + w * self.records(y1 or None)[k1 - 1]


def area_weights():
    """Area weights of the wet cells (zero on land), shape (NY, NX)."""
    edges = np.radians(YG0 + DY * np.arange(NY + 1))
    area = (np.sin(edges[1:]) - np.sin(edges[:-1]))[:, None] * np.ones((1, NX))
    bathy = np.fromfile(os.path.join(LAB, "input", "bathy.labsea1979"),
                        dtype=">f4").reshape(NY, NX)
    return area * (bathy < 0.0)


def statistics(field, weights):
    """Monitor statistics of a field, as MON_CALC_STATS_RL computes them."""
    wet = weights > 0.0
    mean = (weights * field).sum() / weights.sum()
    var = (weights * (field - mean) ** 2).sum() / weights.sum()
    return {"max": field[wet].max(), "min": field[wet].min(), "mean": mean,
            "sd": math.sqrt(var)}


def monitor_series(path):
    """Monitor times (s) and runoff statistics printed in a model STDOUT."""
    text = open(path, errors="replace").read()

    def values(name):
        """All values printed for the monitor variable ``name``."""
        return [float(x) for x in re.findall(
            r"%MON " + name + r"\s+=\s+(\S+)", text)]
    out = {s: values("exf_runoff_" + s) for s in STATS}
    out["time"] = values("exf_time_sec")
    return out


def sparse_case(directory):
    """True when the case takes its runoff from ``pkg/rnf``, not from exf.

    Such a case names a sparse runoff file in ``data.rnf`` and switches the
    package on with ``useRNF`` in ``data.pkg``; its ``runoffFile`` is blank,
    so ``EXF_MONITOR`` writes no ``exf_runoff_*`` statistics at all
    (``exf_monitor.F``). The six dense cases have neither file setting.
    """
    if os.path.exists(os.path.join(directory, "data.rnf")):
        return True
    pkg = os.path.join(directory, "data.pkg")
    if os.path.exists(pkg):
        with open(pkg) as handle:
            text = "\n".join(line.split("#")[0] for line in handle)
        value = namelist_value(text, "useRNF")
        if value is not None and value.strip().upper().startswith(".T"):
            return True
    return False


def dense_twin(directory):
    """Dense ``input.rnof_<X>`` whose timing a sparse case must reproduce.

    The sparse cases are named after the dense ones they convert:
    ``input.rnof_sp_daily`` against ``input.rnof_daily``. Returns the path
    if it exists, else ``None`` -- a sparse case with no dense twin cannot
    be judged by this script, because the exf settings of the twin's
    ``data.exf`` are the conventions it compares against.
    """
    name = os.path.basename(directory)
    if not name.startswith("input.rnof_sp_"):
        return None
    twin = os.path.join(LAB, "input.rnof_" + name[len("input.rnof_sp_"):])
    return twin if os.path.isdir(twin) else None


def record_trace(path):
    """Records ``RNF_FIELDS_LOAD`` reported, from a model standard output.

    Returns a list of ``(model time, (year0, rec0), (year1, rec1), weight
    of the later record)``, one entry per forcing step, in the order the
    run printed them. ``pkg/rnf`` prints this line at every step when
    ``RNF_debugLev`` is at least ``debLevC`` (3), which the committed
    ``input.rnof_sp_*`` cases set; the weight it prints is the weight of
    the *earlier* record, so it is turned round here to match
    :meth:`Case.bracket`.

    The first line of a run is printed twice, by ``RNF_INIT_VARIA`` and
    by the first step, both for the start time; duplicates are harmless
    because each entry is judged on its own.
    """
    with open(path, errors="replace") as handle:
        text = handle.read()
    out = []
    for m in re.finditer(
            r"RNF_FIELDS_LOAD: it=\s*(-?\d+), rec0=\s*(-?\d+),"
            r" yr0=\s*(-?\d+), rec1=\s*(-?\d+), yr1=\s*(-?\d+),"
            r" t=\s*(\S+), fac=\s*(\S+)", text):
        out.append((float(m.group(6)),
                    (int(m.group(3)), int(m.group(2))),
                    (int(m.group(5)), int(m.group(4))),
                    1.0 - float(m.group(7))))
    return out


def check_sparse_case(directory, suffix):
    """Compare the records ``pkg/rnf`` selected with the exf conventions.

    The sparse path has no ``exf_runoff_*`` monitor to compare -- exf
    writes those only for a dense ``runoffFile`` (``exf_monitor.F``) and
    ``pkg/rnf`` publishes no monitor of its own yet (RUNOFF-015) -- so
    what is compared here is the record selection itself: at every
    forcing step of the run, the two records and the weight that
    ``RNF_FIELDS_LOAD`` reported, against the two records and the weight
    :meth:`Case.bracket` derives from the **dense** twin's ``data.exf``
    under the pkg/exf conventions this script already models and which
    its six dense cases qualify against the model's own monitor.

    That makes the sparse verdict exactly "the sparse reader picks the
    records and weights pkg/exf would", at every step of the run, which
    is the question RUNOFF-005 is about. What it does not compare is the
    field those records produce; that is
    ``tests/rnf/applied_field_check.py`` (bitwise, against the file) and
    ``tests/rnf/timing_field_check.py`` (cell by cell, against a dense
    run of the same case).
    """
    name = os.path.basename(directory)
    result = {"case": name, "run": "output_esx_%s%s" % (name, suffix),
              "ok": False, "sparse": True}
    output = os.path.join(LAB, result["run"], "output.txt")
    if not os.path.exists(output):
        result["message"] = "missing run output %s" % output
        return result
    twin = dense_twin(directory)
    if twin is None:
        result["message"] = ("no dense input.rnof_<X> twin: the exf timing "
                             "conventions to compare against are the twin's")
        return result
    result["dense_twin"] = os.path.basename(twin)
    case = Case(twin)
    result["mode"] = case.mode()
    trace = record_trace(output)
    if len(trace) < MIN_TRACE:
        result["message"] = (
            "the run reported %d RNF_FIELDS_LOAD record lines, fewer than "
            "the %d this check needs (RNF_debugLev must be at least 3)"
            % (len(trace), MIN_TRACE))
        return result
    base = calendar_start(directory)
    held, weighted, wmin, wmax = set(), set(), 1.0, 0.0
    # ``bad`` keeps at most EXAMPLES of them, so the count has to be kept
    # separately: reporting the length of the example list as the count
    # would say "5 of 769 steps disagree" for a run in which every step
    # does, which is what a one-day shift of the start date produces.
    worst, nbad, bad = 0.0, 0, []
    try:
        for seconds, got0, got1, got_w in trace:
            date = base + dt.timedelta(seconds=seconds)
            r0, r1, w = case.bracket(date)
            held.update([r0, r1])
            weighted.add(r0 if w < 1.0 else r1)
            if w > 0.0:
                weighted.add(r1)
            wmin, wmax = min(wmin, w), max(wmax, w)
            # The weight of a record that contributes nothing is not
            # observable: with w == 0 the model applies record 0 alone
            # and need not even read record 1, so only the record that
            # carries the weight is compared then.
            same = (got0 == r0) if w < 1.0 else True
            if w > 0.0:
                same = same and got1 == r1
            if not same or abs(got_w - w) > WEIGHT_TOLERANCE:
                nbad = nbad + 1
                worst = max(worst, abs(got_w - w))
                if len(bad) < EXAMPLES:
                    bad.append({"time": seconds, "date": str(date),
                                "model": [got0, got1, got_w],
                                "exf": [list(r0), list(r1), w]})
    except (ValueError, IndexError, OSError) as exc:
        result["message"] = "cannot evaluate the records: %s" % exc
        return result
    result.update(
        samples=len(trace), first=str(base + dt.timedelta(
            seconds=trace[0][0])), last=str(base + dt.timedelta(
                seconds=trace[-1][0])),
        records_held=sorted(held), records_with_weight=sorted(weighted),
        weight_min=wmin, weight_max=wmax, disagreements=nbad,
        disagreement_examples=bad, worst_weight_error=worst)
    result["ok"] = nbad == 0
    result["message"] = (
        "%d of %d steps disagree with pkg/exf; largest weight error %.1e; "
        "weight of the later record %.3f..%.3f over the forcing steps"
        % (nbad, len(trace), worst, wmin, wmax))
    if bad:
        result["message"] += "; first: %s" % (bad[0],)
    return result


def check_case(directory, suffix, weights):
    """Compare one case; return a result dictionary with key ``ok``."""
    name = os.path.basename(directory)
    result = {"case": name, "run": "output_esx_%s%s" % (name, suffix),
              "ok": False}
    output = os.path.join(LAB, result["run"], "output.txt")
    if not os.path.exists(output):
        result["message"] = "missing run output %s" % output
        return result
    case = Case(directory)
    result["mode"] = case.mode()
    series = monitor_series(output)
    n = len(series["time"])
    if n < 2 or any(len(series[s]) != n for s in STATS):
        result["message"] = "monitor output has %d runoff records" % n
        return result
    worst = dict.fromkeys(STATS, 0.0)
    distinct = set()
    held, weighted, wmin, wmax = set(), set(), 1.0, 0.0
    try:
        for i, t in enumerate(series["time"]):
            date = case.base + dt.timedelta(seconds=t)
            r0, r1, w = case.bracket(date)
            held.update([r0, r1])
            weighted.add(r0 if w < 1.0 else r1)
            if w > 0.0:
                weighted.add(r1)
            wmin, wmax = min(wmin, w), max(wmax, w)
            expected = statistics(case.field(date), weights)
            distinct.add(series["max"][i])
            for s in STATS:
                err = abs(series[s][i] - expected[s]) / expected["max"]
                worst[s] = max(worst[s], err)
    except (ValueError, IndexError, OSError) as exc:
        result["message"] = "cannot evaluate the records: %s" % exc
        return result
    result.update(
        samples=n, distinct_max_values=len(distinct),
        first=str(case.base + dt.timedelta(seconds=series["time"][0])),
        last=str(case.base + dt.timedelta(seconds=series["time"][-1])),
        worst_relative_error=worst,
        records_held=sorted(held), records_with_weight=sorted(weighted),
        weight_min=wmin, weight_max=wmax)
    result["ok"] = all(v <= TOLERANCE for v in worst.values())
    result["message"] = ("largest relative error %.1e; weight of the later "
                         "record %.3f..%.3f over the monitor times"
                         % (max(worst.values()), wmin, wmax))
    return result


def main():
    """Check every case, print one line each and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--mpi", type=int, default=0, metavar="N",
                        help="check the output_esx_input.rnof_<X>_mpiN runs")
    parser.add_argument("--json", metavar="FILE",
                        help="also write the results to this JSON file")
    args = parser.parse_args()
    suffix = "_mpi%d" % args.mpi if args.mpi else ""
    directories = sorted(glob.glob(os.path.join(LAB, "input.rnof_*")))
    weights = area_weights()
    # A sparse case matches the glob and is judged on its record trace,
    # not on the monitor it does not write. One that has no dense twin
    # to take the exf conventions from is reported as a skip, with the
    # reason, and counts as neither a pass nor a failure.
    dense, sparse, skipped = [], [], []
    for d in directories:
        if not sparse_case(d):
            dense.append(d)
        elif dense_twin(d) is None:
            skipped.append({
                "case": os.path.basename(d),
                "reason": "sparse runoff case with no dense input.rnof_<X>"
                          " twin: the pkg/exf timing conventions this check"
                          " compares against are read from the twin's"
                          " data.exf, and there is none to read"})
        else:
            sparse.append(d)
    results = [check_case(d, suffix, weights) for d in dense] \
        + [check_sparse_case(d, suffix) for d in sparse]
    for r in results:
        print("%-4s %-18s %-24s %4s samples  %s .. %s  %s" % (
            "PASS" if r["ok"] else "FAIL", r["case"], r.get("mode", "-"),
            r.get("samples", "-"), r.get("first", "-"), r.get("last", "-"),
            r["message"]))
    for s in skipped:
        print("SKIP %-18s %s" % (s["case"], s["reason"]))
    if not dense or not sparse:
        print("FAIL no %s input.rnof_* case found under %s (%d skipped)"
              % ("dense" if not dense else "sparse", LAB, len(skipped)))
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump({"tolerance": TOLERANCE,
                       "weight_tolerance": WEIGHT_TOLERANCE,
                       "run_suffix": suffix,
                       "results": results, "skipped": skipped}, f, indent=1)
    return 0 if dense and sparse and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
