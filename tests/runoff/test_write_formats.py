"""Check every ``WRITE(msgBuf,'(...)')`` of ``pkg/rnf`` against its item types.

A Fortran format mismatch is a runtime error, not a compile error: the
compiler never sees which items go with which edit descriptors, so a message
that mixes them up dies with ``Fortran runtime error: Expected INTEGER for
item ...`` the first time it is printed. In ``pkg/rnf`` almost every
``WRITE(msgBuf,...)`` sits on a refusal path, which only a deliberately
invalid input reaches, so such a bug survives every ordinary run. Two of them
did reach the tree during RUNOFF-004 (``RNF_NC_TGT_ERROR`` wrote six
character items against five ``A`` descriptors, and the second message of
``RNF_NC_ATT_REAL`` used a repeat group that put a string where an integer was
written); ``tests/rnf/refusal_check.py`` found them only because it runs those
paths. This module is the static guard, so the next one does not need a run to
be found.

It classifies **three** kinds, not two: ``A`` takes a character item, ``I`` an
integer one, and ``E``/``F``/``G``/``D`` a real one. An ``I`` descriptor with a
``_RL`` item is as fatal as an ``A`` with an integer and is just as invisible
to the compiler, so collapsing the numeric kinds would miss it.

How the item type is found: the declarations of the routine the statement is
in, then those of the package headers ``RNF.h`` and ``RNF_SIZE.h``, then the
model headers a message actually takes items from (``MODEL_HEADERS``: the grid
and the run-time parameters, for the cell coordinates and the time step that
``RNF_EXF_RUNOFF`` prints when it refuses a cell, and -- since RUNOFF-041 --
for ``dTtracerLev`` and ``deltaTFreeSurf`` that ``RNF_SUMMARY`` prints when
they differ; and the pkg/longstep
parameters, for the ``LS_nIter`` of ``RNF_CHECK``), then literals and a small
table of intrinsics (``LEN``, ``ILNBLNK``, ``ABS`` and so on). Scoping is per routine, which matters: ``attVal`` is ``_RL`` in
``RNF_NC_ATT_REAL`` and ``CHARACTER*(*)`` in ``RNF_NC_ATT_TEXT``. An item the
module cannot classify fails
:func:`test_every_write_item_of_pkg_rnf_is_classified` rather than passing
quietly, so the coverage of the check stays visible.

This file lives under ``tests/runoff`` because that is the directory the
configured suites run with ``pytest -q`` (``esx/project.json``); it checks
Fortran source, not the Python runoff tools. It can also be run directly::

    python tests/runoff/test_write_formats.py        # prints one line per finding
"""

import os
import re
import sys

MITGCM = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "MITgcm")
PKG = os.path.join(MITGCM, "pkg", "rnf")

#: Model headers a ``pkg/rnf`` message may take an item from, read before the
#: package ones so that a package declaration shadows a model one. The list is
#: not every header the package includes: it is the ones that actually supply
#: items to a ``WRITE(msgBuf,...)``, which today means the grid
#: (``XC``, ``YC``, ``drF``) and the run-time parameters (``deltaTFreeSurf``)
#: that ``RNF_EXF_RUNOFF`` names when it refuses a cell, plus
#: (``dTtracerLev``, again ``deltaTFreeSurf``) that ``RNF_SUMMARY`` names
#: when they differ (RUNOFF-041). Adding a message that
#: prints a variable from an unlisted header does not pass quietly -- it fails
#: :func:`test_every_write_item_of_pkg_rnf_is_classified` with "has no known
#: type", which is how this list came to exist (RUNOFF-040). Extend it there
#: and then, rather than widening the classifier. ``LONGSTEP_PARAMS.h`` was
#: added by RUNOFF-031, for the ``LS_nIter`` that ``RNF_CHECK`` names when it
#: refuses a runoff tracer under pkg/longstep.
MODEL_HEADERS = (
    os.path.join(MITGCM, "eesupp", "inc", "EEPARAMS.h"),
    os.path.join(MITGCM, "model", "inc", "PARAMS.h"),
    os.path.join(MITGCM, "model", "inc", "GRID.h"),
    os.path.join(MITGCM, "pkg", "longstep", "LONGSTEP_PARAMS.h"),
)

