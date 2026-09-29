"""Sanitized runtime manifests, assessed session transitions and hook attribution.

Raw fingerprints retain byte-level audit identity. Canonical settings hashes
permit formatting-only changes. Every semantic change requires an issue- and
session-bound assessment with a recorded successful compatibility check.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def digest(value):
    """Hash JSON without persisting configuration values or credentials."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def manifest(paths):
    """Measure per-file canonical configuration and hashed top-level settings."""
    result = {}
    for raw in paths:
        path = Path(raw)
        if path.name in ('settings.json', 'settings.local.json'):
            value = json.loads(path.read_text()) if path.is_file() else {}
            if not isinstance(value, dict):
                raise ValueError('settings must contain a JSON object: ' + str(path))
            result[str(path)] = {'kind': 'settings', 'canonical': digest(value),
                                 'fields': {key: digest(v) for key, v in value.items()}}
        else:
            result[str(path)] = {'kind': 'instruction', 'canonical':
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None}
    return result


def changes(before, after):
    """Describe every measured difference without disclosing settings values."""
    if not before or not before.get('effective_manifest'):
        return [{'field': 'legacy_contract', 'before': None, 'after': after['sha256']}]
    result = []
    for key in ('binary', 'binary_sha256', 'version', 'environment', 'transport', 'permission_mode'):
        if before.get(key) != after.get(key):
            result.append(dict(field=key, before=digest(before.get(key)), after=digest(after.get(key))))
    left, right = before['effective_manifest'], after['effective_manifest']
    for name in sorted(left.keys() | right.keys()):
        a, b = left.get(name, {}), right.get(name, {})
        if a == b:
            continue
        keys = sorted(a.get('fields', {}).keys() | b.get('fields', {}).keys())
        changed = [key for key in keys if a.get('fields', {}).get(key) != b.get('fields', {}).get(key)]
        result.append(dict(field=name, settings_fields=changed,
                           before=a.get('canonical'), after=b.get('canonical')))
    return result


def compatibility(root, state, contract, assessment=None):
    """Allow identical effective configuration or a sealed, explicitly assessed delta."""
    before = state.get('runtime_contract')
    delta = changes(before, contract)
    if state['runtime_fingerprint'] == contract['sha256']:
        return {'classification': 'unchanged', 'changes': []}
    if before and before.get('effective_manifest') and not delta:
        return {'classification': 'formatting_only', 'changes': []}
    expected = dict(session_id=state['session_id'], issue_id=state['issue_id'],
                    before=state['runtime_fingerprint'], after=contract['sha256'], changes=delta)
    if assessment is None:
        raise ValueError('runtime contract changed; use assess-transition with exact session, delta and '
                         'compatibility evidence, then followup --transition REF.json: ' + json.dumps(delta))
    import workflow_records
    if not isinstance(assessment, dict) or set(assessment) != {'path', 'sha256'}:
        raise ValueError('transition must be a sealed assessment reference')
    path = workflow_records.local_file(root, assessment['path'])
    if not assessment['path'].startswith('devel-loop/loop_state/runtime-transitions/'):
        raise ValueError('transition reference must remain in runtime-transitions')
    record = json.loads(path.read_text())
    if digest(record) != assessment['sha256'] or any(record.get(k) != v for k, v in expected.items()):
        raise ValueError('transition identity, delta or hash mismatch; reassess the current configuration')
    validate_assessment(root, record)
    return dict(classification='assessed', assessment=assessment, changes=delta,
                reason=record['reason'], check=record['check'])


def validate_assessment(root, record):
    """Require an explicit decision and a hash-bound compatibility check artifact."""
    import workflow_records
    if record.get('decision') != 'resume' or record.get('assessor') != 'arch' or len(record.get('reason', '').strip()) < 40:
        raise ValueError('assessment requires Arch decision=resume and a substantive reason')
    check = record.get('check') or {}
    if check.get('executed') is not True or type(check.get('exit')) is not int or check['exit'] != 0 or not check.get('command'):
        raise ValueError('assessment requires an executed successful compatibility check')
    artifact = check.get('evidence') or {}
    path = workflow_records.local_file(root, artifact.get('path'))
    if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.get('sha256'):
        raise ValueError('compatibility check evidence hash mismatch')
    if record.get('changes') and record['changes'][0].get('field') == 'legacy_contract':
        raise ValueError('legacy session has no effective manifest; use an explicit replacement')


