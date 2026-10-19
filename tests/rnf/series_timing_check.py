#!/usr/bin/env python
"""Flux, temperature, salinity and tracer follow one timing (RUNOFF-029).

**The question.** ``RNF_LOAD_AT`` reads the two records that
``RNF_GETREC`` brackets. It applies one weight to every source series:
the flux, the temperature (with its validity flag), the salinity and
each tracer. ``tests/rnf/timing_field_check.py`` shows that the flux
follows the dense pkg/exf run in every time mode. It cannot look at the
other series, because the dense runs carry none. This check shows that
the other series use the same records and the same weight. The modes are
``daily`` (fixed period), ``month`` (climatological months), ``month1``
(consecutive months), ``clim`` (fixed-period climatology) and ``yearly``
(one file per year). ``clim_long`` is the long climatology span of
RUNOFF-005. Run it with ``--case clim_long``.

**The oracle is direct, with no dense twin.** No dense file holds a
temperature or a tracer. So the check judges each run against the file
itself. The trace of ``RNF_FIELDS_LOAD`` (``RNF_debugLev = 3``) gives, for
every forcing step, the records ``rec0`` and ``rec1`` and their file
years. It gives the weight ``fac`` of the earlier record too. Python rebuilds the
expected applied fields from the file and the trace. It follows the
order of the Fortran in ``RNF_LOAD_AT`` (``pkg/rnf/rnf_fields_load.F``)::

    F_s = fac*F_s(rec0) + (1-fac)*F_s(rec1).
    X_s = fac*X_s(rec0) + (1-fac)*X_s(rec1).
    valid_s = both records used have a temperature.
    w_e = F_s*frac_e/rA_c.
    RNFvflx_c = sum_e w_e.
    mflxT = rho*sum_e w_e*valid_s.
    mXT = rho*sum_e w_e*valid_s*T_s.
    RNFtemp_c = mXT/mflxT where mflxT > 0, else 0.
    RNFsaln_c = (rho*sum_e w_e*S_s)/(rho*RNFvflx_c) where that is > 0.
    RNFtf01_c = rho*sum_e w_e*C_s.

Here ``F`` is the flux in m^3/s and ``X`` stands for ``T``, ``S`` or
``C``. The index ``s`` is the source, and ``e`` is a target entry. It
feeds the cell ``c`` from the source ``s`` with the fraction ``frac_e``.

Here ``rho`` is ``rhoConstFresh`` from the ``output.txt`` of the run. A
record with weight 0 is not used. With ``fac`` = 1 only ``rec0`` counts,
and with ``fac`` = 0 only ``rec1`` counts, as in the Fortran.
``RNFtf01`` is the term of the first runoff tracer that
``RNF_FORCING_SURF_PTR`` adds to ``surfaceForcingPTr``. With
``PTRACERS_EvPrRn = 0`` and ``PTRACERS_ref = 0`` the reference value is 0
and the term equals ``(mC)``. The check refuses a run with a true
``RNF_lagFlds``, because the tracer term then belongs to the step before.
All four dumps are float64 MDS snapshots at every forcing step.

**What each series is.** This check writes one sparse file per mode from
the committed file of the case. The time axis and the attributes stay.
The new file holds seven sources and nine target entries. Sources 0 and 3
feed two cells each, with fractions 0.4/0.6 and 0.25/0.75. Two cells
(``cell[1]`` and ``cell[4]``) get two sources each. Each series is a
distinct, strictly increasing function of the record row ``g``. A file with more than 40 records scales ``g`` by ``40/rows``. This
keeps the values moderate::

    F = F0_s*(1 + 0.3 g).
    T = 2 + 0.5 s + 1.5 g.
    S = 30 + 0.3 s + 0.7 g.
    C = 1 + 0.1 s + 0.9 g.

A record or weight error then shows in each series on its own. Sources 1
and 5 have no temperature (the fill value, validity flag 0) at the
record rows of ``missing`` for the case. The rows are chosen so that the
run uses them. Source 1 shares a cell with source 0, so the temperature
there is the flux-weighted mean of the valid sources. Source 5 is alone in
its cell, so ``RNFtemp`` there is 0. The check refuses a case in which no
step used a missing record.

**Weight cross-check.** The cell of source 6 has one source. For each
series, that cell gives the weight the series implies:
``(V - V(rec1))/(V(rec0) - V(rec1))``. The check reports the largest
distance of this weight from the traced ``fac`` for each series. So "the
same weight" is a measured number as well as a result of the field
comparison.

**Controls (``--control``).** The check must see each of them.

* ``hold``: ``RNF_holdRecord`` on. The model holds each record over its
  interval and does not interpolate. All four series must fail the
  comparison with the oracle of the interpolating run.
* ``shift``: the same file with the temperature, salinity and tracer
  series shifted by one record against the flux. The temperature,
  salinity and tracer must each fail. The flux comparison must not
  change. This shows that the check sees each series apart.
* ``--mutant-build NAME`` runs a code mutant. In ``RNF_LOAD_AT`` of the
  build ``NAME``, the temperature records have the weights ``1-fac`` and
  ``fac`` in the wrong order. The temperature must fail. The flux,
  salinity and tracer must pass. ``--write-mutant`` writes the code
  directory ``code_rnfser029_mut``. ``--build-mutant`` compiles it as
  ``build_esx_ser029_mut``.

**Mutants of the check itself.** ``--mutate NAME`` (with ``--judge-only``
and ``--keep``) changes the oracle and not the model. It lists the
series that must then fail. ``fac_prev`` uses the trace of the step
before. ``t_invert`` uses ``1-fac`` for the temperature. ``s_late`` takes
the salinity records one later. ``c_hold`` holds the tracer on ``rec0``.
``ignore_valid`` takes the temperature without the validity flag.
``--trace-variant`` changes the trace text of the run. ``lower`` writes
it in lower case. ``nospace`` removes its spaces. ``conflict`` adds a
line with another weight. The check must refuse each variant.

**Tolerance.** ``--rtol 1e-12`` relative to the expected value of each
cell and step. The oracle repeats the Fortran operations in the same
order on the same float64 numbers. So the deviation is round-off, and it
measured exactly 0 on 2026-10-19. The controls differ by 1e-3 or more.
An expected 0 (no runoff, or no valid temperature) must be exactly 0 in
the dump.

**Limits.** The check refuses ``RNF_lagFlds`` true, so the lagged
tracer term is not covered. It covers one tracer. It covers the legacy
surface route (``RNF_applyAsRain`` true) only.

The runs use the ``build_esx_roft`` binaries. A file with a temperature
needs their ``ALLOW_RUNOFTEMP``. The case gets ``usePTRACERS`` and one
passive tracer. Nothing compiles here, except with ``--build-mutant``.
Build the binaries first with ``tendency_term_check.py`` (see
``docs/code_map.md``). For ``--mpi 2`` build the ``_mpi2`` binary too.
The check removes its scratch input and run directories at the end. With
``--keep`` the run directories stay. Exit status: 0 if every case passes
and every control is seen. 1 if not. 2 if a binary is missing or stale.

Usage::

    python tests/rnf/series_timing_check.py [--mpi N] [--case NAME ...]
        [--control] [--mutant-build NAME] [--keep] [--judge-only]
        [--mutate NAME] [--json] [--rtol R] [--timeout S]
"""
import argparse
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (VERIF, add_to_namelist, check_build_fresh,  # noqa: E402,E501
                           read_file, replace_line)
