#!/usr/bin/env python3
"""Budget-closure oracle of the runoff volume, heat, salt and tracer (RUNOFF-016).

What this closes, and against what
==================================

``pkg/rnf`` spreads each source over its target cells and applies the
heat, salt and tracer it carries as *tendency* terms (package design,
decision 3), so for those three there is no dense field to compare
against. The existing numerical instruments are per-cell:
``tests/rnf/tendency_term_check.py`` compares the applied term with an
analytic row of the decision-3 table at **one** cell of **one** tile in a
single-process run, and ``tests/rnf/exf_heat_check.py`` cross-checks the
heat term alone against ``pkg/exf``'s own dense computation. Neither sums
over targets, and the tracer term had no numerical oracle at all.

This check sums. For every dump of every case, over **every cell of the
global layout** -- so over every tile of every process, and not only over
the cells the file names as targets, since water delivered to a cell the
file does not name has to enter the sum rather than be left out of it:

==========  ===================================  =========================
closure     summed over all cells                equals, over the sources
==========  ===================================  =========================
volume      ``RNF_vflx(c) * rA(c)``              ``sum_s flux_s``
heat        ``(mT)(c) * rA(c)``                  ``rhoConstFresh * sum_{s: T present} flux_s*T_s``
salt        ``(mS)(c) * rA(c)``                  ``rhoConstFresh * sum_s flux_s*S_s``
tracer n    ``(mC_n)(c) * rA(c)``                ``rhoConstFresh * sum_s flux_s*C_{s,n}``
==========  ===================================  =========================

A cell with no runoff contributes exactly 0 to all four, so the wider sum
costs nothing and cannot divide by a zero thickness: ``EXFroff`` is 0
there and the inverted tendency is 0 both because the package writes
nothing there and because the factor it is multiplied by vanishes wherever
``hFacC`` does.

The right-hand sides are the file's own source series at the record the
model reported for that step, so the closure is a statement about where
the water and its properties went, not about the arithmetic of one cell.
``docs/model_contract.md`` states it under Invariants.

How the four quantities are observed, with no model change
----------------------------------------------------------

``RNF_vflx`` is dumped directly: ``RNF_EXF_RUNOFF``
(``pkg/rnf/rnf_exf_runoff.F:140``) assigns it to the exf ``runoff`` array,
which ``EXF_DIAGNOSTICS_FILL`` publishes as ``EXFroff`` -- the same path
``tests/rnf/applied_field_check.py`` uses, and for the same reason.

``(mT)``, ``(mS)`` and ``(mC_n)`` are not dumped. What is dumped is the
tendency the package applied, through its own ``RNFgT``, ``RNFgS`` and
``RNFtrNN`` diagnostics, filled inside ``RNF_TENDENCY_APPLY_T``, ``_S``
and ``_PTR`` where the terms are computed
(``pkg/rnf/rnf_tendency_apply.F:188``, ``:341``, ``:500``):

    g_X = [ (mX) - m_X * X_ref ] * mass2rUnit * recip_drF(k)
                                              * recip_hFacC(i,j,k,bi,bj)

so each sum is recovered by undoing that one factor,

    (mX)(c) = g_X(c) * drF(ks) * hFacC(c,ks) / mass2rUnit
              + m_X(c) * X_ref(c)

with every number on the right taken from the run itself: ``mass2rUnit``
from its parameter dump (``model/src/config_summary.F:939``; it is read,
not re-derived from ``rhoConst``), ``drF(ks)`` from the ``delR``/``delZ``
of its own ``data``, ``hFacC`` from its own ``hFacC.data`` and ``rA`` from
its own ``RAC.data``.

**``hFacC`` has to be the one the term used.** Under ``NONLIN_FRSURF``
with ``nonlinFreeSurf > 0`` the model rewrites ``recip_hFacC`` at the
surface level on every step (``model/src/update_surf_dr.F:57``), and the
``hFacC.data`` written at initialization would then not be the value the
term was divided by. Every case therefore runs with
``nonlinFreeSurf = 0``, and :func:`judge` reads that back from the
parameter dump and fails the case if it is not 0 rather than trusting the
namelist. That also fixes the freshwater branch: with
``nonlinFreeSurf = 0`` and ``useRealFreshWaterFlux = .FALSE.`` the
package's salinity branch is the ``salt_EvPrRn`` one, which is where
``S_ref`` is a constant.

**``X_ref`` is reduced to zero or to a measured quantity, deliberately.**

* salt: ``salt_EvPrRn = 0`` is the MITgcm default
  (``model/src/set_defaults.F:265``) and makes ``S_ref`` exactly 0
  (``rnf_tendency_apply.F:296-297``), so ``(mS)`` comes straight out of
  ``RNFgS``. :func:`judge` asserts the run reported 0.
* tracer: ``PTRACERS_EvPrRn(1) = 0`` makes ``C_ref`` exactly 0
  (``rnf_tendency_apply.F:453-454``), asserted the same way.
* temperature: in a build with ``ALLOW_ATM_TEMP`` and ``ALLOW_RUNOFF``
  -- which both committed experiments have -- ``T_ref`` is the ambient
  ``theta`` whatever ``temp_EvPrRn`` is set to
  (``rnf_tendency_apply.F:145-149``), so it cannot be zeroed by a
  namelist. ``theta`` is read instead, from the run's own state dump of
  the iteration the dump belongs to (:func:`theta_at`), and ``m_T``
  comes from the reconstruction, which is where the missing-temperature
  rule lives. What that costs, and what pays for it, is the next
  section.

  A zero initial temperature would have removed ``T_ref`` altogether and
  is not available: MITgcm writes **no** snapshot of a negative-frequency
  diagnostic stream at the start time of a run, so the first dump of a
  run from iteration 0 is the *second* step and its ``theta`` has already
  moved (measured on this case: 150 of 320 values away from 0, the
  largest by 6.0e-2). That is the same fact
  ``tests/rnf/tendency_term_check.dump_at`` records from the other side,
  where a two-step run leaves exactly one snapshot and it carries the
  second step.

The missing-temperature rule, and why the heat closure can measure it
---------------------------------------------------------------------

A source whose temperature is missing in **any** record used is left out
of ``(mT)`` and of ``m_T`` and enters at ``T_ref``
(``RNF_LOAD_AT``, ``pkg/rnf/rnf_fields_load.F:336-359``). It is the rule
most likely to make a naive heat budget appear not to close, so the
right-hand side of the heat closure applies it: :func:`source_series`
reproduces the ``RNF_srcTvld`` logic, including the "any record used"
part, and the heat sum runs over the valid sources only.

On a case where every source carries a temperature at every record used,
``m_T`` **is** ``m``, and ``m = rhoConstFresh * RNF_vflx`` is dumped as
``EXFroff``: the inversion reads it off the model and assumes nothing.
:func:`judge` checks that premise rather than trusting the case
description, and fails a case without a declared ``missing`` whose
reconstruction has ``m_T`` different from its volume flux in any bit.

On a case that *does* leave a temperature out, ``m_T`` is smaller than
``m`` by the flux of the excluded sources and ``EXFroff`` cannot say by
how much, so ``m_T`` comes from the reconstruction instead. That does
**not** make the heat closure blind to the rule, and the reason is worth
stating because it is the opposite of what it looks like. What the
inversion gives is

    (mT)_measured = (mT)_model + ( m_T_oracle - m_T_model ) * theta

so a model that applied the rule differently from the oracle leaves a
residual proportional to the difference of the two ``m_T``. A model that
wrongly counted a missing-temperature source in ``m_T`` would have the
same ``(mT)`` -- ``RNF_srcTemp`` of an invalid source is 0
(``rnf_fields_load.F:354-357``), so it adds nothing to ``(mT)`` either
way -- and would fail here on the ``m_T`` term alone.

That the difference is large enough to see is measured, not assumed. Each
dump also reports ``heat_naive``, the same closure with the rule
*ignored*, i.e. with ``m_T`` taken as the whole ``m`` from ``EXFroff``;
:func:`judge` requires a case that declares ``missing`` to have ``heat``
within :data:`RTOL` and ``heat_naive`` above it by at least
:data:`DISCRIMINATION`, so the case cannot pass while the rule makes no
difference to the number (measured on ``lab_sea_missing``: ``heat``
3.850e-16 against ``heat_naive`` 1.946e-01). That case has one source
missing its temperature in every record and a second missing it in one
record of a pair the interpolating brackets of this time axis do use. On
every other case ``heat_naive`` and ``heat`` are the same measurement and
are reported as the same number.

Adams-Bashforth
---------------

The issue flags that with the forcing inside Adams-Bashforth
(``tracForcingOutAB != 1``, ``model/src/temp_integrate.F:367-372``) the
package term is extrapolated like the model's own forcing, so an
instantaneous per-step budget built from the **state change** would not
close. This check does not build one. It closes the term the package
itself recorded, read from the diagnostic filled inside
``RNF_TENDENCY_APPLY_*`` at the point the term is computed -- upstream of
``gT_loc``, of ``gtForc`` and of the extrapolation -- so the closure is
independent of the time-stepping scheme rather than made to work by
choosing one.

That is measured rather than argued, by the ``ab_out``/``ab_in`` pair:
two runs of the same case differing in exactly one namelist value,
``tracForcingOutAB`` 1 against 0. :func:`main` requires

* the **volume, salt and tracer** residuals to be **bitwise identical**
  between the two. Those three closures read no model state at all, so
  anything the extrapolation does to the solution cannot reach them;
* the **heat** residual to be within :data:`RTOL` in both. It is not
  required to be identical, and measuring it is what shows why: the heat
  closure is the one that reads ``theta``, for ``T_ref``, and the two
  runs' ``theta`` genuinely differ because the extrapolation really does
  change the solution. The residuals differ in their last bits only
  (measured 1.677e-16 against 1.608e-16, five orders below
  :data:`RTOL`);
* the two runs' ``theta`` to **differ**. Without that the pair would be
  two identical runs and the measurement would be vacuous, reporting
  insensitivity to a setting that had no effect (LL-014). The comparison
  is on ``state_signature``, an exact sum of the surface temperature of
  every judged dump.

The state-change form of the budget, which does need the forcing out of
Adams-Bashforth, is the one ``tests/rnf/tendency_term_check.py`` builds,
and that script already refuses to judge a run that does not report
``tracForcingOutAB = 1`` (``tendency_term_check.py:981-985``); the AB
claim of the issue is instrumented there, not here, and nothing in this
file measures a state-change budget.

The accumulation order
----------------------

``RNF_LOAD_AT`` accumulates the property sums in the same loop as the
volume, with ``wVol`` as a second expression of the same value, over the
tile's target entries in the file's table order
(``rnf_fields_load.F:446-471``), and that order is a contract:
``tests/rnf/applied_field_check.py`` rebuilds the volume field in it and
compares bitwise.

This check does not assume a different order is equivalent. Two separate
things are compared, with two different criteria:

* the **per-cell** fields (:func:`dense_fields`) are rebuilt in the
  file's table order, term by term, with the expressions
  ``rnf_fields_load.F`` uses, and compared cell by cell. Each cell
  belongs to exactly one tile, so the global table order restricted to a
  cell is the order that cell's tile accumulates in. This comparison is
  made to :data:`CELL_RTOL` and not bitwise, because the measured side
  passes through the division by ``mass2rUnit * D``, which the model
  never performs;
* the **budget** sums those per-cell values over cells and compares them
  with a sum over sources. Those are two different orders of summation of
  the same terms, and the model performs neither, so the budget is a
  physical invariant held to round-off and not a bitwise identity -- the
  same status, and for the same reason, as the applied-volume invariant
  of ``applied_field_check.check_case``. To keep the oracle's own
  summation error out of the residual, both sides are summed with
  ``math.fsum``, which is exact; what is left is the model's per-cell
  round-off, and the measured worst residual is reported so that the
  margin to :data:`RTOL` is a number and not a hope.

What a passing run establishes, and what the controls establish
---------------------------------------------------------------

Two controls run the model on a perturbed file, and they say opposite
things on purpose. Both perturbations are *accepted* by the package:
``RNF_INIT_FIXED`` refuses a per-source fraction sum that differs from 1
by more than ``RNF_fracTol = 1e-6`` (``rnf_init_fixed.F:911``), and both
stay inside that.

``--control permute`` permutes one source's fractions across its own
target cells and leaves the oracle asking for the committed file. A
budget **cannot** see this: the sums of the table are
``sum_c frac_{s,c} = 1`` whichever cell holds which fraction, so every
one of the four right-hand sides is unchanged by construction. The
control therefore requires the budget to **pass** and the per-cell
comparison to **fail**. That corrects the issue's premise, which has the
two the other way round, and it is reported as a measurement:
:func:`main` fails if the budget residual of the permuted run rises above
:data:`RTOL`.

``--control fracsum`` scales one source's fractions by
``1 + FRAC_PERTURB`` and lets the oracle read the perturbed file too. The
per-cell comparison then **passes** -- every cell holds exactly the value
the file asks for -- while the budget **fails**, because the source sends
``1 + FRAC_PERTURB`` times its flux into the ocean.

What that establishes is a statement about a **class** of criterion, and
it is worth stating exactly, because the looser version of it is false:

* **no per-cell criterion can see a fraction-sum error at all.** Every
  cell holds precisely the value the file asks for, so a comparison
  against the file matches bitwise however wrong the sum is. That covers
  the per-cell leg of this check, measured at round-off on the perturbed
  run, and ``applied_field_check``'s cell-by-cell comparison, which
  review B of this issue measured as bitwise equal with 0 extra and 0
  missing over 48 dumps of the perturbed file;
* **no other instrument's heat, salt or tracer criterion can see it,**
  because nothing else in the project sums those three against a source
  total. That is the coverage this check adds.

The volume leg is **not** novel, and the first version of this docstring
wrongly said it was. ``applied_field_check.check_case`` closes the same
volume invariant per record (``applied_field_check.py:873``,
``VOLUME_RTOL`` = 1e-12), and on this very perturbation review B measured
it **failing** at 1.4719309093e-07 -- the same figure this check reports,
and 147,000 times its tolerance. That is consistent with the volume leg
being a second, independent path to an existing invariant rather than new
coverage, which is what the "Volume conservation" row of the
qualification matrix now says.

Two instruments really are blind to it, for two different reasons that
should not be conflated:

* ``tendency_term_check`` is blind **by construction**: it writes
  ``frac[:] = 1.0`` and its oracle multiplies by a literal ``1.0``
  (``tendency_term_check.py:358`` and ``:879``) rather than by the file's
  fraction, so a fraction error is not representable in its cases;
* ``refusal_check`` and ``RNF_INIT_VARIA``'s own pair of sums are blind
  **by tolerance only**, which is weaker: the pair differs by less than
  ``RNF_fracTol`` so the model does not warn (:func:`judge` asserts the
  absence of that warning), and review B measured ``refusal_check``'s
  shipped flux-sum criterion at 1.15e-2 against an allowance of 7.83e-2,
  blind by a factor of 6.8 rather than structurally.

Coverage, and what is not measured
----------------------------------

``lab_sea`` (single process and 2 processes) is a 4-source, 7-target
file on a lat-lon grid with sources that feed two and three cells, a
fixed-period time axis so that the run moves through records and
interpolates between them, a temperature, a salinity and one passive
tracer. ``cs32`` (single process and 4 processes) is a 1189-source
one-record file on the cube sphere with six facets, where the sources are
spread over many tiles and -- on 4 processes -- over many processes; the
closure there is the statement that the per-tile source vectors and the
global layout add back up to the file.

The tracer closure runs only on ``lab_sea``. ``cs32`` does not compile
``pkg/ptracers`` (``verification/global_ocean.cs32x15/code/packages.conf``)
and giving it the package would change the binary every other committed
cs32 oracle is measured through, so the tracer closure is **not measured
on the cube sphere**. ``lab_sea``'s build has ``PTRACERS_num = 1``, so it
carries exactly one passive tracer: the closure is measured on a real
tracer with real values, but the mapping of several runoff tracers onto
several ptracers (``RNF_trPtr``) is **not** exercised, and an error that
swapped two runoff tracers would not show up here. The one tracer series
is also **degenerate across sources**: :func:`series` gives it
``1.0 + 0.2r + 0.1(k mod 3)``, which on lab_sea's four sources takes only
three distinct values, so sources 0 (``newfound``) and 3 (``baffin``)
carry identical tracer values at every record and this -- the project's
only tracer oracle -- cannot distinguish those two sources from each
other at all. The same shape leaves temperature with 7 and salinity with
5 distinct values over cs32's 1189 sources. The sums are correct either
way, because they are sums; but no reader should take them for
per-source resolution.

Nothing here measures the *choice* of record, which is
``tests/rnf/timing_field_check.py``'s and
``tests/runoff/lab_sea_runoff_timing_check.py``'s: the record each dump
applied is taken from the run's own ``RNF_FIELDS_LOAD`` trace, exactly as
``applied_field_check`` takes it. Nothing here measures branch N, the
lagged time level (``RNF_lagFlds``) or the state-change form of the
budget.

**Correct by inspection, unexercised in fact.** The ``hFacC`` factor of
the inversion is numerically **inert** on both configurations: measured,
``hFacC(:,:,1)`` is exactly 1.0 at all 7 lab_sea and all 1189 cs32 target
cells, and forcing it to 1.0 leaves every residual bitwise unchanged
(review A of this issue). So the factor is right by reading
``RNF_TENDENCY_APPLY_*`` and not by measurement here; a partial surface
cell, a cavity column under pkg/shelfice, or an r\* case is where it
would first actually be exercised.

**Where the must-fail controls run.** Both are enrolled, but not in the
same suite: ``focused`` carries only the ``fracsum`` control, so the
suite that runs on every candidate has **no must-fail for the per-cell
leg** -- the one that proves the per-cell criterion can see a
perturbation is the ``permute`` control, and it is in ``scientific``
only (review B).

Usage
=====

    python3 tests/rnf/budget_check.py [--case NAME ...] [--mpi N]
                                      [--control permute|fracsum]
                                      [--keep] [--json PATH] [--timeout S]

Exit status: 0 if every selected case passes, 1 if one fails or none ran,
2 if a binary is missing or a selection does not exist.
"""
import argparse
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from refusal_check import (ROOT, VERIF, add_to_namelist,  # noqa: E402
                           kill_run, read_file, replace_line)
