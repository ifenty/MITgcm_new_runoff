#!/usr/bin/env python3
"""Budget-closure oracle of the runoff volume, heat, salt and tracers (RUNOFF-016, -008).

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
over targets. (When this check was written the tracer term had no
numerical oracle at all; ``tendency_term_check`` now carries analytic
tracer rows too, RUNOFF-008.)

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
tracer k    ``(mC_k)(c) * rA(c)``, from ``RNFtrNN``  ``rhoConstFresh * sum_s flux_s*C_{s,k}``
ptracer n   ``(mC)(c) * rA(c)``, from ``ForcTrNN``  ``rhoConstFresh * sum_s flux_s*C_{s,name(n)}``
==========  ===================================  =========================

``tracer k`` is runoff tracer k, the k-th ``runoff_ptracer_*`` variable
of the file; ``ptracer n`` is passive tracer n of ``data.ptracers``,
closed against the series of the variable *named* like it. The two are
not the same closure, and the difference is the mapping ``RNF_trPtr``:
see "Several tracers" below.

A cell with no runoff contributes exactly 0 to every closure, so the wider sum
costs nothing and cannot divide by a zero thickness: ``EXFroff`` is 0
there and the inverted tendency is 0 both because the package writes
nothing there and because the factor it is multiplied by vanishes wherever
``hFacC`` does.

The right-hand sides are the file's own source series at the record the
model reported for that step, so the closure is a statement about where
the water and its properties went, not about the arithmetic of one cell.
``docs/model_contract.md`` states it under Invariants.

How the quantities are observed, with no model change
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
* tracer: ``PTRACERS_EvPrRn(n) = 0`` makes ``C_ref`` exactly 0
  (``rnf_tendency_apply.F:453-454``), asserted the same way for every
  fed ptracer. With ``PTRACERS_ref(n) = 0`` as well, and these runs in
  branch U (``convertFW2Salt`` = 35, asserted not -1), the model's own
  freshwater term for the tracer, ``EmPmR*(PTRACERS_ref -
  PTRACERS_EvPrRn)``, is exactly 0 too
  (``pkg/longstep/longstep_forcing_surf.F:126-145``: lab_sea compiles
  pkg/longstep, which sets ``surfaceForcingPTr`` in place of
  ``PTRACERS_FORCING_SURF``), so the ptracer's whole forcing tendency
  ``ForcTrNN`` is the package term and inverts with the same factor.
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
``tracForcingOutAB = 1`` (``tendency_term_check.judge``); the AB
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
  (``tendency_term_check.write_sparse``, and ``expected`` and
  ``expected_tracer`` there) rather than by the file's
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

The tracer closures run only on ``lab_sea``. ``cs32`` does not compile
``pkg/ptracers`` (``verification/global_ocean.cs32x15/code/packages.conf``)
and giving it the package would change the binary every other committed
cs32 oracle is measured through, so the tracer closures are **not
measured on the cube sphere**.

Several tracers (RUNOFF-008)
----------------------------

``lab_sea``'s ordinary build has ``PTRACERS_num = 1``, so the one-tracer
cases carry exactly one passive tracer. The mapping of several runoff
tracers onto several ptracers is measured on a second binary,
``build_esx_ptr2``: lab_sea's ``code/`` plus a ``PTRACERS_SIZE.h`` with
``PTRACERS_num = 2``, written by :func:`write_ptr2_code` and compiled by
``--build`` under ``tendency_term_check.build_if_stale``'s staleness rule
(single process only; there is no MPI variant of it). On it:

* ``lab_sea_ptr2`` feeds ptracers ``rnfa``, ``rnfb`` from a file whose
  variables are in the **opposite** order, so ``RNF_trPtr`` = (2, 1).
  The ``RNFtrNN`` closures are **blind to that mapping**: the package
  names the diagnostic after the runoff tracer and fills it from
  ``RNF_apXTr(...,iRnf)`` whichever ptracer it is added to
  (``rnf_tendency_apply.F:480-500``). The ``ForcTrNN`` closures are what
  see it, since that is what each ptracer actually received. Measured:
  the four tracer closures close at 1.962e-16 to 2.170e-16, runoff tracer
  1 matching ptracer 2 and runoff tracer 2 matching ptracer 1.
* ``--control swap`` exchanges the two variables' **names** and keeps
  their data in place, which is a swapped ``RNF_trPtr`` made by the
  input. It must leave the ``RNFtrNN`` closures at round-off and fail
  every ``ForcTrNN`` closure: measured 5.002e-01 and 3.334e-01. A mutant
  binary with ``RNF_trPtr(n) = n`` (an identity mapping, which on this
  file *is* a swap) gives the same two figures and fails the plain case.
* ``lab_sea_unfed`` has a file that feeds only ``rnfa``. The unfed
  ``rnfb`` must get nothing, judged by :func:`judge_unfed` on two legs:
  its ``ForcTrNN`` exactly 0.0 everywhere, and its state bitwise equal
  to a reference run with no ``runoff_ptracer_*`` variable at all.
  ``--control feed_zero`` adds a zero-valued ``rnfb`` variable, so the
  package applies ``-m*C_ref`` to it (``PTRACERS_ref`` = 0.5 there, and
  ``PTRACERS_EvPrRn`` unset): both legs must see it, and do (``ForcTr``
  non-zero on all 6 dumps, 676 state values differing). The two legs
  are **not** equally strong: a mutant that applies the term to *every*
  ptracer no variable feeds is caught by the forcing leg (``ForcTr02``
  up to 3.422e-08) and **missed** by the state leg, because the
  reference run uses the same binary and, having no tracer variables at
  all, receives the same wrong term. The state leg is decisive only for
  a defect that depends on the file's variables; the forcing leg is the
  one that holds either way.

The tracer series are non-degenerate (:func:`series`): every
(record, source, tracer) value is distinct and the two tracers are not
proportional, asserted when the series is built. The series this check
had before RUNOFF-008 gave sources 0 (``newfound``) and 3 (``baffin``)
the same tracer value at every record (12 distinct values of 20), so the
tracer leg could not tell those two sources apart. Temperature and
salinity keep 7 and 5 distinct per-source shapes over cs32's 1189
sources. The sums are correct either way, because they are sums; but
no reader should take them for per-source resolution on cs32.

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
cell, a cavity column under pkg/shelfice, or an r-star case is where it
would first actually be exercised.

**Where the must-fail controls run.** All four are enrolled, but not in
the same suite: ``focused`` carries only the ``fracsum`` control, so the
suite that runs on every candidate has **no must-fail for the per-cell
leg** -- the one that proves the per-cell criterion can see a
perturbation is the ``permute`` control, and it is in ``scientific``
only (review B) -- and none for the tracer mapping: the two-tracer
cases and their ``swap`` and ``feed_zero`` controls are in
``scientific``, each with ``--build``.

Usage
=====

    python3 tests/rnf/budget_check.py [--case NAME ...] [--mpi N] [--build]
                                      [--control permute|fracsum|swap|feed_zero]
                                      [--keep] [--json PATH] [--timeout S]

Exit status: 0 if every selected case passes, 1 if one fails or none ran,
2 if a binary is missing or could not be built, or a selection does not
exist.
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
from tendency_term_check import (build_if_stale, param,  # noqa: E402
                                 param_all, read_mds, report_build,
                                 write_mods_code)

#: The scratch input directories this check writes, one per run.
PREFIX = "input.rnfbudget_"
#: Binary of the ordinary build; the MPI ones are this plus ``_mpiN``.
BUILD = "build_esx"
#: The lab_sea build with ``PTRACERS_num = 2`` (RUNOFF-008), compiled by
#: ``--build`` from the mods directory :func:`write_ptr2_code` writes.
#: Single process only: no ``_mpiN`` variant of it exists.
PTR2_BUILD = "build_esx_ptr2"
PTR2_CODE = "code_rnfterm_ptr2"
#: Name of the sparse file each case writes into its scratch input.
SPARSE_FILE = "runoff_budget.nc"
#: Diagnostic stream names of the three closures every case has, one
#: file each. The tracer streams depend on the case: see
#: :func:`case_streams`.
STREAMS = {"vol": "rnfBudV", "heat": "rnfBudT", "salt": "rnfBudS"}
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
#: Name of the passive tracer the one-tracer lab_sea cases give the
#: runoff, and the ``runoff_ptracer_<NAME>`` variable that feeds it.
TRACER_NAME = "rnfbud"
#: ``PTRACERS_names`` of the two-tracer cases (RUNOFF-008), in
#: ``data.ptracers`` order. Their file writes the variables in the
#: **opposite** order (``PTR2_FILE``), so that runoff tracer 1 feeds
#: ptracer 2 and the reverse: an identity ``RNF_trPtr`` would then put
#: each tracer's water into the other ptracer, which is what the
#: per-ptracer closures and the ``swap`` control are there to see.
PTR2_NAMES = ("rnfa", "rnfb")
PTR2_FILE = ("rnfb", "rnfa")
#: ``PTRACERS_ref`` of the unfed ptracer of ``lab_sea_unfed``. Non-zero
#: on purpose: with ``PTRACERS_EvPrRn`` unset the reference the package
#: would use for it in branch U is ``PTRACERS_ref``, so a term wrongly
#: applied to it with no source tracer, ``-m*C_ref``, is non-zero and
#: visible (the ``feed_zero`` control measures exactly that).
UNFED_REF = 0.5
#: The value the model prints for an unset real parameter
#: (``eesupp/inc/EEPARAMS.h:81``), which is how an unset
#: ``PTRACERS_EvPrRn`` reads back.
UNSET_RL = 1.234567e5
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
#   RNFtrNN  :: the same for runoff tracer NN, i.e. the NN-th
#               runoff_ptracer_* variable of the file (lab_sea only)
#   ForcTrNN :: the forcing tendency of ptracer NN (PTRACERS_INTEGRATE's
#               gTrForc), i.e. what that ptracer actually received
# The tendency streams are level 1 only: that is the surface level
# of every column of these set-ups (z coordinates, no pkg/shelfice), and
# the only level at which the terms are non-zero.
 &DIAGNOSTICS_LIST
  diag_mnc = .FALSE.,
{streams} &

 &DIAG_STATIS_PARMS
 &
"""

