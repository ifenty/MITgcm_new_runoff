#!/usr/bin/env python3
"""Check the project ESX Stop hook and detect competing live loop state.

This structural check establishes configuration consistency. Behavioral tests
execute the handler in scratch projects; a live provider probe remains separate.
"""
import argparse
import json
import os
from pathlib import Path
from project import local

COMMAND = 'python3 "$CLAUDE_PROJECT_DIR/tools/esx/ralph_stop.py"'


def check(root):
    root = Path(root).resolve()
    settings_paths = [Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude'))) / 'settings.json',
                      local(root, '.claude/settings.json'), local(root, '.claude/settings.local.json')]
    commands = []
    all_settings = []
    for path in settings_paths:
        if path.is_file():
            settings = json.loads(path.read_text())
            if not isinstance(settings, dict):
                raise ValueError('Claude settings must be an object: ' + str(path))
            all_settings.append(settings)
            for group in settings.get('hooks', {}).get('Stop', []):
                for hook in group.get('hooks', []):
                    if hook.get('type') == 'command':
                        commands.append(hook.get('command', ''))
    matches = [value for value in commands if 'tools/esx/ralph_stop.py' in value]
    if matches != [COMMAND]:
        raise ValueError('configure exactly one canonical ESX Stop command: ' + COMMAND)
    for settings in all_settings:
        if settings.get('disableAllHooks'):
            raise ValueError('ESX Stop cannot run while disableAllHooks is enabled')
        if settings.get('allowManagedHooksOnly'):
            raise ValueError('project Stop hooks require a deployment compatible with allowManagedHooksOnly')
    if not local(root, 'tools/esx/ralph_stop.py').is_file():
        raise ValueError('ESX Stop handler is missing')
    if local(root, '.claude/esx-loop.local.md').exists() and local(root, '.claude/ralph-loop.local.md').exists():
        raise ValueError('ESX and external Ralph loop states coexist; cancel one owner')
    return {'status': 'PASS', 'owner': 'project ESX Stop', 'command': COMMAND}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.root)))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
