# Assessment: three framework findings from RUNOFF-013 (2026-10-05)

RUNOFF-013 produced three framework findings across two correction rounds. They
are recorded together because they share one shape: each is a mechanism that
reports success while covering less than a reader would take it to cover.

## 1. `--check-start` cannot pass in a correction round (TEAM-LOOPGATE-CHECKSTART-CORRECTION-ROUND-001)

- **What happened:** the round-1 brief told the implementer to run
  `loop_gate.py --check-start --issue RUNOFF-013 --agent bob`. Those flags do
  not exist. The implementer measured that, established that `--check-start` is
  Arch's gate over Arch's own orientation and not a per-agent permission check,
  found that it had already passed **on time** for the iteration (receipt
  `421b6104…`, validated 1.4 s after the start record and before any edit), and
  proceeded on that receipt rather than burning the round.
- **The defect behind it:** Arch then reproduced the full chain. `--check-start`
  compares the *prepare-time* orientation receipt against the working tree, so
  once any work has legitimately changed an oriented target — i.e. in every
  correction round — it can never pass again. The remedy the gate itself prints
  ("navigate again") does not clear it: a fresh orientation receipt was accepted
  (`945ed7db…`) and the next `--check-start` reported the identical six changes
  against the old receipt. That leaves `--late-reason`, which would overwrite an
  honest on-time receipt with one asserting the gate was skipped, or `--prepare`,
  which destroys the round-0 and review history. `rebind-receipt` does not apply;
  it re-points a *final verification* receipt.
- **Why it mattered:** the false field would be "late" — precisely the signal the
  gate exists to protect. A conscientious agent stalls and escalates, costing a
  round; a careless one silently degrades every later audit of whether
  authorization preceded work.
- **Credit:** the implementer refused both escape hatches on record-integrity
  grounds and referred the matter up. That was the right call and it is the
  reason this is a filed finding rather than a corrupted receipt.
- **Cost:** one agent's diagnosis plus one Arch re-navigation that could not
  have worked. The underlying brief error cost nothing, because the agent
  verified the interface instead of trusting it.
- **Classification:** workflow integrity, Medium.

## 2. `navigate --reuse-args` rejects its own declared map (TEAM-DOCCONTRACT-NAVIGATE-REUSE-MAP-001)

- **What happened:** `--reuse-args` tests changed targets for membership in
  `targets` and `documents`, but an orientation's map lives in a third field,
  `map`. So when the changed target *is* the receipt's own `--map` section, the
  tool reports it as outside its own declared scope. Measured **four times on
  this issue, by three different agents and across two rounds**: by Arch in
  round 1 (`docs/code_map.md#pipeline`), by review B in both rounds 1 and 2
  (`#pipeline`), and by the implementer in round 2
  (`docs/code_map.md#verification-routes`) — each time clearing on a full
  `navigate` with the identical arguments the receipt already held. The
  complementary case is confirmed too: in correction round 3 the changed target
  was a declared **document** (`devel-loop/documentation_contract.md`) rather
  than the declared map, and `--reuse-args` accepted it, so the defect is
  specific to the `map` field being omitted from the membership set.
- **Why it mattered, mildly:** the refusal is loud and the workaround mechanical,
  so the risk is not a wrong result. It is that an agent retyping four
  `--target` arguments by hand may drop one, which converts an ergonomic
  nuisance into a real narrowing of what was read. The code map is also the
  document most likely to change on an issue that touches it, so this fires on
  the common case.
- **Classification:** tool ergonomics, **Medium** — raised from Low in
  correction round 3 on the strength of four independent reproductions across
  three agents, which is what the ledger entry now records.

## 3. The stale sweep's scope is undeclared (TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001)

- **What happened:** `doc_inventory.paths` selects 355 paths here, and **no
  project record document is among them** — eleven tracked files plus the whole
  assessments tree, so none receives a stale sweep or a disposition row. The two
  first noticed were `open_issues.md` and `long_term_goals.md`; read them as the
  instances, not the boundary (see the fourth bullet).
  `open_issues.md` — the ledger the
  loop reads to choose work — was modified in both rounds and appears in
  neither sealed report's targets.
- **How it was found:** the implementer hit the `open_issues.md` half while
  fixing a different stale statement (a superseded "76 statements" figure that
  no sweep could see) and reported it without filing it. Review B then measured
  the inventory boundary directly, confirmed the gap was recorded in none of the
  three places it should be, and added the `long_term_goals.md` half. When the
  disclosure line was finally written, the by-hand check it prescribes
  immediately found a live dead citation at `open_issues.md:74`.