from applied_field_check import (dumps, read_mds, record_trace,  # noqa: E402
                                 set_namelist)
from timing_field_check import CASES as TIMING_CASES  # noqa: E402
from timing_field_check import write_input as timing_write_input  # noqa: E402
from budget_check import data_ptracers, nr_of, run_model  # noqa: E402
from tendency_term_check import (build_if_stale, exf_options,  # noqa: E402
                                 param, write_mods_code)

EXPERIMENT = "lab_sea"
LAB = os.path.join(VERIF, EXPERIMENT)
PREFIX = "input.rnfser_"
#: ALLOW_RUNOFTEMP builds: a file with a temperature needs it.
BUILD = "build_esx_roft"
MUTANT_BUILD = "build_esx_ser029_mut"
MUTANT_CODE = "code_rnfser029_mut"
SERIES_FILE = "runoff_series"
TRACER = "serc"
#: Diagnostic stream of each series, and the diagnostic it dumps. No
#: stream name is the beginning of another one.
STREAMS = (("flux", "serV", "RNFvflx "), ("temp", "serT", "RNFtemp "),
           ("salt", "serS", "RNFsaln "), ("trc", "serC", "RNFtf01 "))
SERIES = ("flux", "temp", "salt", "trc")
RTOL = 1.0e-12
#: Series values (see the module docstring).
F0, F_SLOPE = 2000.0, 0.3
T0, T_SLOPE = 2.0, 1.5
S0, S_SLOPE = 30.0, 0.7
C0, C_SLOPE = 1.0, 0.9
FILL = -9999.0
#: The target entries by source: (source, cell-of-source, fraction).
#: ``cell-of-source`` indexes the cell list of the source file.
ENTRIES = ((0, 0, 0.4), (0, 1, 0.6), (1, 1, 1.0), (2, 2, 1.0),
           (3, 3, 0.25), (3, 4, 0.75), (4, 4, 1.0), (5, 5, 1.0),
           (6, 6, 1.0))
#: The sources that lack a temperature at the ``missing`` rows.
MISSING_SOURCES = (1, 5)
#: The single-source cell used for the implied weight (cell-of-source).
CLEAN_CELL = 6

#: The cases. ``missing`` are the rows of the concatenated series at
#: which sources 1 and 5 lack a temperature; ``mpi`` is True for the cases
#: that also run on 2 processes. Values were chosen from the traces of
#: the unmodified runs and the check refuses a run that does not use
#: them.
CASES = (
    {"name": "daily", "mode": "daily", "missing": (6, 7), "mpi": True},
    {"name": "month", "mode": "month", "missing": (1,), "mpi": False},
    {"name": "month1", "mode": "month1", "missing": (2,), "mpi": False},
    {"name": "clim", "mode": "clim", "missing": (0,), "mpi": False},
    {"name": "yearly", "mode": "yearly", "missing": (360, 361), "mpi": True},
    {"name": "clim_long", "mode": "clim", "missing": (0,), "mpi": False,
     "optional": True},
)

#: What each mutant of the check must do: the series that must fail.
MUTATIONS = {
    "fac_prev": SERIES,
    "t_invert": ("temp",),
    "s_late": ("salt",),
    "c_hold": ("trc",),
    "ignore_valid": ("temp",),
}
TRACE_VARIANTS = ("lower", "nospace", "conflict")


