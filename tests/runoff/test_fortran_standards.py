"""Static lint of the new Fortran against the MITgcm coding standards (RUNOFF-027).

The lint reads source text only: it runs no model and needs no compiler. It
covers two kinds of text:

* **every file of ``MITgcm/pkg/rnf``** (``*.F``, ``*.h``, ``README.md``), and
* **the lines that the branch ADDS to existing MITgcm files** (the hooks in
  ``model/src``, ``pkg/exf``, ``pkg/longstep`` and ``pkg/ptracers``, plus
  ``model/inc/PARAMS.h``). The added lines come from
  ``git -C MITgcm diff <merge-base of upstream/master and HEAD> -U0`` (the
  same set as ``upstream/master...HEAD`` once the work is committed) and the
  file text from the working tree. A line that upstream wrote is never reported. If
  ``upstream/master`` cannot be reached, the hook test SKIPS with a message
  that says so: a skip is not a pass.

Rules (the letter is part of every finding):

====  =====================================================================
a     No tab character (all files).
b     No line longer than 72 columns in ``*.F`` and ``*.h``. Columns 73-80
      are ignored by the fixed-form compiler, so a statement line that is
      too long is truncated silently: that is a hard failure. A comment
      line or a ``#`` line over 72 columns is held to the MITgcm style.
      **That 72-column limit for comment and ``#`` lines is a house style:
      Fortran requires it only for code.**
c     Fixed-form layout. A comment line starts with an upper-case ``C`` in
      column 1 (no ``c``, ``*`` or ``!`` in column 1, no inline ``!``
      comment). Columns 1-5 of a code line are blank or a numeric label.
      A continuation mark in column 6 is ``&``.
d     (package only) Every SUBROUTINE has ``myThid`` as its last argument
      and a protex header: ``CBOP``, ``C !ROUTINE: NAME`` (the name of the
      routine), ``C !INTERFACE:``, and ``CEOP`` before the first statement
      after the declarations.
e     (package only) Include order, per routine. The rule is measured on
      ``pkg/exf`` and ``pkg/shelfice`` (see
      :func:`test_include_rule_holds_for_the_neighbour_packages`): the
      ``*_OPTIONS.h`` headers come first, in the file prelude; in a
      routine ``SIZE.h`` and ``EEPARAMS.h`` (either order; ``pkg/exf`` has
      ``EEPARAMS.h`` first, ``pkg/shelfice`` has ``SIZE.h`` first) come
      before ``PARAMS.h``, which comes before the other model headers
      (``GRID.h``, ``DYNVARS.h``, ``FFIELDS.h``); ``RNF_SIZE.h`` comes before
      ``RNF.h``, and both after those model headers. Headers of other
      packages (``EXF_*``, ``SHELFICE.h``, ``cal.h``, ...) come after
      ``SIZE.h`` and ``EEPARAMS.h``; their place among the package's own
      headers is free, as it is in ``pkg/exf``.
f     Real arithmetic is ``_RL`` / ``_RS`` and a constant is written
      ``1. _d 0``. A bare ``D`` or ``E`` exponent, a bare real literal
      (``0.5``) and a ``REAL`` / ``DOUBLE PRECISION`` declaration in code
      are flagged. Text in quotes, comments and ``FORMAT`` statements is
      not code.
g     A ``STOP`` has exactly one form: a ``CALL PRINT_ERROR`` earlier in
      the routine, then ``CALL ALL_PROC_DIE( 0 )`` as the statement just
      before, then ``STOP 'ABNORMAL END: S/R NAME'`` with NAME the routine
      (the pattern of ``rnf_check.F``). A ``STOP`` inside a logical IF
      (``IF ( ... ) STOP``) also counts as a ``STOP`` and fails the form.
      **This rule is stricter than upstream:** ``pkg/shelfice`` has a
      ``STOP`` without a ``PRINT_ERROR``.
h     CPP. Every ``#endif`` (and ``#else``, ``#elif``) carries a
      ``/* ... */`` comment that names a macro of its ``#if``. (package
      ``*.F`` only) the file starts with ``#include "RNF_OPTIONS.h"`` and
      every routine has an ``#ifdef ALLOW_RNF`` guard (or an ``#if`` that
      tests ``defined ALLOW_RNF``), as the other packages do. The 80-column
      MITgcm ruler line ``C---+----1----+...`` is exempt from rule b.
i     No tracker id (``runoff-22``, any case, blanks around the hyphen
      allowed) and no ``github.com/ifenty`` text (any case)
      anywhere in the lint scope: both mean nothing to an upstream reader.
====  =====================================================================

**Exceptions** are in :data:`EXCEPTIONS`, a table of ``(rule, file glob,
regular expression of the source line or None, reason)``. An exception that
no longer matches any finding fails the test, so the table cannot go stale.

**TAF is out of scope.** The TAF list files (``rnf_ad_diff.list``,
``rnf_ad.flow``) need a TAF build. Whether the routines are TAF compatible
(store directives, no hidden state) is NOT checked here; see
``docs/code_standards_checklist.md``.

The lint tests itself: :func:`test_each_rule_fails_on_a_mutant` makes a
mutant of a real source for every rule and demands that the rule, the file
and the line are named. This file lives in ``tests/runoff`` because the
configured suites run ``pytest -q`` there. It can also be run directly::

    python tests/runoff/test_fortran_standards.py    # one line per finding
"""

import collections
import fnmatch
import os
import re
import subprocess
import sys
import warnings

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
MITGCM = os.path.join(ROOT, "MITgcm")
PKG = os.path.join(MITGCM, "pkg", "rnf")
BASE_REF = "upstream/master"

