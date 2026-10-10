#!/usr/bin/env python3
"""Analytic single-cell check of the runoff surface terms (RUNOFF-013, -008, -031).

What this checks
================

Since RUNOFF-031 ``pkg/rnf`` puts the runoff heat, salt and tracers of a
surface target into the surface flux fields the rest of the surface
forcing uses (decisions 3 and 4 of ``docs/package_design.md``):

* heat: ``RNF_EXF_RUNOFF`` sets the exf ``runoftemp`` field to
  ``[(mT) + (m - m_T)*theta]/m`` and ``EXF_MAPFIELDS`` adds
  ``Cp*(theta - runoftemp)*runoff*rhoConstFresh`` to ``Qnet``, i.e. the
  temperature term ``[(mT) - m_T*theta]*mass2rUnit`` once
  ``surfaceForcingT -= Qnet*mu/Cp``;
* salt and tracer: ``RNF_FORCING_SURF`` adds
  ``[(mX) - m*X_ref]*mass2rUnit`` to ``surfaceForcingS`` and
  ``surfaceForcingPTr``,

each applied at the surface level as ``... * recip_drF(1) *
recip_hFacC``. ``X_ref`` is the property the model's own freshwater
formulation has already given this water (for heat the exf block
assumes ``theta``), so that the contributions -- the model's, pkg/exf's
``temp_EvPrRn`` term through ``Qnet`` and the package's -- add up to the
total of the decision-3 tables. Those tables give the references per
freshwater branch and the total each case adds up to; this script
measures both columns of both tables on a model run:

* the **package term**, against the diagnostics the package fills where
  it computes the term: ``RNFqnet`` (W/m^2, ``Qnet``'s sign),
  ``RNFsflx`` (g/m^2/s) and ``RNFtf01``, each against the analytic
  surface flux. This is the "Package" column.
* the **total**, against the same run with the runoff flux set to zero.
  ``TOTTTEND`` and ``TOTSTEND`` are the model's own state tendencies,
  ``(theta^n - theta^(n-1))/dt``, so the difference of the two runs over
  one step is exactly the sum of every runoff contribution *provided the
  two runs enter that step in the same state*: every other term is then
  bitwise the same, and ``tracForcingOutAB = 1`` (the MITgcm default,
  confirmed from each run's own parameter dump) keeps the forcing out of
  the Adams-Bashforth extrapolation, so the state change over the step
  is ``dt`` times the tendency. This is the "Total" column.

  **The step this measures is the second one, not the first.** Each run
  writes exactly one snapshot, labelled ``0000000001`` with
  ``timeStepNumber = 1``; that label is the write slot, not the step
  whose tendency the snapshot holds. Measured on a retained ``L_set``
  pair: the snapshot's value is ``8.313059890300034e-05`` degC/s and the
  run's own ``(theta^2 - theta^1)/dt`` is ``8.313059890300037e-05``,
  equal to 1 ulp, while ``(theta^1 - theta^0)/dt`` is
  ``-4.5143400080746266e-06`` and does not match. The second step is
  also the only one that *could* be measured: record 1 of every case's
  file is dry in both runs (see :func:`write_sparse`), so the first step
  is bitwise identical in the two runs -- their ``theta^1`` differ by
  exactly 0.0 -- and differencing it would measure nothing at all.
  :func:`judge` asserts that identity on the state dumps rather than
  assuming it, which is the same-state-on-entry premise the total rests
  on.

The passive tracer (RUNOFF-008)
-------------------------------

Every case also carries one passive tracer, ``rnfdye``, and is judged on
the same two columns for it (:func:`judge_tracer`), against the four
rows of :data:`C_ROWS`: ``PTRACERS_EvPrRn`` set or unset, in branch L or
U. The **package** column is the ``RNFtf01`` diagnostic against
:func:`expected_tracer`, with ``C_ref`` chosen as
``RNF_FORCING_SURF_PTR`` chooses it (``rnf_forcing_surf.F:278-289``)
and the local tracer read from the run's own ``PTRACER01`` dump of the
step before. The **total** is the two-run difference of ``Tp_gTr01``.
On lab_sea the term reaches the tracer through pkg/longstep, whose
``LONGSTEP_FORCING_SURF`` rebuilds ``surfaceForcingPTr`` before every
ptracer step and re-adds the package term (RUNOFF-031: a hook only after
``PTRACERS_FORCING_SURF`` would be erased there).

Which quantity is the tracer's total was measured, not assumed, because
lab_sea compiles pkg/longstep, which takes the ptracer step over
(``model/src/thermodynamics.F:6`` compiles the ordinary call out;
``LONGSTEP_THERMODYNAMICS`` is called from ``forward_step.F:700-722``)
and recomputes the tracer's surface forcing in ``LONGSTEP_FORCING_SURF``
from the long-step average of ``EmPmR`` rather than in
``PTRACERS_FORCING_SURF``. Measured on retained ``L_set``/``L_unset``
pairs with ``LS_nIter = 1``, ``LS_whenToSample = 0``: the two-run
difference of the ``Tp_gTr01`` snapshot labelled ``0000000001`` equals
the run's own ``((C^2 - C^1) - (C^2 - C^1)_zero)/dt`` from the state
dumps to the last bit (``7.037939279056123e-06`` on ``L_unset``), so the
long step neither moves the measured step nor leaves ``Tp_g`` unfilled;
``ForcTr01``'s difference matches the analytic total to 0.0 relative and
is reported beside it (``total_C_candidates``), as is the state
difference. ``Tp_g`` is the one used because it is the tracer's own
state change, the same quantity ``TOTTTEND`` is for theta.

The initial tracer, ``PTRACERS_ref``, ``PTRACERS_EvPrRn`` and the source
concentrations are all distinct (:data:`TRC0`), and :func:`judge_tracer`
requires the measured package term to be at least ``RTOL *
DISCRIMINATION`` away from the term every *other* reference would have
given (the other arms, the initial tracer, zero): measured, the
smallest such margin over the eight cases is 8.3e-2. Both columns were
also measured failing on mutant binaries, first on the tendency route
(RUNOFF-008) and again on the surface route (RUNOFF-031, mutants built
into separate binaries and run with ``--use-build``): with the branch-L
tracer arm made to use ``PTRACERS_ref``, ``L_unset`` fails both columns
at 2.222e-01; with the local-salinity arm made to use 0, ``L_set``
fails both at 1.172; with the theta that stands in for a missing
temperature dropped from ``runoftemp``, ``missing_temp`` fails both at
1.995; ``U_set``, which reaches none of the three, passes on that same
binary. With every applied term's sign flipped and the diagnostics left
alone, the package column stays at 0.00e+00 on all four ``_set``/
``_unset`` cases while the total fails on every property, at 3.33e-01
to 9.34 -- the RUNOFF-013 lesson that the package column alone is blind
to what was applied.

Adding pkg/ptracers to these runs changes nothing for T and S: every
measured and expected T and S figure, and the theta and salt the
measured step starts from, are bitwise identical to the same eight cases
run without it (RUNOFF-008).

Why the oracle is analytic
--------------------------

Each case is two runs of ``STEPS`` steps from iteration 0 with a uniform
initial state written by this script (``hydrogThetaFile``,
``hydrogSaltFile``). The oracle does **not** evaluate the term at that
uniform value: :func:`expected` reads the ``theta`` and ``salt`` it uses
out of the run's own iteration-1 state dump, which is the state the
measured second step starts from, so the comparison is made against the
state the model actually had rather than one assumed for it. What the
uniform start supplies is a premise that can be *measured* --
:func:`judge` requires the run's own iteration-0 dump to hold exactly
the values this script wrote, so a case cannot be judged against an
initial condition the model never read -- and it puts the target cell in
a column of known, constant properties, which is what makes the
iteration-1 state a clean number to difference against.
``pkg/seaice``, ``pkg/kpp`` and ``pkg/gmredi`` are
switched off: the first two read ``Qnet`` and ``surfaceForcingT``, which
carry part of the runoff heat, so with them on the difference of two
runs would include their indirect response and would no longer be the
sum of the three terms.

Everything else in the expected value is taken from the run: the cell
area from its ``RAC.data``, the layer thickness from ``delR`` of its own
``data``, ``hFacC`` from its ``hFacC.data``, and ``rhoConst``,
``rhoConstFresh``, ``tRef(1)``, ``temp_EvPrRn``, ``salt_EvPrRn`` and
``convertFW2Salt`` from the parameter dump the model prints -- and, for
the tracer, ``PTRACERS_ref`` and ``PTRACERS_EvPrRn`` -- so that a case
cannot pass against a setting it did not actually run.

The two rows without ``ALLOW_ATM_TEMP``
-------------------------------------------

Since RUNOFF-031 the totals of rows T3 and T6 are the dense
``runoftempfile`` path's: nothing cancels the model's own
``temp_EvPrRn`` term for the runoff in that build, and the exf
``runoftemp`` term assumes the water arrives at ``theta``, so the total
is ``[(mT) - m*theta]*mu*D`` plus the model's ``m*(temp_EvPrRn -
theta)*mu*D`` (L) or ``m*(temp_EvPrRn - tRef)*mu*D`` (U). The tendency
route delivered the source heat there by using ``T_ref = temp_EvPrRn``;
following the exf convention gives that up, which is recorded in
decision 3 of the package design. :func:`expected` sums the three
columns as before, so these rows measure the new algebra rather than
assume it.

Coverage, and what a passing run does not establish
---------------------------------------------------

The ``rows`` field of each case names the table rows it covers, and
:func:`main` fails if any row of :data:`T_ROWS`, :data:`S_ROWS` or
:data:`C_ROWS` is left uncovered, so the set cannot silently shrink. Every case needs a build with
``ALLOW_RUNOFTEMP`` defined, which the runoff heat goes through, and two
rows need one with ``ALLOW_ATM_TEMP`` undefined as well, where pkg/exf
does not cancel the model's own term: they are the cases with
``atm_temp`` false. ``--build``
compiles that binary, and the ordinary one, when either is missing or
older than its sources (:func:`build_if_stale`); without ``--build`` a
missing binary is reported with its compile command and the run exits
2. There is no flag that lets a run
report success with a row no case exercised.

A passing run establishes the terms at one cell, at one level, in a
linear free surface (branches L and U), for one time step, for
temperature, salinity and one passive tracer. It does not establish the
branch-N algebra (RUNOFF-014) -- for tracers no more than for T and S,
which is why :data:`C_ROWS` has no N row -- the budget over many steps
or many cells (RUNOFF-016, ``tests/rnf/budget_check.py``), the mapping of
several runoff tracers onto several ptracers (one tracer here, since the
ordinary lab_sea build has ``PTRACERS_num = 1``; that is
``budget_check``'s two-tracer case), or the lagged time level, which no
verification experiment configures. In the two local-arm rows the tracer
at the target cell is still exactly :data:`TRC0` when the measured step
starts (nothing moves a uniform tracer there over the dry first step),
so those rows tell the local arm from the other arms but not the local
tracer of that step from the initial one.

Usage
=====

    python3 tests/rnf/tendency_term_check.py --build   # self-contained
    python3 tests/rnf/tendency_term_check.py [--case NAME] [--keep]

The second form needs the binaries to exist already, from ``--build``.
``--use-build NAME`` runs every selected case on another lab_sea build,
for the must-fail demonstrations on mutant binaries.

Exit status: 0 if every case passes, 1 if one fails or a table row has
no passing case, 2 if a binary is missing or could not be built, or a
selection does not exist.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (ROOT, VERIF, add_to_namelist,  # noqa: E402
                           kill_run, read_file, replace_line, sparse_info)
from applied_field_check import set_namelist  # noqa: E402

EXPERIMENT = "lab_sea"
#: The scratch input directories this check writes, one per run.
PREFIX = "input.rnfterm_"
#: Binary of the ordinary build, and of a build with ALLOW_ATM_TEMP undefined.
#: Both define ALLOW_RUNOFTEMP, which the committed pkg/exf option file
#: leaves undefined and which the runoff heat needs since RUNOFF-031: it
#: goes through the exf runoftemp field (``RNF_CHECK`` refuses a file
#: with ``runoff_temperature`` in a build without it). The ordinary one
#: is the binary ``tests/rnf/exf_heat_check.py`` uses as well.
BUILD = "build_esx_roft"
NOATM_BUILD = "build_esx_noatm"
#: Code directories of those builds, written by :func:`write_roft_code`
#: and :func:`write_noatm_code`.
ROFT_CODE = "code_rnfterm_roft"
NOATM_CODE = "code_rnfterm_noatm"
#: Name of the sparse file each case writes into its scratch input.
SPARSE_FILE = "runoff_term.nc"
#: The uniform initial state. Both are exact in float32, which is what
#: readBinaryPrec = 32 of lab_sea/input/data reads.
THETA0 = 2.0
SALT0 = 34.0
#: Initial-condition file names.
THETA_FILE = "theta0_rnfterm.bin"
SALT_FILE = "salt0_rnfterm.bin"
#: Total source flux into the one target cell [m^3/s]. Large on purpose:
#: the term has to dominate the round-off of the state difference the
#: TOTTTEND diagnostic is built from. With the lab_sea cell area
#: (3.112287e10 m^2 at the target of ``sparse_info()["wet_cell"]``) this
#: is 3.21e-5 m/s, 32 times the 1e-6 m/s the pkg/exf range check allows.
#: The cases used to switch ``useExfCheckRange`` off for that reason.
#: They no longer do (RUNOFF-030), and the override turns out never to
#: have been needed: ``EXF_CHECK_RANGE`` is called only at ``nIter0``
#: (``pkg/exf/exf_getforcing.F:346-349``, unless ``exf_debugLev`` is 3 or
#: more), and under ``RNF_holdRecord`` record 1 of :func:`write_sparse`
#: is dry, so the one call sees zero runoff and this flux arrives at the
#: second step when the check is no longer running. Measured on a
#: retained ``L_set`` run: ``exf_debugLev = 2``, the ``it= 0`` trace
#: selects ``rec0 = 1`` with ``fac = 1.0``, and the log holds no
#: ``EXF WARNING`` line. So these cases say nothing about the RUNOFF-030
#: skip either way. Two package bounds do apply to this flux, and it is
#: under both: ``RNF_srcFluxMax`` = 1e7 m^3/s on one source, ten times
#: this value; and ``RNF_cellVolMax`` = 0.2 of the target cell's
#: top-layer volume per step (RUNOFF-040), which on this cell is
#: 5.5556e-4 m/s (10 m first level, 3600 s step) against the 3.21e-5 m/s
#: above, a factor of 17. Unlike the exf check, that one runs on **every**
#: step, so raising ``FLUX`` by more than 17 would refuse these runs in
#: ``RNF_EXF_RUNOFF`` rather than merely warn.
FLUX = 1.0e6
#: Steps each run takes. Only the **second** one is measured (see
#: :func:`dump_at`); the first is there to put the two runs of a case
#: into a common, bitwise identical state for it, which the dry record 1
#: of :func:`write_sparse` gives. Two is also the fewest that leaves a
#: snapshot at all: a snapshot of a step is written during the step
#: after it, so a one-step run leaves no diagnostic dump (measured: a
#: run from 0 to 3600 s writes T.0000000000 and T.0000000001 but no
#: diagnostic file), and a two-step run leaves exactly one.
STEPS = 2
#: Label of that one snapshot, and of the state dump of the step before
#: the measured one. MITgcm labels the snapshot by its write slot, not
#: by the step whose tendency it holds, so this is "0000000001" while
#: the tendency in it is the second step's; :func:`dump_at` records the
#: measurement behind that.
FIRST_DUMP = "0000000001"
#: Relative tolerance of every comparison (RUNOFF-013 acceptance).
RTOL = 1.0e-12
#: A term smaller than this is not a measurement: a case whose measured
#: term is below it fails as vacuous rather than passing [degC/s, g/kg/s].
FLOOR = 1.0e-9
#: Where a row's Package and Total differ analytically, the measured
#: difference has to exceed this multiple of the tolerance, so that the
#: case really tells the two columns apart.
DISCRIMINATION = 1.0e3

#: Table rows of decision 3 that this check has to cover, by name.
T_ROWS = ("T1-NL-unset", "T2-NL-set-atm", "T3-NL-set-noatm",
          "T4-U-unset", "T5-U-set-atm", "T6-U-set-noatm")
S_ROWS = ("S1-NL-set", "S2-NL-unset", "S3-U-set", "S4-U-unset")
#: Rows of the passive-tracer term (decision 4, RUNOFF-008): one per
#: reference arm of ``RNF_FORCING_SURF_PTR`` that a linear free surface
#: reaches, each with ``PTRACERS_EvPrRn`` set or unset. Branch N
#: (``nonlinFreeSurf > 0`` with ``useRealFreshWaterFlux``) is RUNOFF-014's
#: for tracers as it is for T and S, so it has no row here.
C_ROWS = ("C1-L-set", "C2-L-unset", "C3-U-set", "C4-U-unset")

#: The passive tracer every case carries (RUNOFF-008). Its name is the
#: ``runoff_ptracer_<NAME>`` variable of the file and the
#: ``PTRACERS_names(1)`` of ``data.ptracers``.
TRACER_NAME = "rnfdye"
#: The four tracer values a case can confuse, all distinct, so that each
#: reference arm gives a different term and a wrong choice of ``C_ref``
#: cannot pass at :data:`RTOL` (:func:`judge` measures that margin on
#: every case against :data:`DISCRIMINATION`): the uniform initial
#: tracer (``PTRACERS_initialFile``; exact in float32, which is what
#: ``readBinaryPrec = 32`` reads), ``PTRACERS_ref``, ``PTRACERS_EvPrRn``
#: where a case sets it, and the source concentrations of ``sources``,
#: which are 3.0 and 0.5.
TRC0 = 0.75
TRC_REF = 0.25
TRC_EVPRRN = 1.25
TRC_FILE = "trc0_rnfterm.bin"
#: Which measured quantity is the tracer's "Total" column: the two-run
#: difference of ``Tp_gTr01``. See :func:`judge_tracer`.
TOTAL_C_STREAM = "Tp_g"

DATA_DIAGNOSTICS = """# Analytic single-cell oracle of the runoff surface
# terms, tests/rnf/tendency_term_check.py. Snapshots (frequency < 0) of
# level 1 only, through MDS (diag_mnc = .FALSE.) and in float64
# (fileFlags 'D'), of
#   TOTTTEND, TOTSTEND :: the model's own state tendencies, which carry
#                         the sum of every runoff contribution
#   RNFqnet            :: the runoff heat pkg/rnf hands to Qnet [W/m^2]
#   RNFsflx            :: the runoff salt flux it adds [g/m^2/s]
#   RNFtf01            :: the flux of runoff tracer 1 it adds
#   Tp_gTr01           :: the tracer's own state change over the step,
#                         (C^(n+1) - C^n)/dt, i.e. its TOTTTEND
#   ForcTr01           :: the tracer's forcing tendency (gTrForc),
#                         kept for the record of which one is the total
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
  fields(1,1) = 'TOTTTEND',
  fileName(1) = 'rnfTotT',
  frequency(1) = -{dt!r},
  levels(1,1) = 1.,
  fileFlags(1) = 'D       ',
  fields(1,2) = 'TOTSTEND',
  fileName(2) = 'rnfTotS',
  frequency(2) = -{dt!r},
  levels(1,2) = 1.,
  fileFlags(2) = 'D       ',
  fields(1,3) = 'RNFqnet ',
  fileName(3) = 'rnfQnet',
  frequency(3) = -{dt!r},
  fileFlags(3) = 'D       ',
  fields(1,4) = 'RNFsflx ',
  fileName(4) = 'rnfSflx',
  frequency(4) = -{dt!r},
  fileFlags(4) = 'D       ',
  fields(1,5) = 'RNFtf01 ',
  fileName(5) = 'rnfTfC',
  frequency(5) = -{dt!r},
  fileFlags(5) = 'D       ',
  fields(1,6) = 'Tp_gTr01',
  fileName(6) = 'rnfTpC',
  frequency(6) = -{dt!r},
  levels(1,6) = 1.,
  fileFlags(6) = 'D       ',
  fields(1,7) = 'ForcTr01',
  fileName(7) = 'rnfForcC',
  frequency(7) = -{dt!r},
  levels(1,7) = 1.,
  fileFlags(7) = 'D       ',
 &

 &DIAG_STATIS_PARMS
 &