def data_ptracers(case, iter0, nr):
    """Return the ``data.ptracers`` of a tracer case.

    One block per name of ``case["ptracers"]``, in that order, which is
    the ``PTRACERS_names`` order and so the ptracer numbering.

    * ``PTRACERS_EvPrRn(n) = 0`` and ``PTRACERS_ref(:,n) = 0`` for every
      **fed** ptracer. The first makes ``C_ref`` exactly 0 in
      ``RNF_TENDENCY_APPLY_PTR`` (``rnf_tendency_apply.F:453-454``), so
      the term is ``(mC)*mass2rUnit*D`` and can be inverted without a
      reference value; the second makes the model's own freshwater term
      for the tracer vanish too, since these runs are in branch U
      (``convertFW2Salt`` = 35, the default lab_sea keeps) where that
      term is ``EmPmR*(PTRACERS_ref - PTRACERS_EvPrRn)*mass2rUnit``
      (``pkg/longstep/longstep_forcing_surf.F:126-145``, the routine that
      sets ``surfaceForcingPTr`` under pkg/longstep). So the ptracer's own
      forcing tendency ``ForcTrNN`` holds the package term and nothing
      else, which is what lets it be closed per ptracer.
    * The unfed ptracer of ``case["unfed_ref"]`` gets that
      ``PTRACERS_ref`` and **no** ``PTRACERS_EvPrRn``: unset, the model
      adds nothing for it in any arm, and a package term wrongly applied
      to it would subtract ``m*PTRACERS_ref`` and be seen.
    * ``PTRACERS_Iter0`` is ``nIter0``, so each tracer is initialized from
      ``PTRACERS_ref`` rather than from a pickup this scratch run has
      none of. No GM/Redi, no KPP and no diffusion on the tracers: they
      would not change the terms this check reads, which are filled where
      they are computed, and are off so that the run cannot fail for a
      reason that has nothing to do with runoff.
    """
    names = case["ptracers"]
    lines = ["# Written by tests/rnf/budget_check.py.",
             " &PTRACERS_PARM01",
             f" PTRACERS_numInUse = {len(names)},",
             f" PTRACERS_Iter0 = {iter0},"]
    for n, name in enumerate(names, start=1):
        unfed = name not in case["file_tracers"]
        ref = case.get("unfed_ref", 0.0) if unfed else 0.0
        lines += [f" PTRACERS_names({n}) = '{name}',",
                  f" PTRACERS_long_names({n}) = 'runoff budget tracer "
                  f"{name}',",
                  f" PTRACERS_units({n}) = '1',",
                  f" PTRACERS_advScheme({n}) = 30,",
                  f" PTRACERS_diffKh({n}) = 0.,",
                  f" PTRACERS_diffKr({n}) = 0.,",
                  f" PTRACERS_ref(:,{n}) = {nr}*{ref!r},",
                  f" PTRACERS_useGMRedi({n}) = .FALSE.,",
                  f" PTRACERS_useKPP({n}) = .FALSE.,"]
        if not unfed:
            lines.append(f" PTRACERS_EvPrRn({n}) = 0.,")
    lines.append(" &")
    return "\n".join(lines) + "\n"


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
#: ``ptracers`` are the ``PTRACERS_names`` of the run, in order (empty:
#: pkg/ptracers off), and ``file_tracers`` the ``runoff_ptracer_<NAME>``
#: variables of its file, in file order, which is the runoff-tracer
#: numbering of ``RNFtrNN``. A ptracer the file does not feed is
#: *unfed*: it gets no closure and is judged by :func:`judge_unfed`
#: against a reference run whose file has no tracer variable at all.
#: ``build`` names a non-default binary (``PTR2_BUILD``).
#: ``minimal_pkgs`` switches off pkg/seaice, pkg/thsice, pkg/kpp and
#: pkg/gmredi; see :func:`write_input`.
#: ``steps`` is the number of time steps; ``mpi`` the process counts.
CASES = (
    {"name": "lab_sea", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "ptracers": (TRACER_NAME,), "file_tracers": (TRACER_NAME,),
     "mpi": (0, 2), "min_records": 2,
     "perturb_source": 3},
    # The cube sphere: 1189 sources over six facets and, on 4 processes,
    # over four processes. One constant record (no pkg/cal there).
    {"name": "cs32", "experiment": "global_ocean.cs32x15",
     "input": "input.rnof_sp_icedyn", "data_from": "input.icedyn",
     "table_from": ("global_ocean.cs32x15", "input.rnof_sp_icedyn",
                    "runoff_sparse_const.nc"),
     "records": None, "period": None, "steps": 3,
     "ptracers": (), "file_tracers": (), "mpi": (0, 4), "min_records": 1,
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
     "ptracers": (TRACER_NAME,), "file_tracers": (TRACER_NAME,),
     "mpi": (0, 2), "min_records": 2,
     "missing": {0: "all", 1: (3,)}, "perturb_source": 3},
    # The Adams-Bashforth pair. Two runs of the lab_sea case that differ
    # in exactly one namelist value, tracForcingOutAB, and in nothing
    # else: the residuals of every closure that reads no state (all but
    # heat) have to come out identical, which is the
    # measurement that this instrument is upstream of the extrapolation.
    # Both carry ``minimal_pkgs`` because pkg/seaice refuses
    # tracForcingOutAB other than 1 outright, so the comparison could not
    # be made with it on; having it off in *both* is what keeps the pair
    # a one-variable comparison.
    {"name": "ab_out", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "ptracers": (TRACER_NAME,), "file_tracers": (TRACER_NAME,),
     "mpi": (0,), "min_records": 2,
     "trac_forcing_out_ab": 1, "minimal_pkgs": True,
     "perturb_source": 3},
    {"name": "ab_in", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "ptracers": (TRACER_NAME,), "file_tracers": (TRACER_NAME,),
     "mpi": (0,), "min_records": 2,
     "trac_forcing_out_ab": 0, "minimal_pkgs": True, "same_as": "ab_out",
     "perturb_source": 3},
    # Two runoff tracers feeding two ptracers (RUNOFF-008), on the
    # PTRACERS_num = 2 build. The file carries the variables in the
    # opposite order to PTRACERS_names, so RNF_trPtr is (2, 1): an
    # identity mapping or a swap would put each tracer's water into the
    # other ptracer, which the per-ptracer closures (ForcTrNN against the
    # series of the variable *named* like that ptracer) cannot miss,
    # because :func:`series` gives the two tracers different,
    # non-proportional values at every (record, source).
    {"name": "lab_sea_ptr2", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "ptracers": PTR2_NAMES, "file_tracers": PTR2_FILE,
     "build": PTR2_BUILD, "mpi": (0,), "min_records": 2,
     "perturb_source": 3},
    # A ptracer the file does not feed adds nothing (RUNOFF-008): the
    # same build and the same two ptracers, with a file that carries
    # only runoff_ptracer_rnfa. rnfb must get no term at all; see
    # :func:`judge_unfed` for the oracle and the feed_zero control.
    {"name": "lab_sea_unfed", "experiment": "lab_sea",
     "input": "input.rnof_sp_const", "data_from": "input.rnof_sp_const",
     "table_from": ("lab_sea", "input.rnof_const", "runoff_sparse.nc"),
     "records": 5, "period": 2, "steps": 6,
     "ptracers": PTR2_NAMES, "file_tracers": ("rnfa",),
     "unfed_ref": UNFED_REF,
     "build": PTR2_BUILD, "mpi": (0,), "min_records": 2,
     "perturb_source": 3},
)

