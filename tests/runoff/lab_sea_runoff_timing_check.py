#!/usr/bin/env python3
"""Check the runoff that pkg/exf applied in the lab_sea ``input.rnof_*`` runs.

For every ``MITgcm/verification/lab_sea/input.rnof_<X>`` case the script reads

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
weight of the later record over the monitor times (``--json`` also lists the
records held and the records with non-zero weight at those times). The
``input.rnof_daily`` and ``input.rnof_yearly`` runs print the monitor every
12 h, so the weights 0, 0.5 and (in the yearly case) the year-wrap weight all
occur. The exit status is non-zero when a statistic
differs by more than the tolerance (1e-12 relative to the largest runoff
value), when a run directory or its monitor output is missing, or when no
case is found.

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
    results = [check_case(d, suffix, weights) for d in directories]
    for r in results:
        print("%-4s %-18s %-24s %4s samples  %s .. %s  %s" % (
            "PASS" if r["ok"] else "FAIL", r["case"], r.get("mode", "-"),
            r.get("samples", "-"), r.get("first", "-"), r.get("last", "-"),
            r["message"]))
    if not results:
        print("FAIL no input.rnof_* case found under %s" % LAB)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump({"tolerance": TOLERANCE, "run_suffix": suffix,
                       "results": results}, f, indent=1)
    return 0 if results and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