#: Existing MITgcm files that the branch edits. Only the ADDED lines are
#: linted. A file of this list that the branch does not touch is an error.
HOOK_FILES = (
    "model/inc/PARAMS.h",
    "model/src/apply_forcing.F",
    "model/src/external_forcing.F",
    "model/src/external_forcing_surf.F",
    "model/src/load_fields_driver.F",
    "model/src/packages_boot.F",
    "model/src/packages_check.F",
    "model/src/packages_init_fixed.F",
    "model/src/packages_init_variables.F",
    "model/src/packages_readparms.F",
    "pkg/exf/exf_check_range.F",
    "pkg/exf/exf_getffields.F",
    "pkg/exf/exf_mapfields.F",
    "pkg/longstep/longstep_forcing_surf.F",
    "pkg/ptracers/ptracers_apply_forcing.F",
)

#: Named exceptions: (rule, file glob relative to MITgcm, regex of the
#: source line or None for any line, reason).
EXCEPTIONS = (
    ("g", "pkg/rnf/rnf_fields_load.F",
     r"STOP 'ABNORMAL END: S/R RNF_FIELDS_LOAD'",
     "RNF_FIELDS_BUILD, the routine of this STOP, is the internal part of "
     "RNF_FIELDS_LOAD: all its messages are prefixed RNF_FIELDS_LOAD, the "
     "S/R the user knows, and tests/rnf/restart_check.py (REFUSAL_STOP) "
     "reads this exact text"),
    ("f", "pkg/exf/exf_check_range.F", r"\.GT\. 1\.E-6",
     "upstream's own threshold, only re-indented by the hook that wraps it "
     "in a new IF: writing it as '1. _d -6' would change the single-"
     "precision value of the bound"),
    ("f", "pkg/rnf/rnf_nc_utils.F", r"^\s+Real\*8\s+tmpVal\(1\)",
     "NF_GET_VAR1_DOUBLE writes a REAL*8 argument whatever _RL is "
     "(a single-precision build has _RL = REAL*4), so the variable is "
     "declared REAL*8 on purpose"),
)

FINDING = collections.namedtuple("FINDING", "rule path line msg text")

_TRACKER = re.compile(r"(?i)runoff\s*-\s*[0-9]")
_REPO_URL = re.compile(r"(?i)github\.com/ifenty")
_ROUTINE = re.compile(
    r"^(?:(?:INTEGER|LOGICAL|CHARACTER(?:\*\(?[\w*]+\)?)?|_RL|_RS|REAL(?:\*\d)?"
    r"|DOUBLE\s+PRECISION)\s+)?(SUBROUTINE|FUNCTION)\s+(\w+)\s*"
    r"(?:\((.*)\))?\s*$", re.I)
_INCLUDE = re.compile(r'^#\s*include\s+"([^"]+)"')


# ---------------------------------------------------------------------------
# Line handling


def classify(line):
    """Return ``blank``, ``comment``, ``cpp`` or ``code`` for one line."""
    if not line.strip():
        return "blank"
    if line[0] == "C":
        return "comment"
    if line[0] == "#":
        return "cpp"
    if line[0] in "c*!":
        return "comment"          # reported by rule c, not treated as code
    return "code"


def cut_comment(body):
    """Return ``body`` without an inline ``!`` comment (quotes respected)."""
    quote = None
    for i, ch in enumerate(body):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "!":
            return body[:i]
    return body


def blank_strings(body):
    """Return ``body`` with the inside of every quoted string blanked."""
    out, quote = [], None
    for ch in body:
        if quote:
            if ch == quote:
                quote = None
                out.append(ch)
            else:
                out.append(" ")
        else:
            if ch in "'\"":
                quote = ch
            out.append(ch)
    return "".join(out)


def is_continuation(line):
    """True for a fixed-form continuation line (mark in column 6)."""
    return (classify(line) == "code" and len(line) > 5
            and line[5] not in (" ", "0") and not line[:5].strip())


def statements(lines):
    """Return ``[(first line, last line, text)]`` with continuations joined.

    ``text`` is the statement without inline comment, strings kept, one
    space between the pieces. Line numbers start at 1.
    """
    out = []
    for n, line in enumerate(lines, 1):
        if classify(line) != "code":
            continue
        body = cut_comment(line[6:]).rstrip() if len(line) > 6 else ""
        if is_continuation(line) and out:
            first, _, text = out[-1]
            out[-1] = (first, n, text + " " + body.strip())
        else:
            out.append((n, n, body.strip()))
    return out


def routines(lines):
    """Return ``[(name, kind, args, start line, end line)]`` of the source.

    ``end`` is the line of the matching ``END`` statement (or the last line
    when it is missing).
    """
    out, cur = [], None
    for first, last, text in statements(lines):
        m = _ROUTINE.match(text)
        if m and cur is None:
            args = [a.strip() for a in (m.group(3) or "").split(",")
                    if a.strip()]
            cur = [m.group(2).upper(), m.group(1).upper(), args, first]
        elif cur is not None and re.match(r"^END\s*$", text, re.I):
            out.append((cur[0], cur[1], cur[2], cur[3], last))
            cur = None
    if cur is not None:
        out.append((cur[0], cur[1], cur[2], cur[3], len(lines)))
    return out


# ---------------------------------------------------------------------------
# The rules. Each takes the lines and returns [(rule, line number, message)].


def rule_a(lines):
    """No tab character."""
    return [("a", n, "tab character at column {0}".format(line.index("\t") + 1))
            for n, line in enumerate(lines, 1) if "\t" in line]


