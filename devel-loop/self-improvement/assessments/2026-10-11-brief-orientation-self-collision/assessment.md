# Assessment: brief.build false-refuses on its own reconstructed orientation command

**Date**: 2026-10-11
**Issue**: RUNOFF-039 preparation
**UUID**: TEAM-BRIEF-ORIENTATION-SELFCOLLISION-001

## Mechanism

`brief.build` renders Arch's orientation receipt as a "re-run this" line:
`'# Own orientation\n' + shlex.join(command) + ...` (`brief.py:342`), where
`command` is reconstructed as `doc_contract.py navigate --issue ... --target
<t1> --target <t2> ... --doc ... --use ...` from the orientation's own stored
targets (`brief.py:311-315`).

`interface_errors`'s `COMMAND_PATTERN` (`r'tools/esx/([a-z_]+\.py)((?:(?!\.py)
[^\n\`"\'])*)'`) matches `tools/esx/<script>.py` anywhere in the full brief
text and captures everything up to the next backtick/quote/newline as `rest`,
then checks every `--flag` token found in `rest` against that script's own
`--help` output.

When an orientation target is itself under `tools/esx/`, the regex matches
that target's own script name and then swallows every flag that follows it in
the reconstructed command line -- a second `--target`, `--doc`, or `--use` --
misattributing them to whichever `tools/esx/*.py` script happened to be named
last among the orientation's own targets. The brief is refused for a flag no
one actually wrote as an instruction to the dispatched agent.

## Reproduced twice, two different victims

1. Orientation `--target tools/esx/brief.py::build --target
   tools/esx/brief.py::<module>` -> refusal `brief.py does not accept
   --target` (the second `--target` was swallowed into the first match's
   `rest`).
2. Orientation `--target tools/esx/project.py::source_signature` (one target)
   plus `--doc docs/code_map.md --use '...'` -> refusal `project.py does not
   accept --doc; project.py does not accept --use`.

Confirms the defect is general to any `tools/esx/*.py` orientation target, not
specific to `brief.py` as a target.

## Workaround used

Oriented through `tests/esx/test_framework_fixes.py::<module>` and
`tests/esx/test_instrument_claims.py::<module>` instead -- neither path starts
with `tools/esx/`, so `COMMAND_PATTERN` never matches, and the brief built
cleanly.

## Proposed fix

Exclude the orientation's own reconstructed command block from
`interface_errors`'s scan (it is Arch's generated evidence trail, not an
instruction to the dispatched agent), or terminate `COMMAND_PATTERN`'s `rest`
capture at the next recognized flag token (`--\w+`) rather than only at a
quote/backtick/newline, so a second script's flags are never folded into the
first script's checked span.