def source_files(mode):
    """Return ``[(year or None, path)]`` of the case's committed sparse file(s)."""
    base = os.path.join(LAB, "input.rnof_" + mode)
    names = sorted(n for n in os.listdir(base)
                   if re.match(r"runoff_sparse(_\d{4})?\.nc$", n))
    out = []
    for name in names:
        match = re.search(r"_(\d{4})\.nc$", name)
        out.append((int(match.group(1)) if match else None,
                    os.path.join(base, name)))
    return out


def read_table(path):
    """Return the source file's cells, areas, lon, lat and attributes."""
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(path) as ds:
        ds.set_auto_maskandscale(False)
        cells = np.asarray(ds["target_cell"][:])
        sources = np.asarray(ds["target_source"][:])
        order = [int(c) for _, c in sorted(zip(sources, cells))]
        info = {}
        for k, cell in enumerate(cells):
            info[int(cell)] = {
                name: float(ds[name][k]) for name in
                ("target_cell_area", "target_lon", "target_lat")
                if name in ds.variables}
        return {"cells": order, "info": info,
                "nsrc": len(ds.dimensions["source"]),
                "nx": int(ds.getncattr("mitgcm_grid_nx")),
                "ny": int(ds.getncattr("mitgcm_grid_ny"))}


def entry_table(table):
    """Return the target entries ``(source, cell, fraction)`` of this check."""
    if table["nsrc"] != 7 or len(table["cells"]) != 7:
        raise ValueError("the source file has %d sources, 7 expected"
                         % table["nsrc"])
    return [(s, table["cells"][c], f) for s, c, f in ENTRIES]


def make_series(rows, nsrc, missing, shift=False):
    """Return the four series of ``rows`` records, as dictionaries of arrays.

    ``shift`` moves the temperature (with its validity), the salinity and
    the tracer one record forward relative to the flux (the last record
    stays).
    """
    import numpy as np
    scale = 1.0 if rows <= 40 else 40.0 / rows
    g = np.arange(rows, dtype=np.float64)[:, None] * scale
    s = np.arange(nsrc, dtype=np.float64)[None, :]
    flux = F0 * (1.0 + 0.1 * s) * (1.0 + F_SLOPE * g)
    temp = T0 + 0.5 * s + T_SLOPE * g
    salt = S0 + 0.3 * s + S_SLOPE * g
    trc = C0 + 0.1 * s + C_SLOPE * g
    valid = np.ones((rows, nsrc))
    for src in MISSING_SOURCES:
        for row in missing:
            valid[row, src] = 0.0
    out = {"flux": flux, "temp": temp, "salt": salt, "trc": trc,
           "valid": valid}
    if shift:
        idx = np.minimum(np.arange(rows) + 1, rows - 1)
        for name in ("temp", "salt", "trc", "valid"):
            out[name] = out[name][idx]
    return out