- **Why it mattered:** this is the companion of
  TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001 and the second blind spot of the
  same sweep found on the same issue — but sharper, because no figures row can
  help. A document outside the inventory is not swept at all, so there is no
  wording that would have caught it.
- **And the first fix reproduced the failure one level up.** The disclosure as
  first written named the two files that had been noticed. Review B then
  measured the whole boundary and found **eleven** project record documents
  outside the inventory, plus the assessments tree — including
  `lessons_learned.md`, whose lessons are quoted in every brief, and,
  recursively, the ledger the framework issue is filed in. Running the issue's
  own figures table by hand over all of them gave **8 hits in 5 files**, of
  which only `open_issues.md` was covered by the check the disclosure
  prescribed; `closed_issues.md:350` was still carrying, in the present tense,
  the same two stale tokens that had been a must-fix in the profile two rounds
  earlier. Arch reproduced the eleven-file count independently and widened all
  three records to state the class. **A confident wrong boundary is worse than
  an acknowledged unknown one**, and that is now the issue's acceptance
  criterion — which the round-3 wording strengthens to require the boundary be
  enumerated mechanically rather than listed by hand.
- **A hit count over these files measures the disclosure as much as the gap.**
  Re-measured at the round-3 seal: 7 hits in 5 files over the tracked record
  documents and 8 in 6 with this assessment included, of which **four are the
  ledger and this file quoting the superseded tokens as their own subject
  matter**, three are labelled history and one is the corrected
  `closed_issues.md:350`. The total moved twice inside the round as these
  paragraphs were rewritten, so only a mechanical enumeration of the boundary is
  a stable measure — which is why the acceptance criterion now demands one.
- **Classification:** coverage gap, Medium.

## The pattern across all three, and the issue that produced them

RUNOFF-013 took **fifteen must-fix items across three review cycles and two
independent reviewers, and not one defect in the tendency terms.** Every item
was a false or incomplete statement about correct code, an instrument that
could not run, or a guard nobody had fired. (Counted from the hook-captured
reviewer footers in correction round 3: 4 + 5 after round 0, 3 + 2 after round
1, 1 + 0 after round 2. The earlier wording here said "fourteen ... across two
rounds", which was right when written and was superseded by review B's single
round-2 item — the one that caused this round. A figure about the issue's own
review history goes stale while the issue is still open, which is a reason to
re-derive it at closure rather than carry it.) The two items that were not records
— `BUILD_SOURCES` omitting three compiled paths, and figures rows that fired on
nothing — were both inside the machinery built to catch description errors.

Two findings of the round sharpen that further:

- Review A established by mutation that the issue's subject had been shipping
  green: no configured command executed `RNF_TENDENCY_APPLY_T` or `_S` at all,
  and a wrong `X_ref` or a sign flip would have survived every one of the 57
  scientific commands. An enrolment whose command cannot run on a clean tree is
  decorative, and the smell was a suppression flag whose stated purpose was to
  tolerate a missing prerequisite.
- The implementer's `BUILD_SOURCES` fix nearly repeated the shape at one level
  down: `os.walk` of a plain file yields nothing, so adding `pkg_depend` as a
  path would have looked like coverage and measured nothing. It was caught by
  measuring the predicate flip rather than by inspecting the list.
- Review A then found a **third** instance of the same class in the same
  function, still live: a `BUILD_SOURCES` entry that does not *exist*
  contributes `delta 0.000` and raises nothing. Review B quantified why that
  matters — `MITgcm/pkg/rnf` is the entry that currently *sets* the maximum, so
  losing it to a rename would move the staleness reference back **117 326 s**
  (1 d 8 h 35 m) and silently stop the LL-011 guard from guarding the one
  directory under development, while still reporting `reused`. Both reviewers
  judged it optional because nothing is wrong today and the trigger is a
  deliberate future edit — but the trigger is scheduled: this package is to be
  rebased on upstream MITgcm before the PR, which is exactly when a path gets
  renamed. Carried as a hardening with that figure attached, because the figure
  is what makes the risk legible.

Three instances of one class in one function, found by three different agents,
is the durable finding here: **a listed entry that looks like coverage and
measures nothing.** The general defence is to measure the mechanism's output
change when the entry is perturbed, never to inspect the list.

**Related:** TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001 and
TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001 (RUNOFF-005) — same tool family,
and like these, each surfaced by a reviewer re-measuring something that already
looked settled.