#: The closures every case has. The tracer closures come on top, per
#: case (:func:`closures_of`). ``heat_naive`` is measured alongside them
#: but is not one of them: it is the heat closure with the
#: missing-temperature rule deliberately ignored, and it is required to
#: *fail* on a case that declares ``missing``.
CLOSURES = ("volume", "heat", "salt")
#: The one closure that reads model state, ``theta`` for ``T_ref``. Every
#: other closure reads none, so cannot be moved by the time-stepping
#: scheme, and the Adams-Bashforth pair requires those to come out
#: bitwise identical.
STATE_READING = ("heat",)


def write_ptr2_code():
    """Write the mods directory of the ``PTRACERS_num = 2`` lab_sea build.

    ``lab_sea/code`` has no ``PTRACERS_SIZE.h``, so lab_sea compiles the
    package default, ``PTRACERS_num = 1``
    (``pkg/ptracers/PTRACERS_SIZE.h:16``), which has room for exactly one
    passive tracer. This writes ``lab_sea/code`` plus a copy of that
    header with the one value changed to 2, through
    ``tests/rnf/tendency_term_check.write_mods_code``; nothing in
    ``lab_sea/code`` itself is edited. Returns the directory.
    """
    with open(os.path.join(ROOT, "MITgcm", "pkg", "ptracers",
                           "PTRACERS_SIZE.h")) as fh:
        text = fh.read()
    new, count = re.subn(r"(?m)^(\s+PARAMETER\s*\(\s*PTRACERS_num\s*=\s*)1"
                         r"(\s*\))", r"\g<1>2\g<2>", text)
    if count != 1:
        raise ValueError(f"pkg/ptracers/PTRACERS_SIZE.h has {count} "
                         f"'PARAMETER(PTRACERS_num = 1 )' lines, expected 1")
    return write_mods_code(PTR2_CODE, {"PTRACERS_SIZE.h": new})