from applied_field_check import (dump_name, dump_iteration,  # noqa: E402
                                 record_trace, set_namelist, time_step)
from tendency_term_check import param, read_mds  # noqa: E402

#: The scratch input directories this check writes, one per run.
PREFIX = "input.rnfbudget_"
#: Binary of the ordinary build; the MPI ones are this plus ``_mpiN``.
BUILD = "build_esx"
#: Name of the sparse file each case writes into its scratch input.
SPARSE_FILE = "runoff_budget.nc"
#: Diagnostic stream names, one file each.
STREAMS = {"vol": "rnfBudV", "heat": "rnfBudT", "salt": "rnfBudS",
           "tracer": "rnfBudC"}
#: Relative tolerance of every budget closure (RUNOFF-016 acceptance).
RTOL = 1.0e-12
#: Relative tolerance of the per-cell comparison. Not bitwise: the
#: measured side is divided by ``mass2rUnit * D``, which the model never
#: divides by, so the two sides are two roundings of the same formula.
CELL_RTOL = 1.0e-12
#: A volume source sum at or below this is not a measurement: a run whose
#: file asks for no water on any judged dump is reported as vacuous
#: rather than as a pass, because every closure's right-hand side would
#: then be zero and a relative residual of a zero reference is not
#: defined. It is a floor on the **volume** sum only, in m^3/s, because
#: the other three carry the units of their own property; those are held
#: against vacuity by the per-dump `nonzero_expected` count instead.
FLOOR = 1.0e-30
#: Fraction scaling of the ``fracsum`` control. Under ``RNF_fracTol``,
#: which is 1e-6 (``RNF.h:650``) and is compared against the per-source
#: fraction sum at ``rnf_init_fixed.F:911``, so the package accepts the
#: file; and five orders above :data:`RTOL` so the budget cannot miss it.
FRAC_PERTURB = 5.0e-7
#: Name of the passive tracer the lab_sea cases give the runoff, and the
#: ``runoff_ptracer_<NAME>`` variable that feeds it.
TRACER_NAME = "rnfbud"
#: How far above :data:`RTOL` the rule-ignoring heat closure
#: (``heat_naive``) has to be on a case that declares ``missing``, so that
#: the case really tells the missing-temperature rule apart from its
#: absence instead of passing where the rule makes no difference.
DISCRIMINATION = 1.0e3


DATA_DIAGNOSTICS = """# Budget-closure oracle of tests/rnf/budget_check.py.
# Snapshots (frequency < 0) through MDS (diag_mnc = .FALSE.) in float64
# (fileFlags 'D'), one per time step:
#   EXFroff  :: the exf runoff field, which RNF_EXF_RUNOFF has set to
#               RNF_vflx, i.e. the volume flux per unit area applied
#   RNFgT    :: the runoff temperature tendency term, as pkg/rnf applied
#               it, at the surface level
#   RNFgS    :: the same for salinity
#   RNFtr01  :: the same for runoff tracer 1 (lab_sea only)
# The three tendency streams are level 1 only: that is the surface level
# of every column of these set-ups (z coordinates, no pkg/shelfice), and
# the only level at which the terms are non-zero.
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
{streams} &

 &DIAG_STATIS_PARMS
 &
"""