#: The MITgcm separator line before each routine ("C---+----1----+----2..."),
#: 80 columns by MITgcm's own convention, is the one line exempt from rule b.
_RULER = re.compile(r"^C---\+----1----\+----2----\+----3----\+----4----\+"
                    r"----5----\+----6----\+----7-\|--\+----\|\s*$")


def rule_b(lines):
    """No line longer than 72 columns."""
    out = []
    for n, line in enumerate(lines, 1):
        width = len(line.rstrip())
        if width <= 72 or _RULER.match(line):
            continue
        if classify(line) == "code":
            out.append(("b", n, "statement line has {0} columns: columns "
                        "73-{0} are cut off by the compiler (silent "
                        "truncation)".format(width)))
        else:
            out.append(("b", n, "{0} line has {1} columns, the MITgcm style "
                        "is 72".format(classify(line), width)))
    return out


def rule_c(lines):
    """Fixed-form layout: comment marker, label field, continuation mark."""
    out = []
    # MITgcm marks the intent of an argument (I, O, U) in column 6 of the
    # continuation lines of a SUBROUTINE or CALL statement
    arglist = set()
    for first, last, text in statements(lines):
        if re.match(r"^(?:IF\s*\(.*\)\s*)?(?:SUBROUTINE|CALL)\b", text, re.I):
            arglist.update(range(first + 1, last + 1))
    for n, line in enumerate(lines, 1):
        kind = classify(line)
        if kind == "comment" and line[0] != "C":
            out.append(("c", n, "comment line starts with {0!r}, MITgcm "
                        "style is an upper-case C in column 1"
                        .format(line[0])))
        elif kind == "code":
            if line[:5].strip() and not line[:5].strip().isdigit():
                out.append(("c", n, "text {0!r} in columns 1-5 (only a "
                            "numeric label is allowed there)"
                            .format(line[:5].strip())))
            elif (is_continuation(line) and line[5] != "&"
                  and not (line[5] in "IOU" and n in arglist)):
                out.append(("c", n, "continuation mark is {0!r}, MITgcm "
                            "style is '&' (I, O, U only in the argument "
                            "list of a SUBROUTINE or CALL)"
                            .format(line[5])))
            if len(line) > 6 and cut_comment(line[6:]) != line[6:]:
                out.append(("c", n, "inline '!' comment (use a C comment "
                            "line)"))
    return out


def rule_d(lines):
    """Every SUBROUTINE ends its argument list with myThid, has a header."""
    out = []
    for name, kind, args, start, end in routines(lines):
        if kind != "SUBROUTINE":
            out.append(("d", start, "{0} {1} is not a SUBROUTINE (the "
                        "package has none)".format(kind, name)))
            continue
        if not args or args[-1] != "myThid":
            out.append(("d", start, "SUBROUTINE {0}: last argument is {1}, "
                        "not myThid".format(name, args[-1] if args
                                            else "(none)")))
        # the comment block just before the SUBROUTINE statement
        i = start - 2
        while i >= 0 and classify(lines[i]) != "code":
            i -= 1
        block = lines[i + 1:start - 1]
        names = [m.group(1).upper() for l in block
                 for m in [re.match(r"^C\s+!ROUTINE:\s+(\w+)\s*$", l)] if m]
        if not any(re.match(r"^CBOP\b", l) for l in block):
            out.append(("d", start, "SUBROUTINE {0}: no CBOP before it"
                        .format(name)))
        if names != [name]:
            out.append(("d", start, "SUBROUTINE {0}: header 'C !ROUTINE:' "
                        "names {1}".format(name, names or "nothing")))
        if not any(re.match(r"^C\s+!INTERFACE:", l) for l in block):
            out.append(("d", start, "SUBROUTINE {0}: no 'C !INTERFACE:' "
                        "line in the header".format(name)))
        if not any(l.strip() == "CEOP" for l in lines[start - 1:end]):
            out.append(("d", start, "SUBROUTINE {0}: no CEOP".format(name)))
    return out


#: The include order of rule e: lower rank first. A header that is in none
#: of the tables is the header of another package: free, but not before
#: SIZE.h / EEPARAMS.h.
_RANK = (
    (1, ("SIZE.h", "EEPARAMS.h")),
    (2, ("PARAMS.h",)),
    (3, ("GRID.h", "DYNVARS.h", "FFIELDS.h", "SURFACE.h")),
    (4, ("RNF_SIZE.h",)),
    (5, ("RNF.h",)),
)


def _rank(header):
    for rank, names in _RANK:
        if header in names:
            return rank
    return None


def include_order(lines, first, last):
    """Return ``[(line, message)]`` for the includes of lines first..last."""
    seq = [(n, _INCLUDE.match(lines[n - 1]).group(1))
           for n in range(first, last + 1)
           if _INCLUDE.match(lines[n - 1])]
    seq = [(n, h) for n, h in seq if not h.endswith("_OPTIONS.h")]
    out, top = [], 0
    for n, header in seq:
        rank = _rank(header)
        if rank is None:
            if top == 0:
                out.append((n, "{0} comes before SIZE.h / EEPARAMS.h"
                            .format(header)))
            continue
        if top == 0 and rank != 1:
            out.append((n, "{0} comes before SIZE.h / EEPARAMS.h"
                        .format(header)))
        if rank < top:
            out.append((n, "{0} comes after a header of a later group "
                        "(order: SIZE/EEPARAMS, PARAMS, GRID/DYNVARS/"
                        "FFIELDS, RNF_SIZE, RNF)".format(header)))
        top = max(top, rank)
    return out