#: Fortran type keywords and the item kind each one declares.
TYPES = (
    ("CHARACTER", "c"),
    ("INTEGER", "i"),
    ("LOGICAL", "l"),
    ("_RL", "r"),
    ("_RS", "r"),
    ("REAL*8", "r"),
    ("REAL*4", "r"),
    ("DOUBLE PRECISION", "r"),
)

#: Intrinsics and helper functions used inside message items.
FUNCS = {
    "LEN": "i", "ILNBLNK": "i", "IFNBLNK": "i", "INDEX": "i", "NINT": "i",
    "INT": "i", "MOD": "i", "IABS": "i",
    "FLOAT": "r", "DFLOAT": "r", "DBLE": "r", "REAL": "r", "SQRT": "r",
    "NF_STRERROR": "c", "CHAR": "c",
}
#: Functions whose kind is the kind of their arguments.
SAME_KIND = ("MAX", "MIN", "ABS")

_NAME = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*")


def split_items(text):
    """Split a Fortran argument or format list on top-level commas."""
    out, depth, cur, quote = [], 0, "", False
    for ch in text:
        if ch == "'":
            quote = not quote
        if not quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                out.append(cur.strip())
                cur = ""
                continue
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def descriptor_kinds(fmt):
    """Return the kinds a format writes, as a list of ``c``/``i``/``r``/``l``.

    Repeat counts and groups are expanded. Scale factors (``1P``), literal
    strings and position descriptors (``X``, ``T``) consume no item.
    """
    kinds = []
    for tok in split_items(fmt):
        tok = tok.strip()
        if tok.startswith("'"):
            continue
        m = re.match(r"^(\d*)\((.*)\)$", tok)
        if m:
            kinds += descriptor_kinds(m.group(2)) * int(m.group(1) or 1)
            continue
        # a scale factor comes first (1PE16.8), then any repeat count (4I6)
        m = re.match(r"^(\d+P)?(\d*)([A-Za-z]+)", tok)
        if not m or not m.group(3):
            continue
        count = int(m.group(2) or 1)
        letter = m.group(3).upper()
        if letter.startswith("ES") or letter.startswith("EN"):
            letter = "E"
        kind = {"A": "c", "I": "i", "L": "l",
                "E": "r", "F": "r", "G": "r", "D": "r"}.get(letter[0])
        if letter[0] in ("X", "T", "P", "S", "B", "H"):
            continue
        if kind is None:
            continue
        kinds += [kind] * count
    return kinds


def reverted_kinds(fmt, n_items):
    """Return ``n_items`` kinds, applying Fortran format reversion.

    When the format runs out of descriptors, control reverts to the last
    repeatable group at the top level, or to the whole format when there is
    none (Fortran 77 format reversion).
    """
    kinds = descriptor_kinds(fmt)
    if not kinds:
        return []
    groups = [t for t in split_items(fmt)
              if re.match(r"^\d*\(.*\)$", t.strip())]
    tail = descriptor_kinds(groups[-1]) if groups else kinds
    while len(kinds) < n_items and tail:
        kinds = kinds + tail
    # a format may hold more descriptors than there are items: output then
    # simply stops, which is not an error
    return kinds[:n_items] if len(kinds) >= n_items else kinds


