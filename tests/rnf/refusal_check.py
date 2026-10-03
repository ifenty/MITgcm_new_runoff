#!/usr/bin/env python
"""Check that pkg/rnf refuses invalid configurations with the expected message.

Each case builds a scratch input directory layered on ``lab_sea/input`` (as
``lab_sea/input.rnfchk_<case>``), with ``useRNF=.TRUE.`` in ``data.pkg``, a
``data.rnf`` and one deliberate violation. The case is run with the existing
lab_sea binary through ``experiment_run_no_compile.sh``, the run step that
``tests/mitgcm_oracle.sh`` uses, so nothing is compiled here. Build the binary
first with ``tests/mitgcm_oracle.sh lab_sea input``.

With ``--mpi N`` the cases run on N processes with the binary of
``tests/mitgcm_oracle.sh lab_sea input -mpi N`` (``build_esx_mpiN``).

Every process is judged on its own files. A single-process run writes its
standard output and its ``STOP`` line to ``output.txt`` and its error messages
to ``STDERR.0000``. In an MPI run, process ``n`` writes its standard output to
``STDOUT.000n`` and its error messages to ``STDERR.000n``, and the ``STOP``
lines of all processes go to ``mpirun.log``.

A case passes when all of these hold:

* the model did not end normally;
* every expected error message is in the error file of every process;
* every expected standard-output line is in the standard output of every
  process;
* there is exactly one ``STOP`` line of the expected routine per process;
* no forbidden message is in any log.

A refusal case forbids the lines that are printed only after the checks pass.
Without that, the test could not tell a refusal from the stop that every
``useRNF=.TRUE.`` run meets in the package skeleton, where the reader of
``RNF_file`` does not exist yet (RUNOFF-004). The positive control is the
reverse: a valid configuration must pass the checks, print the parameter
summary and stop at "reader not implemented", with no refusal message. Its
``RNF_file`` value is read from the summary's own value line. The echo of
``data.rnf`` contains the same name and value and is not accepted, because a
run that stops before the summary still prints the echo.

The scratch input and run directories are removed afterwards (``--keep``
leaves the run directories for inspection). Exit status: 0 if every case
passes, 1 if any fails or none ran, 2 if the lab_sea binary is missing or a
``--case`` name is unknown.

Usage::

    python tests/rnf/refusal_check.py [--mpi N] [--keep] [--json] [--case NAME ...]
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERIF = os.path.join(ROOT, "MITgcm", "verification")
EXPERIMENT = "lab_sea"
BUILD = "build_esx"
PREFIX = "input.rnfchk_"

# The process and thread label that MITgcm puts in front of its log lines.
PID_PREFIX = re.compile(r"^\(PID\.TID \d{4}\.\d{4}\)\s?")

DATA_RNF = """# Sparse runoff package parameters
 &RNF_PARM01
  RNF_file = 'runoff_sparse.nc',
 &
"""

DATA_RNF_BLANK = """# Sparse runoff package parameters
 &RNF_PARM01
 &
