# Assessment: RUNOFF-001 process issues (2026-09-30)

Iteration RUNOFF-001 (2026-09-29T21:42Z to 2026-09-30T12:33Z). Measured: 10 Bob dispatches ($60.30) and 14 Richard dispatches ($114.61), provider-reported. Coordinator cost unknown.

1. ESX kit defects surfaced only under live role dispatch:
   - retained-role Bash denied by the permission-rewriting hook (ESX-002);
   - the adapter crashed on string `message` events (ESX-001);
   - provider overshoot failed completed turns;
   - review context exceeded the 131,072-byte argv limit.
   All were fixed upstream in ESX-Team 1.5.1 to 1.5.6 and deployed here. Cost: about 3 h of Arch time; two failed Bob turns ($27.48) and two failed Richard launches.
2. A bare `claude --print` run in the project directory during an active loop loaded the project Stop hook. It advanced iterations 2 to 6 and emitted the completion promise, ending the loop at 2026-09-30T05:39:41Z (see .claude/esx-loop-exit.log). The ESX adapter isolates its own children; manual runs are not isolated, and ralph_stop.py doesn't check that the stopping session owns the loop.
3. Documentation dispositions and docstrings drifted across correction rounds because they were regenerated from templates, which caused round-2 rejections. Fixed with source-derived reasons and tests/runoff/test_docstring_rules.py (lesson LL-001).
