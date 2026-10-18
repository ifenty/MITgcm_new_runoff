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
