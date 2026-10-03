# Assessment: runtime transition evidence (RUNOFF-010, 2026-10-02)

- **What happened:** Arch edited one sentence of CLAUDE.md to record the package design. The next followup for retained Bob (a6fef0e4) was refused because the runtime contract had changed. That refusal is correct.
- **The defect:** `assess-transition` required a judgment file whose format is visible only in `runtime_recovery.validate_assessment`. Its check evidence must carry the raw-file sha256, while `verify.py` returns a canonical-JSON digest for the same file. The first attempt, using the `verify.py` reference as returned, failed with "compatibility check evidence hash mismatch". Re-hashing the raw file passed.
- **Cost:** about five minutes of coordinator time. No role turn was lost.
- **Classification:** kit usability defect, low severity. The fix belongs upstream in ESX-Team: validate the evidence with `verify.load_evidence` and document the judgment format in `--help`.
