"""Retained roles run in `auto` unless the loop chooses `bypassPermissions` or `inherit`.

A headless `claude --print` ignores permissions.defaultMode from the settings files, so a role ran in `default`
mode and most compound commands were denied (TEAM-AGENT-PERMISSION-DENIALS-001). The launcher passes a mode
explicitly: `auto` by default, `bypassPermissions` on request, or the settings' defaultMode on `inherit`.
"""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/esx'))
import agent_runtime  # noqa: E402
import loop_control  # noqa: E402


def _settings(path, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'permissions': {'defaultMode': mode}}))


def _loop(root, extra=''):
    (root / '.claude').mkdir(parents=True, exist_ok=True)
    (root / '.claude/esx-loop.local.md').write_text(
        '---\nactive: true\niteration: 1\nmax_iterations: 3\n' + extra + '---\nprompt\n')


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / 'home'))
    return tmp_path / 'proj'


def test_default_is_auto_whatever_the_settings_say(root):
    assert agent_runtime.role_permission_mode(root) == 'auto'
    _settings(root / '.claude/settings.local.json', 'bypassPermissions')
    assert agent_runtime.role_permission_mode(root) == 'auto'
    _loop(root)
    assert agent_runtime.role_permission_mode(root) == 'auto'


def test_loop_can_choose_bypass(root):
    _loop(root, 'permission_mode: bypassPermissions\n')
    assert agent_runtime.role_permission_mode(root) == 'bypassPermissions'


def test_inherit_follows_the_settings_local_over_project_over_user(root, tmp_path):
    _loop(root, 'permission_mode: inherit\n')
    assert agent_runtime.role_permission_mode(root) == 'auto'
    _settings(tmp_path / 'home/settings.json', 'bypassPermissions')
    assert agent_runtime.role_permission_mode(root) == 'bypassPermissions'
    _settings(root / '.claude/settings.json', 'auto')
    assert agent_runtime.role_permission_mode(root) == 'auto'
    _settings(root / '.claude/settings.local.json', 'bypassPermissions')
    assert agent_runtime.role_permission_mode(root) == 'bypassPermissions'


def test_modes_that_cannot_run_shell_headless_fall_back_to_auto(root):
    """acceptEdits, dontAsk, plan, manual and `default` denied or could not run the shell commands (measured)."""
    for mode in ('acceptEdits', 'dontAsk', 'plan', 'manual', 'default', 'nonsense'):
        _loop(root, f'permission_mode: {mode}\n')
        assert agent_runtime.role_permission_mode(root) == 'auto'
        _loop(root, 'permission_mode: inherit\n')
        _settings(root / '.claude/settings.local.json', mode)
        assert agent_runtime.role_permission_mode(root) == 'auto'


def test_loop_control_validates_and_stores_permissions(root):
    _loop(root)
    loop_control.set_permissions(root, 'bypassPermissions')
    assert loop_control.permissions_of(root) == 'bypassPermissions'
    assert agent_runtime.role_permission_mode(root) == 'bypassPermissions'
    loop_control.set_permissions(root, 'inherit')
    assert loop_control.permissions_of(root) == 'inherit'
    loop_control.set_permissions(root, 'auto')
    assert loop_control.permissions_of(root) == 'auto'
    assert 'permission_mode' not in (root / '.claude/esx-loop.local.md').read_text()
    for bad in ('plan', 'dontAsk', 'yolo'):
        with pytest.raises(ValueError):
            loop_control.set_permissions(root, bad)


def test_launcher_always_passes_the_mode():
    source = Path(agent_runtime.__file__).read_text()
    assert 'command += ["--permission-mode", role_permission_mode(root)]' in source