def tracer_closures(case):
    """Return the tracer closures of ``case``, as ``(name, field, stream, series)``.

    Two kinds, which see different things:

    * ``tracer``, ``tracer2``, ...: runoff tracer k, i.e. the k-th
      ``runoff_ptracer_*`` variable of the file, read from ``RNFtrNN``.
      ``RNF_TENDENCY_APPLY_PTR`` names that diagnostic after the runoff
      tracer, not after the ptracer (``rnf_tendency_apply.F:499``), and
      fills it from ``RNF_apXTr(...,iRnf)`` whichever ptracer it is
      applied to, so this closure is **blind to the mapping**
      ``RNF_trPtr``: it measures what the package loaded.
    * ``ptracer``, ``ptracer2``, ...: ptracer n, read from ``ForcTrNN``,
      the forcing tendency ``PTRACERS_INTEGRATE`` actually adds to that
      ptracer (``pkg/ptracers/ptracers_integrate.F:301-310``), against
      the series of the file variable **named** like it. With the
      settings of :func:`data_ptracers` the model adds nothing else to
      it, so this is the closure that sees which ptracer the water went
      into. Only fed ptracers have one.

    ``series`` is the name of the file variable whose source series is
    the right-hand side, as the committed (unperturbed) file has it.
    """
    out = []
    for k, name in enumerate(case["file_tracers"], start=1):
        out.append(("tracer" if k == 1 else f"tracer{k}", f"RNFtr{k:02d}",
                    f"rnfBudC{k:02d}", name))
    for n, name in enumerate(case["ptracers"], start=1):
        if name in case["file_tracers"]:
            out.append(("ptracer" if n == 1 else f"ptracer{n}",
                        f"ForcTr{n:02d}",
                        f"rnfBudP{n:02d}", name))
    return out


def unfed_ptracers(case):
    """Return ``(n, name, stream)`` of every ptracer the file does not feed."""
    return [(n, name, f"rnfBudU{n:02d}")
            for n, name in enumerate(case["ptracers"], start=1)
            if name not in case["file_tracers"]]


def closures_of(case):
    """Return every closure ``case`` measures: the three plus its tracers."""
    return CLOSURES + tuple(c[0] for c in tracer_closures(case))


def declared_closures(case):
    """Return the closures ``case`` is supposed to measure.

    :func:`closures_of`. :func:`judge` requires every closure this
    returns to be **present** in the measurement, so that one which
    stopped being measured fails instead of disappearing.
    """
    return closures_of(case)


def case_streams(case):
    """Return ``{key: stream}`` of every diagnostic stream ``case`` dumps.

    The tracer streams carry a two-digit number (``rnfBudC01``,
    ``rnfBudP02``, ``rnfBudU02``) so that no stream name is a prefix of
    another: :func:`stream_dumps` globs ``<stream>*`` and refuses any file
    that is not one of that stream's dumps.
    """
    out = dict(STREAMS)
    for name, _field, stream, _series in tracer_closures(case):
        out[name] = stream
    for n, _name, stream in unfed_ptracers(case):
        out[f"unfed{n}"] = stream
    return out


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

    The temperature, the salinity and the tracers vary with both the
    source and the record, and none of them is a multiple of the flux, so
    a flux-weighted sum cannot be confused with an unweighted one. The
    temperature of a source listed in ``missing`` is stored as the fill
    value in the records named there.

    **The tracer series are non-degenerate (RUNOFF-008).** Every
    (record, source, tracer) value is distinct, and no two tracers are
    proportional, which is asserted here rather than left to the
    formula: an earlier ``1.0 + 0.2r + 0.1(k mod 3)`` gave lab_sea's
    sources 0 and 3 the same value at every record, so the tracer leg
    could not tell those two sources apart, and a single shared shape
    would let a swap of two tracers pass a closure that is a sum. A
    tracer's series depends on its position in ``case["ptracers"]``
    (``PTRACERS_names`` order), so a name keeps its series whatever
    position the file gives its variable.

    Returns a dict of float64 arrays -- ``trc`` is a dict of them, by
    tracer name, over ``case["file_tracers"]`` -- plus ``tvld``, the
    per-record validity flag of the temperature, which is what
    ``RNF_LOAD_REC`` stores as ``RNF_bufTvld``.
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
    rec = np.arange(nrec, dtype=np.float64)[:, None]
    out["trc"] = {}
    for name in case["file_tracers"]:
        j = float(case["ptracers"].index(name))
        out["trc"][name] = ((1.0 + 0.5 * j) + (0.2 + 0.05 * j) * rec
                            + (0.1 + 0.07 * j) * k[None, :]
                            + 0.003 * (k * k)[None, :])
    if out["trc"]:
        every = np.concatenate([v.ravel() for v in out["trc"].values()])
        if np.unique(every).size != every.size:
            raise ValueError(f"the tracer series hold {every.size} values of "
                             f"which only {np.unique(every).size} are "
                             f"distinct: some (record, source, tracer) "
                             f"cannot be told apart")
        names = list(out["trc"])
        for a in range(len(names)):
            for b in range(a + 1, len(names)):
                ratio = out["trc"][names[a]] / out["trc"][names[b]]
                if float(np.ptp(ratio)) < 1.0e-3:
                    raise ValueError(f"tracers {names[a]} and {names[b]} "
                                     f"are proportional: a swap of the two "
                                     f"would scale a closure, not break it")
    tvld = np.ones((nrec, nsrc), dtype=np.float64)
    for src, where in (case.get("missing") or {}).items():
        if where == "all":
            tvld[:, src] = 0.0
        else:
            for record in where:
                tvld[record - 1, src] = 0.0
    out["tvld"] = tvld
    return out