DATA_PTRACERS = """# One passive tracer for the runoff tracer closure of
# tests/rnf/budget_check.py.
#   PTRACERS_EvPrRn(1) = 0 makes C_ref exactly 0 in
#     RNF_TENDENCY_APPLY_PTR, so the applied term is (mC_1)*mass2rUnit*D
#     and the budget can invert it without a reference value.
#   PTRACERS_Iter0 = {iter0} is nIter0, so the tracer is initialized from
#     PTRACERS_ref rather than from a pickup this scratch run has none of.
#   No GM/Redi and no KPP on the tracer, and no diffusion: the tendency
#     term the check reads is filled where pkg/rnf computes it, so none of
#     this changes what is measured; they are off so the run cannot fail
#     for a reason that has nothing to do with runoff.
 &PTRACERS_PARM01
 PTRACERS_numInUse = 1,
 PTRACERS_Iter0 = {iter0},
 PTRACERS_names(1) = '{name}',
 PTRACERS_long_names(1) = 'runoff budget check tracer',
 PTRACERS_units(1) = '1',
 PTRACERS_advScheme(1) = 30,
 PTRACERS_diffKh(1) = 0.,
 PTRACERS_diffKr(1) = 0.,
 PTRACERS_ref(:,1) = {nr}*0.,
 PTRACERS_EvPrRn(1) = 0.,
 PTRACERS_useGMRedi(1) = .FALSE.,
 PTRACERS_useKPP(1) = .FALSE.,
 &
"""

#: The cases.
#:
#: ``experiment``/``input``/``data_from`` locate the committed sparse
#: input to layer on, exactly as ``applied_field_check.CASES`` does.
#: ``table_from`` is the committed sparse file whose target table (source
#: ids, target_source, target_cell, target_fraction and the three
#: optional target_* columns) this check reuses; only the time axis and
#: the series are this check's own, so every placement check of
#: ``RNF_INIT_FIXED`` still sees a table it accepts.
#: ``records`` is the number of time records written, and ``period`` the
#: fixed period in units of the time step; ``None`` writes a one-record
#: constant file, which is what the cs32 case has to be because that
#: set-up runs with ``pkg/cal`` disabled (``-cal`` in its
#: ``packages.conf``) and so has no calendar for a dated time axis.
#: ``missing`` maps a source index to the records whose temperature is
#: missing, or to ``"all"``.
#: ``tracer`` asks for the passive-tracer closure.
#: ``minimal_pkgs`` switches off pkg/seaice, pkg/thsice, pkg/kpp and
#: pkg/gmredi; see :func:`write_input`.
#: ``steps`` is the number of time steps; ``mpi`` the process counts.
CASES = (
    {"name": "lab_sea", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "tracer": True, "mpi": (0, 2), "min_records": 2,
     "perturb_source": 3},
    # The cube sphere: 1189 sources over six facets and, on 4 processes,
    # over four processes. One constant record (no pkg/cal there).
    {"name": "cs32", "experiment": "global_ocean.cs32x15",
     "input": "input.rnof_sp_icedyn", "data_from": "input.icedyn",
     "table_from": ("global_ocean.cs32x15", "input.rnof_sp_icedyn",
                    "runoff_sparse_const.nc"),
     "records": None, "period": None, "steps": 3,
     "tracer": False, "mpi": (0, 4), "min_records": 1,
     "perturb_source": 0},
    # The missing-temperature rule. Source 0 has no temperature in any
    # record and source 1 has none in record 3, which the interpolating
    # brackets of this time axis do use, so both halves of the "missing in
    # any record used" rule are exercised. judge() requires the
    # rule-ignoring closure (heat_naive) to fail by DISCRIMINATION, so the
    # case cannot pass where the rule makes no difference.
    {"name": "lab_sea_missing", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "tracer": True, "mpi": (0, 2), "min_records": 2,
     "missing": {0: "all", 1: (3,)}, "perturb_source": 3},
    # The Adams-Bashforth pair. Two runs of the lab_sea case that differ
    # in exactly one namelist value, tracForcingOutAB, and in nothing
    # else: the four residuals have to come out identical, which is the
    # measurement that this instrument is upstream of the extrapolation.
    # Both carry ``minimal_pkgs`` because pkg/seaice refuses
    # tracForcingOutAB other than 1 outright, so the comparison could not
    # be made with it on; having it off in *both* is what keeps the pair
    # a one-variable comparison.
    {"name": "ab_out", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "tracer": True, "mpi": (0,), "min_records": 2,
     "trac_forcing_out_ab": 1, "minimal_pkgs": True,
     "perturb_source": 3},
    {"name": "ab_in", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "tracer": True, "mpi": (0,), "min_records": 2,
     "trac_forcing_out_ab": 0, "minimal_pkgs": True, "same_as": "ab_out",
     "perturb_source": 3},
)

#: The four closures the acceptance is about. ``heat_naive`` is measured
#: alongside them but is not one of them: it is the heat closure with the
#: missing-temperature rule deliberately ignored, and it is required to
#: *fail* on a case that declares ``missing``.
CLOSURES = ("volume", "heat", "salt", "tracer")
#: The closures that read no model state, and so cannot be moved by the
#: time-stepping scheme. The Adams-Bashforth pair requires these to come
#: out bitwise identical; "heat" is not among them because it reads
#: ``theta`` for ``T_ref``.
STATE_FREE = ("volume", "salt", "tracer")


def declared_closures(case):
    """Return the closures ``case`` is supposed to measure.

    All four except on a case without ``tracer``, where the file carries
    no ``runoff_ptracer_<NAME>`` variable and no tracer stream is dumped.
    :func:`judge` requires every closure this returns to be **present**
    in the measurement, so that one which stopped being measured fails
    instead of disappearing.
    """
    return tuple(c for c in CLOSURES if c != "tracer" or case["tracer"])


def table_path(case):
    """Absolute path of the committed file whose target table a case reuses."""
    experiment, directory, name = case["table_from"]
    return os.path.join(VERIF, experiment, directory, name)


def read_table(path):
    """Return the target table and grid of a committed sparse file.

    Only the static part: the source ids, which source each target entry
    belongs to, its cell, its fraction and the three optional ``target_*``
    columns, plus the grid size and the record-1 flux the series are
    scaled from. The time axis and every series are written fresh by
    :func:`write_sparse`.
    """
    import netCDF4
    import numpy as np
    with netCDF4.Dataset(path) as ds:
        ds.set_auto_maskandscale(False)
        table = {
            "ids": [str(s) for s in netCDF4.chartostring(ds["source_id"][:])],
            "target_source": np.asarray(ds["target_source"][:]).astype(int),
            "target_cell": np.asarray(ds["target_cell"][:]).astype(int),
            "target_fraction": np.asarray(
                ds["target_fraction"][:]).astype(np.float64),
            "nx": int(ds.getncattr("mitgcm_grid_nx")),
            "ny": int(ds.getncattr("mitgcm_grid_ny")),
            "flux1": np.asarray(ds["runoff_flux"][0], dtype=np.float64),
        }
        for name in ("target_cell_area", "target_lon", "target_lat"):
            if name in ds.variables:
                table[name] = np.asarray(ds[name][:], dtype=np.float64)
    table["nsrc"] = len(table["ids"])
    return table


def series(table, case):
    """Return the ``(nrec, nsrc)`` series the case's file carries.

    The flux of every record is the committed record-1 flux scaled by a
    factor that differs per record, so the run has something to
    interpolate and no record is a repeat of another; every factor is at
    most 1, so the applied field stays under the per-cell bound
    ``RNF_cellVolMax`` that the committed case already satisfies
    (``RNF_EXF_RUNOFF``), and under ``RNF_srcFluxMax``.

    The temperature, the salinity and the tracer vary with both the
    source and the record, and none of them is a multiple of the flux, so
    a flux-weighted sum cannot be confused with an unweighted one. The
    temperature of a source listed in ``missing`` is stored as the fill
    value in the records named there.

    Returns a dict of float64 arrays plus ``tvld``, the per-record
    validity flag of the temperature, which is what ``RNF_LOAD_REC``
    stores as ``RNF_bufTvld``.
    """
    import numpy as np
    nrec = case["records"] or 1
    nsrc = table["nsrc"]
    k = np.arange(nsrc, dtype=np.float64)
    out = {}
    # 1.0, 0.85, 0.7, 0.55, 0.4 ... : distinct, decreasing, all <= 1
    scale = 1.0 - 0.15 * np.arange(nrec, dtype=np.float64)
    out["flux"] = np.outer(scale, table["flux1"])
    # degC in a plausible river range, different for every (record,
    # source) pair and not proportional to the flux
    out["temp"] = (2.0 + 0.5 * np.arange(nrec, dtype=np.float64)[:, None]
                   + 0.25 * (k % 7.0)[None, :])
    # g/kg, small and non-zero: runoff is nearly fresh but the term must
    # carry what the file says
    out["salt"] = (0.1 + 0.03 * np.arange(nrec, dtype=np.float64)[:, None]
                   + 0.01 * (k % 5.0)[None, :])
    out["trc"] = (1.0 + 0.2 * np.arange(nrec, dtype=np.float64)[:, None]
                  + 0.1 * (k % 3.0)[None, :])
    tvld = np.ones((nrec, nsrc), dtype=np.float64)
    for src, where in (case.get("missing") or {}).items():
        if where == "all":
            tvld[:, src] = 0.0
        else:
            for record in where:
                tvld[record - 1, src] = 0.0
    out["tvld"] = tvld
    return out


