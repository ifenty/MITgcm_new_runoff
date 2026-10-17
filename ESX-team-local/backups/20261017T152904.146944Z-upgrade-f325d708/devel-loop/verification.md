# Verification and scientific evidence

The project owner completes esx/project.json with argv arrays for structural,
focused and scientific suites. `{python}` expands to the verifier's interpreter.
Commands execute directly without a shell. Use an explicitly versioned script
for pipelines and preserve its actual failing exit code. No empty suite passes.

```sh
python3 tools/esx/verify.py --suite focused --owner bob
python3 tools/esx/verify.py --suite structural --owner arch
```

For an active scientific issue, first assemble the exact candidate, reviews and
sealed documentation in a project-relative review packet. The assigned owner runs:

```sh
python3 tools/esx/final_verification.py check --review devel-loop/loop_state/review.json --owner arch
python3 tools/esx/final_verification.py run --review devel-loop/loop_state/review.json --owner arch
```

Store returned `scientific` and `receipt` references in closeout verification.
Direct scientific verification during an active issue is refused. With no active
issue, `verify.py --suite scientific --owner arch` supports standalone qualification.
One owner lock serializes final attempts. Reuse requires the exact reviewed source,
review events, documentation, inputs, configuration and measured toolchain. A
failed fresh attempt invalidates the former final receipt. Readiness is checked
again after execution; drift during the run blocks acceptance. Process interruption
terminates the verifier's process group. Test scripts must avoid detaching
background workers beyond that group.

Each attempt record under `final-verification/` carries one status, and
`final-verification/latest.json` names the most recent attempt:

- `PASS`: the suite passed on the unchanged reviewed candidate.
- `FAILED`: the suite reached a non-zero verdict (or timed out) on the candidate.
- `INTERRUPTED`: the verifier or its child was killed by a signal, or a pytest
  session ended without its summary line; no verdict exists, so re-run.
- `SOURCE_CHANGED`: source, configuration or review moved during the run; the
  outcome describes no single candidate, so re-run after edits finish.

Non-PASS attempts record their `log` and count of `FAILED`/`ERROR` lines. When no
current receipt exists, `--check-done` names the latest attempt, its status and log.

After a successful re-run, re-point the prepared closeout at the current receipt:

```sh
python3 tools/esx/loop_lifecycle.py rebind-receipt
```

It refuses unless `current.json` is an intact PASS whose `review_signature` equals
the closeout record's, and the rebound record must pass the gate's receipt check.
Never hand-edit `verification.receipt` in `issue-done.json`.

For Richard's independent check, use his actual runtime identity:

```sh
python3 tools/esx/verify.py --suite focused --owner RUNTIME_AGENT_ID --fresh   --command '["{python}", "tests/check_boundary.py"]'
```

The example command must be replaced with an actual project test. An independent
check varies an input, boundary, parameter, method or oracle and explains its
additional coverage. The final scientific receipt must run the entire configured
scientific suite; a custom focused command cannot satisfy it.

Evidence under devel-loop/loop_state/verification includes source/command/environment
fingerprints, configured toolchain probe outputs and actual external-input hashes,
owner, start/end, duration, exit status, stable-source result and log hash. A matching
complete PASS may be reused. Missing or modified logs/artifacts, changed input or
configuration, a failure, timeout or source change invalidates evidence.
Matching suite executions are serialized with a POSIX lock. A fresh attempt clears
its reusable cache entry before running, so failure or interruption cannot expose
an older matching PASS as the result of that attempt.

Scientific input scope comprises source_paths, test_paths and configuration_paths.
The framework and profile are also fingerprinted where their execution affects
verification. External input files are hashed from bytes, including their absolute
identity. Use bounded qualification inputs for routine local runs. Declare compiler,
MPI, BLAS, package/lockfile, precision, thread and environment differences that
matter. There is no automatic discovery of undeclared dependencies.

The scientific suite owns its mathematical oracle: finite-value/sample-count
checks, conservation, convergence, manufactured solutions, derivative identities,
independent reference calculations, uncertainty or observational comparisons as
appropriate. Select criteria in advance and justify tolerances scientifically.

The local runner waits for foreground commands. A cluster adapter must wait for
job completion, retrieve logs/results, compare the acceptance oracle and return
that verdict. Record scheduler/job/environment provenance with those outputs.
A local smoke test cannot substitute for required full-data or remote qualification.

The [recovery contract](recovery.md#reuse-execution-with-fresh-acceptance) separates
current acceptance from the measured scientific execution. Refreshed approval
evidence can reuse an intact execution when its scientific dependencies agree.
Use `final_verification.py run --fresh` to require a new execution.