def rule_e(lines):
    """Include order per routine; OPTIONS headers only in the prelude."""
    out = []
    rts = routines(lines)
    firsts = [r[3] for r in rts] or [len(lines) + 1]
    # the prelude: only *_OPTIONS.h may be included there
    for n in range(1, firsts[0]):
        m = _INCLUDE.match(lines[n - 1])
        if m and not m.group(1).endswith("_OPTIONS.h"):
            out.append(("e", n, "{0} is included before the first routine; "
                        "only *_OPTIONS.h belong there".format(m.group(1))))
    for name, _, _, start, end in rts:
        for n, msg in include_order(lines, start, end):
            out.append(("e", n, "{0}: {1}".format(name, msg)))
        for n in range(start, end + 1):
            m = _INCLUDE.match(lines[n - 1])
            if m and m.group(1).endswith("_OPTIONS.h"):
                out.append(("e", n, "{0} is included inside routine {1}"
                            .format(m.group(1), name)))
    return out


_PROPER = re.compile(r"(?:\d+\.\d*|\.\d+)\s*_[dD]\s*[+-]?\d+")
_EXPONENT = re.compile(r"(?<![A-Za-z_0-9.])(?:\d+\.?\d*|\.\d+)[EeDd][+-]?\d+"
                       r"(?![A-Za-z_0-9])")
_BARE_REAL = re.compile(r"(?<![A-Za-z_0-9.])(?:\d+\.\d*|\.\d+)"
                        r"(?![A-Za-z_0-9])")
_REAL_DECL = re.compile(r"^\s*(?:REAL|DOUBLE\s+PRECISION|COMPLEX)\b", re.I)


def rule_f(lines):
    """_RL/_RS arithmetic and ``_d`` constants; no bare real in code."""
    out = []
    for n, line in enumerate(lines, 1):
        if classify(line) != "code":
            continue
        body = blank_strings(cut_comment(line[6:])) if len(line) > 6 else ""
        if re.match(r"^\s*FORMAT\b", body, re.I) or (
                line[:5].strip().isdigit()
                and re.match(r"^\s*FORMAT\b", body, re.I)):
            continue
        if _REAL_DECL.match(body):
            out.append(("f", n, "REAL / DOUBLE PRECISION declaration "
                        "(use _RL or _RS)"))
        rest = _PROPER.sub(" ", body)
        for m in _EXPONENT.finditer(rest):
            out.append(("f", n, "bare exponent constant {0!r} (write "
                        "'1. _d 0' style)".format(m.group(0))))
        rest = _EXPONENT.sub(" ", rest)
        for m in _BARE_REAL.finditer(rest):
            out.append(("f", n, "bare real literal {0!r} (write "
                        "'0. _d 0' style)".format(m.group(0))))
    return out


def rule_g(lines):
    """STOP only in the PRINT_ERROR / ALL_PROC_DIE / STOP ABNORMAL pattern."""
    out = []
    rts = routines(lines)
    stmts = statements(lines)
    for k, (first, last, text) in enumerate(stmts):
        if not re.match(r"^(?:\d+\s+)?(?:IF\s*\(.*\)\s*)?STOP\b", text,
                        re.I):
            continue
        owner = [r for r in rts if r[3] <= first <= r[4]]
        name = owner[0][0] if owner else None
        m = re.match(r"^STOP\s+'ABNORMAL END: S/R (\w+)'\s*$", text)
        if not m:
            out.append(("g", first, "STOP is not of the form STOP "
                        "'ABNORMAL END: S/R NAME'"))
            continue
        if name and m.group(1).upper() != name:
            out.append(("g", first, "STOP names S/R {0} inside {1}"
                        .format(m.group(1), name)))
        if k == 0 or not re.match(
                r"^CALL\s+ALL_PROC_DIE\(\s*(0|myThid)\s*\)\s*$",
                stmts[k - 1][2], re.I):
            out.append(("g", first, "STOP is not directly after CALL "
                        "ALL_PROC_DIE( 0 ) (or ( myThid ))"))
        lo = owner[0][3] if owner else 1
        if not any(re.match(r"^CALL\s+PRINT_ERROR\b", s[2], re.I)
                   for s in stmts[:k] if s[0] >= lo):
            out.append(("g", first, "no CALL PRINT_ERROR before the STOP in "
                        "this routine"))
    return out


_COND = re.compile(r"^#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$")


def rule_h(lines, package=False):
    """CPP: commented #endif/#else; for a package file, options and guard."""
    out, stack = [], []
    for n, line in enumerate(lines, 1):
        m = _COND.match(line)
        if not m:
            continue
        word, rest = m.group(1), m.group(2)
        cond = re.sub(r"/\*.*?\*/", " ", rest)
        if word in ("if", "ifdef", "ifndef"):
            stack.append((n, set(re.findall(r"[A-Za-z_]\w*", cond))
                          - {"defined"}))
            continue
        if not stack:
            out.append(("h", n, "#{0} without a matching #if".format(word)))
            continue
        opened, names = stack[-1]
        if word == "endif":
            stack.pop()
        text = re.search(r"/\*(.*?)\*/", rest)
        if word == "elif":
            names = names | set(re.findall(r"[A-Za-z_]\w*", cond))
        if not text:
            out.append(("h", n, "#{0} has no /* ... */ comment (opened on "
                        "line {1})".format(word, opened)))
        elif not (set(re.findall(r"[A-Za-z_]\w*", text.group(1))) & names):
            out.append(("h", n, "#{0} comment {1!r} names none of {2} (line "
                        "{3})".format(word, text.group(1).strip(),
                                      sorted(names), opened)))
    for opened, names in stack:
        out.append(("h", opened, "#if without a matching #endif"))
    if package:
        if not lines or lines[0].strip() != '#include "RNF_OPTIONS.h"':
            out.append(("h", 1, 'the file does not start with #include '
                        '"RNF_OPTIONS.h"'))
        for name, _, _, start, end in routines(lines):
            if not any(re.match(r"^#\s*(?:ifdef\s+ALLOW_RNF\b|if\b.*"
                                r"\bdefined\s*\(?\s*ALLOW_RNF\b)", l)
                       for l in lines[start - 1:end]):
                out.append(("h", start, "routine {0} has no '#ifdef "
                            "ALLOW_RNF' guard".format(name)))
    return out


