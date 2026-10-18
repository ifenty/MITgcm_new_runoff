"""verification.full must contain every command of verification.scientific_groups.

RUNOFF-052. ``esx/project_profile.md`` ("Two verification tiers") calls the
``full`` suite the wider tier and the ``standard`` group the one every
scientific change closes against.  A standard command that full does not run
makes a green full suite weaker than the standard one (RUNOFF-052 found
``runoftemp_range_check.py --build`` was in standard only).

What "contains" means
=====================

Matching is by exact argv list, ignoring order, EXCEPT for the commands in
``REDUCED`` below.  The standard group is built from deliberately reduced or
resource-tuned forms of commands that full carries in its plain form, so only
2 of the 12 standard commands are exact members (``applied_field_check.py
--case lab_sea_daily`` and ``runoftemp_range_check.py --build``, the latter
added by RUNOFF-052; before it, 1) and the other 10 are in ``REDUCED``
(``restart_check.py --case daily`` of RUNOFF-022 is the 10th).
Each exception names the full command(s), themselves required to be exact
members of full, that run everything the standard form runs, and says why.
A drop of the covering command is therefore still caught.

This is weaker than "same argv" and is stated rather than hidden: a covering
claim (for example that plain ``refusal_check.py`` runs the six named cases)
is a reading of the script's defaults, checked below only where cheap
(``test_reduced_entries_are_live``) -- not re-proved on every run.
"""

import json
import os
import copy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT = os.path.join(ROOT, "esx", "project.json")

PY = "{python}"
ORACLE = "tests/mitgcm_oracle.sh"

# standard argv (as a tuple) -> (covering full argv lists, reason)
REDUCED = {
    (PY, "-m", "pytest", "-q", "tests/runoff", "-k", "not test_scale_"): (
        [[PY, "-m", "pytest", "-q", "tests/runoff"]],
        "standard deselects the slow test_scale_ tests; full runs them all"),
    (ORACLE, "lab_sea", "input", "-j", "4"): (
        [[ORACLE, "lab_sea", "input"]],
        "-j 4 only sets the build parallelism"),
    (ORACLE, "lab_sea", "input.rnof_sp_const", "-j", "4"): (
        [[ORACLE, "lab_sea", "input.rnof_sp_const"]],
        "-j 4 only sets the build parallelism"),
    (ORACLE, "lab_sea", "input.rnof_sp_const", "-j", "4", "-mpi", "2"): (
        [[ORACLE, "lab_sea", "input.rnof_sp_const", "-mpi", "2"]],
        "-j 4 only sets the build parallelism"),
    (ORACLE, "global_ocean.cs32x15", "input.rnof_sp_icedyn", "-j", "4",
     "-mpi", "4"): (
        [[ORACLE, "global_ocean.cs32x15", "input.rnof_sp_icedyn", "-mpi", "4"]],
        "-j 4 only sets the build parallelism"),
    (PY, "tests/rnf/timing_field_check.py", "--case", "daily"): (
        [[PY, "tests/rnf/timing_field_check.py", "--case", "daily",
          "--case", "month", "--case", "month1"]],
        "full runs the daily case together with two more cases"),
    (PY, "tests/rnf/restart_check.py", "--case", "daily"): (
        [[PY, "tests/rnf/restart_check.py", "--build", "--control"]],
        "full runs every case (daily, month, yearly, sync...) with the "
        "wrong-pickup control; standard keeps the daily mid-record case "
        "(about 20 s)"),
    (PY, "tests/rnf/budget_check.py", "--build", "--case", "lab_sea",
     "--mpi", "0"): (
        [[PY, "tests/rnf/budget_check.py", "--build"]],
        "with no --case/--mpi budget_check runs every case on every process "
        "count it lists, including lab_sea on 0 processes"),
    (PY, "tests/rnf/exf_heat_check.py", "--build"): (
        [[PY, "tests/rnf/exf_heat_check.py", "--control", "--build"]],
        "--control runs the same comparison and then also the control"),
    (PY, "tests/rnf/refusal_check.py", "--case", "runofffile", "--case",
     "three_at_once", "--case", "positive_control", "--case",
     "cells_equal_dense", "--case", "two_sources_one_cell", "--case",
     "ptracer_match"): (
        [[PY, "tests/rnf/refusal_check.py"]],
        "plain refusal_check runs every case without needs_build, which "
        "includes these six"),
}


def load(path=PROJECT):
    with open(path) as fh:
        return json.load(fh)["verification"]


def standard_commands(ver):
    return [c for g in ver["scientific_groups"] for c in g["commands"]]


def missing(ver):
    """Standard commands that full does not contain, by the rule above."""
    full = ver["full"]
    out = []
    for cmd in standard_commands(ver):
        if cmd in full:
            continue
        covers = REDUCED.get(tuple(cmd))
        if covers and all(c in full for c in covers[0]):
            continue
        out.append(cmd)
    return out


def test_full_contains_every_standard_command():
    ver = load()
    assert missing(ver) == []


def test_reduced_entries_are_live():
    """No dead exception: each is a real standard command that full lacks
    verbatim, and each covering command is a member of full."""
    ver = load()
    std = [tuple(c) for c in standard_commands(ver)]
    for key, (covers, reason) in REDUCED.items():
        assert key in std, f"REDUCED entry not in standard: {key}"
        assert list(key) not in ver["full"], f"needless exception: {key}"
        assert reason
        for c in covers:
            assert c in ver["full"], f"cover absent from full: {c}"


def test_full_keeps_its_commands_after_the_addition():
    ver = load()
    assert len(ver["full"]) == 74
    assert len(standard_commands(ver)) == 12
    assert len(set(map(tuple, ver["full"]))) == 74


def test_detects_the_pre_fix_state():
    """The pre-fix config (no runoftemp_range_check in full) must fail."""
    ver = copy.deepcopy(load())
    gone = [PY, "tests/rnf/runoftemp_range_check.py", "--build"]
    ver["full"].remove(gone)
    assert missing(ver) == [gone]


def test_detects_a_dropped_cover():
    ver = copy.deepcopy(load())
    ver["full"].remove([PY, "tests/rnf/refusal_check.py"])
    assert [PY, "tests/rnf/refusal_check.py", "--case", "runofffile"] == \
        missing(ver)[0][:4]


def test_detects_a_new_standard_command():
    ver = copy.deepcopy(load())
    new = [PY, "tests/rnf/new_check.py"]
    ver["scientific_groups"][0]["commands"].append(new)
    assert missing(ver) == [new]
