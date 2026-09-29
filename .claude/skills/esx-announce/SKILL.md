---
name: esx-announce
description: Deliver required authorized ESX loop updates and retain provider receipts.
---

# esx-announce

Read devel-loop/communication.md and esx/project.json. Use the owner's applicable
standing/session authorization; do not request routine reconfirmation. A configured
channel alone grants no permission. Arch owns delivery; subagents report to Arch.

1. Run `python3 tools/esx/notifications.py pending` in the project's environment.
2. For each pending event, use the authenticated provider tool to send its text
   to its recorded channel. Discover the actual tool by name (for Slack, search
   for slack_send_message or the available message-posting tool). Read its schema.
   Use the real message-send operation. A draft does not establish delivery.
3. Retain the exact returned response in a JSON file under devel-loop/loop_state.
   Record it using `notifications.py record EVENT_ID --response-file PATH --tool
   ACTUAL_TOOL --authorization 'Applicable owner instruction reference'`.
   Slack MCP responses use `message_context.channel_id` and
   `message_context.message_ts`; Web API responses use `ok`, `channel`, `ts`.
   Extract the actual returned object if wrapped, preserving the original output.
4. If provider discovery or sending fails, record `--disposition unavailable`
   or `failed`, `--tool` and concrete `--detail`. Continue scientific work. Never
   repeatedly ask the owner to approve already-authorized updates. Use
   `unauthorized` only when authorization actually is absent or revoked.
   If the provider is dead for the whole session, record one outage instead
   of per-event dispositions: `notifications.py outage --provider NAME --tool
   ACTUAL_DISCOVERY --probe-evidence TEXT`. It covers queued and later events.
   When `--next` demands it, re-probe the provider for real and record
   `notifications.py reprobe --provider NAME --tool T --result down|up
   --probe-evidence TEXT`; `up` clears it. Renew a spent outage by rerunning
   `outage` with fresh evidence. See communication.md#session-provider-outage.
5. Continue `loop_gate.py --next`. Report undelivered events at loop end; consult
   `notifications.py status`. Retry an unsuccessful event after a real provider
   recovery, checking recent channel messages first to avoid duplicate delivery.

Keep messages concise (roughly 80 words, under 200), with issue/lesson IDs,
consequence and honest status. Validate the underlying record before announcing
its result. Do not fabricate receipts or treat a completion draft as a sent post.
