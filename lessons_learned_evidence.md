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

## LESSON: Declare the grid kind; do not infer it from geometry [LL-004]

**Date Identified**: 2026-10-02T00:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
The target-table builder first chose neighbour connectivity automatically from grid geometry. Each heuristic failed silently on some layout: cs32 with blank tiles hiding every mismatched seam (192 links lost), LLC-like stacked lat-lon facets (seam links lost), blank tiles at the wrap column, polar rows under corner matching. Geometry cannot distinguish an exch2 mosaic with blank tiles from a lat-lon block.

### Evidence
RUNOFF-009 Richard B (9e7ef5a1) must-fix lists, rounds 1-4, with verification records 2442fb8f, a543755b, 0682223540 and a21e7c51; diagnosis checkpoints diagnosis-RUNOFF-009-r2.json and -r4.json. After the design changed to a declared kind (latlon or exch2, default exch2 with data.exch2) with exact-or-refuse checks, round 5 was approved by both reviewers.

### Limits and counterexamples
Three documented non-detections remain for constructed grids (lone triangle, apex that is another cell's SW corner, polar cells wider than about 45 degrees). No LLC grid output was available for a direct test.

### Recommended action
RUNOFF-004 (the Fortran reader) must take tile placement from exch2/mdsio variables, never from geometry. Test any layout logic with blank tiles.

## LESSON: Check build link targets before claiming coverage; serialize oracle runs per experiment [LL-005]

**Date Identified**: 2026-10-03T07:00:00Z
**Confidence**: supported

### Lesson and applicability
A verification experiment can carry its own copy of a model or package routine in `code/`. genmake2 then links that copy into the build, and the edited routine in `model/src` or `pkg/` is never compiled there. Coverage claims must rest on the build's link target, not on the package being "compiled and used". Separately, all input variants of one experiment share its build directory, so concurrent oracle runs of the same experiment overwrite each other's build.

### Evidence
RUNOFF-012:
- **The false claim:** Richard B (round 0) proposed `tutorial_global_oce_latlon` as compiled-out ptracers coverage. Bob found that `build_esx/ptracers_apply_forcing.F` links to `../code/ptracers_apply_forcing.F`. Both reviewers confirmed this in round 1, and `tutorial_advection_in_gyre` (linked to `pkg/ptracers`) replaced it.
- **Scope of the trap:** a search of every `verification/*/code*` directory found five experiments with local copies of hooked routines.
- **The build collision:** Richard A (round 0) discarded his first evidence after running the focused suite and `lab_sea input -mpi 2` at the same time.

### Limits and counterexamples
A local copy that contains the same hook would be covered. The check is per routine and per experiment.

### Recommended action
- Cite coverage with the link target: `ls -l build/<file>.F`.
- Keep a list of experiments with local copies in docs/verification_matrix.md.
- Run oracle commands for a given experiment sequentially.

