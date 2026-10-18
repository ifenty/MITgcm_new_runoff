# Assessment: retained agents lose time to permission-check denials

**Date**: 2026-10-18
**Issue**: RUNOFF-037, RUNOFF-052 and RUNOFF-022 iterations
**UUID**: TEAM-AGENT-PERMISSION-DENIALS-001

## Observation

Counting `permission_denials` in the retained-turn results of the three iterations run on 2026-10-17/18
(`devel-loop/loop_state/*-RUNOFF-037.out`, `*-RUNOFF-052.out`, `*-RUNOFF-022.out`):

| turn | denials |
|---|---|
| bob-start RUNOFF-037 | 6 |
| bob-resume RUNOFF-037 | 14 |
| bob-start RUNOFF-052 | 8 |
| bob-start RUNOFF-022 | 13 |
| richard-start RUNOFF-037 | 5 |
| richard-followup1 RUNOFF-037 | 3 |
| richard-resume1 RUNOFF-037 | 1 |
| richard-start RUNOFF-052 | 3 |
| richard-start RUNOFF-022 | 7 |

The reasons repeat: "Compound command contains cd with write operation", "This Bash command contains multiple operations",
"Contains brace with quote character (expansion obfuscation)", "A variable in this command can't be checked before it runs",
"Output redirection ... needs approval", and **"What 'taskset' starts can't be checked before it runs"**.

The taskset reason is partly self-inflicted. The owner's resource rule (4 CPUs, 4 GB) was passed to the agents as "prefix model and
test runs with taskset -c 0-3". `Bash(taskset *)` was added to `.claude/settings.local.json` on 2026-10-17 and the checker still
refuses it. The prefix is also redundant: `agent_runtime.py` is itself started under `taskset -c 0-3`, and a child process inherits the
CPU affinity, so every command the agent runs is already pinned.

## Not yet measured

How many minutes each denial cost. Agents mostly worked around a denial (a file instead of a heredoc, the command without taskset),
so the loss is spread across turns. The one stop that mattered was RUNOFF-037's first Bob turn, where the missing python rule ended the turn
with only the edit done (about 25 minutes including the owner decision).
