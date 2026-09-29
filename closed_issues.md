# Closed issues

`loop_gate.py --check-done` moves a completed entry here, with its original UUID,
only when it accepts the closeout. Status is Resolved or False Positive. Preserve the evidence and the scientific bounds of the conclusion.

```markdown
## RESOLVED: <Brief title>

**Date Identified**: <UTC ISO timestamp>
**Date Resolved**: <UTC ISO timestamp>
**Status**: Resolved
**UUID**: <Original ID>

### Issue
<Original contract violation or question>

### Resolution and justification
<Implemented behavior or evidence establishing the finding>

### Verification and remaining bounds
<Regression witness, independent check, final suite receipts and untested conditions>

### Traceability
<Commit SHA or noncommit reason; iteration history/evidence references; related blockers>
```