def write_sparse(path, source, entries, table, series_rows, year_rows):
    """Write one sparse file, from ``source`` with this check's table and series.

    ``series_rows`` is the dictionary of full-length series and
    ``year_rows`` the ``slice`` of it that belongs to this file.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(source) as src, netCDF4.Dataset(path, "w") as ds:
        src.set_auto_maskandscale(False)
        ds.set_auto_maskandscale(False)
        for att in src.ncattrs():
            ds.setncattr(att, src.getncattr(att))
        ds.setncattr("title", "sparse runoff with four timed series for "
                              "tests/rnf/series_timing_check.py")
        nrec = len(src.dimensions["time"])
        nsrc = len(src.dimensions["source"])
        ds.createDimension("time", nrec)
        ds.createDimension("source", nsrc)
        ds.createDimension("target", len(entries))
        ds.createDimension("id_strlen", len(src.dimensions["id_strlen"]))
        if "nv" in src.dimensions:
            ds.createDimension("nv", len(src.dimensions["nv"]))
        for name in ("time", "time_bnds", "source_id"):
            if name not in src.variables:
                continue
            old = src[name]
            new = ds.createVariable(name, old.dtype, old.dimensions)
            for att in old.ncattrs():
                new.setncattr(att, old.getncattr(att))
            new[:] = old[:]
        ds.createVariable("target_source", "i4", ("target",))[:] = \
            np.array([e[0] for e in entries], dtype=np.int32)
        ds.createVariable("target_cell", "i4", ("target",))[:] = \
            np.array([e[1] for e in entries], dtype=np.int32)
        out = ds.createVariable("target_fraction", "f8", ("target",))
        out.units = "1"
        out[:] = np.array([e[2] for e in entries])
        for name, units in (("target_cell_area", "m2"),
                            ("target_lon", "degrees_east"),
                            ("target_lat", "degrees_north")):
            if all(name in table["info"][e[1]] for e in entries):
                out = ds.createVariable(name, "f8", ("target",))
                out.units = units
                out[:] = np.array([table["info"][e[1]][name]
                                   for e in entries])
        part = {k: v[year_rows] for k, v in series_rows.items()}
        out = ds.createVariable("runoff_flux", "f8", ("time", "source"))
        out.units = "m3 s-1"
        out[:] = part["flux"]
        out = ds.createVariable("runoff_temperature", "f8",
                                ("time", "source"), fill_value=FILL)
        out.units = "degC"
        out[:] = np.where(part["valid"] > 0.0, part["temp"], FILL)
        out = ds.createVariable("runoff_salinity", "f8", ("time", "source"))
        out.units = "g kg-1"
        out[:] = part["salt"]
        out = ds.createVariable("runoff_ptracer_" + TRACER, "f8",
                                ("time", "source"))
        out.units = "1"
        out[:] = part["trc"]


def diagnostics_text(delta):
    """Return ``data.diagnostics``: one float64 snapshot stream per series."""
    lines = ["# Series-timing oracle of tests/rnf/series_timing_check.py:",
             "# one global float64 snapshot per time step and per series.",
             " &DIAGNOSTICS_LIST", "  diag_mnc = .FALSE.,"]
    for n, (_, stream, diag) in enumerate(STREAMS, start=1):
        lines += [f"  fields(1,{n}) = '{diag.strip():<8}',",
                  f"  fileName({n}) = '{stream}',",
                  f"  frequency({n}) = -{delta!r},",
                  f"  fileFlags({n}) = 'D       ',"]
    lines += [" &", "", " &DIAG_STATIS_PARMS", " &", ""]
    return "\n".join(lines)


def build_layout(case):
    """Return the facts of the case: files, years, rows, entries, table."""
    files = source_files(case["mode"])
    if not files:
        raise ValueError("no sparse file in input.rnof_" + case["mode"])
    table = read_table(files[0][1])
    import netCDF4
    sizes = []
    for _, path in files:
        with netCDF4.Dataset(path) as ds:
            sizes.append(len(ds.dimensions["time"]))
    offsets = [sum(sizes[:i]) for i in range(len(sizes))]
    return {"files": files, "table": table, "entries": entry_table(table),
            "rows": sum(sizes), "sizes": sizes, "offsets": offsets,
            "years": [y for y, _ in files]}


def write_case_input(case, layout, input_dir, kind):
    """Build the scratch input of a run; return ``(deltaT, startTime)``.

    ``kind`` is ``"nominal"``, ``"hold"`` or ``"shift"``. The input is
    that of ``timing_field_check.write_input`` for the sparse case of the
    mode, then with this check's diagnostics, the sparse file(s), the
    passive tracer and ``data.rnf`` pointing to the new file.
    """
    timing_case = next((c for c in TIMING_CASES
                        if c["name"] == case["name"]), {"name": case["name"]})
    source = os.path.join(LAB, "input.rnof_sp_" + case["mode"])
    delta, begin = timing_write_input(timing_case, source, input_dir,
                                      hold=(kind == "hold"))
    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(diagnostics_text(delta))
    series = make_series(layout["rows"], layout["table"]["nsrc"],
                         case["missing"], shift=(kind == "shift"))
    for k, (year, path) in enumerate(layout["files"]):
        name = SERIES_FILE + (("_%d" % year) if year else "") + ".nc"
        rows = slice(layout["offsets"][k],
                     layout["offsets"][k] + layout["sizes"][k])
        write_sparse(os.path.join(input_dir, name), path, layout["entries"],
                     layout["table"], series, rows)
    with open(os.path.join(input_dir, "data.rnf")) as fh:
        text = fh.read()
    text = replace_line(text, "RNF_file",
                        "  RNF_file = '%s.nc'," % SERIES_FILE)
    with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
        fh.write(text)
    with open(os.path.join(input_dir, "data")) as fh:
        data = fh.read()
    pkg = read_file(input_dir, "data.pkg")
    line = "  usePTRACERS = .TRUE.,"
    pkg = (replace_line(pkg, "usePTRACERS", line)
           if re.search(r"(?mi)^\s*usePTRACERS\s*=", pkg)
           else add_to_namelist(pkg, "PACKAGES", line))
    with open(os.path.join(input_dir, "data.pkg"), "w") as fh:
        fh.write(pkg)
    iter0 = int(round(begin / delta))
    with open(os.path.join(input_dir, "data.ptracers"), "w") as fh:
        fh.write(data_ptracers({"ptracers": [TRACER],
                                "file_tracers": [TRACER]},
                               iter0, nr_of(data)))
    with open(os.path.join(input_dir, "data.longstep"), "w") as fh:
        fh.write("# Written by tests/rnf/series_timing_check.py: one passive\n"
                 "# tracer step per dynamics step.\n"
                 " &LONGSTEP_PARM01\n  LS_nIter = 1,\n"
                 "  LS_whenToSample = 0,\n &\n")
    prep = os.path.join(input_dir, "prepare_run")
    if os.path.isfile(prep):
        with open(prep) as fh:
            text = fh.read()
        if re.search(r"skipList=", text):
            new = re.sub(r'skipList="([^"]*)"',
                         r'skipList="\1 data.pkg data.ptracers data.longstep"',
                         text)
            with open(prep, "w") as fh:
                fh.write(new)
    return delta, begin


def trace_problems(text, trace, dump_iters):
    """Return what is wrong with the trace of a run, as a list of messages.

    The trace is taken from ``applied_field_check.record_trace``, whose
    expression is exact. A line that mentions the trace but does not match
    it (another case, other spacing) would be dropped silently, so every
    loose match is counted and each of its iterations has to be in the
    parsed trace. Two lines of one iteration are normal (the build at
    initialization and the first step print the same one) but they have
    to be equal.
    """
    out = []
    loose = {int(m.group(1)) for m in re.finditer(
        r"(?i)rnf_fields_load\s*:\s*it\s*=\s*(-?\d+)", text)}
    seen = {}
    for m in re.finditer(
            r"(?i)rnf_fields_load\s*:\s*it\s*=\s*(-?\d+)\s*,\s*rec0\s*="
            r"\s*(-?\d+)\s*,\s*yr0\s*=\s*(-?\d+)\s*,\s*rec1\s*="
            r"\s*(-?\d+)\s*,\s*yr1\s*=\s*(-?\d+)\s*,\s*t\s*=\s*\S+"
            r"\s*,\s*fac\s*=\s*(\S+)", text):
        key = int(m.group(1))
        value = (int(m.group(2)), int(m.group(3)), int(m.group(4)),
                 int(m.group(5)), float(m.group(6)))
        if seen.setdefault(key, value) != value:
            out.append("one trace line per iteration or equal lines; "
                       "iteration %d has two different ones" % key)
            break
    lost = sorted(loose - set(trace))
    if lost:
        out.append("every trace line to be read; %d iterations (first %s) "
                   "are in the log but not in the trace" % (len(lost),
                                                            lost[:3]))
    missing = [i for i in dump_iters if i not in trace]
    if missing:
        out.append("a trace line for every dump; none for %d iterations "
                   "(first %s)" % (len(missing), missing[:3]))
    return out


def expected_fields(layout, series, rec, rho, rac, mutate=None, prev=None):
    """Return the four expected fields of one step, as flat arrays.

    ``rec`` is ``(rec0, yr0, rec1, yr1, fac)`` of the trace. ``mutate`` is
    one name of :data:`MUTATIONS` and changes the oracle on purpose.
    """
    import numpy as np
    rec0, yr0, rec1, yr1, fac = rec
    if mutate == "fac_prev" and prev is not None:
        rec0, yr0, rec1, yr1, fac = prev

    def row(count, year):
        if len(layout["files"]) > 1:
            k = layout["years"].index(year)
        else:
            k = 0
        r = layout["offsets"][k] + count - 1
        if not 0 <= r < layout["offsets"][k] + layout["sizes"][k]:
            raise ValueError("record %d of year %d is outside the file"
                             % (count, year))
        return r

    r0, r1 = row(rec0, yr0), row(rec1, yr1)
    need0, need1 = fac > 0.0, fac < 1.0
    nsrc = layout["table"]["nsrc"]

    def blend(name, w0=None):
        a, b = series[name][r0], series[name][r1]
        f = fac if w0 is None else w0
        if not need1:
            return a.copy()
        if not need0:
            return b.copy()
        return f * a + (1.0 - f) * b

    flux = blend("flux")
    temp = blend("temp", (1.0 - fac) if mutate == "t_invert" else None)
    if mutate == "s_late":
        s0, s1 = min(r0 + 1, layout["rows"] - 1), min(r1 + 1,
                                                       layout["rows"] - 1)
        a, b = series["salt"][s0], series["salt"][s1]
        salt = a.copy() if not need1 else (
            b.copy() if not need0 else fac * a + (1.0 - fac) * b)
    else:
        salt = blend("salt")
    if mutate == "c_hold":
        trc = series["trc"][r0].copy()
    else:
        trc = blend("trc")
    valid = np.ones(nsrc, dtype=bool)
    if mutate != "ignore_valid":
        if need0:
            valid &= series["valid"][r0] > 0.0
        if need1:
            valid &= series["valid"][r1] > 0.0
    ncell = rac.size
    vflx = np.zeros(ncell)
    mfT = np.zeros(ncell)
    mXT = np.zeros(ncell)
    mXS = np.zeros(ncell)
    mXC = np.zeros(ncell)
    for s, c, f in layout["entries"]:
        w = flux[s] * f / rac[c]
        vflx[c] += w
        mfT[c] += w * float(valid[s])
        mXT[c] += w * float(valid[s]) * temp[s]
        mXS[c] += w * salt[s]
        mXC[c] += w * trc[s]
    mflx = rho * vflx
    mfT, mXT, mXS, mXC = rho * mfT, rho * mXT, rho * mXS, rho * mXC
    out_t = np.zeros(ncell)
    out_s = np.zeros(ncell)
    pos = mfT > 0.0
    out_t[pos] = mXT[pos] / mfT[pos]
    pos = mflx > 0.0
    out_s[pos] = mXS[pos] / mflx[pos]
    return {"flux": vflx, "temp": out_t, "salt": out_s, "trc": mXC}, \
        {"r0": r0, "r1": r1, "valid": valid, "flux": flux, "temp": temp,
         "salt": salt, "trc": trc, "mflx": mflx}


def compare(got, want):
    """Return ``(max relative deviation, cells that should be 0 and are not)``."""
    import numpy as np
    zero = want == 0.0
    bad = int(np.count_nonzero(got[zero] != 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(got[~zero] - want[~zero]) / np.abs(want[~zero])
    rel = np.where(np.isfinite(rel), rel, np.inf)
    worst = float(rel.max()) if rel.size else 0.0
    return worst, bad


def judge_run(case, layout, run_dir, trace_from=None, series_from=None,
              mutate=None):
    """Compare the four dumped series of a run with the oracle.

    The oracle uses ``trace_from`` (the trace of another run, for a
    control) and ``series_from`` (the unshifted series, for the shift
    control); by default the run's own. Returns the measurements.
    """
    import numpy as np
    out = {"problems": [], "series": {}}
    log = read_file(run_dir, "output.txt") or ""
    rac, shape = read_mds(run_dir, "RAC")
    iters = {}
    for name, stream, _ in STREAMS:
        iters[name], stray = dumps(run_dir, stream)
        if stray:
            out["problems"].append("only dumps of the stream %s: %s"
                                   % (stream, stray[:3]))
            return out
    if not (iters["flux"] == iters["temp"] == iters["salt"] == iters["trc"]):
        out["problems"].append("the four streams to dump the same iterations")
        return out
    dump_iters = [int(i) for i in iters["flux"]]
    out["dumps"] = len(dump_iters)
    own = record_trace(run_dir)
    trace = trace_from if trace_from is not None else own
    out["problems"] += trace_problems(log, own, dump_iters)
    if trace_from is not None:
        out["problems"] += trace_problems("", trace, dump_iters)
    try:
        rho = param(log, "rhoConstFresh")
    except ValueError as err:
        out["problems"].append(str(err))
        return out
    lag = re.search(r"(?m)^\(PID\.TID \S+\) RNF_lagFlds =[^\n]*\n"
                    r"\(PID\.TID \S+\)\s+([TF])\s*$", log)
    if not lag or lag.group(1) == "T":
        out["problems"].append("RNF_lagFlds = F in the log (the tracer term "
                               "belongs to the step before otherwise)")
        return out
    if out["problems"]:
        return out
    series = series_from if series_from is not None else make_series(
        layout["rows"], layout["table"]["nsrc"], case["missing"])
    worst = {n: {"max_rel": 0.0, "bad_zero": 0, "at": None,
                 "values": set()} for n in SERIES}
    used_missing = 0
    zero_temp = 0
    lone = layout["entries"][MISSING_SOURCES[1] + 2][1]
    clean, clean_frac = layout["entries"][-1][1:]
    implied = {n: 0.0 for n in SERIES}
    implied_n = 0
    prev = None
    for it in dump_iters:
        step_rec = trace[it]
        fields, info = expected_fields(layout, series, step_rec, rho, rac,
                                       mutate, prev)
        prev = step_rec
        fac = step_rec[4]
        if fields["flux"][lone] > 0.0 and fields["temp"][lone] == 0.0:
            zero_temp += 1
        for name, stream, _ in STREAMS:
            dump, d_shape = read_mds(run_dir, stream, "%010d" % it)
            if d_shape != shape:
                raise ValueError("%s.%010d has shape %s, RAC.data has %s"
                                 % (stream, it, d_shape, shape))
            rel, bad = compare(dump, fields[name])
            slot = worst[name]
            slot["bad_zero"] += bad
            if rel > slot["max_rel"]:
                slot["max_rel"] = rel
                slot["at"] = {"iteration": it, "rec": list(step_rec)}
            slot["values"].add(round(float(dump.max()), 15))
            if name == "flux":
                got_flux = dump
            elif name == "temp":
                got_temp = dump
            elif name == "salt":
                got_salt = dump
            else:
                got_trc = dump
        r0, r1 = info["r0"], info["r1"]
        need = 0.0 < fac < 1.0
        for r, used in ((r0, fac > 0.0), (r1, fac < 1.0)):
            if used and any(series["valid"][r][m] <= 0.0
                            for m in MISSING_SOURCES):
                used_missing += 1
                break
        # implied weight on the single-source cell of the last source
        if need:
            srcs = {"flux": got_flux[clean] * rac[clean] / clean_frac,
                    "temp": got_temp[clean], "salt": got_salt[clean],
                    "trc": got_trc[clean] / (rho * got_flux[clean])
                    if got_flux[clean] != 0.0 else float("nan")}
            for name in SERIES:
                a = series[name][r0][CLEAN_CELL]
                b = series[name][r1][CLEAN_CELL]
                if a != b and np.isfinite(srcs[name]):
                    implied[name] = max(
                        implied[name],
                        abs((srcs[name] - b) / (a - b) - fac))
            implied_n += 1
    for name in SERIES:
        slot = worst[name]
        slot["distinct"] = len(slot.pop("values"))
    out["series"] = worst
    out["used_missing_steps"] = used_missing
    out["no_temperature_cell_steps"] = zero_temp
    out["implied_weight_dev"] = implied
    out["implied_steps"] = implied_n
    out["rho"] = rho
    return out


def verdict_nominal(result, rtol):
    """Return the problems of a nominal run's measurements."""
    problems = list(result["problems"])
    for name in SERIES:
        slot = result["series"].get(name)
        if slot is None:
            continue
        if slot["max_rel"] > rtol:
            problems.append("%s to equal the oracle to %g relative (found "
                            "%.3e at %s)" % (name, rtol, slot["max_rel"],
                                             slot["at"]))
        if slot["bad_zero"]:
            problems.append("%s to be exactly 0 where the oracle is 0 (%d "
                            "cells are not)" % (name, slot["bad_zero"]))
        if slot["distinct"] < 5:
            problems.append("at least 5 distinct %s fields over the run "
                            "(found %d): a constant series says nothing "
                            "about timing" % (name, slot["distinct"]))
    if result.get("no_temperature_cell_steps", 1) == 0:
        problems.append("a step with runoff and no valid temperature in a "
                        "cell: the zero rule of RNFtemp is not tested")
    if result.get("used_missing_steps", 1) == 0:
        problems.append("a step that used a record without temperature: "
                        "the validity flag is not tested by this run")
    return problems