def declarations(lines):
    """Return ``{name: kind}`` for the declaration lines given."""
    out = {}
    for line in lines:
        body = line[6:] if len(line) > 6 else ""
        upper = body.strip().upper()
        for key, kind in TYPES:
            if upper.startswith(key):
                rest = body.strip()[len(key):]
                # a length or kind suffix: CHARACTER*(MAX_LEN_MBUF), REAL*8
                if rest.startswith("*"):
                    rest = rest[1:].lstrip()
                    if rest.startswith("("):
                        depth = 0
                        for i, ch in enumerate(rest):
                            depth += (ch == "(") - (ch == ")")
                            if depth == 0:
                                rest = rest[i+1:]
                                break
                    else:
                        rest = re.sub(r"^\d+", "", rest)
                for item in split_items(rest):
                    name = _NAME.match(item.strip())
                    if name:
                        out[name.group(0).upper()] = kind
                break
    return out


def join_continuations(text):
    """Return the fixed-form lines of ``text`` with continuations joined."""
    out = []
    for line in text.split("\n"):
        if line.startswith(("C", "c", "*", "#", "!")):
            continue
        if len(line) > 5 and line[5] not in (" ", "", "0"):
            if out:
                out[-1] = out[-1] + " " + line[6:]
            continue
        out.append(line)
    return out


def symbols_of_headers():
    """Return the declarations of the headers in scope, by upper-case name.

    The model headers of :data:`MODEL_HEADERS` first, then the package
    headers, so a ``pkg/rnf`` declaration shadows a model one of the same
    name. Measured when this was added: the two sets declare no name in
    common, so the order is a rule for the future and not a live fix.
    """
    out = {}
    for path in MODEL_HEADERS:
        with open(path) as fh:
            out.update(declarations(join_continuations(fh.read())))
    for name in ("RNF_SIZE.h", "RNF.h"):
        with open(os.path.join(PKG, name)) as fh:
            out.update(declarations(join_continuations(fh.read())))
    return out


def _is_simple(item):
    """True when ``item`` is one name, optionally with one trailing (...)."""
    m = _NAME.match(item)
    if not m:
        return False
    rest = item[len(m.group(0)):].strip()
    if not rest:
        return True
    if not rest.startswith("("):
        return False
    depth = 0
    for i, ch in enumerate(rest):
        depth += (ch == "(") - (ch == ")")
        if depth == 0:
            return not rest[i+1:].strip()
    return False


def _split_operands(item):
    """Split an expression on its top-level + - * / operators."""
    out, depth, cur, quote = [], 0, "", False
    for ch in item:
        if ch == "'":
            quote = not quote
        if not quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch in "+-*/" and depth == 0:
                out.append(cur)
                cur = ""
                continue
        cur += ch
    out.append(cur)
    return [p.strip() for p in out if p.strip()]


def _expression_kind(item, symbols):
    """Return the kind of an expression: real wins over integer."""
    item = item.strip()
    while item.startswith("(") and item.endswith(")"):
        inner = item[1:-1]
        depth = 0
        for ch in inner:
            depth += (ch == "(") - (ch == ")")
            if depth < 0:
                return None
        item = inner.strip()
    parts = _split_operands(item)
    if len(parts) < 2 and (not parts or parts[0] == item):
        return None
    kinds = {item_kind(p, symbols) for p in parts}
    if None in kinds:
        return None
    if "r" in kinds:
        return "r"
    return "i" if kinds == {"i"} else None


def item_kind(item, symbols):
    """Return the kind of one output item, or ``None`` if it is not known."""
    item = item.strip()
    if not item:
        return None
    if item.startswith("'") or item.startswith('"'):
        return "c"
    if re.match(r"^[-+]?\d+$", item):
        return "i"
    if re.match(r"^[-+]?(\d+\.\d*|\.\d+|\d+)\s*(_d|_D|[eEdD])\s*[-+]?\d+$",
                item) or re.match(r"^[-+]?(\d+\.\d*|\.\d+)$", item):
        return "r"
    if item.upper() in (".TRUE.", ".FALSE."):
        return "l"
    m = _NAME.match(item)
    if not m or not _is_simple(item):
        return _expression_kind(item, symbols)
    if not m:
        return None
    name = m.group(0)
    rest = item[len(name):].lstrip()
    if rest.startswith("("):
        upper = name.upper()
        inner = rest[1:rest.rfind(")")]
        if upper in FUNCS:
            return FUNCS[upper]
        if upper in SAME_KIND:
            kinds = {item_kind(a, symbols) for a in split_items(inner)}
            if None in kinds:
                return None
            return "r" if "r" in kinds else ("i" if kinds == {"i"} else None)
        # an array element or a character substring of a declared name
        kind = symbols.get(upper)
        if kind == "c" and ":" in inner:
            return "c"
        return kind
    return symbols.get(name.upper())


