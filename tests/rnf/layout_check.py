#!/usr/bin/env python
"""Check that the sparse runoff does not depend on the tile layout (lab_sea).

RUNOFF-023, part 1. The sparse package keeps on each tile only the target
cells of that tile. A wrong tile offset would change the result with the
layout. So would a source cut by a tile edge or a process edge. So would an
overlap cell that a sum counts twice. This check runs the same case on five
layouts of the 20 x 16 grid and compares the layouts with each other.

Layouts (``nSx``, ``nSy`` tiles per process, ``nPx``, ``nPy`` processes):

```
====== ========= ======= ======= ========= ==============================
name   tile      nSx,nSy nPx,nPy processes build
====== ========= ======= ======= ========= ==============================
t1     20 x 16   1,1     1,1     1         ``build_rnflay_t1`` (new)
t4p1   10 x 8    2,2     1,1     1         ``build_esx`` (existing)
t4p2   10 x 8    1,2     2,1     2         ``build_esx_mpi2`` (existing)
t1p4   10 x 8    1,1     2,2     4         ``build_rnflay_p4`` (new)
t4p4u  5 x 4     2,2     2,2     4         ``build_rnflay_p4u`` (new)
====== ========= ======= ======= ========= ==============================
```

:func:`write_layout_code` writes the three new builds through
``tendency_term_check.write_mods_code``. It replaces the six tile numbers
of ``SIZE.h`` and keeps ``Nr`` and the overlaps. The model numbers the
processes x first. The layouts t1p4 and t4p4u split the sources over processes. The
layout t4p4u also cuts them at tile edges that no other layout has. The
limit of three new builds dropped one layout: 4 tiles of 5 x 8 or 10 x 4 on
4 processes.

The target cells come from ``input.rnof_const/runoff_sparse.nc``. It has 4
sources and 7 cells. The global cell is j*20 + i, 0-based. In the last five
columns the three digits are the process, then bi, then bj:

```
====== ======== ====== ==== ==== ==== ==== =====
cell   source    i,j    t1   t4p1 t4p2 t1p4 t4p4u
====== ======== ====== ==== ==== ==== ==== =====
52     newfound 12,2   011  021  111  111  111
147    labrador 7,7    011  011  011  011  022
167    labrador 7,8    011  012  012  211  221
233    greenland 13,11 011  022  112  311  311
288    baffin   8,14   011  012  012  211  222
289    baffin   9,14   011  012  012  211  222
290    baffin   10,14  011  022  112  311  312
====== ======== ====== ==== ==== ==== ==== =====
```

Baffin has cells on different tiles of one process in t4p1. It has cells
on different tiles and processes in t4p2, t1p4 and t4p4u. Labrador is
split over tiles in t4p1 and t4p2. It is split over processes in t1p4 and
t4p4u.

Each layout runs two cases, sparse and the dense twin without pkg/rnf:

* ``const``: ``input.rnof_sp_const`` and ``input.rnof_const``, 12 steps.
* ``daily``: ``input.rnof_sp_daily`` and ``input.rnof_daily``, 48 steps
  with time-varying records.

The scratch input changes only ``endTime``, ``monitorFreq`` (every step),
the float64 output and ``data.diagnostics``. That file dumps these fields
at every step. Sparse runs dump ``EXFroff``, ``RNFvflx``, ``RNFmflx``,
``RNFtemp``, ``RNFsaln`` and ``RNFnsrc``. All runs dump ``THETA``,
``SALT`` and ``ETAN``.

The check compares each of the 10 pairs of layouts:

a. The package fields above, bitwise, with tolerance 0. Every layout builds
   them from the same numbers in the same order.
b. The applied field of each layout against the file, with
   ``applied_field_check.compare``: bitwise, no extra or missing cell. The
   cell count that process 0 owns must equal the table above.
c. The ``%MON rnf_*`` lines of ``output.txt``, without ``*_del2``. The
   measure is the largest difference over the largest value of the series.
   The limit ``MON_RTOL`` is 1e-12. The monitor prints 14 digits, so this
   allows a few units in the last digit from the order of a global sum.
d. ``THETA``, ``SALT``, ``ETAN`` and the ``dynstat`` extremes. The largest
   difference of a pair must not exceed ``FACTOR`` = 2 times the largest
   difference of the same pair in the dense twin. The dense twin has no
   pkg/rnf code in the run, so it is the model's own tile-size noise. The
   factor 2 only leaves room for the order of a sum. If the dense pair is
   bitwise equal, the sparse pair must be bitwise equal.

Measured: the layouts with the same tile size (t4p1, t4p2, t1p4) are
bitwise equal in every field, sparse and dense. Layouts with different
tile sizes differ by at most 1.3e-4 in Theta, 8.5e-6 in Salt and 1.8e-5 in
Eta. The sparse runs show exactly the dense differences. The package
fields are bitwise equal in all pairs. The ``rnf_vflx_del2`` monitor
depends on the tile size, because a Laplacian statistic sees the tile
edges. The check reports it and does not judge it.

**Must-fail mutant** (``--mutant``). A copy of ``rnf_init_fixed.F`` has its
own directory ``code_rnflay_mut`` and build ``build_rnflay_mut``, on layout
t4p4u. It adds one to the stored local x index of each target when the
cell to the east is wet. It does this on tile bi=2 and on every process
but the first. The model refuses a shift into land with its own volume
guard. It refuses a doubled cell in the same way. So the mutant also sets
``RNF_cellVolMax`` to 1e30 in its own ``RNF.h``. The check must fail for
the mutant, and it does in the pairs with the other layouts. The mutant
has no single-tile layout. There the mutant is inert by construction, and
this is not measured.

**Offline variants of the check** (``--variants``) change the check and use
the mutant data. They reverse the layout order. They drop one layout and
two layouts. They set a tolerance of 1e-3. They keep only the state rule or
only the package rule.

**Limits.** This check does not cover cs32 or any exch2 grid, OpenMP
threads, ``do_tst_2+2`` (RUNOFF-023 part 2), the default addMass route
(only ``RNF_applyAsRain = .TRUE.`` runs), tile sizes that cut the sources
in other ways than the five layouts, or 3D runoff. The mutant runs the
``const`` case only. The option ``--build`` compiles the new builds and
nothing else.

Exit status: 0 if every case passes, 1 if one fails, 2 if a build or run
is missing or fails.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (ROOT, VERIF, add_to_namelist,  # noqa: E402
                           check_build_fresh, kill_run, read_file,
                           replace_line)
from applied_field_check import (STREAM, compare, dumps,  # noqa: E402
                                 set_namelist, time_step, rnf_file)
from timing_field_check import start_time  # noqa: E402
from tendency_term_check import build_if_stale, write_mods_code  # noqa: E402

EXPERIMENT = "lab_sea"
LAB = os.path.join(VERIF, EXPERIMENT)
NX, NY = 20, 16

#: name, build directory, process count (0: single process), tiling.
#: ``code`` is the mods directory written for a new build (None: existing).
LAYOUTS = (
    {"name": "t1", "build": "build_rnflay_t1", "mpi": 0,
     "code": "code_rnflay_t1", "size": (20, 16, 1, 1, 1, 1)},
    {"name": "t4p1", "build": "build_esx", "mpi": 0, "code": None,
     "size": (10, 8, 2, 2, 1, 1)},
    {"name": "t4p2", "build": "build_esx_mpi2", "mpi": 2, "code": None,
     "size": (10, 8, 1, 2, 2, 1)},
    {"name": "t1p4", "build": "build_rnflay_p4", "mpi": 4,
     "code": "code_rnflay_p4", "size": (10, 8, 1, 1, 2, 2)},
    {"name": "t4p4u", "build": "build_rnflay_p4u", "mpi": 4,
     "code": "code_rnflay_p4u", "size": (5, 4, 2, 2, 2, 2)},
)
MUTANT = {"name": "mut", "build": "build_rnflay_mut", "mpi": 4,
          "code": "code_rnflay_mut", "size": (5, 4, 2, 2, 2, 2)}

LAYOUT_BY_NAME = {lay["name"]: lay for lay in LAYOUTS}
LAYOUT_BY_NAME["mut"] = MUTANT
#: The 7 target cells of input.rnof_const/runoff_sparse.nc (0-based, j*20+i).
CELLS = (52, 147, 167, 233, 288, 289, 290)

#: cases: sparse input, dense twin, steps
CASES = (
    {"name": "const", "sparse": "input.rnof_sp_const",
     "dense": "input.rnof_const", "steps": 12},
    {"name": "daily", "sparse": "input.rnof_sp_daily",
     "dense": "input.rnof_daily", "steps": 48},
)

#: (stream, diagnostic) written by sparse runs only / by all runs.
SPARSE_ONLY = (("rnfVflx", "RNFvflx"), ("rnfMflx", "RNFmflx"),
               ("rnfTemp", "RNFtemp"), ("rnfSaln", "RNFsaln"),
               ("rnfNsrc", "RNFnsrc"))
ALL_RUNS = ((STREAM, "EXFroff"), ("stTheta", "THETA"), ("stSalt", "SALT"),
            ("stEta", "ETAN"))
STATE = ("stTheta", "stSalt", "stEta")
PKG_FIELDS = tuple(s for s, _ in SPARSE_ONLY) + (STREAM,)

#: Factor on the dense baseline and relative bound on rnf monitor sums.
FACTOR = 2.0
MON_RTOL = 1.0e-12


# ---------------------------------------------------------------- layouts
def tile_of(layout, i, j):
    """Return (process, bi, bj, local i, local j), all 1-based, of cell (i,j).

    ``i``, ``j`` are 0-based global indices. Processes are numbered x
    fastest; tile (bi,bj) of process (px,py) starts at global
    ``(px*nSx + bi-1)*sNx``.
    """
    sx, sy, nsx, nsy, npx, npy = layout["size"]
    gi, gj = i // sx, j // sy
    px, bi = divmod(gi, nsx)
    py, bj = divmod(gj, nsy)
    return (py * npx + px, bi + 1, bj + 1, i % sx + 1, j % sy + 1)


def size_text(size):
    """Return lab_sea's ``SIZE.h`` with the tiling ``size`` put in."""
    with open(os.path.join(LAB, "code", "SIZE.h")) as fh:
        text = fh.read()
    names = ("sNx", "sNy", "nSx", "nSy", "nPx", "nPy")
    sx, sy, nsx, nsy, npx, npy = size
    if (sx * nsx * npx, sy * nsy * npy) != (NX, NY):
        raise ValueError(f"tiling {size} is not {NX} x {NY}")
    for name, value in zip(names, size):
        text, count = re.subn(r"(?m)^(\s*&\s+%s\s*=\s*)\d+," % name,
                              lambda m: "%s%3d," % (m.group(1), value), text)
        if count != 1:
            raise ValueError(f"SIZE.h has {count} lines for {name}")
    return text


