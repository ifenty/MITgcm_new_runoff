#!/usr/bin/env python
"""Check where pkg/rnf places a fixed set of cells on the tiles of an exch2 grid.

The probe makes the model say where it puts a set of global cell indices and
compares the answer with a placement computed here from the exch2 (W2)
topology. It checks the placement arithmetic on the cells it samples: the
four corners of every tile and fixed interior positions, at most 20 per
process. It does not read a runoff file, and it is not a check of the runoff
targets of an experiment: a target on a cell that the probe does not sample
is not covered by it.

The sparse = dense oracle of ``global_ocean.cs32x15`` does not see a one-cell
move of its weakest targets either (``docs/verification_matrix.md``, coverage
limits). What protects such a target is not this probe but, since
RUNOFF-033, ``tests/rnf/applied_field_check.py``, which compares the field
the model applies with the field the file asks for on every cell, and the
cell-centre check of ``RNF_INIT_FIXED`` when the file has
``target_lon``/``target_lat``. The area check of ``RNF_INIT_FIXED`` covers
only a move between cells of different area.

How the model is made to answer. ``RNF_INIT_FIXED`` refuses a target on land,
and a target whose ``target_cell_area`` differs from the cell area, with a
message that gives the cell index of the file and the local indices
``i,j,bi,bj`` where the target was placed. The probe file gives every target
an area of 1 m^2, so every probe is refused and reported. A process prints
at most ``RNF_maxErrMsg`` (20) such messages, so each process gets at most
that many probes: the four corners of each of its tiles, and interior cells.

For each exch2 I/O layout (``W2_mapIO`` = -1, 0, 1 in ``data.exch2``) the
probe runs the model twice on N processes with the existing
``build_esx_mpiN`` binary of ``global_ocean.cs32x15``; nothing is compiled.

1. A run without the probe file stops when ``RNF_INIT_FIXED`` cannot open
   it. By then exch2 has written ``w2_tile_topology.NNNN.log``: the size of
   the global I/O map, the facets, each tile's facet, offset in the facet and
   position on the global map, and the tiles of each process with their
   ``bi,bj``.
2. From those logs the probe computes the global index of each probe cell
   (``predict``), writes the probe file and runs the model again.

The placement rule used here is the definition of the layouts, not the record
arithmetic of the model: with ``W2_mapIO = -1`` the facets lie side by side
in x; with 0 and 1 the file holds the facets one after another, each row by
row. The rule is checked against exch2's own "on Glob.Map" position of every
tile before it is used.

A layout passes when all of these hold:

* the run finished within ``--timeout`` seconds and did not end normally;
* the set of ``(cell, process, i, j, bi, bj)`` the model reports equals the
  prediction, with nothing missing and nothing extra;
* each probe is reported "on land" exactly where the bathymetry file holds a
  land value at that cell index, the value the model's dense reader puts on
  the cell where the target was placed (with ``W2_mapIO`` 0 and 1 the
  bathymetry is read in a layout it was not written for; the comparison
  still holds, because it is made index by index);
* every process prints the number of probes as the count of refused targets
  and there is one ``STOP`` line per process.

A control run (``W2_mapIO = -1``, every probe index raised by one) must fail
the comparison for every probe: it shows that a one-cell move is detected.

The scratch input and run directories are removed afterwards (``--keep``
leaves the run directories). Exit status: 0 if every layout and the control
pass, 1 otherwise, 2 if the binary is missing or the layout of the processes
leaves no room for the corners.

Usage::

    python tests/rnf/placement_probe.py [--mpi N] [--map M ...] [--keep]
                                        [--json] [--timeout S]
"""
import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import ROOT, VERIF, kill_run, read_file  # noqa: E402

EXPERIMENT = "global_ocean.cs32x15"
BASE_INPUT = "input.rnof_sp_icedyn"
PREFIX = "input.rnfprobe_"
BUILD = "build_esx"
RNF_H = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "RNF.h")