def statements(path):
    """Yield ``(line number, format, items)`` of each WRITE(msgBuf,...)."""
    raw = open(path).read().split("\n")
    i = 0
    while i < len(raw):
        if "WRITE(msgBuf," in raw[i]:
            stmt, j = raw[i], i + 1
            while j < len(raw) and len(raw[j]) > 5 and raw[j][5] not in (
                    " ", ""):
                stmt += " " + raw[j][6:]
                j += 1
            m = re.search(r"WRITE\(msgBuf,'\((.*?)\)'\)(.*)", stmt)
            if m:
                yield i + 1, m.group(1), m.group(2)
            i = j
        else:
            i += 1


def scopes(path):
    """Return ``[(first line, last line, symbols)]`` per routine of ``path``."""
    raw = open(path).read().split("\n")
    starts = [i for i, line in enumerate(raw)
              if re.match(r"^      (SUBROUTINE|.*FUNCTION)\s", line)]
    starts = starts or [0]
    bounds = list(zip(starts, starts[1:] + [len(raw)]))
    out = []
    for lo, hi in bounds:
        out.append((lo + 1, hi,
                    declarations(join_continuations("\n".join(raw[lo:hi])))))
    return out


def check_file(path, headers):
    """Return a list of ``(line, message)`` findings for one source file."""
    found = []
    routines = scopes(path)
    for line, fmt, items in statements(path):
        symbols = dict(headers)
        for lo, hi, local in routines:
            if lo <= line <= hi:
                symbols.update(local)
        values = split_items(items)
        kinds = [item_kind(v, symbols) for v in values]
        # An internal write to the one character variable msgBuf has ONE
        # record, so a format with fewer descriptors than items would
        # revert to a second record and die with "End of file" (the
        # message of rnf_init_fixed.F:384, RUNOFF-017). reverted_kinds
        # models reversion within a record, which is right for a file or
        # a multi-record unit and is why this went unflagged before.
        if len(descriptor_kinds(fmt)) < len(values):
            found.append((line, "format ({0}) has {1} descriptor(s) for {2}"
                          " item(s): reversion starts a second record of the"
                          " one-record msgBuf (runtime End of file)"
                          .format(fmt, len(descriptor_kinds(fmt)),
                                  len(values))))
        want = reverted_kinds(fmt, len(values))
        if len(want) < len(values):
            found.append((line, "format ({0}) writes {1} item(s), {2} given"
                          .format(fmt, len(want), len(values))))
            continue
        for n, (value, kind) in enumerate(zip(values, kinds)):
            if kind is None:
                found.append((line, "item {0} ({1}) has no known type"
                              .format(n + 1, value)))
            elif kind != want[n]:
                found.append((line,
                              "item {0} ({1}) is {2} but descriptor {0} of"
                              " ({3}) writes {4}".format(
                                  n + 1, value, kind, fmt, want[n])))
    return found


def check_package():
    """Return the findings of every ``.F`` file of ``pkg/rnf``."""
    headers = symbols_of_headers()
    out = []
    for name in sorted(os.listdir(PKG)):
        if name.endswith(".F"):
            out += [(name, line, msg)
                    for line, msg in check_file(os.path.join(PKG, name),
                                                headers)]
    return out


def count_statements():
    """Return how many WRITE(msgBuf,...) statements the check covers."""
    return sum(1 for name in os.listdir(PKG) if name.endswith(".F")
               for _ in statements(os.path.join(PKG, name)))


# ---------------------------------------------------------------------------
# The checks


