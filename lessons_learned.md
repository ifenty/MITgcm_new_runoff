# Active lessons

Keep each entry short and independently useful; load detailed evidence when its trigger applies.

```markdown
- [LL-001] <General lesson; confidence and scope>
  Trigger: <When this lesson matters>
```

- [LL-001] Write documentation dispositions and docstrings from the current source each correction round, not from templates; guard docstring/rule agreement with a test. Supported (RUNOFF-001).
  Trigger: a correction round changes a rule set, a public contract or scientific behavior.
- [LL-002] A tools-disabled runtime probe cannot establish role capability; run the live probe (allowed and denied Bash witness) after every ESX upgrade and before the first dispatch of an issue. Strongly supported (four kit defects, RUNOFF-001).
  Trigger: an ESX upgrade, a settings/permission change, or the first role dispatch of an issue.
- [LL-003] Every statement a project document makes about MITgcm runtime behavior (exf, exch2, cal) cites the source routine and lines it rests on. Supported (RUNOFF-001 rounds 1-4).
  Trigger: writing or reviewing schema/contract text that describes model behavior.
- [LL-004] Do not infer an MITgcm grid's kind (single lat-lon block vs exch2 cubed-sphere/LLC) from array geometry; blank tiles and LLC lat-lon-like facets defeat every heuristic. Have the user declare it, or read it from run metadata such as data.exch2, and test with blank-tile layouts. Strongly supported (RUNOFF-009 rounds 1-4).
  Trigger: any tool or reader that needs neighbour or layout information from grid output.
- [LL-005] Before claiming that a verification experiment exercises an edited MITgcm routine, check the build link target: experiments with their own `code/` copy compile that copy, not the edited file. Run oracle commands for one experiment one at a time, because every input variant shares its build directory. Supported (RUNOFF-012).
  Trigger: citing an experiment as coverage of edited model or package code, or running oracle tests in parallel.

- [LL-006] A documentation seal binds the whole inventory, and a reviewer's `candidate_signature` is sampled at the end of its turn, so editing an inventoried document after sealing both invalidates the seal and can strand a reviewer's signature — even for a one-line wording fix the reviewer itself called non-blocking. Reverting is not symmetric: it restores the seal but strands the signature the other way. Take optional documentation fixes inside the round that seals, or route them to the issue ledger, which is not inventoried. Strongly supported (RUNOFF-004: one cosmetic edit staled a twice-confirmed report, and reverting it dropped the approval count to 1 of 2 and cost a reviewer re-affirmation turn).
  Trigger: about to edit an inventoried document after its report is sealed or a reviewer has approved.
- [LL-007] A matching-digit oracle cannot detect a misplaced target: mass is conserved and the water simply arrives in the wrong cell. Measured on cs32, a cross-facet one-cell move of a 1st-percentile target whose two cells have bitwise-equal `rA` passes `compare_results.sh` at exactly the 10 required digits. Guard placement with a cell-exact check of the applied field, not with monitor digits. Strongly supported (RUNOFF-004 review A on `b8251cd1c`; 47 of 1189 targets have an equal-area wet neighbour).
  Trigger: claiming a digit-threshold oracle covers where runoff is placed, or choosing a tolerance meant to guard target identity.
- [LL-008] A discovery glob must carry an explicit scope predicate and report its out-of-scope matches, because discovery by name pattern silently equates "matches the pattern" with "is in scope for this model". Adding `lab_sea/input.rnof_sp_const` enrolled a sparse case in a timing check that models only the dense `pkg/exf` path; it survived five focused-suite passes and two independent approvals, because the scientific suite was in nobody's assignment. A predicate is enforced; remembering to grep is not. Supported (RUNOFF-004: the scientific suite failed at final verification on exactly this; `sparse_case()` is the predicate, and it reports SKIP with the reason and owning issue).
  Trigger: writing or reviewing a test that discovers its own cases by glob, or adding or renaming a verification input directory.
