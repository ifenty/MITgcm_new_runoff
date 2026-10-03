#!/usr/bin/env python
"""Check what pkg/rnf refuses, and that a valid sparse file gives the dense run.

Each case builds a scratch input directory layered on ``lab_sea/input`` (as
``lab_sea/input.rnfchk_<case>``), with ``useRNF=.TRUE.`` in ``data.pkg``, a
``data.rnf`` and, for a refusal case, one deliberate violation. The case is
run with the existing lab_sea binary through ``experiment_run_no_compile.sh``,
the run step that ``tests/mitgcm_oracle.sh`` uses, so nothing is compiled
here. Build the binary first with ``tests/mitgcm_oracle.sh lab_sea input``.

With ``--mpi N`` the cases run on N processes with the binary of
``tests/mitgcm_oracle.sh lab_sea input -mpi N`` (``build_esx_mpiN``).

There are three kinds of case.

* **Configuration refusals** (``RNF_READPARMS``, ``RNF_CHECK``): a setting of
  ``data.exf``, ``data.pkg`` or ``data.rnf`` that the package refuses. They
  name a valid sparse file, ``input.rnof_const/runoff_sparse.nc``, because
  the file is read before ``RNF_CHECK`` runs.
* **File refusals** (``RNF_INIT_FIXED``, ``RNF_NC_READ_FLUX``,
  ``RNF_NC_ATT_REAL``): a copy of that file with one violation, written into
  the scratch directory by ``sparse_file``:

  - table entries: a cell index or a source index out of range, a
    ``target_level`` of 2, a fraction that is negative or not a number, a
    negative fraction hidden in a sum that is still 1;
  - a target on land, a wrong cell area, a fraction sum off by 1e-3;
  - the file as a whole: a grid size mismatch, a missing grid attribute, a
    time sampling other than ``constant``, a missing required variable;
  - the flux: not a number, infinite, above 1e30, equal to a numeric
    ``missing_value`` or to the ``_FillValue`` of a float32 variable, and a
    ``missing_value`` stored as text, which must stop the run and not be
    taken as absent;
  - more sources or more target entries on one tile than ``RNF_nSrcTile`` or
    ``RNF_nTgtTile``.
* **Runs that must end normally**: the positive control (the valid file on
  ``lab_sea/input``; the flux sums that the model prints must equal the sum
  of the file), ``cells_equal_dense`` (the one-source-per-cell file must
  reproduce the dense reference ``results/output.rnof_const.txt``), and
  ``zero_flux_differs`` (the same run with every flux set to zero must NOT
  reproduce it, which shows that the comparison is sensitive to the runoff).

Every process is judged on its own files. A single-process run writes its
standard output and its ``STOP`` line to ``output.txt`` and its error messages
to ``STDERR.0000``. In an MPI run, process ``n`` writes its standard output to
``STDOUT.000n`` and its error messages to ``STDERR.000n``, and the ``STOP``
lines of all processes go to ``mpirun.log``.

A refusal case passes when all of these hold:

* the run finished within ``--timeout`` seconds (a process that waits for
  another one that has stopped would hang);
* the model did not end normally;
* every expected error message is in the error file of every process
  (``stderr``), and every message that only the process owning the tile
  prints is in the error file of at least one process (``stderr_any``);
* every expected standard-output line is in the standard output of every
  process;
* there is exactly one ``STOP`` line of the expected routine per process;
* no forbidden message is in any log.

A refusal detected on one tile only (land, cell area, array bound) must stop
every process. Under ``--mpi`` this is what the ``STOP`` count and the timeout
check: one ``STOP`` line per process, and no hang.

The scratch input and run directories are removed afterwards (``--keep``
leaves the run directories for inspection). Exit status: 0 if every case
passes, 1 if any fails or none ran, 2 if the lab_sea binary is missing or a
``--case`` name is unknown.

Usage::

    python tests/rnf/refusal_check.py [--mpi N] [--keep] [--json]
                                      [--timeout S] [--case NAME ...]
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
# The valid sparse file (four sources, seven targets) and its dense reference.
SPARSE = os.path.join(VERIF, EXPERIMENT, "input.rnof_const", "runoff_sparse.nc")
SPARSE_REL = "../input.rnof_const/runoff_sparse.nc"
CELLS_REL = "../input.rnof_const/runoff_sparse_cells.nc"
DENSE_INPUT = "input.rnof_sp_const"
DENSE_REF = "output.rnof_const.txt"
RNF_SIZE = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "RNF_SIZE.h")

# The process and thread label that MITgcm puts in front of its log lines.
PID_PREFIX = re.compile(r"^\(PID\.TID \d{4}\.\d{4}\)\s?")

DATA_RNF = """# Sparse runoff package parameters
 &RNF_PARM01
  RNF_file = '{0}',
 &