def write_sparse(path, table, case, dt, perturb=None):
    """Write the sparse runoff file of one case.

    The target table is the committed one of ``table_from``; the time
    axis and every series are this check's own (:func:`series`).

    With ``records`` the axis is a fixed period of ``period`` time steps
    anchored on the model's own calendar start (``lab_sea/input/data.cal``:
    1979-01-01), which is the same axis
    ``tests/rnf/tendency_term_check.write_sparse`` writes and for the same
    reason: the record the model selects for a step is then a function of
    the step alone. Without it the file is one constant record, which is
    what a set-up with ``pkg/cal`` disabled can read.

    ``perturb`` is ``"permute"`` (the fractions of
    ``case["perturb_source"]`` cyclically shifted across its own target
    entries, which leaves their sum at exactly 1) or ``"fracsum"`` (those
    same fractions scaled by ``1 + FRAC_PERTURB``, which leaves the sum
    inside ``RNF_fracTol``). Returns what was perturbed, for the report.
    """
    import netCDF4
    import numpy as np
    value = series(table, case)
    nrec, nsrc = value["flux"].shape
    ntgt = table["target_cell"].size
    frac = table["target_fraction"].copy()
    done = None
    if perturb:
        src = case["perturb_source"]
        rows = np.flatnonzero(table["target_source"] == src)
        if perturb == "permute":
            if rows.size < 2:
                raise ValueError(
                    f"source {src} of {table['ids'][src]!r} has {rows.size} "
                    f"target entries: a permutation of its fractions across "
                    f"its own cells needs at least 2")
            frac[rows] = np.roll(table["target_fraction"][rows], 1)
            if bool((frac[rows] == table["target_fraction"][rows]).all()):
                raise ValueError(
                    f"the cyclic shift of the fractions of source {src} "
                    f"changed nothing: they are all equal, so this control "
                    f"would perturb nothing")
        elif perturb == "fracsum":
            frac[rows] = table["target_fraction"][rows] * (1.0 + FRAC_PERTURB)
        else:
            raise ValueError(f"unknown perturbation {perturb!r}")
        done = {"perturb": perturb, "source": table["ids"][src],
                "entries": rows.tolist(),
                "from": table["target_fraction"][rows].tolist(),
                "to": frac[rows].tolist(),
                "sum_from": float(table["target_fraction"][rows].sum()),
                "sum_to": float(frac[rows].sum())}
    with netCDF4.Dataset(path, "w") as ds:
        ds.set_auto_maskandscale(False)
        atts = {"mitgcm_runoff_schema_version": "1.0",
                "mitgcm_grid_nx": np.int32(table["nx"]),
                "mitgcm_grid_ny": np.int32(table["ny"]),
                "mitgcm_time_repeat": "none",
                "title": "sparse runoff with temperature, salinity and a "
                         "tracer for tests/rnf/budget_check.py"}
        if case["records"]:
            atts["mitgcm_time_sampling"] = "fixed"
            atts["mitgcm_time_period"] = np.float64(case["period"] * dt)
        else:
            atts["mitgcm_time_sampling"] = "constant"
        ds.setncatts(atts)
        ds.createDimension("time", nrec)
        ds.createDimension("source", nsrc)
        ds.createDimension("target", ntgt)
        width = max(len(s) for s in table["ids"])
        ds.createDimension("id_strlen", width)
        time = ds.createVariable("time", "f8", ("time",))
        time.units = "seconds since 1979-01-01 00:00:00"
        time.calendar = "gregorian"
        time.axis = "T"
        period = (case["period"] or 1) * dt
        time[:] = period * np.arange(nrec, dtype=np.float64)
        if case["records"]:
            ds.createDimension("nv", 2)
            time.bounds = "time_bnds"
            bnds = ds.createVariable("time_bnds", "f8", ("time", "nv"))
            bnds.units = time.units
            bnds.calendar = time.calendar
            bnds[:] = np.stack(
                [time[:], time[:] + period], axis=1)
        ids = np.array([list(s.ljust(width)) for s in table["ids"]],
                       dtype="S1")
        ds.createVariable("source_id", "S1", ("source", "id_strlen"))[:] = ids
        ds.createVariable("target_source", "i4",
                          ("target",))[:] = table["target_source"]
        ds.createVariable("target_cell", "i4",
                          ("target",))[:] = table["target_cell"]
        out = ds.createVariable("target_fraction", "f8", ("target",))
        out.units = "1"
        out[:] = frac
        for name, units in (("target_cell_area", "m2"),
                            ("target_lon", "degrees_east"),
                            ("target_lat", "degrees_north")):
            if name in table:
                out = ds.createVariable(name, "f8", ("target",))
                out.units = units
                out[:] = table[name]
        out = ds.createVariable("runoff_flux", "f8", ("time", "source"))
        out.units = "m3 s-1"
        out[:] = value["flux"]
        fill = np.float64(-9999.0)
        out = ds.createVariable("runoff_temperature", "f8",
                                ("time", "source"), fill_value=fill)
        out.units = "degC"
        out[:] = np.where(value["tvld"] > 0.0, value["temp"], fill)
        out = ds.createVariable("runoff_salinity", "f8", ("time", "source"))
        out.units = "g kg-1"
        out[:] = value["salt"]
        if case["tracer"]:
            out = ds.createVariable(f"runoff_ptracer_{TRACER_NAME}", "f8",
                                    ("time", "source"))
            out.units = "1"
            out[:] = value["trc"]
    return done


def source_series(table, case, records):
    """Return the source series of one step, as ``RNF_LOAD_AT`` builds them.

    ``records`` is ``(rec0, year0, rec1, year1, fac)`` as
    ``RNF_FIELDS_LOAD`` reported it for the step. The flux, the salinity
    and the tracer are combined the way ``rnf_fields_load.F:324-387``
    combines them:

    * ``fac == 1``: record ``rec0`` alone, with no arithmetic;
    * ``fac == 0``: record ``rec1`` alone;
    * otherwise ``fac*x(rec0) + (1-fac)*x(rec1)``.

    The temperature follows the same rule but only where it is valid, and
    its validity is the **conjunction** over the records used
    (``rnf_fields_load.F:336-359``): a source whose temperature is
    missing in either record of an interpolated pair is dropped from
    ``(mT)`` and from ``m_T`` for that step and enters at ``T_ref``. A
    dropped source gets ``tvld = 0`` and a temperature of 0, which is
    what ``RNF_srcTvld`` and ``RNF_srcTemp`` hold.

    The years are ignored: no case here uses a yearly file set, and
    :func:`judge` fails a run whose trace reports a non-zero year rather
    than quietly reading the wrong file.
    """
    import numpy as np
    value = series(table, case)
    rec0, _, rec1, _, fac = records
    need0, need1 = fac > 0.0, fac < 1.0

    def combine(name):
        """Interpolate one series between the two records, as the model does.

        The three branches are ``rnf_fields_load.F:325-333``'s, in its
        order: the earlier record alone when its weight is 1, the later
        alone when it is 0, and ``fac*x0 + (1-fac)*x1`` otherwise. The
        first two copy rather than compute, which is what makes
        hold-exact apply a value of the file and not a combination of
        two, so this reproduces that and does not multiply by 1.0.
        """
        if not need1:
            return value[name][rec0 - 1].copy()
        if not need0:
            return value[name][rec1 - 1].copy()
        return fac * value[name][rec0 - 1] \
            + (1.0 - fac) * value[name][rec1 - 1]

    tvld = np.ones(table["nsrc"], dtype=np.float64)
    if need0:
        tvld = np.where(value["tvld"][rec0 - 1] > 0.0, tvld, 0.0)
    if need1:
        tvld = np.where(value["tvld"][rec1 - 1] > 0.0, tvld, 0.0)
    temp = np.where(tvld > 0.0, combine("temp"), 0.0)
    out = {"flux": combine("flux"), "salt": combine("salt"),
           "trc": combine("trc"), "temp": temp, "tvld": tvld}
    return out


def dense_fields(table, source, rac, ncells, frac=None):
    """Return the dense per-cell fields ``RNF_LOAD_AT`` builds, in table order.

    ``sum over the tile's target entries`` of

        wVol  = flux_s * frac_{s,c} / rA(c)
        vflx += wVol                                 (its own expression)
        mflxT += wVol * tvld_s
        mXT   += wVol * tvld_s * T_s
        mXS   += wVol * S_s
        mXTr  += wVol * C_s

    then one pass multiplying the four property sums and the mass flux by
    ``rhoConstFresh`` (``rnf_fields_load.F:446-488``). The scaling by
    ``rhoConstFresh`` is left to the caller, which has the run's own
    value; what is returned is in volume-flux units, which is how the
    routine accumulates them.

    The terms are added in the file's table order, which is the order
    ``RNF_INIT_FIXED`` builds each tile's list in and therefore the order
    that tile accumulates in. ``vflx`` is accumulated with the single
    expression ``flux*frac/rA`` and the properties with ``wVol``, as the
    two statements of the routine are written, so that the comparison is
    of two evaluations of the same formula.

    ``frac`` overrides the table's fractions, which is how the controls
    give the model one set and the oracle another.
    """
    import numpy as np
    fraction = table["target_fraction"] if frac is None else frac
    out = {k: np.zeros(ncells, dtype=np.float64)
           for k in ("vflx", "mflxT", "mXT", "mXS", "mXTr")}
    cells = table["target_cell"]
    owner = table["target_source"]
    for k in range(cells.size):
        c = int(cells[k])
        s = int(owner[k])
        out["vflx"][c] += source["flux"][s] * fraction[k] / rac[c]
        w = source["flux"][s] * fraction[k] / rac[c]
        out["mflxT"][c] += w * source["tvld"][s]
        out["mXT"][c] += w * source["tvld"][s] * source["temp"][s]
        out["mXS"][c] += w * source["salt"][s]
        out["mXTr"][c] += w * source["trc"][s]
    return out


def diagnostics_text(case, dt):
    """Return the ``data.diagnostics`` of a case: one stream per quantity."""
    wanted = [("vol", "EXFroff ", None), ("heat", "RNFgT   ", 1),
              ("salt", "RNFgS   ", 1)]
    if case["tracer"]:
        wanted.append(("tracer", "RNFtr01 ", 1))
    lines = []
    for n, (key, field, level) in enumerate(wanted, start=1):
        lines.append(f"  fields(1,{n}) = '{field}',")
        lines.append(f"  fileName({n}) = '{STREAMS[key]}',")
        lines.append(f"  frequency({n}) = -{dt!r},")
        if level is not None:
            lines.append(f"  levels(1,{n}) = {float(level)!r},")
        lines.append(f"  fileFlags({n}) = 'D       ',")
    return DATA_DIAGNOSTICS.format(streams="\n".join(lines) + "\n")


def nr_of(data):
    """Return Nr, the number of vertical levels, from a ``data`` text.

    Counted from the ``delR``/``delZ`` list, which may run over several
    continuation lines. ``ValueError`` if neither is set, so a case can
    never be run against a layer count guessed for it.
    """
    match = re.search(r"^\s*del[RZ]\s*=\s*((?:[^&\n]*\n)*?)\s*(?=\S*\s*=|&)",
                      data, re.MULTILINE)
    if not match:
        raise ValueError("data sets neither delR nor delZ")
    body = match.group(1).split("#")[0]
    numbers = re.findall(r"(\d+)\s*\*\s*[-+0-9.DdEe]+|[-+0-9.DdEe]+", body)
    total = 0
    for repeat in numbers:
        total += int(repeat) if repeat else 1
    if total < 1:
        raise ValueError(f"data's delR/delZ list has no values: {body!r}")
    return total


def layer_thickness(run_dir):
    """Return delR(1) of the run's own ``data``, in metres.

    **Limitation (review A).** This takes the first number after
    ``delR=``/``delZ=``, so a list written in the repeat form
    ``delR = 23*10.,`` would return 23.0 rather than 10.0. Both
    configurations this check runs list their levels explicitly, and a
    wrong thickness fails loudly rather than quietly -- it enters the
    inversion linearly, so the residual moves by the same factor, with a
    gain of 1.0 against a 1e-12 criterion. :func:`nr_of`, which parses
    the same list for the level *count*, does handle the repeat form; this
    function deliberately does not acquire a second parser for a form no
    case uses, and the asymmetry is recorded here rather than hidden.
    """
    data = read_file(run_dir, "data")
    if data is None:
        raise ValueError(f"{run_dir} has no data file")
    match = re.search(r"^\s*del[RZ]\s*=\s*([-+0-9.DdEe]+)", data,
                      re.MULTILINE)
    if not match:
        raise ValueError("data sets neither delR nor delZ")
    return float(match.group(1).replace("D", "E").replace("d", "e"))


