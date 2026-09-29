"""Durable loop event outbox. Arch delivers via the authorized provider tool.

No network or credential access occurs here. Events are derived from project
records and deduplicated by stable identity; successful delivery retains the raw
provider response. A concrete failed/unavailable attempt permits scientific work
while remaining visible in the ledger. Pending is never treated as an attempt.

A provider established dead for the session is recorded once as an outage with
its probe evidence. It covers every queued event for that provider, and events
queued later in the same loop run, as ``outage_covered`` (never ``failed``). It
is never assumed to recover or to persist: while it is active, --next demands a
recorded re-probe every loop iteration or every OUTAGE_PROBE_EVENTS covered
events, whichever comes first, and after OUTAGE_RENEW_ITERATIONS iterations the
outage stops covering events until renewed with fresh probe evidence. Only a
re-probe with result ``up`` clears it; later events are adjudicated one by one.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import re
import sys
from project import STATE, atomic_json, digest, local, now, require
from records import json_lines, validate_records

ROOT = Path(__file__).resolve().parents[2]
LEDGER = f'{STATE}/notifications.json'
OUTAGE_PROBE_EVENTS = 10      # covered events allowed between recorded probes
OUTAGE_RENEW_ITERATIONS = 5   # loop iterations an outage record applies before renewal


@contextmanager
def ledger(root):
    path = local(root, LEDGER)
    lock = local(root, f'{STATE}/notifications.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        data = json.loads(path.read_text()) if path.exists() else {'version': 1, 'events': {}, 'runs': {}}
        require(data.get('version') == 1, 'unsupported notification ledger')
        try:
            yield data
            atomic_json(path, data)
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def emit(data, key, kind, subject, text, route):
    identity = digest([key, route.get('provider'), route.get('channel')])[:24]
    if identity not in data['events']:
        data['events'][identity] = {'id': identity, 'kind': kind, 'subject': subject,
            'text': ((route.get('message_prefix') or '[ESX]') + ' ' + text)[:1800],
            'provider': route.get('provider'), 'channel': route.get('channel'),
            'created_at': now(), 'status': 'pending', 'attempts': []}
    return identity


def synchronize(root, terminal=None):
    """Collect actual transitions; baseline pre-existing issues and lessons once.

    Closeouts come only from validated history. A newly closed Markdown entry
    cannot establish acceptance. Local state and provider receipts are excluded
    from source signatures by their loop_state location.
    """
    root = Path(root).resolve()
    current = session(root)
    if current is None:
        return
    state, run = current
    cfg = json.loads(local(root, 'esx/project.json').read_text())
    route = cfg.get('communication', {})
    if not route.get('provider') or route.get('provider') in ('none', 'disabled'):
        return
    require(route.get('channel'), 'configured communication requires a channel')
    opened, closed, lessons = validate_records(root)
    starts = local(root, f'{STATE}/issue-start.json')
    start = json.loads(starts.read_text()) if starts.exists() else None
    history = json_lines(local(root, f'{STATE}/loop_history.jsonl'))
    with ledger(root) as data:
        if run not in data['runs']:
            data['runs'][run] = {'issues': sorted(set(opened) | set(closed)), 'lessons': sorted(lessons),
                                'history': [[h['id'], h['timestamp']] for h in history]}
            emit(data, ['loop_start', run], 'loop_start', run,
                 f"Loop active at iteration {state['iteration']}/{state['limit']}. "
                 f"{len(opened)} open issues; autonomous work follows the project contracts.", route)
        seen = data['runs'][run]
        for iid in sorted(set(opened) - set(seen['issues'])):
            emit(data, ['issue_opened', run, iid], 'issue_opened', iid,
                 f"New issue {iid}: {opened[iid]['title']}. Recorded for investigation.", route)
        for lid in sorted(lessons - set(seen['lessons'])):
            lines = local(root, 'lessons_learned.md').read_text().splitlines()
            description = next((line.strip() for line in lines if f'[{lid}]' in line), lid)
            emit(data, ['lesson', run, lid], 'lesson', lid, f'Lesson recorded: {description}', route)
        seen['issues'] = sorted(set(seen['issues']) | set(opened) | set(closed))
        seen['lessons'] = sorted(set(seen['lessons']) | lessons)
        if start and not any((h['id'], h['timestamp']) == (start['id'], start['timestamp']) for h in history):
            emit(data, ['issue_start', start['id'], start['timestamp']], 'issue_start', start['id'],
                 f"Starting {start['id']}: {start['title']}. {start['priority_reason']}", route)
        for h in history:
            identity = [h['id'], h['timestamp']]
            if identity not in seen['history']:
                emit(data, ['closeout', *identity], 'issue_closeout', h['id'],
                     f"{h['id']} — {h['outcome']}: {h['summary']}", route)
                seen['history'].append(identity)
        if state['iteration'] > 1 and terminal is None:
            iid = start['id'] if start else 'issue selection'
            emit(data, ['progress', run, state['iteration']], 'progress', run,
                 f"Loop iteration {state['iteration']}/{state['limit']}; current record: {iid}. "
                 'Work and verification continue; completion is reported after validated closeout.', route)
        if terminal:
            emit(data, ['loop_end', run], 'loop_end', run,
                 f"Loop ending: {terminal}. {len(opened)} open issues, "
                 f"{sum(r['state'] == 'blocked' for r in opened.values())} blocked. "
                 'Unfinished work remains recorded on disk.', route)
        cover(data, run, state['iteration'])


def session(root):
    """Return (loop state, run id) for the active loop, else None."""
    path = local(Path(root).resolve(), '.claude/esx-loop.local.md')
    if not path.exists():
        return None
    from ralph_stop import parse_state
    state = parse_state(path.read_text())
    if state['active'] != 'true':
        return None
    match = re.search(r'(?m)^run_id:\s*([^\s]+)', state['header'])
    # Existing deployments use the fixed header (minus the counter) as identity.
    return state, match[1] if match else digest([state['limit'], state['promise'], state['prompt']])[:24]


def active_outage(data, provider, run):
    """The active outage recorded for this provider in this loop run, if any."""
    return next((o for o in data.get('outages', {}).values() if o['status'] == 'active'
                 and o['provider'] == provider and o['run'] == run), None)


def expired(outage, iteration):
    return iteration >= outage['bound_iteration'] + OUTAGE_RENEW_ITERATIONS


def cover(data, run, iteration):
    """Mark pending events of a provider under a current, unexpired outage."""
    for e in sorted(data['events'].values(), key=lambda e: (e['created_at'], e['id'])):
        outage = active_outage(data, e['provider'], run) if e['status'] == 'pending' else None
        if outage and not expired(outage, iteration):
            e['status'], e['outage'] = 'outage_covered', outage['id']
            outage['covered'].append(e['id'])
            outage['covered_since_probe'] += 1


def probe_due(outage, iteration):
    """Why a re-probe is required now, or None."""
    if expired(outage, iteration):
        return (f"outage bound of {OUTAGE_RENEW_ITERATIONS} iterations from iteration "
                f"{outage['bound_iteration']} is spent; renew it with fresh probe evidence or clear it")
    if iteration > outage['last_probe_iteration']:
        return f"no probe recorded in loop iteration {iteration}"
    if outage['covered_since_probe'] >= OUTAGE_PROBE_EVENTS:
        return f"{outage['covered_since_probe']} events covered since the last probe (limit {OUTAGE_PROBE_EVENTS})"
    return None


def _probe_input(tool, evidence):
    require(isinstance(tool, str) and tool.strip(), 'record the actual probe tool or tool-discovery action')
    require(isinstance(evidence, str) and len(evidence.strip()) >= 20, 'provide concrete probe evidence')


def outage(root, provider, tool, evidence):
    """Declare, or renew with fresh evidence, a session-scoped provider outage."""
    root = Path(root).resolve()
    current = session(root)
    require(current is not None, 'an outage is session-scoped; it requires an active ESX loop')
    state, run = current
    _probe_input(tool, evidence)
    iteration = state['iteration']
    with ledger(root) as data:
        outages = data.setdefault('outages', {})
        o = active_outage(data, provider, run)
        probe = {'at': now(), 'iteration': iteration, 'tool': tool, 'evidence': evidence}
        if o is None:
            identity = digest(['outage', provider, run, probe['at']])[:24]
            o = outages[identity] = {'id': identity, 'provider': provider, 'run': run, 'status': 'active',
                                     'declared_at': probe['at'], 'declared_iteration': iteration,
                                     'covered': [], 'covered_since_probe': 0, 'probes': []}
            probe['result'] = 'declared'
        else:
            probe['result'] = 'renewed'
        o['probes'].append(probe)
        o.update(bound_iteration=iteration, last_probe_iteration=iteration)
        cover(data, run, iteration)
        o['covered_since_probe'] = 0  # events queued before this probe are covered by it
        return o


def reprobe(root, provider, tool, result, evidence):
    """Record a forced re-probe: ``down`` keeps the outage, ``up`` clears it."""
    root = Path(root).resolve()
    current = session(root)
    require(current is not None, 'an outage is session-scoped; it requires an active ESX loop')
    state, run = current
    _probe_input(tool, evidence)
    require(result in ('down', 'up'), 'probe result must be down or up')
    iteration = state['iteration']
    with ledger(root) as data:
        o = active_outage(data, provider, run)
        require(o is not None, f'no active {provider} outage in this loop run')
        if result == 'down':
            require(not expired(o, iteration), 'outage bound is spent; renew it with notifications.py outage')
        o['probes'].append({'at': now(), 'iteration': iteration, 'tool': tool, 'result': result, 'evidence': evidence})
        o.update(last_probe_iteration=iteration, covered_since_probe=0)
        if result == 'up':
            o.update(status='cleared', cleared_at=o['probes'][-1]['at'], cleared_iteration=iteration)
        return o


def outage_notice(root):
    """Instruction for any active outage in this run whose re-probe is due."""
    root = Path(root).resolve()
    path = local(root, LEDGER)
    current = session(root)
    if current is None or not path.exists():
        return None
    state, run = current
    messages = []
    for o in json.loads(path.read_text()).get('outages', {}).values():
        if o['status'] == 'active' and o['run'] == run:
            reason = probe_due(o, state['iteration'])
            if reason:
                messages.append(f"NEXT: re-probe the {o['provider']} provider (outage {o['id']}): {reason}. "
                                f"Attempt the provider, then run tools/esx/notifications.py reprobe --provider "
                                f"{o['provider']} --tool ACTUAL_TOOL --result down|up --probe-evidence TEXT"
                                + (', or renew with notifications.py outage' if expired(o, state['iteration']) else '')
                                + '; then run --next again.')
    return ' '.join(messages) or None


def status(root):
    """Ledger plus counts that separate outage coverage from per-event failures."""
    path = local(Path(root).resolve(), LEDGER)
    data = json.loads(path.read_text()) if path.exists() else {'events': {}}
    counts = {}
    for e in data['events'].values():
        counts[e['status']] = counts.get(e['status'], 0) + 1
    return dict(data, summary={'by_status': counts,
        'outage_covered': sorted(e['id'] for e in data['events'].values() if e['status'] == 'outage_covered'),
        'failed': sorted(e['id'] for e in data['events'].values() if e['status'] == 'failed'),
        'active_outages': sorted(o['id'] for o in data.get('outages', {}).values() if o['status'] == 'active')})


def pending(root):
    path = local(Path(root).resolve(), LEDGER)
    if not path.exists():
        return []
    events = [e for e in json.loads(path.read_text())['events'].values() if e['status'] == 'pending']
    return sorted(events, key=lambda e: (e['created_at'], e['id']))


def record(root, identity, response=None, disposition=None, detail=None, tool=None, authorization=None):
    """Attach an actual response or a concrete provider/authorization failure.

    The local receipt proves what was recorded; the provider owns delivery truth.
    It must contain an explicit successful message/channel or Slack timestamp.
    """
    with ledger(Path(root).resolve()) as data:
        require(identity in data['events'], 'unknown notification event')
        e = data['events'][identity]
        require(e['status'] != 'sent', 'event already delivered; do not post it again')
        require(isinstance(tool, str) and tool.strip(), 'record the attempted tool or tool-discovery action')
        attempt = {'at': now(), 'tool': tool}
        if response is not None:
            require(isinstance(authorization, str) and authorization.strip(), 'record applicable owner authorization')
            require(isinstance(response, dict) and not response.get('error') and response.get('ok') is not False,
                    'provider response reports an error or has invalid shape')
            if e['provider'] == 'slack':
                # Authenticated Slack MCP returns message_context; Web API uses ok/channel/ts.
                context = response.get('message_context', {})
                require(isinstance(context, dict), 'invalid Slack message_context')
                channel = context.get('channel_id') if context else response.get('channel')
                ts = context.get('message_ts') if context else response.get('ts')
                require(bool(context) or response.get('ok') is True, 'Slack API receipt requires ok=true')
                require(channel == e['channel'], 'receipt channel differs from the event destination')
                require(isinstance(ts, str) and re.fullmatch(r'\d{10}\.\d{6}', ts),
                        'Slack receipt requires the returned message timestamp')
            else:
                require(response.get('ok') is True and response.get('channel') == e['channel']
                        and response.get('message_id'), 'provider receipt needs success, destination and message_id')
            attempt.update(status='sent', response=response, authorization=authorization)
        else:
            require(disposition in ('failed', 'unavailable', 'unauthorized'), 'record a real delivery disposition')
            require(isinstance(detail, str) and len(detail.strip()) >= 20, 'provide concrete failure/discovery/authorization details')
            attempt.update(status=disposition, detail=detail)
        e['attempts'].append(attempt)
        e['status'] = attempt['status']
        return e


def notice(root):
    """Blocking instruction for --next: pending delivery, then any forced outage re-probe."""
    events = pending(root)
    message = None
    if events:
        message = ('NEXT: deliver ' + str(len(events)) + ' pending loop notification(s) using '
                   '.claude/skills/esx-announce/SKILL.md; run tools/esx/notifications.py pending. '
                   'Record the real receipt or concrete provider failure (or a session outage), '
                   'then run --next again.')
    probe = outage_notice(root)
    return ' '.join(m for m in (message, probe) if m) or None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('pending')
    sub.add_parser('sync')
    sub.add_parser('status')
    r = sub.add_parser('record')
    r.add_argument('event')
    r.add_argument('--response-file', type=Path)
    r.add_argument('--disposition', choices=('failed', 'unavailable', 'unauthorized'))
    r.add_argument('--detail')
    r.add_argument('--tool', required=True)
    r.add_argument('--authorization')
    o = sub.add_parser('outage', help='declare or renew a session-scoped provider outage')
    o.add_argument('--provider', required=True)
    o.add_argument('--tool', required=True)
    o.add_argument('--probe-evidence', required=True)
    q = sub.add_parser('reprobe', help='record a forced outage re-probe; result up clears the outage')
    q.add_argument('--provider', required=True)
    q.add_argument('--tool', required=True)
    q.add_argument('--result', required=True, choices=('down', 'up'))
    q.add_argument('--probe-evidence', required=True)
    args = p.parse_args(argv)
    try:
        if args.action in ('sync', 'pending'):
            synchronize(args.root)
            result = pending(args.root)
        elif args.action == 'status':
            result = status(args.root)
        elif args.action == 'outage':
            result = outage(args.root, args.provider, args.tool, args.probe_evidence)
        elif args.action == 'reprobe':
            result = reprobe(args.root, args.provider, args.tool, args.result, args.probe_evidence)
        else:
            result = record(args.root, args.event,
                json.loads(args.response_file.read_text()) if args.response_file else None,
                args.disposition, args.detail, args.tool, args.authorization)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'ESX notifications: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