def mutant_source():
    """Return rnf_init_fixed.F with a tile-dependent placement error.

    After the entry has passed every check, the stored local x index is
    raised by one, when the cell to the east is wet, on tile bi=2 and on
    every process but the first.
    """
    path = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "rnf_init_fixed.F")
    with open(path) as fh:
        text = fh.read()
    old = "               RNF_tgtI(k,bi,bj) = iLoc\n"
    new = old + ("               IF ( ( bi.EQ.2 .OR. myProcId.GT.0 )\n"
                 "     &           .AND. hFacC(iLoc+1,j,1,bi,bj).GT.0. _d 0 )\n"
                 "     &           RNF_tgtI(k,bi,bj) = iLoc + 1\n")
    if text.count(old) != 1:
        raise ValueError("rnf_init_fixed.F: placement line not found once")
    text = text.replace(old, new)
    inc = '#include "EEPARAMS.h"\n'
    if text.count(inc) != 1:
        raise ValueError("rnf_init_fixed.F: EEPARAMS.h include not once")
    return text.replace(inc, inc + '#include "EESUPPORT.h"\n')


def mutant_header():
    """Return RNF.h with RNF_cellVolMax raised to 1e30.

    The per-cell volume guard of RNF_EXF_RUNOFF refuses a misplaced cell
    at step 1 (measured: a shift of one cell in x or y that lands on land, or
    on a wet cell that takes 0.2 of its volume), so the mutant run could not be compared without this second change. It
    is a PARAMETER of RNF.h, not a namelist entry.
    """
    path = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "RNF.h")
    with open(path) as fh:
        text = fh.read()
    old = "PARAMETER ( RNF_cellVolMax = 0.2 _d 0 )"
    if text.count(old) != 1:
        raise ValueError("RNF.h: RNF_cellVolMax parameter not found once")
    return text.replace(old, "PARAMETER ( RNF_cellVolMax = 1.0 _d 30 )")