def write_input(case, input_dir, table, perturb=None):
    """Build the scratch input directory of one run; return ``(dt, info)``.

    Every regular file of the case's committed sparse input is copied,
    then ``data`` comes from ``data_from`` with the settings the oracle
    needs, ``data.diagnostics``, ``data.rnf`` and -- for a tracer case --
    ``data.ptracers`` are written, and the sparse file of
    :func:`write_sparse` replaces the committed one.

    The settings in ``data`` are of three kinds, and they are listed
    apart because they are not equally innocent:

    * output only: ``writeBinaryPrec = 64`` (so the dumps, ``RAC.data``
      and ``hFacC.data`` are float64), ``outputTypesInclusive`` (so the
      grid files are written through MDS even where the set-up uses MNC),
      ``dumpFreq`` and ``dumpInitAndLast`` (so the state dump the
      temperature reference is read from exists at every step), and a
      shorter ``endTime``/``nTimeSteps``;
    * needed by the measurement, and read back from the parameter dump by
      :func:`judge` so that no case is judged against a setting it did
      not run: ``nonlinFreeSurf = 0``, which is what makes
      ``recip_hFacC`` the static one the run's ``hFacC.data`` holds --
      its only rewrite is guarded by
      ``useLatest .AND. nonlinFreeSurf.GT.0``
      (``update_surf_dr.F:49``, assigning at ``:57``) -- and
      ``salt_EvPrRn = 0``, so that ``S_ref`` is 0;
    * needed, but **not** read back, and not for the reason an earlier
      version of this docstring gave: ``useRealFreshWaterFlux = .FALSE.``
      and ``select_rStar = 0``. Neither has any bearing on
      ``recip_hFacC``; the guard above names only ``nonlinFreeSurf``.
      ``select_rStar = 0`` is there because ``CONFIG_CHECK`` refuses r*
      with a linear free surface, and ``useRealFreshWaterFlux = .FALSE.``
      only reaches the salinity and tracer branch tests
      (``rnf_tendency_apply.F:298-299`` and ``:455-456``), which
      ``salt_EvPrRn = 0`` and ``PTRACERS_EvPrRn(1) = 0`` already
      short-circuit -- so it changes nothing this check measures and is
      set for consistency with ``nonlinFreeSurf = 0`` rather than out of
      need;
    * the case's own: ``tracForcingOutAB`` where the case sets it, also
      read back by :func:`judge`.
    """
    exp_dir = os.path.join(VERIF, case["experiment"])
    base = os.path.join(exp_dir, case["input"])
    for name in sorted(os.listdir(base)):
        src = os.path.join(base, name)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(input_dir, name))
    with open(os.path.join(exp_dir, case["data_from"], "data")) as fh:
        data = fh.read()
    dt = time_step(data)
    nr = nr_of(data)
    settings = [
        ("PARM01", "writeBinaryPrec", " writeBinaryPrec=64,"),
        ("PARM03", "outputTypesInclusive", " outputTypesInclusive=.TRUE.,"),
        ("PARM03", "dumpFreq", f" dumpFreq={dt!r},"),
        ("PARM03", "dumpInitAndLast", " dumpInitAndLast=.TRUE.,"),
        ("PARM03", "pChkptFreq", " pChkptFreq=0.,"),
        ("PARM03", "chkptFreq", " chkptFreq=0.,"),
        # monitorFreq is deliberately left alone: nothing here reads the
        # monitor, and cs32's own `data` sets it twice (the second wins in
        # Fortran), so touching it would stop on an ambiguity that has no
        # bearing on the measurement.
        ("PARM01", "nonlinFreeSurf", " nonlinFreeSurf=0,"),
        # r* goes with a nonlinear free surface and CONFIG_CHECK refuses
        # the pair ("r* Coordinate (select_rStar= 2) cannot be used with
        # Linear FreeSurf"), so the two are set together. cs32's own
        # `data` sets select_rStar=2.
        ("PARM01", "select_rStar", " select_rStar=0,"),
        ("PARM01", "useRealFreshWaterFlux",
         " useRealFreshWaterFlux=.FALSE.,"),
        ("PARM01", "salt_EvPrRn", " salt_EvPrRn=0.,"),
    ]
    if case.get("trac_forcing_out_ab") is not None:
        settings.append(("PARM03", "tracForcingOutAB",
                         f" tracForcingOutAB={case['trac_forcing_out_ab']},"))
    # The run length. Both forms are set where the file uses them, so the
    # one the set-up actually reads is the one that is shortened.
    if re.search(r"(?m)^\s*nTimeSteps\s*=", data):
        settings.append(("PARM03", "nTimeSteps",
                         f" nTimeSteps={case['steps']},"))
    start = re.search(r"(?m)^\s*startTime\s*=\s*([-+0-9.DdEe]+)", data)
    if start and not re.search(r"(?m)^\s*nTimeSteps\s*=", data):
        t0 = float(start.group(1).replace("D", "E").replace("d", "e"))
        settings.append(("PARM03", "endTime",
                         f" endTime={t0 + case['steps'] * dt!r},"))
    for namelist, name, line in settings:
        data = set_namelist(data, namelist, name, line)
    with open(os.path.join(input_dir, "data"), "w") as fh:
        fh.write(data)

    with open(os.path.join(input_dir, "data.diagnostics"), "w") as fh:
        fh.write(diagnostics_text(case, dt))

    # Packages. A tracer case needs pkg/ptracers on. A case with
    # ``minimal_pkgs`` switches off pkg/seaice, pkg/thsice, pkg/kpp and
    # pkg/gmredi. None of them can change the term this check reads, which
    # pkg/rnf fills where it computes it rather than through the state,
    # but pkg/seaice refuses any ``tracForcingOutAB`` other than 1
    # outright (``SEAICE_CHECK``: "Need T,S forcing out of AB"), which is
    # exactly what the Adams-Bashforth pair has to vary. Both halves of
    # that pair carry the flag, so having it is not a difference between
    # them.
    pkg_path = os.path.join(input_dir, "data.pkg")
    pkg = read_file(input_dir, "data.pkg")
    if pkg is None:
        raise ValueError(f"{case['input']} has no data.pkg")
    flags = {"useDiagnostics": ".TRUE.", "useRNF": ".TRUE.",
             "useMNC": ".FALSE."}
    if case["tracer"]:
        flags["usePTRACERS"] = ".TRUE."
    if case.get("minimal_pkgs"):
        flags.update({"useSEAICE": ".FALSE.", "useKPP": ".FALSE.",
                      "useGMRedi": ".FALSE.", "useThSIce": ".FALSE."})
    for name, value in flags.items():
        line = f"  {name} = {value},"
        pkg = (replace_line(pkg, name, line)
               if re.search(r"(?mi)^\s*%s\s*=" % re.escape(name), pkg)
               else add_to_namelist(pkg, "PACKAGES", line))
    with open(pkg_path, "w") as fh:
        fh.write(pkg)

    if case["tracer"]:
        iter0 = 0
        start = re.search(r"(?m)^\s*nIter0\s*=\s*(\d+)",
                          read_file(input_dir, "data") or "")
        if start:
            iter0 = int(start.group(1))
        else:
            begin = re.search(r"(?m)^\s*startTime\s*=\s*([-+0-9.DdEe]+)",
                              read_file(input_dir, "data") or "")
            if begin:
                iter0 = int(round(float(begin.group(1).replace("D", "E")
                                        .replace("d", "e")) / dt))
        with open(os.path.join(input_dir, "data.ptracers"), "w") as fh:
            fh.write(DATA_PTRACERS.format(iter0=iter0, name=TRACER_NAME,
                                          nr=nr))
        # lab_sea compiles pkg/longstep (its packages.conf), and that
        # package stops the run for a missing data.longstep as soon as
        # usePTRACERS is true (longstep_readparms.F:46-69) -- there is no
        # useLongStep flag to switch it off. LS_nIter = 1 takes a passive
        # tracer step on every dynamics step, so nothing is skipped and
        # the tracer term is applied, and dumped, at every step. This
        # could not change what is measured either way: the term read
        # here is the diagnostic pkg/rnf fills where it computes it, not
        # a state change.
        with open(os.path.join(input_dir, "data.longstep"), "w") as fh:
            fh.write("# Written by tests/rnf/budget_check.py: one passive\n"
                     "# tracer step per dynamics step, so no step is\n"
                     "# skipped and RNFtr01 is filled on every one.\n"
                     " &LONGSTEP_PARM01\n"
                     "  LS_nIter = 1,\n"
                     "  LS_whenToSample = 0,\n"
                     " &\n")

    # A prepare_run must not link the committed data files over the ones
    # written here.
    prep = os.path.join(input_dir, "prepare_run")
    if os.path.isfile(prep):
        with open(prep) as fh:
            text = fh.read()
        new, count = re.subn(
            r'skipList="([^"]*)"',
            r'skipList="\1 data data.diagnostics data.pkg data.ptracers'
            r' data.longstep"',
            text)
        if count != 1:
            raise ValueError(f"{case['input']}/prepare_run has {count} "
                             f"skipList assignments, expected 1")
        with open(prep, "w") as fh:
            fh.write(new)
        os.chmod(prep, os.stat(prep).st_mode | stat.S_IXUSR | stat.S_IXGRP
                 | stat.S_IXOTH)

    info = write_sparse(os.path.join(input_dir, SPARSE_FILE), table, case,
                        dt, perturb=perturb)
    with open(os.path.join(input_dir, "data.rnf"), "w") as fh:
        fh.write("# Written by tests/rnf/budget_check.py.\n"
                 "# RNF_debugLev = 3 (debLevC) makes RNF_FIELDS_LOAD print,\n"
                 "# at every step, the records it bracketed and the weight\n"
                 "# of the earlier one. That trace is what names the record\n"
                 "# each dump applied; it only prints and changes no value.\n"
                 " &RNF_PARM01\n"
                 f"  RNF_file = '{SPARSE_FILE}',\n"
                 "  RNF_debugLev = 3,\n"
                 " &\n")
    return dt, info


def run_model(experiment, input_name, nproc, timeout):
    """Run one scratch input; return ``(run dir, exit status, timed out)``."""
    output_name = "output_esx_" + input_name
    build, mpi_args = BUILD, []
    if nproc:
        output_name += f"_mpi{nproc}"
        build += f"_mpi{nproc}"
        mpi_args = ["-mpi", str(nproc)]
    run_dir = os.path.join(VERIF, experiment, output_name)
    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        proc = subprocess.run(
            ["./experiment_run_no_compile.sh", experiment, input_name]
            + mpi_args + ["-build", build, "-output", output_name],
            cwd=VERIF, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout)
        return run_dir, proc.returncode, False
    except subprocess.TimeoutExpired:
        kill_run(output_name)
        return run_dir, -1, True


