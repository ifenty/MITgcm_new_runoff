#!/usr/bin/env python
"""Sweep for footprint claims that a later change can make stale by ADDING a site.

Why this exists
===============

RUNOFF-030 was rejected by review twice over one error class and never over
its code. Five must-fix items, all the same sentence shape: *a claim that some
package is touched in exactly one place*, made false by a change that added a
second place. Rounds 1 and 2 were scoped as "fix these named lines", so round 1
found four, round 2 corrected them, and round 2's review found a fifth in a
file round 2 had just edited.

The diagnosis (``devel-loop/loop_state/diagnosis/runoff-030-sweep-recall.py``)
measured why the usual sweeps miss this class. Keying on the changed *symbol*
(``useExfCheckRange``/``sflux``/``RNF_srcFluxMax``) found 2 candidates and
missed the survivor; keying on the changed *path* (``exf_check_range.F``)
found **zero**. The reason is structural, and it is this script's whole
premise:

    A footprint claim never names the site that was added.

"the only exf change is one guarded call in ``exf_getffields.F``" contains
neither ``exf_check_range.F`` nor any symbol the patch touched, so no sweep
keyed on what the patch changed can reach it. What it does contain is *the
package* and *an exclusivity word*. So the predicate keys on the package, not
on the edit:

    (a package mention) NEAR (an exclusivity marker) NEAR (a footprint word)

Proximity is what makes it usable. Without it the marker ``only`` matches any
400-character Markdown table row that happens to mention exf: measured on
RUNOFF-030's ``.md``/``.rst``/``.F``/``.h`` scope, 101 candidates, almost all
noise. With the windows below, that scope gave 72 candidate hits over 167
swept files with 11 recorded keeps at RUNOFF-030, and 68 over the same 167
files when RUNOFF-042 re-measured it (tree growth, not a predicate change).
Adding ``.py`` on RUNOFF-042 makes it **95 candidate hits over 214 swept
files, of which 38 are recorded keeps and 57 are the standing triage queue**.
That queue was also 57 before the suffix, and the coincidence is worth
spelling out rather than reading as "nothing changed": the ``.py`` suffix adds
52 candidates, of which 25 are in this file and excluded by :data:`SELF` and
27 were triaged into ``KEEP`` by RUNOFF-042, so the 57 untriaged lines are the
same ``.md``/``.F`` queue as before. The swept-file figure moved twice in this
one issue and both steps are measured: the suffix took 167 files to 294, the
self-exclusion to 293, and round 1's :data:`EXCLUDED_PREFIXES` to **214** by
dropping 79 vendored snapshot copies that carry no candidate at all.

Recall is measured, not asserted
================================

``--self-test`` runs the predicate over the eight known claims of this class
and over benign lines that must not match, and reports 8 of 8 and 0 of 3. Five
are the sentences review actually must-fixed on RUNOFF-030; three are recall
gaps found while building the predicate, each kept so its gap cannot reopen.
Four of the five are verbatim from the pre-change tree (commit ``d95645a``)
and from this issue's own round-0 edit; the fifth is verbatim from commit
``1224dd2``, contiguous at ``open_issues.md:441``, where the corrected record
quotes its own pre-fix clause as the subject of that correction. All five are
therefore recovered text traceable to a commit, and none is a reconstruction.
A predicate for this class is only worth having if it would have caught the
class, so the check ships with it rather than being done once by hand.

**Three places state that provenance -- this paragraph, the ``MUST_MATCH``
block comment and element 5's own comment -- and they must be kept in step.**
They were not: correction round 4 replaced element 5 and updated this
paragraph, round 5 corrected the block comment and the element comment and
left this paragraph behind. Both times the same shape, which is the very class
this file sweeps for: a claim about a set made false by changing one element,
corrected in some places and left standing in another. The audit that caught
the round-5 instance is worth keeping as the method -- compare all three, do
not read one.

Scope is declared, never derived from VCS state
===============================================

See :func:`authored_paths`. Round 3 keyed the nested-repository scope on ``git
status --porcelain``, so committing both repositories dropped
``pkg/exf/exf_check_range.F`` -- the file carrying this issue's own code
change -- out of the swept set: 72 candidates fell to 70 and 10 keeps to 9,
and the exit-2 alarm fired only because that one file happened to hold a
needle. Review A named the generative premise: **the candidate signature is a
sufficient guard only for artifacts that are functions of file content.** This
one was a function of (content, VCS state), so committing changed its
behaviour while the signature stayed ``6ab98655`` and neither the signature,
the documentation contract nor the focused suite objected. Hence the scope
guard below, which asserts the *set* rather than trusting where keeps happen
to live.

What a hit means
================

A hit is a **candidate**, not a defect. Such a sentence is fine when an
antecedent nearby enumerates the sites, and fine when it is dated history. It
is a defect only when it asserts exclusivity with no antecedent, or with one
the change outgrew. Each candidate is therefore corrected or recorded in
``KEEP`` with the reason it stays true, so a later reader can tell a
deliberate keep from a miss -- the thing the first two rounds could not do.

Exit status: 0 when every candidate hit is covered by ``KEEP`` and all three
guards pass; 1 when a hit needs triage; 2 when a ``KEEP`` needle matches
nothing or is multi-line (a rotted allowlist, which would silently lose
coverage); **3 when a file named in ``KEEP`` is not in the swept set**, which
is the scope guard that makes scope and recall one check; 4 when
``--self-test`` fails.

Which invocations a suite can hold
==================================

RUNOFF-042 settled an enrolment both RUNOFF-030 reviewers deferred. Two modes
are in the ``structural`` suite of ``esx/project.json``, and the reason is the
exit codes above:

* ``--self-test`` returns 0 or 4 only. It evaluates the predicate against the
  literal fixtures in this file and **never calls** :func:`tracked` or
  :func:`sweep`, so it cannot see a scope shrink, a dead needle or a
  multi-line needle. It guards the predicate, not the instrument.
* ``--guards`` runs the real sweep over the tree and returns the three guards
  alone -- 3, 2 or 0 -- treating untriaged candidates as information. It
  guards the instrument.
* The **default** invocation cannot be enrolled: it returns 1 whenever any
  candidate is untriaged, which is the normal state of a live triage queue
  (57 lines at the time of writing), so it would fail for ever.

Usage::

    python tests/footprint_claim_sweep.py [--packages exf rnf] [--json]
    python tests/footprint_claim_sweep.py --self-test
    python tests/footprint_claim_sweep.py --guards [--json]
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Packages whose footprint this project claims anywhere. ``rnf`` is included
#: although it is the package being added: "pkg/rnf touches the model only
#: here" fails the same way, and keying only on the package being *edited* is
#: the mistake this script exists to avoid.
PACKAGES = ("exf", "rnf")

#: Suffixes swept. Fortran and headers carry footprint claims in comments just
#: as prose files do -- ``exf_check_range.F``'s own banner is one. ``.py`` was
#: added on RUNOFF-042: the tests and tools carry them in docstrings and
#: comments the same way, and the scan found one live stale instance the moment
#: it was turned on (``refusal_check.py``'s list of the tile-local refusals,
#: which named three of the five checks: RUNOFF-033 added the cell-centre
#: check and RUNOFF-040 the per-cell aggregate, and neither was added to the
#: list). Measured cost of the suffix alone: 167 swept files to 294 and 68
#: candidate hits to 120, of which 25 are this file's own fixtures and prose;
#: with those excluded (:data:`SELF`) the sweep reads 293 files and reports 95,
#: and with the vendored snapshots excluded too
#: (:data:`EXCLUDED_PREFIXES`) 214 files and the same 95.
SUFFIXES = (".md", ".rst", ".F", ".h", ".py")

#: This file is **excluded from its own sweep**, by path, in :func:`tracked`.
#:
#: Why: all 25 of its candidate hits are *quotations*, not claims this project
#: makes. 18 are inside the three fixture lists (8 in :data:`KEEP`, 7 in
#: :data:`MUST_MATCH`, 3 in :data:`MUST_MATCH_PATHED`) and the other 7 are
#: prose that quotes an example claim in order to explain the predicate
#: ("the only exf change is one guarded call in ``exf_getffields.F``" above,
#: "pkg/rnf touches the model only here" on :data:`PACKAGES`). Triaging a
#: quotation of a claim is meaningless: the ``KEEP`` reason would have to be
#: "this is a fixture", 25 times, and every one of those needles would then be
#: a line that no longer may be reworded without turning the sweep red.
#:
#: The narrower alternative -- excluding the three fixture spans rather than
#: the file -- was refused, and not on cost: a span is line numbers, and a
#: line-number allowlist rots on the first insertion above it. That is the
#: exact failure mode :data:`KEEP` is substring-matched to avoid, so buying
#: seven quoted prose lines with a mechanism this file exists to warn against
#: is the wrong trade.
#:
#: **What the exclusion leaves unwatched, as a class and not as examples
#: (LL-016):** every line of this file -- module docstring, every comment,
#: every ``#:`` attribute doc, every string literal, every fixture -- is
#: outside the swept set. So a footprint claim this file makes *about the
#: project* in any of those places is invisible to this sweep, and no other
#: mechanism replaces it: ``--self-test`` evaluates the literal fixtures in
#: memory and never reads the file from disk, and the documentation inventory
#: covers this path only for *superseded figures*
#: (``doc_contract.py stale``), which is a different predicate. The residual
#: risk is accepted because the file's subject matter is the predicate rather
#: than the model's footprint; the way to re-cover it, if that ever stops
#: being true, is to move the fixtures into a data module the sweep skips and
#: drop this exclusion.
SELF = os.path.relpath(os.path.abspath(__file__), ROOT).replace(os.sep, "/")

#: Characters either side of the marker within which the footprint word and
#: the package mention must fall. Chosen by measurement, not taste
#: (``devel-loop/loop_state/scratch/.../tune_window.py``): over the frontier
#: 30/40/60/90 x 90/120/200 the recall on the known class is identical, so the
#: tightest pair is taken and the cost is the lowest -- 30/90 gives the
#: candidate count reported in the issue, which is also the count review B
#: reached independently with its own wording.
FOOTPRINT_WINDOW = 30
PACKAGE_WINDOW = 90

#: An exclusivity or completeness marker. Wider than the diagnosis script's,
#: which required ``only|sole|single`` and so would miss the
#: "unaffected"/"untouched"/"no other" phrasings that were three of the five
#: must-fix items. Every alternative below is a form that actually occurred.
MARKER = re.compile(
    r"\b(only|sole|solely|single|exclusively"
    r"|no other|nothing else|none other|everything else"
    r"|every other|all other"
    r"|unaffected|untouched|unchanged|not edited|not touched"
    r"|is the whole|are the whole)\b", re.I)

#: The claim has to be *about a footprint*: the sites a change occupies, or
#: the guards it leaves alone. ``check|test|bound|guard`` are in the set
#: because three of the five must-fix items were about range checks rather
#: than about edits, and the self-test below is what established that the
#: edit-only wording missed them.
FOOTPRINT = re.compile(
    r"\b(change[sd]?|edit(s|ed|ing)?|modif\w+|touch(es|ed)?|footprint[s]?"
    r"|patch(es|ed)?|hook(s|ed)?|call[s]?|diff|line[s]?|file[s]?|code"
    r"|check[s]?|test[s]?|bound[s]?|guard[s]?|site[s]?|routine[s]?)\b", re.I)

#: A marker directly introducing a condition is a *behaviour* claim, not a
#: footprint claim: "exf applies it only when a dense file is set" says when
#: something happens, while "the only change to exf code" says where the
#: change is. Without this the first sentence is a false positive, which the
#: self-test demonstrated.
CONDITIONAL = re.compile(
    r"^\s*(when|if|where|while|unless|after|before|during|once|for|to)\b",
    re.I)

#: "leaves results unchanged" is a no-change *result* claim, which this
#: project makes constantly and which adding a site cannot falsify -- it is
#: about the model's answers, not about where the code was touched. Excluded
#: by its object rather than by its file, so a genuine footprint claim in the
#: verification matrix is still found.
RESULT_CLAIM = re.compile(
    r"\b(result|results|output|answer|bit|bitwise|digit|identical|value)\b",
    re.I)

#: Path prefixes dropped from the swept set outright, with the reason.
#:
#: ``ESX-team-local/backups/`` is 81 tracked files in timestamped snapshots
#: (``<stamp>-upgrade-<hash>/``) that ``ESX-team-local/deployments/`` writes
#: before each kit upgrade overwrites ``tools/esx/``. 79 of them were in the
#: swept set -- 61 ``.py`` of the 126 files the RUNOFF-042 suffix added, plus
#: 18 ``.md`` that had been swept since RUNOFF-030 -- and all 79 are copies
#: this project may not edit, so a candidate there would be **unactionable**:
#: the only honest triage would be a ``KEEP`` entry whose reason is "we do not
#: own this file", and the needle would then pin a line in a snapshot.  Worse,
#: a kit upgrade landing one footprint-shaped sentence would turn this
#: project's ``structural`` suite red over a file it does not own, which is
#: precisely the alarm-for-nothing the enrolment is meant to avoid. Measured
#: cost of the exclusion today: **zero candidates** -- all 79 files produce no
#: hit under the current predicate -- so it removes 79 files from the swept
#: figure (293 to 214) and changes no candidate, keep or guard.
#:
#: ``tools/esx/`` is deliberately **NOT** excluded, though it is the same kit:
#: those 35 files we edit constantly (`f80e881` and this iteration both
#: changed them), so a footprint claim there is ours and is actionable. The
#: asymmetry with the documentation contract, whose ``stale_lines`` skips
#: ``tools/esx/`` outright, is intended and is the same judgment read from the
#: other end: a *superseded figure* in the kit is almost always the kit's own
#: and not about this model, while a claim that ``pkg/exf`` or ``pkg/rnf`` is
#: touched in exactly one place is about this project wherever it is written.
#: Excluded by path and not by content, in :func:`tracked`, so that a ``KEEP``
#: entry naming an excluded file fails loudly as scope guard (1), exit 3,
#: exactly as one naming :data:`SELF` does.
EXCLUDED_PREFIXES = ("ESX-team-local/backups/",)


#: Files that are dated, append-only history. A claim in them describes what
#: was true when it was written and is not maintained; the project's own
#: documentation contract already treats these as records outside the
#: inventory. ``open_issues.md`` is deliberately NOT here: it is live, and it
#: did carry one of this issue's stale footprint claims.
HISTORY = ("closed_issues.md", "lessons_learned.md",
           "lessons_learned_evidence.md", "old_lessons_learned.md")


def package_pattern(packages):
    """A mention of an affected package, in any of the forms it takes.

    Deliberately a case-insensitive **substring** and not ``\\bexf\\b``. The
    package name is usually embedded in an identifier -- ``useExfCheckRange``,
    ``EXF_CHECK_RANGE``, ``exf_getffields.F``, ``useRNF``,
    ``RNF_srcFluxMax`` -- and ``_`` is a word character, so a word-boundary
    pattern matches none of those. The self-test below is what exposed this:
    with boundaries, two of the five must-fix sentences were missed because
    their only package mention was ``useExfCheckRange``. ``exf`` and ``rnf``
    occur in no ordinary English word, so substring matching costs little
    precision here.
    """
    return re.compile("|".join(re.escape(p) for p in packages), re.I)


def candidate(text, packages=PACKAGES, path=""):
    """True when ``text`` carries a footprint claim about an affected package.

    Evaluated per marker occurrence inside the windows above, so the
    exclusivity word has to be near both the footprint word and a package
    mention rather than merely on the same line.

    ``path`` supplies the package by **location**: a footprint claim inside
    ``pkg/exf/...`` or ``doc/phys_pkgs/exf.rst`` is about exf whether or not
    the sentence repeats the name, and measurement showed two such claims
    (``exf_check_range.F``'s own banner and ``exf.rst``'s paragraph) were
    missed for exactly that reason.
    """
    pkg = package_pattern(packages)
    in_package_file = bool(path and pkg.search(path))
    text = normalise(text)
    for m in MARKER.finditer(text):
        if CONDITIONAL.match(text[m.end():]):
            continue
        f_lo = max(0, m.start() - FOOTPRINT_WINDOW)
        p_lo = max(0, m.start() - PACKAGE_WINDOW)
        near = text[f_lo:m.end() + FOOTPRINT_WINDOW]
        if RESULT_CLAIM.search(near):
            continue
        if FOOTPRINT.search(near) and (
                in_package_file
                or pkg.search(text[p_lo:m.end() + PACKAGE_WINDOW])):
            return True
    return False


#: Deliberate keeps: (path, substring of the claim, reason it is true).
#: Matched by substring rather than line number so an entry survives edits
#: above it; a line-number allowlist would rot on the first insertion, which
#: is the very failure mode this script is about.
#:
#: Triaged in RUNOFF-030 correction round 3, re-checked rather than inherited.
#: Entries 12-38 are RUNOFF-042's triage of the ``.py`` scope, in three
#: classes. Class A is RUNOFF-030's: the exclusivity claim is true because an
#: adjacent antecedent enumerates the sites. The two new ones:
#:
#: * **B -- not a footprint claim.** The exclusivity word governs a behaviour,
#:   a command-line option, a file-name pattern or a generated fixture, so no
#:   site added to ``pkg/exf`` or ``pkg/rnf`` can make it false. The predicate
#:   drops most of these through ``CONDITIONAL`` and ``RESULT_CLAIM``; these
#:   are the residue that survives because ``candidate()`` takes the package
#:   from the *path* (every ``tests/rnf/*.py`` file is an "rnf file"), so a
#:   sentence in them needs no package word of its own to be a candidate. That
#:   is a known precision cost of the path keying, not a defect in the line.
#: * **C -- a coverage claim.** It says which instrument or which model check
#:   sees what. Adding an instrument or a check falsifies it exactly as adding
#:   a code site falsifies a footprint claim, so these are kept deliberately
#:   and each reason names the antecedent that holds it true. One of them was
#:   stale when the ``.py`` scan first ran and was corrected rather than kept
#:   (``refusal_check.py``'s tile-local list; entry 29 keeps the fixed line).
KEEP = [
    # ---- CLASS A: an exclusivity claim that is true because an antecedent
    # ---- enumerating the sites is immediately adjacent.
    ("docs/package_design.md",
     "every range check of every field other than those two is untouched",
     "A: 'other than those two' refers to the two conditioned tests "
     "enumerated in the two bullets immediately above, so the exclusion is "
     "explicit. This is the form package_design uses after round 2."),
    ("docs/package_design.md",
     "two above are the whole exf footprint of this change",
     "A: 'the two above' is the antecedent, in the same bullet."),
    ("docs/package_design.md",
     "Those two are the whole exf",
     "A: round 3 replaced the false 'only change to exf code' here; the "
     "antecedent is this sentence itself, which names both edits."),
    ("docs/package_design.md",
     "`exf_mapfields.F` is not edited",
     "A: a true negative claim about one named file, not an exclusivity "
     "claim over the set of sites, and review B asked for it to be kept."),
    ("esx/project_profile.md",
     "test and every other field's range check are untouched",
     "A: antecedent is the two sub-bullets immediately above in the same "
     "bullet. Kept implicit deliberately; the round-3 note in "
     "open_issues.md records why this one stayed implicit while "
     "package_design's was made explicit."),
    ("esx/project_profile.md",
     "The exf footprint is **two** files and nothing else in `pkg/exf`",
     "A: states the count and then enumerates both sites in the two "
     "sub-bullets that follow, so adding a third site would contradict a "
     "number rather than slip past a vague word."),
    # Needles are SINGLE LINE by contract, enforced below. This one was
    # written multi-line in round 3 and could never match, because kept()
    # compares against one stripped line: that is the second root cause of
    # the blind guard review B found, independent of the path keying.
    ("esx/project_profile.md",
     "sflux` bound (next sub-item); no *other* exf field's range check",
     "A: round 3 fixed this line, which was the sixth instance of the class "
     "and was found by this sweep rather than by review; it now names both "
     "conditioned tests before the exclusion, so 'other' has an antecedent "
     "in the same sentence."),
    ("MITgcm/pkg/exf/exf_check_range.F",
     "every other field's range included, and nothing changes at all",
     "A: the two conditioned tests are enumerated in the bullets "
     "immediately above in the same banner comment."),
    ("MITgcm/doc/phys_pkgs/exf.rst",
     "every other field's range check, and both conditions are guarded by",
     "A: both conditioned tests are described in the paragraph immediately "
     "above, and the sentence goes on to name what still applies."),
    ("docs/model_contract.md",
     "Nothing else in `pkg/exf` changed",
     "A: trails an explicit enumeration of both exf edits in the same "
     "sentence, so it closes that list rather than asserting one site."),
    ("esx/project_profile.md",
     "without `pkg/rnf` is byte-for-byte unaffected",
     "A: a claim about a build with the package off, whose antecedent is "
     "the useRNF guard named in the same sentence. Adding an exf site "
     "cannot falsify it as long as the guard holds, which is what the "
     "no-change experiments measure."),

    # ======== RUNOFF-042: the .py scope, 27 candidates, each read in place.
    # ---- tests/rnf/applied_field_check.py
    ("tests/rnf/applied_field_check.py",
     "Pattern of the only file name in scope as a dump of",
     "B: 'only file name in scope' is about which of the run's output files "
     "this regex accepts as a dump of one stream, and the next sentence "
     "states the complement (anything else matching the wider glob is "
     "reported, never silently taken as a dump). Nothing about where pkg/rnf "
     "is touched."),
    ("tests/rnf/applied_field_check.py",
     'help="check only this case (repeatable)")',
     "B: an argparse help string describing what --case restricts the run "
     "to. The exclusivity is the option's semantics; it is kept rather than "
     "reworded because the wording is the user-visible help text."),

    # ---- tests/rnf/budget_check.py
    ("tests/rnf/budget_check.py",
     "single-process run, and ``tests/rnf/exf_heat_check.py`` cross-checks",
     "C: the marker is 'single' in 'single-process run', describing where "
     "tendency_term_check measures (one cell, one tile). True and dated by "
     "construction: that check writes its own one-cell file. The sentence it "
     "serves -- 'Neither sums over targets' -- is the coverage claim, and it "
     "names both instruments it is about rather than saying 'no other'."),
    ("tests/rnf/budget_check.py",
     "so over every tile of every process, and not only over",
     "B: states the domain this check sums over (every cell of the global "
     "layout, not just the file's targets). A scope-of-summation statement "
     "about this script's own oracle, with its reason in the same sentence; "
     "no site in pkg/exf or pkg/rnf can falsify it."),
    ("tests/rnf/budget_check.py",
     "no other instrument's heat, salt or tracer criterion can see it",
     "C: the strongest claim of the class in the .py scope, and it carries "
     "its own antecedent ('because nothing else in the project sums those "
     "three against a source total') plus, in the two bullets below, the "
     "enumeration of every other instrument and the reason each is blind. "
     "RUNOFF-016 round 1 narrowed this very sentence from a looser version "
     "(commit 00bf581, 'Scope my own overclaim'), and budget_check is the "
     "newest instrument, so no later one is unaccounted for. An instrument "
     "added after this must be added to that enumeration."),
    ("tests/rnf/budget_check.py",
     "would change the binary every other committed",
     "B: 'every other committed cs32 oracle' is about which reference "
     "results a changed packages.conf would invalidate -- a build-input "
     "claim about the verification set, not about the sites of a change. "
     "Its conclusion (the tracer closure is not measured on cs32) is stated "
     "in the same sentence."),
    ("tests/rnf/budget_check.py",
     "this check reuses; only the time axis and",
     "B: says which columns of the committed sparse file this check reuses "
     "and which it writes itself, so that RNF_INIT_FIXED's placement checks "
     "still see a table they accept. A claim about this script's fixtures."),
    ("tests/rnf/budget_check.py",
     "the guard above names only ``nonlinFreeSurf``.",
     "C: a claim about the condition of one named model guard "
     "(update_surf_dr.F:49, cited two lines above), made to correct an "
     "earlier wrong reason in the same docstring. It is falsifiable by a "
     "change to that guard, which is why it is worth keeping visible rather "
     "than reworded; the citation is the antecedent."),
    ("tests/rnf/budget_check.py",
     "Over **every** cell of the layout, not only the file's target",
     "B: the code comment at the oracle that implements the domain stated "
     "in the docstring above, with its reason on the next two lines. Same "
     "judgment as the docstring line; kept separately because guard (2) is "
     "per needle and these two lines can drift apart."),

    # ---- tests/rnf/exf_heat_check.py
    ("tests/rnf/exf_heat_check.py",
     "1 K in the **sparse** file only: the control.",
     "B: describes the perturbation the control applies -- one source's "
     "temperature moved in the sparse file and not in the dense one. The "
     "'only' is the perturbation's extent, which is what makes the two runs "
     "differ; it asserts nothing about code sites."),
    ("tests/rnf/exf_heat_check.py",
     "which is what makes it a check of the unchanged dense path",
     "C: 'the unchanged dense path' is a real footprint claim, and it is "
     "true for the reason given in the four lines above it: this run has "
     "useRNF false, so both exf edits are on their unconditioned branch and "
     "the run is held to the exf bound in full. It is the per-run form of "
     "the project_profile keep 'without pkg/rnf is byte-for-byte "
     "unaffected', and the no-change experiments are what measure it."),
    ("tests/rnf/exf_heat_check.py",
     "temperature moved 1 K in the sparse file only, largest",
     "B: the printed PASS/FAIL line of the control, wording the same "
     "perturbation as the docstring above. Kept, not reworded: this text is "
     "the instrument's own output and refusal_check-style log assertions "
     "elsewhere depend on such lines being stable."),

    # ---- tests/rnf/placement_probe.py
    ("tests/rnf/placement_probe.py",
     "only a move between cells of different area.",
     "C: a claim about the coverage of ONE named model check (the area "
     "check of RNF_INIT_FIXED), and the sentences immediately above state "
     "the complement -- what protects such a target is applied_field_check "
     "and the cell-centre check. The enumeration is adjacent, so a new "
     "check would contradict a named list rather than slip past."),
    ("tests/rnf/placement_probe.py",
     "the two differ only in how the",
     "B: distinguishes two exch2 I/O layouts (map_io 0 and 1) in the "
     "arithmetic of the global file index. A statement about the exch2 "
     "layout definition, not about this project's footprint."),

    # ---- tests/rnf/refusal_check.py
    ("tests/rnf/refusal_check.py",
     "what no other check can see: the cell it lands on is wet",
     "C: an exclusivity claim about model checks, and the rest of the "
     "sentence is the antecedent: the cell is wet, the fractions still sum "
     "to 1 and the rA is bitwise equal, so the land, fraction and area "
     "checks cannot see the move. The case's own forbid list asserts that "
     "blindness, so the claim is measured on every run, not just written."),
    ("tests/rnf/refusal_check.py",
     "the aggregate is the only thing wrong with the file",
     "A: the antecedent is in the same sentence -- the collapse carries "
     "target_cell_area, target_lon and target_lat with the targets and "
     "leaves the fractions alone -- and the forbid list of the case asserts "
     "that no init check fires."),
    ("tests/rnf/refusal_check.py",
     "Every process is judged on its own files. A single-process run writes",
     "B: the marker is 'single' in 'single-process run'; the paragraph "
     "states which log file each process writes under MPI and without it. "
     "A fact about MITgcm's output layout."),
    ("tests/rnf/refusal_check.py",
     "A refusal that only one tile's check detects (land, cell area, cell "
     "centre,",
     "C, corrected by this sweep rather than kept as it stood: the "
     "enumeration said 'land, cell area, array bound' and had been missing "
     "the cell-centre check since RUNOFF-033 added it. RUNOFF-042's .py "
     "scan returned the line; the list is now FIVE checks over SEVEN cases "
     "(the cases carrying a stderr_any message, which is by definition the "
     "message only the owning process prints), all seven named in the "
     "sentence. Round 0 of this issue wrote six cases over four checks and "
     "both reviewers refuted it: that figure came from walking the AST for "
     "file_case(...) calls, which cannot see cell_above_vol_max, a dict "
     "literal at refusal_check.py:1304-1314, whose per-cell RNF_cellVolMax "
     "breach is detected on the owning tile and reduced with GLOBAL_SUM_INT "
     "(rnf_exf_runoff.F:184-205). Kept because that tie is what a future "
     "tile-local check has to contradict -- and the tie itself is no longer "
     "prose only: tests/esx/test_instrument_claims.py asserts the names and "
     "both counts against a real cases() call, because this needle makes "
     "kept() return a reason and so takes the line out of the triage queue "
     "where guard (2) can never raise it again."),
    ("tests/rnf/refusal_check.py",
     "this one is the only time_bnds in the file.",
     "B: true by construction of the fixture -- the case is built with "
     "bounds: False, which leaves the ordinary time_bnds out, so the "
     "one-dimensional variable this helper writes is the only one. A "
     "statement about a generated NetCDF file."),
    ("tests/rnf/refusal_check.py",
     "would make the run a check of initialisation only",
     "B: explains why the one-step case sets endTime=7200 rather than 3600 "
     "-- with 3600 the model takes no step, so the run would exercise only "
     "initialisation. A claim about what a run measures, with the measured "
     "reason in the two lines above."),
    ("tests/rnf/refusal_check.py",
     "the land, fraction and area checks are all blind to it: only the",
     "C: the code-comment twin of the docstring claim kept above, at the "
     "target_coords case itself. It enumerates the blind checks and names "
     "the one that sees the move, and the next line records that forbid "
     "asserts the blindness. Kept separately from its docstring twin "
     "because guard (2) is per needle; the two must stay in step, which is "
     "this file's own error class."),
    ("tests/rnf/refusal_check.py",
     "test when useRNF would pass everything else here",
     "B: 'everything else' is the rest of this case's assertions, not a set "
     "of code sites: the sentence says a diff that dropped the sflux test "
     "under useRNF would still satisfy them, which is why the case is "
     "decisive for sflux. The five lines around it enumerate what the case "
     "does assert."),
    ("tests/rnf/refusal_check.py",
     "``nproc`` 0 is a single-process run, whose standard output",
     "B: the marker is 'single' in 'single-process run'; the docstring of "
     "process_logs states which files a run on nproc processes writes. "
     "Same class as the module docstring's log paragraph."),

    # ---- tests/rnf/tendency_term_check.py
    ("tests/rnf/tendency_term_check.py",
     "Analytic single-cell check of the runoff tendency terms",
     "B: the marker is 'single' in 'single-cell', the check's own summary "
     "line. It describes the oracle's geometry, which the cases implement by "
     "writing a one-cell file; nothing about footprint."),
    ("tests/rnf/tendency_term_check.py",
     "Only the files this check changes are written; everything else is",
     "B: states what write_input puts in the scratch input directory and "
     "that the harness layers the rest in from lab_sea/input. A claim about "
     "this script's own run directory, falsifiable only by changing this "
     "script."),

    # ---- tests/rnf/timing_field_check.py
    ("tests/rnf/timing_field_check.py",
     'help="check only this case (repeatable)")',
     "B: the same argparse help string as applied_field_check's --case, and "
     "the same judgment. Listed separately because KEEP is keyed on the "
     "path, so one entry cannot cover two files."),

    # ---- MITgcm/utils/python/.../runoff/convert.py
    ("MITgcm/utils/python/MITgcmutils/MITgcmutils/runoff/convert.py",
     "Only the start date's offset from",
     "B: a statement about upstream pkg/exf behaviour -- for yearly files "
     "exf keeps only the start date's offset from 1 January -- with the "
     "routine and line range cited in the same sentence "
     "(exf_getffield_start.F, lines 85-92). It describes what exf does, not "
     "where this project touches it, and this project does not edit that "
     "routine."),
]


#: Nested repositories that the project repo ignores. ``MITgcm/`` is a clone
#: of the fork and is git-ignored here, so a single ``git ls-files`` at the
#: project root lists **none** of the package source, none of the MITgcm docs
#: and neither of the two exf footprint claims that live there. Measured while
#: building this: the sweep silently covered only the project tree until this
#: was added, which would have made every future run a false clean.
NESTED = ("MITgcm",)


#: Paths this project authors inside a nested repository but which
#: ``esx/project.json`` does not declare: the MITgcm documentation pages we
#: write. Neither is a build input, so neither is a ``source_path``. Named
#: individually and not as the ``doc/phys_pkgs/`` prefix, because that prefix
#: is 29 upstream package pages this project neither wrote nor may edit --
#: measured, and it was part of round 3's over-coverage. ``rnf.rst`` does not
#: exist yet (RUNOFF-026 adds it); declaring it now costs nothing and means
#: the page arrives already in scope.
DOC_EXTRA = ("doc/phys_pkgs/exf.rst", "doc/phys_pkgs/rnf.rst")


def authored_paths(root, prefix):
    """The nested-repo paths this project **declares** as its own.

    Read from ``esx/project.json``'s ``source_paths`` and
    ``configuration_paths``, which already are this project's declarative
    statement of what it owns, plus :data:`DOC_EXTRA` for the documentation
    pages that declaration does not cover.

    **This used to be derived from VCS state and that was the defect.** The
    previous version kept a file if it appeared in ``git status --porcelain``
    or lay under one of three guessed prefixes, with the premise written out
    as "any file we have modified -- which is what keeps
    ``pkg/exf/exf_check_range.F`` in scope precisely because this issue edited
    it". "A file we have modified" is not a stable property: it is
    working-tree dirtiness, which empties on exactly the act ``CLAUDE.md``
    tells this project to perform often. Committing both repositories dropped
    ``exf_check_range.F`` -- the file carrying this issue's own code change --
    out of the swept set, measured as 72 candidates falling to 70 and 10 keeps
    to 9. Scope is therefore **declared**, never computed from history.

    Keying on a merge-base was considered and **refused**, by both reviewers
    independently and re-measured here: ``git merge-base --is-ancestor master
    HEAD`` is already true, so the moment ``master`` contains this work -- an
    upstream PR landing, a merge, a sync fast-forward -- ``base..HEAD`` empties
    and the failure returns byte for byte. That is deferral, not immunity, and
    must not be recorded as immunity. ``master`` is also the wrong ref on
    availability grounds: the clone's only remote is the fork, there is no
    ``upstream`` remote, and a clone made with ``-b new_runoff`` would have no
    local ``master`` at all.

    The declaration covers all eleven authored files (``model/inc/PARAMS.h``,
    seven ``model/src`` hooks, ``pkg/exf/exf_check_range.F``,
    ``pkg/exf/exf_getffields.F`` and
    ``pkg/ptracers/ptracers_apply_forcing.F``) plus ``pkg/rnf`` and the
    verification set. Because ``MITgcm/pkg/exf`` is declared as a *directory*,
    the swept set includes exf files this project never edited; that
    over-coverage is the price of using the existing declaration instead of
    maintaining a parallel list, and it is stated rather than hidden.
    """
    import json
    cfg = json.loads((open(os.path.join(root, "esx", "project.json"))).read())
    declared = []
    for key in ("source_paths", "configuration_paths"):
        for p in cfg.get(key, ()):
            parts = p.split("/", 1)
            if parts[0] == prefix and len(parts) == 2:
                declared.append(parts[1])
    declared += list(DOC_EXTRA)
    # A declared directory covers everything under it; a declared file is
    # itself. Both are matched without touching git.
    def keep(f):
        return any(f == d or f.startswith(d.rstrip("/") + "/")
                   for d in declared)
    return keep


def tracked(root, suffixes):
    """Tracked files of this repository and the authored files of nested ones.

    :data:`SELF` and :data:`EXCLUDED_PREFIXES` are dropped here rather than in
    :func:`sweep`, so that the *swept set* main reports is the set actually
    read. That placement is also what makes a ``KEEP`` entry naming one of
    them fail as scope guard (1), exit 3 -- "names a KEEP entry but is not in
    the swept set", which is true -- instead of rotting quietly into a dead
    needle.

    The :data:`HISTORY` exclusion stays in :func:`sweep` because it is a
    different kind, and the difference is worth stating exactly: a history
    file **is** in the swept set and is counted in the swept-file figure, but
    :func:`sweep` ``continue``s before ``open()``, so its bytes are never
    read. (This docstring said "in scope and read" until RUNOFF-042 round 1;
    ``esx/project_profile.md``'s "never read at all" was the correct half of
    that pair.) It is skipped on the content policy that dated history is not
    maintained, and a ``KEEP`` entry naming one of them dies as exit 2 rather
    than exit 3. Both fail loudly, which is the property that matters.
    """
    out = subprocess.run(["git", "ls-files"], cwd=root,
                         stdout=subprocess.PIPE, text=True, check=True)
    names = [f for f in out.stdout.split()
             if f.endswith(suffixes) and f != SELF
             and not f.startswith(EXCLUDED_PREFIXES)]
    for prefix in NESTED:
        cwd = os.path.join(root, prefix)
        if not os.path.isdir(os.path.join(cwd, ".git")):
            continue
        keep = authored_paths(root, prefix)
        out = subprocess.run(["git", "ls-files"], cwd=cwd,
                             stdout=subprocess.PIPE, text=True, check=True)
        names += [os.path.join(prefix, f) for f in out.stdout.split()
                  if f.endswith(suffixes) and keep(f)]
    return names


#: Markdown and RST emphasis split a marker in two: ``no *other* exf field``
#: does not match ``\bno other\b``. Measured on this issue's own round-3 fix,
#: which disappeared from the sweep for exactly that reason. Stripped before
#: matching; offsets are only used for windows, so losing them is harmless.
EMPHASIS = re.compile(r"[*_`]+")


def normalise(text):
    """Drop emphasis punctuation so a marker is not split by formatting."""
    return EMPHASIS.sub("", text)


def needle_is_live(name, needle, hits):
    """Does this one ``KEEP`` needle match a line of its own file's hits?

    Keyed on the **needle**, which is the whole point. The previous version
    asked ``kept(path, text)``, which returns the *first* matching reason for
    that path, so a single live needle marked every needle on the same file
    as used. Measured consequence (review B): entry 7 was dead under every
    scope, including the sealed one, and was masked by three live needles in
    ``esx/project_profile.md`` -- so the sealed "0 stale KEEP needles" was an
    artifact of this defect rather than a property of the allowlist.
    """
    flat = " ".join(needle.split())
    return any(flat in " ".join(text.split())
               for path, _, text in hits if path == name)


def sweep(root, packages=PACKAGES, suffixes=SUFFIXES):
    """Every (path, lineno, text) carrying a footprint claim.

    Each line is matched together with the one **before** and the one after
    it, so a claim wrapped over three lines is still found; the hit is
    reported at the marker's own line. Reaching backwards is not symmetry for
    its own sake: the fifth must-fix sentence of RUNOFF-030 put its marker on
    the last of three lines and its only package mention on the middle one,
    so a forward-only window missed it at every width (measured).
    """
    hits = []
    for name in tracked(root, suffixes):
        if os.path.basename(name) in HISTORY:
            continue
        try:
            with open(os.path.join(root, name), errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines):
            joined = "\n".join(lines[max(0, i - 1):i + 2])
            if (candidate(joined, packages, name)
                    and MARKER.search(normalise(line))):
                hits.append((name, i + 1, line.strip()))
    return hits


def kept(name, text, keeps=KEEP):
    """The KEEP reason covering this hit, or None."""
    for path, needle, reason in keeps:
        if path == name and " ".join(needle.split()) in " ".join(text.split()):
            return reason
    return None


#: The five sentences review actually must-fixed on RUNOFF-030. Four are
#: verbatim from the pre-change tree (commit d95645a) and from this issue's own
#: round-0 edit; the fifth is verbatim from commit 1224dd2, where the record
#: quotes its own pre-fix clause as the subject of its correction -- see the
#: comment on that element. The predicate must match every one of them.
#: Review B found this header still claiming all five were verbatim from the
#: pre-change tree after the fifth had been replaced: a claim about a set made
#: false by changing an element, corrected in the module docstring and in the
#: element's own comment but not here, which is this issue's error class
#: committed against its own fixtures. Keep all three statements in step.
MUST_MATCH = [
    "  `useRNF`; the only exf change is one guarded call in "
    "`exf_getffields.F`\n  (package design, decision 2).",
    "  (read in `rnf_readparms.F`, reported in `rnf_summary.F`). The only "
    "edit inside\n  exf is one guarded call in `exf_getffields.F`.",
    "- This call is the only change to exf code. `exf_mapfields.F` is not "
    "edited.",
    # Three lines, as it stood in the tree: the marker is on the last line
    # and the only package mention on the middle one, which is why the window
    # has to reach the PRECEDING line and not just the following one.
    "test variant. RUNOFF-026 documents `useExfCheckRange`: that its runoff "
    "upper\nbound is skipped with `useRNF`, that `RNF_srcFluxMax` applies "
    "instead, and that\nthe negative-runoff test and every other field's "
    "range check are unaffected.",
    # The genuine fifth, corrected in round 4 on review B's provenance check.
    # Round 3 listed `docs/package_design.md:404` here, which was NEVER
    # must-fixed: review B judged that line true in round 1 and the
    # implementer tightened it voluntarily in round 2. The real fifth lived in
    # `open_issues.md:441` and Arch fixed it himself.
    #
    # WHICH ONE WAS MISSING MATTERS: it is the only must-fixed instance that
    # lived in a RECORD file, and that is the very reason HISTORY above keeps
    # `open_issues.md` in scope while excluding the append-only records. A
    # provenance list that omitted it also quietly undercut that decision.
    #
    # VERBATIM, from commit 1224dd2, contiguous at open_issues.md:441. The
    # pre-fix bytes of this paragraph are indeed in no commit -- it was first
    # committed only after correction -- but the corrected paragraph QUOTES its
    # own pre-fix clause as the subject of that correction, and the quotation
    # is committed. So the fixture is recovered text after all, not a
    # reconstruction, and it is traceable with `git show 1224dd2:open_issues.md`.
    #
    # Earlier wordings of this element were a splice of the corrected stem and
    # the pre-fix clause joined by an invented ", and", labelled "quoted from
    # review B" -- a quotation of neither the review nor any one generation of
    # the record (review B, correction round 4).
    #
    # The stem is NOT decoration and must not be trimmed to the bare clause:
    # the predicate needs a package mention inside its window, and
    # "no other field's range check was touched" alone carries none, so the
    # short form MATCHES NOTHING and would drop recall from 8 of 8 to 7 of 8
    # silently. Measured while making this correction, which is also why the
    # earlier splice existed.
    #
    # KNOWN WEAKNESS OF THIS EXEMPLAR, measured in the round-5 audit rather
    # than assumed. It matches on marker "no other" + footprint word "check"
    # + package token "RNF", and that RNF comes from `useRNF` in the STEM --
    # not from the claim's own subject, which is "no other field's range
    # check" and names no package. So element 5 tests the package window
    # reaching back across a sentence to a mention the claim does not itself
    # make. That is a real property of this class (element 4 above has the
    # same shape, marker on the last line and package on the middle one), so
    # the fixture is legitimate; but it is a weaker exemplar than a claim that
    # names its own package, and a future narrowing of PACKAGE_WINDOW would
    # drop it before it dropped the others. Recorded so that is a decision
    # rather than a surprise.
    "so the quantity tested under `useRNF` is `evap - precip`. The original "
    "wording here said no other field's range check was touched, which was "
    "true of round 0 and false after round 1",
]

#: Three further claims of the same class that the predicate missed when it
#: was first written, each for a different reason, each fixed and kept here so
#: the gap cannot reopen: an unlisted marker word ("Everything else"), a claim
#: whose package is given only by its file path (``exf.rst``), and a footprint
#: noun in the plural ("files") that the singular pattern missed.
MUST_MATCH_PATHED = [
    ("MITgcm/pkg/exf/exf_check_range.F",
     "C     Everything else is unconditional, the negative-runoff test and\n"
     "C     every other field's range included, and nothing changes at all"),
    ("MITgcm/doc/phys_pkgs/exf.rst",
     "Nothing else changes. The negative-:code:`runoff` test still applies, "
     "so does\nevery other field's range check"),
    ("esx/project_profile.md",
     "  `useRNF`. The exf footprint is **two** files and nothing else in "
     "`pkg/exf`"),
]

#: Lines that must NOT match: an exclusivity word about behaviour rather than
#: footprint, and a table row that merely mentions exf far from its 'only'.
MUST_NOT_MATCH = [
    "- The exf `runoftemp` field is not used: exf applies it only when a "
    "dense\n  file is set.",
    "| `time` | `(time)` | double | R | yes | The time each record "
    "represents, in CF form, and only the start date matters |",
    "Each source's fractions sum to 1 across the whole domain, within 1e-6.",
]


def self_test():
    """Measure recall on the known class and precision on benign lines."""
    total = len(MUST_MATCH) + len(MUST_MATCH_PATHED)
    missed = [t for t in MUST_MATCH if not candidate(t)]
    missed += [t for p, t in MUST_MATCH_PATHED if not candidate(t, path=p)]
    caught = [t for t in MUST_NOT_MATCH if candidate(t)]
    print(f"self-test: {total - len(missed)} of {total} known claims of the "
          f"class matched ({len(MUST_MATCH)} actually must-fixed by review on "
          f"RUNOFF-030, {len(MUST_MATCH_PATHED)} recall gaps found while "
          f"building this predicate); {len(caught)} of {len(MUST_NOT_MATCH)} "
          f"benign lines wrongly matched")
    for t in missed:
        print("  MISSED:", " ".join(t.split())[:100])
    for t in caught:
        print("  FALSE POSITIVE:", " ".join(t.split())[:100])
    return 0 if not missed and not caught else 4


def evaluate(root, packages=PACKAGES, suffixes=SUFFIXES):
    """The one measurement both the default run and ``--guards`` read.

    Extracted from ``main`` on RUNOFF-042 when the guards gained their own
    invocation: two code paths computing "the same" swept set and the same
    three guards would be free to drift, and this file's whole subject is a
    statement that stops being true in one place and not another.
    """
    swept = set(tracked(root, suffixes))
    hits = sweep(root, packages, suffixes)
    triaged, untriaged = [], []
    for name, lineno, text in hits:
        reason = kept(name, text)
        (triaged if reason else untriaged).append(
            {"path": name, "line": lineno, "text": text, "keep": reason})

    # (1) Scope guard. Every file a KEEP entry names must be in the swept
    # set. Both reviewers proposed this independently and it is what closes
    # the class, because the exit-2 alarm fired this round only by luck of
    # placement: of the eleven authored MITgcm files, exactly one
    # (exf_check_range.F) happens to hold a needle, so a silent shrink in any
    # region without one would have reported a confident, wrong clean. An
    # assertion on the SET does not depend on where the keeps happen to live,
    # and it makes scope and recall one check.
    absent = sorted({p for p, _, _ in KEEP if p not in swept})
    # (2) Per-needle liveness, keyed on the needle and not the path.
    dead = [(p, n) for p, n, _ in KEEP if not needle_is_live(p, n, hits)]
    # (3) Needles are single-line by contract: kept() compares one stripped
    # line, so a multi-line needle can never match and would masquerade as a
    # keep. Enforced rather than documented.
    multiline = [(p, n) for p, n, _ in KEEP if "\n" in n]
    return {"swept": swept, "hits": hits, "triaged": triaged,
            "untriaged": untriaged, "absent": absent, "dead": dead,
            "multiline": multiline}


def guard_status(result):
    """The exit status of the three guards alone: 3, 2 or 0.

    Untriaged candidates are deliberately not consulted. The guards answer
    "is this instrument still measuring what it claims to measure"; the triage
    queue answers "has every candidate been judged yet", which is work in
    progress rather than rot.
    """
    if result["absent"]:
        return 3
    if result["multiline"] or result["dead"]:
        return 2
    return 0


def report(result, as_json=False, guards_only=False):
    """Print the measurement, in the same shape for both invocations."""
    if as_json:
        print(json.dumps(
            {"candidates": len(result["hits"]),
             "untriaged": result["untriaged"], "triaged": result["triaged"],
             "swept_files": len(result["swept"]),
             "absent_keep_paths": result["absent"],
             "dead_needles": [n for _, n in result["dead"]],
             "multiline_needles": [n for _, n in result["multiline"]],
             "guards_only": guards_only,
             "guard_status": guard_status(result)}, indent=1))
        return
    print(f"{len(result['swept'])} file(s) swept; {len(result['hits'])} "
          f"footprint candidate hit(s): {len(result['untriaged'])} to triage, "
          f"{len(result['triaged'])} covered by {len(KEEP)} KEEP entries")
    for h in result["untriaged"]:
        # Lower case in --guards on purpose: there the line is information and
        # does not affect the status, and a shouted TRIAGE in a suite log
        # reads as the thing that failed.
        label = "info   " if guards_only else "TRIAGE "
        print(f"  {label}{h['path']}:{h['line']}: {h['text'][:110]}")
    if not guards_only:
        for h in result["triaged"]:
            print(f"  keep   {h['path']}:{h['line']}: {h['text'][:70]}")
    for path in result["absent"]:
        print(f"  SCOPE SHRANK: {path} names a KEEP entry but is not in "
              f"the swept set")
    for path, n in result["multiline"]:
        print(f"  MULTI-LINE NEEDLE (can never match) {path}: "
              f"{' '.join(n.split())[:60]}")
    for path, n in result["dead"]:
        print(f"  DEAD NEEDLE {path}: {' '.join(n.split())[:70]}")
    if guards_only:
        # Paths and entries are counted separately on purpose: `absent` is a
        # set of paths while KEEP is a list of entries, and printing one
        # against the other would read as "11 of 11 paths" for 11 entries
        # over 5 files.
        paths = {p for p, _, _ in KEEP}
        print(f"guards: scope {len(paths) - len(result['absent'])} of "
              f"{len(paths)} KEEP path(s) in the swept set, "
              f"{len(result['dead'])} of {len(KEEP)} needle(s) dead, "
              f"{len(result['multiline'])} multi-line; the "
              f"{len(result['untriaged'])} line(s) above are information, not "
              f"a failure")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--packages", nargs="+", default=list(PACKAGES))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="check recall against the known must-fix class")
    parser.add_argument("--guards", action="store_true",
                        help="run the real sweep but fail only on the three "
                             "guards (exit 3 scope shrank, 2 rotted needle, "
                             "0 otherwise); untriaged candidates are printed "
                             "as information")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    result = evaluate(ROOT, tuple(args.packages))
    report(result, as_json=args.json, guards_only=args.guards)
    status = guard_status(result)
    if args.guards:
        return status
    return status or (1 if result["untriaged"] else 0)


if __name__ == "__main__":
    sys.exit(main())
