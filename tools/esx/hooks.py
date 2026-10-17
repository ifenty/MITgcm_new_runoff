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
    """Record a native subagent launch so the Stop hook can see work in flight.

    Returns context for the subagent: its own runtime id, which exists only once
    it has been launched and so can never be written into its brief, and a
    warning when the iteration it is joining was never start-checked.
    """
    path = inflight_path(root, event.get('agent_id'))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'agent_id': event.get('agent_id'), 'agent_type': event.get('agent_type'),
                                'session_id': event.get('session_id'), 'started_at': now()}))
    context = (f"ESX: your runtime agent id is {event['agent_id']}. Use it as --owner for tools/esx/verify.py; "
               'evidence sealed under any other owner is refused at closeout.')
    start_path = local(Path(root), f'{STATE}/issue-start.json')
    if event.get('agent_type') in ('bob', 'richard') and start_path.is_file():
        import loop_iteration
        start = json.loads(start_path.read_text())
        history = [json.loads(line) for line in local(Path(root), f'{STATE}/loop_history.jsonl').read_text().splitlines()
                   if line.strip()] if local(Path(root), f'{STATE}/loop_history.jsonl').is_file() else []
        if (start.get('state_version', 1) >= 2 and not loop_iteration.finished(start, history)
                and not loop_iteration.start_status(root, start)['validated']):
            context += (f" ESX warning: iteration {start.get('id')} has no --check-start receipt. Do no work on it; "
                        'report this to the coordinator, who must run tools/esx/loop_gate.py --check-start first.')
    return context


def kind_notice(root, event):
    """One line when an edit makes closeout require a kind amendment, else None.

    The active issue is not scientific_change but the edited file is in the
    scientific inventory (source, tests, configuration paths and esx/project.json),
    so the scientific signature moves and closeout will refuse the kind. Seen
    otherwise only at --check-done. A membership test on one path, not a tree walk.
    """
    from project import config, selected
    root = Path(root).resolve()
    given = ((event.get('tool_input') or {}).get('file_path') or (event.get('tool_input') or {}).get('notebook_path')
             if isinstance(event, dict) else None)
    start_path = local(root, f'{STATE}/issue-start.json')
    if not isinstance(given, str) or not start_path.is_file():
        return None
    start = json.loads(start_path.read_text())
    kind = (start.get('workflow') or {}).get('kind')
    if kind == 'scientific_change':
        return None
    history = local(root, f'{STATE}/loop_history.jsonl')
    rows = [json.loads(line) for line in history.read_text().splitlines() if line.strip()] if history.is_file() else []
    import loop_iteration
    if loop_iteration.finished(start, rows):
        return None
    path = Path(given)
    try:
        name = (path if path.is_absolute() else root / path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None
    if not selected(name, config(root, ready=False), True):
        return None
    return (f"ESX notice: {name} is in the scientific inventory, but {start.get('id')} is a {kind} issue; closeout will "
            'require a kind amendment (loop_lifecycle.py amend-kind --kind scientific_change --reason "..."), '
            'which adds the scientific reviews and final qualification. Revert the edit or plan for that now.')


def whoami(root, role):
    """The runtime id of the one running native subagent of ``role``, for --owner.

    Fails when none or several are running, because a guess would seal evidence
    under the wrong identity.
    """
    folder = local(Path(root), INFLIGHT)
    found = []
    for marker in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        try:
            value = json.loads(marker.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(value, dict) and value.get('agent_type') == role:
            found.append({'agent_id': value.get('agent_id'), 'started_at': value.get('started_at')})
    if len(found) != 1:
        raise ValueError(f'{len(found)} running {role} subagents recorded; the id cannot be chosen for you'
                         + (': ' + json.dumps(found) if found else ''))
    return found[0]['agent_id']


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
    parser.add_argument('event', choices=('session-start', 'subagent-start', 'subagent-stop', 'records', 'whoami'))
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('CLAUDE_PROJECT_DIR', Path(__file__).resolve().parents[2])))
    parser.add_argument('--role', help='whoami: the role whose running native subagent id is wanted')
    args = parser.parse_args()
    if args.event == 'whoami':
        try:
            print(whoami(args.root.resolve(), args.role))
            raise SystemExit(0)
        except (ValueError, OSError) as exc:
            print(f'ESX whoami: {exc}', file=sys.stderr)
            raise SystemExit(1)
    try:
        if args.event == 'session-start':
            print('Read CLAUDE.md, .claude/ESX-team/ARCHITECT.md and esx/project_profile.md. For an active loop run python3 tools/esx/loop_gate.py --next. Use docs/code_map.md before broad source reads.')
        elif args.event == 'subagent-start':
            if os.environ.get('ESX_AGENT_RUNTIME_CHILD') != '1':
                try:
                    event = json.load(sys.stdin)
                except ValueError:
                    event = {}
                print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SubagentStart',
                                                         'additionalContext': started(args.root.resolve(), event)}}))
        elif args.event == 'subagent-stop':
            try:
                event = json.load(sys.stdin)
            except ValueError:
                event = {}
            record = capture(args.root.resolve(), event)
            if isinstance(record, dict) and record.get('status') != 'completed':
                # Tell the coordinator at once; a broken report otherwise surfaces only at closeout.
                print(f"ESX: the {record.get('agent_type')} stop {record.get('event_id')} was recorded "
                      f"{record.get('status')}: {record.get('error')}", file=sys.stderr)
        else:
            validate_records(args.root.resolve())
            try:
                event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
                notice = kind_notice(args.root, event)
                if notice:
                    print(notice)
            except Exception:  # an advisory line must never fail the hook
                pass
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