def write_layout_code(layout, mutant=False):
    """Write the mods directory of a layout; return its path."""
    text = size_text(layout["size"])
    files = {"SIZE.h": text, "SIZE.h_mpi": text}
    if mutant:
        files["rnf_init_fixed.F"] = mutant_source()
        files["RNF.h"] = mutant_header()
    return write_mods_code(layout["code"], files)


def ensure_build(layout, mutant=False, jobs=4):
    """Return an error string if the build is missing/stale (and cannot be
    built), after compiling a new layout's build when needed."""
    if layout["code"]:
        info = build_if_stale(
            layout["build"], lambda: write_layout_code(layout, mutant),
            jobs=jobs, mpi=bool(layout["mpi"]))
        print(f"BUILD {layout['build']}: {info['action']} "
              f"({info['seconds']:.0f} s)")
        return None if info["ok"] else info.get("log_tail", "failed")
    binary = os.path.join(LAB, layout["build"], "mitgcmuv")
    if not os.path.isfile(binary):
        return f"missing {binary}"
    return check_build_fresh(binary, os.path.join(LAB, "code"))


# ----------------------------------------------------------------- inputs
def diagnostics_text(streams, dt):
    """Return a data.diagnostics dumping each (stream, field) every step."""
    lines = ["# Written by tests/rnf/layout_check.py: float64 snapshots.",
             " &DIAGNOSTICS_LIST", "  diag_mnc = .FALSE.,"]
    for n, (stream, field) in enumerate(streams, 1):
        lines += [f"  fields(1,{n}) = '{field:<8s}',",
                  f"  fileName({n}) = '{stream}',",
                  f"  frequency({n}) = -{dt!r},",
                  f"  fileFlags({n}) = 'D       ',"]
    return "\n".join(lines) + "\n &\n\n &DIAG_STATIS_PARMS\n &\n"