def stream_dumps(run_dir, stream):
    """Return the iterations of a stream's dumps, and anything unexpected.

    Same contract as ``applied_field_check.dumps``, for an arbitrary
    stream name: a file that matches the wider glob without being a dump
    is reported rather than skipped (LL-008).
    """
    import glob
    pattern = dump_name(stream)
    iterations, strays = [], []
    for path in sorted(glob.glob(os.path.join(run_dir, stream + "*"))):
        base = os.path.basename(path)
        if base.endswith(".meta") and pattern.match(base[:-5] + ".data"):
            if os.path.isfile(path[:-5] + ".data"):
                continue
            strays.append(base + " (no matching .data)")
            continue
        match = pattern.match(base)
        if match:
            iterations.append(match.group(1))
        else:
            strays.append(base)
    return iterations, strays


def level1(field, sizes, ncells):
    """Return the first horizontal level of a dumped field, as a flat array.

    An MDS dump of one level is written either as a 2-D array or as a
    3-D one with a single level, and a state dump is 3-D with ``Nr``.
    ``ValueError`` if the horizontal size is not ``ncells``, so a dump of
    a different layout is refused rather than sliced.
    """
    if sizes[0] * sizes[1] != ncells:
        raise ValueError(f"a dump of shape {sizes} has {sizes[0] * sizes[1]} "
                         f"horizontal values, not the {ncells} of RAC.data")
    return field[:ncells]


def measure(case, run_dir, table, oracle_frac, iterations):
    """Measure the four closures on every judged dump of one run.

    Returns a dictionary with the run's parameters, the per-dump
    residuals and the worst of each closure. Everything the inversion
    needs is read from this run: see the module docstring.
    """
    import numpy as np
    text = read_file(run_dir, "output.txt") or ""
    out = {"params": {}}
    for name in ("mass2rUnit", "rhoConstFresh", "rhoConst", "salt_EvPrRn",
                 "convertFW2Salt", "nonlinFreeSurf", "tracForcingOutAB",
                 "temp_EvPrRn"):
        out["params"][name] = param(text, name)
    if case["tracer"]:
        out["params"]["PTRACERS_EvPrRn"] = param(text, "PTRACERS_EvPrRn")
    mu = out["params"]["mass2rUnit"]
    rho_fresh = out["params"]["rhoConstFresh"]

    rac, rac_sizes = read_mds(run_dir, "RAC")
    ncells = rac.size
    hfac, hfac_sizes = read_mds(run_dir, "hFacC")
    hfac1 = level1(hfac, hfac_sizes, ncells)
    drf1 = layer_thickness(run_dir)
    out["grid"] = {"cells": ncells, "RAC_dims": rac_sizes,
                   "hFacC_dims": hfac_sizes, "drF1": drf1}

    cells = np.unique(table["target_cell"])
    out["target_cells"] = int(cells.size)
    if float(hfac1[cells].min()) <= 0.0:
        raise ValueError(
            f"{int((hfac1[cells] <= 0.0).sum())} of {cells.size} target cells "
            f"have hFacC(:,:,1) <= 0 in this run: the tendency term there is "
            f"divided by a zero thickness and cannot be inverted")
    # 1/(mass2rUnit*D) with D = recip_drF(1)*recip_hFacC(:,:,1), as
    # RNF_TENDENCY_APPLY_* applies it.
    inverse = drf1 * hfac1 / mu

    trace = record_trace(run_dir)
    out["traced"] = len(trace)
    # Every dump of the run is judged. There is no selection: a dump the
    # model wrote and this check skipped would be coverage it did not have.
    out["dumps"] = list(iterations)

    out["per_dump"] = []
    out["records_applied"] = []
    out["state_signature"] = []
    for iteration in iterations:
        step = dump_iteration(iteration)
        if step not in trace:
            raise ValueError(f"no RNF_FIELDS_LOAD trace for iteration "
                             f"{step}, the forcing step of dump {iteration}; "
                             f"{len(trace)} steps traced (needs "
                             f"RNF_debugLev >= 3)")
        records = trace[step]
        if records[1] or records[3]:
            raise ValueError(f"the trace of iteration {step} reports file "
                             f"years {records[1]} and {records[3]}: this "
                             f"check writes no yearly file set and cannot "
                             f"name the file those records came from")
        key = list(records[:4])
        if key not in out["records_applied"]:
            out["records_applied"].append(key)

        source = source_series(table, case, records)
        want = dense_fields(table, source, rac, ncells, frac=oracle_frac)
        # The model's own values, inverted back to the loaded fields.
        applied, sizes = read_mds(run_dir, f"{STREAMS['vol']}.{iteration}")
        v_got = level1(applied, sizes, ncells)
        got = {"vflx": v_got}
        for key_q, name in (("mXT", "heat"), ("mXS", "salt"),
                            ("mXTr", "tracer")):
            if name == "tracer" and not case["tracer"]:
                continue
            raw, sizes = read_mds(run_dir, f"{STREAMS[name]}.{iteration}")
            got[key_q] = level1(raw, sizes, ncells) * inverse
        # T_ref is the ambient theta of the iteration this dump belongs
        # to; (mT) = RNFgT/(mass2rUnit*D) + m_T*theta.
        #
        # ``mXT_naive`` always takes m_T as the whole mass flux, from the
        # model's own EXFroff dump: m_T = rhoConstFresh*RNF_vflx, which is
        # what m_T *is* when every source carries a temperature. On a case
        # with no missing temperature that is the measurement, and nothing
        # about m_T is assumed -- in particular it is also the measurement
        # on the permute control, where the oracle and the model
        # deliberately disagree about the fractions and a reconstructed
        # m_T would make the heat closure sensitive to that disagreement
        # through T_ref rather than through the transport.
        #
        # ``mXT`` differs from it only on a case that declares ``missing``,
        # where m_T is smaller than m and EXFroff cannot say by how much:
        # there it comes from the reconstruction, which is where the
        # missing-temperature rule lives. The two together are what make
        # the rule measurable (module docstring).
        theta = theta_at(run_dir, iteration, ncells)
        out["state_signature"].append(math.fsum(theta.tolist()))
        got["mXT_naive"] = got["mXT"] + rho_fresh * v_got * theta
        got["mXT"] = got["mXT"] + rho_fresh * (
            want["mflxT"] if case.get("missing") else v_got) * theta
        # The reconstruction is in volume-flux units; the property sums
        # the model holds are rhoConstFresh times them.
        want_scaled = {"vflx": want["vflx"]}
        for key_q in ("mflxT", "mXT", "mXS", "mXTr"):
            want_scaled[key_q] = rho_fresh * want[key_q]

        entry = {"iteration": iteration, "records": records,
                 "fac": records[4]}
        # --- the budget: sums over all cells against sums over sources
        flux = source["flux"]
        rhs = {
            "volume": math.fsum(flux.tolist()),
            "heat": rho_fresh * math.fsum(
                (flux * source["tvld"] * source["temp"]).tolist()),
            "salt": rho_fresh * math.fsum((flux * source["salt"]).tolist()),
        }
        rhs["heat_naive"] = rhs["heat"]
        # Over **every** cell of the layout, not only the file's target
        # cells, so that water or property delivered to a cell the file
        # does not name enters the sum rather than being left out of it.
        # A cell with no runoff contributes exactly 0 to all four: EXFroff
        # is 0 there, and the tendency diagnostics are 0 both because the
        # package writes nothing there and because `inverse` is 0 wherever
        # hFacC is (a dry cell), which is also why this cannot divide by a
        # zero thickness.
        lhs = {
            "volume": math.fsum((got["vflx"] * rac).tolist()),
            "heat": math.fsum((got["mXT"] * rac).tolist()),
            "heat_naive": math.fsum((got["mXT_naive"] * rac).tolist()),
            "salt": math.fsum((got["mXS"] * rac).tolist()),
        }
        if case["tracer"]:
            rhs["tracer"] = rho_fresh * math.fsum(
                (flux * source["trc"]).tolist())
            lhs["tracer"] = math.fsum((got["mXTr"] * rac).tolist())
        entry["source_sum"] = rhs
        entry["target_sum"] = lhs
        entry["residual"] = {
            k: (abs(lhs[k] - rhs[k]) / abs(rhs[k]) if rhs[k] else None)
            for k in rhs}
        # --- the per-cell criterion, on the same dump
        cell = {}
        for key_q, name in (("vflx", "volume"), ("mXT", "heat"),
                            ("mXS", "salt"), ("mXTr", "tracer")):
            if key_q not in got:
                continue
            ref = want_scaled[key_q]
            with np.errstate(divide="ignore", invalid="ignore"):
                rel = np.where(ref != 0.0,
                               np.abs(got[key_q] - ref) / np.abs(ref),
                               np.where(got[key_q] != 0.0, 1.0, 0.0))
            rel = np.where(np.isfinite(rel), rel, np.inf)
            worst = int(np.argmax(rel))
            cell[name] = {"max_rel": float(rel[worst]), "cell": worst,
                          "applied": float(got[key_q][worst]),
                          "expected": float(ref[worst])}
        entry["per_cell"] = cell
        entry["extra"] = int(np.count_nonzero(
            (got["vflx"] != 0.0) & (want_scaled["vflx"] == 0.0)))
        entry["missing"] = int(np.count_nonzero(
            (got["vflx"] == 0.0) & (want_scaled["vflx"] != 0.0)))
        entry["nonfinite"] = int(sum(
            int(np.count_nonzero(~np.isfinite(v))) for v in got.values()))
        # m_T against m, on the reconstruction: what makes m_T a measured
        # quantity on a case without `missing`, and the discrimination of
        # the one with it.
        entry["mflxT_equals_mflx"] = bool(
            (want["mflxT"] == want["vflx"]).all())
        volume = math.fsum((want["vflx"] * rac).tolist())
        entry["mflxT_over_mflx"] = (
            math.fsum((want["mflxT"] * rac).tolist()) / volume
            if volume else None)
        entry["nonzero_expected"] = int(
            np.count_nonzero(want_scaled["vflx"]))
        out["per_dump"].append(entry)

    out["worst"] = {}
    for name in CLOSURES + ("heat_naive",):
        values = [(d["residual"][name], d["iteration"])
                  for d in out["per_dump"] if name in d["residual"]
                  and d["residual"][name] is not None]
        if values:
            out["worst"][name] = max(values)
    out["worst_cell"] = {}
    for name in ("volume", "heat", "salt", "tracer"):
        values = [(d["per_cell"][name]["max_rel"], d["iteration"])
                  for d in out["per_dump"] if name in d["per_cell"]]
        if values:
            out["worst_cell"][name] = max(values)
    return out


