"""Claude adapter: route session context, capture completions and check records.

This adapter captures reports and routes session context. The separate ESX Stop
adapter drives its own finite loop. Read-only roles may write local evidence.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import uuid
from project import STATE, local, now
from records import validate_records


INFLIGHT = STATE + '/native_inflight'


def inflight_path(root, agent_id):
    """Marker for one running Agent-tool subagent; the id is a CLI-issued token."""
    if not isinstance(agent_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', agent_id):
        raise ValueError('subagent event lacks a usable agent_id')
    return local(Path(root), f'{INFLIGHT}/{agent_id}.json')


def started(root, event):
    """Record a native subagent launch so the Stop hook can see work in flight."""
    path = inflight_path(root, event.get('agent_id'))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'agent_id': event.get('agent_id'), 'agent_type': event.get('agent_type'),
                                'session_id': event.get('session_id'), 'started_at': now()}))


def capture(root, event):
    """Persist the exact final report and distinguish completed, incomplete and failed."""
    from agent_runtime import stop_record
    try:
        return stop_record(Path(root).resolve(), event)
    finally:
        try:
            inflight_path(root, event.get('agent_id')).unlink(missing_ok=True)
        except ValueError:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event', choices=('session-start', 'subagent-start', 'subagent-stop', 'records'))
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('CLAUDE_PROJECT_DIR', Path(__file__).resolve().parents[2])))
    args = parser.parse_args()
    try:
        if args.event == 'session-start':
            print('Read CLAUDE.md, .claude/ESX-team/ARCHITECT.md and esx/project_profile.md. For an active loop run python3 tools/esx/loop_gate.py --next. Use docs/code_map.md before broad source reads.')
        elif args.event == 'subagent-start':
            if os.environ.get('ESX_AGENT_RUNTIME_CHILD') != '1':
                try:
                    event = json.load(sys.stdin)
                except ValueError:
                    event = {}
                started(args.root.resolve(), event)
        elif args.event == 'subagent-stop':
            try:
                event = json.load(sys.stdin)
            except ValueError:
                event = {}
            capture(args.root.resolve(), event)
        else:
            validate_records(args.root.resolve())
            if os.environ.get('ESX_AGENT_RUNTIME_CHILD') != '1':
                import notifications
                notifications.synchronize(args.root.resolve())
                message = notifications.notice(args.root.resolve())
                if message:
                    print(message)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Preserve the session so Arch can repair the record; closeout fails when
        # required completion evidence or consistent project records are missing.
        print(f'ESX hook needs attention: {exc}', file=sys.stderr)
