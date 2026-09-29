# Developer code map

Complete the routes below with actual paths and qualified Python symbols before
activation. Use `path::<module>` for a non-Python source file. Python AST locations
come from `python3 tools/esx/orient.py --outline path/to/file.py`; they do not prove
a dynamic call graph. Use a language-aware outline or bounded source search for
Fortran, Julia, C/C++, R or other languages.

## Pipeline

TODO_ESX: Name each scientific/computational stage, its owner, upstream inputs,
downstream consumers and nearest focused check. Include data ingestion, masks,
coordinates, numerical/analysis kernels, diagnostics and serialization as relevant.

| Stage | Source and owning symbol | Input → output | Contract / nearest test |
|---|---|---|---|
| TODO_ESX | TODO_ESX | TODO_ESX | TODO_ESX |

## Verification routes

TODO_ESX: Give runnable focused commands, full qualification routes and where
independent oracles live. Point to configured suites in esx/project.json.

## Framework routes

| Responsibility | Owning operation |
|---|---|
| Project configuration and source signatures | `tools/esx/project.py::config`, `tools/esx/project.py::source_signature` |
| Issue selection and acceptance | `tools/esx/loop_gate.py::Gate.prepare`, `tools/esx/loop_gate.py::Gate.check_done` |
| Verification and reuse | `tools/esx/verify.py::run`, `tools/esx/verify.py::load_evidence` |
| Map navigation and documentation coverage | `tools/esx/doc_contract.py::navigate`, `tools/esx/doc_contract.py::validate_report` |
| Commit, notification and iteration history | `tools/esx/records.py::save_history` |
| Hook completion receipts | `tools/esx/hooks.py::capture` |

## Maintenance

Update stage ownership, input/output contracts and check routes when their source
changes. Keep line numbers out of manual tables; resolve them from live source.
A MAP-OK disposition explains which routes remain accurate for the actual patch.

## Review packet and runtime recovery

- `tools/esx/workflow_handoff.py::assemble` constructs explicit candidate/report/brief handoffs.
- `tools/esx/workflow_handoff.py::readiness` collects prerequisite failures without dispatching agents.
- `tools/esx/closeout_doctor.py::diagnose` lists every unmet closeout requirement, then replays the strict gate read-only.
- `tools/esx/workflow_records.py::locate_prior` and `replacement_skeleton` draft reiteration continuity without judging it.
- `tools/esx/runtime_recovery.py::compatibility` checks canonical configuration and assessed transitions.
- `tools/esx/runtime_recovery.py::hook_doctor` attributes configured hooks without executing them.
- `tools/esx/doc_contract.py::validate_orientation` diagnoses the changed dependency slice.

The owning procedure is [Evidence handoff and recovery](../devel-loop/recovery.md).
