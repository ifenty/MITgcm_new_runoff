# Assessment: recurring provider-interruption/failure-notification noise across retrospectives

Observed in at least three recent retrospectives (RUNOFF-008 correction round 1, RUNOFF-031, RUNOFF-015):

- A dispatched agent's turn is sometimes cut off mid-work by a transient provider API error
  ("the response stopped arriving"). The agent is resumed in the same runtime identity with no
  lost work (RUNOFF-008 Bob, RUNOFF-031 Bob, RUNOFF-015 Bob).
- Separately, a "failed" task-notification can arrive for a turn that, inside the agent's own
  session, had already completed successfully in full (RUNOFF-015 Richard round 0: the suite,
  audit and final orientation/signature were already done; re-running them was idempotent and
  cost about 25 minutes of redundant work and one extra coordinator message).

Cost so far: roughly one extra correction/resume turn per occurrence, 5-25 minutes each. No
correctness defect has resulted; every resumed agent finished with full, correct evidence.

### Proposed owner
File a team issue: distinguish a genuine mid-turn provider interruption (missing footer, missing
evidence, process killed) from a notification-layer false failure (agent's own transcript shows a
complete, footer-bearing turn) before paying for a resume. A cheap check: before sending a resume
message, read the dispatch log for a completed-with-footer event at or after the failed
notification's timestamp; if one exists, treat the notification as advisory only.