def theta_at(run_dir, iteration, ncells):
    """Return the surface potential temperature of iteration ``iteration``.

    The state dump labelled N is the state at iteration N, and the
    snapshot of a negative-frequency diagnostic stream labelled N carries
    the field loaded at iteration N
    (``applied_field_check.dump_iteration``), which is the forcing applied
    over the step that starts from that state. So the two labels line up,
    which is the same pairing
    ``tests/rnf/tendency_term_check.judge`` makes when it evaluates the
    analytic term with the ``theta`` of the dump labelled
    ``FIRST_DUMP``.
    """
    field, sizes = read_mds(run_dir, "T." + iteration)
    return level1(field, sizes, ncells)


def judge(case, run_dir, result, control=None):
    """Compare the measured closures with what the case asks for.

    ``problems`` lists every unmet expectation, so an empty list is a
    pass. The verdict of a control is inverted in the way that control
    asks for: see the module docstring.
    """
    problems = result["problems"]
    data = result["measure"]
    params = data["params"]

    # --- premises, read back from the run
    if params["nonlinFreeSurf"] != 0.0:
        problems.append(
            f"nonlinFreeSurf = {params['nonlinFreeSurf']}, not 0: the model "
            f"rewrites recip_hFacC at the surface every step "
            f"(update_surf_dr.F:57), so the run's hFacC.data is not the "
            f"thickness the tendency term was divided by")
    if params["salt_EvPrRn"] != 0.0:
        problems.append(
            f"salt_EvPrRn = {params['salt_EvPrRn']}, not 0: S_ref is then "
            f"not 0 and RNFgS is not (mS)*mass2rUnit*D")
    if case["tracer"] and params.get("PTRACERS_EvPrRn") != 0.0:
        problems.append(
            f"PTRACERS_EvPrRn(1) = {params.get('PTRACERS_EvPrRn')}, not 0: "
            f"C_ref is then not 0 and RNFtr01 is not (mC_1)*mass2rUnit*D")
    want_ab = case.get("trac_forcing_out_ab", 1)
    if params["tracForcingOutAB"] != float(want_ab):
        problems.append(f"tracForcingOutAB = {params['tracForcingOutAB']}, "
                        f"not the {want_ab} this case asked for")
    if data["traced"] < len(data["dumps"]):
        problems.append(f"a RNF_FIELDS_LOAD record trace for every dump "
                        f"({data['traced']} traced, "
                        f"{len(data['dumps'])} dumps)")
    if len(data["records_applied"]) < case.get("min_records", 1):
        problems.append(
            f"at least {case['min_records']} distinct record selections over "
            f"the judged dumps (found {len(data['records_applied'])}: "
            f"{data['records_applied']}): a run that never changes record "
            f"cannot show the closure holds at every record")
    for dump in data["per_dump"]:
        if not dump["nonzero_expected"]:
            problems.append(f"the file to ask for runoff somewhere on every "
                            f"judged dump (dump {dump['iteration']} asks for "
                            f"none: nothing is summed)")
            break
    if data["per_dump"] and not any(
            d["source_sum"]["volume"] > FLOOR for d in data["per_dump"]):
        problems.append("a non-zero source flux on at least one judged dump")
    for dump in data["per_dump"]:
        if dump["nonfinite"]:
            problems.append(f"every inverted value to be finite (dump "
                            f"{dump['iteration']} has {dump['nonfinite']} "
                            f"that are not)")
            break

    # --- the missing-temperature rule, where the case is about it
    ratios = [d["mflxT_over_mflx"] for d in data["per_dump"]
              if d["mflxT_over_mflx"] is not None]
    result["mflxT_over_mflx"] = ratios
    naive = data["worst"].get("heat_naive")
    result["heat_naive"] = naive
    if case.get("missing"):
        if not ratios or max(ratios) >= 1.0 - 1.0e-6:
            problems.append(
                f"m_T to be measurably below m on a case whose file leaves a "
                f"temperature out (largest ratio "
                f"{max(ratios) if ratios else None}): the "
                f"missing-temperature rule then makes no difference and the "
                f"case measures nothing about it")
        if naive is None or naive[0] <= RTOL * DISCRIMINATION:
            problems.append(
                f"the heat closure with the missing-temperature rule ignored "
                f"to fail by at least {RTOL * DISCRIMINATION:g} (it is "
                f"{naive and naive[0]}): the rule then makes no measurable "
                f"difference to the budget and a pass of the heat closure "
                f"would say nothing about it")
    else:
        # The reconstruction's m_T is its volume flux, bitwise, and the
        # per-cell volume comparison of the same dump shows that
        # reconstruction equal to the model's own EXFroff. So m_T is a
        # measured quantity on these cases and nothing about it is
        # assumed.
        bad = [d["iteration"] for d in data["per_dump"]
               if not d["mflxT_equals_mflx"]]
        if bad:
            problems.append(
                f"m_T to equal the volume flux bitwise on every judged dump, "
                f"which is what makes m_T a measured quantity here (it does "
                f"not on {bad[:4]}): a case without a declared `missing` "
                f"must have a temperature on every source of every record "
                f"it uses")

    # --- every closure the case declares has to be present at all
    #
    # A closure whose right-hand side is exactly 0 on every dump gets
    # ``residual = None`` in :func:`measure`, never reaches ``worst``, and
    # every ``if name in data["worst"]`` test below then silently skips
    # it. So a closure that stopped being measured would be **absent**
    # rather than failed -- on the plain cases and on both controls
    # alike, and the fracsum must-fail would be satisfied by whatever
    # closures were left. Nothing is vacuous today, because
    # :func:`series` hard-codes salt >= 0.1, tracer >= 1.0 and
    # temperature >= 2.0, but a guard that is measured once and not
    # asserted does not stop a later edit from undoing it (LL-009).
    declared = declared_closures(case)
    result["declared_closures"] = list(declared)
    absent = [c for c in declared if c not in data["worst"]]
    if absent:
        problems.append(
            f"every closure this case declares to be measured on at least "
            f"one dump; {absent} produced no residual at all, which means "
            f"its source sum was exactly zero on every dump and the closure "
            f"was silently not measured rather than failed")

    # --- the four closures, and the per-cell criterion
    result["budget_pass"] = True
    result["cell_pass"] = True
    for name in CLOSURES:
        if name in data["worst"] and data["worst"][name][0] > RTOL:
            result["budget_pass"] = False
    for name, (value, iteration) in sorted(data["worst_cell"].items()):
        if value > CELL_RTOL:
            result["cell_pass"] = False
    if any(d["extra"] or d["missing"] for d in data["per_dump"]):
        result["cell_pass"] = False

    if control == "permute":
        # The budget cannot see a permutation: every right-hand side is a
        # sum over the source's fractions, which the permutation leaves at
        # 1. So the budget has to pass and the per-cell comparison has to
        # fail. Both halves are required, which is what makes this a
        # measurement of the issue's premise and not an assertion about it.
        if not result["budget_pass"]:
            problems.append(
                f"the budget to still close on a permuted file (worst "
                f"residual "
                f"{max(data['worst'][k][0] for k in CLOSURES if k in data['worst']):.3e}"
                f" > {RTOL:g}): a permutation of one source's fractions "
                f"across its own cells leaves every sum over targets "
                f"unchanged, so a budget that moves has moved for another "
                f"reason")
        if result["cell_pass"]:
            problems.append(
                "the per-cell comparison to see the permutation (it did "
                "not): the control perturbed nothing the oracle looks at")
        return result
    if control == "fracsum":
        # Per closure, not in aggregate. ``budget_pass`` is the
        # conjunction of "every closure closed", so ``not budget_pass``
        # -- which is what this branch used to test -- is satisfied by
        # **one** closure discriminating, and heat, salt and tracer could
        # all go blind with every enrolled command still passing. Each
        # one that is present has to see the perturbation on its own.
        # Measured today: volume 1.472e-07, heat 1.676e-07, salt
        # 1.637e-07, tracer 1.414e-07, all five orders above RTOL.
        #
        # **What this guards against, and what it cannot.** It is a guard
        # against a later edit, not against a state a correct run can
        # reach, and the structure says why. Scaling one source's
        # fractions by (1+eps) leaves every right-hand side untouched --
        # they are sums over sources and do not involve fractions at all
        # -- while the target-side sum gains eps times that source's
        # contribution. So each leg's residual is eps times **the
        # perturbed source's share of that leg's own total**: not one
        # common factor, because the shares differ per property, but four
        # figures that move together. Measured against that prediction
        # on the lab_sea case: volume 1.4719e-07, heat 1.6975e-07, salt
        # 1.6584e-07, tracer 1.4202e-07, within 1.2x of each other and
        # each matching the residual above. No real run can therefore
        # leave one leg at round-off while the others discriminate; the
        # only way to reach that state is to break a leg, which is what
        # the must-fail demonstration substitutes.
        #
        # The one precondition is that the perturbed source carries a
        # **non-zero value of every property**, or its share of that
        # leg's total is zero and the leg legitimately does not move.
        # :func:`series` guarantees it today (salt >= 0.1, tracer >= 1.0,
        # temperature >= 2.0 on every source and record), and the
        # presence requirement above catches the related case where a
        # whole leg's source sum is zero.
        blind = [c for c in CLOSURES
                 if c in data["worst"] and data["worst"][c][0] <= RTOL]
        result["fracsum_blind"] = blind
        if blind:
            shown = ", ".join(f"{c} {data['worst'][c][0]:.3e}"
                              for c in blind)
            problems.append(
                f"every closure to fail on a file whose fractions sum to "
                f"{1.0 + FRAC_PERTURB!r}; {shown} closed to {RTOL:g} or "
                f"better, so {len(blind)} of the four cannot see "
                f"{FRAC_PERTURB:g} of extra water and is not measuring its "
                f"own closure")
        if not result["cell_pass"]:
            problems.append(
                "the per-cell comparison to still pass on the scaled file "
                "(it did not): the contrast this control exists for needs "
                "the per-cell criterion blind to the perturbation")
        logs = read_file(run_dir, "output.txt") or ""
        result["init_varia_warned"] = bool(re.search(
            r"RNF_INIT_VARIA: the\s+applied volume differs", logs))
        if result["init_varia_warned"]:
            problems.append(
                "RNF_INIT_VARIA not to warn about this perturbation: it is "
                "inside RNF_fracTol, so the existing start-time witness is "
                "meant to be blind to it and the contrast would be weaker "
                "if it were not")
        return result

    for name in CLOSURES:
        if name not in data["worst"]:
            continue
        value, iteration = data["worst"][name]
        if value > RTOL:
            problems.append(f"the {name} closure to hold to {RTOL:g} "
                            f"relative (worst {value:.3e} at dump "
                            f"{iteration})")
    for name, (value, iteration) in sorted(data["worst_cell"].items()):
        if value > CELL_RTOL:
            problems.append(f"the per-cell {name} field to match the file to "
                            f"{CELL_RTOL:g} relative (worst {value:.3e} at "
                            f"dump {iteration})")
    total_extra = sum(d["extra"] for d in data["per_dump"])
    total_missing = sum(d["missing"] for d in data["per_dump"])
    if total_extra or total_missing:
        problems.append(f"no cell to differ in placement (found "
                        f"{total_extra} extra and {total_missing} missing)")
    return result


