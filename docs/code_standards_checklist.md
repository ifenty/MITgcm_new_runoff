# Coding standards checklist for the new Fortran (RUNOFF-027)

This list is for the reviewer. It covers the new Fortran of `pkg/rnf` and the
lines that the branch adds to existing MITgcm files (the hooks). One script
checks most items: `tests/runoff/test_fortran_standards.py`. The pytest suite
of `tests/runoff` runs it. A result is "pass" only when the script or a
measurement shows it. A person or a tool that we do not have must do the
other items. Those items are "open", with the reason.

Run the lint alone:

```
python tests/runoff/test_fortran_standards.py     # one line per finding
python -m pytest -q tests/runoff/test_fortran_standards.py
```

## Scope

- All files of `MITgcm/pkg/rnf`: 16 `.F` files, 3 `.h` files and `README.md`.
- The lines that the branch adds to 15 existing files (`model/src` 9 files,
  `model/inc/PARAMS.h`, `pkg/exf` 3 files, `pkg/longstep` 1 file,
  `pkg/ptracers` 1 file). The lint takes them from `git diff` of the merge
  base of `upstream/master` and `HEAD` against the working tree. If
  `upstream/master` is not reachable, the hook test skips and says so. A skip
  is not a pass.
- Out of scope: the TAF list files (`rnf_ad_diff.list`, `rnf_ad.flow`). They
  need a TAF build, which we do not have here.

## Rules of the lint

| Rule | What it checks |
| --- | --- |
| a | No tab character in any file of the scope. |
| b | No line over 72 columns in `.F` and `.h`. A statement line is a hard failure, because the compiler cuts columns 73 to 80 without a message. A comment line or a `#` line over 72 columns breaks the MITgcm style. The 80-column ruler line before each routine is the one exception. The 72-column limit for comment lines and `#` lines is a house style. Fortran requires it only for code. |
| c | Fixed-form layout. A comment line starts with `C` in column 1. Columns 1 to 5 of a code line hold only a numeric label. The continuation mark is `&`. The marks `I`, `O` and `U` belong only in the argument list of a SUBROUTINE or CALL. No inline `!` comment. |
| d | Each SUBROUTINE of `pkg/rnf` has `myThid` as the last argument. It has a protex header: `CBOP`, `C !ROUTINE:` with its own name, `C !INTERFACE:` and `CEOP`. |
| e | Include order in each routine. `SIZE.h` and `EEPARAMS.h` come first (either order). `PARAMS.h` comes next. The other model headers (`GRID.h`, `DYNVARS.h`, `FFIELDS.h`) come next. `RNF_SIZE.h` comes before `RNF.h`, and both come after the model headers. Only `*_OPTIONS.h` headers come before the first routine. |
| f | No `REAL` or `DOUBLE PRECISION` declaration, no bare real literal (`0.5`) and no bare `D` or `E` exponent in code. Constants use the form `1. _d 0`. Text in quotes, comments and `FORMAT` statements is not code. |
| g | A `STOP` has one form only. A `CALL PRINT_ERROR` comes earlier in the routine. `CALL ALL_PROC_DIE( 0 )` (or `( myThid )`) is the statement just before. The `STOP` text is `'ABNORMAL END: S/R NAME'` with the name of the routine. A `STOP` in a logical IF also fails. This rule is stricter than upstream: `pkg/shelfice` has a `STOP` without `PRINT_ERROR`. |
| h | Each `#endif`, `#else` and `#elif` has a `/* ... */` comment that names a macro of its `#if`. In a package `.F` file, line 1 is `#include "RNF_OPTIONS.h"`, and each routine has an `#ifdef ALLOW_RNF` guard (or an `#if` that tests `defined ALLOW_RNF`). |
| i | No tracker id (`RUNOFF-` and a digit, in any case, with blanks allowed around the hyphen), and no text `github.com/ifenty` in any case. Such text means nothing to an upstream reader. |

The rule for item e comes from `pkg/exf` and `pkg/shelfice`. The test
`test_include_rule_holds_for_the_neighbour_packages` checks that both packages
follow the part of the rule that orders `SIZE.h`, `EEPARAMS.h` and `PARAMS.h`.
`pkg/exf` puts `EEPARAMS.h` first. `pkg/shelfice` puts `SIZE.h` first. So the
rule allows both orders.

The rules are stricter than the neighbour packages. The same lint finds 1474
items in `pkg/exf` and `pkg/shelfice` (mostly rules h, c, f and b). This is
not a defect of those packages. The rules apply only to the new code.

## Named exceptions

The table `EXCEPTIONS` in the test file holds them. A test fails if an
exception matches nothing. There are three.