def write_sparse(path, table, case, dt, perturb=None, no_tracers=False):
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
    inside ``RNF_fracTol``), or one of the two tracer controls of
    RUNOFF-008, which leave the table alone:

    * ``"swap"`` exchanges the **names** of the two tracer variables and
      keeps their data where it was, so runoff tracer k still carries
      the series the oracle expects for position k while each series now
      reaches the other ptracer -- exactly what a swapped ``RNF_trPtr``
      would do, made by the input;
    * ``"feed_zero"`` adds a variable for every unfed ptracer, holding
      0.0 at every record and source: the package then applies to that
      ptracer the term it would apply if it fed a tracer the file does
      not carry, ``-m*C_ref``.

    ``no_tracers`` writes no ``runoff_ptracer_*`` variable at all, which
    is the reference run of :func:`judge_unfed`. Returns what was
    perturbed, for the report.
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
        elif perturb not in ("swap", "feed_zero"):
            raise ValueError(f"unknown perturbation {perturb!r}")
        done = {"perturb": perturb, "source": table["ids"][src],
                "entries": rows.tolist(),
                "from": table["target_fraction"][rows].tolist(),
                "to": frac[rows].tolist(),
                "sum_from": float(table["target_fraction"][rows].sum()),
                "sum_to": float(frac[rows].sum())}
    # The tracer variables: (name written, series it carries).
    written = [(name, value["trc"][name]) for name in case["file_tracers"]]
    if perturb == "swap":
        if len(written) != 2:
            raise ValueError(f"the swap control needs exactly two tracer "
                             f"variables; {case['name']} has {len(written)}")
        written = [(written[1][0], written[0][1]),
                   (written[0][0], written[1][1])]
        done["tracers"] = [w[0] for w in written]
    if perturb == "feed_zero":
        unfed = [name for _, name, _ in unfed_ptracers(case)]
        if not unfed:
            raise ValueError(f"the feed_zero control needs an unfed "
                             f"ptracer; {case['name']} has none")
        written += [(name, np.zeros((nrec, nsrc))) for name in unfed]
        done["tracers"] = [w[0] for w in written]
    if no_tracers:
        written = []
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
        for name, data in written:
            out = ds.createVariable(f"runoff_ptracer_{name}", "f8",
                                    ("time", "source"))
            out.units = "1"
            out[:] = data
    return done


def source_series(table, case, records):
    """Return the source series of one step, as ``RNF_LOAD_AT`` builds them.

    ``records`` is ``(rec0, year0, rec1, year1, fac)`` as
    ``RNF_FIELDS_LOAD`` reported it for the step. The flux, the salinity
    and every tracer (``trc`` is a dict by tracer name, as in
    :func:`series`) are combined the way ``rnf_fields_load.F:324-387``
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
           "temp": temp, "tvld": tvld, "trc": {}}
    for name, data in value["trc"].items():
        if not need1:
            out["trc"][name] = data[rec0 - 1].copy()
        elif not need0:
            out["trc"][name] = data[rec1 - 1].copy()
        else:
            out["trc"][name] = fac * data[rec0 - 1] \
                + (1.0 - fac) * data[rec1 - 1]
    return out


def dense_fields(table, source, rac, ncells, frac=None):
    """Return the dense per-cell fields ``RNF_LOAD_AT`` builds, in table order.

    ``sum over the tile's target entries`` of

        wVol  = flux_s * frac_{s,c} / rA(c)
        vflx += wVol                                 (its own expression)
        mflxT += wVol * tvld_s
        mXT   += wVol * tvld_s * T_s
        mXS   += wVol * S_s
        mXTr  += wVol * C_s                          (per tracer)

    then one pass multiplying the property sums and the mass flux by
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
           for k in ("vflx", "mflxT", "mXT", "mXS")}
    out["mXTr"] = {name: np.zeros(ncells, dtype=np.float64)
                   for name in source["trc"]}
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
        for name, trc in source["trc"].items():
            out["mXTr"][name][c] += w * trc[s]
    return out


def diagnostics_text(case, dt):
    """Return the ``data.diagnostics`` of a case: one stream per quantity."""
    wanted = [("EXFroff ", STREAMS["vol"], None),
              ("RNFgT   ", STREAMS["heat"], 1),
              ("RNFgS   ", STREAMS["salt"], 1)]
    for _name, field, stream, _series in tracer_closures(case):
        wanted.append((f"{field:8s}", stream, 1))
    for n, _name, stream in unfed_ptracers(case):
        wanted.append((f"ForcTr{n:02d}", stream, 1))
    lines = []
    for n, (field, stream, level) in enumerate(wanted, start=1):
        lines.append(f"  fields(1,{n}) = '{field}',")
        lines.append(f"  fileName({n}) = '{stream}',")
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


def write_input(case, input_dir, table, perturb=None, no_tracers=False):
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
      ``salt_EvPrRn = 0`` and ``PTRACERS_EvPrRn(n) = 0`` already
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
    if case["ptracers"]:
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

    if case["ptracers"]:
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
            fh.write(data_ptracers(case, iter0, nr))
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
                     "# skipped and RNFtrNN is filled on every one.\n"
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
                        dt, perturb=perturb, no_tracers=no_tracers)
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