def write_input(case, dense, input_dir, rnf_set=None):
    """Build the scratch input of a case; return the RNF file or None."""
    src = os.path.join(LAB, case["dense" if dense else "sparse"])
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if os.path.isfile(path):
            shutil.copyfile(path, os.path.join(input_dir, name))
    with open(os.path.join(src, "data")) as fh:
        data = fh.read()
    dt, t0 = time_step(data), start_time(data)
    data = set_namelist(data, "PARM01", "writeBinaryPrec",
                        " writeBinaryPrec=64,")
    data = set_namelist(data, "PARM03", "outputTypesInclusive",
                        " outputTypesInclusive=.TRUE.,")
    data = replace_line(data, "endTime",
                        f" endTime={t0 + case['steps'] * dt!r},")
    data = replace_line(data, "monitorFreq", " monitorFreq=1.,")
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)
    streams = ALL_RUNS if dense else SPARSE_ONLY + ALL_RUNS
    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(diagnostics_text(streams, dt))
    if dense:
        return None
    path = os.path.join(input_dir, "data.rnf")
    with open(path) as fh:
        rnf = fh.read()
    rnf = replace_line(rnf, "RNF_debugLev", "  RNF_debugLev = 3,")
    for key, value in (rnf_set or {}).items():
        rnf = add_to_namelist(rnf, "RNF_PARM01", f"  {key} = {value},")
    with open(path, "w") as fh:
        fh.write(rnf)
    return rnf_file(rnf)


def run_model(layout, input_name, output_name, timeout):
    """Run a scratch input with a layout's binary."""
    run_dir = os.path.join(LAB, output_name)
    shutil.rmtree(run_dir, ignore_errors=True)
    cmd = ["./experiment_run_no_compile.sh", EXPERIMENT, input_name]
    if layout["mpi"]:
        cmd += ["-mpi", str(layout["mpi"])]
    cmd += ["-build", layout["build"], "-output", output_name]
    try:
        proc = subprocess.run(cmd, cwd=VERIF, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True,
                              timeout=timeout)
        return run_dir, proc.returncode, False
    except subprocess.TimeoutExpired:
        kill_run(output_name)
        return run_dir, -1, True


