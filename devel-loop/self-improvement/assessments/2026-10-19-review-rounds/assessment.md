# Assessment: correction rounds caused by wording and checker holes

**Date**: 2026-10-19
**Issue**: RUNOFF-024, RUNOFF-027
**UUID**: TEAM-REVIEW-ROUNDS-PREFLIGHT-001

## Observation

RUNOFF-024 needed four correction rounds. Two of them (Richard A, rounds 1 and 2) rejected only because an added sentence in the
documentation rows was longer than 25 words. Each wording fix changed the sealed documentation report, so both approvals became stale
and both Richards had to review again.

RUNOFF-027 needed one correction round. Richard B wrote three mutants that the author of the new lint had not written (a case variant of an
id, a `STOP` inside an `IF`, a quiet skip) and all three passed the lint.

## Cost

About 40 minutes in RUNOFF-024 and 15 minutes in RUNOFF-027 (see the retrospectives of the two issues).