"""

DATA_RNF_BLANK = """# Sparse runoff package parameters
 &RNF_PARM01
 &
"""

# Lines printed only after every configuration check has passed.
PASSED = "RNF_CHECK: configuration checks passed"

# The configuration refusal messages, by the parameter each one names.
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


def size_bound(name):
    """Return the integer bound ``name`` set in ``pkg/rnf/RNF_SIZE.h``."""
    with open(RNF_SIZE) as fh:
        match = re.search(rf"PARAMETER\s*\(\s*{name}\s*=\s*(\d+)\s*\)", fh.read())
    if not match:
        raise ValueError(f"{name} not found in {RNF_SIZE}")
    return int(match.group(1))


def sparse_info():
    """Return what the cases need to know about the valid sparse file.

    The result has ``ids`` (source ids in file order), ``target_source``
    (the source index of each target entry), ``nx``, ``ny``, ``flux_sum``
    (sum of the one flux record, m^3/s), ``wet_cell`` (the cell of the first
    target) and ``land_cell`` (a land cell of the western half of the grid,
    which one process owns in a two-process run). Land is where
    ``input/bathy.labsea1979`` is not negative.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(SPARSE) as ds:
        ids = [str(s) for s in netCDF4.chartostring(ds["source_id"][:])]
        target_source = [int(s) for s in ds["target_source"][:]]
        nx = int(ds.getncattr("mitgcm_grid_nx"))
        ny = int(ds.getncattr("mitgcm_grid_ny"))
        flux_sum = float(np.asarray(ds["runoff_flux"][0], dtype="f8").sum())
        wet_cell = int(ds["target_cell"][0])
    bathy = np.fromfile(os.path.join(VERIF, EXPERIMENT, "input", "bathy.labsea1979"),
                        dtype=">f4").reshape(ny, nx)
    land = [(int(j), int(i)) for j, i in np.argwhere(bathy >= 0.0) if i < nx // 2]
    j, i = land[len(land) // 2]
    return {"ids": ids, "target_source": target_source, "nx": nx, "ny": ny,
            "flux_sum": flux_sum, "wet_cell": wet_cell,
            "land_cell": i + nx * j}


def sparse_file(path, edit=None, skip=(), retype=None, many_sources=0,
                many_targets=0, wet_cell=0):
    """Write a sparse runoff file at ``path``, derived from the valid one.

    Every dimension, variable and attribute of ``SPARSE`` is copied except
    the variables named in ``skip``; then ``edit(ds)`` changes the open copy.
    ``retype`` maps a variable name to ``(dtype, fill value)``: that variable
    is stored with this type and ``_FillValue`` in the copy.

    With ``many_sources`` the file is instead a synthetic one with that many
    sources, each sending all its flux to ``wet_cell``, which puts them all
    on one tile. With ``many_targets`` it is a synthetic file with one source
    and that many target entries, all on ``wet_cell`` with equal fractions.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(SPARSE) as src, netCDF4.Dataset(path, "w") as dst:
        src.set_auto_maskandscale(False)
        dst.set_auto_maskandscale(False)
        dst.setncatts({k: src.getncattr(k) for k in src.ncattrs()})
        if many_sources or many_targets:
            n_src = many_sources or 1
            n_tgt = many_sources or many_targets
            dst.createDimension("time", None)
            dst.createDimension("source", n_src)
            dst.createDimension("target", n_tgt)
            dst.createDimension("id_strlen", 8)
            ids = np.array([list(f"s{k:07d}") for k in range(n_src)], dtype="S1")
            dst.createVariable("time", "f8", ("time",))[:] = [0.0]
            dst["time"].setncatts({k: src["time"].getncattr(k)
                                   for k in src["time"].ncattrs()})
            dst.createVariable("source_id", "S1", ("source", "id_strlen"))[:] = ids
            dst.createVariable("target_source", "i4", ("target",))[:] = \
                np.arange(n_tgt) if many_sources else 0
            dst.createVariable("target_cell", "i4", ("target",))[:] = wet_cell
            frac = dst.createVariable("target_fraction", "f8", ("target",))
            frac[:] = 1.0 if many_sources else 1.0 / n_tgt
            frac.units = "1"
            flux = dst.createVariable("runoff_flux", "f8", ("time", "source"))
            flux[0, :] = 1.0e-3
            flux.units = "m3 s-1"
            return
        for name, dim in src.dimensions.items():
            dst.createDimension(name, None if dim.isunlimited() else len(dim))
        for name, var in src.variables.items():
            if name in skip:
                continue
            atts = {k: var.getncattr(k) for k in var.ncattrs()}
            # a fill value can only be given when the variable is created
            dtype, fill = var.dtype, atts.pop("_FillValue", None)
            if retype and name in retype:
                dtype, fill = retype[name]
            out = dst.createVariable(name, dtype, var.dimensions,
                                     fill_value=fill)
            out.setncatts(atts)
            out[:] = var[:]
        if edit:
            edit(dst)


def cases(data_pkg, data_exf, info=None):
    """Return the test cases as a list of dictionaries.

    ``info`` is the result of ``sparse_info``; without it only the
    configuration cases are returned. Each case has:

    * ``name``;
    * ``files``: file name to content, written into the scratch input
      directory;
    * ``nc`` (optional): file name to the keyword arguments of
      ``sparse_file``, which writes that NetCDF file there;
    * ``copy_from`` (optional): an input directory of lab_sea whose files are
      copied first, so that the case runs on that set-up;
    * ``stderr``: error messages that every process must print;
    * ``stderr_any`` (optional): error messages that at least one process
      must print (the process that owns the tile);
    * ``stdout``: lines that every process must print to its standard output;
    * ``stop``: the text of the ``STOP`` line, expected once per process;
    * ``forbid``: messages that must be in no log;
    * ``normal_end`` (optional): the run must end normally, with no ``STOP``;
    * ``summary`` (optional): parameter name to the value that the parameter
      summary must report;
    * ``flux_sum`` (optional): the value both flux sums printed by
      ``RNF_INIT_VARIA`` must have;
    * ``digits`` (optional): ``(reference file, lowest, highest)`` number of
      matching digits against that reference of lab_sea ``results/``.
    """
    pkg_on = set_package_flags(data_pkg, {"useRNF": ".TRUE."})
    rnf_ok = DATA_RNF.format(SPARSE_REL)
    rnf_bad = DATA_RNF.format("bad.nc")
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
    after_checks = [PASSED]
    stop_check = "ABNORMAL END: S/R RNF_CHECK"
    one_error = "RNF_CHECK: detected  1 fatal error(s)"
    out = [
        {"name": "runofffile",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_ok,
                   "data.exf": exf_file},
         "stderr": [MESSAGES["runofffile"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "runoffconst",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_ok,
                   "data.exf": exf_const},
         "stderr": [MESSAGES["runoffconst"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "exf_outscal_sflux",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_ok,
                   "data.exf": exf_scale},
         "stderr": [MESSAGES["exf_outscal_sflux"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
        {"name": "three_at_once",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_ok,
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
         "files": {"data.pkg": pkg_no_exf, "data.rnf": rnf_ok},
         "stderr": [MESSAGES["useEXF"], one_error],
         "stdout": [], "stop": stop_check, "forbid": after_checks},
    ]
    if info is None:
        return out

    import numpy as np
    ids = info["ids"]
    stop_init = "ABNORMAL END: S/R RNF_INIT_FIXED"
    forbid_file = after_checks + ["RNF_CHECK: #define ALLOW_RNF"]
    one_init = "RNF_INIT_FIXED: detected       1 fatal error(s)"
    bound = size_bound("RNF_nSrcTile")

    def file_case(name, stderr, stderr_any=(), stop=stop_init, **nc_kw):
        return {"name": name,
                "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
                "nc": {"bad.nc": nc_kw},
                "stderr": list(stderr), "stderr_any": list(stderr_any),
                "stdout": [], "stop": stop, "forbid": forbid_file}

    def set_var(name, index, value):
        def edit(ds):
            ds[name][index] = value
        return edit

    def set_att(**atts):
        def edit(ds):
            ds.setncatts(atts)
        return edit

    def scale_var(name, index, factor):
        def edit(ds):
            ds[name][index] = ds[name][index] * factor
        return edit

    def del_att(name):
        def edit(ds):
            ds.delncattr(name)
        return edit

    def add_level(value):
        def edit(ds):
            level = ds.createVariable("target_level", "i4", ("target",))
            level[:] = 1
            level[0] = value
        return edit

    def marker(att, value, flux):
        """Declare ``att`` = ``value`` on the flux and set one flux to it."""
        def edit(ds):
            ds["runoff_flux"].setncattr(att, value)
            ds["runoff_flux"][0, 0] = flux
        return edit

    def several(*edits):
        def edit(ds):
            for one in edits:
                one(ds)
        return edit

    # The targets of the last source (three cells), for a negative fraction
    # that the other two hide in a sum of exactly 1.
    last = [k for k, s in enumerate(info["target_source"])
            if s == len(ids) - 1]
    range_msg = "target_fraction is not in [0,1]: source "
    missing_msg = [f"RNF: missing runoff_flux: source {ids[0]},",
                   "missing value(s) of runoff_flux (not allowed)"]
    stop_flux = "ABNORMAL END: S/R RNF_NC_READ_FLUX"
    tgt_bound = size_bound("RNF_nTgtTile")

    out += [
        file_case("cell_negative",
                  ["target_cell out of range (valid: 0 to nx*ny-1): "
                   f"source {ids[0]},", one_init],
                  edit=set_var("target_cell", 0, -3)),
        file_case("cell_too_large",
                  ["target_cell out of range (valid: 0 to nx*ny-1): "
                   f"source {ids[0]},", one_init],
                  edit=set_var("target_cell", 0, info["nx"] * info["ny"])),
        file_case("target_on_land",
                  ["refused target(s) on all processes", one_init],
                  [f"RNF: target on land: source {ids[0]},"],
                  edit=set_var("target_cell", 0, info["land_cell"])),
        file_case("fraction_sum",
                  [f"RNF: fraction sum is not 1: source {ids[0]},",
                   "source(s) whose fractions do not sum to 1", one_init],
                  edit=set_var("target_fraction", 0, 1.0 - 1.0e-3)),
        file_case("grid_size",
                  ["RNF: grid size mismatch: the file has mitgcm_grid_nx,ny =",
                   one_init],
                  edit=set_att(mitgcm_grid_nx=np.int32(info["nx"] + 1))),
        file_case("time_sampling",
                  ['mitgcm_time_sampling = "fixed" cannot be read yet',
                   "RUNOFF-005", one_init],
                  edit=set_att(mitgcm_time_sampling="fixed",
                               mitgcm_time_period=86400.0)),
        file_case("missing_variable",
                  ["RNF: looking for the required variable target_fraction "
                   "failed", "NetCDF: Variable not found"],
                  stop="ABNORMAL END: S/R RNF_NC_ERROR",
                  skip=("target_fraction",)),
        file_case("cell_area",
                  ["refused target(s) on all processes", one_init],
                  ["RNF: target_cell_area differs from the cell area rA: "
                   f"source {ids[0]},"],
                  edit=scale_var("target_cell_area", 0, 1.01)),
        file_case("missing_flux",
                  [f"RNF: missing runoff_flux: source {ids[0]},",
                   "missing value(s) of runoff_flux (not allowed)"],
                  stop="ABNORMAL END: S/R RNF_NC_READ_FLUX",
                  edit=set_var("runoff_flux", (0, 0), float("nan"))),
        file_case("too_many_sources",
                  ["array bound(s) of RNF_SIZE.h that are too small"],
                  [f"RNF: RNF_nSrcTile ={bound:8d} is too small",
                   f"needs{bound + 1:8d}"],
                  many_sources=bound + 1, wet_cell=info["wet_cell"]),
        file_case("too_many_targets",
                  ["array bound(s) of RNF_SIZE.h that are too small"],
                  [f"RNF: RNF_nTgtTile ={tgt_bound:8d} is too small",
                   f"needs{tgt_bound + 1:8d}"],
                  many_targets=tgt_bound + 1, wet_cell=info["wet_cell"]),
        # No source can be named here: the message gives the value and the
        # index of the entry in the table.
        file_case("source_negative",
                  [f"RNF: target_source out of range:{-1:12d} at target "
                   f"entry (from 0){0:12d}", one_init],
                  edit=set_var("target_source", 0, -1)),
        file_case("source_too_large",
                  [f"RNF: target_source out of range:{len(ids):12d} at target "
                   f"entry (from 0){0:12d}", one_init],
                  edit=set_var("target_source", 0, len(ids))),
        file_case("target_level",
                  ["target_level is not 1 (only the surface cell is "
                   f"allowed): source {ids[0]},", one_init],
                  edit=add_level(2)),
        file_case("fraction_negative",
                  [range_msg + f"{ids[0]},", one_init],
                  edit=set_var("target_fraction", 0, -0.25)),
        file_case("fraction_nan",
                  [range_msg + f"{ids[0]},", one_init],
                  edit=set_var("target_fraction", 0, float("nan"))),
        file_case("fraction_hidden",
                  [range_msg + f"{ids[-1]},", one_init],
                  edit=several(set_var("target_fraction", last[0], -0.25),
                               set_var("target_fraction", last[1], 0.5),
                               set_var("target_fraction", last[2], 0.75))),
        file_case("missing_attribute",
                  ["RNF: the file has no global attribute mitgcm_grid_nx",
                   one_init],
                  edit=del_att("mitgcm_grid_nx")),
        file_case("flux_inf", missing_msg, stop=stop_flux,
                  edit=set_var("runoff_flux", (0, 0), float("inf"))),
        file_case("flux_huge", missing_msg, stop=stop_flux,
                  edit=set_var("runoff_flux", (0, 0), 1.0e31)),
        file_case("missing_value_numeric", missing_msg, stop=stop_flux,
                  edit=marker("missing_value", -9999.0, -9999.0)),
        file_case("fill_value_float32", missing_msg, stop=stop_flux,
                  retype={"runoff_flux": ("f4", np.float32(-1.0e20))},
                  edit=set_var("runoff_flux", (0, 0), np.float32(-1.0e20))),
        # A marker that cannot be read as a number must stop the run; if it
        # were taken as absent, the flux of 9999 m^3/s would be applied.
        file_case("missing_value_text",
                  ["RNF: the attribute missing_value of runoff_flux must be "
                   "one number"],
                  stop="ABNORMAL END: S/R RNF_NC_ATT_REAL",
                  edit=marker("missing_value", "9999.", 9999.0)),
    ]
    # The flux is read in RNF_INIT_VARIA, after RNF_CHECK has passed; the
    # flux sums are printed only if the whole record was accepted.
    for case in out:
        if case["stop"] in (stop_flux, "ABNORMAL END: S/R RNF_NC_ATT_REAL"):
            case["forbid"] = ["RNF_INIT_VARIA: runoff flux"]
    next(c for c in out if c["name"] == "fraction_hidden")["forbid"] = \
        forbid_file + ["fraction sum is not 1"]

    # Runs that must end normally.
    no_error = list(MESSAGES.values()) + ["fatal error(s)", "ABNORMAL END"]
    stdout_ok = ["pkg/rnf", "Sparse runoff (RNF) configuration >>> START",
                 PASSED]
    dense = {name: None for name in ("data", "data.exf")}
    out += [
        {"name": "positive_control",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_ok},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "summary": {"RNF_file": f"'{SPARSE_REL}'",
                     "RNF_nSrcFile": str(len(ids)), "RNF_nTgtOwned": "7"},
         "flux_sum": info["flux_sum"], "stop": "ABNORMAL END",
         "forbid": no_error},
        {"name": "cells_equal_dense",
         "copy_from": DENSE_INPUT, "copy": dense,
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF.format(CELLS_REL)},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "summary": {"RNF_nSrcFile": "7", "RNF_nTgtOwned": "7"},
         "flux_sum": info["flux_sum"], "digits": (DENSE_REF, 13, 99),
         "stop": "ABNORMAL END", "forbid": no_error},
        {"name": "zero_flux_differs",
         "copy_from": DENSE_INPUT, "copy": dense,
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": scale_var("runoff_flux", slice(None), 0.0)}},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "flux_sum": 0.0, "digits": (DENSE_REF, 0, 9),
         "stop": "ABNORMAL END", "forbid": no_error},
    ]
    return out


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


def flux_sums(text):
    """Return the flux sums that ``RNF_INIT_VARIA`` printed, as floats.

    The first is the sum over the sources of the file and the second the sum
    over the targets of all tiles, in m^3/s.
    """
    return [float(m) for m in re.findall(
        r"RNF_INIT_VARIA: runoff flux, sum over the \w+ of [\w ]+ \[m\^3/s\] ="
        r"\s*([-+0-9.Ee]+)", text)]


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


def matching_digits(output_name, reference):
    """Return the digits of agreement of a run with ``results/<reference>``.

    Runs ``compare_results.sh`` with ``--ref`` and reads its "Matching
    digits" line, which is for the deciding variable (``cg2d_init_res``).
    Returns ``None`` if no comparison was possible.
    """
    proc = subprocess.run(
        ["./compare_results.sh", EXPERIMENT, output_name, "--ref", reference],
        cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    match = re.search(r"Matching digits:\s+(\d+)", proc.stdout)
    return int(match.group(1)) if match else None


def judge(case, run_dir, nproc, run_exit, timed_out=False, digits=None):
    """Judge the logs in ``run_dir`` against ``case``; return the result.

    Each process is judged on its own files, named by ``process_logs``: its
    error file must hold every ``stderr`` message, its standard output every
    ``stdout`` line, every ``summary`` value and the ``flux_sum``. Every
    ``stderr_any`` message must be in the error file of at least one process.

    A refusal case needs exactly one ``stop`` line per process in the ``STOP``
    file, no normal end and a non-zero ``run_exit``. A ``normal_end`` case
    needs a normal end, a zero ``run_exit``, no ``stop`` line and, if the case
    has ``digits``, a number of matching digits within its bounds. A
    ``forbid`` message in any log, a run that ``timed_out`` or an empty log
    fails any case. ``missing`` in the result names each unmet expectation.
    """
    names = process_logs(nproc)
    missing = []
    errors = []
    for kind in ("stderr", "stdout"):
        for name in names[kind]:
            text = read_file(run_dir, name)
            if text is None:
                missing.append(f"{name}: no such file")
                continue
            if kind == "stderr":
                errors.append(text)
            missing += [f"{name}: {msg}" for msg in case[kind]
                        if msg not in text]
            if kind == "stdout":
                for param, value in case.get("summary", {}).items():
                    found = summary_value(text, param)
                    if found != value:
                        missing.append(f"{name}: summary reports {param} = "
                                       f"{value} (found {found})")
                if "flux_sum" in case:
                    want = case["flux_sum"]
                    sums = flux_sums(text)
                    tol = [1e-12 * abs(want), 1e-6 * abs(want)]
                    if len(sums) != 2 or any(
                            abs(s - want) > t for s, t in zip(sums, tol)):
                        missing.append(f"{name}: flux sums {want!r} over the "
                                       f"sources and the targets (found {sums})")
    for msg in case.get("stderr_any", []):
        if not any(msg in text for text in errors):
            missing.append(f"STDERR of any process: {msg}")
    processes = len(names["stderr"])
    normal = bool(case.get("normal_end"))
    stop_lines = (read_file(run_dir, names["stop"]) or "").count(case["stop"])
    want_stops = 0 if normal else processes
    if stop_lines != want_stops:
        missing.append(f"{names['stop']}: {want_stops} line(s) with "
                       f"'{case['stop']}' (found {stop_lines})")
    if "digits" in case:
        reference, low, high = case["digits"]
        if digits is None or not low <= digits <= high:
            missing.append(f"{low} to {high} matching digits against "
                           f"{reference} (found {digits})")
    if timed_out:
        missing.append("the run to finish (it timed out: a process hangs)")
    logs = read_logs(run_dir)
    ended_normally = "Execution ended Normally" in logs
    present = [m for m in case["forbid"] if m in logs]
    observed = [line.strip() for line in logs.splitlines()
                if "RNF_" in line and ("*** ERROR ***" in line
                                       or "ABNORMAL END" in line)]
    if normal:
        ended = ended_normally and run_exit == 0
    else:
        ended = not ended_normally and run_exit != 0
    passed = bool(logs) and ended and not missing and not present
    return {
        "case": case["name"], "passed": passed, "processes": processes,
        "run_exit": run_exit, "ended_normally": ended_normally,
        "normal_end_expected": normal, "timed_out": timed_out,
        "log_bytes": len(logs), "stop_lines": stop_lines, "digits": digits,
        "expected": {key: case[key] for key in
                     ("stderr", "stderr_any", "stdout", "stop", "summary",
                      "flux_sum", "digits") if key in case},
        "missing": missing, "forbidden_present": present,
        "observed": observed,
    }


def kill_run(output_name):
    """Kill the Docker container that runs in the directory ``output_name``.

    Used after a timeout: the run script starts the model in a container
    whose working directory ends with the run directory name.
    """
    listed = subprocess.run(["docker", "ps", "-q"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    for cid in listed.stdout.split():
        where = subprocess.run(
            ["docker", "inspect", "--format", "{{.Config.WorkingDir}}", cid],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if where.stdout.strip().endswith("/" + output_name):
            subprocess.run(["docker", "kill", cid], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)


def run_case(case, keep, nproc=0, timeout=600):
    """Run one case and return the result dictionary of ``judge``.

    ``nproc`` is the number of MPI processes; 0 runs the single-process
    binary. A run that lasts longer than ``timeout`` seconds is killed and
    fails. The scratch input directory is always removed, and the run
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
    timed_out = False
    try:
        for name in case.get("copy", {}):
            shutil.copyfile(
                os.path.join(VERIF, EXPERIMENT, case["copy_from"], name),
                os.path.join(input_dir, name))
        for name, content in case["files"].items():
            with open(os.path.join(input_dir, name), "w") as fh:
                fh.write(content)
        for name, kwargs in case.get("nc", {}).items():
            sparse_file(os.path.join(input_dir, name), **kwargs)
        try:
            proc = subprocess.run(
                ["./experiment_run_no_compile.sh", EXPERIMENT, input_name]
                + mpi_args
                + ["-build", build_name(nproc), "-output", output_name],
                cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, timeout=timeout)
            run_exit = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            run_exit = -1
            kill_run(output_name)
        digits = None
        if "digits" in case and not timed_out:
            digits = matching_digits(output_name, case["digits"][0])
        result = judge(case, run_dir, nproc, run_exit, timed_out, digits)
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
    parser.add_argument("--timeout", type=float, default=600.0, metavar="S",
                        help="seconds after which a run counts as hanging")
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

    selected = cases(data_pkg, data_exf, sparse_info())
    if args.case:
        unknown = set(args.case) - {c["name"] for c in selected}
        if unknown:
            print(f"unknown case(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        selected = [c for c in selected if c["name"] in args.case]

    results = [run_case(case, args.keep, args.mpi, args.timeout)
               for case in selected]
    for res in results:
        note = "" if res["digits"] is None else f" ({res['digits']} digits)"
        print(f"{'PASS' if res['passed'] else 'FAIL'} {res['case']}{note}")
        for line in res["observed"]:
            print(f"     {line}")
        for msg in res["missing"]:
            print(f"     missing: {msg}")
        for msg in res["forbidden_present"]:
            print(f"     must not appear: {msg}")
        if res["ended_normally"] != res["normal_end_expected"]:
            print("     the model ended normally" if res["ended_normally"]
                  else "     the model did not end normally")
    if args.json:
        print(json.dumps(results, indent=1))
    failed = [r["case"] for r in results if not r["passed"]]
    print(f"{len(results) - len(failed)} of {len(results)} cases passed")
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
