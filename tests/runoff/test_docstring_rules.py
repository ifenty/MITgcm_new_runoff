"""Docstrings of the checker name the rule ids they emit (RUNOFF-001).

Permanent form of the round-2 diagnosis reproducer
(``devel-loop/loop_state/diag_docstring_rules.py``). ``check.py`` is parsed
with :mod:`ast`; a rule id "emitted" by a function is a string literal of the
form ``[A-Z]\\d\\d`` anywhere in its body (``ctx.add("S07", ...)``, the
``(rule, mask, what)`` tuples of ``_stream_values``, ...). Every ``_check_*``
function, and every other top-level function that emits a rule id, must name
each id it emits in its docstring, directly (``S07``) or inside a range of one
letter (``S01-S07``). A docstring may also name rules it reaches through a
called helper (e.g. ``_check_time`` names M05, emitted by ``_check_sampling``).
"""

import ast
import re

import pytest

from conftest import ROOT
from MITgcmutils.runoff import schema

CHECK_PY = ROOT / "MITgcm" / "utils" / "python" / "MITgcmutils" / "MITgcmutils" / "runoff" / "check.py"
RULE_ID = re.compile(r"[A-Z]\d\d")
#: ``S07`` or a same-letter range ``S01-S07`` (the second letter may be omitted).
NAMED = re.compile(r"\b([A-Z])(\d\d)(?:-([A-Z])?(\d\d))?\b")


def named_rules(doc):
    """Rule ids a docstring names, with ranges expanded."""
    out = set()
    for letter, lo, letter2, hi in NAMED.findall(doc or ""):
        if hi and letter2 in ("", letter):
            out |= {"{0}{1:02d}".format(letter, i) for i in range(int(lo), int(hi) + 1)}
        else:
            out.add(letter + lo)
            if hi:                      # "S01-T03" names two ids, not a range
                out.add(letter2 + hi)
    return out


def emitted_rules(fn):
    """Rule-id string literals anywhere in the body of ``fn`` (nested code too)."""
    return {n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and RULE_ID.fullmatch(n.value)}


def _functions():
    tree = ast.parse(CHECK_PY.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


FUNCTIONS = _functions()
#: Every _check_* function, plus every other top-level function emitting a rule.
AUDITED = sorted(name for name, fn in FUNCTIONS.items()
                 if name.startswith("_check_") or emitted_rules(fn))


def test_named_rules_parser():
    assert named_rules("S01-S07, S09, P02 and G01.") == {
        "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S09", "P02", "G01"}
    assert named_rules("X01-X09") == {"X0{0}".format(i) for i in range(1, 10)}
    assert named_rules("D02-09 and M05") == {"D0{0}".format(i) for i in range(2, 10)} | {"M05"}
    assert named_rules("S01-T03") == {"S01", "T03"}      # no cross-letter ranges
    assert named_rules("no rules here, 2024-01-01") == set()


def test_audit_covers_every_rule_and_every_check_function():
    """The parse is not vacuous: every rule of ``schema.RULES`` (``len(schema.RULES)``
    of them) is emitted, and all _check_* are audited."""
    emitted = set().union(*(emitted_rules(FUNCTIONS[n]) for n in AUDITED))
    assert emitted == set(schema.RULES) and len(emitted) == len(schema.RULES)
    checks = {n for n in FUNCTIONS if n.startswith("_check_")}
    assert checks and checks <= set(AUDITED)


@pytest.mark.parametrize("name", AUDITED)
def test_docstring_names_every_emitted_rule(name):
    fn = FUNCTIONS[name]
    doc = ast.get_docstring(fn)
    emitted = emitted_rules(fn)
    if emitted:
        assert doc, "{0} emits {1} but has no docstring".format(name, sorted(emitted))
    missing = sorted(emitted - named_rules(doc))
    assert not missing, "{0} emits {1} but its docstring doesn't name {2}".format(
        name, sorted(emitted), missing)