def run_model(experiment, input_name, nproc, timeout, build=BUILD):
    """Run one scratch input; return ``(run dir, exit status, timed out)``.

    ``build`` is the serial build name; ``_mpiN`` is appended here for an
    ``nproc``-process run, so callers pass the case's base build.
    """
    output_name = "output_esx_" + input_name
    mpi_args = []
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
    """Measure every closure of the case on every judged dump of one run.

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
    if case["ptracers"]:
        # One value per ptracer, in PTRACERS_names order. An unset
        # PTRACERS_EvPrRn is printed as UNSET_RL.
        for name in ("PTRACERS_EvPrRn", "PTRACERS_ref"):
            out["params"][name] = param_all(text, name)
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
    tracers = tracer_closures(case)
    streams = case_streams(case)
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
        for key_q, name in (("mXT", "heat"), ("mXS", "salt")):
            raw, sizes = read_mds(run_dir, f"{STREAMS[name]}.{iteration}")
            got[key_q] = level1(raw, sizes, ncells) * inverse
        # Each tracer closure inverts its own stream with the same factor:
        # C_ref is 0 and the model adds nothing (data_ptracers), so the
        # stream is (mC)*mass2rUnit*D whether it is RNFtrNN or ForcTrNN.
        for name, _field, stream, _series in tracers:
            raw, sizes = read_mds(run_dir, f"{stream}.{iteration}")
            got[name] = level1(raw, sizes, ncells) * inverse
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
        for key_q in ("mflxT", "mXT", "mXS"):
            want_scaled[key_q] = rho_fresh * want[key_q]
        for name, _field, _stream, series_name in tracers:
            want_scaled[name] = rho_fresh * want["mXTr"][series_name]

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
        # A cell with no runoff contributes exactly 0 to every closure: EXFroff
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
        for name, _field, _stream, series_name in tracers:
            rhs[name] = rho_fresh * math.fsum(
                (flux * source["trc"][series_name]).tolist())
            lhs[name] = math.fsum((got[name] * rac).tolist())
        entry["source_sum"] = rhs
        entry["target_sum"] = lhs
        entry["residual"] = {
            k: (abs(lhs[k] - rhs[k]) / abs(rhs[k]) if rhs[k] else None)
            for k in rhs}
        # --- the per-cell criterion, on the same dump
        cell = {}
        for key_q, name in ((("vflx", "volume"), ("mXT", "heat"),
                             ("mXS", "salt"))
                            + tuple((c[0], c[0]) for c in tracers)):
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
        # What every unfed ptracer received on this dump: its whole
        # forcing tendency, which must be exactly zero (judge_unfed).
        entry["unfed"] = {}
        for n, name, _stream in unfed_ptracers(case):
            raw, sizes = read_mds(run_dir,
                                  f"{streams[f'unfed{n}']}.{iteration}")
            field = level1(raw, sizes, ncells)
            entry["unfed"][name] = {
                "nonzero": int(np.count_nonzero(field)),
                "max_abs": float(np.abs(field).max())}
        out["per_dump"].append(entry)

    out["worst"] = {}
    for name in closures_of(case) + ("heat_naive",):
        values = [(d["residual"][name], d["iteration"])
                  for d in out["per_dump"] if name in d["residual"]
                  and d["residual"][name] is not None]
        if values:
            out["worst"][name] = max(values)
    out["worst_cell"] = {}
    for name in closures_of(case):
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
    for n, name in enumerate(case["ptracers"], start=1):
        ev = params["PTRACERS_EvPrRn"][n - 1]
        ref = params["PTRACERS_ref"][n - 1]
        if name in case["file_tracers"]:
            if ev != 0.0 or ref != 0.0:
                problems.append(
                    f"PTRACERS_EvPrRn({n}) = {ev} and PTRACERS_ref({n}) = "
                    f"{ref}, not both 0: C_ref is then not 0 or the model "
                    f"adds a freshwater term of its own, and neither RNFtrNN "
                    f"nor ForcTr{n:02d} is (mC)*mass2rUnit*D")
        elif ev != UNSET_RL or ref != case.get("unfed_ref", 0.0):
            problems.append(
                f"the unfed ptracer {n} ({name}) to have PTRACERS_EvPrRn "
                f"unset and PTRACERS_ref = {case.get('unfed_ref', 0.0)} "
                f"(found {ev} and {ref}): otherwise a term wrongly applied "
                f"to it need not be visible")
    if case["ptracers"] and params["convertFW2Salt"] == -1.0:
        problems.append(
            "convertFW2Salt = -1 (branch L): the model's own tracer term is "
            "then EmPmR*(C_local - PTRACERS_EvPrRn), not zero, and ForcTrNN "
            "is no longer the package term alone")
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
    # :func:`series` hard-codes salt >= 0.1, tracers >= 1.0 and
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

    # --- the closures, and the per-cell criterion
    result["budget_pass"] = True
    result["cell_pass"] = True
    closures = closures_of(case)
    for name in closures:
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
                f"{max(data['worst'][k][0] for k in closures if k in data['worst']):.3e}"
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
        # 1.637e-07, tracer and ptracer 1.661e-07, all five orders above
        # RTOL.
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
        # on the lab_sea case (eps times the source's share at each
        # judged dump's own interpolated series, worst dump): volume
        # 1.4719e-07, heat 1.6761e-07, salt 1.6370e-07, tracer 1.6607e-07,
        # within 1.2x of each other and each equal to the residual above
        # to the four digits shown. No real run can therefore
        # leave one leg at round-off while the others discriminate; the
        # only way to reach that state is to break a leg, which is what
        # the must-fail demonstration substitutes.
        #
        # The one precondition is that the perturbed source carries a
        # **non-zero value of every property**, or its share of that
        # leg's total is zero and the leg legitimately does not move.
        # :func:`series` guarantees it today (salt >= 0.1, tracers >= 1.0,
        # temperature >= 2.0 on every source and record), and the
        # presence requirement above catches the related case where a
        # whole leg's source sum is zero.
        blind = [c for c in closures
                 if c in data["worst"] and data["worst"][c][0] <= RTOL]
        result["fracsum_blind"] = blind
        if blind:
            shown = ", ".join(f"{c} {data['worst'][c][0]:.3e}"
                              for c in blind)
            problems.append(
                f"every closure to fail on a file whose fractions sum to "
                f"{1.0 + FRAC_PERTURB!r}; {shown} closed to {RTOL:g} or "
                f"better, so {len(blind)} of the {len(closures)} cannot "
                f"see "
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
    if control == "swap":
        # A swap of the two tracers' names is a swap of RNF_trPtr made by
        # the input: runoff tracer k still carries the series the oracle
        # expects for position k, so the RNFtrNN closures (blind to the
        # mapping) must still close, while each ptracer now receives the
        # other one's water, so every ForcTrNN closure must fail.
        ptr = [c[0] for c in tracer_closures(case) if c[0].startswith("p")]
        trc = [c[0] for c in tracer_closures(case) if c[0].startswith("t")]
        result["swap"] = {c: data["worst"].get(c) for c in ptr + trc}
        for name in CLOSURES + tuple(trc):
            if name in data["worst"] and data["worst"][name][0] > RTOL:
                problems.append(
                    f"the {name} closure to still hold on the swapped file "
                    f"(worst {data['worst'][name][0]:.3e}): the swap moves "
                    f"only which ptracer each series reaches")
        for name in ptr:
            worst = data["worst"].get(name)
            if worst is None or worst[0] <= RTOL * DISCRIMINATION:
                problems.append(
                    f"the {name} closure to fail by more than "
                    f"{RTOL * DISCRIMINATION:g} on the swapped file (it is "
                    f"{worst and worst[0]}): it cannot then see a swap of "
                    f"RNF_trPtr")
        judge_unfed(case, result, problems)
        return result
    if control == "feed_zero":
        # The counterfactual of the unfed oracle: a zero-valued variable
        # for the unfed ptracer makes the package apply -m*C_ref to it,
        # which is the term it would apply if it fed a tracer the file
        # does not carry. Both legs of judge_unfed must see that, while
        # every closure still holds.
        for name in closures:
            if name in data["worst"] and data["worst"][name][0] > RTOL:
                problems.append(
                    f"the {name} closure to still hold on the feed_zero file "
                    f"(worst {data['worst'][name][0]:.3e})")
        seen = []
        judge_unfed(case, result, seen)
        result["feed_zero_seen"] = seen
        legs = result.get("unfed_legs", {})
        for leg in ("forcing", "state"):
            if not legs.get(leg):
                problems.append(
                    f"the unfed oracle's {leg} leg to fail when the term is "
                    f"applied to the unfed ptracer (it did not): it would "
                    f"then pass a run that adds -m*C_ref to it")
        return result

    for name in closures:
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
    judge_unfed(case, result, problems)
    return result


def judge_unfed(case, result, problems):
    """A ptracer the file does not feed gets nothing (RUNOFF-008).

    Two legs, each decisive on its own, for every unfed ptracer:

    * **forcing**: its ``ForcTrNN`` is exactly 0.0 at every cell of every
      dump. With ``PTRACERS_EvPrRn`` unset the model's own surface term
      for it is zero in every arm
      (``pkg/longstep/longstep_forcing_surf.F:81``, ``:105``, ``:129``
      test it before adding anything), so the package is the only thing
      that could make it non-zero;
    * **state**: its ``PTRACER0n`` state dump is bitwise identical, at
      every dump, to a reference run with the same flux and **no**
      ``runoff_ptracer_*`` variable at all (``check_case`` runs it). A
      passive tracer feeds nothing back, so nothing else differs between
      the two runs for it.

    ``result["unfed_legs"]`` records, per leg, whether it *saw* a term
    (True = the leg failed); ``feed_zero`` requires both to be True.
    """
    unfed = unfed_ptracers(case)
    if not unfed:
        return
    data = result.get("measure") or {}
    forcing = {}
    for _n, name, _stream in unfed:
        hits = [(d["iteration"], d["unfed"][name]["nonzero"],
                 d["unfed"][name]["max_abs"]) for d in data.get("per_dump", [])
                if d["unfed"][name]["nonzero"]]
        forcing[name] = hits
        if hits:
            problems.append(
                f"the unfed ptracer {name} to receive no forcing at all; "
                f"ForcTr is non-zero on {len(hits)} dump(s), first "
                f"{hits[0][1]} cell(s) at dump {hits[0][0]}, largest "
                f"{max(h[2] for h in hits):.3e}")
    state = result.get("unfed_state") or {}
    for _n, name, _stream in unfed:
        got = state.get(name)
        if not got or not got["compared"]:
            problems.append(f"the unfed ptracer {name}'s state to be "
                            f"compared with the reference run on at least "
                            f"one dump (none was)")
        elif got["differing"]:
            problems.append(
                f"the unfed ptracer {name}'s state to be bitwise identical "
                f"to the run with no runoff tracer variable; "
                f"{got['differing']} values differ over {got['compared']} "
                f"dump(s), largest {got['max_abs']:.3e}")
    result["unfed_legs"] = {
        "forcing": any(forcing.values()),
        "state": any(v.get("differing") for v in state.values())}


def compare_unfed_state(case, run_dir, ref_dir):
    """Compare every unfed ptracer's state dumps between two runs, bitwise."""
    import glob
    import numpy as np
    out = {}
    for n, name, _stream in unfed_ptracers(case):
        paths = sorted(glob.glob(os.path.join(run_dir,
                                              f"PTRACER{n:02d}.*.data")))
        compared, differing, worst = 0, 0, 0.0
        for path in paths:
            base = os.path.basename(path)[:-5]
            mine, _ = read_mds(run_dir, base)
            theirs, _ = read_mds(ref_dir, base)
            compared += 1
            diff = mine != theirs
            differing += int(np.count_nonzero(diff))
            if diff.any():
                worst = max(worst, float(np.abs(mine - theirs).max()))
        out[name] = {"compared": compared, "differing": differing,
                     "max_abs": worst,
                     "labels": [os.path.basename(p).split(".")[1]
                                for p in paths]}
    return out


