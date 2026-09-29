# Communication and publication contract

Arch owns external announcements. Bob and specialists report findings to Arch.
SessionStart routes context, SubagentStop captures report JSON, and PostToolUse
checks project records. These hooks never post or commit. The project ESX Stop
hook re-injects the saved loop prompt within its finite budget. Internal role
messages use the retained session adapter described in [execution.md](execution.md).
Arch receives scope decisions and escalations; peers exchange bounded evidence
directly through recorded sender and recipient identities.

The project owner supplies provider, channel, audience and authorization. Record
them in esx/project.json and the project profile. Existing applicable authorization
persists; do not ask again merely because an iteration changed. A configuration
field alone grants no permission. Use the esx-announce procedure when sending.

## Required loop events

With applicable owner authorization, attempt delivery for loop start, issue
start, newly filed issue, validated issue closeout (completed/partial/blocked),
new lesson, progress on each continuation, and loop end. Arch adds a bounded
milestone update when a long iteration makes a material discovery. Report the
scientific/user consequence and honest status. Routine announcements need no
new confirmation when standing authorization covers them.

`tools/esx/notifications.py` maintains `devel-loop/loop_state/notifications.json`.
Events have stable IDs, a destination, message text, attempts and status. Its
first scan baselines existing issues/lessons to avoid announcing the old backlog
as newly discovered. Closeouts originate in validated history; moving a Markdown
entry alone cannot create a resolution announcement. Hooks queue events and
reminders. They never send network requests or obtain credentials.

Arch reads `.claude/skills/esx-announce/SKILL.md` and calls `notifications.py pending`
after loop activation, issue preparation, issue/lesson changes and closeout, and
before returning from a turn. Send using the authenticated provider tool in the
current session. Save its actual JSON result under loop_state and record it:

```sh
python3 tools/esx/notifications.py record EVENT_ID --response-file PROVIDER_RESULT.json \
  --tool ACTUAL_PROVIDER_TOOL --authorization 'Applicable owner instruction reference'
```

A Slack MCP receipt uses returned `message_context.channel_id` and
`message_context.message_ts` (plus the returned message link when supplied).
Slack Web API receipts use `ok: true`, `channel`, and `ts`. If the tool wraps the Slack object in content, extract that actual
object and preserve the original response alongside it. Do not invent receipt
fields. Recording validates the response structure; provider delivery truth must
come from the actual tool call. An interrupted call can have delivered: search
recent channel messages for this event before retrying. Already-sent events are
never reposted by the local queue.

On failure or absent tools, save the concrete result/discovery:

```sh
python3 tools/esx/notifications.py record EVENT_ID --disposition unavailable \
  --tool 'Tool discovery: actual search used' --detail 'Concrete provider discovery result and reason sending is unavailable.'
```

Use `failed` for an executed send failure, `unavailable` for a demonstrated absent
provider, or `unauthorized` when applicable permission is missing or revoked.
Do not label an authorized channel unauthorized merely because a turn changed.
`pending`, a draft, and an intention to post cannot satisfy the delivery duty.
Failed/unavailable events retain their attempts in `notifications.py status`;
retry them explicitly after the provider recovers, checking for earlier delivery.

## Session provider outage

When the provider is established dead for the session (for example, only an
authentication tool is exposed and the owner step cannot be completed), record
the discovery once instead of adjudicating each event:

```sh
python3 tools/esx/notifications.py outage --provider slack \
  --tool 'Tool discovery: actual search used' --probe-evidence 'Concrete probe result.'
```

The outage belongs to the current loop run. It marks every queued event for that
provider, and every event the run queues later, `outage_covered` with the outage
ID; the evidence lives only on the outage record. `status` lists outage-covered
events separately from individually `failed` ones. Use per-event `failed` for an
executed send that failed; an outage asserts that no send was possible at all.

Recovery is never assumed and the outage is never assumed to persist. While it is
active, `--next` blocks until a re-probe is recorded in every loop iteration, and
after every `OUTAGE_PROBE_EVENTS` (10) covered events, whichever comes first:

```sh
python3 tools/esx/notifications.py reprobe --provider slack --tool ACTUAL_TOOL \
  --result down|up --probe-evidence 'What the fresh probe returned.'
```

`--result up` clears the outage; events queued afterwards are again pending and
individually adjudicated, while earlier covered events keep their outage status
(retry them explicitly if the owner still needs them). An outage applies for
`OUTAGE_RENEW_ITERATIONS` (5) loop iterations from its declaration or last renewal.
After that it covers nothing new, `down` re-probes are refused, and `--next`
blocks until the `outage` command is rerun with fresh probe evidence (a renewal)
or the outage is cleared. `pending` still blocks exactly as before.
Report undelivered messages in the owner-facing loop summary. A network failure
must not turn a correct scientific result into a failure or consume endless
retries. Batch related findings while keeping their event receipts identifiable.

`--next` prioritizes pending delivery before further work or a completion promise.
Cancellation and forced termination preserve undelivered events for the next
main session. If the process is killed or the provider is unavailable, ESX cannot
guarantee an immediate final Slack post. The ledger exposes that limitation.

Existing issue records may also carry `communication`, `slack_ts` or `slack_error`.
When changing those fields after a validated closeout, rerun `--check-done` with
the original timestamp so durable history reflects the delivery result. The
notification ledger supplies the per-event delivery history for the loop.

Arch decides whether and when to commit within owner authorization. Every closeout
records either a resolvable commit SHA or the reason the changes remain uncommitted.
The gate checks commit existence; it does not prove the commit contains the complete
reviewed change. The owner may require one scoped commit per accepted issue in the
project profile. Preserve unrelated working changes and obey project commit style.