def judge_control(result, rtol, must_fail, must_pass):
    """Return the problems of a control: a series that should have failed."""
    problems = list(result["problems"])
    for name in must_fail:
        slot = result["series"].get(name)
        if slot is not None and not (slot["max_rel"] > rtol
                                     or slot["bad_zero"]):
            problems.append("the comparison of %s to see the control (max "
                            "relative deviation %.3e, not above %g)"
                            % (name, slot["max_rel"], rtol))
    for name in must_pass:
        slot = result["series"].get(name)
        if slot is not None and (slot["max_rel"] > rtol or slot["bad_zero"]):
            problems.append("the comparison of %s not to change (max "
                            "relative deviation %.3e)" % (name,
                                                          slot["max_rel"]))
    return problems


def run_one(case, layout, nproc, kind, timeout, build, keep, tag=""):
    """Write one scratch input, run it; return ``(run_dir, problems)``."""
    name = PREFIX + case["name"] + (("_mpi%d" % nproc) if nproc else "") \
        + "_" + kind + tag
    path = os.path.join(LAB, name)
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    try:
        write_case_input(case, layout, path, "nominal" if kind in (
            "mutant", "nominal") else kind)
        run_dir, code, timed = run_model(EXPERIMENT, name, nproc, timeout,
                                         build)
    finally:
        shutil.rmtree(path, ignore_errors=True)
    logs = "\n".join(filter(None, (read_file(run_dir, n)
                                   for n in ("output.txt", "mpirun.log"))))
    if timed:
        return run_dir, ["%s to finish (it timed out)" % name]
    if code != 0 or "Execution ended Normally" not in logs:
        return run_dir, ["%s to end normally (exit %s)" % (name, code)]
    return run_dir, []


