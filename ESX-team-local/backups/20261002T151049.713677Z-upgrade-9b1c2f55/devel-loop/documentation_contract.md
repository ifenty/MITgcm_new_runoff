# Code map and documentation maintenance contract

Code correctness, accurate documentation, and use of the code map are equal
acceptance requirements. Arch owns their completion. Each implementing agent
maintains the explanations affected by its patch; each independent reviewer
checks those explanations as part of the same review. This contract owns the
maintenance procedure; Arch's contract owns scope, role selection and verification.

## Before implementation

Use `tools/esx/doc_contract.py` from the ESX root. Save a baseline before issue edits:

```sh
esx_doc_base=$(python3 tools/esx/doc_contract.py baseline --issue EXAMPLE-001)
```

Each command producing evidence prints a JSON reference with `path` and `sha256`.
Preserve that complete reference. Evidence lives under the ignored
`devel-loop/loop_state/maintenance/` directory. Files use their content hashes as
names and are written once. The baseline includes the working tree's existing
uncommitted changes, so the eventual inventory identifies subsequent edits.
It covers configured scientific source, tests and configuration plus framework,
documentation and role/skill paths, including ignored and untracked source files. Generated logs and issue state are excluded. See
[the inventory implementation](../tools/esx/doc_inventory.py) for the exact selection.

Arch uses the map to locate the owning stage and reads a bounded dependency slice.
Record that orientation before writing the implementation brief. When the change
alters a named default, symbol or documented contract, declare the name with
`brief.py --sweep-symbol NAME` ([Bounded operations](team_operations.md)): the
disposition below covers only changed files, so unchanged documents that still
state the old meaning must be enumerated at brief time. Each dispatched
role does the same before dependent problem solving, using the baseline reference
provided in its brief. For example:

```sh
python3 tools/esx/doc_contract.py navigate --issue EXAMPLE-001 \
  --baseline "$esx_doc_base" --role bob \
  --map 'docs/code_map.md#pipeline' \
  --target 'src/model.py::step' \
  --target 'tests/test_model.py::<module>' \
  --doc 'docs/model_contract.md' \
  --use 'Follow boundary updates into the independent conservation test; inspect the owner and consumer before changing the numerical operation.'
```

Choose the **actual** owning symbol, a related caller/consumer/test, and the owning
technical reference for the issue. The example establishes the command syntax.
Use `path::<module>` for module headers, constants, shell/Fortran code and
instruction files. Python names can include nested functions and class methods.
References use repository-relative paths and exact Markdown heading slugs.
Heading-style `#` references require unique ATX headings; ambiguous headings need
more specific names. The helper prints up to 65 lines per reference on stderr;
read the relevant remainder with a focused `Read` or `rg`. Explain which fact or
invariant from these references guides the intended change or investigation.

`navigate` records role, issue, baseline, references, hashes and the use explanation.
Arch puts the baseline and its orientation reference in `issue-start.maintenance`.
Run `loop_gate.py --check-start` before implementation. Include the baseline and
relevant reference suggestions in every dispatch; each agent records its own
orientation in its structured footer. Read-only roles may run this helper and
write its maintenance evidence. Their source-edit restrictions remain in effect.

## During implementation and corrections

Update descriptions in the same patch as the behavior they explain. Review the
function docstring, adjacent comments, module header, affected caller/consumer
contracts and owning technical document. A changed interface, default, refusal,
artifact or test route also requires review of summaries that repeat that claim.
Describe implemented behavior, assumptions and useful justification. Follow
[the documentation format guide](../docs/doc_format_guide.md).

Use live AST outlines for symbol locations. Python's abstract syntax tree records
functions, classes and expressions in a structured form; the helper reads that
structure without importing or running project code. It identifies lexical edits
to qualified definitions, including nested functions, decorators, removals and
additions. Every changed file also has a module row for constants, imports,
headers and other file-level contracts. Non-Python files receive a module row.
The review must cover the actual affected Fortran/shell routines within that row.
A Python parse error blocks inventory generation and requires investigation.

Retain navigation evidence through corrections when its selected inputs remain
unchanged. Test reuse with:

```sh
python3 tools/esx/doc_contract.py check-orientation --issue EXAMPLE-001 \
  --baseline "$esx_doc_base" --role bob --receipt "$esx_orientation_ref"
```

A changed selected symbol, map section or documentation section requires reading
the delta and recording refreshed navigation before further dependent work. An
edit to its module-level imports, constants or executable initialization also
invalidates that symbol's navigation. An unrelated function-body or file edit
preserves the selected slice. Syntactic call matches
are navigation candidates; inspect aliasing, imports and dynamic dispatch before
asserting the actual dependency. No new specialist or full test run is required
solely to maintain these records.

## Review and closure

Once source and documentation are ready, generate the disposition plan:

```sh
python3 tools/esx/doc_contract.py draft --issue EXAMPLE-001 \
  --baseline "$esx_doc_base" > /tmp/esx-doc-plan.json
```

For **every** generated target, fill the existing `action`, `reason` and
`references` fields. Preserve the generated identity, candidate and change list.

- `updated`: identify the contract text changed and explain the resulting behavior.
  At least one referenced documentation section or Python prose span must have a
  measured edit. Changing executable Python alone cannot satisfy this claim.
- `reviewed_unchanged`: explain why the existing description remains accurate for
  this change and cite that description. Use this for implementation changes that
  preserve a documented contract, with the specific invariant that establishes it.
