#!/usr/bin/env python3
"""EXF_CHECK_RANGE tests the runoff temperature, not the runoff (RUNOFF-037).

``pkg/exf/exf_check_range.F`` (inside ``ALLOW_RUNOFTEMP``) refuses a wet
cell whose ``runoftemp`` is below -2 or above 36 degC. Before RUNOFF-037
the upper bound read ``runoff`` (m/s) and the warning printed ``runoff``:
a temperature above 36 was never caught and a volume flux above 36 was
reported as a temperature error. Every case below is a run of lab_sea
that either stops in ``EXF_CHECK_RANGE`` with the named message or ends
normally; a refusal is a binary outcome, so that is the whole oracle. The
message must name ``runoftemp`` and print the temperature (the value is
read back from the ``D22.15`` field of the warning).

Cases (dense = ``runoffFile`` + ``runoftempfile`` with ``useRNF`` false,
sparse = ``pkg/rnf`` with ``runoff_temperature`` per source; both reach
the same shared check):

* refused: 36.5, 100 and -3 degC on the dense path; 36.5, 100 and -3 on
  the sparse path;
* accepted: exactly 36 and exactly -2 (dense, exact in float32), 35.9 and
  -2 on the sparse path, and 100 degC at a *dry* cell (dense; mask zero).
  The sparse upper boundary is 35.9, not 36: pkg/rnf hands exf
  ``(m*T)/m``, which for T = 36 is one ulp above 36 (measured: the
  warning prints 0.360000000000000D+02 and the run is refused), so the
  exact boundary is only meaningful on the dense path;
* ``dense_flux_40``: a volume flux of 40 m/s with a 10 degC temperature
  must be refused by the *volume* check ("runoff out of range") and must
  **not** print the temperature message.

The expected result on the unfixed build (``--unfixed``, a mods directory
that reverses the fix textually) is that exactly the cases in
:data:`UNFIXED_FAILS` fail; ``--unfixed`` requires that.

Usage: python3 tests/rnf/runoftemp_range_check.py [--build] [--unfixed]
[--mpi N] [--case NAME] [--keep]. Exit 0 pass, 1 fail, 2 missing binary.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exf_heat_check as H  # noqa: E402
from refusal_check import CELLS, ROOT, VERIF, read_logs  # noqa: E402
from applied_field_check import set_namelist  # noqa: E402
from tendency_term_check import (build_if_stale, report_build,  # noqa: E402
                                 write_mods_code, exf_options)

EXPERIMENT = "lab_sea"
PREFIX = "input.rnfrange_"
UNFIXED_BUILD = "build_esx_roft_unfixed"
UNFIXED_CODE = "code_rnfterm_roft_unfixed"
CHECK_FILE = os.path.join("MITgcm", "pkg", "exf", "exf_check_range.F")
STOP = "ABNORMAL END: S/R EXF_CHECK_RANGE"
TEMP_MSG = "EXF WARNING: runoftemp out of range"
VOL_MSG = "EXF WARNING: runoff out of range"
#: Dry surface cell of lab_sea (bathy.labsea1979 is 0 there; flat index).
DRY_CELL = 0
#: Dense volume flux [m/s] everywhere, inside the exf bound of 1e-6.
BASE_FLUX = 4.0e-7
BASE_TEMP = 10.0

#: (name, path, temperature, flux at the test cell or None, expectation)
#: expectation: "temp" refused with TEMP_MSG; "vol" refused with VOL_MSG
#: only; "ok" ends normally.
CASES = [
    ("dense_36.5", "dense", 36.5, None, "temp"),
    ("dense_100", "dense", 100.0, None, "temp"),
    ("dense_m3", "dense", -3.0, None, "temp"),
    ("dense_36", "dense", 36.0, None, "ok"),
    ("dense_m2", "dense", -2.0, None, "ok"),
    ("dense_dry_100", "dense", 100.0, "dry", "ok"),
    ("dense_flux_40", "dense", BASE_TEMP, 40.0, "vol"),
    ("sparse_36.5", "sparse", 36.5, None, "temp"),
    ("sparse_100", "sparse", 100.0, None, "temp"),
    ("sparse_m3", "sparse", -3.0, None, "temp"),
    ("sparse_35.9", "sparse", 35.9, None, "ok"),
    ("sparse_m2", "sparse", -2.0, None, "ok"),
]
#: Cases that must fail on the unfixed build: the temperature above 36
#: that was not caught, the volume flux that was misreported, and the
#: temperature below -2, which was refused but with the runoff value
#: printed (measured: 4.0e-07 dense, 6.4e-07 sparse, not -3).
UNFIXED_FAILS = {"dense_36.5", "dense_100", "sparse_36.5", "sparse_100",
                 "dense_flux_40", "dense_m3", "sparse_m3"}


def fixed_text():
    with open(os.path.join(ROOT, CHECK_FILE)) as fh:
        return fh.read()


def unfixed_text():
    """Return exf_check_range.F with the RUNOFF-037 fix reversed.

    Each substitution must match exactly once, so a change to the routine
    stops the check instead of building something else.
    """
    text = fixed_text()
    for new, old in (
            ("runoftemp(i,j,bi,bj) .GT. 36 )", "runoff(i,j,bi,bj) .GT. 36 )"),
            ("bi, bj, i, j, myIter, runoftemp(i,j,bi,bj)",
             "bi, bj, i, j, myIter, runoff(i,j,bi,bj)")):
        if text.count(new) != 1:
            raise ValueError(f"{CHECK_FILE}: {text.count(new)} matches of "
                             f"{new!r}, expected 1")
        text = text.replace(new, old)
    return text


def write_unfixed_code():
    return write_mods_code(UNFIXED_CODE, {
        "EXF_OPTIONS.h": exf_options(True),
        "exf_check_range.F": unfixed_text()})


def build_for(args):
    base = H.BUILD
    if args.unfixed:
        return UNFIXED_BUILD + (f"_mpi{args.mpi}" if args.mpi else "")
    return base + (f"_mpi{args.mpi}" if args.mpi else "")


def code_writer(args):
    return write_unfixed_code if args.unfixed else H.write_code


def wet_cell():
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(CELLS) as src:
        return int(np.asarray(src["target_cell"][:])[0])


def write_dense(input_dir, temp, flux, cell):
    import numpy as np
    runoff = np.full(H.NX*H.NY, BASE_FLUX)
    roft = np.full(H.NX*H.NY, BASE_TEMP)
    roft[cell] = temp
    if flux is not None:
        runoff[cell] = flux
    runoff.astype(">f4").tofile(os.path.join(input_dir, H.DENSE_RUNOFF))
    roft.astype(">f4").tofile(os.path.join(input_dir, H.DENSE_TEMP))


def fmt_d(value):
    """Return ``value`` as Fortran ``D22.15`` prints it, without padding."""
    mant, exp = ("%.15E" % value).split("E")
    return mant, int(exp)


def message_value(text):
    """Return the number printed by the runoftemp warning, or None."""
    m = re.search(re.escape(TEMP_MSG) + r"[^\n]*?\s(-?\d\.\d+D[+-]\d+)\s*$",
                  text, re.M)
    return float(m.group(1).replace("D", "E")) if m else None


def run_case(case, args):
    name, path, temp, flux, want = case
    input_name = PREFIX + name
    input_dir = os.path.join(VERIF, EXPERIMENT, input_name)
    suffix = (f"_mpi{args.mpi}" if args.mpi else "") + (
        "_unfixed" if args.unfixed else "")
    output_name = "output_esx_" + input_name + suffix
    run_dir = os.path.join(VERIF, EXPERIMENT, output_name)
    for p in (input_dir, run_dir):
        shutil.rmtree(p, ignore_errors=True)
    os.makedirs(input_dir)
    problems = []
    try:
        if path == "dense":
            H.write_input(input_dir, False)
            cell = DRY_CELL if flux == "dry" else wet_cell()
            write_dense(input_dir, temp, None if flux == "dry" else flux, cell)
        else:
            old = H.TEMPERATURES
            H.TEMPERATURES = (temp,)
            try:
                H.write_files(input_dir)
            finally:
                H.TEMPERATURES = old
            H.write_input(input_dir, True)
        cmd = ["./experiment_run_no_compile.sh", EXPERIMENT, input_name]
        if args.mpi:
            cmd += ["-mpi", str(args.mpi)]
        cmd += ["-build", build_for(args), "-output", output_name]
        try:
            proc = subprocess.run(cmd, cwd=VERIF, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True,
                                  timeout=args.timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = None
            problems.append("timed out")
        logs = read_logs(run_dir)
        normal = "Execution ended Normally" in logs
        has_temp = TEMP_MSG in logs
        has_vol = VOL_MSG in logs
        has_stop = STOP in logs
        if not logs:
            problems.append("no logs")
        if want == "ok":
            if not normal or code != 0:
                problems.append("did not end normally")
            if has_temp or has_vol or has_stop:
                problems.append("refused by EXF_CHECK_RANGE")
        else:
            if normal or code == 0:
                problems.append("run was not refused")
            if not has_stop:
                problems.append(f"no '{STOP}'")
            if want == "temp":
                if not has_temp:
                    problems.append(f"no '{TEMP_MSG}'")
                else:
                    got = message_value(logs)
                    if got is None or abs(got - temp) > 1e-9*abs(temp):
                        problems.append(f"message prints {got}, not {temp}")
            else:
                if not has_vol:
                    problems.append(f"no '{VOL_MSG}'")
                if has_temp:
                    problems.append("reported as a temperature error")
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)
        if not args.keep:
            shutil.rmtree(run_dir, ignore_errors=True)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--unfixed", action="store_true")
    parser.add_argument("--mpi", type=int, default=0)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)
    build = build_for(args)
    if args.build and not report_build(build_if_stale(
            build, code_writer(args), jobs=4, timeout=3600, mpi=bool(args.mpi))):
        return 2
    if not os.path.isfile(os.path.join(VERIF, EXPERIMENT, build, "mitgcmuv")):
        print(f"MISSING: {build}; rerun with --build")
        return 2
    selected = [c for c in CASES if not args.case or c[0] in args.case]
    failed = set()
    for case in selected:
        problems = run_case(case, args)
        print(f"{'FAIL' if problems else 'PASS'} {case[0]} ({build})")
        for p in problems:
            print(f"     {p}")
        if problems:
            failed.add(case[0])
    if args.unfixed:
        want = UNFIXED_FAILS & {c[0] for c in selected}
        ok = failed == want
        print(f"{'PASS' if ok else 'FAIL'} unfixed build fails exactly "
              f"{sorted(want)}; failed {sorted(failed)}")
        return 0 if ok else 1
    print(f"{len(selected) - len(failed)} of {len(selected)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