def run_dir_of(case, nproc, kind, tag=""):
    """Return the run directory ``run_one`` makes (for ``--judge-only``)."""
    name = "output_esx_" + PREFIX + case["name"] + (
        ("_mpi%d" % nproc) if nproc else "") + "_" + kind + tag
    if nproc:
        name += "_mpi%d" % nproc
    return os.path.join(LAB, name)


def apply_trace_variant(run_dir, variant):
    """Return the log text of ``run_dir`` altered by a ``--trace-variant``."""
    text = read_file(run_dir, "output.txt") or ""
    lines = text.splitlines()
    out = []
    done = False
    for line in lines:
        if "RNF_FIELDS_LOAD: it=" in line:
            if variant == "lower":
                line = line.lower()
            elif variant == "nospace":
                line = re.sub(r"\s+", "", line)
            elif variant == "conflict" and not done:
                out.append(line)
                line = re.sub(r"fac=\s*\S+", "fac= 5.0000000000000000E-01",
                              line)
                done = True
        out.append(line)
    return "\n".join(out) + "\n"


def write_mutant_code():
    """Write the code directory of the temperature-weight mutant; return it."""
    path = os.path.join(LAB, "..", "..", "pkg", "rnf", "rnf_fields_load.F")
    with open(path) as fh:
        text = fh.read()
    old = ("              tVal = fac             *RNF_bufTemp(k,bi,bj,1)\n"
           "     &           + ( 1. _d 0 - fac )*RNF_bufTemp(k,bi,bj,2)\n")
    new = ("              tVal = ( 1. _d 0 - fac )*RNF_bufTemp(k,bi,bj,1)\n"
           "     &           + fac             *RNF_bufTemp(k,bi,bj,2)\n")
    if text.count(old) != 1:
        raise ValueError("the temperature blend occurs %d times in %s"
                         % (text.count(old), path))
    return write_mods_code(MUTANT_CODE, {"EXF_OPTIONS.h": exf_options(True),
                                         "rnf_fields_load.F":
                                         text.replace(old, new)})


