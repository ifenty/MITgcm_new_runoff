"""Hold one instrument's prose to what its own code returns.

Why this file exists
====================

RUNOFF-042 made the footprint sweep read ``.py`` and it immediately returned a
real stale claim: ``tests/rnf/refusal_check.py``'s module docstring listed the
*tile-local* refusals -- the ones only the process owning the tile detects, so
that MPI correctness depends on every process still stopping -- and the list
had been missing RUNOFF-033's cell-centre check ever since that check was
added.

The correction was written as a *mechanical antecedent* so it could not rot
again: "those checks are exactly the ones behind the cases that carry a
``stderr_any`` message". It rotted in the same round. The round-0 figure was
derived by walking the module's AST for ``file_case(...)`` calls, and
``cell_above_vol_max`` is built as a **dict literal**
(``refusal_check.py:1304-1314``), so the method could not see it: the
correction said six cases over four checks where calling :func:`cases` returns
seven over five. Both reviewers found that independently, by two different
methods.

So the lesson of that round is not "count again more carefully". It is that a
prose mechanical antecedent rots exactly like the remembered list it replaced,
and that the only enumeration which cannot miss a case is the one the program
itself performs. This test performs it: it **calls** ``cases()`` with the real
lab_sea namelists and ``sparse_info()``, and holds the docstring paragraph to
the result. A third instance of the same defect fails the ``structural`` suite
instead of being parked behind a ``KEEP`` entry, which is where the second one
was found (``tests/footprint_claim_sweep.py``'s needle for that line makes
``kept()`` return a reason, so the sweep's own triage queue and its dead-needle
guard can never raise it again).

Scope, deliberately narrow: one assertion over one paragraph. It does not
re-check anything else in that docstring and it does not touch the sweep's
predicate.
"""

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RNF_TESTS = ROOT / "tests" / "rnf"

#: Which measured case drives which tile-local check. This is the *grouping*
#: the docstring's first parenthetical states in words, written as data so the
#: check count is derived from it rather than counted by hand. It is not an
#: independent oracle and is not trusted as one: the assertion below requires
#: it to cover the measured case set **exactly**, so a tile-local case added
#: later lands in ``cases_with_no_check_named`` and fails here until both this
#: mapping and the docstring are updated.
CHECK_CASES = {
    "land": {"target_on_land"},
    "cell area": {"cell_area"},
    "cell centre": {"target_coords", "target_coords_nan"},
    "array bound": {"too_many_sources", "too_many_targets"},
    "per-cell aggregate": {"cell_above_vol_max"},
}

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def load_refusal_check():
    """Import ``tests/rnf/refusal_check.py``, or skip with the reason.

    The module reads ``pkg/rnf`` headers and the committed sparse NetCDF file
    at import and in ``sparse_info()``, so it needs the ``MITgcm/`` clone. That
    clone is a host prerequisite of this project rather than a property of the
    code under test, so its absence skips; **anything else missing fails**,
    because a broken fixture that quietly skips is the inert-instrument failure
    this file exists to prevent (LL-012, LL-014).
    """
    if not (ROOT / "MITgcm" / ".git").exists():
        pytest.skip("MITgcm/ clone absent: see CLAUDE.md for the prerequisite")
    sys.path.insert(0, str(RNF_TESTS))
    import refusal_check
    return refusal_check


def measured(refusal_check):
    """The cases carrying a non-empty ``stderr_any``, by calling ``cases()``.

    Deliberately the real call with the real namelists, not an AST walk and not
    a re-implementation: ``cases()`` is what the instrument runs, and a case
    can be built by ``file_case()`` or as a bare dict, which is exactly how the
    round-0 enumeration lost one.
    """
    base = os.path.join(refusal_check.VERIF, refusal_check.EXPERIMENT, "input")
    with open(os.path.join(base, "data.pkg")) as fh:
        data_pkg = fh.read()
    with open(os.path.join(base, "data.exf")) as fh:
        data_exf = fh.read()
    built = refusal_check.cases(data_pkg, data_exf, refusal_check.sparse_info())
    assert built, "cases() returned nothing: the fixture is broken, not the claim"
    return {c["name"] for c in built if c.get("stderr_any")}


def documented(refusal_check):
    """What the module docstring's tile-local paragraph states.

    Parsed rather than eyeballed so the figures compared are the ones a reader
    of the docstring actually gets. Raises through ``AssertionError`` if the
    paragraph is no longer there in the shape this test reads, which is itself
    worth failing on: the claim would then be unwatched again.
    """
    doc = refusal_check.__doc__
    start = doc.find("A refusal that only one tile's check detects")
    assert start >= 0, ("the tile-local refusal paragraph is gone from "
                        "refusal_check.py's module docstring, so nothing "
                        "states which checks are tile-local")
    para = " ".join(doc[start:doc.find("\n\n", start)].split())

    checks = re.search(r"detects \(([^)]*)\)", para)
    counted = re.search(r"Those (\w+) checks", para)
    listed = re.search(r"-- (\w+) cases \(([^)]*)\)", para)
    assert checks and counted and listed, (
        "the tile-local paragraph no longer states its checks, its check "
        f"count and its case list in the documented shape: {para!r}")

    return {
        "cases": sorted(re.findall(r"``(\w+)``", listed.group(2))),
        "case_count": NUMBER_WORDS[listed.group(1).lower()],
        "checks": sorted(c.strip() for c in checks.group(1).split(",")),
        "check_count": NUMBER_WORDS[counted.group(1).lower()],
        "cases_with_no_check_named": [],
    }


def test_tile_local_refusal_paragraph_matches_cases():
    """refusal_check.py's tile-local list == the cases ``cases()`` returns.

    One assertion, over the whole claim at once so the failure shows every
    part that drifted: the seven case names, the case count, the five check
    names, the check count, and whether any measured case is covered by no
    named check.
    """
    refusal_check = load_refusal_check()
    names = measured(refusal_check)
    mapped = set().union(*CHECK_CASES.values())
    observed = {
        "cases": sorted(names),
        "case_count": len(names),
        "checks": sorted(name for name, group in CHECK_CASES.items()
                         if group & names),
        "check_count": len({name for name, group in CHECK_CASES.items()
                            if group & names}),
        "cases_with_no_check_named": sorted(names - mapped),
    }
    assert observed == documented(refusal_check), (
        "tests/rnf/refusal_check.py's tile-local refusal paragraph no longer "
        "matches what cases() returns. Derive the replacement by CALLING "
        "cases() (see this file's docstring: an AST walk over file_case() "
        "calls misses cell_above_vol_max, a dict literal), then update the "
        "paragraph, CHECK_CASES here, and the matching KEEP reason in "
        "tests/footprint_claim_sweep.py.")
