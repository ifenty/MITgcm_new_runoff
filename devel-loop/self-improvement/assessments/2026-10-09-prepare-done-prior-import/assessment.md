# Assessment: prepare-done drafts a closeout the strict gate refuses after a re-prepared iteration

Found 2026-10-09 closing RUNOFF-008 (iteration re-prepared after an owner session restart, so the
closeout spans two iteration timestamps: 04:44:55 for round 0 and 15:32:16 for correction round 1).

Gate refusals met in sequence, each after a 2-3 minute `--closeout-doctor` or `rebind-receipt` call:
1. `agent_continuity.bob must list exactly the dispatch_ids already in subagents.bob`. The draft carried only `replacements`.
2. `candidate reference is required`. The draft had no `candidate` or `map_delta`, although the final packet carried both.
3. `ad98e39fd4b872093: review's iteration_timestamp does not match the active issue`. prepare-done imported the previous iteration's Richard review (`ea2b60d5…`) into `subagents.richard`. The gate then refuses it as a current approval, and the supersession route requires the replacement's verdict to be a plain APPROVE (Richard returned APPROVE_WITH_FIXES with an empty must-fix).
4. `documentation evidence reference is required`. The draft's `maintenance` lacked `documentation` and `orientation`, which the packet carried.

Resolution used: copy `candidate`, `map_delta` and `maintenance` from `packets/runoff-008-final.json`; drop
the prior-iteration review from `subagents.richard`, since it stays in the prior closeout; then list the identities.
About 15 minutes of serial refusal, consistent with the RUNOFF-008 round-0 carry-forward ("Closeout
bookkeeping revealed its contract one rejection at a time").