def test_descriptor_kinds_expand_counts_and_groups():
    """Hand-computed expansions, including the two formats that were wrong."""
    assert descriptor_kinds("2A") == ["c", "c"]
    assert descriptor_kinds("A,I8,A") == ["c", "i", "c"]
    assert descriptor_kinds("A,2(A,I8)") == ["c", "c", "i", "c", "i"]
    assert descriptor_kinds("3A,1PE16.8,A,I12") == [
        "c", "c", "c", "r", "c", "i"]
    assert descriptor_kinds("6A,I12,A,4I6") == (
        ["c"]*6 + ["i", "c"] + ["i"]*4)
    assert descriptor_kinds("A,I6,A,I6,A") == ["c", "i", "c", "i", "c"]
    # reversion: the last top-level group repeats, not the whole format
    assert reverted_kinds("A,2(A,I8)", 6) == [
        "c", "c", "i", "c", "i", "c"]
    assert reverted_kinds("A,I8", 4) == ["c", "i", "c", "i"]


def test_item_kind_uses_the_declared_type_of_the_routine():
    """The same name is character in one routine and real in another."""
    headers = symbols_of_headers()
    # RNF.h constants and bounds
    assert headers["RNF_FRACTOL"] == "r"
    assert headers["RNF_NSRCTILE"] == "i"
    assert headers["RNF_FILE"] == "c"
    # literals and intrinsics
    assert item_kind("'text'", headers) == "c"
    assert item_kind("12", headers) == "i"
    assert item_kind("1. _d 0", headers) == "r"
    assert item_kind("LEN(attVal)", headers) == "i"
    assert item_kind("NF_STRERROR(errNC)", headers) == "c"
    assert item_kind("RNF_period", headers) == "r"
    assert item_kind("RNF_nSrcTile", headers) == "i"
    # per-routine scoping of attVal in rnf_nc_utils.F
    kinds = []
    for lo, hi, local in scopes(os.path.join(PKG, "rnf_nc_utils.F")):
        if "ATTVAL" in local:
            kinds.append(local["ATTVAL"])
    assert sorted(kinds) == ["c", "r"], kinds


def test_the_two_fixed_bugs_and_an_integer_real_mix_are_detected(tmp_path):
    """The checker must fail on the bugs it exists to catch.

    Three synthetic routines: the ``RNF_NC_TGT_ERROR`` format that was one
    ``A`` short, the ``RNF_NC_ATT_REAL`` repeat group that put a string where
    an integer was written, and an ``I`` descriptor with a ``_RL`` item, which
    a two-class checker would accept.
    """
    src = (
        "      SUBROUTINE BAD_ONE( myThid )\n"
        "      CHARACTER*(MAX_LEN_MBUF) msgBuf\n"
        "      CHARACTER*(8) caller\n"
        "      INTEGER cell, i, j, bi, bj\n"
        "      WRITE(msgBuf,'(5A,I12,A,4I6)') caller, ': RNF: ',\n"
        "     &     'text', ': source ', caller,\n"
        "     &     ', target_cell', cell, ', i,j,bi,bj =', i, j, bi, bj\n"
        "      RETURN\n"
        "      END\n"
        "      SUBROUTINE BAD_TWO( myThid )\n"
        "      CHARACTER*(MAX_LEN_MBUF) msgBuf\n"
        "      INTEGER attType, nVals\n"
        "      WRITE(msgBuf,'(A,2(A,I6))') 'it has type',\n"
        "     &     attType, ' and', nVals, ' value(s)'\n"
        "      RETURN\n"
        "      END\n"
        "      SUBROUTINE BAD_THREE( myThid )\n"
        "      CHARACTER*(MAX_LEN_MBUF) msgBuf\n"
        "      _RL     fracF\n"
        "      WRITE(msgBuf,'(A,I12)') 'fraction', fracF\n"
        "      RETURN\n"
        "      END\n")
    path = tmp_path / "mutant.F"
    path.write_text(src)
    found = check_file(str(path), symbols_of_headers())
    # one misplaced item shifts every item after it, so a statement can
    # report more than one finding; what matters is that each of the three
    # is reported, with the type clash named
    assert sorted({line for line, _ in found}) == [5, 13, 20], found
    text = {line: " ".join(m for l, m in found if l == line)
            for line in (5, 13, 20)}
    assert "is c but descriptor 6" in text[5], text[5]
    assert "is c but descriptor 3" in text[13], text[13]
    assert "(fracF) is r but descriptor 2" in text[20], text[20]


