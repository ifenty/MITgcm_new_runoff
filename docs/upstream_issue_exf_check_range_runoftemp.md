# Draft upstream issue: EXF_CHECK_RANGE tests `runoff` instead of `runoftemp`

Draft for https://github.com/MITgcm/MITgcm/issues. **Not posted.** Posting to MITgcm/MITgcm needs the
owner's go-ahead (see esx/project_profile.md). Local tracking entry: RUNOFF-037 in open_issues.md.
The fork's `new_runoff` branch carries the fix (RUNOFF-037, test `tests/rnf/runoftemp_range_check.py`);
the code quoted below is upstream `master`, not the fork.

---

**Title:** pkg/exf: EXF_CHECK_RANGE upper bound of the runoff-temperature check tests `runoff`, not `runoftemp`

## Summary

In `pkg/exf/exf_check_range.F`, the `ALLOW_RUNOFTEMP` block that is meant to check the runoff temperature
compares the wrong array in the upper bound, and prints the wrong array in its warning:

```fortran
# ifdef ALLOW_RUNOFTEMP
C     Runoff temperature.
          IF ( (runoftemp(i,j,bi,bj) .LT. -2. .OR.
     &         runoff(i,j,bi,bj) .GT. 36 ) .AND.        <-- should be runoftemp
     &         maskC(i,j,ks,bi,bj) .NE. 0. ) THEN
           WRITE(standardMessageUnit,'(A,5(1X,I6),2X,D22.15)')
     &          'EXF WARNING: runoftemp out of range at bi,bj,i,j,it= ',
     &          bi, bj, i, j, myIter, runoff(i,j,bi,bj)   <-- should be runoftemp
           exferr = 1
          ENDIF
# endif /* ALLOW_RUNOFTEMP */
```

The lower bound (`runoftemp .LT. -2.`) is correct. Present on current `master`; `git log -S` places it in the
original commit that added `ALLOW_RUNOFTEMP` (e603dbf00, 2013-04-23, "adding ALLOW_RUNOFTEMP for specifying
temperature of runoff").

## Consequence

Two defects in opposite directions, both only when `ALLOW_RUNOFTEMP` is defined and `useExfCheckRange` is true
(its default):

1. A runoff temperature above 36 degC is **not** caught. The array tested is a volume flux in m/s, which
   never gets near 36.
2. A runoff *volume flux* above 36 m/s **would** be reported as "runoftemp out of range" and abort the run
   (`STOP 'ABNORMAL END: S/R EXF_CHECK_RANGE'`), with the flux printed as if it were the temperature.

Neither is likely in a realistic run, which is probably why it has survived. It only affects the sanity check,
not the model state.

## Proposed fix

```diff
-     &         runoff(i,j,bi,bj) .GT. 36 ) .AND.
+     &         runoftemp(i,j,bi,bj) .GT. 36 ) .AND.
 ...
-     &          bi, bj, i, j, myIter, runoff(i,j,bi,bj)
+     &          bi, bj, i, j, myIter, runoftemp(i,j,bi,bj)
```

## How it was found / status of evidence

Found by reading the code while working on a separate runoff package; confirmed by reading the file on
`master`. The defect has since been reproduced and the fix tested in the fork (RUNOFF-037) with
`tests/rnf/runoftemp_range_check.py`, a `lab_sea` build with `ALLOW_RUNOFTEMP` defined, on the dense
`runoffFile` + `runoftempfile` path and on the sparse `pkg/rnf` path:

- **Fixed build:** 12 of 12 cases pass, serial and `-mpi 2`. A `runoftemp` of 36.5, 100 or -3 degC at a wet cell
  stops the run with `ABNORMAL END: S/R EXF_CHECK_RANGE` and a message naming `runoftemp` and its value; exactly
  36 and -2 (dense), 35.9 and -2 (sparse) and 100 degC at a dry cell are accepted; a volume flux of 40 m/s with
  10 degC is refused by the runoff-volume check and is not reported as a temperature error.
- **Unfixed build** (the fix reversed textually): it fails exactly the 7 expected cases. 36.5 and 100 degC on both
  paths are not caught; the 40 m/s flux is reported as a temperature error; and -3 degC is refused but the message
  prints the runoff (4.0e-07 dense, 6.4e-07 sparse) instead of the temperature.
- The reviewer's own run agreed: 36.01 degC dense, a flux of 100 with 10 degC, and 20 degC behaved as required.
  Caveat: a dense `runoftemp` file is float32, so 36.01 is stored as 36.0099983, and the test's 1e-9 comparison of
  the printed value is an artifact of the chosen test inputs (36.5, 100 and -3 are exact in float32), not a
  property of the fix. On the sparse path `(m*T)/m` for T = 36 lands one ulp above 36 and is refused, so the
  exact boundary is only asserted on the dense path.

Not run against upstream `master` itself, only against the fork.