def check_case(case, nproc, args):
    """Run and judge one case on ``nproc`` processes; return the result."""
    result = {"case": case["name"], "processes": nproc, "problems": [],
              "controls": {}}
    keep = args.keep
    try:
        layout = build_layout(case)
        build = BUILD
        if args.judge_only:
            nominal_dir = run_dir_of(case, nproc, "nominal")
        else:
            nominal_dir, problems = run_one(case, layout, nproc, "nominal",
                                            args.timeout, build, keep)
            if problems:
                result["problems"] += problems
                return result
        measured = judge_run(case, layout, nominal_dir, mutate=args.mutate)
        result.update(measured)
        if args.mutate:
            fails = {n for n in SERIES
                     if measured["series"][n]["max_rel"] > args.rtol
                     or measured["series"][n]["bad_zero"]}
            want = set(MUTATIONS[args.mutate])
            result["mutate"] = {"name": args.mutate, "failed": sorted(fails),
                                "expected": sorted(want)}
            if fails != want:
                result["problems"].append(
                    "the mutant %s of the oracle to fail exactly %s (failed "
                    "%s)" % (args.mutate, sorted(want), sorted(fails)))
            return result
        if args.trace_variant:
            text = apply_trace_variant(nominal_dir, args.trace_variant)
            tmp = os.path.join(LAB, "output_esx_" + PREFIX + "variant")
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(nominal_dir, tmp, symlinks=True)
            with open(os.path.join(tmp, "output.txt"), "w") as fh:
                fh.write(text)
            try:
                got = judge_run(case, layout, tmp)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            seen = verdict_nominal(got, args.rtol)
            result["trace_variant"] = {"name": args.trace_variant,
                                       "problems": seen[:2]}
            if not seen:
                result["problems"].append(
                    "the altered trace %s to be refused" % args.trace_variant)
            return result
        result["problems"] = verdict_nominal(result, args.rtol)
        trace = record_trace(nominal_dir)
        if args.control:
            plan = (("hold", SERIES, ()),
                    ("shift", ("temp", "salt", "trc"), ("flux",)))
            for kind, must_fail, must_pass in plan:
                if args.judge_only:
                    run_dir = run_dir_of(case, nproc, kind)
                else:
                    run_dir, problems = run_one(case, layout, nproc, kind,
                                                args.timeout, build, keep)
                    if problems:
                        result["controls"][kind] = {"problems": problems}
                        continue
                shifted = None
                got = judge_run(case, layout, run_dir, trace_from=trace,
                                series_from=None)
                result["controls"][kind] = {
                    "series": got["series"],
                    "problems": judge_control(got, args.rtol, must_fail,
                                              must_pass)}
        if args.mutant_build:
            if args.judge_only:
                run_dir = run_dir_of(case, nproc, "mutant")
            else:
                run_dir, problems = run_one(case, layout, nproc, "mutant",
                                            args.timeout, args.mutant_build,
                                            keep)
                if problems:
                    result["controls"]["mutant"] = {"problems": problems}
                    return result
            got = judge_run(case, layout, run_dir)
            result["controls"]["mutant"] = {
                "series": got["series"],
                "problems": judge_control(got, args.rtol, ("temp",),
                                          ("flux", "salt", "trc"))}
        return result
    except (ValueError, OSError, KeyError) as err:
        result["problems"].append(str(err))
        result["unusable"] = True
        return result
    finally:
        if not keep and not args.judge_only:
            for kind in ("nominal", "hold", "shift", "mutant"):
                shutil.rmtree(run_dir_of(case, nproc, kind),
                              ignore_errors=True)


