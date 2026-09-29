---
name: esx-verify
description: Use when running checks, claiming correctness or reviewing scientific changes.
---

# esx-verify

Read devel-loop/verification.md and the project scientific acceptance contract.
Run configured commands through tools/esx/verify.py so evidence includes commands,
source, toolchain, inputs, logs and completion. Reuse only matching complete PASS.
An empty, nonfinite, insensitive or zero-sample scientific comparison cannot pass.
Use the actual scientific oracle and project tolerances; the wrapper records exit
status and provenance and does not invent a domain-specific correctness criterion.

Richard runs an independent focused check with --fresh and --owner <runtime-id>.
One named owner provides final configured suites. For an active scientific issue,
use tools/esx/final_verification.py with the exact reviewed candidate packet;
readiness and receipt checks enforce the final-run ordering. Report untested scales, datasets
and configurations. A submitted cluster job must be collected and checked before
its command returns success. Distinguish process failure from scientific mismatch.

Before final execution, use the stage-final readiness command in
`devel-loop/recovery.md`. Distinguish fresh acceptance from scientific execution;
report execution reuse explicitly and preserve its original receipt.
