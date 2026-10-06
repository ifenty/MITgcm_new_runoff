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
400-character Markdown table row that happens to mention exf: measured, 101
candidates, almost all noise. With the windows below the same tree gives 72
candidate hits over 167 swept files, of which 11 are recorded keeps.

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

Usage::

    python tests/footprint_claim_sweep.py [--packages exf rnf] [--json]
    python tests/footprint_claim_sweep.py --self-test
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
#: as prose files do -- ``exf_check_range.F``'s own banner is one.
SUFFIXES = (".md", ".rst", ".F", ".h")

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
    """Tracked files of this repository and the authored files of nested ones."""
    out = subprocess.run(["git", "ls-files"], cwd=root,
                         stdout=subprocess.PIPE, text=True, check=True)
    names = [f for f in out.stdout.split() if f.endswith(suffixes)]
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--packages", nargs="+", default=list(PACKAGES))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="check recall against the known must-fix class")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    swept = set(tracked(ROOT, SUFFIXES))
    hits = sweep(ROOT, tuple(args.packages))
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

    if args.json:
        print(json.dumps({"candidates": len(hits), "untriaged": untriaged,
                          "triaged": triaged, "swept_files": len(swept),
                          "absent_keep_paths": absent,
                          "dead_needles": [n for _, n in dead],
                          "multiline_needles": [n for _, n in multiline]},
                         indent=1))
    else:
        print(f"{len(swept)} file(s) swept; {len(hits)} footprint candidate "
              f"hit(s): {len(untriaged)} to triage, {len(triaged)} covered by "
              f"{len(KEEP)} KEEP entries")
        for h in untriaged:
            print(f"  TRIAGE {h['path']}:{h['line']}: {h['text'][:110]}")
        for h in triaged:
            print(f"  keep   {h['path']}:{h['line']}: {h['text'][:70]}")
        for path in absent:
            print(f"  SCOPE SHRANK: {path} names a KEEP entry but is not in "
                  f"the swept set")
        for path, n in multiline:
            print(f"  MULTI-LINE NEEDLE (can never match) {path}: "
                  f"{' '.join(n.split())[:60]}")
        for path, n in dead:
            print(f"  DEAD NEEDLE {path}: {' '.join(n.split())[:70]}")
    if absent:
        return 3
    if multiline:
        return 2
    if dead:
        return 2
    return 1 if untriaged else 0


if __name__ == "__main__":
    sys.exit(main())
