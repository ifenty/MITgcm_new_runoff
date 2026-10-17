# Project milestones

Append dated, evidence-linked milestones when warranted. Keep any resume block limited to stable navigation links.

## 2026-10-08 — the footprint sweep scans .py and is enrolled (RUNOFF-042)

First milestone that is about the project's own guards rather than about
`pkg/rnf`. `tests/footprint_claim_sweep.py` now scans `.py`, excludes its own
file and the vendored `ESX-team-local/backups/`, carries 38 `KEEP` entries over
13 paths, and is **executed** for the first time: `--self-test` and a new
`--guards` mode are in the `structural` suite, and the sweep has a route in
`docs/code_map.md`, which it never had.

Evidence: `caa6c92`; both reviewers approving on candidate `31442c39`; final
scientific qualification `EXECUTED PASS`, receipt `74616934`, 62 commands,
exit 0, stable, 6467 s, with `refusal_check.py` at 69 of 69.

What it actually bought, and what it cost: the issue's filing premise was
false — the sweep could never have seen the RUNOFF-040 claim that prompted it —
so the change stands on one genuinely stale claim it did find, in
`tests/rnf/refusal_check.py`. Correcting that claim reproduced the same error
class and pinned it behind a `KEEP` entry, caught only by two reviewers working
independently; the durable fix is `tests/esx/test_instrument_claims.py`, which
asserts the claim against what `cases()` returns instead of restating it in
prose. Recorded as **LL-019**.