def check_case(case, nproc, args, control=None):
    """Run and judge one case; return the result dictionary."""
    name = case["name"] + (f"_mpi{nproc}" if nproc else "") \
        + (f"_{control}" if control else "")
    input_name = PREFIX + name
    exp_dir = os.path.join(VERIF, case["experiment"])
    input_dir = os.path.join(exp_dir, input_name)
    build = case.get("build", BUILD) + (f"_mpi{nproc}" if nproc else "")
    binary = os.path.join(exp_dir, build, "mitgcmuv")
    result = {"case": case["name"], "processes": nproc, "control": control,
              "closures": list(closures_of(case)), "problems": []}
    if not os.path.isfile(binary):
        print(f"MISSING {name}: no binary at {binary}")
        if case.get("build") == PTR2_BUILD:
            print("     rerun this check with --build, which compiles it")
        else:
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
            case["experiment"], input_name, nproc, args.timeout,
            build=case.get("build", BUILD))
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
        for key, stream in case_streams(case).items():
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
        if unfed_ptracers(case):
            # The reference of the unfed oracle: the same input with no
            # runoff_ptracer_* variable at all.
            ref_input = input_name + "_ref"
            ref_input_dir = os.path.join(exp_dir, ref_input)
            shutil.rmtree(ref_input_dir, ignore_errors=True)
            os.makedirs(ref_input_dir)
            write_input(case, ref_input_dir, table, no_tracers=True)
            ref_dir, ref_exit, ref_timed_out = run_model(
                case["experiment"], ref_input, nproc, args.timeout,
                build=case.get("build", BUILD))
            ref_logs = read_file(ref_dir, "output.txt") or ""
            if (ref_timed_out or ref_exit != 0
                    or "Execution ended Normally" not in ref_logs):
                result["problems"].append(
                    f"the reference run with no tracer variable to end "
                    f"normally (exit {ref_exit})")
            else:
                result["unfed_state"] = compare_unfed_state(case, run_dir,
                                                            ref_dir)
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
            if unfed_ptracers(case):
                ref_input = input_name + "_ref"
                shutil.rmtree(os.path.join(exp_dir, ref_input),
                              ignore_errors=True)
                shutil.rmtree(os.path.join(exp_dir, "output_esx_" + ref_input
                                           + (f"_mpi{nproc}" if nproc
                                              else "")),
                              ignore_errors=True)