def report(res):
    """Print the lines of one case result."""
    where = "%s on %s" % (res["case"], "%d processes" % res["processes"]
                          if res["processes"] else "1 process")
    problems = res["problems"]
    print("%s %s: %d dumps%s" % ("FAIL" if problems else "PASS", where,
                                 res.get("dumps", 0),
                                 ", steps with a missing temperature used: "
                                 "%d (%d with a cell lacking temperature)"
                                 % (res["used_missing_steps"],
                                    res["no_temperature_cell_steps"])
                                 if "used_missing_steps" in res else ""))
    for name in SERIES:
        slot = res.get("series", {}).get(name)
        if slot:
            print("     %-5s max relative deviation %.3e, %d cells not 0 "
                  "where 0, %d distinct fields, implied weight deviation "
                  "%.3e" % (name, slot["max_rel"], slot["bad_zero"],
                            slot["distinct"],
                            res["implied_weight_dev"][name]))
    for msg in problems:
        print("     missing: %s" % msg)
    for kind, ctl in res.get("controls", {}).items():
        seen = {n: "%.3e" % s["max_rel"]
                for n, s in ctl.get("series", {}).items()}
        print("     control %s: %s %s" % (kind, "SEEN" if not ctl[
            "problems"] else "NOT AS EXPECTED", seen))
        for msg in ctl["problems"]:
            print("          missing: %s" % msg)
    if "mutate" in res:
        print("     mutant of the check %(name)s: failed %(failed)s, "
              "expected %(expected)s" % res["mutate"])
    if "trace_variant" in res:
        print("     trace variant %(name)s refused with: %(problems)s"
              % res["trace_variant"])


def main(argv=None):
    """Check the selected cases and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mpi", type=int, default=0, metavar="N")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--control", action="store_true",
                        help="also run the hold and shift controls")
    parser.add_argument("--mutant-build", metavar="NAME",
                        help="also run the temperature-weight code mutant")
    parser.add_argument("--write-mutant", action="store_true")
    parser.add_argument("--build-mutant", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--judge-only", action="store_true",
                        help="do not run; judge kept run directories")
    parser.add_argument("--mutate", choices=sorted(MUTATIONS))
    parser.add_argument("--trace-variant", choices=TRACE_VARIANTS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=2400.0)
    parser.add_argument("--rtol", type=float, default=RTOL)
    args = parser.parse_args(argv)
    if args.write_mutant or args.build_mutant:
        print(write_mutant_code())
        if args.build_mutant:
            info = build_if_stale(MUTANT_BUILD, write_mutant_code, jobs=4)
            print(info)
            return 0 if info.get("ok") else 2
        return 0
    names = [c["name"] for c in CASES]
    unknown = set(args.case) - set(names)
    if unknown:
        print("unknown case(s): %s" % sorted(unknown), file=sys.stderr)
        return 2
    selected = [c for c in CASES if (c["name"] in args.case if args.case
                                     else not c.get("optional"))]
    if args.mpi:
        selected = [c for c in selected if c["mpi"]]
    build = BUILD + ("_mpi%d" % args.mpi if args.mpi else "")
    binaries = [build] + ([args.mutant_build] if args.mutant_build else [])
    if not args.judge_only:
        for name in binaries:
            binary = os.path.join(LAB, name, "mitgcmuv")
            if not os.path.isfile(binary):
                print("missing %s" % binary, file=sys.stderr)
                return 2
            stale = check_build_fresh(binary, os.path.join(LAB, "code"))
            if stale:
                print(stale, file=sys.stderr)
                return 2
    results = [check_case(c, args.mpi, args) for c in selected]
    for res in results:
        report(res)
    if args.json:
        print(json.dumps(results, indent=1, default=str))
    failed = [r["case"] for r in results if r["problems"] or any(
        c["problems"] for c in r.get("controls", {}).values())]
    print("%d of %d cases passed" % (len(results) - len(failed), len(results)))
    if any(r.get("unusable") for r in results):
        return 2
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