| Rule | Place | Reason |
| --- | --- | --- |
| f | `pkg/rnf/rnf_nc_utils.F`, `Real*8 tmpVal(1)` | `NF_GET_VAR1_DOUBLE` writes a `REAL*8` argument, whatever `_RL` is. A single-precision build has `_RL` as `REAL*4`. |
| f | `pkg/exf/exf_check_range.F`, two lines with `.GT. 1.E-6` | The constant is the upstream threshold. The hook only changed its indentation. The form `1. _d -6` would change the single-precision value of the bound. |
| g | `pkg/rnf/rnf_fields_load.F`, `STOP 'ABNORMAL END: S/R RNF_FIELDS_LOAD'` | The STOP is in `RNF_FIELDS_BUILD`, the internal part of `RNF_FIELDS_LOAD`. All its messages have the prefix `RNF_FIELDS_LOAD`, and `tests/rnf/restart_check.py` reads this exact text. |

## Checklist

| Item of the issue | How it is checked | Result | Evidence |
| --- | --- | --- | --- |
| Fixed form and 72 columns | Rules b and c | pass | 0 findings. Before the sweep there were 8 comment lines over 72 columns. The 22 other long lines were rulers. All were comments, so nothing was cut. |
| CPP guards | Rule h | pass | 0 findings. The sweep added 22 comments to `#endif` lines in `pkg/rnf` and 13 in the hook files. It also added an `#ifdef ALLOW_RNF` guard to `RNF_DIAGNOSTICS_INIT`. |
| `_RL` and `_RS` for real arithmetic | Rule f | pass | 0 findings, with the exceptions above. |
| Choice of `_RL` or `_RS` for each variable | manual | open | The lint cannot judge whether a field should be `_RS`. A person must review it. |
| `myThid` as the last argument | Rule d | pass | 0 findings. |
| `bi,bj` tile loops and thread safety (`_BEGIN_MASTER`, `myByLo`) | manual | open | The lint does not parse the loops. A person must check that each routine works on its own tile and that master-only code is inside `_BEGIN_MASTER`. |
| Order of the header includes | Rule e | pass | 0 findings. |
| No tabs | Rule a | pass | 0 findings. |
| Comment style, protex headers | Rules c and d | pass | 0 findings. |
| STOP through the ERROR handling | Rule g | pass | 0 findings, with one exception above. 15 STOP statements in the package follow the pattern. |
| Tracker ids and repository URL in the scope | Rule i | pass | Before the sweep: 50 ids in 14 files of `pkg/rnf`, one URL in `README.md` and none in the hooks. After: 0. One run-time message changed (see below). |
| Tracker ids and repository URL in other files of the pull request | Rule i, test marked `xfail` | open | `doc/phys_pkgs/rnf.rst` has the URL (line 207). Five lines in `utils/python/MITgcmutils/MITgcmutils/runoff` (`check.py` 2, `schema.py` 1, `targets.py` 2) have ids. These files are outside this issue. The strict `xfail` test fails when someone cleans them. Then remove its marker. The `xfail` stands until an issue exists for these out-of-scope files. |
| Pointers to files that the pull request does not hold | manual | open | 44 lines say "package design" and 21 lines name `docs/` or `tests/` files of the development repository (measured in `pkg/rnf` and `doc/phys_pkgs/rnf.rst`). They are not tracker ids, so rule i does not find them. Richard B recommends that we remove them or make them self-contained before an upstream pull request. |
| Hook edits in existing MITgcm files | All rules on the added lines | pass, with a condition | 0 findings on the added lines, measured on a clone that has the `upstream` remote. The sweep changed 13 hook lines in 11 files (comments on `#endif` and `#else` only). On a clone without the `upstream` remote, the hook part is **not run**, not pass. The test then prints a warning (`HOOK LINT NOT RUN`) in the warnings summary of `pytest -q` and skips. |
| TAF store directives | manual | open | Needs a TAF build. We do not have one. |
| `rnf_ad_diff.list` and `rnf_ad.flow` | manual | open | Out of scope. They need a TAF build. |
| Carry-forward of RUNOFF-010 review B: the state of a field of the previous step needs store directives or a recomputation | manual | open | Review B named this for the adjoint. The package keeps the fields `RNF_curIter` and `RNF_apIter` between steps. A TAF build must show whether the adjoint needs `STORE` directives or a recomputation. No such build exists. |
| MITgcm contribution checklist outside the code (manual chapter, `pkg_groups`, `pkg_depend`, verification README, `testreport` run) | manual | open | The files `doc/phys_pkgs/rnf.rst` and `pkg/pkg_depend` exist in the branch. The rest needs a person. The upstream `testreport` run is in the verification matrix row "Upstream contribution". |

## What the sweep changed

- Comments only, except two kinds of line: one run-time message and
  `README.md`. The message in `rnf_check.F` lost the text `; RUNOFF-045`. No
  test reads that text. The other change is the `#ifdef ALLOW_RNF` guard in
  `RNF_DIAGNOSTICS_INIT`. It does not change a build that has ALLOW_RNF.
- `git -C MITgcm diff -w -U0` shows the non-comment lines that changed. They
  are the message line, the README text and the new guard.
- A rebuild of `lab_sea` with these sources passes the oracle (11 matching
  digits, 10 required). The cases `evprrn_runoff_temp` and `evprrn_unset` of
  `tests/rnf/refusal_check.py` pass on a build without `ALLOW_ATM_TEMP`.