def test_format_reversion_onto_a_second_record_is_detected(tmp_path):
    """The old zero-count message of RNF_INIT_FIXED must be flagged.

    ``'(A,2(A,I8))'`` with six items passed the kind check, because the
    reversion tail has the right kinds, yet it fails at run time: msgBuf
    is a one-record internal unit (RUNOFF-017). The corrected format and
    one that fits without reversion must stay clean.
    """
    def run(fmt):
        src = ("      SUBROUTINE T( myThid )\n"
               "      CHARACTER*(MAX_LEN_MBUF) msgBuf\n"
               "      INTEGER nS, nT\n"
               "      WRITE(msgBuf,'(" + fmt + ")') 'the file',\n"
               "     &    ' has', nS, ' source(s) and', nT,\n"
               "     &    ' target entry(ies)'\n"
               "      RETURN\n"
               "      END\n")
        path = tmp_path / "t.F"
        path.write_text(src)
        return check_file(str(path), symbols_of_headers())
    old = run("A,2(A,I8)")
    assert len(old) == 1 and "second record" in old[0][1], old
    assert run("A,A,I8,A,I8,A") == []


def test_pkg_rnf_write_statements_match_their_formats():
    """Every WRITE(msgBuf,...) of pkg/rnf writes the types its format says."""
    found = check_package()
    assert not found, "\n".join("{0}:{1}: {2}".format(*f) for f in found)


def test_every_write_item_of_pkg_rnf_is_classified():
    """The check covers every statement: no item of unknown type."""
    assert count_statements() >= 70
    assert not [f for f in check_package() if "no known type" in f[2]]


# ---------------------------------------------------------------------------
# Width of the diagnostics names and titles (RUNOFF-047)

DIAG_FILE = os.path.join(PKG, "rnf_diagnostics_init.F")
DIAG_LIMITS = {"diagName": 8, "diagTitle": 80}


def _fortran_string(text):
    """Return the value of a quoted Fortran literal (doubled quote = one)."""
    return text[1:-1].replace("''", "'")


def _joined_statements(path):
    """Yield ``(line number, statement)`` with continuations joined."""
    raw = open(path).read().split("\n")
    i = 0
    while i < len(raw):
        line = raw[i]
        if line.startswith(("C", "c", "*", "#", "!")) or not line.strip():
            i += 1
            continue
        stmt, j = line[6:], i + 1
        while j < len(raw) and len(raw[j]) > 5 and raw[j][5] not in (" ", ""):
            stmt += " " + raw[j][6:]
            j += 1
        yield i + 1, stmt.strip()
        i = j


def guard_limit(path):
    """Return N of the ``IF ( RNF_nTr .GT. N )`` guard, or None if absent."""
    for _, stmt in _joined_statements(path):
        m = re.match(r"IF\s*\(\s*RNF_nTr\s*\.GT\.\s*(\d+)\s*\)\s*THEN",
                     stmt, re.I)
        if m:
            return int(m.group(1))
    return None