def report(result):
    """Print one case's verdict and its measured figures; return its pass."""
    name = result["case"] + (f"_mpi{result['processes']}"
                             if result["processes"] else "") \
        + (f"_{result['control']}" if result["control"] else "")
    ok = not result["problems"]
    data = result.get("measure") or {}
    parts = []
    for key in result.get("closures") or CLOSURES:
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
    for name, got in sorted((result.get("unfed_state") or {}).items()):
        forcing = sum(1 for d in data.get("per_dump") or []
                      if d["unfed"][name]["nonzero"])
        print(f"     unfed {name}: ForcTr non-zero on {forcing} dump(s); "
              f"state {got['differing']} value(s) differ from the "
              f"no-variable run over {got['compared']} dump(s)")
    for problem in result["problems"]:
        print(f"     expected {problem}")
    return ok


def control_applies(case, control):
    """Return whether ``control`` can be run on ``case``.

    ``permute`` and ``fracsum`` perturb the table and apply to every
    case; ``swap`` needs exactly two tracer variables and ``feed_zero`` an
    unfed ptracer. A selection that leaves no applicable pair exits 2.
    """
    if control == "swap":
        return len(case["file_tracers"]) == 2
    if control == "feed_zero":
        return bool(unfed_ptracers(case))
    return True


def main(argv=None):
    """Run the selected cases and controls, and judge the whole selection.

    Builds the run list as the cross product of the selected cases, the
    process counts each case declares (``--mpi`` narrows it, and a count
    a case does not declare simply contributes no run) and the controls
    asked for; an empty list is exit 2 rather than a vacuous success.

    After the runs it makes the Adams-Bashforth comparison of every case
    that names a ``same_as`` partner: the residuals of every closure not
    in ``STATE_READING`` must
    be bitwise identical between the two, the heat residual must be
    within :data:`RTOL` in both, and their ``state_signature`` must
    differ so that the insensitivity is not the insensitivity of two
    identical runs. A selection that ran one half of a pair without the
    other fails rather than reporting the half it ran, because the pair
    *is* the measurement (LL-014).

    With ``--build`` it first compiles the ``PTRACERS_num = 2`` binary
    when a selected case needs it and it is missing or stale
    (``tendency_term_check.build_if_stale``).

    Exit status: 0 if every run met its own expectations, 1 if one did
    not or none ran, 2 if a binary is missing or could not be built, or a
    selection does not exist.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", action="append", default=None,
                        help="run only this case (may be repeated)")
    parser.add_argument("--mpi", type=int, default=None,
                        help="run only this process count (0: serial)")
    parser.add_argument("--control",
                        choices=("permute", "fracsum", "swap", "feed_zero"),
                        action="append", default=None,
                        help="run the named control instead of the plain "
                             "case; the verdict is inverted as that "
                             "control asks. swap applies to the cases "
                             "with two tracer variables, feed_zero to "
                             "the cases with an unfed ptracer")
    parser.add_argument("--build", action="store_true",
                        help="compile the PTRACERS_num = 2 binary the "
                             "selected cases need, when missing or older "
                             "than its sources; without it a missing "
                             "binary is reported and the run exits 2")
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
                if control_applies(case, control):
                    runs.append((case, nproc, control))
    if not runs:
        print(f"no selected case runs on {args.mpi} process(es) with "
              f"control(s) {args.control}")
        return 2
    if args.build and any(c.get("build") == PTR2_BUILD for c, _, _ in runs):
        if not report_build(build_if_stale(PTR2_BUILD, write_ptr2_code,
                                           timeout=args.timeout)):
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
                for k in closures_of(case) if k in a and k in b}
        state_free = [k for k in same if k not in STATE_READING]
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
        differ = [k for k in state_free if same[k][0] != same[k][1]]
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
              + (f"{', '.join(state_free)} identical"
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