def rule_i(lines):
    """No tracker id and no development repository URL."""
    out = []
    for n, line in enumerate(lines, 1):
        for rx, what in ((_TRACKER, "tracker id"),
                         (_REPO_URL, "development repository URL")):
            m = rx.search(line)
            if m:
                out.append(("i", n, "{0} {1!r}".format(what, m.group(0))))
    return out


# ---------------------------------------------------------------------------
# Lint drivers


def lint_lines(label, lines, profile, added=None):
    """Return the findings of one file.

    ``profile`` is ``package`` (all rules), ``hook`` or ``header`` (rules
    a, b, c, f, g, h-CPP, i) or ``text`` (a and i). With ``added`` (a set of
    line numbers) only the findings on those lines are kept.
    """
    found = []
    if profile == "text":
        found += rule_a(lines) + rule_i(lines)
    else:
        found += (rule_a(lines) + rule_b(lines) + rule_c(lines)
                  + rule_f(lines) + rule_g(lines) + rule_i(lines)
                  + rule_h(lines, package=(profile == "package"
                                 and label.endswith(".F"))))
        if profile == "package" and label.endswith(".F"):
            found += rule_d(lines) + rule_e(lines)
    out = []
    for rule, n, msg in sorted(found, key=lambda f: (f[1], f[0])):
        if added is not None and n not in added:
            continue
        out.append(FINDING(rule, label, n, msg, lines[n - 1]
                           if 0 < n <= len(lines) else ""))
    return out


