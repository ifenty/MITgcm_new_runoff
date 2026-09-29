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


def capture(root, event):
    """Persist the exact final report and distinguish completed, incomplete and failed."""
    from agent_runtime import stop_record
    return stop_record(Path(root).resolve(), event)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event', choices=('session-start', 'subagent-stop', 'records'))
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('CLAUDE_PROJECT_DIR', Path(__file__).resolve().parents[2])))
    args = parser.parse_args()
    try:
        if args.event == 'session-start':
            print('Read CLAUDE.md, .claude/ESX-team/ARCHITECT.md and esx/project_profile.md. For an active loop run python3 tools/esx/loop_gate.py --next. Use docs/code_map.md before broad source reads.')
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
