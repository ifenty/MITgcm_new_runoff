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
  - a target on land, a wrong cell area, a fraction sum off by 1e-3, and
    a target moved one cell in x while its ``target_lon``/``target_lat``
    still name the cell it came from (``target_coords``). That move is
    what no other check can see: the cell it lands on is wet, the
    fractions still sum to 1, and on this lat-lon grid its ``rA`` is
    bitwise equal, so the case also asserts that the land, fraction and
    area messages do **not** appear. ``target_coords_nan`` is the same
    check against a coordinate that is not a number, which the obvious
    "distance greater than the tolerance" form accepts;
  - the file as a whole: a grid size mismatch, a missing grid attribute, a
    time sampling other than ``constant``, a missing required variable;
  - the flux: not a number, infinite, above 1e30, equal to a numeric
    ``missing_value`` or to the ``_FillValue`` of a float32 variable, and a
    ``missing_value`` stored as text, which must stop the run and not be
    taken as absent;
  - the flux above ``RNF_srcFluxMax``, the package's own magnitude bound
    (``flux_above_source_max``, RUNOFF-030). It is the negative control of
    the relaxations that issue makes in ``EXF_CHECK_RANGE``, which with
    ``useRNF`` skips its runoff upper bound of 1e-6 m/s and exempts the
    runoff from its ``sflux`` bound, so without this refusal nothing would
    stop an absurd flux. Its at-the-bound companion
    ``flux_at_source_max`` is among the normal-end runs below;
  - the per-cell **aggregate** above ``RNF_cellVolMax``
    (``cell_above_vol_max``, RUNOFF-040), which is the error class the
    bound above cannot see: it is per source and per file, so four
    sources each carrying *exactly* ``RNF_srcFluxMax`` with every target
    collapsed onto one cell got past it, applying 1.285228e-3 m/s and
    ending normally with no message at all (measured). The collapse
    carries ``target_cell_area``, ``target_lon`` and ``target_lat`` with
    the targets and leaves the fractions alone, so no init check can
    fire and the aggregate is the only thing wrong with the file; the
    ``forbid`` list asserts that. ``RNF_EXF_RUNOFF`` refuses it on every
    step, naming the cell, the applied value and the limit. Its control
    ``cell_at_vol_max``, just under the bound, is among the normal-end
    runs below;
  - the exf freshwater bound with ``useRNF`` on and **no** runoff at all
    (``sflux_out_of_range``, RUNOFF-030 correction round 1): the ``sflux``
    test is applied to ``sflux + runoff`` with ``useRNF``, and this case
    holds that to being a *restore* rather than a removal. ``precipfile``
    is blanked, ``precipconst`` is 1e-4 m/s and every flux of the file is
    zeroed, so the quantity the test sees is exactly ``evap - precip`` and
    must still stop the run. It is judged on ``pkg/exf``'s standard-output
    warnings and on ``ABNORMAL END: S/R EXF_CHECK_RANGE``; the uniform
    ``precipconst`` is what makes every process stop with its own ``STOP``
    line, which is required under ``--mpi N`` because ``EXF_CHECK_RANGE``
    calls ``STOP`` without ``ALL_PROC_DIE``;
  - more sources or more target entries on one tile than ``RNF_nSrcTile`` or
    ``RNF_nTgtTile``;
  - the runoff tracer series (``RNF_NC_SERIES``, RUNOFF-013): a tracer name
    that matches no ptracer, tracer variables in a run that does not use
    pkg/ptracers, a name with nothing after the prefix, a name longer than
    ``RNF_idLen`` and more tracer variables than ``RNF_nTr``. The last three
    each have an **at-the-bound** companion (``ptracer_name_min``,
    ``ptracer_name_max``, ``ptracer_count_max``) in which the guard must stay
    silent and the run is refused by the *next* test instead -- the direction
    a weakened-guard mutant cannot measure.
* **Runs that must end normally**: the positive control (the valid file on
  ``lab_sea/input``; the flux sums that the model prints must equal the sum
  of the file), ``flux_at_source_max`` (one source carrying exactly
  ``RNF_srcFluxMax``: the magnitude guard must stay silent at the bound
  and the record must then be applied. It is also the enrolled
  acceptance of the exf relaxation, because the applied field is
  3.21e-4 m/s, 321 times what pkg/exf allows, and the run must finish
  with ``useExfCheckRange`` at the lab_sea default ``.TRUE.``, printing
  neither range warning and no m/yr advice. No case here switches
  ``useExfCheckRange`` off),
  ``cell_at_vol_max`` (the control of ``cell_above_vol_max``: the same
  collapse onto one cell, sized so that the aggregate is 0.99 of
  ``RNF_cellVolMax`` rather than 2.31 times it, so the per-cell guard
  must stay silent and the record must then be applied. It is the
  tightest run here that must still finish: it applies 5.50e-4 m/s against
  that bound's 5.5556e-4 m/s, where ``flux_at_source_max`` applies
  3.21e-4 m/s, so it sits 1.7 times nearer the bound. A margin that thin is
  safe only because lab_sea is a linear free surface, so the thickness the
  guard divides by never moves; see the case's own comment),
  ``cells_equal_dense`` (the one-source-per-cell file must
  reproduce the dense reference ``results/output.rnof_const.txt``),
  ``zero_flux_differs`` (the same run with every flux set to zero must NOT
  reproduce it, which shows that the comparison is sensitive to the runoff),
  ``two_sources_one_cell`` (each cell fed by two sources carrying a
  third and two thirds of its flux must reproduce the same dense reference,
  which is the case that makes the model add two contributions into one
  cell), and ``three_sources_one_cell`` (the same with three sources,
  sized by ``ulp_shares`` so that the three-term sum is sensitive to the
  order it is added in; what tests the order itself is the bitwise case
  ``order_sensitive_sum`` of ``tests/rnf/applied_field_check.py``, which
  uses the same generator).

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

A refusal that only one tile's check detects (land, cell area, cell centre,
array bound, per-cell aggregate) must stop every process. Under ``--mpi``
this is what the ``STOP`` count and the timeout check: one ``STOP`` line per
process, and no hang. Those five checks are not a remembered list: they are
exactly the checks behind the cases that carry a ``stderr_any`` message,
which is by definition the message only the owning process prints -- seven
cases (``target_on_land``, ``cell_area``, ``target_coords``,
``target_coords_nan``, ``too_many_sources``, ``too_many_targets``,
``cell_above_vol_max``). Four of the five checks are ``RNF_INIT_FIXED``'s;
the fifth is the per-cell aggregate bound ``RNF_cellVolMax``, which
``RNF_EXF_RUNOFF`` evaluates per cell on the tile that owns it and then
reduces with ``GLOBAL_SUM_INT`` so that every process stops
(``rnf_exf_runoff.F``, the per-cell loop at 144-179 and the reduction and
stop at 184-205).

**This paragraph has been wrong twice, both times by omitting a check that
had just been added, so it is asserted rather than maintained:**
``tests/esx/test_instrument_claims.py`` compares the two counts and the seven
names above against what :func:`cases` returns, and fails the ``structural``
suite when they drift. "Cell centre" was missing from RUNOFF-033, which added
that check, until RUNOFF-042's sweep of ``.py`` returned the line as a
candidate; that correction then omitted ``cell_above_vol_max`` (RUNOFF-040),
because the enumeration behind it walked the AST for ``file_case(...)`` calls
and this one case is a dict literal instead, so the method could not see it.
Both reviewers found the omission by **calling** :func:`cases`, which is the
enumeration that sees every case however it was built, and that is how the
test above derives the set.

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
# The same runoff with one source per cell, and its path for ``split_from``.
CELLS = os.path.join(VERIF, EXPERIMENT, "input.rnof_const",
                     "runoff_sparse_cells.nc")
CELLS_REL = "../input.rnof_const/runoff_sparse_cells.nc"
DENSE_INPUT = "input.rnof_sp_const"
DENSE_REF = "output.rnof_const.txt"
# Size of each of the two small terms of the order-sensitive three-way
# split, in units in the last place of the big one. It has to lie
# strictly between 0.25 and 0.5: see ``ulp_shares``.
ULP_SHARE = 0.35
RNF_SIZE = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "RNF_SIZE.h")
RNF_HEADER = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "RNF.h")

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

# The committed yearly set, with a repeat cycle added: the one
# combination RNF_TIME_SETUP refuses that is a data.rnf fault rather
# than a file fault, so it needs the real yearly files and not a
# generated one.
DATA_RNF_YEARLY = """# Sparse runoff package parameters
 &RNF_PARM01
  RNF_file = '../input.rnof_yearly/runoff_sparse.nc',
  RNF_useYearlyFiles = .TRUE.,
  RNF_repCycle = 31536000.,
 &
"""

