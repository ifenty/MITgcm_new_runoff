# Standing loop rules

Project-owned brief rules promoted from measured retrospectives. `--next` prints
these rules and recent carry-forward instructions. `--check-retro` refuses repeated
standing rules. Maximum: 25 active bullets.

When a rule occurs in two of the last three retrospectives, promote it here or
retire it with a reason. Keep each rule short and actionable. Once a gate enforces
a rule, remove its active bullet and name that gate under Retired.

## Rules

- Give independent reviewers distinct correctness questions; preserve scientific acceptance even for small textual changes.

## Retired

Structural checks before paid review: enforced by agent_runtime.review_context.
Successful start before closeout: enforced by loop_gate.check_done.