def check_case(case, nproc, args, control=None):
    """Run and judge one case; return the result dictionary."""
    name = case["name"] + (f"_mpi{nproc}" if nproc else "") \
        + (f"_{control}" if control else "")
    input_name = PREFIX + name
    exp_dir = os.path.join(VERIF, case["experiment"])
    input_dir = os.path.join(exp_dir, input_name)
    build = BUILD + (f"_mpi{nproc}" if nproc else "")
    binary = os.path.join(exp_dir, build, "mitgcmuv")
    result = {"case": case["name"], "processes": nproc, "control": control,
              "problems": []}
    if not os.path.isfile(binary):
        print(f"MISSING {name}: no binary at {binary}")
        print(f"     build it with tests/mitgcm_oracle.sh "
              f"{case['experiment']} {case['input']}"
              + (f" -mpi {nproc}" if nproc else ""))
        return None
    shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir)
    run_dir = None
    try:
        table = read_table(table_path(case))
        result["sources"] = table["nsrc"]
        result["target_entries"] = int(table["target_cell"].size)
        dt, info = write_input(case, input_dir, table, perturb=control)
        result["perturbation"] = info
        # The oracle reads the perturbed fractions for ``fracsum`` -- the
        # point there is that the per-cell criterion is satisfied -- and
        # the committed ones for ``permute``, so that the per-cell
        # criterion sees the move.
        oracle_frac = None
        if control == "fracsum":
            oracle_frac = table["target_fraction"].copy()
            oracle_frac[info["entries"]] = info["to"]
        run_dir, run_exit, timed_out = run_model(
            case["experiment"], input_name, nproc, args.timeout)
        logs = "\n".join(filter(None, (
            read_file(run_dir, n) for n in ("output.txt", "mpirun.log"))))
        result["ended_normally"] = "Execution ended Normally" in logs
        result["run_exit"] = run_exit
        if timed_out:
            result["problems"].append("the run to finish (it timed out)")
            return result
        if not result["ended_normally"] or run_exit != 0:
            result["problems"].append(
                f"the run to end normally (exit {run_exit})")
            result["log_tail"] = "\n".join(logs.splitlines()[-25:])
            return result
        iterations = None
        for key, stream in STREAMS.items():
            if key == "tracer" and not case["tracer"]:
                continue
            found, strays = stream_dumps(run_dir, stream)
            if strays:
                result["problems"].append(
                    f"only dumps of {stream} to match {stream}*: "
                    f"{strays[:5]} are out of scope")
                return result
            if iterations is None:
                iterations = found
            elif found != iterations:
                result["problems"].append(
                    f"the {stream} stream to be dumped at the same "
                    f"iterations as {STREAMS['vol']} ({found[:4]} against "
                    f"{iterations[:4]})")
                return result
        if not iterations:
            result["problems"].append(
                "at least one dump of every stream (found none)")
            return result
        result["measure"] = measure(case, run_dir, table, oracle_frac,
                                    iterations)
        judge(case, run_dir, result, control=control)
        return result
    except ValueError as err:
        result["problems"].append(str(err))
        result["unusable"] = True
        return result
    finally:
        if not args.keep:
            shutil.rmtree(input_dir, ignore_errors=True)
            if run_dir:
                shutil.rmtree(run_dir, ignore_errors=True)


def report(result):
    """Print one case's verdict and its measured figures; return its pass."""
    name = result["case"] + (f"_mpi{result['processes']}"
                             if result["processes"] else "") \
        + (f"_{result['control']}" if result["control"] else "")
    ok = not result["problems"]
    data = result.get("measure") or {}
    parts = []
    for key in CLOSURES:
        if key in (data.get("worst") or {}):
            parts.append(f"{key} {data['worst'][key][0]:.3e}")
    naive = (data.get("worst") or {}).get("heat_naive")
    heat = (data.get("worst") or {}).get("heat")
    # Only where it is a different measurement: on a case with every
    # temperature present the two are the same number, and printing it
    # twice would read as corroboration it is not.
    if naive is not None and (heat is None or naive[0] != heat[0]):
        parts.append(f"(heat with the missing-temperature rule ignored "
                     f"{naive[0]:.3e})")
    cell = ", ".join(
        f"{k} {v[0]:.3e}" for k, v in sorted(
            (data.get("worst_cell") or {}).items()))
    print(f"{'PASS' if ok else 'FAIL'} {name}: "
          f"{len(data.get('dumps') or [])} dump(s), "
          f"{result.get('sources', '?')} source(s), "
          f"{data.get('target_cells', '?')} target cell(s); "
          f"budget {', '.join(parts) or 'none'}")
    if cell:
        print(f"     per cell: {cell}")
    for problem in result["problems"]:
        print(f"     expected {problem}")
    return ok


def main(argv=None):
    """Run the selected cases and controls, and judge the whole selection.

    Builds the run list as the cross product of the selected cases, the
    process counts each case declares (``--mpi`` narrows it, and a count
    a case does not declare simply contributes no run) and the controls
    asked for; an empty list is exit 2 rather than a vacuous success.

    After the runs it makes the Adams-Bashforth comparison of every case
    that names a ``same_as`` partner: the ``STATE_FREE`` residuals must
    be bitwise identical between the two, the heat residual must be
    within :data:`RTOL` in both, and their ``state_signature`` must
    differ so that the insensitivity is not the insensitivity of two
    identical runs. A selection that ran one half of a pair without the
    other fails rather than reporting the half it ran, because the pair
    *is* the measurement (LL-014).

    Exit status: 0 if every run met its own expectations, 1 if one did
    not or none ran, 2 if a binary is missing or a selection does not
    exist.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", action="append", default=None,
                        help="run only this case (may be repeated)")
    parser.add_argument("--mpi", type=int, default=None,
                        help="run only this process count (0: serial)")
    parser.add_argument("--control", choices=("permute", "fracsum"),
                        action="append", default=None,
                        help="run the named control instead of the plain "
                             "case; the verdict is inverted as that "
                             "control asks")
    parser.add_argument("--keep", action="store_true",
                        help="keep the scratch input and run directories")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--json", help="write the measurements here")
    args = parser.parse_args(argv)

    selected = CASES
    if args.case:
        names = {c["name"] for c in CASES}
        unknown = sorted(set(args.case) - names)
        if unknown:
            print(f"no such case: {', '.join(unknown)}")
            return 2
        selected = tuple(c for c in CASES if c["name"] in args.case)
    runs = []
    for case in selected:
        counts = case["mpi"] if args.mpi is None else (
            (args.mpi,) if args.mpi in case["mpi"] else ())
        for nproc in counts:
            for control in (args.control or [None]):
                runs.append((case, nproc, control))
    if not runs:
        print(f"no case runs on {args.mpi} process(es)")
        return 2

    results, missing = [], False
    for case, nproc, control in runs:
        result = check_case(case, nproc, args, control=control)
        if result is None:
            missing = True
            continue
        report(result)
        results.append(result)

    # The AB measurement: a case with ``same_as`` has to produce the same
    # residuals as the case it names, which is what says the instrument is
    # upstream of the Adams-Bashforth extrapolation.
    for case in selected:
        if not case.get("same_as"):
            continue
        mine = [r for r in results if r["case"] == case["name"]
                and not r["control"] and not r["processes"]]
        theirs = [r for r in results if r["case"] == case["same_as"]
                  and not r["control"] and not r["processes"]]
        if not mine:
            continue
        if not theirs:
            # The pair is the measurement. A selection that runs one half
            # of it cannot report the half it ran as a pass, or the
            # Adams-Bashforth claim would be recorded as measured by a run
            # that measured nothing (LL-014).
            mine[0]["problems"].append(
                f"the {case['same_as']} case to have run too: the "
                f"Adams-Bashforth measurement is the comparison of the "
                f"pair, and {case['name']} on its own establishes nothing "
                f"about it")
            continue
        one, two = mine[0].get("measure") or {}, theirs[0].get("measure") or {}
        a, b = one.get("worst") or {}, two.get("worst") or {}
        same = {k: (a[k][0], b[k][0])
                for k in CLOSURES if k in a and k in b}
        comparison = {"against": case["same_as"], "residuals": same,
                      "state_signature": [one.get("state_signature"),
                                          two.get("state_signature")]}
        mine[0]["ab_comparison"] = comparison
        if not same:
            mine[0]["problems"].append(
                f"residuals of both {case['name']} and {case['same_as']} to "
                f"compare against each other (one of them has none)")
            continue
        # The three closures that read no model state have to be bitwise
        # identical; the heat one reads theta and need only close.
        differ = [k for k in STATE_FREE
                  if k in same and same[k][0] != same[k][1]]
        if differ:
            mine[0]["problems"].append(
                f"the {', '.join(differ)} residual(s) of {case['name']} "
                f"(forcing inside Adams-Bashforth) to be bitwise identical "
                f"to those of {case['same_as']}: those closures read no "
                f"model state, so the time-stepping scheme cannot reach "
                f"them. Measured {({k: same[k] for k in differ})}")
        if "heat" in same and max(same["heat"]) > RTOL:
            mine[0]["problems"].append(
                f"the heat closure to hold to {RTOL:g} in both halves of "
                f"the Adams-Bashforth pair (measured {same['heat']})")
        # Without a state difference the pair is two identical runs and
        # the insensitivity it reports is vacuous (LL-014).
        if comparison["state_signature"][0] == comparison["state_signature"][1]:
            mine[0]["problems"].append(
                f"the two halves of the Adams-Bashforth pair to reach "
                f"different model states (their surface temperature sums "
                f"are identical): the tracForcingOutAB setting then had no "
                f"effect and the comparison measures nothing")
        print(f"AB   {case['name']} against {case['same_as']}: "
              + (f"{', '.join(STATE_FREE)} identical"
                 if not differ else f"DIFFER on {differ}")
              + "; " + ", ".join(f"{k} {x:.3e}/{y:.3e}" for k, (x, y)
                                 in same.items())
              + "; states "
              + ("differ" if comparison["state_signature"][0]
                 != comparison["state_signature"][1] else "IDENTICAL"))

    passing = sum(1 for r in results if not r["problems"])
    print(f"{len(results)} run(s), {passing} passing")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"runs": results, "rtol": RTOL,
                       "cell_rtol": CELL_RTOL,
                       "frac_perturb": FRAC_PERTURB}, fh, indent=1,
                      default=str)
    if missing:
        return 2
    if not results or any(r["problems"] for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
