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
from ralph_stop import archive, loop_lock, parse_state

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
        return {'status': 'active' if parsed['active'] == 'true' else 'inactive', 'state': STATE,
                'iteration': parsed['iteration'], 'max_iterations': parsed['limit'],
                'completion_promise': parsed['promise']}


def cancel(root, reason='cancelled by the project owner'):
    if os.environ.get('ESX_AGENT_RUNTIME_CHILD') == '1':
        raise ValueError('retained role sessions cannot cancel the parent ESX loop')
    root = Path(root).resolve()
    with loop_lock(root):
        state = local(root, STATE)
        if not state.exists():
            return {'status': 'inactive', 'state': STATE}
        original = state.read_bytes()
        import notifications
        if local(root, 'esx/project.json').exists():
            notifications.synchronize(root, terminal='cancelled: ' + reason)
        try:
            iteration = parse_state(original.decode())['iteration']
        except (ValueError, UnicodeError):
            iteration = '?'
        archive(root, state, original, 'CANCELLED', iteration, reason)
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
    sub.add_parser('status')
    stop = sub.add_parser('cancel')
    stop.add_argument('--reason', default='cancelled by the project owner')
    args = parser.parse_args(argv)
    try:
        if args.action == 'run':
            result = run(args.root, args.max_iterations)
        elif args.action == 'start':
            result = start(args.root, args.prompt_file.read_text(), args.max_iterations, args.completion_promise)
        elif args.action == 'cancel':
            result = cancel(args.root, args.reason)
        else:
            result = status(args.root)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print('ESX loop: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
