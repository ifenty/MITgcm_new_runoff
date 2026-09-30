# Lesson evidence

One detailed entry per stable ID. Include counterexamples and the cost of being wrong.

```markdown
## LESSON: <Title> [LL-001]

**Date Identified**: <UTC ISO timestamp>
**Confidence**: <tentative / supported / strongly supported>

### Lesson and applicability
<General principle and conditions>

### Evidence
<Exact command, inputs, source/environment identity and measured result>

### Limits and counterexamples
<What the evidence cannot establish>

### Recommended action
<How to apply or validate it>
```

## LESSON: Dispositions and docstrings drift when regenerated from templates [LL-001]

**Date Identified**: 2026-09-30T06:00:00Z
**Confidence**: supported

### Lesson and applicability
Across correction rounds the rule set grew (42 -> 44 -> 46 rules). Disposition reasons and function docstrings produced from fixed templates kept stating the old scope. Write reasons from the current source (the function docstring plus the rule ids it actually emits, and counts from the rule table), and keep a test that fails when a rule function's docstring omits an emitted rule id.

### Evidence
RUNOFF-001 round 2: both reviewers rejected on documentation accuracy only. Reproducer devel-loop/loop_state/diag_docstring_rules.py exited 1 (_check_structure omitted P02, S07, S09; _check_timeseries omitted D09, P02). After the round-3 rewrite and tests/runoff/test_docstring_rules.py, it exits 0 and reviewers confirmed 18 spot-checked dispositions.

### Limits and counterexamples
The docstring test is one-directional (a docstring may name delegated rules). Source-derived reasons are only as good as the docstrings they quote.

### Recommended action
Regenerate the documentation plan from source every round; never carry template text across rounds.

## LESSON: Tools-disabled probes cannot qualify role capability [LL-002]

**Date Identified**: 2026-09-30T06:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
ESX 1.5.0's probe ran tools-disabled turns and passed while every retained-role Bash call was denied (ESX-002). Three more kit defects surfaced only under real dispatch: permission_denied events crashing the adapter (ESX-001), provider overshoot failing completed turns, and review context exceeding the 131,072-byte argv limit. All four were fixed upstream (ESX-Team 1.5.1-1.5.6).

### Evidence
Bob session a7e61b17 turn 3cc0d65c: permission denials for pwd and python. Richard round-3 launches: E2BIG at a 152,783-byte argv string. The live probe added in 1.5.1 (allowed plus denied witness) passes after each upgrade (probe-152 ... probe-156).

### Limits and counterexamples
The live probe checks Bash permissions only, not other role tools or large-context dispatch.

### Recommended action
Run agent_runtime.py probe after every upgrade and settings change. Report kit defects upstream with session and event IDs.

## LESSON: Cite MITgcm source for runtime-behavior claims [LL-003]

**Date Identified**: 2026-09-30T06:00:00Z
**Confidence**: supported

### Lesson and applicability
Reviewer B found six imprecise statements about exf, exch2 and cal behavior across rounds 1-4: yearly midpoints, where exch2 prints the global map, climatology repeat, the per-update read count, first-time vs bound offsets, and exf -12 January start. Each cost a correction round.

### Evidence
RUNOFF-001 Richard B (12879e9b) must-fix lists, rounds 1-4, each citing lines such as exf_set_fld.F:184-242, w2_eeboot.F:75-93 and exf_getffieldrec.F:152-190.

### Limits and counterexamples
Source citations drift with upstream MITgcm changes; cite routine names as well as lines.

### Recommended action
Before review, check each behavior claim against the live source and record the citation in the text or the disposition.
