# Assessment: final_verification.py run did not reuse a matching scientific execution

**Date**: 2026-10-11
**Issue**: RUNOFF-046 closeout
**UUID**: TEAM-FINALVERIFY-FINGERPRINT-REUSE-001

## Observation

`final_verification.py check --review <packet>` printed `scientific_fingerprint:
8572c195d2331bf1cae24b4c4c6f66843c8d3ff5c4546b682498bcb4ea9331bf` for the final
packet built after a documentation-only reseal round (candidate `bc477f32...`),
exactly matching the fingerprint recorded in an already-passing scientific
execution from ~2 hours earlier (same value, confirmed by direct read of
`devel-loop/loop_state/verification/49a0d8a6...json`'s `identity.scientific_fingerprint`
equivalent field before the second run started).

`final_verification.py run --review <packet> --owner arch` (no `--fresh`) was
expected, per `run()`'s own docstring ("Serialize final runs and rebind
unchanged execution to current acceptance"), to take the `check_receipt`/
`_reissue` reuse path and return near-instantly. Instead it re-executed the
full 71-command scientific suite from scratch (`experiment_compile.sh
global_ocean.cs32x15` observed running via `ps aux` within 15 seconds of
start), taking a further ~6760 seconds (~1h53m), and finishing with a NEW,
independently-executed EXECUTED PASS at the same signature.

## Not yet root-caused

Did not instrument `run()`'s two `except (ValueError, OSError, KeyError,
TypeError): pass` branches (`check_receipt` attempt, then `_reissue` attempt)
to capture which exception each raised. Candidates not yet distinguished:
- `current.json` (the reuse index) may not have existed yet, or may have
  pointed at a receipt from a different, non-matching `review_signature`
  component (not just `scientific_fingerprint`) at the time of this run.
- `check_receipt`'s own `require(record.get('identity') == ready(root, done,
  owner), ...)` may have failed on a field other than `scientific_fingerprint`
  (e.g. `review_signature`, which legitimately differs run-to-run as closeout
  fields are filled in).

Deliberately did not debug further in the moment, to avoid risking additional
process errors during an already-long closeout sequence (see RUNOFF-046's
closed_issues.md entry and LL-020 for the `created_at` bug found and fixed in
the same closeout). The suite re-ran correctly and produced a valid result;
only wall-clock time was lost, not correctness.

## Proposed next step

Reproduce on a future issue with available slack: run `final_verification.py
run` twice in a row with no tree changes between them (first with `--fresh`,
second without), and add a temporary diagnostic print inside `run()`'s two
`except` blocks to capture the actual exception raised, before removing it.