- `removed`: for a removed symbol/file, explain disposition of its callers and
  references, citing the resulting documentation or surviving owning contract.

Each reason needs at least 40 characters; length is only a missing-content check.
A generic approval or a copied reason that fails to explain the target is a review
finding. A new internal helper may share its parent's owning documentation when
that contract adequately explains it. Avoid boilerplate docstrings on trivial
helpers. Fill `map_delta` with `status` (`updated` or `MAP-OK`), a substantive
`reason`, and relevant map heading `references`. An unchanged map requires a
specific explanation of why its routes remain accurate. Changed mapped entry
points, artifacts, dependencies and test routes require the corresponding update.

Seal the completed plan:

```sh
python3 tools/esx/doc_contract.py seal /tmp/esx-doc-plan.json
```

The helper rejects missing targets, blank dispositions, broken references,
unsupported update claims and stale candidate snapshots. It saves the accepted
plan and its reference hashes, returning a documentation-report reference.
If another edit is needed, generate a fresh draft with `--previous` set to the
sealed report JSON reference. Automatic reuse requires unchanged target, enclosing
module context, cited prose and declared `dependencies` references. Dependencies
are exact `path::symbol` or `path#heading` entries. Without explicit dependencies,
the judgment conservatively depends on the complete inventory. Review changes
and seal again; a map judgment requires unchanged inventory for automatic reuse. Never update only the hash
in a stale report. Code and documentation edits both invalidate final approval.

Richard reads the sealed report and affected source/documentation, checks the
judgments, and supplies this addition to the ordinary hook-captured footer:

```json
{
  "orientation": {"path": "<helper output>", "sha256": "<helper output>"},
  "documentation_review": {
    "report": {"path": "<seal output>", "sha256": "<seal output>"},
    "status": "confirmed",
    "notes": "<specific contracts examined and why their descriptions match the candidate>"
  }
}
```

Every role footer includes `orientation`. Distinct agents must produce their own
receipts; the same resumed agent can reuse valid evidence. Each final approving
reviewer confirms the exact sealed report. Every correction re-seals, so a reviewer
brief names the current sealed report's path and sha256 in a standalone section
(and pre-fills `documentation_review.report`); an approval citing any other report
is rejected when the turn is captured, naming the cited and expected hashes. Earlier rounds preserve their original
navigation as historical evidence. Arch and final approving reviewers must have
fresh orientation at closure. Stale descriptions anywhere affected by the patch,
missing coverage and inaccurate dispositions are Must Fix findings. Resolve them
in the ordinary correction round with the assigned Bob and Richard.

Arch records the original baseline, current Arch orientation and sealed report
in `issue-done.maintenance`; copy the sealed `map_delta` into issue-done. The gate
validates them, the map's symbols/paths, and exact captured reviewer acknowledgments.
It rejects completion with missing or stale evidence, for every configured
workflow. There is no maintenance waiver. Partial/blocked outcomes can
record the outstanding work honestly. History retains the maintenance references
and map disposition. Documentation/harness tasks performed directly by Arch use
the same disposition coverage; role selection continues to follow the risk policy.

## Recovery and practical limits

The first issue baseline is pinned across correction rounds and validated partial
iterations. The baseline retains source bytes for later comparison and extraction.
A baseline recovered from an older metadata record preserves that original
metadata honestly; only available bytes can be reconstructed. Keep the baseline
unchanged across the issue's correction rounds. If work began
without a saved baseline, reconstruct from a known commit explicitly:

```sh
python3 tools/esx/doc_contract.py baseline --issue EXAMPLE-001 --git-base HEAD \
  --reason 'Recover the missing initial snapshot from this known commit and review every intervening working-tree change.'
```

This includes **all** differences from that commit, including pre-existing edits
and new files. Inspect that larger scope. Record the recovery provenance in the
start record and retain it through completion. Never take a fresh post-edit
baseline that erases the work under review. If the relevant prior source is
unavailable, retain a partial/blocked disposition and recover that evidence.

For existing hook completions recorded before a recovered baseline, preserve the
original footer and add an explicit `maintenance_history` object to its done entry:
`status: "predates_recovery"`, `baseline: <recovered reference>`, and a substantive
`reason`. The gate checks the hook timestamp against the recovery time. This
records the absence of contemporaneous navigation honestly; it supplies no final
documentation approval. Arch and the workflow's required number of current
reviewers must inspect the recovered inventory, record fresh orientation and
confirm the sealed report. Resume the assigned reviewers for that work. Keep
historical investigations available without redispatching them solely for a receipt.
This recovery path requires an explicitly justified commit baseline; ordinary
working-tree baselines cannot exempt completions from navigation requirements.

A direct user task can use its own task ID and evidence without modifying another
active issue's state; use `check` on its filled plan and the applicable review.

These mechanisms establish coverage, existence, provenance and review participation.
They cannot prove that an agent understood a paragraph or that a prose claim is
scientifically true. The explicit use explanation and independent review address
that judgment. Non-Python comment extraction recognizes selected full-line comment
forms; cite an owning Markdown section for other languages or inline-comment
changes. Binary artifacts and external repositories need their own validation.
Git-ignored sources used by a numerical witness must retain the verification
workflow's explicit input provenance. Do not treat this inventory as their oracle.

## Evidence packet fields

The [handoff contract](recovery.md) defines `handoff`, `closeout_pending`, exact
completion selections and structured readiness findings. Source and sealed report
references remain immutable. Orientation receipts include source, module-context,
enclosing-definition and documentation component hashes for precise recovery.