# ---------------------------------------------------------------- reading
def read_dump(run_dir, stream, iteration):
    """Return a float64 array (levels, ny, nx) of one dump (precision checked)."""
    import numpy as np
    base = f"{stream}.{iteration}"
    meta = read_file(run_dir, base + ".meta") or ""
    prec = re.search(r"dataprec\s*=\s*\[\s*'([^']+)'", meta)
    dims = re.search(r"dimList\s*=\s*\[(.*?)\]", meta, re.DOTALL)
    if not prec or prec.group(1) != "float64" or not dims:
        raise ValueError(f"{base}.meta is missing or not float64")
    nums = [int(v) for v in re.findall(r"-?\d+", dims.group(1))]
    nx, ny = nums[0], nums[3]
    arr = np.fromfile(os.path.join(run_dir, base + ".data"), dtype=">f8")
    if arr.size % (nx * ny):
        raise ValueError(f"{base}.data has {arr.size} values for {nx}x{ny}")
    return arr.astype(np.float64).reshape(-1, ny, nx)


def read_stream(run_dir, stream):
    """Return {iteration: array} for every dump of a stream (>= 1 needed)."""
    its, strays = dumps(run_dir, stream)
    if strays or not its:
        raise ValueError(f"stream {stream}: {len(its)} dumps, strays {strays}")
    return {it: read_dump(run_dir, stream, it) for it in its}


def monitors(run_dir):
    """Return {name: [value strings]} of the ``%MON`` lines of output.txt."""
    out = {}
    text = read_file(run_dir, "output.txt") or ""
    for m in re.finditer(r"%MON\s+(\S+)\s*=\s*(\S+)", text):
        out.setdefault(m.group(1), []).append(m.group(2))
    return out


def run_one(layout, case, dense, timeout, keep, tag="", rnf_set=None):
    """Run one (layout, case, dense) and return its data dictionary."""
    name = f"{case['name']}_{layout['name']}{'_dense' if dense else ''}{tag}"
    input_name, output_name = "input.rnflay_" + name, "output_rnflay_" + name
    input_dir = os.path.join(LAB, input_name)
    shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir)
    res = {"layout": layout["name"], "case": case["name"], "dense": dense,
           "problems": [], "fields": {}}
    run_dir = None
    try:
        rnf_name = write_input(case, dense, input_dir, rnf_set)
        run_dir, status, timed_out = run_model(layout, input_name,
                                               output_name, timeout)
        logs = "\n".join(filter(None, (read_file(run_dir, n) for n in
                                       ("output.txt", "mpirun.log"))))
        if timed_out or status != 0 or "Execution ended Normally" not in logs:
            res["problems"].append(f"{name}: run did not end normally "
                                   f"(exit {status}, timeout {timed_out})")
            return res
        streams = ALL_RUNS if dense else SPARSE_ONLY + ALL_RUNS
        for stream, _ in streams:
            res["fields"][stream] = read_stream(run_dir, stream)
        res["mon"] = monitors(run_dir)
        if not dense:
            owned = re.search(r"owned here:\s*(\d+)", logs)
            res["owned"] = int(owned.group(1)) if owned else None
            committed = os.path.normpath(os.path.join(
                LAB, case["sparse"], rnf_name))
            iters = sorted(res["fields"][STREAM])
            res["file"] = compare(run_dir, committed, iters)
    except ValueError as err:
        res["problems"].append(f"{name}: {err}")
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)
        if run_dir and not keep:
            shutil.rmtree(run_dir, ignore_errors=True)
    return res


# -------------------------------------------------------------- comparing
def maxabs(a, b):
    """Largest absolute difference of two {iteration: array} dictionaries."""
    import numpy as np
    if a.keys() != b.keys():
        return float("inf")
    worst = 0.0
    for it in a:
        d = np.abs(a[it] - b[it])
        d = np.where(np.isfinite(d), d, np.inf)
        worst = max(worst, float(d.max()))
    return worst


