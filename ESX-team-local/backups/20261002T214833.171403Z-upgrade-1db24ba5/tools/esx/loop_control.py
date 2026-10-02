#!/usr/bin/env python3
"""Start, inspect and cancel a finite project-owned ESX continuation loop.

The ESX state is separate from an external Ralph plugin's state. Lifecycle
operations share the Stop adapter's lock. Cancellation archives the prompt and
budget so a later hook cannot revive the removed state.
"""
import argparse
import json
import re
import os
from pathlib import Path
import sys
import uuid
from project import atomic_bytes, local
from ralph_stop import archive, cancel_request, log, loop_lock, parse_state, set_field, work_in_progress

ROOT = Path(__file__).resolve().parents[2]
STATE = '.claude/esx-loop.local.md'


def owner_session():
    """The Claude Code session running this command; only its Stop events drive the loop."""
    value = os.environ.get('CLAUDE_CODE_SESSION_ID', '').strip()
    return value if re.fullmatch(r'[A-Za-z0-9_-]{8,128}', value) else None


def bind_owner(root):
    """An explicit /esx-loop continuation from another session takes ownership of the loop."""
    owner = owner_session()
    if not owner:
        return None
    with loop_lock(root):
        state = local(root, STATE)
        if not state.exists():
            return None
        text = state.read_text()
        head, sep, body = text.partition('\n---\n')
        if re.search(r'(?m)^owner_session:\s*' + re.escape(owner) + r'\s*$', head):
            return owner
        head = re.sub(r'(?m)^owner_session:.*\n?', '', head).rstrip('\n') + '\nowner_session: ' + owner
        atomic_bytes(state, (head + sep + body).encode())
        return owner


def start(root, prompt, max_iterations=30, completion_promise='ESX-LOOP-NO-ACTIONABLE-WORK'):
    """Create a bounded state only after checking both possible loop owners."""
    root = Path(root).resolve()
    if os.environ.get('ESX_AGENT_RUNTIME_CHILD') == '1':
        raise ValueError('retained role sessions cannot own an ESX loop')
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('continuation prompt must be nonempty text')
    if type(max_iterations) is not int or max_iterations <= 0:
        raise ValueError('max_iterations must be a positive integer')
    if not isinstance(completion_promise, str) or not completion_promise.strip():
        raise ValueError('completion_promise must be nonempty text')
    from check_ralph_hook import check
    check(root)
    with loop_lock(root):
        state = local(root, STATE)
        if state.exists():
            raise ValueError('ESX state already exists; inspect or cancel it before starting a new loop')
        if local(root, '.claude/ralph-loop.local.md').exists():
            raise ValueError('external Ralph state exists; resolve that loop before starting ESX')
        owner = owner_session()
        data = ('---\nactive: true\nrun_id: ' + uuid.uuid4().hex + '\niteration: 1\nmax_iterations: ' + str(max_iterations)
                + '\ncompletion_promise: ' + json.dumps(completion_promise)
                + ('\nowner_session: ' + owner if owner else '') + '\n---\n' + prompt)
        atomic_bytes(state, data.encode())
        return {'status': 'active', 'state': STATE, 'iteration': 1, 'max_iterations': max_iterations}


def run(root, max_iterations=None):
    """Start or continue without resetting an existing budget or prompt."""
    root = Path(root).resolve()
    if os.environ.get('ESX_AGENT_RUNTIME_CHILD') == '1':
        raise ValueError('retained role sessions cannot own an ESX loop')
    from check_ralph_hook import check
    check(root)
    if local(root, '.claude/ralph-loop.local.md').exists():
        raise ValueError('external Ralph state exists; resolve that loop before starting ESX')
    current = status(root)
    if current['status'] == 'active':
        if max_iterations is not None and max_iterations != current['max_iterations']:
            raise ValueError('active loop budget differs; continue with run and no budget override')
        result = dict(current, action='continued', owner_session=bind_owner(root))
        if current.get('cancelling'):
            # An explicit continuation is the owner changing their mind.
            with loop_lock(root):
                state = local(root, STATE)
                parsed = parse_state(state.read_text())
                header = set_field(set_field(parsed['header'], 'stop_after_current', None), 'cancel_reason', None)
                atomic_bytes(state, ('---\n' + header + '\n---\n' + parsed['prompt']).encode())
            for key in ('cancelling', 'cancel_reason', 'finishing'):
                result.pop(key, None)
            result['cancellation'] = 'withdrawn'
    else:
        prompt = local(root, 'devel-loop/autonomous_prompt.md').read_text()
        result = dict(start(root, prompt, 30 if max_iterations is None else max_iterations), action='started')
    import notifications
    notifications.synchronize(root)
    result['next'] = 'Run tools/esx/loop_gate.py --next now and execute its instruction autonomously.'
    result['notifications'] = notifications.notice(root)
    return result


def status(root):
    root = Path(root).resolve()
    with loop_lock(root):
        state = local(root, STATE)
        if not state.exists():
            return {'status': 'inactive', 'state': STATE}
        parsed = parse_state(state.read_text())
        result = {'status': 'active' if parsed['active'] == 'true' else 'inactive', 'state': STATE,
                  'iteration': parsed['iteration'], 'max_iterations': parsed['limit'],
                  'completion_promise': parsed['promise']}
        pending = cancel_request(parsed)
        if pending is not None:
            result.update(cancelling=True, cancel_reason=pending, finishing=work_in_progress(root))
        return result