DATA_RNF = """# Sparse runoff package parameters: the placement probe
 &RNF_PARM01
  RNF_file = 'probe.nc',
 &
"""
DATA_EXCH2 = """# exch2 I/O layout of the placement probe
 &W2_EXCH2_PARM01
  W2_mapIO = {0},
 &
"""
KINDS = {"target on land": "land",
         "target_cell_area differs from the cell area rA": "area"}
REPORT = re.compile(
    r"RNF_INIT_FIXED: RNF: (" + "|".join(re.escape(k) for k in KINDS)
    + r"): source (\S+), target_cell\s+(-?\d+), i,j,bi,bj =\s+(\d+)\s+(\d+)"
    r"\s+(\d+)\s+(\d+)")
# Interior cells of a tile, as fractions of its size; used in turn.
INTERIOR = ((0.10, 0.20), (0.50, 0.50), (0.90, 0.80), (0.30, 0.85),
            (0.75, 0.15), (0.55, 0.35), (0.20, 0.60), (0.85, 0.45))


def message_cap():
    """Return ``RNF_maxErrMsg``, the messages one process prints per counter."""
    with open(RNF_H) as fh:
        match = re.search(r"PARAMETER\s*\(\s*RNF_maxErrMsg\s*=\s*(\d+)\s*\)",
                          fh.read())
    if not match:
        raise ValueError(f"RNF_maxErrMsg not found in {RNF_H}")
    return int(match.group(1))