def mon_diff(a, b, prefix, del2=False, only=None):
    """(largest difference / series scale, count of differing strings).

    The scale is the largest absolute value of the series over the run,
    so that a statistic that passes near zero is not judged on a ratio of
    round-off to round-off. ``del2`` selects the ``*_del2`` statistics
    only (True) or leaves them out (False): they are Laplacian
    statistics, which see tile edges (see the module docstring).
    """
    worst, nstr = 0.0, 0
    for key in sorted(a):
        if (not key.startswith(prefix) or key not in b
                or key.endswith("_del2") != del2
                or (only and not key.endswith(only))):
            continue
        if len(a[key]) != len(b[key]):
            return float("inf"), 10 ** 6
        fa = [float(x.replace("D", "E")) for x in a[key]]
        fb = [float(x.replace("D", "E")) for x in b[key]]
        scale = max(max(map(abs, fa)), max(map(abs, fb)))
        for x, y, u, v in zip(a[key], b[key], fa, fb):
            if x != y:
                nstr += 1
                if scale:
                    worst = max(worst, abs(u - v) / scale)
    return worst, nstr


def pair_table(runs, order):
    """Return {(A,B): {metric: value}} for every pair in ``order``."""
    table = {}
    for n, a in enumerate(order):
        for b in order[n + 1:]:
            ra, rb = runs[a], runs[b]
            row = {s: maxabs(ra["fields"][s], rb["fields"][s])
                   for s in ra["fields"] if s in rb["fields"]}
            row["mon_dynstat"] = mon_diff(
                ra["mon"], rb["mon"], "dynstat_",
                only=("theta_max", "theta_min", "salt_max", "salt_min",
                      "eta_max", "eta_min"))[0]
            row["mon_rnf"] = mon_diff(ra["mon"], rb["mon"], "rnf_")[0]
            row["mon_rnf_del2"] = mon_diff(ra["mon"], rb["mon"], "rnf_",
                                           True)[0]
            table[(a, b)] = row
    return table