"""

#: The cases. Each one is a freshwater formulation plus a sparse file,
#: and covers one row of the temperature table and one of the salinity
#: table of decision 3.
#:
#: ``branch`` is "L" (linear free surface, convertFW2Salt = -1) or "U"
#: (virtual salt flux, convertFW2Salt = 35). Branch N needs a nonlinear
#: free surface and is RUNOFF-014's; the temperature table groups N with
#: L, and the salinity table does too, so both tables are covered here
#: for the formulations lab_sea can run in one step.
#: ``temp_EvPrRn`` and ``salt_EvPrRn`` are None for "unset", which is
#: written into the namelist as UNSET_RL, the value the model itself
#: prints for an unset parameter.
#: ``sources`` lists (flux share, temperature, salinity, tracer) per
#: source; a temperature of None is stored as a NaN, i.e. missing, which
#: the schema allows and which must leave that source out of (mT) and
#: m_T -- and *not* out of (mC) or m, which :func:`expected` holds it to.
#: Every source feeds the same cell with fraction 1, so a case with more
#: than one source is also a check that volumes add while the properties
#: are flux-weighted.
#: ``ptr_EvPrRn`` is ``PTRACERS_EvPrRn(1)``: :data:`TRC_EVPRRN` or None
#: for unset, which is left out of ``data.ptracers`` so that the model's
#: own default, ``UNSET_RL``, stands. It is independent of
#: ``temp_EvPrRn``/``salt_EvPrRn``, so the tracer row of a case is named
#: by its own setting: the four ``_set``/``_unset`` cases cover the four
#: tracer rows between them, and the ``focused`` suite runs exactly those
#: four for that reason.
CASES = (
    {"name": "L_unset", "branch": "L",
     "temp_EvPrRn": None, "salt_EvPrRn": 0.0, "ptr_EvPrRn": None,
     "sources": ((1.0, 30.0, 5.0, 3.0),),
     "rows": ("T1-NL-unset", "S1-NL-set", "C2-L-unset")},
    {"name": "L_set", "branch": "L",
     "temp_EvPrRn": 1.5, "salt_EvPrRn": None, "ptr_EvPrRn": TRC_EVPRRN,
     "sources": ((1.0, 30.0, 5.0, 3.0),),
     "rows": ("T2-NL-set-atm", "S2-NL-unset", "C1-L-set")},
    {"name": "U_unset", "branch": "U",
     "temp_EvPrRn": None, "salt_EvPrRn": 0.0, "ptr_EvPrRn": None,
     "sources": ((1.0, 30.0, 5.0, 3.0),),
     "rows": ("T4-U-unset", "S3-U-set", "C4-U-unset")},
    {"name": "U_set", "branch": "U",
     "temp_EvPrRn": 1.5, "salt_EvPrRn": None, "ptr_EvPrRn": TRC_EVPRRN,
     "sources": ((1.0, 30.0, 5.0, 3.0),),
     "rows": ("T5-U-set-atm", "S4-U-unset", "C3-U-set")},
    # Two sources on one cell, with different fluxes and different
    # properties: (mT), (mS) and (mC) are flux-weighted sums, so a mean
    # or a last-one-wins would be a large error here, not a round-off one.
    {"name": "mix", "branch": "L",
     "temp_EvPrRn": None, "salt_EvPrRn": 0.0, "ptr_EvPrRn": TRC_EVPRRN,
     "sources": ((0.75, 30.0, 5.0, 3.0), (0.25, -1.0, 20.0, 0.5)),
     "rows": ("T1-NL-unset", "S1-NL-set", "C1-L-set")},
    # The same, with the temperature of the larger source missing: it
    # must drop out of (mT) and of m_T, so the cell's effective inflow
    # temperature is the smaller source's, while the volume, the
    # salinity and the tracer of both still arrive.
    {"name": "missing_temp", "branch": "L",
     "temp_EvPrRn": None, "salt_EvPrRn": 0.0, "ptr_EvPrRn": None,
     "sources": ((0.75, None, 5.0, 3.0), (0.25, -1.0, 20.0, 0.5)),
     "rows": ("T1-NL-unset", "S1-NL-set", "C2-L-unset")},
    # The two rows where pkg/exf does not cancel the model's own term,
    # because the cancellation is inside #ifdef ALLOW_ATM_TEMP. They
    # need the binary of a build with that option undefined.
    {"name": "L_set_noatm", "branch": "L", "atm_temp": False,
     "temp_EvPrRn": 1.5, "salt_EvPrRn": 0.0, "ptr_EvPrRn": TRC_EVPRRN,
     "sources": ((1.0, 30.0, 5.0, 3.0),),
     "rows": ("T3-NL-set-noatm", "S1-NL-set", "C1-L-set")},
    {"name": "U_set_noatm", "branch": "U", "atm_temp": False,
     "temp_EvPrRn": 1.5, "salt_EvPrRn": None, "ptr_EvPrRn": TRC_EVPRRN,
     "sources": ((1.0, 30.0, 5.0, 3.0),),
     "rows": ("T6-U-set-noatm", "S4-U-unset", "C3-U-set")},
)

UNSET_RL = 1.234567e5


def write_sparse(path, cell, sources, dt, zero_flux=False):
    """Write the one-cell sparse runoff file of a case.

    One target cell, one target entry per source with fraction 1, both
    optional property series, and the ``runoff_ptracer_<TRACER_NAME>``
    series of the case's tracer (RUNOFF-008). With ``zero_flux`` every
    flux is 0,
    which is the reference run: no volume, so no runoff contribution of
    any kind.

    **Two records, and why the first one is dry.** The step the check
    measures is the second one (see :func:`dump_at`), and the oracle
    needs the two runs of a case to be in the same state when it
    starts. So record 1, which hold-exact applies over the first step,
    has zero flux in both runs, and only record 2 carries the case's
    flux. The first step is then bitwise identical in the two runs --
    the record-2 values are not even read, because hold-exact gives the
    record it does not use a weight of exactly zero -- and
    :func:`judge` checks that identity on the state dumps rather than
    assuming it.

    The time axis is a fixed period of one time step anchored on the
    model's own calendar start (``lab_sea/input/data.cal``:
    1979-01-01), so record 1 is at model time 0 and record 2 at the
    start of the second step.
    """
    import netCDF4
    import numpy as np
    n = len(sources)
    with netCDF4.Dataset(path, "w") as ds:
        ds.set_auto_maskandscale(False)
        ds.setncatts({"mitgcm_runoff_schema_version": "1.0",
                      "mitgcm_grid_nx": np.int32(20),
                      "mitgcm_grid_ny": np.int32(16),
                      "mitgcm_time_sampling": "fixed",
                      "mitgcm_time_period": np.float64(dt),
                      "mitgcm_time_repeat": "none",
                      "title": "single-cell runoff for "
                               "tests/rnf/tendency_term_check.py"})
        ds.createDimension("time", 2)
        ds.createDimension("nv", 2)
        ds.createDimension("source", n)
        ds.createDimension("target", n)
        ds.createDimension("id_strlen", 8)
        time = ds.createVariable("time", "f8", ("time",))
        time.units = "seconds since 1979-01-01 00:00:00"
        time.calendar = "gregorian"
        time.axis = "T"
        time.bounds = "time_bnds"
        time[:] = [0.0, dt]
        bnds = ds.createVariable("time_bnds", "f8", ("time", "nv"))
        bnds.units = time.units
        bnds.calendar = time.calendar
        bnds[:] = [[0.0, dt], [dt, 2.0*dt]]
        ids = np.array([list(f"src{k:05d}") for k in range(n)], dtype="S1")
        ds.createVariable("source_id", "S1",
                          ("source", "id_strlen"))[:] = ids
        ds.createVariable("target_source", "i4",
                          ("target",))[:] = np.arange(n, dtype="i4")
        ds.createVariable("target_cell", "i4", ("target",))[:] = cell
        frac = ds.createVariable("target_fraction", "f8", ("target",))
        frac.units = "1"
        frac[:] = 1.0
        flux = ds.createVariable("runoff_flux", "f8", ("time", "source"))
        flux.units = "m3 s-1"
        flux[0, :] = 0.0
        flux[1, :] = [0.0 if zero_flux else FLUX*s[0] for s in sources]
        temp = ds.createVariable("runoff_temperature", "f8",
                                 ("time", "source"),
                                 fill_value=np.float64(-9999.0))
        temp.units = "degC"
        values = [-9999.0 if s[1] is None else s[1] for s in sources]
        temp[0, :] = values
        temp[1, :] = values
        salt = ds.createVariable("runoff_salinity", "f8",
                                 ("time", "source"))
        salt.units = "g kg-1"
        salt[0, :] = [s[2] for s in sources]
        salt[1, :] = [s[2] for s in sources]
        trc = ds.createVariable(f"runoff_ptracer_{TRACER_NAME}", "f8",
                                ("time", "source"))
        trc.units = "1"
        trc[0, :] = [s[3] for s in sources]
        trc[1, :] = [s[3] for s in sources]


def write_mods_code(name, files):
    """Write a lab_sea mods directory: ``code/`` plus replaced files.

    ``experiment_compile.sh -mods`` takes a directory used *instead* of
    the experiment's ``code/``, so every file of ``lab_sea/code`` is
    copied and then each entry of ``files`` (file name -> text) is
    written over or beside it. This is the one helper every non-default
    lab_sea build of these checks is written through:
    :func:`write_noatm_code` here and
    ``tests/rnf/budget_check.write_ptr2_code`` (``PTRACERS_num = 2``).

    Returns the directory. It is git-ignored by name
    (``MITgcm/.git/info/exclude``), and this function does not compile.
    """
    code = os.path.join(VERIF, EXPERIMENT, name)
    shutil.rmtree(code, ignore_errors=True)
    os.makedirs(code)
    base = os.path.join(VERIF, EXPERIMENT, "code")
    for entry in sorted(os.listdir(base)):
        src = os.path.join(base, entry)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(code, entry))
    for entry, text in files.items():
        with open(os.path.join(code, entry), "w") as fh:
            fh.write(text)
    return code


def exf_options(atm_temp):
    """Return the pkg/exf option file with ``ALLOW_RUNOFTEMP`` defined.

    With ``atm_temp`` false ``ALLOW_ATM_TEMP`` is undefined as well
    (which also drops ``ALLOW_BULKFORMULAE``, since that option file
    defines it inside the same ``#ifdef``). Each substitution must match
    exactly once, so a change of the committed option file stops the
    check instead of silently building something else.
    """
    with open(os.path.join(ROOT, "MITgcm", "pkg", "exf",
                           "EXF_OPTIONS.h")) as fh:
        options = fh.read()
    options, count = re.subn(r"(?m)^#undef\s+ALLOW_RUNOFTEMP\s*$",
                             "#define ALLOW_RUNOFTEMP", options)
    if count != 1:
        raise ValueError(f"pkg/exf/EXF_OPTIONS.h has {count} "
                         f"'#undef ALLOW_RUNOFTEMP' lines, expected 1")
    if not atm_temp:
        options, count = re.subn(r"(?m)^#define ALLOW_ATM_TEMP\s*$",
                                 "#undef  ALLOW_ATM_TEMP", options)
        if count != 1:
            raise ValueError(f"pkg/exf/EXF_OPTIONS.h has {count} "
                             f"'#define ALLOW_ATM_TEMP' lines, expected 1")
    return options


def write_roft_code():
    """Write the code directory of the ordinary build of this check.

    ``experiment_compile.sh -mods`` takes a directory used *instead* of
    the experiment's ``code/``, so every file of ``lab_sea/code`` is
    copied and one is added: ``EXF_OPTIONS.h``, the pkg/exf default with
    ``ALLOW_RUNOFTEMP`` defined (:func:`exf_options`).

    Returns the directory, written through :func:`write_mods_code`. It
    is git-ignored (``MITgcm/.git/info/exclude``), and this function does
    not compile: :func:`main` prints the command when the binary is
    missing.
    """
    return write_mods_code(ROFT_CODE, {"EXF_OPTIONS.h": exf_options(True)})


def write_noatm_code():
    """Write the code directory of the build with ALLOW_ATM_TEMP undefined.

    As :func:`write_roft_code`, with ``ALLOW_ATM_TEMP`` undefined too.
    """
    return write_mods_code(NOATM_CODE, {"EXF_OPTIONS.h": exf_options(False)})


def compile_command(code, build):
    """Return the command that builds ``build`` from the mods ``code``."""
    return ("./experiment_compile.sh %s -mods %s -build %s -j 8"
            % (EXPERIMENT, code, build))


#: Sources whose newest file decides whether a build is out of date.
#: These are every path the project declares as a source **and**
#: compiles into a `pkg/rnf` binary: the package itself; pkg/exf (the one
#: guarded call, and the option file the mods directory is derived from);
#: model/src (EXTERNAL_FORCING_SURF, the caller of the salt and tracer
#: terms); pkg/longstep, whose LONGSTEP_FORCING_SURF re-adds the tracer
#: term;
#: model/inc, which holds PARAMS.h, where ``temp_EvPrRn``,
#: ``salt_EvPrRn``, ``convertFW2Salt`` and ``UNSET_RL`` are declared --
#: every one of them read by the terms this script measures;
#: pkg/ptracers, whose surface forcing the tracer term is added to; and
#: ``pkg/pkg_depend``, the plain file
#: that declares ``rnf +exf`` to genmake2. An edit to any of them
#: changes the binary, so leaving it out would let the reuse predicate
#: hand back a binary older than its own source -- the LL-011 failure
#: :func:`build_if_stale` exists to prevent. (The last three were added
#: in RUNOFF-013 correction round 2 after review A measured the hole:
#: touching PARAMS.h left the predicate reusing a stale binary.)
#: The experiment's own ``code/`` is added by :func:`build_if_stale`,
#: because the mods directory is copied from it.
#: The *generated* mods directory is deliberately **not** in this set:
#: it is rewritten on every ``--build`` and so would always look newer
#: than the binary, which would force a recompile every run. Its content
#: is a pure function of ``code/`` and ``pkg/exf/EXF_OPTIONS.h``, both of
#: which are covered here, so nothing is lost by leaving it out.
BUILD_SOURCES = ("MITgcm/pkg/rnf", "MITgcm/pkg/exf", "MITgcm/model/src",
                 "MITgcm/model/inc", "MITgcm/pkg/ptracers",
                 "MITgcm/pkg/longstep", "MITgcm/pkg/pkg_depend")


def newest_source_time(extra=()):
    """Return the mtime of the newest source a binary is compiled from.

    Walks :data:`BUILD_SOURCES` plus ``extra``, all relative to the
    repository root or absolute, and returns the largest ``st_mtime``
    found. Used as the staleness reference of :func:`build_if_stale`.

    An entry may be a directory or a **plain file**: ``os.walk`` of a
    file yields nothing at all, so a file entry (``pkg/pkg_depend``) is
    stat'ed directly. Without that, adding such a path would look like
    coverage and measure nothing.
    """
    newest = 0.0
    for path in tuple(BUILD_SOURCES) + tuple(extra):
        root = path if os.path.isabs(path) else os.path.join(ROOT, path)
        if os.path.isfile(root):
            try:
                newest = max(newest, os.stat(root).st_mtime)
            except OSError:
                pass
            continue
        for dirpath, _, names in os.walk(root):
            for name in names:
                try:
                    stamp = os.stat(os.path.join(dirpath, name)).st_mtime
                except OSError:
                    continue
                if stamp > newest:
                    newest = stamp
    return newest


def build_if_stale(build, write_code=None, jobs=8, timeout=1800,
                   mpi=False):
    """Compile ``build`` when its binary is missing or older than its sources.

    This is what makes a configured command self-contained: the mods
    directory of a non-default build does not exist until ``write_code``
    has run, so a literal ``experiment_compile.sh`` command in
    ``esx/project.json`` could not compile it on a clean tree.

    ``write_code`` is the function that writes the mods directory
    (:func:`write_noatm_code` here, ``exf_heat_check.write_code``
    there); ``None`` builds the experiment's own ``code/`` with no
    ``-mods``, which is what ``tests/mitgcm_oracle.sh`` does for
    ``build_esx``. ``mpi`` compiles with ``-mpi``, for a ``_mpiN`` build
    of the same code (``tests/rnf/budget_check.py``).

    **Staleness, and why it is not just "does the binary exist".** A
    binary left over from before an edit to ``pkg/rnf`` would make every
    figure measured through it a figure of the old code (LL-011). So the
    binary is reused only when it is strictly newer than every file in
    :data:`BUILD_SOURCES` and in the experiment's ``code/``; otherwise it
    is rebuilt. The reference time is taken **before** the compile, so
    the post-compile check that the binary is now newer than it cannot
    be satisfied by the compile having touched the sources.

    Returns a dict with ``build``, ``action`` (``reused``, ``compiled``
    or ``failed``), ``ok``, ``seconds`` and the two mtimes.
    """
    binary = os.path.join(VERIF, EXPERIMENT, build, "mitgcmuv")
    code_dir = os.path.join(VERIF, EXPERIMENT, "code")
    newest = newest_source_time((code_dir,))
    have = os.path.getmtime(binary) if os.path.isfile(binary) else None
    result = {"build": build, "newest_source": newest, "binary_mtime": have,
              "seconds": 0.0}
    if have is not None and have > newest:
        result.update(action="reused", ok=True)
        return result
    start = time.time()
    command = ["./experiment_compile.sh", EXPERIMENT]
    if write_code is not None:
        command += ["-mods", write_code()]
    if mpi:
        command.append("-mpi")
    command += ["-build", build, "-j", str(jobs)]
    result["command"] = " ".join(command)
    try:
        proc = subprocess.run(command, cwd=VERIF, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True,
                              timeout=timeout)
        status, tail = proc.returncode, proc.stdout[-2000:]
    except subprocess.TimeoutExpired:
        status, tail = -1, f"timed out after {timeout} s"
    result["seconds"] = time.time() - start
    after = os.path.getmtime(binary) if os.path.isfile(binary) else None
    result["binary_mtime"] = after
    # A compile that returns 0 but leaves no binary, or leaves one still
    # older than the sources, is a failure here rather than a reuse: it
    # is exactly the stale-build figure this function exists to prevent.
    if status != 0 or after is None or after <= newest:
        result.update(action="failed", ok=False, exit=status, log_tail=tail)
    else:
        result.update(action="compiled", ok=True, exit=status)
    return result


def report_build(info):
    """Print one :func:`build_if_stale` result; return its ``ok``."""
    if info["action"] == "reused":
        print(f"BUILD {info['build']}: reused, newer than every source")
    elif info["action"] == "compiled":
        print(f"BUILD {info['build']}: compiled in "
              f"{info['seconds']:.1f} s")
    else:
        print(f"BUILD {info['build']}: FAILED after "
              f"{info['seconds']:.1f} s (exit {info.get('exit')})")
        print(f"  {info.get('command', '')}")
        for line in (info.get("log_tail") or "").splitlines()[-15:]:
            print(f"  | {line}")
    return info["ok"]


def write_state(input_dir, tracer=False):
    """Write the uniform initial potential temperature and salinity.

    With ``tracer`` also the uniform initial passive tracer of
    :data:`TRC_FILE`, which only this script's cases read
    (``tests/rnf/exf_heat_check.py`` shares the function and runs no
    tracer).
    """
    import numpy as np
    fields = [(THETA_FILE, THETA0), (SALT_FILE, SALT0)]
    if tracer:
        fields.append((TRC_FILE, TRC0))
    for name, value in fields:
        field = np.full((23, 16, 20), value, dtype=">f4")
        field.tofile(os.path.join(input_dir, name))


def data_ptracers(evprrn):
    """Return the ``data.ptracers`` of a case: one tracer, from a file.

    ``PTRACERS_Iter0 = 0`` is the ``nIter0`` of these runs, so the tracer
    starts from ``PTRACERS_initialFile`` (the uniform :data:`TRC0` of
    :func:`write_state`), and :func:`judge` requires the run's own
    iteration-0 dump to hold exactly that. ``PTRACERS_ref`` is
    :data:`TRC_REF` on every level; ``PTRACERS_EvPrRn(1)`` is written only
    when ``evprrn`` is not None, so an unset case runs on the model's own
    ``UNSET_RL``. No diffusion and no GM/Redi or KPP on the tracer: they
    act identically in the two runs of a case, so they cannot enter the
    measured difference, and they are off so that nothing else moves the
    tracer state the term is evaluated with.
    """
    lines = ["# Written by tests/rnf/tendency_term_check.py (RUNOFF-008).",
             " &PTRACERS_PARM01",
             " PTRACERS_numInUse = 1,",
             " PTRACERS_Iter0 = 0,",
             f" PTRACERS_names(1) = '{TRACER_NAME}',",
             " PTRACERS_long_names(1) = 'runoff tendency check tracer',",
             " PTRACERS_units(1) = '1',",
             f" PTRACERS_initialFile(1) = '{TRC_FILE}',",
             " PTRACERS_diffKh(1) = 0.,",
             " PTRACERS_diffKr(1) = 0.,",
             " PTRACERS_useGMRedi(1) = .FALSE.,",
             " PTRACERS_useKPP(1) = .FALSE.,",
             f" PTRACERS_ref(:,1) = 23*{TRC_REF!r},"]
    if evprrn is not None:
        lines.append(f" PTRACERS_EvPrRn(1) = {evprrn!r},")
    lines.append(" &")
    return "\n".join(lines) + "\n"


def write_input(case, input_dir, zero_flux):
    """Build the scratch input directory of one run.

    Only the files this check changes are written; everything else is
    layered in from ``lab_sea/input`` by the harness.
    """
    base = os.path.join(VERIF, EXPERIMENT, "input")
    cell = sparse_info()["wet_cell"]
    dt = 3600.0
    write_sparse(os.path.join(input_dir, SPARSE_FILE), cell,
                 case["sources"], dt, zero_flux=zero_flux)
    write_state(input_dir, tracer=True)

    with open(os.path.join(base, "data")) as fh:
        data = fh.read()
    settings = [
        # one step from iteration 0, so that the initial state is the one
        # written above and not lab_sea's pickup (startTime = 3600 there)
        ("PARM03", "startTime", " startTime=0.0,"),
        ("PARM03", "endTime", f" endTime={STEPS*dt!r},"),
        ("PARM03", "monitorFreq", " monitorFreq=1.,"),
        ("PARM03", "pChkptFreq", " pChkptFreq=0.,"),
        # the initial state has to be written, as T.0000000000: it is
        # the theta and salt the terms are evaluated with
        ("PARM03", "dumpFreq", f" dumpFreq={dt!r},"),
        ("PARM03", "dumpInitAndLast", " dumpInitAndLast=.TRUE.,"),
        ("PARM01", "writeBinaryPrec", " writeBinaryPrec=64,"),
        ("PARM03", "outputTypesInclusive", " outputTypesInclusive=.TRUE.,"),
        ("PARM05", "hydrogThetaFile", f" hydrogThetaFile='{THETA_FILE}',"),
        ("PARM05", "hydrogSaltFile", f" hydrogSaltFile='{SALT_FILE}',"),
        ("PARM01", "useRealFreshWaterFlux",
         " useRealFreshWaterFlux=.FALSE.,"),
        # The state change of a step has to be deltaT times the
        # tendency, and an implicit vertical diffusion solve would
        # instead apply (I - deltaT*A)^-1 to it: measured on
        # lab_sea/input, which has implicitDiffusion on, the surface
        # cell then keeps only 1 - 5.2e-4 of the runoff term, which is
        # 9 orders above the tolerance of this check.
        ("PARM01", "implicitDiffusion", " implicitDiffusion=.FALSE.,"),
        ("PARM01", "nonlinFreeSurf", " nonlinFreeSurf=0,"),
        ("PARM01", "convertFW2Salt",
         f" convertFW2Salt={-1.0 if case['branch'] == 'L' else 35.0!r},"),
        ("PARM01", "temp_EvPrRn",
         f" temp_EvPrRn="
         f"{UNSET_RL if case['temp_EvPrRn'] is None else case['temp_EvPrRn']!r},"),
        ("PARM01", "salt_EvPrRn",
         f" salt_EvPrRn="
         f"{UNSET_RL if case['salt_EvPrRn'] is None else case['salt_EvPrRn']!r},"),
    ]
    for namelist, name, line in settings:
        data = set_namelist(data, namelist, name, line)
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)

    # Only the packages whose terms are being measured. pkg/seaice and
    # pkg/kpp read Qnet and surfaceForcingT, which carry part of the
    # runoff heat, so their response would enter the difference of the
    # two runs and the total would no longer be the sum of the three
    # terms. pkg/mnc off so the output is MDS. pkg/ptracers on for the
    # tracer rows (RUNOFF-008); a passive tracer feeds nothing back into
    # theta, salt or the flow, and the T and S figures of every case were
    # measured bitwise unchanged by switching it on.
    with open(os.path.join(base, "data.pkg")) as fh:
        pkg = fh.read()
    for name, value in (("useGMRedi", ".FALSE."), ("useKPP", ".FALSE."),
                        ("useSEAICE", ".FALSE."), ("useMNC", ".FALSE."),
                        ("useEXF", ".TRUE."), ("useCAL", ".TRUE."),
                        ("useDiagnostics", ".TRUE."), ("useRNF", ".TRUE."),
                        ("usePTRACERS", ".TRUE.")):
        line = f"  {name} = {value},"
        pkg = (replace_line(pkg, name, line)
               if re.search(r"(?mi)^\s*%s\s*=" % re.escape(name), pkg)
               else add_to_namelist(pkg, "PACKAGES", line))
    with open(os.path.join(input_dir, "data.pkg"), "w") as fh:
        fh.write(pkg)

    # No dense runoff. useExfCheckRange is left at the setting of
    # lab_sea/input (.TRUE.); see the FLUX comment at the top for why
    # the override that used to be here was unnecessary, and for the
    # measurement that says so. pkg/rnf bounds the source flux itself
    # (RNF_srcFluxMax, package design decision 2, RUNOFF-030) and the
    # applied field per cell (RNF_cellVolMax, RUNOFF-040); FLUX is under
    # both, by factors of 10 and 17.
    with open(os.path.join(base, "data.exf")) as fh:
        exf = fh.read()
    exf = set_namelist(exf, "EXF_NML_02", "runoffFile",
                       " runoffFile        = ' ',")
    if not case.get("atm_temp", True):
        # Without ALLOW_ATM_TEMP these namelist variables do not exist,
        # so the namelist read would stop the run on an unknown name.
        exf = "\n".join(
            ln for ln in exf.splitlines()
            if not re.match(r"\s*(atemp|aqh|precip|snowprecip)\w*\s*=", ln))
        # and EXF_CHECK refuses the downward-radiation fields in that
        # build ("Cannot read-in field lwdown with #undef
        # ALLOW_ATM_TEMP"), so this run has no radiative forcing
        # either. It changes nothing here: the measured step is
        # differenced against a run with the same forcing.
        for name in ("lwdownfile", "swdownfile"):
            exf = replace_line(exf, name, f" {name}        = ' ',")
    with open(os.path.join(input_dir, "data.exf"), "w") as fh:
        fh.write(exf)

    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(DATA_DIAGNOSTICS.format(dt=dt))

    with open(os.path.join(input_dir, "data.ptracers"), "w") as fh:
        fh.write(data_ptracers(case["ptr_EvPrRn"]))
    # lab_sea compiles pkg/longstep, which takes over the ptracer step
    # (model/src/thermodynamics.F:6 compiles the ordinary
    # PTRACERS_INTEGRATE call out, and forward_step.F:700-722 calls
    # LONGSTEP_THERMODYNAMICS instead) and stops the run without this
    # file. LS_nIter = 1 with LS_whenToSample = 0 is one tracer step per
    # dynamics step, taken from the state at the start of the step.
    with open(os.path.join(input_dir, "data.longstep"), "w") as fh:
        fh.write("# Written by tests/rnf/tendency_term_check.py: one\n"
                 "# passive tracer step per dynamics step.\n"
                 " &LONGSTEP_PARM01\n"
                 "  LS_nIter = 1,\n"
                 "  LS_whenToSample = 0,\n"
                 " &\n")

    with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
        fh.write("# Written by tests/rnf/tendency_term_check.py.\n"
                 "# RNF_holdRecord: each record is applied over its own\n"
                 "# interval with a weight of exactly 1, so the first\n"
                 "# step gets record 1 (zero flux) and the measured\n"
                 "# second step gets record 2 exactly as stored, with no\n"
                 "# interpolation between them.\n"
                 " &RNF_PARM01\n"
                 f"  RNF_file = '{SPARSE_FILE}',\n"
                 "  RNF_holdRecord = .TRUE.,\n"
                 "  RNF_debugLev = 3,\n"
                 " &\n")
    return dt


def run_model(input_name, build, timeout):
    """Run one scratch input; return ``(run dir, exit status, timed out)``."""
    output_name = "output_esx_" + input_name
    run_dir = os.path.join(VERIF, EXPERIMENT, output_name)
    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        proc = subprocess.run(
            ["./experiment_run_no_compile.sh", EXPERIMENT, input_name,
             "-build", build, "-output", output_name],
            cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return run_dir, proc.returncode, False
    except subprocess.TimeoutExpired:
        kill_run(output_name)
        return run_dir, -1, True


def read_mds(run_dir, base):
    """Return one MDS field of any rank, as a flat float64 array, with dims.

    A precision other than float64 raises ``ValueError`` rather than
    being read at face value: every comparison here is meant to be
    exact to round-off.
    """
    import numpy as np
    meta = read_file(run_dir, base + ".meta")
    if meta is None:
        raise ValueError(f"{base}.meta is missing from {run_dir}")
    prec = re.search(r"dataprec\s*=\s*\[\s*'([^']+)'", meta)
    if not prec or prec.group(1) != "float64":
        raise ValueError(f"{base}.meta says dataprec "
                         f"{prec and prec.group(1)!r}, not 'float64'")
    dims = re.search(r"dimList\s*=\s*\[(.*?)\]", meta, re.DOTALL)
    if not dims:
        raise ValueError(f"{base}.meta has no dimList")
    numbers = [int(v) for v in re.findall(r"-?\d+", dims.group(1))]
    if len(numbers) % 3 or not numbers:
        raise ValueError(f"{base}.meta dimList has {len(numbers)} numbers")
    sizes = [numbers[3*k] for k in range(len(numbers)//3)]
    field = np.fromfile(os.path.join(run_dir, base + ".data"), dtype=">f8")
    want = 1
    for s in sizes:
        want *= s
    if field.size != want:
        raise ValueError(f"{base}.data holds {field.size} values, not "
                         f"{want} for dimList {sizes}")
    return field.astype(np.float64), sizes


def dump_at(run_dir, stream, cell, whole=False):
    """Return the stream's dump of the measured step at ``cell``, and its label.

    With ``whole`` the entire field is returned instead of the one cell,
    for a check that compares every cell
    (``tests/rnf/exf_heat_check.py``).

    **The dump holds the second time step, despite its label.** The run
    takes ``STEPS`` = 2 steps and writes exactly one snapshot, labelled
    ``0000000001`` with ``timeStepNumber = 1`` and
    ``timeInterval = deltaT`` in its ``.meta``; MITgcm labels a snapshot
    by its write slot, and the tendency in this one is the second step's.
    Measured on a retained ``L_set`` pair: the snapshot is
    ``8.313059890300034e-05`` degC/s where the run's own
    ``(theta^2 - theta^1)/dt`` is ``8.313059890300037e-05`` (equal to
    1 ulp) and ``(theta^1 - theta^0)/dt`` is
    ``-4.5143400080746266e-06``. A run of one step writes no diagnostic
    file at all, which is the same fact seen from the other side: a
    snapshot of a step is written during the step after it.

    The second step is the comparable one. The two runs of a case enter
    it in a bitwise identical state, because record 1 of the file is dry
    in both, so every term other than the runoff ones is bitwise the
    same and the difference of the two runs is the runoff total; over
    the first step the two runs are identical and the difference is
    exactly zero, and by the third step they would have drifted apart.

    Both the label and the ``timeStepNumber`` are checked here rather
    than assumed, so a change in the labelling would stop the check
    instead of silently moving which step it measures.
    """
    import glob
    paths = sorted(glob.glob(os.path.join(run_dir, stream + ".*.data")))
    labels = [os.path.basename(p).split(".")[1] for p in paths]
    if len(paths) != 1:
        raise ValueError(f"{stream}: {len(paths)} dumps in {run_dir} "
                         f"({labels}), expected exactly 1")
    if labels[0] != FIRST_DUMP:
        raise ValueError(f"{stream}: the dump in {run_dir} is labelled "
                         f"{labels[0]}, not {FIRST_DUMP}: it is not the "
                         f"snapshot that carries the measured second "
                         f"time step")
    base = os.path.basename(paths[0])[:-5]
    meta = read_file(run_dir, base + ".meta") or ""
    step = re.search(r"timeStepNumber\s*=\s*\[\s*(\d+)", meta)
    if not step or int(step.group(1)) != 1:
        raise ValueError(f"{base}.meta says timeStepNumber "
                         f"{step and step.group(1)}, not 1")
    field, sizes = read_mds(run_dir, base)
    if sizes[0]*sizes[1] <= cell:
        raise ValueError(f"{stream}: cell {cell} is outside {sizes}")
    if whole:
        return field, labels[0]
    return float(field[cell]), labels[0]


def param(text, name):
    """Return a real parameter as the model's own parameter dump prints it.

    ``config_summary`` writes the name and the comment on one line and
    the value on the next, so the value is read from the line after the
    match. Raises ``ValueError`` if the name is not reported, so a case
    can never be judged against a setting the run did not have.

    Lines the model echoes from the input files are skipped (it marks
    them with ``>``): the echo of ``data`` sets the same names, and
    reading the value from there would report what the file said rather
    than what the model resolved it to.
    """
    lines = [ln for ln in text.splitlines() if ") >" not in ln]
    for k, line in enumerate(lines):
        if re.search(r"\b%s\s*=" % re.escape(name), line):
            for value in lines[k+1:k+3]:
                match = re.search(r"(-?\d+\.\d+E[-+]\d+)", value)
                if match:
                    return float(match.group(1))
                match = re.fullmatch(r"\s*\(PID\.TID \S+\)\s+(-?\d+)\s*",
                                     value)
                if match:
                    return float(match.group(1))
    raise ValueError(f"the parameter dump does not report {name}")


def param_all(text, name):
    """Return every value of a per-tracer parameter, in the order printed.

    ``PTRACERS_CHECK`` prints one block per tracer, so a name such as
    ``PTRACERS_EvPrRn`` occurs once per tracer in use; :func:`param`
    returns only the first. Same parsing rules as :func:`param` (echoed
    input lines are skipped, the value is on the line after the name).
    Raises ``ValueError`` if the name is not reported at all.
    """
    lines = [ln for ln in text.splitlines() if ") >" not in ln]
    values = []
    for k, line in enumerate(lines):
        if re.search(r"\b%s\s*=" % re.escape(name), line):
            for value in lines[k+1:k+3]:
                match = re.search(r"(-?\d+\.\d+E[-+]\d+)", value)
                if match:
                    values.append(float(match.group(1)))
                    break
    if not values:
        raise ValueError(f"the parameter dump does not report {name}")
    return values


def state_at(run_dir, label, cell, tracer=False):
    """Return the model's own theta and salt at ``cell``, and the fields.

    The state dump labelled 0000000000 is the state at iteration
    ``nIter0``, which these cases set to 0, i.e. the uniform field this
    script wrote and the model read through ``hydrogThetaFile``; the one
    labelled 0000000001 is the state after the first step, which is the
    state the measured second step evaluates its terms with. Reading
    them back is what turns "the term was evaluated with this theta"
    from an assumption into a measurement.

    With ``tracer`` the passive tracer is read the same way, from the
    ptracer state dump ``PTRACER01.<label>`` that ``PTRACERS_WRITE_STATE``
    writes on the same ``dumpFreq``; ``tests/rnf/exf_heat_check.py``
    shares this function and runs no tracer, so it is off by default.
    """
    theta, _ = read_mds(run_dir, "T." + label)
    salt, _ = read_mds(run_dir, "S." + label)
    out = {"theta": float(theta[cell]), "salt": float(salt[cell]),
           "theta_field": theta, "salt_field": salt}
    if tracer:
        trc, _ = read_mds(run_dir, "PTRACER01." + label)
        out.update(trc=float(trc[cell]), trc_field=trc)
    return out


def layer_thickness(run_dir):
    """Return delR(1) of the run's own ``data``, in metres."""
    data = read_file(run_dir, "data")
    if data is None:
        raise ValueError(f"{run_dir} has no data file")
    match = re.search(r"^\s*del[RZ]\s*=\s*([-+0-9.DdEe]+)", data,
                      re.MULTILINE)
    if not match:
        raise ValueError("data sets neither delR nor delZ")
    return float(match.group(1).replace("D", "E").replace("d", "e"))


def expected_tracer(case, text, m, mu, dterm, area, c_local):
    """Return the analytic passive-tracer terms of ``case`` (RUNOFF-008).

    ``m``, ``mu``, ``dterm`` and ``area`` are the run's own numbers as
    :func:`expected` builds them for T and S; ``c_local`` is the tracer
    the model had at the target cell when the measured step started,
    read from its own ``PTRACER01`` dump of the step before.

    **Package**, as ``RNF_FORCING_SURF_PTR`` chooses ``C_ref``
    (``pkg/rnf/rnf_forcing_surf.F:278-289``): ``PTRACERS_EvPrRn`` when
    set; otherwise the local tracer when ``convertFW2Salt = -1`` (branch
    L; the branch-N arm before it needs a nonlinear free surface and is
    RUNOFF-014's); otherwise ``PTRACERS_ref(ks)`` (branch U).

    **Model**, i.e. what the model's own freshwater treatment of the
    tracer adds for the runoff water. On lab_sea that is **not**
    ``PTRACERS_FORCING_SURF``: lab_sea compiles pkg/longstep, under which
    ``LONGSTEP_THERMODYNAMICS`` recomputes ``surfaceForcingPTr`` by
    ``LONGSTEP_FORCING_SURF`` before every ptracer step
    (``pkg/longstep/longstep_thermodynamics.F:156-159``), with the same
    three arms as ``pkg/ptracers/ptracers_forcing_surf.F:114-189`` but
    ``EmPmR`` replaced by its long-step average ``LS_fwFlux``
    (``pkg/longstep/longstep_forcing_surf.F:96-147``). With
    ``LS_nIter = 1`` that average is one sample of the step's own
    ``EmPmR`` (``pkg/longstep/longstep_average.F:111-115``). Both
    routines add nothing at all unless ``PTRACERS_EvPrRn`` is set, and in
    L and U add ``EmPmR*(C_L - PTRACERS_EvPrRn)*mass2rUnit`` with ``C_L``
    the local tracer (L) or ``PTRACERS_ref(ks)`` (U); runoff contributes
    ``-m`` to ``EmPmR`` (``sflux - runoff`` at
    ``pkg/exf/exf_getforcing.F:313``, times ``rhoConstFresh`` at
    ``pkg/exf/exf_mapfields.F:118-119``), so the model's
    share of the runoff is ``m*(PTRACERS_EvPrRn - C_L)*mu``, applied
    through ``surfForcPtr*recip_drF*recip_hFacC`` in
    ``PTRACERS_APPLY_FORCING``. No pkg/exf term exists for a tracer.

    **Total** = package + model. So in the two set rows the
    ``PTRACERS_EvPrRn`` the package subtracts is exactly what the model
    added, and the total is ``(mC) - m*C_L``; in the two unset rows the
    model adds nothing and the total *is* the package term.

    ``alternatives`` gives the package term with every other reference
    the routine could have used -- the other arms, the initial tracer
    and zero -- so that :func:`judge` can require the measured term to be
    far from each of them.
    """
    import math
    ptr_ref = param(text, "PTRACERS_ref")
    ptr_ev = param(text, "PTRACERS_EvPrRn")
    vxc = 0.0
    for share, _temp, _salt, trc in case["sources"]:
        w = FLUX*share*1.0/area
        vxc = vxc + w*trc
    rho_fresh = param(text, "rhoConstFresh")
    mxc = rho_fresh*vxc
    candidates = {"local": c_local, "PTRACERS_ref": ptr_ref,
                  "initial": TRC0, "zero": 0.0}
    if case["ptr_EvPrRn"] is not None:
        candidates["PTRACERS_EvPrRn"] = ptr_ev
        arm = "PTRACERS_EvPrRn"
    elif case["branch"] == "L":
        arm = "local"
    else:
        arm = "PTRACERS_ref"
    c_ref = candidates[arm]
    pack = mxc - m*c_ref
    model = 0.0
    if case["ptr_EvPrRn"] is not None:
        against = ptr_ref if case["branch"] == "U" else c_local
        model = m*(ptr_ev - against)*mu
    total = (pack*mu + model)*dterm
    alternatives = {k: mxc - m*v for k, v in candidates.items()
                    if k != arm and v != c_ref}
    return {"PTRACERS_ref": ptr_ref, "PTRACERS_EvPrRn": ptr_ev,
            "mXC": mxc, "C_ref": c_ref, "C_ref_arm": arm,
            "C_local": c_local, "package_C": pack,
            "package_C_tendency": pack*mu*dterm,
            "model_C": model*dterm, "total_C": total,
            "alternatives_C": alternatives,
            "finite": all(math.isfinite(v) for v in (pack, total))}


def expected(case, run_dir, cell, theta, salt0):
    """Return the analytic terms of ``case``, from the run's own numbers.

    ``theta`` and ``salt0`` are the model state the measured step
    evaluates its terms with, read from the run's own state dump of the
    step before it.

    The sums are formed in the order and with the expressions
    ``RNF_FIELDS_LOAD`` uses -- ``w = flux*frac/rA`` per target entry in
    table order, then one multiplication by ``rhoConstFresh`` -- so the
    comparison is a comparison of two evaluations of the same formula and
    not of two different roundings of it.
    """
    import math
    text = read_file(run_dir, "output.txt") or ""
    rho = param(text, "rhoConst")
    rho_fresh = param(text, "rhoConstFresh")
    t_ref1 = param(text, "tRef")
    temp_ev = param(text, "temp_EvPrRn")
    salt_ev = param(text, "salt_EvPrRn")
    fw2salt = param(text, "convertFW2Salt")
    out_ab = param(text, "tracForcingOutAB")
    nonlin = param(text, "nonlinFreeSurf")

    rac, _ = read_mds(run_dir, "RAC")
    area = float(rac[cell])
    hfac, sizes = read_mds(run_dir, "hFacC")
    hfac1 = float(hfac[cell])
    drf1 = layer_thickness(run_dir)

    mu = 1.0/rho
    dterm = 1.0/(drf1*hfac1)
    vflx = 0.0
    vfxT = 0.0
    vxT = 0.0
    vxS = 0.0
    for share, temp, salt, _trc in case["sources"]:
        w = FLUX*share*1.0/area
        vflx = vflx + w
        if temp is not None:
            vfxT = vfxT + w
            vxT = vxT + w*temp
        vxS = vxS + w*salt
    m = rho_fresh*vflx
    m_t = rho_fresh*vfxT
    mxt = rho_fresh*vxT
    mxs = rho_fresh*vxS

    # Package column. Heat: the term RNF_EXF_RUNOFF hands to the exf
    # runoftemp block of EXF_MAPFIELDS, HeatCapacity_Cp*(theta -
    # runoftemp)*runoff*rhoConstFresh in W/m^2 with Qnet's sign, with
    # runoftemp built as RNF_EXF_RUNOFF builds it (pkg/rnf/
    # rnf_exf_runoff.F, the ALLOW_RUNOFTEMP block): (mT)/m where every
    # source carries a temperature, theta where none does, and
    # [(mT) + (m - m_T)*theta]/m otherwise. Its reference is therefore
    # theta in every case: the exf block assumes the water arrives at
    # theta. Salt: [(mS) - m*S_ref] in g/m^2/s, with the reference the
    # model has already applied (RNF_FORCING_SURF).
    atm = case.get("atm_temp", True)
    cp = param(text, "HeatCapacity_Cp")
    if m == 0.0:
        roft = 0.0
    elif m_t == m:
        roft = mxt/m
    elif m_t == 0.0:
        roft = theta
    else:
        roft = (mxt + (m - m_t)*theta)/m
    pack_t = cp*(theta - roft)*vflx*rho_fresh
    t_ref = theta
    if case["salt_EvPrRn"] is not None:
        s_ref = salt_ev
    elif case["branch"] == "L":
        s_ref = salt0
    else:
        s_ref = fw2salt
    pack_s = mxs - m*s_ref

    # Model and exf columns, then the total as their sum with the
    # package column. The three are kept apart, as the tables of
    # decision 3 keep them, because their sum is the claim: with every
    # source carrying a temperature (m_T = m) this reduces to the
    # table's Total entry, and where one does not it is the general
    # form of it (decision 3, "Missing temperature"), which no row of
    # the table states.
    #   model: PmEpR*(temp_EvPrRn - theta)*mu in branch N and
    #          EmPmR*(theta - temp_EvPrRn)*mu in branches L and U, and
    #          runoff contributes +m to PmEpR and -m to EmPmR, so both
    #          come to m*(temp_EvPrRn - reference)*mu
    #          (model/src/external_forcing_surf.F:261-349)
    #   exf:   -Cp*(theta - temp_EvPrRn)*runoff*rhoConstFresh added to
    #          Qnet, which surfaceForcingT subtracts as Qnet*mu/Cp,
    #          i.e. m*(theta - temp_EvPrRn)*mu, and only with
    #          ALLOW_ATM_TEMP (pkg/exf/exf_mapfields.F, the
    #          temp_EvPrRn block)
    #   package: the runoftemp term above, which surfaceForcingT
    #          subtracts as Qnet*mu/Cp, i.e. -pack_t/Cp*mu; and the salt
    #          term, which RNF_FORCING_SURF adds to surfaceForcingS times
    #          mu. Both are applied at the surface level times D.
    # Without ALLOW_ATM_TEMP and with temp_EvPrRn set, nothing cancels the
    # model's term for the runoff, so the total is the model's term plus
    # the runoftemp term: the water is counted at temp_EvPrRn and again
    # from theta to its own temperature. That is the dense runoftempfile
    # path's total in that build too (package design, decision 3,
    # comparison point 5), which the sparse path now shares.
    model_t, exf_t = 0.0, 0.0
    if case["temp_EvPrRn"] is not None:
        against = t_ref1 if case["branch"] == "U" else theta
        model_t = m*(temp_ev - against)*mu
        if atm:
            exf_t = m*(theta - temp_ev)*mu
    pack_t_tend = -pack_t/cp*mu*dterm
    pack_s_tend = pack_s*mu*dterm
    total_t = pack_t_tend + (model_t + exf_t)*dterm
    model_s = 0.0
    if case["salt_EvPrRn"] is not None:
        against = fw2salt if case["branch"] == "U" else salt0
        model_s = m*(salt_ev - against)*mu
    total_s = pack_s_tend + model_s*dterm

    return {"rA": area, "hFacC": hfac1, "drF": drf1, "mu": mu, "D": dterm,
            "m": m, "m_T": m_t, "mXT": mxt, "mXS": mxs,
            "T_ref": t_ref, "S_ref": s_ref, "tRef1": t_ref1,
            "temp_EvPrRn": temp_ev, "salt_EvPrRn": salt_ev,
            "convertFW2Salt": fw2salt, "tracForcingOutAB": out_ab,
            "nonlinFreeSurf": nonlin, "hFacC_dims": sizes,
            "package_T": pack_t, "package_S": pack_s,
            "package_T_tendency": pack_t_tend,
            "package_S_tendency": pack_s_tend,
            "runoftemp": roft, "HeatCapacity_Cp": cp,
            "model_T": model_t*dterm, "exf_T": exf_t*dterm,
            "model_S": model_s*dterm,
            "total_T": total_t, "total_S": total_s,
            "finite": all(math.isfinite(v) for v in
                          (pack_t, pack_s, total_t, total_s))}


def judge_tracer(case, run_dir, zero_dir, cell, dt, want, before, result,
                 problems):
    """Judge the passive-tracer row of ``case`` (RUNOFF-008).

    Same two columns as T and S. **Package**: the ``RNFtf01`` dump
    against :func:`expected_tracer`. **Total**: the difference of the
    two runs of ``Tp_gTr01``, which ``PTRACERS_INTEGRATE`` fills with
    ``(gTracer - pTracer)/PTRACERS_dTLev`` after the time step
    (``pkg/ptracers/ptracers_integrate.F:476-494``), i.e. the tracer's
    own state change over the step -- its ``TOTTTEND``. Which quantity
    that is was measured, not assumed; see :data:`TOTAL_C_STREAM`. The
    other two candidates, ``ForcTr01`` and ``(C^2 - C^1)/dt`` from the
    ptracer state dumps, are reported beside it in ``total_C_candidates``.

    Appends to ``problems`` and fills ``result``. ``before`` is the
    case run's state at the start of the measured step.
    """
    text = read_file(run_dir, "output.txt") or ""
    tw = expected_tracer(case, text, want["m"], want["mu"], want["D"],
                         want["rA"], before["trc"])
    result["expected_tracer"] = tw
    if not tw["finite"]:
        problems.append("the analytic tracer terms are not all finite")
    asked = UNSET_RL if case["ptr_EvPrRn"] is None else case["ptr_EvPrRn"]
    if abs(tw["PTRACERS_EvPrRn"] - asked) > 1.0e-12*max(1.0, abs(asked)):
        problems.append(f"the run reports PTRACERS_EvPrRn = "
                        f"{tw['PTRACERS_EvPrRn']!r}, not the {asked!r} the "
                        f"case asked for")
    if tw["PTRACERS_ref"] != TRC_REF:
        problems.append(f"the run reports PTRACERS_ref = "
                        f"{tw['PTRACERS_ref']!r}, not {TRC_REF!r}")

    package, label = dump_at(run_dir, "rnfTfC", cell)
    result["package_C_dump"] = label
    zero_pack, _ = dump_at(zero_dir, "rnfTfC", cell)
    if zero_pack != 0.0:
        problems.append(f"the zero-flux run's rnfTfC at the target cell is "
                        f"{zero_pack!r}, not 0")
    candidates = {}
    for key, stream in (("Tp_g", "rnfTpC"), ("Forc", "rnfForcC")):
        one, _ = dump_at(run_dir, stream, cell)
        two, _ = dump_at(zero_dir, stream, cell)
        candidates[key] = one - two
    after = state_at(run_dir, "0000000002", cell, tracer=True)
    zero_after = state_at(zero_dir, "0000000002", cell, tracer=True)
    zero_before = state_at(zero_dir, FIRST_DUMP, cell, tracer=True)
    candidates["state"] = ((after["trc"] - before["trc"])
                           - (zero_after["trc"] - zero_before["trc"]))/dt
    total = candidates[TOTAL_C_STREAM]
    result["total_C_candidates"] = {
        k: {"value": v, "relative": (abs(v - tw["total_C"])/abs(tw["total_C"])
                                     if tw["total_C"] else None)}
        for k, v in candidates.items()}
    measured = {"package_C": package, "total_C": total}
    result["measured_tracer"] = measured

    rel = result.setdefault("relative", {})
    for key in ("package_C", "total_C"):
        ref = tw[key]
        if abs(ref) < FLOOR:
            problems.append(f"{key} is {ref!r}, below the floor {FLOOR!r}: "
                            f"the case does not measure this term")
            rel[key] = None
            continue
        rel[key] = abs(measured[key] - ref)/abs(ref)
        if rel[key] > RTOL:
            problems.append(f"{key}: measured {measured[key]!r}, expected "
                            f"{ref!r}, relative {rel[key]:.3e} > {RTOL!r}")

    # A wrong reference must be impossible at the tolerance: the measured
    # package term has to be far from the term every other arm (and the
    # initial tracer, and no reference at all) would have given.
    margins = {}
    for arm, alt in tw["alternatives_C"].items():
        margin = abs(package - alt)/max(abs(alt), abs(package))
        margins[arm] = margin
        if margin <= RTOL*DISCRIMINATION:
            problems.append(
                f"tracer: the measured package term is within "
                f"{margin:.3e} of the term with C_ref = {arm}, so the case "
                f"cannot tell the {tw['C_ref_arm']} arm from that one")
    result["C_ref_margins"] = margins

    # The package term is a flux and the total a tendency; compare them
    # in tendency units, the package one converted with the run's own
    # mass2rUnit and D, as PTRACERS_APPLY_FORCING applies it.
    pack, tot = tw["package_C_tendency"], tw["total_C"]
    apart = abs(pack - tot)/max(abs(pack), abs(tot))
    result["apart_C"] = apart
    result["differ_C"] = apart > RTOL*DISCRIMINATION
    if result["differ_C"]:
        package_tend = package*want["mu"]*want["D"]
        got = abs(package_tend - total)
        scale = max(abs(package_tend), abs(total))
        if got/scale <= RTOL*DISCRIMINATION:
            problems.append(
                f"C: the package term and the total are expected to differ "
                f"by {apart:.3e} relative but the measured ones differ by "
                f"{got/scale:.3e}")


def judge(case, run_dir, zero_dir, cell, dt):
    """Compare the measured terms with the analytic ones."""
    problems = []
    result = {"name": case["name"], "rows": list(case["rows"])}

    # The premises the oracle rests on, measured from the runs
    # themselves: the initial state is the uniform one this script
    # wrote, and the two runs are still in the same state when the
    # measured step starts, so that the difference of their state
    # tendencies over that step is the runoff total and nothing else.
    start = state_at(run_dir, "0000000000", cell, tracer=True)
    result["initial_state"] = {"theta": start["theta"],
                               "salt": start["salt"], "trc": start["trc"]}
    for name, value in (("theta", THETA0), ("salt", SALT0), ("trc", TRC0)):
        if start[name] != value:
            problems.append(f"the run's own iteration-0 dump has "
                            f"{name} = {start[name]!r} at the target cell, "
                            f"not the {value!r} this script wrote")
    before = state_at(run_dir, FIRST_DUMP, cell, tracer=True)
    zero_before = state_at(zero_dir, FIRST_DUMP, cell, tracer=True)
    result["state_of_measured_step"] = {"theta": before["theta"],
                                        "salt": before["salt"],
                                        "trc": before["trc"]}
    for name in ("theta", "salt", "trc"):
        same = (before[name + "_field"] == zero_before[name + "_field"])
        if not bool(same.all()):
            problems.append(
                f"the two runs are not in the same state when the measured "
                f"step starts: {int((~same).sum())} of {same.size} "
                f"{name} values of the iteration-{FIRST_DUMP} dump differ, "
                f"so their tendency difference is not the runoff total")

    want = expected(case, run_dir, cell, before["theta"], before["salt"])
    result["expected"] = {k: v for k, v in want.items()
                          if k not in ("hFacC_dims",)}
    if not want["finite"]:
        problems.append("the analytic terms are not all finite")
    if want["tracForcingOutAB"] != 1.0:
        problems.append(f"tracForcingOutAB = {want['tracForcingOutAB']}, "
                        f"not 1: the forcing is inside Adams-Bashforth, so "
                        f"the state change of one step is not dt times the "
                        f"tendency")
    if want["nonlinFreeSurf"] != 0.0:
        problems.append(f"nonlinFreeSurf = {want['nonlinFreeSurf']}, not 0")
    text = read_file(run_dir, "output.txt") or ""
    if not re.search(r"implicitDiffusion\s*=.*\n.*\s+F\s*$",
                     "\n".join(ln for ln in text.splitlines()
                               if ") >" not in ln), re.MULTILINE):
        problems.append("the run does not report implicitDiffusion = F: "
                        "the state change of a step is then the implicit "
                        "solve applied to the tendency, not deltaT times "
                        "it")
    for name, value in (("temp_EvPrRn", case["temp_EvPrRn"]),
                        ("salt_EvPrRn", case["salt_EvPrRn"])):
        asked = UNSET_RL if value is None else value
        if abs(want[name] - asked) > 1.0e-12*max(1.0, abs(asked)):
            problems.append(f"the run reports {name} = {want[name]!r}, "
                            f"not the {asked!r} the case asked for")
    asked = -1.0 if case["branch"] == "L" else 35.0
    if want["convertFW2Salt"] != asked:
        problems.append(f"the run reports convertFW2Salt = "
                        f"{want['convertFW2Salt']!r}, not {asked!r}: it is "
                        f"not in branch {case['branch']}")

    # The package terms, as the package itself recorded them.
    measured = {}
    for key, stream in (("package_T", "rnfQnet"), ("package_S", "rnfSflx")):
        measured[key], label = dump_at(run_dir, stream, cell)
        result[key + "_dump"] = label
    for key, stream in (("total_T", "rnfTotT"), ("total_S", "rnfTotS")):
        case_value, label = dump_at(run_dir, stream, cell)
        zero_value, zlabel = dump_at(zero_dir, stream, cell)
        # degC/day and g/kg/day of the state difference over one step
        measured[key] = (case_value - zero_value)/86400.0
        result[key + "_dump"] = label
        result[key + "_zero_dump"] = zlabel
        result[key + "_raw"] = [case_value, zero_value]
    # The reference run applies no runoff at all, so its package terms
    # have to be exactly zero; otherwise the difference above is not the
    # total of this case.
    for key, stream in (("package_T", "rnfQnet"), ("package_S", "rnfSflx")):
        zero_value, _ = dump_at(zero_dir, stream, cell)
        if zero_value != 0.0:
            problems.append(f"the zero-flux run's {stream} at the target "
                            f"cell is {zero_value!r}, not 0")
    result["measured"] = measured

    rel = {}
    for key in ("package_T", "package_S", "total_T", "total_S"):
        ref = want[key]
        if abs(ref) < FLOOR:
            problems.append(f"{key} is {ref!r}, below the floor {FLOOR!r}: "
                            f"the case does not measure this term")
            rel[key] = None
            continue
        rel[key] = abs(measured[key] - ref)/abs(ref)
        if rel[key] > RTOL:
            problems.append(f"{key}: measured {measured[key]!r}, expected "
                            f"{ref!r}, relative {rel[key]:.3e} > {RTOL!r}")
    result["relative"] = rel

    # Where the row says the package term and the total differ, they have
    # to differ by much more than the tolerance, or the case would pass
    # without telling the two columns apart. The package terms are fluxes
    # and the totals tendencies, so the comparison is made in tendency
    # units, with the factors the model applies them with: the heat
    # through surfaceForcingT -= Qnet*mu/Cp, the salt through
    # surfaceForcingS += flux*mu, both times D at the surface level.
    to_tendency = {"T": -1.0/want["HeatCapacity_Cp"]*want["mu"]*want["D"],
                   "S": want["mu"]*want["D"]}
    for term in ("T", "S"):
        pack = want["package_" + term + "_tendency"]
        total = want["total_" + term]
        apart = abs(pack - total)/max(abs(pack), abs(total))
        result["apart_" + term] = apart
        differ = apart > RTOL*DISCRIMINATION
        result["differ_" + term] = differ
        if differ:
            measured_pack = measured["package_" + term]*to_tendency[term]
            got = abs(measured_pack - measured["total_" + term])
            scale = max(abs(measured_pack),
                        abs(measured["total_" + term]))
            if got/scale <= RTOL*DISCRIMINATION:
                problems.append(
                    f"{term}: the package term and the total are expected "
                    f"to differ by {apart:.3e} relative but the measured "
                    f"ones differ by {got/scale:.3e}")

    judge_tracer(case, run_dir, zero_dir, cell, dt, want, before, result,
                 problems)
    result["problems"] = problems
    return result


def check_case(case, args):
    """Run one case and its zero-flux reference, and judge them."""
    build = BUILD if case.get("atm_temp", True) else NOATM_BUILD
    if args.use_build:
        build = args.use_build
    binary = os.path.join(VERIF, EXPERIMENT, build, "mitgcmuv")
    if not os.path.isfile(binary):
        print(f"MISSING {case['name']}: no binary at {binary}")
        code = (write_noatm_code() if build == NOATM_BUILD
                else write_roft_code())
        print(f"     the code directory is written at {code}; build "
              f"it from {VERIF} with")
        print(f"       {compile_command(code, build)}")
        print("     or rerun this check with --build, which compiles "
              "what it needs")
        return None
    cell = sparse_info()["wet_cell"]
    runs = {}
    for zero_flux in (False, True):
        name = PREFIX + case["name"] + ("_zero" if zero_flux else "")
        input_dir = os.path.join(VERIF, EXPERIMENT, name)
        shutil.rmtree(input_dir, ignore_errors=True)
        os.makedirs(input_dir)
        dt = write_input(case, input_dir, zero_flux)
        run_dir, status, timed_out = run_model(name, build, args.timeout)
        runs[zero_flux] = (run_dir, status, timed_out, input_dir)
    bad = [f"{'zero' if z else 'case'} run exit {s}"
           + (" (timed out)" if t else "")
           for z, (_, s, t, _) in runs.items() if s != 0]
    if bad:
        print(f"FAIL {case['name']}: " + "; ".join(bad))
        return {"name": case["name"], "rows": list(case["rows"]),
                "problems": bad}
    result = judge(case, runs[False][0], runs[True][0], cell, dt)
    verdict = "PASS" if not result["problems"] else "FAIL"
    rel = result.get("relative", {})
    print(f"{verdict} {case['name']}: rows {', '.join(case['rows'])}; "
          + ", ".join(f"{k} {v:.2e}" for k, v in rel.items()
                      if v is not None))
    for problem in result["problems"]:
        print(f"     {problem}")
    if not args.keep:
        for _, _, _, input_dir in runs.values():
            shutil.rmtree(input_dir, ignore_errors=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", action="append", default=None,
                        help="run only this case (may be repeated)")
    parser.add_argument("--keep", action="store_true",
                        help="keep the scratch input directories")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json", help="write the measurements here")
    parser.add_argument("--build", action="store_true",
                        help="compile the binaries the selected cases "
                             "need, when missing or older than their "
                             "sources; without it a missing binary is "
                             "reported with its compile command and the "
                             "run exits 2")
    parser.add_argument("--use-build", default=None, metavar="NAME",
                        help="run every selected case on this lab_sea "
                             "build instead of its own: for the must-fail "
                             "demonstrations on mutant binaries, which "
                             "are never compiled into the builds this "
                             "check reuses")
    args = parser.parse_args(argv)
    if args.use_build and args.build:
        parser.error("--use-build names a binary built elsewhere; it does "
                     "not combine with --build")

    selected = CASES
    if args.case:
        names = {c["name"] for c in CASES}
        unknown = sorted(set(args.case) - names)
        if unknown:
            print(f"no such case: {', '.join(unknown)}")
            return 2
        selected = tuple(c for c in CASES if c["name"] in args.case)

    if args.build:
        # Only the builds the selection actually needs, in a fixed
        # order, so that --case does not pay for the other binary.
        wanted = [(BUILD, write_roft_code)]
        if any(not c.get("atm_temp", True) for c in selected):
            wanted.append((NOATM_BUILD, write_noatm_code))
        for build, writer in wanted:
            if not report_build(build_if_stale(build, writer,
                                               timeout=args.timeout*2)):
                return 2

    results = []
    missing_binary = False
    for case in selected:
        result = check_case(case, args)
        if result is None:
            missing_binary = True
            continue
        results.append(result)

    covered = set()
    for result in results:
        if not result["problems"]:
            covered.update(result["rows"])
    rows = tuple(T_ROWS) + tuple(S_ROWS) + tuple(C_ROWS)
    uncovered = [r for r in rows if r not in covered]
    print(f"{len(results)} case(s) run, "
          f"{sum(1 for r in results if not r['problems'])} passing; "
          f"{len(rows) - len(uncovered)} of {len(rows)} table rows covered")
    if uncovered:
        print("  rows with no passing case: " + ", ".join(uncovered))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"results": results, "uncovered": uncovered}, fh,
                      indent=1, default=str)
    # A missing binary is always exit 2: there is no flag that lets a run
    # report success with a table row that no case exercised. `--case`
    # is exempt from the coverage failure only, because a named
    # selection is asking for those cases and not for the whole table.
    if missing_binary:
        return 2
    if any(r["problems"] for r in results):
        return 1
    if uncovered and not args.case:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