# One passive tracer called "dye", for the runoff-tracer cases of
# RUNOFF-013: a runoff_ptracer_<NAME> variable has to match a
# PTRACERS_names entry exactly. PTRACERS_num of the build is 1
# (pkg/ptracers/PTRACERS_SIZE.h), so one is all there is room for.
# PTRACERS_Iter0 = 1 = nIter0 of lab_sea/input, so the tracer starts
# from PTRACERS_initialFile (blank: zero) instead of from a
# pickup_ptracers file, which this set-up has none of.
DATA_PTRACERS = """# One passive tracer, for the runoff tracer cases
 &PTRACERS_PARM01
 PTRACERS_numInUse = 1,
 PTRACERS_Iter0 = 1,
 PTRACERS_names(1) = 'dye',
 PTRACERS_long_names(1) = 'runoff dye',
 PTRACERS_units(1) = '1',
 PTRACERS_initialFile(1) = ' ',
 PTRACERS_diffKh(1) = 0.,
 PTRACERS_diffKr(1) = 0.,
 &
"""

# lab_sea compiles pkg/longstep, which reads this file whenever
# usePTRACERS is true (model/src/packages_readparms.F:248-249 calls
# LONGSTEP_READPARMS before PTRACERS_READPARMS, and it stops the run if
# the file is absent). LS_nIter = 1 is its default: one ptracer step per
# dynamics step, i.e. no long step.
DATA_LONGSTEP = """# pkg/longstep defaults, for the runoff tracer cases
 &LONGSTEP_PARM01
 LS_nIter = 1,
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


def size_bound(name, header=None):
    """Return the integer bound ``name`` set in a ``pkg/rnf`` header.

    ``header`` defaults to ``RNF_SIZE.h``; the runoff-tracer name-length
    bound ``RNF_idLen`` lives in ``RNF.h`` instead. Reading the value
    from the source rather than repeating it keeps a case that quotes it
    in an expected message from drifting away from the code.
    """
    path = header or RNF_SIZE
    with open(path) as fh:
        match = re.search(rf"PARAMETER\s*\(\s*{name}\s*=\s*(\d+)\s*\)", fh.read())
    if not match:
        raise ValueError(f"{name} not found in {path}")
    return int(match.group(1))


def real_bound(name, header=None):
    """Return the real ``PARAMETER`` ``name`` set in a ``pkg/rnf`` header.

    ``header`` defaults to ``RNF.h``, which holds the constants fixed by
    the model contract. The Fortran literal carries MITgcm's ``_d``
    exponent macro (``1. _d 7``), which this turns into a Python float.
    Reading the value from the source rather than repeating it keeps a
    case that drives a bound, or quotes it in an expected message, from
    drifting away from the code, exactly as :func:`size_bound` does for
    the integer bounds.
    """
    path = header or RNF_HEADER
    with open(path) as fh:
        match = re.search(
            rf"PARAMETER\s*\(\s*{name}\s*=\s*"
            rf"([-+]?[0-9]*\.?[0-9]*)\s*_d\s*([-+]?\d+)\s*\)", fh.read())
    if not match:
        raise ValueError(f"{name} not found in {path}")
    return float(match.group(1)) * 10.0**int(match.group(2))


def e16_8(value):
    """Render ``value`` as Fortran's ``1PE16.8`` edit descriptor does.

    One digit before the point, eight after it, a two-digit exponent,
    right-justified in sixteen columns. Used to build the expected text
    of a message that prints a real with that descriptor, so the case
    asserts the figure the model prints and not merely a substring in
    front of it.
    """
    return f"{value:.8E}".rjust(16)


def sparse_info():
    """Return what the cases need to know about the valid sparse file.

    The result has ``ids`` (source ids in file order), ``target_source``
    (the source index of each target entry), ``nx``, ``ny``, ``flux_sum``
    (sum of the one flux record, m^3/s), ``flux0`` (the flux of the first
    source, which the flux-bound cases replace), ``wet_cell`` (the cell of
    the first target) and ``land_cell`` (a land cell of the western half of
    the grid, which one process owns in a two-process run). Land is where
    ``input/bathy.labsea1979`` is not negative.

    For the per-cell aggregate cases of RUNOFF-040 it also has
    ``fracs`` (``target_fraction`` in file order) and the three stored
    properties of the cell the targets are collapsed onto, which the
    collapse carries with them so that no area or cell-centre check can
    fire: ``wet_area``, ``wet_lon`` and ``wet_lat``.

    It also has the three values of the ``target_coords`` case, which moves
    one target to its neighbour in x: ``moved_entry`` (the table entry),
    ``moved_cell`` (the cell it is moved to) and ``moved_source`` (the id
    of its source, for the expected message). The entry is the first whose
    neighbour in x is wet, is not already a target of the file and is in
    the same row, so that the move is the failure the cell-centre check
    exists for: on this lat-lon grid ``rA`` depends only on latitude, so
    the neighbour's area is bitwise equal and no area tolerance can tell
    the two cells apart, exactly as for the two cs32 cells across the
    facet 2/3 boundary of RUNOFF-033. ``ValueError`` if the file has no
    such entry, so the case can never run as something weaker.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(SPARSE) as ds:
        ids = [str(s) for s in netCDF4.chartostring(ds["source_id"][:])]
        target_source = [int(s) for s in ds["target_source"][:]]
        nx = int(ds.getncattr("mitgcm_grid_nx"))
        ny = int(ds.getncattr("mitgcm_grid_ny"))
        flux = np.asarray(ds["runoff_flux"][0], dtype="f8")
        flux_sum = float(flux.sum())
        flux0 = float(flux[0])
        cells = np.asarray(ds["target_cell"][:]).astype(int)
        wet_cell = int(cells[0])
        fracs = [float(f) for f in ds["target_fraction"][:]]
        wet_area = float(ds["target_cell_area"][0])
        wet_lon = float(ds["target_lon"][0])
        wet_lat = float(ds["target_lat"][0])
    bathy = np.fromfile(os.path.join(VERIF, EXPERIMENT, "input", "bathy.labsea1979"),
                        dtype=">f4").reshape(ny, nx)
    land = [(int(j), int(i)) for j, i in np.argwhere(bathy >= 0.0) if i < nx // 2]
    j, i = land[len(land) // 2]
    wet = (bathy < 0.0).ravel()
    moved = [(k, int(c) + 1) for k, c in enumerate(cells)
             if int(c) % nx + 1 < nx and wet[int(c) + 1]
             and int(c) + 1 not in set(cells.tolist())]
    if not moved:
        raise ValueError(f"{SPARSE} has no target whose neighbour in x is "
                         f"wet and not already a target: the target_coords "
                         f"case has no one-cell move to make")
    moved_entry, moved_cell = moved[0]
    return {"ids": ids, "target_source": target_source, "nx": nx, "ny": ny,
            "flux_sum": flux_sum, "flux0": flux0, "wet_cell": wet_cell,
            "land_cell": i + nx * j,
            "fracs": fracs, "wet_area": wet_area,
            "wet_lon": wet_lon, "wet_lat": wet_lat,
            "moved_entry": moved_entry, "moved_cell": moved_cell,
            "moved_source": ids[target_source[moved_entry]]}


def applied_on_cell(flux, info):
    """Aggregate applied value, in m/s, when every target is on one cell.

    ``flux`` is the volume flux every source of ``SPARSE`` carries, in
    m^3/s. The sum is accumulated over the target entries **in file
    order**, each as ``flux*frac/rA``, which is what ``RNF_LOAD_AT``
    builds (``pkg/rnf/rnf_fields_load.F``, the ``RNF_vflx`` statement)
    and whose order the package design declares a contract. It is
    rebuilt here rather than shortened to ``n*flux/rA`` so that the
    figure a case asserts is the one the model computes, to the last
    place.
    """
    total = 0.0
    for k in range(len(info["fracs"])):
        total += flux*info["fracs"][k]/info["wet_area"]
    return total


def surface_bound(experiment_input="input"):
    """Return ``(drF(1), deltaTFreeSurf, limit)`` of a lab_sea run.

    ``limit`` is the largest runoff one cell may take, in m/s, i.e. the
    value ``RNF_EXF_RUNOFF`` compares the applied field with: its
    ``vLim`` is ``RNF_cellVolMax*drF(ks)*hFacC(ks)/deltaTFreeSurf``.
    ``RNF_cellVolMax`` is read from ``RNF.h`` and the two grid values
    from the experiment's own ``data``, so neither can drift away from
    what the run uses:

    * ``drF(1)`` is ``delZ(1)``. ``hFacC(i,j,1)`` is 1 at every target
      cell of the sparse files, because the shallowest of them is 55 m
      deep against a 10 m first level (measured);
    * ``deltaTFreeSurf`` defaults to ``deltaTMom``
      (``model/src/ini_parms.F:1068``) and lab_sea's ``data`` does not
      set it. A ``data`` that did would make that default wrong, so
      this raises rather than return a stale figure.

    **The validity condition is ``nonlinFreeSurf`` = 0, which lab_sea
    satisfies** (and ``select_rStar`` = 0 with it, as its own run
    reports). The guard compares against the *live* ``hFacC``, and
    nothing updates ``hFacC`` at run time only when
    ``nonlinFreeSurf`` = 0 -- that is the arm where
    ``update_surf_dr.F:125`` resets it to ``h0FacC``. There the live
    thickness is the reference one for the whole run and the limit
    returned here is the limit enforced at every step.

    **Do not read the condition as "no r\\*".** With
    ``nonlinFreeSurf`` > 0 and ``select_rStar`` = 0 there is no r\\*
    and the live thickness is still not the reference: ``CALC_SURF_DR``
    computes ``hFac_surfC`` and ``UPDATE_SURF_DR`` installs it into
    ``hFacC`` (``update_surf_dr.F:56``, ``:92``), the
    ``select_rStar`` = 0 arm of the ``IF`` at ``forward_step.F:832``.
    So this helper is **not** valid there either, and an earlier
    version of this docstring said "with no r\\*" and would have told a
    maintainer adding such an experiment that it was. Measured on the
    one r\\* grid here: 26% of cs32's target cells run more than 1%
    thinner than their reference, so a caller that took this figure to
    any ``nonlinFreeSurf`` > 0 set-up would be computing a limit the
    model does not enforce.
    """
    path = os.path.join(VERIF, EXPERIMENT, experiment_input, "data")
    with open(path) as fh:
        text = fh.read()
    active = [ln for ln in text.splitlines()
              if not ln.lstrip().startswith("#") and "=" in ln]
    for line in active:
        if line.split("=")[0].strip().lower() == "deltatfreesurf":
            raise ValueError(f"{path} sets deltaTFreeSurf: surface_bound "
                             f"assumes it defaults to deltaTMom")
    def one(name):
        hits = [ln.split("=", 1)[1] for ln in active
                if ln.split("=")[0].strip().lower() == name]
        if len(hits) != 1:
            raise ValueError(f"expected one {name} in {path}, "
                             f"found {len(hits)}")
        return hits[0]
    drf1 = float(one("delz").split(",")[0].strip())
    dtfs = float(one("deltatmom").strip().rstrip(",").replace("D", "E"))
    return drf1, dtfs, real_bound("RNF_cellVolMax")*drf1/dtfs


def ulp_shares(flux, area, fraction=0.35):
    """Three fluxes whose sum on one cell is sensitive to the order it is added in.

    ``flux`` goes to one cell of area ``area``, so the term the model adds
    is ``flux/area``. This returns ``(big, small, small)`` such that the
    two small terms are each ``fraction`` units in the last place (ulp) of
    the big one, with ``0.25 < fraction < 0.5``.

    That window is the whole point (RUNOFF-005, review A of RUNOFF-033).
    With ``t`` the big term and ``c = fraction*ulp(t)``:

    * ``fl(t + c) = t`` and ``fl(t + c) + c = t``: adding the two small
      terms **after** the big one changes nothing, because each one on
      its own rounds away;
    * ``fl(c + c) = 2c`` and ``fl(2c + t) = t + ulp(t)``: adding them to
      each other **first** carries the pair over the rounding boundary.

    So the forward and reversed sums differ by exactly one ulp. Two
    sub-sources could not do this: a two-term floating-point sum is
    commutative, so a two-way split is order-insensitive whatever the
    sizes, and a case built that way would pass vacuously.

    The ulp is taken of the big term itself, not of ``flux/area``, so the
    sizing survives the big term falling in a lower binade than the
    original value; two passes are enough because the correction is of
    order 1e-16.
    """
    import numpy as np
    small = 0.0
    for _ in range(2):
        big = (flux - 2.0*small)/area
        small = fraction*(float(np.nextafter(big, np.inf)) - big)*area
    return flux - 2.0*small, small, small


def split_file(path, source_path, share=1.0/3.0, ulp=None):
    """Write a file in which several sources feed each cell of ``source_path``.

    Every source of ``source_path`` (a one-source-per-cell file) becomes
    two sources, ``<id>_a`` and ``<id>_b``, carrying ``share`` and
    ``1 - share`` of its flux, each with one target entry of fraction 1 on
    the same cell. Every source's fractions still sum to 1 and the total
    flux is unchanged, so the field the model applies is the same to
    round-off: the only difference is that each cell now receives two
    contributions, which is what exercises the accumulation of
    ``rnf_fields_load.F``. A reader that overwrote instead of adding would
    apply a third or two thirds of the runoff.

    With ``ulp`` set to a fraction, each source becomes **three**
    sub-sources instead, ``<id>_a``, ``<id>_b`` and ``<id>_c``, sized by
    :func:`ulp_shares` so that the three-term sum on each cell differs by
    one unit in the last place between the file's order and the reverse.
    That is the construction that makes the bitwise criterion of
    ``tests/rnf/applied_field_check.py`` test the accumulation order and
    not merely the accumulation; its docstring explains why a two-way
    split cannot.

    Returns the per-source shares that were written, in file order.
    """
    import netCDF4
    import numpy as np
    parts = ("_a", "_b", "_c") if ulp else ("_a", "_b")
    with netCDF4.Dataset(source_path) as src, netCDF4.Dataset(path, "w") as dst:
        src.set_auto_maskandscale(False)
        dst.set_auto_maskandscale(False)
        dst.setncatts({k: src.getncattr(k) for k in src.ncattrs()})
        ids = [str(s) for s in netCDF4.chartostring(src["source_id"][:])]
        cell = {int(s): int(c) for s, c in zip(src["target_source"][:],
                                               src["target_cell"][:])}
        area = {int(s): float(a) for s, a in zip(src["target_source"][:],
                                                 src["target_cell_area"][:])}
        flux = np.asarray(src["runoff_flux"][0], dtype="f8")
        shares = []
        for k in range(len(ids)):
            if ulp:
                shares.extend(ulp_shares(float(flux[k]), area[k], ulp))
            else:
                shares.extend((float(flux[k])*share,
                               float(flux[k])*(1.0 - share)))
        n = len(parts)*len(ids)
        strlen = max(len(i) for i in ids) + 2
        dst.createDimension("time", None)
        dst.createDimension("source", n)
        dst.createDimension("target", n)
        dst.createDimension("id_strlen", strlen)
        dst.createVariable("time", "f8", ("time",))[:] = [0.0]
        dst["time"].setncatts({k: src["time"].getncattr(k)
                               for k in src["time"].ncattrs()})
        names = [i + s for i in ids for s in parts]
        dst.createVariable("source_id", "S1", ("source", "id_strlen"))[:] = \
            np.array([list(x.ljust(strlen)) for x in names], dtype="S1")
        dst.createVariable("target_source", "i4", ("target",))[:] = np.arange(n)
        dst.createVariable("target_cell", "i4", ("target",))[:] = \
            [cell[k] for k in range(len(ids)) for _ in parts]
        frac = dst.createVariable("target_fraction", "f8", ("target",))
        frac[:] = 1.0
        frac.units = "1"
        ar = dst.createVariable("target_cell_area", "f8", ("target",))
        ar[:] = [area[k] for k in range(len(ids)) for _ in parts]
        ar.units = "m2"
        out = dst.createVariable("runoff_flux", "f8", ("time", "source"))
        out[0, :] = shares
        out.units = "m3 s-1"
    return shares


#: Time axis of the file :func:`sparse_file` writes with ``timed``: daily
#: records from the calendar start date of ``lab_sea/input``
#: (1 January 1979 00:00), on the model's own calendar, which is what
#: makes such a file valid for these runs.
TIMED_UNITS = "days since 1979-01-01 00:00:00"
TIMED_CALENDAR = "gregorian"
TIMED_PERIOD = 86400.0


def timed_axis(dst, nrec, period=TIMED_PERIOD, repeat="none", first=0.0,
               units=TIMED_UNITS, calendar=TIMED_CALENDAR, bounds=True,
               monthly=False, drop=()):
    """Give an open file a valid timed axis, in place of its constant one.

    ``nrec`` records ``period`` seconds apart from ``first`` (in the units
    of the axis), with ``time_bnds`` centred on them, and the three global
    attributes that say so. With ``monthly`` the sampling is ``monthly``
    and the records are the midpoints of consecutive calendar months from
    the month ``first`` falls in, with their months as bounds. The flux of
    record 1 is repeated into every record, so the field the model applies
    does not depend on which record it picks.

    This is the valid file the time refusals of :func:`cases` each break
    in one place. It is written rather than committed because the
    violations are what the cases are about, not the data.

    ``drop`` names global attributes to leave out, for a case whose
    violation is a **missing** attribute. They are dropped here rather
    than deleted afterwards by the case's ``edit``, because netCDF4
    does not persist the deletion of an attribute that was set earlier
    in the same session with variable data written in between:
    measured, ``delncattr`` left ``mitgcm_time_sampling`` absent in
    session and present on disk, and the case then exercised the wrong
    refusal.
    """
    import datetime as dt
    import numpy as np
    day = 86400.0
    for name in drop:
        if name in dst.ncattrs():
            dst.delncattr(name)
    flux = np.asarray(dst["runoff_flux"][0], dtype="f8")
    atts = {k: dst["time"].getncattr(k) for k in dst["time"].ncattrs()}
    atts.update(units=units, calendar=calendar, bounds="time_bnds")
    if monthly:
        base = dt.datetime(1979, 1, 1) + dt.timedelta(days=first)
        edges = []
        year, month = base.year, base.month
        for _ in range(nrec + 1):
            edges.append((dt.datetime(year, month, 1)
                          - dt.datetime(1979, 1, 1)).total_seconds() / day)
            year, month = (year + (month == 12), month % 12 + 1)
        times = [0.5 * (edges[k] + edges[k + 1]) for k in range(nrec)]
        pairs = [(edges[k], edges[k + 1]) for k in range(nrec)]
        sampling, period_att = "monthly", None
    else:
        step = period / day
        times = [first + k * step for k in range(nrec)]
        pairs = [(t - 0.5 * step, t + 0.5 * step) for t in times]
        sampling, period_att = "fixed", period
    # ``time`` is the unlimited dimension of the file, so writing nrec
    # values to it grows the axis and the flux with it.
    dst["time"][:] = times
    dst["time"].setncatts(atts)
    if bounds:
        if "nv" not in dst.dimensions:
            dst.createDimension("nv", 2)
        bnd = dst.createVariable("time_bnds", "f8", ("time", "nv"))
        bnd[:] = np.array(pairs, dtype="f8")
        bnd.units = units
        bnd.calendar = calendar
    else:
        dst["time"].delncattr("bounds")
    dst["runoff_flux"][:] = np.tile(flux, (nrec, 1))
    if "mitgcm_time_sampling" not in drop:
        dst.setncattr("mitgcm_time_sampling", sampling)
    if "mitgcm_time_repeat" not in drop:
        dst.setncattr("mitgcm_time_repeat", repeat)
    if period_att is not None and "mitgcm_time_period" not in drop:
        dst.setncattr("mitgcm_time_period", np.float64(period_att))
    elif "mitgcm_time_period" in dst.ncattrs():
        dst.delncattr("mitgcm_time_period")


def sparse_file(path, edit=None, skip=(), retype=None, many_sources=0,
                many_targets=0, wet_cell=0, split_from=None, split_ulp=None,
                timed=None):
    """Write a sparse runoff file at ``path``, derived from the valid one.

    Every dimension, variable and attribute of ``SPARSE`` is copied except
    the variables named in ``skip``; then ``edit(ds)`` changes the open copy.
    ``retype`` maps a variable name to ``(dtype, fill value)``: that variable
    is stored with this type and ``_FillValue`` in the copy.

    With ``many_sources`` the file is instead a synthetic one with that many
    sources, each sending all its flux to ``wet_cell``, which puts them all
    on one tile. With ``many_targets`` it is a synthetic file with one source
    and that many target entries, all on ``wet_cell`` with equal fractions.
    With ``split_from`` it is the file of :func:`split_file`, in which two
    sources feed each cell of that file, or three with ``split_ulp``.
    """
    import netCDF4
    import numpy as np
    if split_from:
        split_file(path, split_from, ulp=split_ulp)
        return
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
        if timed:
            timed_axis(dst, **timed)
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
    # With pkg/ptracers in use, for the runoff-tracer cases of
    # RUNOFF-013. lab_sea compiles ptracers (its code/packages.conf) and
    # leaves it switched off, so both the "no matching name" refusal and
    # the "ptracers is not in use" one are reachable with the one binary.
    pkg_ptr = set_package_flags(data_pkg, {"useRNF": ".TRUE.",
                                           "usePTRACERS": ".TRUE."})
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

    def n_init(count):
        """The RNF_INIT_FIXED tally line for ``count`` fatal errors."""
        return f"RNF_INIT_FIXED: detected {count:7d} fatal error(s)"
    bound = size_bound("RNF_nSrcTile")

    def file_case(name, stderr, stderr_any=(), stop=stop_init, rnf=None,
                  **nc_kw):
        return {"name": name,
                "files": {"data.pkg": pkg_on, "data.rnf": rnf or rnf_bad},
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

    def set_bnd(record, side, value):
        """Move one bound of one record (1-based record, 1 or 2 side)."""
        def edit(ds):
            ds["time_bnds"][record - 1, side - 1] = value
        return edit

    def del_var_att(var, att):
        """Drop an attribute of a variable, not of the file."""
        def edit(ds):
            ds[var].delncattr(att)
        return edit

    def bnds_1d():
        """Write a time_bnds with one dimension instead of (time, nv).

        Used with ``bounds: False``, which leaves the variable out, so
        this one is the only time_bnds in the file.
        """
        def edit(ds):
            ds.createVariable("time_bnds", "f8", ("time",))[:] = \
                np.zeros(len(ds.dimensions["time"]))
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

    def add_series(name, value):
        """Add a (time, source) series, e.g. a runoff tracer (RUNOFF-013)."""
        def edit(ds):
            var = ds.createVariable(name, "f8", ("time", "source"))
            var.units = "1"
            var[:] = value
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
    # The two bounds the runoff-tracer name cases quote in their expected
    # messages, read from the headers so a case cannot outlive its bound.
    # RNF_NC_SERIES prints both with the Fortran I6 edit descriptor, which
    # is the ``:6d`` in the expected strings below.
    tr_bound = size_bound("RNF_nTr")
    id_bound = size_bound("RNF_idLen", RNF_HEADER)
    # The package's own bound on the volume flux of one source
    # (RUNOFF-030). It is what replaces the pkg/exf runoff upper bound
    # of 1e-6 m/s, which EXF_CHECK_RANGE skips when useRNF is true, so
    # the pair of cases below is the negative control of that
    # relaxation: with the bound gone, nothing would refuse an absurd
    # flux at all. Both the value and the limit are quoted as the
    # model prints them (``1PE16.8``), from the value in RNF.h.
    flux_bound = real_bound("RNF_srcFluxMax")
    over_msg = [
        f"RNF_NC_READ_FLUX: RNF: runoff_flux out of range: source"
        f" {ids[0]}, record{1:8d}, value{e16_8(2.0*flux_bound)},"
        f" limit{e16_8(flux_bound)}",
        f"RNF_NC_READ_FLUX: RNF:{1:8d} value(s) of runoff_flux out of"
        f" range (not allowed)"]
    # The package's own bound on the per-cell AGGREGATE (RUNOFF-040).
    # RNF_srcFluxMax above is per source and per file, so it cannot see
    # several sources adding up on one cell; RNF_cellVolMax is the share
    # of the target cell's top-layer volume that one time step of runoff
    # may add, and RNF_EXF_RUNOFF refuses the cell that exceeds it. The
    # limit in m/s is read from the constant and the grid, never
    # repeated: see ``surface_bound``.
    vol_bound = real_bound("RNF_cellVolMax")
    drf1, dtfs, cell_limit = surface_bound()
    # Review B's witness: four sources each carrying exactly
    # RNF_srcFluxMax with every target on one cell.
    agg_applied = applied_on_cell(flux_bound, info)
    # Just under the bound, for the control that must still run. The
    # per-source flux it needs has to stay under RNF_srcFluxMax, or the
    # control would be refused by that guard instead and so would
    # measure it rather than this one -- which is what happens, and is
    # how this was found, on a mutant whose RNF_cellVolMax is ten times
    # too large. Raise rather than run as something weaker.
    at_vol_flux = 0.99*cell_limit*info["wet_area"]/sum(info["fracs"])
    if at_vol_flux >= flux_bound:
        raise ValueError(
            f"cell_at_vol_max needs {at_vol_flux:.6E} m^3/s a source to "
            f"reach 0.99 of RNF_cellVolMax on this grid, which is not "
            f"below RNF_srcFluxMax = {flux_bound:.6E}: the control would "
            f"be refused by the per-source bound instead")
    cell_msg = [
        "RNF_EXF_RUNOFF: RNF: runoff out of range: cell (i,j,bi,bj) =",
        f", value{e16_8(agg_applied)}, limit{e16_8(cell_limit)}",
        f"RNF_EXF_RUNOFF: its XC,YC ={e16_8(info['wet_lon'])}"
        f"{e16_8(info['wet_lat'])}, top-layer thickness{e16_8(drf1)}"
        f" m, deltaTFreeSurf{e16_8(dtfs)}"]
    cell_tally = [
        f"RNF_EXF_RUNOFF: RNF:{1:8d} cell(s) with too much runoff at"
        f" iteration{1:10d}",
        f"RNF_EXF_RUNOFF: one step adds more than RNF_cellVolMax ="
        f"{e16_8(vol_bound)} of the cell top-layer volume",
        "RNF_EXF_RUNOFF: several sources on one cell add up here:"
        " check target_cell of the file"]
    # None of the adjacent reasons may be what stops the run. The first
    # is the point of the case: the per-source bound is NOT breached,
    # each source carries exactly the value it allows. The next four are
    # the init checks that the collapse is built to walk past, and the
    # last two are pkg/exf, whose runoff upper bound is skipped with
    # useRNF and must not be what fires.
    cell_forbid = ["runoff_flux out of range",
                   "target_cell_area differs from the cell area",
                   "target on land",
                   "fraction sum is not 1",
                   "target_lon/target_lat are not the centre",
                   "missing runoff_flux",
                   "EXF WARNING",
                   "ABNORMAL END: S/R EXF_CHECK_RANGE"]

    def collapse(flux):
        """Put every target on the first one's cell, at ``flux`` a source.

        ``target_cell_area``, ``target_lon`` and ``target_lat`` move
        with the targets, so the area and cell-centre checks of
        RNF_INIT_FIXED see a consistent entry, and ``target_fraction``
        is left alone, so every source's fractions still sum to 1. That
        is what leaves the per-cell aggregate as the only thing wrong
        with the file.
        """
        def edit(ds):
            n = len(ds.dimensions["target"])
            for name in ("target_cell", "target_cell_area",
                         "target_lon", "target_lat"):
                ds[name][:] = [ds[name][0]]*n
            ds["runoff_flux"][0, :] = flux
        return edit

    # A one-step run, for the at-the-bound companion below: a flux of
    # exactly RNF_srcFluxMax has to be applied, and over the nine steps
    # of lab_sea/input it would add 3.2e11 m^3 to one cell, i.e. 10 m
    # of water. One step is enough -- EXF_CHECK_RANGE is called at
    # nIter0 (pkg/exf/exf_getforcing.F:346-349) -- and keeps the case a
    # measurement of the guard rather than of the model's response.
    #
    # lab_sea/input runs from startTime = 3600 to endTime = 36000, so
    # ONE step is endTime = 7200 and not 3600: with 3600 the model
    # reports nTimeSteps = 0 and takes no step at all (measured), which
    # would make the run a check of initialisation only.
    with open(os.path.join(VERIF, EXPERIMENT, "input", "data")) as fh:
        data_one_step = replace_line(fh.read(), "endTime", " endTime=7200.,")
    # The control of the second half of RUNOFF-030: an out-of-range
    # evap - precip must STILL be refused, with useRNF true, now that
    # the sflux bound is tested on sflux + runoff. precipfile is
    # blanked so precipconst becomes the field, and the sparse file has
    # every flux zeroed, so the restored term is identically zero and
    # the quantity tested is exactly evap - precip. 1e-4 m/s is two
    # orders above the 1e-6 m/s sflux bound on every wet cell of every
    # tile, which is what lets this case be judged under --mpi 2: each
    # process has out-of-range cells of its own, so each prints its own
    # STOP line and none waits for another (EXF_CHECK_RANGE calls STOP
    # without ALL_PROC_DIE, so a refusal seen on one tile only could
    # not be enrolled).
    exf_wet = replace_line(
        replace_line(data_exf, "precipfile", " precipfile        = ' ',"),
        "precipperiod", " precipperiod      = 0.0,")
    exf_wet = add_to_namelist(exf_wet, "EXF_NML_03",
                              " precipconst = 1.E-4,")

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
        # The time handling of RNF_TIME_SETUP: each of these breaks one
        # rule of a valid time axis. All but the first start from the
        # valid timed file of ``timed_axis``, so the case is the one
        # violation and not an accident of the constant file.
        file_case("time_sampling",
                  ['mitgcm_time_sampling = "yearly" is not supported',
                   'has no pkg/exf mode', one_init],
                  edit=set_att(mitgcm_time_sampling="yearly")),
        # The schema marks mitgcm_time_sampling required, so a file
        # without it says nothing about how to read its records; the
        # reader must not fall back to a guess.
        file_case("time_sampling_missing",
                  ["the file has no global attribute"
                   " mitgcm_time_sampling", one_init],
                  timed={"nrec": 3, "drop": ("mitgcm_time_sampling",)}),
        # "constant" sampling with more than one record: the reader
        # would apply record 1 for ever and silently ignore the rest.
        file_case("constant_many_records",
                  ['"constant" sampling but the file has', "record(s)",
                   one_init],
                  timed={"nrec": 3},
                  edit=set_att(mitgcm_time_sampling="constant")),
        # A time variable with no units at all. Distinct from
        # time_units_bad, which has units the reader cannot parse.
        file_case("time_units_missing",
                  ["the variable time has no attribute units", one_init],
                  timed={"nrec": 3},
                  edit=del_var_att("time", "units")),
        # A reference date with a seventh number: a fraction of a
        # second or a time-zone offset, neither of which the reader
        # applies, so it is refused rather than dropped.
        file_case("ref_date_numbers",
                  ["must be YYYY-MM-DD[ hh:mm[:ss]]; it has", "number(s)",
                   one_init],
                  timed={"nrec": 3,
                         "units": "days since 1979-01-01 00:00:00.5"}),
        # A time_bnds that is not (time, nv): the reader takes the
        # repeat cycle from the first and last bound pair, which such a
        # variable does not have.
        file_case("bnds_not_2d",
                  ["time_bnds must have the dimensions (time, nv)",
                   one_init],
                  timed={"nrec": 3, "repeat": "annual", "bounds": False},
                  edit=bnds_1d()),
        file_case("time_repeat",
                  ['mitgcm_time_repeat = "biennial" is not "none" or'
                   ' "annual"', one_init],
                  timed={"nrec": 3},
                  edit=set_att(mitgcm_time_repeat="biennial")),
        file_case("time_period_missing",
                  ['"fixed" sampling needs mitgcm_time_period > 0', one_init],
                  timed={"nrec": 3},
                  edit=del_att("mitgcm_time_period")),
        file_case("time_units_bad",
                  ['time:units = "fortnights since 1979-01-01 00:00:00" is'
                   ' not understood', one_init],
                  timed={"nrec": 3,
                         "units": "fortnights since 1979-01-01 00:00:00"}),
        # Carry-forward of RUNOFF-002: a reference date before the
        # pkg/cal reference date (15 October 1582) must not be handed to
        # pkg/cal. The constant files carry 0001-01-01, which is why a
        # constant file's time axis is never read at all; a timed one
        # that carries it has to say its start date in data.rnf instead.
        file_case("ref_date_before_cal",
                  ["precedes the", "pkg/cal reference date 15821015",
                   "RNF_startDate1/RNF_startDate2", one_init],
                  timed={"nrec": 3,
                         "units": "days since 0001-01-01 00:00:00"}),
        file_case("calendar_mismatch",
                  ['calendar "360_day" of the time axis is not the'
                   ' calendar of this run', one_init],
                  timed={"nrec": 3, "calendar": "360_day"}),
        file_case("calendar_unknown",
                  ['calendar "julian" of the time axis is not one of',
                   one_init],
                  timed={"nrec": 3, "calendar": "julian"}),
        file_case("clim_no_bounds",
                  ['a "fixed" climatology (mitgcm_time_repeat = "annual")'
                   ' needs', "time_bnds: its span is the repeat cycle",
                   one_init],
                  timed={"nrec": 3, "repeat": "annual", "bounds": False}),
        # The cycle has to hold exactly one record per period: a longer
        # one wraps onto a record the file does not have and a shorter
        # one never reaches the last records.
        file_case("cycle_not_records",
                  ["repeat cycle", "is not the record count times the"
                   " period", one_init],
                  timed={"nrec": 3, "repeat": "annual"},
                  edit=set_bnd(3, 2, 3.5)),
        file_case("month_not_twelve",
                  ["a monthly climatology needs 12 records; the file has",
                   "record k is calendar month k", one_init],
                  timed={"nrec": 3, "repeat": "annual", "monthly": True}),
        # A monthly climatology is January to December in pkg/exf, which
        # ignores the start date for period -12, so a file starting in
        # another month would be read with every record shifted.
        file_case("clim_not_january",
                  ["record 1 of a monthly climatology is dated",
                   "has", "to be in January", one_init],
                  timed={"nrec": 12, "repeat": "annual", "monthly": True,
                         "first": 40.0}),
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
        # One target moved one cell in x, with target_lon/target_lat left
        # pointing at the cell it came from. The cell it lands on is wet,
        # its fractions still sum to 1 and its area is bitwise equal, so
        # the land, fraction and area checks are all blind to it: only the
        # cell-centre check sees it. ``forbid`` asserts that blindness, so
        # the case cannot pass through the area check by accident.
        file_case("target_coords",
                  ["refused target(s) on all processes", one_init],
                  ["RNF: target_lon/target_lat are not the centre of this "
                   f"cell: source {info['moved_source']},",
                   "RNF: the two centres are"],
                  edit=set_var("target_cell", info["moved_entry"],
                               info["moved_cell"])),
        # A coordinate that is not a number. Every comparison with a NaN
        # is false, so the natural "distance greater than the tolerance"
        # form accepts such a target and the summary still reports that
        # the check ran; whether it did was build-dependent (refused at
        # -O3, accepted at -O0). The check is written as a negated .LE.
        # for that reason, and this case is what holds it that way. The
        # file stays schema-valid: MITgcmutils.runoff.check passes it.
        file_case("target_coords_nan",
                  ["refused target(s) on all processes", one_init],
                  ["RNF: target_lon/target_lat are not the centre of this "
                   f"cell: source {ids[0]},",
                   "RNF: the two centres are"],
                  edit=set_var("target_lon", 0, float("nan"))),
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
        # Twice RNF_srcFluxMax: present, finite, far below the
        # missing-value sentinel RNF_fluxMax, and refused for its
        # magnitude alone. This is the case that makes the pkg/exf
        # relaxation safe, so its ``forbid`` list (set below) excludes
        # every adjacent reason it could pass for.
        file_case("flux_above_source_max", over_msg, stop=stop_flux,
                  edit=set_var("runoff_flux", (0, 0), 2.0*flux_bound)),
        # The per-cell aggregate (RUNOFF-040), which RNF_srcFluxMax
        # cannot see at all: four sources each carrying EXACTLY the
        # value it allows, with every target collapsed onto one cell.
        # Measured on the build before this check existed: the run
        # ended normally with exit 0, no message of any kind and no
        # EXF WARNING, applying 1.2852284E-03 m/s -- 1285 times the
        # pkg/exf runoff bound that useRNF skips -- at the one
        # non-zero cell. Its route is a converter index bug collapsing
        # sources, which is on this project's own highest-risk list,
        # and N is 10^5 to 10^6 in the intended case.
        # The messages the owning process prints name the cell, the
        # applied value and the limit, which is what locates the
        # collapsed target; the tally and the two lines after it are
        # printed by every process, because the count is reduced
        # before the stop so that a refusal on one tile stops them all.
        {"name": "cell_above_vol_max",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad,
                   "data": data_one_step},
         "nc": {"bad.nc": {"edit": collapse(flux_bound)}},
         "stderr": cell_tally, "stderr_any": cell_msg,
         "stdout": [],
         # the record was read and applied: the refusal is about the
         # aggregate on the cell and not about rejecting the record
         "flux_sum": flux_bound*len(ids),
         "stop": "ABNORMAL END: S/R RNF_EXF_RUNOFF",
         "forbid": cell_forbid},
        # The control of the sflux half of RUNOFF-030: with useRNF
        # true and NO runoff at all, an out-of-range evap - precip
        # must still stop the run. The sflux bound is now tested on
        # sflux + runoff, and this is the case that holds it to being
        # a restore rather than a removal: a diff that dropped the
        # test when useRNF would pass everything else here.
        # The precip bound fires as well at 1e-4 m/s, and both
        # messages are asserted so neither can vanish unnoticed; what
        # makes the case decisive for sflux is the presence of the
        # sflux line, because a removed sflux test would leave the
        # precip line and the stop exactly as they are.
        {"name": "sflux_out_of_range",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad,
                   "data": data_one_step, "data.exf": exf_wet},
         "nc": {"bad.nc": {"edit": scale_var("runoff_flux",
                                             slice(None), 0.0)}},
         "stderr": [], "stdout": ["EXF WARNING: sflux out of range",
                                  "EXF WARNING: precip out of range",
                                  "EXF WARNING: then set"
                                  " useExfCheckRange=.FALSE."],
         "stop": "ABNORMAL END: S/R EXF_CHECK_RANGE",
         "forbid": ["EXF WARNING: runoff out of range",
                    "m/s not m/yr",
                    "runoff_flux out of range"]},
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
        # RNF_startTime is the override for a run without pkg/cal; with
        # pkg/cal the start time comes from the file or from
        # RNF_startDate1/2, as it does for a dense exf field
        # (pkg/exf/exf_getffield_start.F).
        file_case("start_time_with_cal",
                  ["RNF_startTime cannot be set with pkg/cal (useCAL=T)",
                   "RNF_startDate1/RNF_startDate2", one_init],
                  timed={"nrec": 3},
                  rnf=DATA_RNF.format("bad.nc").replace(
                      " &\n", "  RNF_startTime = 0.,\n &\n")),
        # A non-repeating series that ends before the run does: at the
        # first step the bracket already needs record 2 of a one-record
        # file. The header is valid, so this is refused where the record
        # is read and not at init.
        file_case("record_out_of_range",
                  ["record", "is outside the", "record(s) of bad.nc",
                   "the series does not cover the model time"],
                  stop=stop_flux,
                  timed={"nrec": 1}),
        # A yearly set with a repeat cycle, which exf does not allow
        # (pkg/exf/exf_check.F refuses useExfYearlyFields with a repeat
        # period). This case exists because the limit recorded for it in
        # round 0 -- that the _YYYY file is opened before the check, so
        # the guard is unreachable -- was false: the file of the start
        # year exists, so it opens normally and the guard fires. It runs
        # on the committed yearly set-up, not on a generated file,
        # because what is broken is a data.rnf combination and not the
        # file (review B of RUNOFF-005, correction round 1).
        {"name": "yearly_repcycle",
         "copy_from": "input.rnof_sp_yearly",
         "copy": {name: None for name in ("data", "data.cal", "data.exf")},
         "files": {"data.pkg": pkg_on, "data.rnf": DATA_RNF_YEARLY},
         "stderr": ["RNF_TIME_SETUP: RNF: RNF_useYearlyFiles=.TRUE. allows"
                    " no repeat cycle", one_init],
         "stdout": [], "stop": stop_init, "forbid": forbid_file},
        # A runoff tracer whose name matches no ptracer (RUNOFF-013).
        # There is nothing to add the tracer to, so the water would
        # arrive without it and nothing in the log would say so; the
        # run stops instead. The control ptracer_match below has the
        # same file with the name the ptracer really has, so this
        # refusal cannot be passing for the mere presence of a tracer
        # variable.
        {"name": "ptracer_unknown",
         "files": {"data.pkg": pkg_ptr, "data.rnf": rnf_bad,
                   "data.ptracers": DATA_PTRACERS,
                   "data.longstep": DATA_LONGSTEP},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_ghost", 1.0)}},
         "stderr": ["RNF_NC_SERIES: RNF: runoff_ptracer_ghost: no"
                    " PTRACERS_names entry matches",
                    "RNF_NC_SERIES: ptracer   1 is called dye", one_init],
         "stdout": [], "stop": stop_init, "forbid": forbid_file},
        # The same file in a run that does not use pkg/ptracers at all:
        # refused for that reason, and named, rather than read and
        # dropped.
        {"name": "ptracer_off",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_dye", 1.0)}},
         "stderr": ["RNF_NC_SERIES: RNF: runoff_ptracer_dye: the file has"
                    " runoff tracers but pkg/ptracers is not in use",
                    one_init],
         "stdout": [], "stop": stop_init, "forbid": forbid_file},
        # The name checks that come before the ptracer matching: a
        # variable called exactly ``runoff_ptracer_`` leaves no name
        # after the prefix, and one whose name is longer than
        # RNF_idLen = 64 would not fit RNF_trNam. Both are reached with
        # pkg/ptracers switched off, because RNF_NC_SERIES tests the
        # length before it looks at usePTRACERS, so neither case needs
        # a second build or a second ptracer. (Correction round 1: the
        # matrix had recorded all five of these series refusals as
        # unenrolled with their reachability "read from the source and
        # not measured"; review B fired three of them by hand and these
        # two are the first two.)
        {"name": "ptracer_name_empty",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_", 1.0)}},
         "stderr": ["RNF_NC_SERIES: RNF: runoff_ptracer_: the tracer name"
                    " after the prefix runoff_ptracer_ is empty",
                    one_init],
         "stdout": [], "stop": stop_init,
         # it must not be refused for one of the later reasons instead,
         # which would make the case a measurement of those
         "forbid": forbid_file + ["no PTRACERS_names entry matches",
                                  "pkg/ptracers is not in use",
                                  "the tracer name is longer than"]},
        {"name": "ptracer_name_long",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_"
                                              + "d"*(id_bound + 1), 1.0)}},
         "stderr": [f"RNF_NC_SERIES: RNF: runoff_ptracer_"
                    f"{'d'*(id_bound + 1)}: the tracer name is longer"
                    f" than{id_bound:6d}", one_init],
         "stdout": [], "stop": stop_init,
         "forbid": forbid_file + ["no PTRACERS_names entry matches",
                                  "pkg/ptracers is not in use",
                                  "the tracer name after the prefix"]},
        # More runoff tracer variables than RNF_nTr = 5, which is the
        # capacity of RNF_trNam/RNF_trPtr. The count is taken over every
        # variable carrying the prefix, after the two name checks and
        # before the matching, so the refusal does not depend on the
        # names matching anything -- which is just as well, because with
        # PTRACERS_num = 1 six matching names are impossible, so no
        # reachable witness of this bound can be free of companion
        # errors. With pkg/ptracers switched off each of the six
        # variables also raises the "not in use" error, so the tally is
        # 6 + 1 = 7; the capacity message is what this case measures and
        # the tally is asserted so that the companion errors cannot grow
        # or vanish unnoticed.
        {"name": "ptracer_too_many",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": several(*[
             add_series(f"runoff_ptracer_t{k:02d}", 1.0)
             for k in range(tr_bound + 1)])}},
         "stderr": [f"RNF_NC_SERIES: RNF: RNF_nTr ={tr_bound:6d} is too"
                    f" small: the file has{tr_bound + 1:6d} runoff"
                    f" tracer(s)", n_init(tr_bound + 2)],
         "stdout": [], "stop": stop_init, "forbid": forbid_file},
        # The complement of the three cases above: the same three
        # guards **at** the bound, where each must stay silent. A
        # mutant that weakens a guard cannot test this direction; these
        # are what hold `.GT.` back from becoming `.GE.` (and
        # `nTrLen .LT. 1` from `.LT. 2`). One character after the prefix
        # is the shortest name the empty-name test admits, RNF_idLen
        # characters the longest the length test admits, and RNF_nTr
        # variables the most the capacity test admits.
        #
        # What makes each one decisive is *which* error it does raise:
        # with pkg/ptracers switched off, a name that gets past both
        # name checks reaches the usePTRACERS test (rnf_nc_utils.F:637,
        # after the checks at :618 and :626) and is refused there,
        # naming the variable. So the expected message is itself the
        # proof that control went past the guard under test -- a
        # `forbid` list alone would also be satisfied by a run that
        # never reached the matching at all. The first two differ from
        # `ptracer_name_empty`/`ptracer_name_long` in exactly one
        # character of the variable name, and nothing else.
        # (Review B of correction round 1 offered all three; enrolled in
        # round 2.)
        {"name": "ptracer_name_min",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_d", 1.0)}},
         "stderr": ["RNF_NC_SERIES: RNF: runoff_ptracer_d: the file has"
                    " runoff tracers but pkg/ptracers is not in use",
                    one_init],
         "stdout": [], "stop": stop_init,
         "forbid": forbid_file + ["the tracer name after the prefix",
                                  "the tracer name is longer than",
                                  "is too small: the file has"]},
        {"name": "ptracer_name_max",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_"
                                              + "d"*id_bound, 1.0)}},
         "stderr": [f"RNF_NC_SERIES: RNF: runoff_ptracer_{'d'*id_bound}:"
                    f" the file has runoff tracers but pkg/ptracers is"
                    f" not in use", one_init],
         "stdout": [], "stop": stop_init,
         "forbid": forbid_file + ["the tracer name after the prefix",
                                  "the tracer name is longer than",
                                  "is too small: the file has"]},
        # Exactly RNF_nTr variables: nTrFile reaches the bound and the
        # capacity test must not fire. Each of the five raises the "not
        # in use" error of :637, so the tally is RNF_nTr and not
        # RNF_nTr + 1 -- which is what distinguishes this case from
        # `ptracer_too_many` by one error rather than by a wording.
        {"name": "ptracer_count_max",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"edit": several(*[
             add_series(f"runoff_ptracer_t{k:02d}", 1.0)
             for k in range(tr_bound)])}},
         "stderr": ["RNF_NC_SERIES: RNF: runoff_ptracer_t00: the file has"
                    " runoff tracers but pkg/ptracers is not in use",
                    f"RNF_NC_SERIES: RNF: runoff_ptracer_t{tr_bound - 1:02d}:"
                    f" the file has runoff tracers but pkg/ptracers is not"
                    f" in use", n_init(tr_bound)],
         "stdout": [], "stop": stop_init,
         "forbid": forbid_file + ["the tracer name after the prefix",
                                  "the tracer name is longer than",
                                  "is too small: the file has"]},
    ]
    # The flux is read in RNF_INIT_VARIA, after RNF_CHECK has passed; the
    # flux sums are printed only if the whole record was accepted.
    for case in out:
        if case["stop"] in (stop_flux, "ABNORMAL END: S/R RNF_NC_ATT_REAL"):
            case["forbid"] = ["RNF_INIT_VARIA: runoff flux"]
    next(c for c in out if c["name"] == "fraction_hidden")["forbid"] = \
        forbid_file + ["fraction sum is not 1"]
    # The point of target_coords: the checks that came before it cannot see
    # a one-cell move. If any of them fires, the case is no longer the
    # measurement it claims to be.
    next(c for c in out if c["name"] == "target_coords")["forbid"] = \
        forbid_file + ["target_cell_area differs from the cell area",
                       "target on land", "fraction sum is not 1"]
    # The NaN case must not be let through by the skip path either: if the
    # check had been skipped, the summary would say so and the run would
    # end normally, which "refused target(s)" above already excludes.
    next(c for c in out if c["name"] == "target_coords_nan")["forbid"] = \
        forbid_file + ["the target cell centres are not checked against"]
    # The magnitude refusal must be the package's own and not any of
    # the three things it sits between: the missing-value tests that
    # share the loop (the value is present and finite), the record
    # being accepted at all, and the pkg/exf range check, whose runoff
    # upper bound is skipped here and must not be what stops the run.
    next(c for c in out if c["name"] == "flux_above_source_max")["forbid"] = [
        "RNF_INIT_VARIA: runoff flux",
        "missing runoff_flux",
        "missing value(s) of runoff_flux",
        "EXF WARNING: runoff out of range"]

    # Runs that must end normally.
    no_error = list(MESSAGES.values()) + ["fatal error(s)", "ABNORMAL END"]
    stdout_ok = ["pkg/rnf", "Sparse runoff (RNF) configuration >>> START",
                 PASSED]
    # The five "which bounds applied" lines of RNF_SUMMARY, asserted on every
    # normal-end case. ("Four" until RUNOFF-040 added the per-cell line
    # below; this comment went on saying four for a whole issue, and RUNOFF-042
    # measured why rather than inheriting the explanation that stood here.
    # It was NOT a sweep skipping .py. The stale-figure sweep reads the
    # documentation inventory, which is `test_paths: ["tests"]` in
    # esx/project.json -- unchanged since before RUNOFF-040 -- and lists this
    # file among 66 .py entries. What missed was the figure TOKEN: RUNOFF-040
    # recorded the rows "four lines", "four RNF_SUMMARY lines" and
    # "four `RNF_SUMMARY`", and this wording puts the quoted phrase between
    # the number and its noun, so none of them matches here, while both .md
    # twins said "four lines" contiguously and were listed and fixed. A row of
    # plain "four" matches this line (measured). The footprint sweep of
    # tests/footprint_claim_sweep.py never saw it either, with .py in SUFFIXES
    # or without, because the line carries no exclusivity marker at all.)
    # Review B of RUNOFF-030 correction round 2 found them unenrolled:
    # nothing observed them, so deleting the whole report would have failed
    # no case, and its own inertness argument cuts both ways -- the lines are
    # inert because nothing reads them. They exist so that a reader of
    # STDOUT.0000 can tell which runoff bounds a run was held to after
    # RUNOFF-030 conditioned two exf tests on useRNF, which is exactly the
    # kind of claim this project does not leave unmeasured.
    bounds_report = [
        "RNF_SUMMARY: pkg/exf skips its runoff upper bound (1.E-6 m/s)",
        "RNF_SUMMARY: RNF_NC_READ_ONE refuses a source flux above"
        " RNF_srcFluxMax =",
        "RNF_SUMMARY: its sflux bound tests sflux+runoff, i.e. evap-precip,"
        " with useRNF=.TRUE.",
        "RNF_SUMMARY: the negative-runoff test of EXF_CHECK_RANGE still"
        " applies per cell (at nIter0)",
        # RUNOFF-040: the per-cell aggregate bound, which is the one of
        # the five that is checked on every step of every run
        "RNF_SUMMARY: RNF_EXF_RUNOFF refuses a cell above"
        " RNF_cellVolMax ="]
    stdout_ok = stdout_ok + bounds_report
    dense = {name: None for name in ("data", "data.exf")}
    out += [
        {"name": "positive_control",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_ok},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "summary": {"RNF_file": f"'{SPARSE_REL}'",
                     "RNF_nSrcFile": str(len(ids)), "RNF_nTgtOwned": "7",
                     # the file has target_lon/target_lat and the grid is
                     # spherical polar, so the cell-centre check must have
                     # run on this control rather than be skipped
                     "RNF_lonLatChk": "T"},
         "flux_sum": info["flux_sum"], "stop": "ABNORMAL END",
         "forbid": no_error},
        # The control of the two runoff-tracer refusals above: the same
        # file, with the name the ptracer really has. It must run, report
        # the match, and apply the term, which is the only case that
        # reaches RNF_TENDENCY_APPLY_PTR at all. Without it, both
        # refusals could be refusing every tracer variable and would
        # still pass.
        {"name": "ptracer_match",
         "files": {"data.pkg": pkg_ptr, "data.rnf": rnf_bad,
                   "data.ptracers": DATA_PTRACERS,
                   "data.longstep": DATA_LONGSTEP},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_dye", 2.0)}},
         "normal_end": True, "stderr": [], "stdout": stdout_ok + [
             "RNF_SUMMARY: runoff tracer  1 is runoff_ptracer_dye,"
             " applied to ptracer  1"],
         "summary": {"RNF_nTrUse": "1", "RNF_usePtracers": "T"},
         "flux_sum": info["flux_sum"], "stop": "ABNORMAL END",
         "forbid": no_error},
        # The counterfactual of the two refusals: the same unmatched
        # name with RNF_usePtracers switched off, which is the
        # documented way to read such a file on purpose. The run goes
        # through and says what it did not apply, which is what the
        # reader did for every property before RUNOFF-013 -- so this
        # case is the measurement of what the guard changed, and of the
        # switch having an effect at all, which it did not before.
        {"name": "ptracer_ignored",
         "files": {"data.pkg": pkg_on,
                   "data.rnf": add_to_namelist(
                       rnf_bad, "RNF_PARM01",
                       "  RNF_usePtracers = .FALSE.,")},
         "nc": {"bad.nc": {"edit": add_series("runoff_ptracer_ghost", 1.0)}},
         "normal_end": True, "stderr": [], "stdout": stdout_ok + [
             "RNF_NC_SERIES: runoff_ptracer_ghost is in the file and"
             " RNF_usePtracers is false:"],
         "summary": {"RNF_nTrUse": "0", "RNF_usePtracers": "F"},
         "flux_sum": info["flux_sum"], "stop": "ABNORMAL END",
         "forbid": no_error},
        # The at-the-bound companion of flux_above_source_max, and the
        # acceptance of RUNOFF-030 as a whole. The first source carries
        # exactly RNF_srcFluxMax, so:
        #   o the pkg/rnf magnitude guard must stay silent, which is
        #     what holds its `.GT.` back from becoming a `.GE.` -- the
        #     direction a weakened-bound mutant cannot measure -- and
        #     the record must then be applied, which the flux sums
        #     assert;
        #   o the applied field at that cell is 3.21e-4 m/s, 321 times
        #     the 1e-6 m/s pkg/exf allows, and the run must end
        #     normally with useExfCheckRange at the lab_sea default
        #     .TRUE. That takes BOTH relaxations: the runoff upper
        #     bound skipped, and the sflux bound tested on
        #     sflux + runoff. Measured against a build with either one
        #     reverted, this case fails.
        #   o neither the runoff nor the sflux warning may be printed,
        #     and nor may the m/yr advice, which with useRNF could only
        #     be triggered by a negative value and names
        #     exf_inscal_runoff, a parameter that does not touch the
        #     sparse field.
        # One time step, from a data with endTime=7200.: lab_sea/input
        # starts at 3600, so 7200 is one step and 3600 would be zero
        # steps (measured), which would never reach EXF_CHECK_RANGE.
        {"name": "flux_at_source_max",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad,
                   "data": data_one_step},
         "nc": {"bad.nc": {"edit": set_var("runoff_flux", (0, 0),
                                           flux_bound)}},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "summary": {"RNF_nSrcFile": str(len(ids)), "RNF_nTgtOwned": "7",
                     # the parameter line of the bound this case sits at, so
                     # the reported value and the enforced one cannot drift
                     # apart unnoticed (review B, correction round 2).
                     # WRITE_0D_RL prints 15 decimals, not the 8 of the
                     # 1PE16.8 messages, so this is not e16_8: measured
                     # "1.000000000000000E+07" in a run's own output.
                     "RNF_srcFluxMax": f"{flux_bound:.15E}"},
         "flux_sum": info["flux_sum"] - info["flux0"] + flux_bound,
         "stop": "ABNORMAL END",
         "forbid": no_error + ["out of range", "m/s not m/yr"]},
        # The negative control of cell_above_vol_max: the same collapse
        # onto the same cell, sized so that the aggregate is 0.99 of
        # RNF_cellVolMax instead of 2.31 times it. The guard must stay
        # silent and the record must then be applied, which the flux
        # sums assert. It is the tightest configuration in this file
        # that must still run: it applies 0.99 of the 5.5556e-4 m/s the
        # bound allows on this cell, where flux_at_source_max applies
        # 3.21e-4 m/s, i.e. 0.578 of it -- so this case sits 1.7 times
        # nearer the bound. The witness, for scale, is 2.31 times OVER
        # the bound and a factor of 4 above flux_at_source_max.
        #
        # A MARGIN AS THIN AS 0.99 IS ONLY SAFE BECAUSE lab_sea IS A
        # LINEAR FREE SURFACE (nonlinFreeSurf = 0, select_rStar = 0), so
        # nothing updates hFacC at run time and the thickness the guard
        # divides by is the reference 10 m at every step -- which is
        # also why cell_above_vol_max can assert
        # "top-layer thickness 1.00000000E+01 m" as a literal. Moving
        # either case to an r* grid would void both: 26% of cs32's
        # target cells run more than 1% thinner than their reference
        # (measured), so this control would be REFUSED there. Size any
        # future per-cell control from the live thickness.
        #
        # What this case does NOT do is pin the `.LE.` of the guard
        # against a `.LT.`, the way ptracer_name_max pins its length
        # test. A control exactly at the bound would have to make
        # ABS(vflx)*deltaTFreeSurf land on the last bit of
        # RNF_cellVolMax*drF*hFacC, a product of three reals the
        # compiler is free to round its own way, so it would measure
        # rounding rather than the guard. The direction does not carry
        # a promise here either: RNF_cellVolMax is a round safety
        # share, not a value a file may sit on, which RNF_srcFluxMax
        # (where the at-the-bound direction IS a promise) is.
        {"name": "cell_at_vol_max",
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad,
                   "data": data_one_step},
         "nc": {"bad.nc": {"edit": collapse(at_vol_flux)}},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "summary": {"RNF_nSrcFile": str(len(ids)), "RNF_nTgtOwned": "7",
                     # the parameter line of the bound this case sits
                     # under, so the reported value and the enforced
                     # one cannot drift apart unnoticed; WRITE_0D_RL
                     # prints 15 decimals, as for RNF_srcFluxMax above
                     "RNF_cellVolMax": f"{vol_bound:.15E}"},
         "flux_sum": at_vol_flux*len(ids),
         "stop": "ABNORMAL END",
         "forbid": no_error + ["out of range", "m/s not m/yr",
                               "too much runoff"]},
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
        # Two sources on every cell: the only case in which the model adds
        # two contributions into one cell. Overwriting instead of adding
        # would apply a third or two thirds of the runoff, which the dense
        # comparison sees (the zero-flux control above matches to 2 digits).
        {"name": "two_sources_one_cell",
         "copy_from": DENSE_INPUT, "copy": dense,
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"split_from": CELLS}},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "summary": {"RNF_nSrcFile": "14", "RNF_nTgtFile": "14",
                     "RNF_nTgtOwned": "14"},
         "flux_sum": info["flux_sum"], "digits": (DENSE_REF, 13, 99),
         "stop": "ABNORMAL END", "forbid": no_error},
        # Three sources on every cell, sized by ulp_shares so that the
        # three-term sum is order-sensitive. Here that only asserts that
        # a three-way split still gives the dense run: the one-ulp
        # difference the sizing creates is far below any digit
        # threshold. What tests the order itself is the bitwise case
        # order_sensitive_sum of tests/rnf/applied_field_check.py, which
        # uses the same generator.
        {"name": "three_sources_one_cell",
         "copy_from": DENSE_INPUT, "copy": dense,
         "files": {"data.pkg": pkg_on, "data.rnf": rnf_bad},
         "nc": {"bad.nc": {"split_from": CELLS, "split_ulp": ULP_SHARE}},
         "normal_end": True, "stderr": [], "stdout": stdout_ok,
         "summary": {"RNF_nSrcFile": "21", "RNF_nTgtFile": "21",
                     "RNF_nTgtOwned": "21"},
         "flux_sum": info["flux_sum"], "digits": (DENSE_REF, 13, 99),
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
