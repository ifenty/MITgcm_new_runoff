# ESX project instructions

ESX (Earth Science-X) provides the team workflow. Read project-specific facts in
[project_profile.md](project_profile.md) and executable settings in
[project.json](project.json). Explicit owner instructions define the authorized
scope and take precedence over template guidance.

The main session is Arch. The [.claude/ESX-team/ARCHITECT.md](../.claude/ESX-team/ARCHITECT.md)
contract owns technical workflow, risk, verification ownership and corrections.
[The loop contract](../devel-loop/loop_contract.md) owns iteration order.
Use `python3 tools/esx/loop_gate.py --next` at the start of every active-loop turn.
Do not create a separate issue loop for a bounded direct task. `/esx-loop` starts
or continues autonomous work under Arch's Autonomous loop authority section.
Routine choices, required review, record updates and authorized announcements
proceed without owner confirmation.

Use [the code map](../docs/code_map.md) and live source locations before broad
reading. Code correctness, documentation accuracy and map use are equally required.
Keep source comments, public contracts and scientific claims consistent with edits.
Read the active lessons index; open detailed evidence only when its trigger applies.

Bob implements; Richard reviews independently. Scout, Prober, Bisector and Auditor
have bounded specialist duties. Keep runtime identities through corrections.
Use [retained execution](../devel-loop/execution.md) to dispatch, resume and deliver
peer findings, and [the framework map](../docs/esx_framework_map.md) to locate the
workflow mechanisms without repeatedly reading their entire implementations.
Required scientific review must run on a runtime supporting independent agents;
record an unavailable runtime as a blocker. Do not invent agent completions.

Follow verification stages and the single final-run owner. Preserve exact inputs,
commands, working directory, toolchain and logs. Label reused evidence. A successful
smoke run supports only its exercised configurations. Scientific qualification
requires the project's stated numerical, observational or statistical acceptance.

Preserve unrelated changes. Existing authorization remains applicable until
revoked or superseded. Commit, publish, deploy, spend paid compute, access restricted
data or send external messages only within the owner's applicable authorization.
Configuration expresses preferences; a filled field alone grants no authority.
Arch records commit and communication outcomes. Subagents report to Arch.

Keep development history in issue, lesson and milestone records. Reference docs
explain implemented behavior and useful justification in the present tense.
Follow [the documentation guide](../docs/doc_format_guide.md).

Keep records economical. Default budgets are 60 lines per open/closed issue,
50 lines per detailed lesson, and 40 lines per milestone. Active lessons use a
short statement plus a trigger of at most 12 words. A resume block contains at
most 12 lines of stable navigation links; disk records own changing state. The
owner can adjust these budgets in the project profile for a specific workflow.