"""

# Lines printed only after every configuration check has passed.
PASSED = "RNF_CHECK: configuration checks passed"
NOT_IMPLEMENTED = "RNF: reader not implemented (RUNOFF-004)"

# The refusal messages, by the parameter each one names.
MESSAGES = {
    "runofffile": "RNF_CHECK: runofffile must be blank with useRNF=.TRUE.",
    "runoffconst": "RNF_CHECK: runoffconst must be 0 with useRNF=.TRUE.",
    "exf_outscal_sflux":
        "RNF_CHECK: exf_outscal_sflux must be 1 with useRNF=.TRUE.",
    "RNF_file": "RNF_READPARMS: RNF_file is blank",
    "useEXF": "RNF_CHECK: useRNF=.TRUE. needs useEXF=.TRUE.",
}


def set_package_flags(text, flags):
    """Return ``data.pkg`` text with the given ``name: value`` flags set.

    A flag already in the file is replaced; the others are added before the
    namelist terminator. Raises ``ValueError`` if the terminator is missing.
    """
    lines = text.splitlines()
    remaining = dict(flags)
    for i, line in enumerate(lines):
        name = line.split("=")[0].strip()
        if name in remaining:
            lines[i] = f"  {name} = {remaining.pop(name)},"
    for i, line in enumerate(lines):
        if line.strip() in ("&", "/"):
            for name, value in remaining.items():
                lines.insert(i, f"  {name} = {value},")
            break
    else:
        raise ValueError("no namelist terminator in data.pkg")
    return "\n".join(lines) + "\n"


def replace_line(text, name, new_line):
    """Replace the one line of ``text`` that sets namelist variable ``name``.

    The match ignores case and skips comment lines. Raises ``ValueError``
    unless exactly one line matches, so a case can never run unmodified.
    """
    lines = text.splitlines()
    hits = [i for i, line in enumerate(lines)
            if not line.lstrip().startswith("#")
            and line.split("=")[0].strip().lower() == name.lower()
            and "=" in line]
    if len(hits) != 1:
        raise ValueError(f"expected one line setting {name}, found {len(hits)}")
    lines[hits[0]] = new_line
    return "\n".join(lines) + "\n"


def add_to_namelist(text, namelist, new_line):
    """Insert ``new_line`` as the first entry of ``&namelist`` in ``text``.

    Raises ``ValueError`` unless the namelist header occurs exactly once.
    """
    lines = text.splitlines()
    hits = [i for i, line in enumerate(lines)
            if line.strip().lower() == "&" + namelist.lower()]
    if len(hits) != 1:
        raise ValueError(f"expected one &{namelist}, found {len(hits)}")
    lines.insert(hits[0] + 1, new_line)
    return "\n".join(lines) + "\n"


def cases(data_pkg, data_exf):
    """Return the test cases as a list of dictionaries.

    Each case has:

    * ``name``;
    * ``files``: file name to content, written into the scratch input
      directory;
    * ``stderr``: error messages that every process must print;
    * ``stdout``: lines that every process must print to its standard output;
    * ``stop``: the text of the ``STOP`` line, expected once per process;
    * ``forbid``: messages that must be in no log;
    * ``summary`` (positive control only): parameter name to the value that
      the parameter summary must report.
    """
    pkg_on = set_package_flags(data_pkg, {"useRNF": ".TRUE."})
    # Without exf the model must still reach PACKAGES_CHECK: sea ice needs
    # exf (SEAICE_CHECK stops first), and data.diagnostics lists exf and
    # sea-ice fields.
    pkg_no_exf = set_package_flags(data_pkg, {
        "useRNF": ".TRUE.", "useEXF": ".FALSE.", "useSEAICE": ".FALSE.",
        "useDiagnostics": ".FALSE."})
    # A dense file on the lab_sea grid that exists in lab_sea/input, so the
    # case does not depend on whether exf opens the file before the check.
    exf_file = replace_line(
        data_exf, "runoffFile", " runoffFile        = 'prate.labsea1979',")
    exf_const = add_to_namelist(data_exf, "EXF_NML_03", " runoffconst = 1.E-8,")
    exf_scale = add_to_namelist(
        data_exf, "EXF_NML_03", " exf_outscal_sflux = 2.0,")
    exf_three = add_to_namelist(
        add_to_namelist(exf_file, "EXF_NML_03", " runoffconst = 1.E-8,"),
        "EXF_NML_03", " exf_outscal_sflux = 2.0,")
    after_checks = [PASSED, NOT_IMPLEMENTED]
    stop_check = "ABNORMAL END: S/R RNF_CHECK"
    one_error = "RNF_CHECK: detected  1 fatal error(s)"
    return [
        {"name": "runofffile",
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF,
                   "data.exf": exf_file},
         "stderr": [MESSAGES["runofffile"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "runoffconst",
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF,
                   "data.exf": exf_const},
         "stderr": [MESSAGES["runoffconst"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "exf_outscal_sflux",
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF,
                   "data.exf": exf_scale},
         "stderr": [MESSAGES["exf_outscal_sflux"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "three_at_once",
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF,
                   "data.exf": exf_three},
         "stderr": [MESSAGES["runofffile"], MESSAGES["runoffconst"],
                    MESSAGES["exf_outscal_sflux"],
                    "RNF_CHECK: detected  3 fatal error(s)"],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "blank_RNF_file",
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF_BLANK},
         "stderr": [MESSAGES["RNF_file"],
                    "RNF_READPARMS: detected  1 fatal error(s)"],
         "stdout": [], "stop": "ABNORMAL END: S/R RNF_READPARMS",
         "forbid": after_checks + ["RNF_CHECK: #define ALLOW_RNF"]},
        {"name": "useEXF_false",
         "files": {"data.pkg": pkg_no_exf, "data.rnf": DATA_RNF},
         "stderr": [MESSAGES["useEXF"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "positive_control",
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF},
         "stderr": [NOT_IMPLEMENTED],
         "stdout": ["pkg/rnf", "Sparse runoff (RNF) configuration >>> START",
                    PASSED],
         "summary": {"RNF_file": "'runoff_sparse.nc'"},
         "stop": stop_check,
         "forbid": list(MESSAGES.values()) + ["fatal error(s)"]},
    ]


def summary_value(text, name):
    """Return the value that ``RNF_SUMMARY`` printed for parameter ``name``.

    The summary writes the name and its comment on one line
    (``RNF_file = /* ... */``) and the value alone on the next line. The echo
    of ``data.rnf`` has name and value on one line without the comment, so it
    does not match. Returns ``None`` if ``text`` has no such summary line.
    """
    lines = [PID_PREFIX.sub("", line).strip() for line in text.splitlines()]
    for i, line in enumerate(lines[:-1]):
        if line.startswith(f"{name} = /*"):
            return lines[i + 1]
    return None


def process_logs(nproc):
    """Return the log file names of a run on ``nproc`` processes, by role.

    The result has ``stdout`` and ``stderr``, each a list with one file name
    per process, and ``stop``, the file that receives the ``STOP`` lines.
    ``nproc`` 0 is a single-process run, whose standard output and ``STOP``
    line are in ``output.txt``.
    """
    stderr = [f"STDERR.{n:04d}" for n in range(max(nproc, 1))]
    if nproc:
        return {"stdout": [f"STDOUT.{n:04d}" for n in range(nproc)],
                "stderr": stderr, "stop": "mpirun.log"}
    return {"stdout": ["output.txt"], "stderr": stderr, "stop": "output.txt"}


def read_file(run_dir, name):
    """Return the text of log file ``name``, or ``None`` if it is missing."""
    path = os.path.join(run_dir, name)
    if not os.path.isfile(path):
        return None
    with open(path, errors="replace") as fh:
        return fh.read()


def read_logs(run_dir):
    """Return the text of all the run's logs, joined.

    The logs are ``output.txt``, ``mpirun.log``, ``STDOUT.*`` and
    ``STDERR.*``. The joined text serves the checks that concern the run as a
    whole: a forbidden message anywhere, and a normal end. What each process
    must print is checked file by file in ``judge``.
    """
    parts = []
    names = ["output.txt", "mpirun.log"] + sorted(
        os.path.basename(p) for pattern in ("STDOUT.*", "STDERR.*")
        for p in glob.glob(os.path.join(run_dir, pattern)))
    for name in names:
        path = os.path.join(run_dir, name)
        if os.path.isfile(path):
            with open(path, errors="replace") as fh:
                parts.append(fh.read())
    return "\n".join(parts)


def build_name(nproc):
    """Return the lab_sea build directory for ``nproc`` processes (0: serial)."""
    return f"{BUILD}_mpi{nproc}" if nproc else BUILD


def judge(case, run_dir, nproc, run_exit):
    """Judge the logs in ``run_dir`` against ``case``; return the result.

    Each process is judged on its own files, named by ``process_logs``: its
    error file must hold every ``stderr`` message, its standard output every
    ``stdout`` line and every ``summary`` value, and the ``STOP`` file must
    hold exactly one ``stop`` line per process. A ``forbid`` message in any
    log, a normal end, a zero ``run_exit`` or an empty log fails the case.
    ``missing`` in the result names the file of each unmet expectation.
    """
    names = process_logs(nproc)
    missing = []
    for kind in ("stderr", "stdout"):
        for name in names[kind]:
            text = read_file(run_dir, name)
            if text is None:
                missing.append(f"{name}: no such file")
                continue
            missing += [f"{name}: {msg}" for msg in case[kind]
                        if msg not in text]
            if kind == "stdout":
                for param, value in case.get("summary", {}).items():
                    found = summary_value(text, param)
                    if found != value:
                        missing.append(f"{name}: summary reports {param} = "
                                       f"{value} (found {found})")
    processes = len(names["stderr"])
    stop_lines = (read_file(run_dir, names["stop"]) or "").count(case["stop"])
    if stop_lines != processes:
        missing.append(f"{names['stop']}: {processes} line(s) with "
                       f"'{case['stop']}' (found {stop_lines})")
    logs = read_logs(run_dir)
    ended_normally = "Execution ended Normally" in logs
    present = [m for m in case["forbid"] if m in logs]
    observed = [line.strip() for line in logs.splitlines()
                if "RNF_" in line and ("*** ERROR ***" in line
                                       or "ABNORMAL END" in line)]
    passed = (bool(logs) and not ended_normally and run_exit != 0
              and not missing and not present)
    return {
        "case": case["name"], "passed": passed, "processes": processes,
        "run_exit": run_exit, "ended_normally": ended_normally,
        "log_bytes": len(logs), "stop_lines": stop_lines,
        "expected": {key: case[key] for key in
                     ("stderr", "stdout", "stop", "summary") if key in case},
        "missing": missing, "forbidden_present": present,
        "observed": observed,
    }


def run_case(case, keep, nproc=0):
    """Run one case and return the result dictionary of ``judge``.

    ``nproc`` is the number of MPI processes; 0 runs the single-process
    binary. The scratch input directory is always removed, and the run
    directory too unless ``keep`` is true.
    """
    input_name = PREFIX + case["name"]
    output_name = "output_esx_" + input_name
    mpi_args = []
    if nproc:
        output_name += f"_mpi{nproc}"
        mpi_args = ["-mpi", str(nproc)]
    input_dir = os.path.join(VERIF, EXPERIMENT, input_name)
    run_dir = os.path.join(VERIF, EXPERIMENT, output_name)
    for path in (input_dir, run_dir):
        shutil.rmtree(path, ignore_errors=True)
    os.makedirs(input_dir)
    try:
        for name, content in case["files"].items():
            with open(os.path.join(input_dir, name), "w") as fh:
                fh.write(content)
        proc = subprocess.run(
            ["./experiment_run_no_compile.sh", EXPERIMENT, input_name]
            + mpi_args
            + ["-build", build_name(nproc), "-output", output_name],
            cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)
        result = judge(case, run_dir, nproc, proc.returncode)
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)
        if not keep:
            shutil.rmtree(run_dir, ignore_errors=True)
    return result


def main(argv=None):
    """Run the selected cases, print one line per case, return the status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mpi", type=int, default=0, metavar="N",
                        help="run on N MPI processes with build_esx_mpiN")
    parser.add_argument("--keep", action="store_true",
                        help="keep the run directories")
    parser.add_argument("--json", action="store_true",
                        help="print the full results as JSON")
    parser.add_argument("--case", action="append", default=[],
                        help="run only this case (repeatable)")
    args = parser.parse_args(argv)

    if args.mpi < 0:
        parser.error("--mpi needs a positive process count")
    binary = os.path.join(VERIF, EXPERIMENT, build_name(args.mpi), "mitgcmuv")
    if not os.path.isfile(binary):
        mpi = f" -mpi {args.mpi}" if args.mpi else ""
        print(f"missing {binary}: run tests/mitgcm_oracle.sh lab_sea input{mpi}",
              file=sys.stderr)
        return 2
    base = os.path.join(VERIF, EXPERIMENT, "input")
    with open(os.path.join(base, "data.pkg")) as fh:
        data_pkg = fh.read()
    with open(os.path.join(base, "data.exf")) as fh:
        data_exf = fh.read()

    selected = cases(data_pkg, data_exf)
    if args.case:
        unknown = set(args.case) - {c["name"] for c in selected}
        if unknown:
            print(f"unknown case(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        selected = [c for c in selected if c["name"] in args.case]

    results = [run_case(case, args.keep, args.mpi) for case in selected]
    for res in results:
        print(f"{'PASS' if res['passed'] else 'FAIL'} {res['case']}")
        for line in res["observed"]:
            print(f"     {line}")
        for msg in res["missing"]:
            print(f"     missing: {msg}")
        for msg in res["forbidden_present"]:
            print(f"     must not appear: {msg}")
        if res["ended_normally"]:
            print("     the model ended normally")
    if args.json:
        print(json.dumps(results, indent=1))
    failed = [r["case"] for r in results if not r["passed"]]
    print(f"{len(results) - len(failed)} of {len(results)} cases passed")
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
