"""The retained-role launcher must pass the owner's permissions.defaultMode to the CLI.

A headless `claude --print` ignores permissions.defaultMode from the settings files, so a role
ran in `default` mode and most compound commands were denied (TEAM-AGENT-PERMISSION-DENIALS-001).
`role_permission_mode` reads the merged setting; the launcher passes it as --permission-mode.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/esx'))
import agent_runtime  # noqa: E402


def _write(path, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'permissions': {'defaultMode': mode}} if mode else {'permissions': {}}))


def test_local_beats_project_beats_user(tmp_path, monkeypatch):
    user = tmp_path / 'home'
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(user))
    root = tmp_path / 'proj'
    _write(user / 'settings.json', 'plan')
    assert agent_runtime.role_permission_mode(root) == 'plan'
    _write(root / '.claude/settings.json', 'acceptEdits')
    assert agent_runtime.role_permission_mode(root) == 'acceptEdits'
    _write(root / '.claude/settings.local.json', 'bypassPermissions')
    assert agent_runtime.role_permission_mode(root) == 'bypassPermissions'


def test_unset_or_unknown_mode_keeps_the_cli_default(tmp_path, monkeypatch):
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / 'home'))
    root = tmp_path / 'proj'
    assert agent_runtime.role_permission_mode(root) is None
    _write(root / '.claude/settings.local.json', 'somethingElse')
    assert agent_runtime.role_permission_mode(root) is None
    (root / '.claude/settings.json').write_text('not json')
    assert agent_runtime.role_permission_mode(root) is None


def test_launcher_passes_the_mode():
    """The role branch of the launcher must use the function, so a refactor cannot drop the flag."""
    source = (Path(agent_runtime.__file__)).read_text()
    assert '"--permission-mode", role_permission_mode(root)' in source


def _loop_state(root, extra=''):
    (root / '.claude').mkdir(parents=True, exist_ok=True)
    (root / '.claude/esx-loop.local.md').write_text(
        '---\nactive: true\niteration: 1\nmax_iterations: 3\n' + extra + '---\nprompt\n')


def test_loop_choice_beats_settings_and_inherit_falls_through(tmp_path, monkeypatch):
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / 'home'))
    root = tmp_path / 'proj'
    _write(root / '.claude/settings.local.json', 'bypassPermissions')
    _loop_state(root, 'permission_mode: acceptEdits\n')
    assert agent_runtime.role_permission_mode(root) == 'acceptEdits'
    _loop_state(root, 'permission_mode: nonsense\n')
    assert agent_runtime.role_permission_mode(root) == 'bypassPermissions'
    _loop_state(root)
    assert agent_runtime.role_permission_mode(root) == 'bypassPermissions'


def test_legacy_default_in_settings_means_no_flag(tmp_path, monkeypatch):
    """`--permission-mode default` is not a CLI choice, so a settings file saying `default` must pass nothing."""
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / 'home'))
    root = tmp_path / 'proj'
    _write(root / '.claude/settings.json', 'plan')
    _write(root / '.claude/settings.local.json', 'default')
    assert agent_runtime.role_permission_mode(root) is None


def test_loop_control_validates_and_stores_permissions(tmp_path, monkeypatch):
    import loop_control
    import pytest
    root = tmp_path / 'proj'
    _loop_state(root)
    loop_control.set_permissions(root, 'dontAsk')
    assert loop_control.permissions_of(root) == 'dontAsk'
    assert agent_runtime.role_permission_mode(root) == 'dontAsk'
    loop_control.set_permissions(root, 'inherit')
    assert loop_control.permissions_of(root) == 'inherit'
    with pytest.raises(ValueError):
        loop_control.set_permissions(root, 'yolo')