def judge(sparse, dense, order, factor=FACTOR, mon_rtol=MON_RTOL,
          state_rule=True, pkg_rule=True, min_layouts=4,
          pkg_tol=0.0):
    """Return the list of unmet expectations of one case.

    ``sparse`` and ``dense`` map layout name to run data. The knobs
    exist so that the offline variants of :func:`check_variants` can
    weaken the rule one way at a time.
    """
    problems = []
    if len(order) < min_layouts:
        problems.append(f"at least {min_layouts} layouts (got {len(order)})")
    st, dt = pair_table(sparse, order), pair_table(dense, order)
    for pair, row in st.items():
        if pkg_rule:
            for s in PKG_FIELDS:
                if row[s] > pkg_tol:
                    problems.append(f"{pair}: {s} differs by {row[s]:.3e}")
        if state_rule:
            for s in STATE + ("mon_dynstat",):
                if row[s] > factor * dt[pair][s]:
                    problems.append(f"{pair}: {s} differs by {row[s]:.3e} > "
                                    f"{factor} x baseline "
                                    f"{dt[pair][s]:.3e}")
        if row["mon_rnf"] > mon_rtol:
            problems.append(f"{pair}: rnf monitor differs by "
                            f"{row['mon_rnf']:.3e}")
    for name in order:
        run = sparse[name]
        f = run["file"]
        want = sum(1 for c in CELLS
                   if tile_of(LAYOUT_BY_NAME[name], c % NX, c // NX)[0] == 0)
        if run.get("owned") != want or f["extra"] or f["missing"] \
                or not f["bitwise"]:
            problems.append(f"{name}: applied field vs file: owned "
                            f"{run.get('owned')} (process 0 should own "
                            f"{want}), extra {f['extra']}, "
                            f"missing {f['missing']}, bitwise {f['bitwise']}")
    return problems


def check_variants(sparse, dense, order, mutant_run):
    """Run offline variants of the check; return {label: (problems, note)}.

    Each variant changes the check, not the model, and says what it did.
    """
    import copy
    out = {}
    mut = copy.copy(sparse)
    mut[order[-1]] = mutant_run
    out["real check, mutant model in last layout"] = judge(mut, dense, order)
    out["layouts in the wrong order (reversed), mutant model"] = judge(
        mut, dense, list(reversed(order)))
    out["drop the layout of the mutant (4 layouts left)"] = judge(
        mut, dense, order[:-1], min_layouts=4)
    out["drop two layouts"] = judge(mut, dense, order[:-2])
    out["tolerance 1e-3 on package fields and monitors"] = judge(
        mut, dense, order, mon_rtol=1e-3, pkg_tol=1e-3)
    out["state rule only, mutant model"] = judge(
        mut, dense, order, pkg_rule=False, mon_rtol=1e30)
    out["state factor 1e30 (state rule off), package rule on"] = judge(
        mut, {k: dense[k] for k in dense}, order, factor=1e30)
    return out


# ------------------------------------------------------------------- main
def print_table(title, table):
    """Print the pair table."""
    print(title)
    for (a, b), row in table.items():
        cells = ", ".join(f"{k}={v:.2e}" for k, v in row.items())
        print(f"  {a:>6s} vs {b:<6s} {cells}")


def main(argv=None):
    """Run the layouts and return the exit status."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", default=[])
    ap.add_argument("--build", action="store_true",
                    help="compile the missing layout builds")
    ap.add_argument("--mutant", action="store_true",
                    help="build and run the tile-dependent placement mutant")
    ap.add_argument("--variants", action="store_true",
                    help="run the offline variants of the check")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--timeout", type=float, default=1200.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    cases = [c for c in CASES if not args.case or c["name"] in args.case]
    for lay in LAYOUTS + ((MUTANT,) if args.mutant else ()):
        if args.build and lay["code"]:
            err = ensure_build(lay, mutant=lay is MUTANT)
        else:
            binary = os.path.join(LAB, lay["build"], "mitgcmuv")
            err = None if os.path.isfile(binary) else f"missing {binary}"
            if not err and not lay["code"]:
                err = check_build_fresh(binary, os.path.join(LAB, "code"))
        if err:
            print(err, file=sys.stderr)
            return 2
    order = [lay["name"] for lay in LAYOUTS]
    status, report = 0, {}
    for case in cases:
        sparse, dense = {}, {}
        for lay in LAYOUTS:
            sparse[lay["name"]] = run_one(lay, case, False, args.timeout,
                                          args.keep)
            dense[lay["name"]] = run_one(lay, case, True, args.timeout,
                                         args.keep)
        bad = [p for r in list(sparse.values()) + list(dense.values())
               for p in r["problems"]]
        if bad:
            print("\n".join(bad))
            return 2
        print_table(f"== {case['name']} sparse, layout pairs",
                    pair_table(sparse, order))
        print_table(f"== {case['name']} dense twin (baseline)",
                    pair_table(dense, order))
        problems = judge(sparse, dense, order)
        print(f"{'FAIL' if problems else 'PASS'} {case['name']}")
        for p in problems:
            print("   missing:", p)
        status = status or (1 if problems else 0)
        if args.mutant and case["name"] == "const":
            mrun = run_one(MUTANT, case, False, args.timeout, args.keep)
            if mrun["problems"]:
                print("\n".join(mrun["problems"]))
                return 2
            mixed = dict(sparse)
            mixed[MUTANT["name"]] = mrun
            order_m = order + [MUTANT["name"]]
            print_table("== mutant vs correct layouts",
                        pair_table(mixed, order_m))
            mp = judge(mixed, dense | {MUTANT["name"]: dense[order[-1]]},
                       order_m, min_layouts=4)
            print(f"mutant verdict: {'FAIL (detected)' if mp else 'PASS'}")
            for p in mp[:12]:
                print("   missing:", p)
            if args.variants:
                for label, probs in check_variants(
                        sparse, dense, order, mrun).items():
                    print(f"variant {label}: "
                          f"{'FAIL' if probs else 'PASS'} ({len(probs)})")
        report[case["name"]] = {"problems": problems}
    if args.json:
        print(json.dumps(report, indent=1))
    return status


if __name__ == "__main__":
    sys.exit(main())