def status_line(root):
    """One line for the owner's screen: where the loop is and roughly how long remains."""
    import datetime as dt
    import notifications
    facts = notifications.loop_status(Path(root).resolve()) if local(Path(root).resolve(), 'esx/project.json').exists() else None
    stamp = dt.datetime.now().strftime('%H:%M')
    return f'ESX status {stamp}: ' + (facts['text'] if facts else 'no active loop.')


def heartbeat_notice(root):
    """Queue the channel heartbeat when it is due; say so, since a long wait fires no Stop event."""
    import notifications
    try:
        due = notifications.heartbeat(root) if local(root, 'esx/project.json').exists() else None
    except (ValueError, OSError, KeyError, TypeError):
        return ''
    return '\nHEARTBEAT DUE: deliver the queued loop_heartbeat (tools/esx/notifications.py pending).' if due else ''


def wake(root, minutes=None):
    """Sleep until the interval passes or the loop ends, then print the status line.

    Run it in the background before ending a turn that waits on a dispatch: its
    completion wakes the coordinator, which relays the line to the owner's screen
    and re-arms it. This is how a long wait still yields a status every interval.
    """
    import time
    root = Path(root).resolve()
    if minutes is None:
        minutes = 15
        config = local(root, 'esx/project.json')
        if config.exists():
            configured = (json.loads(config.read_text()).get('communication') or {}).get('screen_status_minutes')
            if type(configured) in (int, float) and configured > 0:
                minutes = configured
    deadline = time.monotonic() + max(float(minutes), 0) * 60
    while time.monotonic() < deadline and local(root, STATE).exists():
        time.sleep(min(5, max(deadline - time.monotonic(), 0)))
    return status_line(root) + heartbeat_notice(root)


def cancel(root, reason='cancelled by the project owner', now=False):
    """Stop the loop from starting another iteration; ``now`` abandons work in progress.

    A plain cancel never interrupts the active iteration. It marks the live state,
    the iteration runs on through review, closeout and its retrospective with the
    Stop hook, notifications and gates all still working, and the loop ends at the
    point where a new iteration would have started from the top.
    """
    if os.environ.get('ESX_AGENT_RUNTIME_CHILD') == '1':
        raise ValueError('retained role sessions cannot cancel the parent ESX loop')
    root = Path(root).resolve()
    with loop_lock(root):
        state = local(root, STATE)
        if not state.exists():
            return {'status': 'inactive', 'state': STATE}
        original = state.read_bytes()
        if not now:
            try:
                parsed = parse_state(original.decode())
            except (ValueError, UnicodeError):
                parsed = None
            unfinished = work_in_progress(root) if parsed and parsed['active'] == 'true' else None
            if unfinished:
                header = set_field(parsed['header'], 'stop_after_current', 'true')
                header = set_field(header, 'cancel_reason', json.dumps(reason))
                atomic_bytes(state, ('---\n' + header + '\n---\n' + parsed['prompt']).encode())
                log(root, 'CANCEL_REQUESTED', parsed['iteration'], f'{reason}; {unfinished} is finished first')
                return {'status': 'cancelling', 'state': STATE, 'finishing': unfinished,
                        'detail': f'No new iteration will start. {unfinished} continues through review, closeout '
                                  'and its retrospective, and the loop ends after that. Keep working with '
                                  'tools/esx/loop_gate.py --next. If that iteration will not be finished '
                                  '(it was abandoned, or its state is stale), the loop never reaches its '
                                  'end this way: run `loop_control.py abort` to stop immediately.'}
        try:
            iteration = parse_state(original.decode())['iteration']
        except (ValueError, UnicodeError):
            iteration = '?'
        # archive() queues the loop-end notice with this same reason text.
        archive(root, state, original, 'CANCELLED', iteration, 'cancelled: ' + reason)
        return {'status': 'cancelled', 'state': STATE}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    sub = parser.add_subparsers(dest='action', required=True)
    launch = sub.add_parser('run')
    launch.add_argument('--max-iterations', type=int)
    create = sub.add_parser('start')
    create.add_argument('--prompt-file', type=Path, required=True)
    create.add_argument('--max-iterations', type=int, default=30)
    create.add_argument('--completion-promise', default='ESX-LOOP-NO-ACTIONABLE-WORK')
    report = sub.add_parser('status')
    report.add_argument('--line', action='store_true', help="print the one-line owner status instead of JSON")
    alarm = sub.add_parser('wake', help='sleep, then print the status line; run in the background during a wait')
    alarm.add_argument('--minutes', type=float, help='default: communication.screen_status_minutes, else 15')
    stop = sub.add_parser('cancel', help='let the active iteration finish; start no new one')
    stop.add_argument('--reason', default='cancelled by the project owner')
    halt = sub.add_parser('abort', help='end the loop now, abandoning any iteration in progress')
    halt.add_argument('--reason', default='aborted by the project owner')
    args = parser.parse_args(argv)
    try:
        if args.action == 'run':
            result = run(args.root, args.max_iterations)
        elif args.action == 'start':
            result = start(args.root, args.prompt_file.read_text(), args.max_iterations, args.completion_promise)
        elif args.action == 'cancel':
            result = cancel(args.root, args.reason)
        elif args.action == 'abort':
            result = cancel(args.root, args.reason, now=True)
        elif args.action == 'wake':
            print(wake(args.root, args.minutes))
            return 0
        elif args.line:
            print(status_line(args.root))
            return 0
        else:
            result = status(args.root)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print('ESX loop: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
