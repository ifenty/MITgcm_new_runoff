# Agent report footer — field-by-field guide

`esx/templates/agent_report.json` gives the *shape* of the required footer.
This guide gives the *values* — several fields have exactly one correct value
or format, and the wrong-but-plausible-looking alternative is a real mistake
that has recurred across independent agent turns. Read this before your first
report on any issue; it saves a correction round.

## `candidate_signature`

Must be `project.py::source_signature(root)` — **not**
`issue_candidates.py`'s own signature. These are two different hashes over
differently-scoped, differently-structured data; a value from one never
matches what the gate expects from the other.

Compute it directly, right before writing your report:

```sh
python3 tools/esx/project.py signature
```

Copy the printed `signature` value verbatim. If you also ran
`issue_candidates.py capture`/`check` for other reasons, that command's own
`"signature"` field is a *different* value — do not reuse it here.

## `verdict` (Richard only)

Exactly one of: `APPROVE`, `APPROVE_WITH_FIXES`, `REJECT`. No other string,
no lowercase variant.

## `documentation_review.status` (Richard only)

Exactly the literal string `confirmed`. Not `sealed`, not `confirmed_current`,
not any other synonym — these have recurred independently more than once.
The distinction that matters: `sealed` describes the *report's own state*
(set by whoever built it); `confirmed` describes *your own act* of
independently re-validating that exact sealed report against current source.
You are always reporting the second thing, never the first.

## `independent_check`

`independent_check.evidence` must be a **real, content-addressed reference**
returned by `verify.py` or `final_verification.py` — never `{"path": "", "sha256": ""}`.
A plain command (e.g. a bare `pytest` invocation) does not produce a sealed
evidence file on its own and cannot supply this field. If your independent
check was a plain test command, additionally run the project's own configured
suite through `verify.py` (e.g. `python3 tools/esx/verify.py --suite focused
--owner <your-agent-id> --fresh`) and cite *that* command's evidence
reference instead — reusing your own plain-command output only as
`coverage` narrative, not as the structured `evidence` field.

## `orientation`

The reference returned by your own `doc_contract.py::navigate()` call for
this issue and role — not copied from another agent's report, not
reconstructed by hand.

## `correction_round`

The value you were actually dispatched with (the `--correction-round` flag
Arch supplied). If you are unsure, this is the exact value already present in
the runtime's dispatch context passed to you at the start of this turn —
copy it, do not infer or increment it yourself.