def read_topology(run_dir, nproc):
    """Return the exch2 topology that the model wrote in ``run_dir``.

    Read from ``w2_tile_topology.NNNN.log``. The result has ``map`` (size of
    the global I/O map), ``facets`` (number to ``(x size, y size)``),
    ``tile_size``, ``tiles`` (number to a dictionary with ``facet``,
    ``offset`` in the facet and ``on_map``, the 1-based position on the
    global map) and ``owner`` (tile number to ``(process, bi, bj)``).
    Raises ``ValueError`` if a log or one of these lines is missing.
    """
    text = read_file(run_dir, "w2_tile_topology.0000.log")
    if text is None:
        raise ValueError("no w2_tile_topology.0000.log")
    size = re.search(r"Global Map \(IO\): X-size=\s*(\d+) , Y-size=\s*(\d+)", text)
    facets, counts = {}, {}
    for m in re.finditer(r"- facet\s*(\d+) : X-size=\s*(\d+) , Y-size=\s*(\d+) ;"
                         r"\s*\d+ tiles \(Tx,Ty=\s*(\d+),\s*(\d+)\)", text):
        f, nx, ny, tx, ty = (int(v) for v in m.groups())
        facets[f], counts[f] = (nx, ny), (tx, ty)
    tiles = {}
    for m in re.finditer(r"tile\s+(\d+) on facet\s*(\d+) \(\s*\d+,\s*\d+\):"
                         r" offset=\s*(\d+)\s+(\d+) ; on Glob.Map=\s*(\d+)\s+(\d+)",
                         text):
        t, f, bx, by, gx, gy = (int(v) for v in m.groups())
        tiles[t] = {"facet": f, "offset": (bx, by), "on_map": (gx, gy)}
    owner = {}
    for rank in range(max(nproc, 1)):
        log = read_file(run_dir, f"w2_tile_topology.{rank:04d}.log")
        if log is None:
            raise ValueError(f"no w2_tile_topology.{rank:04d}.log")
        for m in re.finditer(r"TILE:\s*(\d+) \(bi,bj=\s*(\d+)\s+(\d+)\s*\)", log):
            t, bi, bj = (int(v) for v in m.groups())
            owner[t] = (rank, bi, bj)
    if not size or not facets or not tiles or set(owner) != set(tiles):
        raise ValueError("the topology logs lack the map size, the facets, the "
                         "tiles or the tiles of each process")
    sizes = {(facets[f][0] // counts[f][0], facets[f][1] // counts[f][1])
             for f in facets}
    if len(sizes) != 1:
        raise ValueError(f"tiles of several sizes: {sorted(sizes)}")
    return {"map": (int(size.group(1)), int(size.group(2))), "facets": facets,
            "tile_size": sizes.pop(), "tiles": tiles, "owner": owner}


def predict(topo, map_io, tile, i, j):
    """Return the 0-based global index of cell ``(i, j)`` of ``tile``.

    Computed from the definition of the exch2 I/O layouts. The cell has the
    position ``(offset + i, offset + j)`` on its facet. With ``map_io`` -1
    the facets lie side by side in x on the global map. With 0 (one long
    line) and 1 (compact) the global file holds the facets one after another,
    each row by row, so the index is the number of cells of the facets before
    plus the row-by-row position on the facet; the two differ only in how the
    line is cut into rows of the map.
    """
    info = topo["tiles"][tile]
    facet = info["facet"]
    x = info["offset"][0] + i - 1
    y = info["offset"][1] + j - 1
    before = [f for f in sorted(topo["facets"]) if f < facet]
    if map_io == -1:
        return sum(topo["facets"][f][0] for f in before) + x + topo["map"][0] * y
    cells = sum(topo["facets"][f][0] * topo["facets"][f][1] for f in before)
    return cells + x + topo["facets"][facet][0] * y


def rule_matches_map(topo, map_io):
    """Return the tiles whose first cell ``predict`` puts off exch2's position.

    exch2 prints where each tile starts on the global map ("on Glob.Map").
    An empty list means the layout rule of ``predict`` agrees with it for
    every tile, and that the map has room for every facet cell.
    """
    nx, ny = topo["map"]
    total = sum(fx * fy for fx, fy in topo["facets"].values())
    bad = [] if nx * ny >= total else ["map smaller than the facets"]
    for tile, info in sorted(topo["tiles"].items()):
        gx, gy = info["on_map"]
        if predict(topo, map_io, tile, 1, 1) != (gx - 1) + nx * (gy - 1):
            bad.append(tile)
    return bad


def probe_cells(topo, cap):
    """Return the probe cells as a list of ``(tile, i, j)``.

    Each process gets the four corners of each of its tiles and interior
    cells up to ``cap`` probes in all, the interior cells spread over its
    tiles in turn. Raises ``ValueError`` if the corners alone exceed ``cap``.
    """
    nx, ny = topo["tile_size"]
    by_rank = {}
    for tile, (rank, _, _) in sorted(topo["owner"].items()):
        by_rank.setdefault(rank, []).append(tile)
    cells = []
    for rank, tiles in sorted(by_rank.items()):
        mine = [(t, i, j) for t in tiles for j in (1, ny) for i in (1, nx)]
        if len(mine) > cap:
            raise ValueError(
                f"process {rank} has {len(tiles)} tiles: their {len(mine)} "
                f"corners exceed the {cap} messages a process prints; run "
                f"on more processes")
        k = 0
        while len(mine) < cap and k < len(INTERIOR) * len(tiles):
            fx, fy = INTERIOR[k // len(tiles) % len(INTERIOR)]
            cell = (tiles[k % len(tiles)],
                    min(nx - 1, max(2, 1 + int(fx * nx) + k % 3)),
                    min(ny - 1, max(2, 1 + int(fy * ny))))
            if cell not in mine:
                mine.append(cell)
            k += 1
        cells += mine
    return cells


def write_probe(path, cells, map_size):
    """Write the probe file: one source per global index in ``cells``.

    Each source sends all its flux to one cell. ``target_cell_area`` is 1
    m^2 everywhere, far from any cell area, so that the model refuses and
    reports every target that is not on land.
    """
    import netCDF4
    import numpy as np
    n = len(cells)
    with netCDF4.Dataset(path, "w") as ds:
        ds.setncatts({"mitgcm_runoff_schema_version": "1.0",
                      "mitgcm_grid_nx": np.int32(map_size[0]),
                      "mitgcm_grid_ny": np.int32(map_size[1]),
                      "mitgcm_time_sampling": "constant",
                      "title": "placement probe of tests/rnf/placement_probe.py"})
        ds.createDimension("time", None)
        ds.createDimension("source", n)
        ds.createDimension("target", n)
        ds.createDimension("id_strlen", 6)
        ds.createVariable("time", "f8", ("time",))[:] = [0.0]
        ds["time"].units = "days since 0001-01-01 00:00:00"
        ids = np.array([list(f"p{k:05d}") for k in range(n)], dtype="S1")
        ds.createVariable("source_id", "S1", ("source", "id_strlen"))[:] = ids
        ds.createVariable("target_source", "i4", ("target",))[:] = np.arange(n)
        ds.createVariable("target_cell", "i4", ("target",))[:] = cells
        frac = ds.createVariable("target_fraction", "f8", ("target",))
        frac[:] = 1.0
        frac.units = "1"
        area = ds.createVariable("target_cell_area", "f8", ("target",))
        area[:] = 1.0
        area.units = "m2"
        flux = ds.createVariable("runoff_flux", "f8", ("time", "source"))
        flux[0, :] = 1.0e-3
        flux.units = "m3 s-1"


def bathymetry():
    """Return the bathymetry file of the experiment as a flat float64 array.

    The file name and its precision are read from ``data`` of
    ``input.icedyn``, the set-up the probe runs. A cell is land where the
    value is not negative.
    """
    import numpy as np
    base = os.path.join(VERIF, EXPERIMENT)
    with open(os.path.join(base, "input.icedyn", "data")) as fh:
        text = "\n".join(line for line in fh.read().splitlines()
                         if not line.lstrip().startswith("#"))
    name = re.search(r"bathyFile\s*=\s*'([^']+)'", text).group(1)
    prec = int(re.search(r"readBinaryPrec\s*=\s*(\d+)", text).group(1))
    for d in ("input.icedyn", "input"):
        path = os.path.join(base, d, name)
        if os.path.isfile(path):
            return np.fromfile(path, dtype=">f8" if prec == 64 else ">f4")
    raise ValueError(f"bathymetry file {name} not found")


def reports(run_dir, nproc):
    """Return what each process reported: ``(cell, process, i, j, bi, bj)``
    mapped to ``land`` or ``area``, read from its ``STDERR`` file."""
    found = {}
    for rank in range(max(nproc, 1)):
        text = read_file(run_dir, f"STDERR.{rank:04d}") or ""
        for m in REPORT.finditer(text):
            cell, i, j, bi, bj = (int(v) for v in m.groups()[2:])
            found[(cell, rank, i, j, bi, bj)] = KINDS[m.group(1)]
    return found


def run_model(input_name, nproc, timeout):
    """Run the scratch input ``input_name``; return ``(run dir, exit status,
    timed out)``. ``nproc`` 0 runs the single-process binary."""
    output_name = "output_esx_" + input_name
    build, mpi_args = BUILD, []
    if nproc:
        output_name += f"_mpi{nproc}"
        build += f"_mpi{nproc}"
        mpi_args = ["-mpi", str(nproc)]
    run_dir = os.path.join(VERIF, EXPERIMENT, output_name)
    try:
        proc = subprocess.run(
            ["./experiment_run_no_compile.sh", EXPERIMENT, input_name]
            + mpi_args + ["-build", build, "-output", output_name],
            cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return run_dir, proc.returncode, False
    except subprocess.TimeoutExpired:
        kill_run(output_name)
        return run_dir, -1, True


def probe_layout(map_io, nproc, timeout, keep, shift=0):
    """Probe one layout; return the result dictionary.

    ``map_io`` is the ``W2_mapIO`` written to ``data.exch2``. With ``shift``
    the cell indices of the probe file are raised by that amount while the
    prediction is left alone: the control, in which the comparison must fail.
    ``problems`` in the result lists every unmet expectation; ``matches`` is
    the number of probes reported where predicted.
    """
    tag = {-1: "m1", 0: "0", 1: "1"}[map_io] + ("_shift" if shift else "")
    input_name = PREFIX + "map" + tag
    exp_dir = os.path.join(VERIF, EXPERIMENT)
    input_dir = os.path.join(exp_dir, input_name)
    shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir)
    result = {"map_io": map_io, "shift": shift, "problems": [], "probes": 0,
              "reported": 0, "matches": 0, "kinds": {}}
    problems = result["problems"]
    run_dir = None
    try:
        for name in ("data.pkg", "data.exf"):
            shutil.copyfile(os.path.join(exp_dir, BASE_INPUT, name),
                            os.path.join(input_dir, name))
        with open(os.path.join(exp_dir, BASE_INPUT, "prepare_run")) as fh:
            text = fh.read().replace("../" + BASE_INPUT, "../" + input_name)
        prep = os.path.join(input_dir, "prepare_run")
        with open(prep, "w") as fh:
            fh.write(text)
        os.chmod(prep, os.stat(prep).st_mode | stat.S_IXUSR | stat.S_IXGRP
                 | stat.S_IXOTH)
        with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
            fh.write(DATA_RNF)
        with open(os.path.join(input_dir, "data.exch2"), "w") as fh:
            fh.write(DATA_EXCH2.format(map_io))

        # 1. no probe file yet: the model writes the topology and stops
        run_dir, _, timed_out = run_model(input_name, nproc, timeout)
        errors = read_file(run_dir, "STDERR.0000") or ""
        if timed_out or "RNF_INIT_FIXED: RNF: opening the file failed" not in errors:
            problems.append("the run without a probe file to stop at the "
                            "opening of the file")
            return result
        topo = read_topology(run_dir, nproc)
        result["map"] = topo["map"]
        bad = rule_matches_map(topo, map_io)
        if bad:
            problems.append(f"the layout rule to match exch2's map (off for: {bad})")
            return result
        cells = probe_cells(topo, message_cap())
        expected = {}
        for tile, i, j in cells:
            rank, bi, bj = topo["owner"][tile]
            expected[(predict(topo, map_io, tile, i, j), rank, i, j, bi, bj)] = \
                (tile, i, j)
        result["probes"] = len(expected)
        if len({key[0] for key in expected}) != len(cells):
            problems.append("distinct cell indices for distinct probe cells")
            return result

        # 2. the probe file, with the indices shifted in the control
        total = topo["map"][0] * topo["map"][1]
        in_file = {key[0]: (key[0] + shift) % total for key in expected}
        write_probe(os.path.join(input_dir, "probe.nc"),
                    sorted(in_file.values()), topo["map"])
        run_dir, run_exit, timed_out = run_model(input_name, nproc, timeout)
        found = reports(run_dir, nproc)
        result["reported"] = len(found)
        for kind in found.values():
            result["kinds"][kind] = result["kinds"].get(kind, 0) + 1
        # A report counts as a match when the model placed the index of the
        # file on the cell predicted for the probe. In the control the file
        # holds index + shift for each probe, so a correct model matches
        # nowhere.
        back = {((key[0] - shift) % total,) + key[1:] for key in found}
        result["matches"] = len(back & set(expected))
        logs = "\n".join(filter(None, (
            read_file(run_dir, n) for n in ("output.txt", "mpirun.log"))))
        if timed_out:
            problems.append("the run to finish (it timed out: a process hangs)")
        if "Execution ended Normally" in logs or run_exit == 0:
            problems.append("the run to stop at the refused targets")
        if shift:
            if result["matches"]:
                problems.append(f"no shifted index on the cell predicted for "
                                f"the unshifted one (found {result['matches']})")
            if 2 * len(found) < len(expected):
                problems.append(f"reports for at least half of the "
                                f"{len(expected)} probes (found {len(found)}); "
                                f"the control would be empty")
            return result
        missing = sorted(set(expected) - set(found))
        extra = sorted(set(found) - set(expected))
        if missing or extra:
            problems.append(
                f"reports equal to the prediction ({len(missing)} missing, "
                f"{len(extra)} unexpected; first missing "
                f"(cell, process, i, j, bi, bj): {missing[:3]}; first "
                f"unexpected: {extra[:3]})")
        depth = bathymetry()
        wrong = sorted(key for key, kind in found.items()
                       if (kind == "land") != (depth[key[0]] >= 0.0))
        result["land"] = sum(1 for key in found if depth[key[0]] >= 0.0)
        if wrong:
            problems.append(
                f"'on land' exactly where the bathymetry file is land at the "
                f"cell index ({len(wrong)} differ; first: {wrong[:3]})")
        processes = max(nproc, 1)
        count = f"{len(expected):8d} refused target(s) on all processes"
        for rank in range(processes):
            if count not in (read_file(run_dir, f"STDERR.{rank:04d}") or ""):
                problems.append(f"STDERR.{rank:04d}: {count.strip()}")
        stop_file = "mpirun.log" if nproc else "output.txt"
        stops = (read_file(run_dir, stop_file) or "").count(
            "ABNORMAL END: S/R RNF_INIT_FIXED")
        if stops != processes:
            problems.append(f"{stop_file}: {processes} STOP line(s) of "
                            f"RNF_INIT_FIXED (found {stops})")
        return result
    except ValueError as err:
        problems.append(str(err))
        result["unusable"] = True
        return result
    finally:
        shutil.rmtree(input_dir, ignore_errors=True)
        if run_dir and not keep:
            shutil.rmtree(run_dir, ignore_errors=True)


def main(argv=None):
    """Probe the selected layouts and the control; return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mpi", type=int, default=4, metavar="N",
                        help="number of MPI processes, with build_esx_mpiN "
                             "(default 4; 0: the single-process binary)")
    parser.add_argument("--map", type=int, action="append", default=[],
                        choices=(-1, 0, 1), metavar="M",
                        help="W2_mapIO to probe (repeatable; default all)")
    parser.add_argument("--keep", action="store_true",
                        help="keep the run directories")
    parser.add_argument("--json", action="store_true",
                        help="print the full results as JSON")
    parser.add_argument("--timeout", type=float, default=600.0, metavar="S",
                        help="seconds after which a run counts as hanging")
    args = parser.parse_args(argv)

    build = BUILD + (f"_mpi{args.mpi}" if args.mpi else "")
    binary = os.path.join(VERIF, EXPERIMENT, build, "mitgcmuv")
    if not os.path.isfile(binary):
        mpi = f" -mpi {args.mpi}" if args.mpi else ""
        print(f"missing {binary}: run tests/mitgcm_oracle.sh {EXPERIMENT} "
              f"input.seaice{mpi}", file=sys.stderr)
        return 2
    results = [probe_layout(m, args.mpi, args.timeout, args.keep)
               for m in (args.map or [-1, 0, 1])]
    results.append(probe_layout(-1, args.mpi, args.timeout, args.keep, shift=1))
    for res in results:
        what = (f"control, W2_mapIO = {res['map_io']}, indices shifted by "
                f"{res['shift']}" if res["shift"]
                else f"W2_mapIO = {res['map_io']:2d}")
        verdict = "FAIL" if res["problems"] else "PASS"
        print(f"{verdict} {what}: map {res.get('map')}, {res['probes']} probes, "
              f"{res['reported']} reported, {res['matches']} where predicted, "
              f"kinds {res['kinds']}"
              + (f", land in the bathymetry file at {res['land']}"
                 if "land" in res else ""))
        for msg in res["problems"]:
            print(f"     missing: {msg}")
    if args.json:
        print(json.dumps(results, indent=1))
    failed = [r for r in results if r["problems"]]
    print(f"{len(results) - len(failed)} of {len(results)} probe runs passed")
    if any(r.get("unusable") for r in results):
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