def diag_widths(path):
    """Return ``[(line, variable, longest text, problem)]`` for the file.

    Every ``diagName = '...'``, ``diagTitle = '...' // '...'`` and
    ``WRITE(diagName|diagTitle,'(...)') items`` is evaluated. A loop index
    ``iTr`` takes the largest value the guard allows; an ``I`` field that
    cannot hold it is reported as a problem (it prints ``**``), and the
    title is also measured at the largest value its own ``Iw`` field holds.
    ``problem`` is empty when the field holds the value.
    """
    limit = guard_limit(path)
    out = []
    for line, stmt in _joined_statements(path):
        m = re.match(r"(diagName|diagTitle)\s*=\s*(.*)$", stmt)
        if m:
            parts = [p.strip() for p in m.group(2).split("//")]
            if all(p.startswith("'") for p in parts):
                out.append((line, m.group(1),
                            "".join(_fortran_string(p) for p in parts), ""))
            continue
        m = re.match(r"WRITE\((diagName|diagTitle),'\((.*?)\)'\)\s*(.*)$",
                     stmt)
        if not m:
            continue
        var, fmt, items = m.groups()
        values = split_items(items)
        descs = split_items(fmt)
        assert len(descs) == len(values), (line, fmt, items)
        text, problem = "", ""
        for desc, value in zip(descs, values):
            if desc == "A" and value.startswith("'"):
                text += _fortran_string(value)
                continue
            d = re.match(r"I(\d+)(?:\.(\d+))?$", desc)
            assert d and value == "iTr", (line, desc, value)
            width = int(d.group(1))
            top = 10 ** width - 1 if var == "diagTitle" else limit
            if top is None:
                top = 10 ** width - 1
                problem = "no guard on RNF_nTr"
            if top > 10 ** width - 1:
                problem = ("iTr up to {0} does not fit {1} (prints '*')"
                           .format(top, desc))
                digits = "*" * width
            else:
                digits = str(top).zfill(int(d.group(2) or 0)).rjust(width)
            text += digits
        out.append((line, var, text, problem))
    return out


def diag_findings(path):
    """Return one message per name or title that is too long or collides."""
    found = []
    for line, var, text, problem in diag_widths(path):
        if problem:
            found.append("{0}:{1}: {2}: {3}: '{4}'".format(
                os.path.basename(path), line, var, problem, text))
        if len(text) > DIAG_LIMITS[var]:
            found.append("{0}:{1}: {2} '{3}' has {4} characters, limit {5}"
                         .format(os.path.basename(path), line, var, text,
                                 len(text), DIAG_LIMITS[var]))
    return found


def test_diagnostics_names_and_titles_fit_their_fields():
    """diagName <= 8 and diagTitle <= 80 characters, loops at the guard."""
    rows = diag_widths(DIAG_FILE)
    assert len([r for r in rows if r[1] == "diagName"]) >= 12, rows
    assert len([r for r in rows if r[1] == "diagTitle"]) >= 12, rows
    assert guard_limit(DIAG_FILE) == 99
    assert not diag_findings(DIAG_FILE), "\n".join(diag_findings(DIAG_FILE))


def test_diagnostics_width_check_fails_on_two_mutants(tmp_path):
    """An 81-character title and a guard at 100 must each be reported.

    The mutants are copies of the real source; the live file is not edited.
    """
    real = open(DIAG_FILE).read()
    title = "'pkg/rnf runoff mass flux, rhoConstFresh*RNFvflx'"
    assert title in real and "RNF_nTr .GT. 99" in real
    long_title = "'" + "x" * 81 + "'"
    mutants = {"title81": real.replace(title, long_title, 1),
               "guard100": real.replace("RNF_nTr .GT. 99",
                                        "RNF_nTr .GT. 100")}
    for name, src in mutants.items():
        path = tmp_path / (name + ".F")
        path.write_text(src)
        found = diag_findings(str(path))
        assert found, name
        text = " ".join(found)
        if name == "title81":
            assert "diagTitle 'xxxx" in text and "has 81 characters" in text
        else:
            assert "diagName" in text and "does not fit I2.2" in text, text


def main():
    """Print one line per finding; exit non-zero if there is any."""
    found = check_package()
    for name, line, msg in found:
        print("{0}:{1}: {2}".format(name, line, msg))
    print("{0} WRITE(msgBuf) statements checked, {1} finding(s)".format(
        count_statements(), len(found)))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
