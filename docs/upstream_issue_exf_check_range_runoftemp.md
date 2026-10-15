# Draft upstream issue: EXF_CHECK_RANGE tests `runoff` instead of `runoftemp`

Draft for https://github.com/MITgcm/MITgcm/issues. **Not posted.** Posting to MITgcm/MITgcm needs the
owner's go-ahead (see esx/project_profile.md). Local tracking entry: RUNOFF-037 in open_issues.md.

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
`master`. **I have not run a reproduction** (a build with `ALLOW_RUNOFTEMP` and a `runoftemp` above 36 degC
that should abort and does not). A reproduction would need that build, e.g. a `lab_sea` variant with
`ALLOW_RUNOFTEMP` defined and a `runoftempfile` holding a temperature above 36. Run that before posting if the
maintainers will want a test.

The one-line fix has not been built or tested upstream-side either; locally the tracking entry (RUNOFF-037)
records the intended acceptance: a `runoftemp` above 36 degC is refused with a message naming the temperature
and its value, and a volume flux of any magnitude is not reported as a temperature error.