def split_lines(text):
    """Split ``text`` into lines without a final empty one."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def apply_exceptions(findings, exceptions=None):
    """Return ``(kept, used)``: findings without the excepted ones."""
    table = EXCEPTIONS if exceptions is None else exceptions
    kept, used = [], set()
    for f in findings:
        for k, (rule, glob, rx, _reason) in enumerate(table):
            if (f.rule == rule and fnmatch.fnmatch(f.path, glob)
                    and (rx is None or re.search(rx, f.text))):
                used.add(k)
                break
        else:
            kept.append(f)
    return kept, used


def package_files(pkg=PKG):
    """Return the sorted regular files of the package directory."""
    return sorted(n for n in os.listdir(pkg)
                  if os.path.isfile(os.path.join(pkg, n)))


def lint_package(pkg=PKG, label_root="pkg/rnf"):
    """Return all raw (before exceptions) findings of the package."""
    out = []
    for name in package_files(pkg):
        with open(os.path.join(pkg, name), encoding="utf-8") as fh:
            lines = split_lines(fh.read())
        profile = ("package" if name.endswith((".F", ".h")) else "text")
        out += lint_lines(label_root + "/" + name, lines, profile)
    return out


def base_reachable(base=BASE_REF):
    """True when the base reference of the branch diff exists."""
    r = subprocess.run(["git", "-C", MITGCM, "rev-parse", "--verify",
                        "--quiet", base + "^{commit}"],
                       capture_output=True, text=True)
    return r.returncode == 0


def parse_added(diff):
    """Return ``{path: set of added line numbers}`` of a ``-U0`` diff."""
    out, path = {}, None
    for line in diff.split("\n"):
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            if path is not None:
                out.setdefault(path, set())
        elif line.startswith("@@") and path is not None:
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            start, count = int(m.group(1)), int(m.group(2) or 1)
            out[path].update(range(start, start + count))
    return out


def merge_base(base=BASE_REF):
    """Return the common ancestor of ``base`` and HEAD."""
    r = subprocess.run(["git", "-C", MITGCM, "merge-base", base, "HEAD"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def added_lines(base=BASE_REF):
    """Return ``{hook file: added line numbers}`` from git.

    The diff is from the merge base of ``base`` and HEAD to the WORKING TREE
    (``git diff <merge-base>``), which equals ``base...HEAD`` once the work
    is committed and also sees an edit not yet committed.
    """
    r = subprocess.run(["git", "-C", MITGCM, "diff", merge_base(base),
                        "-U0", "--"] + list(HOOK_FILES),
                       capture_output=True, text=True, check=True)
    return parse_added(r.stdout)


def lint_hooks(base=BASE_REF):
    """Return the raw findings on the lines the branch adds to the hooks."""
    out, added = [], added_lines(base)
    for path in HOOK_FILES:
        lines_added = added.get(path)
        if not lines_added:
            raise AssertionError("hook file {0} has no added line against "
                                 "{1}".format(path, base))
        with open(os.path.join(MITGCM, path), encoding="latin-1") as fh:
            out += lint_lines(path, split_lines(fh.read()), "hook",
                              lines_added)
    return out


def format_findings(findings):
    """One ``path:line: [rule] message`` per finding, with the line text."""
    return "\n".join("{0}:{1}: [{2}] {3}\n        | {4}".format(
        f.path, f.line, f.rule, f.msg, f.text.rstrip()) for f in findings)


# ---------------------------------------------------------------------------
# Tests of the sources


def test_pkg_rnf_passes_the_standards_lint():
    """Every file of pkg/rnf passes rules a-i, except the named exceptions."""
    kept, _ = apply_exceptions(lint_package())
    assert not kept, "\n" + format_findings(kept)


def test_every_named_exception_still_matches_a_finding():
    """An exception that matches nothing is stale: remove it.

    Without the base reference only the exceptions for ``pkg/rnf`` can be
    judged, since the hook findings cannot be computed.
    """
    raw = lint_package()
    reachable = base_reachable()
    if reachable:
        raw += lint_hooks()
    _, used = apply_exceptions(raw)
    stale = [EXCEPTIONS[k] for k in range(len(EXCEPTIONS)) if k not in used
             and (reachable or EXCEPTIONS[k][1].startswith("pkg/rnf"))]
    assert not stale, "stale exception(s): {0}".format(stale)
    assert all(len(e) == 4 and e[3].strip() for e in EXCEPTIONS)


def hook_not_run_message(base=BASE_REF):
    """Return the text that says the hook part of the lint did not run."""
    return ("HOOK LINT NOT RUN: {0} is not reachable in MITgcm (clone "
            "without the 'upstream' remote). The lines added to existing "
            "MITgcm files were NOT checked. This is not a pass."
            .format(base))


def test_a_missing_base_gives_a_loud_warning_text():
    """The message names 'NOT RUN' and says it is not a pass."""
    text = hook_not_run_message("upstream/master")
    assert "NOT RUN" in text and "not a pass" in text


def test_lines_added_to_existing_mitgcm_files_pass_the_lint():
    """The hook edits pass the rules on their added lines only.

    Without ``upstream/master`` the test warns (shown in the warnings
    summary of ``pytest -q``) and skips: the hook part is "not run".
    """
    if not base_reachable():
        warnings.warn(hook_not_run_message(), UserWarning, stacklevel=1)
        pytest.skip(hook_not_run_message())
    kept, _ = apply_exceptions(lint_hooks())
    assert not kept, "\n" + format_findings(kept)


#: Other files the branch adds that go to the upstream pull request. They
#: are outside the lint scope of RUNOFF-027 (package files and hook lines),
#: but rule i applies to them in the same way.
OTHER_PR_TEXT = ("doc/phys_pkgs/rnf.rst",
                 "utils/python/MITgcmutils/MITgcmutils/runoff/*.py",
                 "utils/python/MITgcmutils/setup.py")


@pytest.mark.xfail(strict=True, reason=(
    "OPEN: doc/phys_pkgs/rnf.rst and the Python runoff utilities still hold "
    "tracker ids / the repository URL; they are outside the scope of "
    "RUNOFF-027. Sweep them, then remove this marker (strict: the test "
    "fails when they are clean)"))
def test_other_pull_request_text_holds_no_tracker_id_or_repository_url():
    """Rule i for the doc chapter and the Python utilities of the branch."""
    import glob
    found = []
    for pattern in OTHER_PR_TEXT:
        for path in sorted(glob.glob(os.path.join(MITGCM, pattern))):
            with open(path, encoding="utf-8") as fh:
                found += lint_lines(os.path.relpath(path, MITGCM),
                                    split_lines(fh.read()), "text")
    found = [f for f in found if f.rule == "i"]
    assert not found, "\n" + format_findings(found)


def test_the_package_directory_holds_only_known_file_kinds():
    """A new file kind must be given a profile on purpose."""
    odd = [n for n in package_files() if not n.endswith((".F", ".h", ".md"))]
    assert not odd, "no lint profile for: {0}".format(odd)
    assert len([n for n in package_files() if n.endswith(".F")]) >= 15


def test_include_rule_holds_for_the_neighbour_packages():
    """Rule e is measured on pkg/exf and pkg/shelfice, not invented.

    The ordering rule (SIZE/EEPARAMS before PARAMS before the model and
    package headers) must hold in every routine of both packages. If it
    does not, the rule is wrong and not the neighbours.
    """
    checked = 0
    for pkg in ("exf", "shelfice"):
        d = os.path.join(MITGCM, "pkg", pkg)
        for name in sorted(os.listdir(d)):
            if not name.endswith(".F"):
                continue
            with open(os.path.join(d, name), encoding="latin-1") as fh:
                lines = split_lines(fh.read())
            for rname, _, _, start, end in routines(lines):
                incs = [h for h in (
                    (_INCLUDE.match(lines[n - 1]) or [None, None])[1]
                    for n in range(start, end + 1)) if h
                    and not h.endswith("_OPTIONS.h")]
                ranks = [_rank(h) for h in incs if _rank(h) in (1, 2)]
                checked += 1
                assert ranks == sorted(ranks), (name, rname, incs)
                if incs and 2 in ranks:
                    assert ranks[0] == 1, (name, rname, incs)
    assert checked > 20


# ---------------------------------------------------------------------------
# Tests of the lint itself: one mutant per rule


def _real(name):
    with open(os.path.join(PKG, name), encoding="utf-8") as fh:
        return fh.read()


def _mutant(tmp_path, text, name="rnf_check.F"):
    """Write ``text`` as a package file in ``tmp_path``, lint it, return."""
    d = tmp_path / "pkg_rnf"
    d.mkdir(exist_ok=True)
    (d / name).write_text(text)
    for other in package_files():
        if other != name and not (d / other).exists():
            (d / other).write_text(_real(other))
    return [f for f in lint_package(str(d)) if f.path.endswith("/" + name)]


def _replace(text, old, new, count=1):
    assert old in text, old
    return text.replace(old, new, count)


def _expect(found, rule, text, fragment):
    """The rule must be reported on the line holding ``fragment``."""
    lines = text.split("\n")
    hits = [f for f in found if f.rule == rule]
    assert hits, "rule {0} did not fire; got {1}".format(rule, found)
    where = [f for f in hits if fragment in lines[f.line - 1]
             or fragment in f.msg]
    assert where, (rule, fragment, hits)
    assert where[0].path.endswith("rnf_check.F") and where[0].line > 0


def test_the_real_source_used_for_the_mutants_is_clean(tmp_path):
    """The base of every mutant passes, so a finding comes from the edit."""
    text = _real("rnf_check.F")
    kept, _ = apply_exceptions(_mutant(tmp_path, text))
    assert not kept, format_findings(kept)


def test_each_rule_fails_on_a_mutant(tmp_path):
    """For every rule, a mutant of rnf_check.F is reported with file:line."""
    base = _real("rnf_check.F")
    tail = "      errCount = errCount + 1"

    def run(text):
        return _mutant(tmp_path, text)

    # a: a tab
    t = _replace(base, "C--   pkg/exf has to", "C--\tpkg/exf has to")
    _expect(run(t), "a", t, "pkg/exf has to")
    # b: a statement line of 80 columns, and a comment of 80 columns
    t = _replace(base, tail, tail + " " * 48 + "+ 0")
    f = run(t)
    _expect(f, "b", t, "errCount = errCount + 1")
    assert any("silent truncation" in x.msg for x in f if x.rule == "b")
    t = _replace(base, "C--   pkg/exf has to", "C--   pkg/exf has to" + "x" * 60)
    _expect(run(t), "b", t, "pkg/exf has to")
    # c: lower-case c, bang in column 1, label text, continuation mark
    t = _replace(base, "C--   pkg/exf has to", "c--   pkg/exf has to")
    _expect(run(t), "c", t, "pkg/exf has to")
    t = _replace(base, "C--   pkg/exf has to", "!--   pkg/exf has to")
    _expect(run(t), "c", t, "pkg/exf has to")
    t = _replace(base, "     &                    SQUEEZE_RIGHT, myThid )",
                 "     $                    SQUEEZE_RIGHT, myThid )")
    _expect(run(t), "c", t, "SQUEEZE_RIGHT")
    t = _replace(base, tail, tail + " ! counted")
    _expect(run(t), "c", t, "errCount")
    # d: myThid not last; header name wrong; header missing
    t = _replace(base, "SUBROUTINE RNF_CHECK( myThid )",
                 "SUBROUTINE RNF_CHECK( myThid, k )")
    _expect(run(t), "d", t, "not myThid")
    t = _replace(base, "C !ROUTINE: RNF_CHECK", "C !ROUTINE: RNF_CHEK")
    _expect(run(t), "d", t, "RNF_CHEK")
    t = _replace(base, "CEOP\n", "C EOP\n")
    _expect(run(t), "d", t, "CEOP")
    # e: PARAMS.h before SIZE.h; RNF.h before RNF_SIZE.h
    t = _replace(base, '#include "SIZE.h"\n#include "EEPARAMS.h"\n'
                 '#include "PARAMS.h"\n',
                 '#include "PARAMS.h"\n#include "SIZE.h"\n'
                 '#include "EEPARAMS.h"\n')
    _expect(run(t), "e", t, "comes before SIZE.h")
    t = _replace(base, '#include "RNF_SIZE.h"\n#include "RNF.h"\n',
                 '#include "RNF.h"\n#include "RNF_SIZE.h"\n')
    _expect(run(t), "e", t, "RNF_SIZE.h")
    # f: bare D exponent, bare real, REAL declaration
    t = _replace(base, "runoffconst .NE. 0. _d 0", "runoffconst .NE. 0.0D0")
    _expect(run(t), "f", t, "runoffconst")
    t = _replace(base, "exf_outscal_sflux .NE. 1. _d 0",
                 "exf_outscal_sflux .NE. 1.5")
    _expect(run(t), "f", t, "exf_outscal_sflux")
    t = _replace(base, "      INTEGER errCount\n",
                 "      INTEGER errCount\n      REAL*8 tmpVal\n")
    _expect(run(t), "f", t, "tmpVal")
    # g: bare STOP; STOP with another routine name; no ALL_PROC_DIE
    t = _replace(base, "STOP 'ABNORMAL END: S/R RNF_CHECK'", "STOP")
    _expect(run(t), "g", t, "STOP")
    t = _replace(base, "S/R RNF_CHECK'", "S/R RNF_CHEK'")
    _expect(run(t), "g", t, "STOP")
    t = _replace(base, "        CALL ALL_PROC_DIE( 0 )\n", "")
    _expect(run(t), "g", t, "ALL_PROC_DIE")
    # h: an #endif without a comment; no RNF_OPTIONS.h first; no guard
    t = _replace(base, "#endif /* ALLOW_SHELFICE */", "#endif")
    _expect(run(t), "h", t, "#endif")
    t = _replace(base, '#include "RNF_OPTIONS.h"\n', "")
    _expect(run(t), "h", t, "RNF_OPTIONS.h")
    t = _replace(base, "#ifdef ALLOW_RNF\n", "#ifdef ALLOW_RNF_X\n")
    t = _replace(t, "#endif /* ALLOW_RNF */", "#endif /* ALLOW_RNF_X */")
    _expect(run(t), "h", t, "ALLOW_RNF")
    t = _replace(base, "#endif /* ALLOW_SHELFICE */",
                 "#endif /* ALLOW_EXF */")
    _expect(run(t), "h", t, "names none of")
    # i: a tracker id and the repository URL, in code, comment and README
    t = _replace(base, "C--   pkg/exf has to", "C--   (RUNOFF-123) pkg/exf has")
    _expect(run(t), "i", t, "RUNOFF-123")
    t = _replace(base, "C--   pkg/exf has to",
                 "C--   github.com/ifenty/x pkg/exf has")
    _expect(run(t), "i", t, "github.com/ifenty")
    t = _replace(base, "'RNF_CHECK: configuration checks passed'",
                 "'RNF_CHECK: see RUNOFF-9 for this'")
    _expect(run(t), "i", t, "RUNOFF-9")
    for bad in ("runoff-022", "RUNOFF - 22", "Runoff -3"):
        t = _replace(base, "C--   pkg/exf has to", "C--   (" + bad + ") pkg/exf")
        _expect(run(t), "i", t, bad)
    t = _replace(base, "C--   pkg/exf has to", "C--   GitHub.com/IFenty/x pkg/exf")
    _expect(run(t), "i", t, "GitHub.com/IFenty")
    # g: a STOP in a logical IF
    t = _replace(base, "        CALL ALL_PROC_DIE( 0 )\n        STOP 'ABNORMAL END: S/R RNF_CHECK'\n",
                 "        IF ( errCount .GT. 1 ) STOP 'ABNORMAL END: S/R RNF_CHECK'\n")
    f = run(t)
    _expect(f, "g", t, "IF ( errCount")
    t = _replace(base, "        CALL ALL_PROC_DIE( 0 )\n        STOP 'ABNORMAL END: S/R RNF_CHECK'\n",
                 "        CALL ALL_PROC_DIE( 0 )\n        IF ( errCount .GT. 1 ) STOP\n")
    _expect(run(t), "g", t, "IF ( errCount")
    readme = _real("README.md") + "\nSee RUNOFF-7.\n\tTabbed.\n"
    found = _mutant(tmp_path, readme, "README.md")
    assert {f.rule for f in found} == {"a", "i"}, found


def test_a_header_file_is_linted_too(tmp_path):
    """Rules a, b, f, h and i also apply to RNF.h."""
    base = _real("RNF.h")
    text = base + "      _RL junk\n      junk = 0.5\n#ifdef ALLOW_X\n"
    found = _mutant(tmp_path, text, "RNF.h")
    assert {"f", "h"} <= {f.rule for f in found}, found


def test_an_exception_hides_only_what_it_names():
    """The exception table matches rule, file and line text, nothing else."""
    f1 = FINDING("f", "pkg/rnf/x.F", 3, "m", "      Real*8 a")
    f2 = FINDING("f", "pkg/rnf/x.F", 4, "m", "      Real*8 b")
    f3 = FINDING("b", "pkg/rnf/x.F", 3, "m", "      Real*8 a")
    table = (("f", "pkg/rnf/x.F", r"Real\*8 a$", "because"),
             ("f", "pkg/rnf/y.F", None, "unused"))
    kept, used = apply_exceptions([f1, f2, f3], table)
    assert kept == [f2, f3] and used == {0}


def test_added_lines_are_parsed_from_a_diff_and_only_they_are_linted():
    """The hook path keeps findings on added lines and drops the others."""
    diff = ("diff --git a/model/src/x.F b/model/src/x.F\n"
            "--- a/model/src/x.F\n+++ b/model/src/x.F\n"
            "@@ -3,0 +4,2 @@\n+a\n+b\n@@ -9 +12 @@\n-c\n+d\n"
            "diff --git a/y.F b/y.F\n--- a/y.F\n+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n")
    assert parse_added(diff) == {"model/src/x.F": {4, 5, 12}}
    long_line = "      x = 1" + " " * 70 + "+ 2"
    lines = ["C ok", "      y = 1", long_line, "      z = 0.5",
             "      w = 2", "c bad", "      v = 3"]
    # only lines 4 and 6 are "added": the long line 3 is upstream's
    found = lint_lines("model/src/x.F", lines, "hook", {4, 6})
    assert sorted((f.line, f.rule) for f in found) == [(4, "f"), (6, "c")]
    # and a long added line is reported, with its file and line
    found = lint_lines("model/src/x.F", lines, "hook", {3})
    assert [(f.path, f.line, f.rule) for f in found] == [
        ("model/src/x.F", 3, "b")]
    assert "silent truncation" in found[0].msg


def test_the_hook_part_names_its_skip_when_the_base_is_missing():
    """With an unreachable base the check reports False, never a pass."""
    assert base_reachable("no-such-remote/no-such-branch") is False


def test_a_stale_hook_file_list_is_detected():
    """lint_hooks fails (does not pass) for a base that adds nothing."""
    if not base_reachable():
        pytest.skip("{0} is not reachable".format(BASE_REF))
    with pytest.raises(AssertionError, match="no added line"):
        lint_hooks("HEAD")


def main():
    """Print one line per finding of the package and the hooks."""
    raw = lint_package()
    if base_reachable():
        raw += lint_hooks()
    else:
        print("SKIP hooks: {0} not reachable".format(BASE_REF))
    kept, _ = apply_exceptions(raw)
    print(format_findings(kept))
    print("{0} finding(s), {1} excepted".format(len(kept),
                                                len(raw) - len(kept)))
    return 1 if kept else 0


if __name__ == "__main__":
    sys.exit(main())
