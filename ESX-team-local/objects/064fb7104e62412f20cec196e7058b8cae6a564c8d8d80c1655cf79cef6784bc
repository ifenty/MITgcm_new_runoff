#!/usr/bin/env python3
"""Enforce tool budgets and isolate Bash timeouts without widening permissions.

Claude PreToolUse updatedInput rewrites Bash through bounded_command, and Claude
Code evaluates permissions against the REWRITTEN string, which no project allow
rule can match (every headless Bash call was denied; TEAM-RUNTIME-PERMDENIED-CRASH-001).
The hook therefore judges the original command with permission_match against the
merged settings. It wraps (and explicitly allows) only a command those settings
already allow; a settings deny is returned as deny. Any other command passes
through unwrapped so Claude's own check (read-only auto-approval or denial)
applies unchanged. Under bypassPermissions every command is wrapped, since
Claude would run it anyway. Unwrapped commands keep the launcher watchdog's
turn-level bound. ESX_RUNTIME_CONTEXT is supplied by the launcher.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import permission_match
import team_budget


def handle(event, context):
    root = Path(context['root'])
    copilot = 'toolName' in event
    if copilot:
        raw = event.get('toolArgs', {})
        value = json.loads(raw) if isinstance(raw, str) else raw
        event = {'tool_name': 'Bash' if event['toolName']=='bash' else event['toolName'],
                 'tool_input': value,
                 'tool_use_id': hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()}
    try:
        team_budget.allow_tool(root, context['event_id'], event['tool_use_id'])
    except (ValueError, KeyError) as exc:
        denied = {'permissionDecision':'deny', 'permissionDecisionReason':str(exc)}
        return denied if copilot else {'hookSpecificOutput':dict(denied,hookEventName='PreToolUse')}
    out = {'hookEventName': 'PreToolUse'}
    if event.get('tool_name') == 'Bash':
        value = dict(event['tool_input'])
        command = value['command']
        decision = permission_match.decide(command, permission_match.load_rules(root))
        if decision == 'deny':
            denied = {'permissionDecision': 'deny',
                      'permissionDecisionReason': 'denied by project permission settings'}
            return denied if copilot else {'hookSpecificOutput': dict(denied, hookEventName='PreToolUse')}
        if decision != 'allow' and event.get('permission_mode') != 'bypassPermissions':
            # Leave the command as written so Claude's permission check sees it.
            return {} if copilot else {'hookSpecificOutput': out}
        if decision == 'allow':
            out['permissionDecision'] = 'allow'
            out['permissionDecisionReason'] = 'original command matches project allow rules'
        value['command'] = shlex.join([sys.executable, str(Path(__file__).with_name('bounded_command.py')),
                                      '--timeout', str(context['tool_timeout']), '--folder', context['folder'],
                                      '--tool-id', event['tool_use_id'], '--', '/bin/bash', '-c', command])
        # Background work can escape task lifetime and cost attribution.
        if copilot:
            value['mode'] = 'sync'
            return {'modifiedArgs': value}
        value['run_in_background'] = False
        out['updatedInput'] = value
    return {} if copilot else {'hookSpecificOutput': out}


if __name__ == '__main__':
    try:
        path = os.environ.get('ESX_RUNTIME_CONTEXT')
        print(json.dumps(handle(json.load(sys.stdin), json.loads(Path(path).read_text())) if path else {}))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('ESX budget hook cannot establish bounds: ' + str(exc), file=sys.stderr)
        raise SystemExit(2)