def assess(root, state, contract, judgment):
    """Seal a human assessment against the currently observed old/new configuration."""
    import workflow_records
    record = dict(judgment, session_id=state['session_id'], issue_id=state['issue_id'],
                  before=state['runtime_fingerprint'], after=contract['sha256'],
                  changes=changes(state.get('runtime_contract'), contract))
    validate_assessment(root, record)
    sha = digest(record)
    name = f'devel-loop/loop_state/runtime-transitions/{sha}.json'
    workflow_records.write_output(root, name, record)
    return {'path': name, 'sha256': sha}


def preflight_event(root, kwargs, error, duration_seconds=0):
    """Record a rejected dispatch separately from actual role completions."""
    import workflow_records
    path = workflow_records.local_file(root, 'devel-loop/loop_state/runtime-preflight.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event_id=uuid.uuid4().hex, status='preflight_rejected', timestamp=time.time(),
                  session_id=kwargs.get('session'), issue_id=kwargs.get('issue'), role=kwargs.get('role'),
                  category='configuration_recovery' if 'runtime' in str(error) else 'packet_repair',
                  error=str(error), duration_seconds=duration_seconds, counts_as_correction=False)
    data = (json.dumps(record) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def hook_doctor(root, config_dir=None, event_id=None):
    """Attribute configured hooks without executing commands or reading credentials.

    Command bodies are returned as hashes; executable words identify the owner.
    This scan reports configuration only. Exit status and stderr must come from
    the exact failed invocation, rather than being inferred from configuration.
    """
    import shlex
    config_dir = Path(config_dir or os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude')))
    rows = []
    paths = [(config_dir / 'settings.json', 'user'), (Path(root) / '.claude/settings.json', 'project'),
             (Path(root) / '.claude/settings.local.json', 'local')]
    installed = config_dir / 'plugins/installed_plugins.json'
    if installed.is_file():
        registry = json.loads(installed.read_text()).get('plugins', {})
        for name, entries in registry.items():
            for entry in entries if isinstance(entries, list) else []:
                directory = entry.get('installPath')
                if directory:
                    paths.append((Path(directory) / 'hooks/hooks.json', 'plugin:' + name))
    for path, scope in paths:
        if not path.is_file():
            continue
        value = json.loads(path.read_text())
        for event, groups in value.get('hooks', {}).items():
            for group in groups:
                for hook in group.get('hooks', []):
                    command = hook.get('command', '')
                    try:
                        words = shlex.split(command)
                    except ValueError:
                        words = []
                    rows.append(dict(source=str(path), scope=scope, event=event, type=hook.get('type'),
                                     executable=words[0] if words else None, command_sha256=digest(command),
                                     process_status='unmeasured', stderr='not inspected', signal=None))
    process = None
    if event_id is not None:
        import workflow_records
        events = workflow_records.read_jsonl(Path(root) / workflow_records.STATE / 'dispatch_log.jsonl')
        matches = [e for e in events if e.get('event_id') == event_id]
        if len(matches) != 1:
            raise ValueError('hook diagnosis needs one exact dispatch event')
        event = matches[0]
        code = event.get('returncode')
        process = {key: event.get(key) for key in ('event_id', 'agent_id', 'agent_type', 'status', 'returncode')}
        process['signal'] = -code if isinstance(code, int) and code < 0 else None
        process['shell_signal_hint'] = code - 128 if isinstance(code, int) and 128 < code < 193 else None
        reference = event.get('stderr')
        if isinstance(reference, dict):
            path = workflow_records.local_file(root, reference['path'])
            data = path.read_bytes()
            process['stderr'] = {'path': reference['path'], 'bytes': len(data),
                'sha256': hashlib.sha256(data).hexdigest(), 'empty': not bool(data)}
        process['attribution'] = 'Process failure alone does not identify the failing hook; match the exact CLI diagnostic.'
    return {'hooks': rows, 'process': process, 'limits': 'Read-only configuration inventory; installed plugins may be disabled. '
            'Inspect exact runtime stderr and OS crash reports for process failures. No hooks were executed.'}
