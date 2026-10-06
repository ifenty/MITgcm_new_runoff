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
candidates, almost all noise. With a window the same tree gives the figure
reported in the issue.

Recall is measured, not asserted
================================

``--self-test`` runs the predicate over the five sentences that were actually
must-fixed on RUNOFF-030, verbatim, and over benign lines that must not match.
A predicate for this class is only worth having if it would have caught the
class, so that check ships with it rather than being done once by hand.

What a hit means
================

A hit is a **candidate**, not a defect. Such a sentence is fine when an
antecedent nearby enumerates the sites, and fine when it is dated history. It
is a defect only when it asserts exclusivity with no antecedent, or with one
the change outgrew. Each candidate is therefore corrected or recorded in
``KEEP`` with the reason it stays true, so a later reader can tell a
deliberate keep from a miss -- the thing the first two rounds could not do.

Exit status: 0 when every candidate is in ``KEEP``, 1 when one is not (triage
it), 2 when a ``KEEP`` entry matches nothing (a rotted allowlist, which would
silently lose coverage), 3 when ``--self-test`` fails.

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
    ("esx/project_profile.md",
     "no *other* exf field's\n    range check\n    changed",
     "A: round 3 fixed this line, which was a sixth instance of the class "
     "found by this sweep; it now names both conditioned tests first."),
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


def nested_scope(root, prefix):
    """Files of a nested repository whose prose this project actually authors.

    ``MITgcm/`` is 10k upstream files. Sweeping all of them returns upstream
    comments this project neither wrote nor may edit ("Otherwise, a single
    input file contains 12 monthly mean records", in ``pkg/obcs``), which are
    noise no triage can retire. The authored set is: our own package, the
    documentation pages we write, and any file we have modified -- which is
    what keeps ``pkg/exf/exf_check_range.F`` in scope precisely because this
    issue edited it.
    """
    out = subprocess.run(["git", "status", "--porcelain"],
                          cwd=os.path.join(root, prefix),
                          stdout=subprocess.PIPE, text=True, check=True)
    modified = {line[3:].strip() for line in out.stdout.splitlines()}
    owned = ("pkg/rnf/", "doc/phys_pkgs/", "verification/lab_sea/")
    return lambda f: f in modified or f.startswith(owned)


def tracked(root, suffixes):
    """Tracked files of this repository and the authored files of nested ones."""
    out = subprocess.run(["git", "ls-files"], cwd=root,
                         stdout=subprocess.PIPE, text=True, check=True)
    names = [f for f in out.stdout.split() if f.endswith(suffixes)]
    for prefix in NESTED:
        cwd = os.path.join(root, prefix)
        if not os.path.isdir(os.path.join(cwd, ".git")):
            continue
        keep = nested_scope(root, prefix)
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


#: The five sentences actually must-fixed on RUNOFF-030, verbatim from the
#: pre-change tree (commit d95645a) and from this issue's own round-0 edit.
#: The predicate must match every one of them.
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
    "  - every other field's range check is untouched, and **nothing changes "
    "at all\n    with `useRNF` false**, the dense `runoffFile` path included.",
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
          f"class matched ({len(MUST_MATCH)} must-fixed on RUNOFF-030, "
          f"{len(MUST_MATCH_PATHED)} recall gaps found while building this); "
          f"{len(caught)} of {len(MUST_NOT_MATCH)} benign lines wrongly "
          f"matched")
    for t in missed:
        print("  MISSED:", " ".join(t.split())[:100])
    for t in caught:
        print("  FALSE POSITIVE:", " ".join(t.split())[:100])
    return 0 if not missed and not caught else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--packages", nargs="+", default=list(PACKAGES))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="check recall against the known must-fix class")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    hits = sweep(ROOT, tuple(args.packages))
    triaged, untriaged = [], []
    for name, lineno, text in hits:
        reason = kept(name, text)
        (triaged if reason else untriaged).append(
            {"path": name, "line": lineno, "text": text, "keep": reason})
    unused = [n for p, n, _ in KEEP
              if not any(h["path"] == p and kept(p, h["text"]) for h in triaged)]

    if args.json:
        print(json.dumps({"candidates": len(hits), "untriaged": untriaged,
                          "triaged": triaged, "unused_keeps": unused},
                         indent=1))
    else:
        print(f"{len(hits)} footprint candidate(s): {len(untriaged)} to "
              f"triage, {len(triaged)} deliberate keep(s)")
        for h in untriaged:
            print(f"  TRIAGE {h['path']}:{h['line']}: {h['text'][:110]}")
        for h in triaged:
            print(f"  keep   {h['path']}:{h['line']}: {h['text'][:70]}")
        for n in unused:
            print(f"  STALE KEEP matches nothing: {' '.join(n.split())[:70]}")
    if unused:
        return 2
    return 1 if untriaged else 0


if __name__ == "__main__":
    sys.exit(main())
