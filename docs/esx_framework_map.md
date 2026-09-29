# ESX framework map

Use this map for workflow code and docs/code_map.md for the project's science.
Read the named owner, its caller and the nearest regression before changing a
mechanism. Python symbols can be inspected with tools/esx/orient.py without
importing scientific code. Paths below are relative to the project root.

| Mechanism | Owning source | Contract | Kit regression |
|---|---|---|---|
| Configuration, paths, signatures | tools/esx/project.py | esx/project.json | test_framework.py |
| Scope, reviews, failure recovery | tools/esx/workflow_policy.py | .claude/ESX-team/ARCHITECT.md | test_execution.py |
| Iteration preparation and closeout | tools/esx/loop_gate.py | devel-loop/loop_contract.md | test_framework.py, test_execution.py |
| Runtime sessions, resumes, peer delivery | tools/esx/agent_runtime.py | devel-loop/execution.md | test_runtime.py, live_runtime.py |
| Native role completion capture | tools/esx/hooks.py | devel-loop/issue_json_schema.md | test_runtime.py |
| Finite loop state and Stop decisions | tools/esx/loop_control.py, tools/esx/ralph_stop.py | devel-loop/loop_contract.md | test_ralph.py |
| Hook ownership | tools/esx/check_ralph_hook.py | devel-loop/loop_contract.md | test_ralph.py |
| Scientific/focused runs, logs, cache | tools/esx/verify.py | devel-loop/verification.md | test_framework.py, test_execution.py |
| Reviewed final candidate and run ownership | tools/esx/final_verification.py | devel-loop/verification.md | test_execution.py |
| Baseline, navigation and documentation | tools/esx/doc_contract.py, tools/esx/doc_inventory.py | devel-loop/documentation_contract.md | test_evidence.py |
| Exact candidate bytes, comparison, extraction | tools/esx/issue_candidates.py | devel-loop/execution.md | test_evidence.py |
| Closeout imports, continuation, diagnosis, timings | tools/esx/workflow_records.py | devel-loop/execution.md | test_evidence.py, test_execution.py |
| Issue/lesson history and links | tools/esx/records.py, tools/esx/audit.py | devel-loop/issue_json_schema.md | test_framework.py |

Regression names identify files under tests/ in the distribution kit. Each test
creates a disposable configured project. The receiving project supplies its own
scientific acceptance suite and test routes. Keep this map accurate when an owning
module, contract or regression route changes. Read-only analysis cannot establish
that an unexecuted scientific oracle passes.

## Review packet and runtime recovery

| Mechanism | Owning source | Contract | Kit regression |
|---|---|---|---|
| Staged review packets and read-only readiness | tools/esx/workflow_handoff.py | devel-loop/recovery.md | test_workflow_recovery.py, test_execution.py |
| Read-only closeout dry run and reiteration drafting | tools/esx/closeout_doctor.py, workflow_records.py | devel-loop/loop_contract.md, devel-loop/execution.md | test_closeout_doctor.py |
| Assessed session transitions and hook diagnostics | tools/esx/runtime_recovery.py | devel-loop/recovery.md | test_runtime.py, test_workflow_recovery.py |
| Real retained-session instruction refresh | tools/esx/agent_runtime.py | devel-loop/recovery.md | live_runtime_transition.py (opt-in) |

A running retained assignment prevents packet readiness and final verification.
The final wrapper can bind current acceptance to unchanged measured scientific
execution; receipts retain the original execution evidence.

## Autonomous operation and communication

| Mechanism | Owning source | Contract | Kit regression |
|---|---|---|---|
| Project slash command and start/continue | .claude/commands/esx-loop.md, tools/esx/loop_control.py | devel-loop/loop_contract.md | test_autonomous_loop.py |
| Routine decision authority | .claude/ESX-team/ARCHITECT.md | Autonomous loop authority section | test_autonomous_loop.py |
| Required event collection and delivery receipts | tools/esx/notifications.py | devel-loop/communication.md | test_autonomous_loop.py |

The notification utility records events and actual provider responses. Arch sends
through the authorized provider tool. Pending events route back to delivery;
recorded provider failures remain visible while scientific work proceeds.

## Measured process operation

| Responsibility | Owner | Validation in master |
|---|---|---|
| Role briefs and early completion contracts | tools/esx/brief.py, footer_contract.py, agent_runtime.py | tests/test_parity_integration.py, test_runtime.py, test_seal_citation.py |
| Shared reservations, coordinator receipts and Arch self-reports | tools/esx/team_budget.py, team_driver.py, team_accounting.py | tests/test_team_operations.py, tests/test_coordinator_cost.py |
| Bounded tool groups and hook counters | tools/esx/bounded_command.py, runtime_tool_hook.py | tests/test_team_operations.py, test_execution.py |
| Successful starts and immutable iteration identity | tools/esx/loop_iteration.py, loop_gate.py | tests/test_parity_integration.py, test_execution.py |
| Required measured reflection and recurring owners | tools/esx/team_retrospective.py | tests/test_parity_integration.py, test_team_operations.py, test_retro_success.py |
| Process evidence and recoverable ledger promotion | tools/esx/process_evidence.py, self_improvement.py, ledger_transaction.py, loop_lifecycle.py | tests/test_self_improvement.py, test_process_improvements.py, test_parity_integration.py |

Owning contracts: [bounded operations](../devel-loop/team_operations.md),
[process records](../devel-loop/self-improvement/README.md), and
[the loop](../devel-loop/loop_contract.md). Test paths above belong to the master;
receiving projects register their own scientific witnesses in project.json.
