#!/usr/bin/env python3
"""Preserve bounded Ralph continuation and record explicit termination reasons.

Configure this portable project Stop hook to own its separate ESX loop state.
Only assistant text in the current user turn can fulfill a tagged completion
promise. Transcript failures continue within the saved iteration budget. Invalid
state or a failed state write suspends with preserved evidence and a visible
reason. Tests in the deployment kit: tests/test_ralph.py.
"""
from contextlib import contextmanager
import fcntl
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid


def log(root, kind, iteration, reason):
    """Append a durable decision; report a write failure to the hook caller."""
    text = f'{dt.datetime.now(dt.timezone.utc).isoformat()} {kind} iteration={iteration} {reason}\n'
    try:
        with (root / '.claude/esx-loop-exit.log').open('a') as handle:
            handle.write(text)
    except OSError as exc:
        print(f'ESX loop could not save its decision: {exc}; {text}', file=sys.stderr)


def parse_state(text):
    """Parse the plugin's scalar frontmatter while preserving the prompt bytes."""
    match = re.fullmatch(r'---\r?\n(.*?)\r?\n---\r?\n(.*)', text, re.S)
    if not match:
        raise ValueError('state requires opening and closing frontmatter delimiters')
    fields = {}
    for line in match[1].splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            key, value = key.strip(), value.strip()
            if key in fields:
                raise ValueError(f'duplicate state field {key}')
            fields[key] = value
    for key in ('iteration', 'max_iterations'):
        if not re.fullmatch(r'[0-9]+', fields.get(key, '')):
            raise ValueError(f'{key} must be an explicit nonnegative integer')
    if int(fields['max_iterations']) <= 0:
        raise ValueError('max_iterations must be positive; ESX loops require a finite budget')
    if not match[2].strip():
        raise ValueError('state contains no continuation prompt')
    promise = fields.get('completion_promise', 'null')
    if promise.startswith('"'):
        try:
            promise = json.loads(promise)
        except ValueError as exc:
            raise ValueError('completion_promise has invalid quoted text') from exc
    elif len(promise) >= 2 and promise.startswith("'") and promise.endswith("'"):
        promise = promise[1:-1].replace("''", "'")
    if promise in ('null', '', None):
        promise = None
    if promise is not None and not isinstance(promise, str):
        raise ValueError('completion_promise must be text or null')
    return {'iteration': int(fields['iteration']), 'limit': int(fields['max_iterations']),
            'promise': promise, 'prompt': match[2], 'header': match[1],
            'active': fields.get('active', 'true'), 'header_fields': fields}


def current_text(path):
    """Read recent assistant text after the last user boundary in bounded memory.

    A truncated tail without a user boundary cannot establish a current promise.
    Malformed records also disable promise detection for this turn. The caller
    can still continue with a valid state file.
    """
    with Path(path).open('rb') as handle:
        size = handle.seek(0, 2)
        offset = max(0, size - 2 * 1024 * 1024)
        handle.seek(offset)
        if offset:
            handle.readline()
        lines = handle.read().decode('utf-8').splitlines()
    texts, last_text_message, boundary = [], None, offset == 0
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError('transcript records must be objects')
        message = row.get('message', {})
        if not isinstance(message, dict):
            continue
        role = message.get('role', row.get('role', row.get('type')))
        content = message.get('content', [])
        if role == 'user':
            # Tool results share the user role but belong to the same user turn.
            if isinstance(content, list) and content and all(
                    isinstance(c, dict) and c.get('type') == 'tool_result' for c in content):
                continue
            texts, last_text_message, boundary = [], None, True
        elif role == 'assistant':
            parts = []
            if isinstance(content, str):
                parts = [content]
            elif isinstance(content, list):
                parts = [c['text'] for c in content if isinstance(c, dict)
                         and c.get('type') == 'text' and isinstance(c.get('text'), str)]
            if parts:
                # Claude can serialize one message as several content-block
                # records sharing message.id. Retain all text in that message.
                # An id-less record is one independent text-bearing message.
                identity = message.get('id') or object()
                if identity != last_text_message:
                    texts = []
                texts.extend(parts)
                last_text_message = identity
    if not boundary:
        raise ValueError('recent transcript has no identifiable user-turn boundary')
    # Later thinking/tool records may carry no text. Earlier text-bearing
    # messages have been discarded so their promises cannot fulfill this one.
    return '\n'.join(texts)


def archive(root, state, original, kind, iteration, reason):
    """Preserve terminal state without recreating a cancelled or replaced loop."""
    if (Path(root) / 'esx/project.json').exists():
        try:
            import notifications
            notifications.synchronize(root, terminal=reason)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            log(root, 'NOTIFICATION_ERROR', iteration, str(exc))
    import team_retrospective
    team_retrospective.persist_debt(root, reason)
    kept = None
    if state.exists() and state.read_bytes() == original:
        kept = state.with_name(state.name + '.' + kind.lower() + '.' + uuid.uuid4().hex[:12])
        state.rename(kept)
    detail = reason + (f'; state preserved at {kept.name}' if kept else '; state already changed')
    log(root, kind, iteration, detail)
    print('ESX loop: ' + detail, file=sys.stderr)
    return {'systemMessage': 'ESX loop: ' + detail}


@contextmanager
def loop_lock(root):
    """Serialize start, cancellation and Stop; reject paths leaving the project."""
    from project import local
    path = local(Path(root).resolve(), '.claude/esx-loop.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


MAX_DISPATCH_WAITS = 3


def dispatch_in_flight(root):
    """True when a retained CLI turn for the active issue holds its turn lock.

    Native Agent-tool subagents are invisible here (the kit observes only their
    stop), so they still consume an iteration if Arch ends a turn to wait.
    """
    import fcntl as _fcntl
    start = Path(root) / 'devel-loop/loop_state/issue-start.json'
    sessions = Path(root) / 'devel-loop/loop_state/agent_runtime/sessions'
    try:
        issue = json.loads(start.read_text()).get('id') if start.is_file() else None
    except (OSError, ValueError):
        return False
    if not issue or not sessions.is_dir():
        return False
    for state_file in sessions.glob('*/session.json'):
        try:
            state = json.loads(state_file.read_text())
        except (OSError, ValueError):
            continue
        if state.get('issue_id') != issue or state.get('status') != 'running':
            continue
        lock = state_file.parent / '.turn.lock'
        if not lock.exists():
            continue
        with lock.open('a') as handle:
            try:
                _fcntl.flock(handle, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            _fcntl.flock(handle, _fcntl.LOCK_UN)
    return False


def step(root, hook_input):
    """Apply a Stop to the project's ESX state with one shared lifecycle lock."""
    if os.environ.get('ESX_AGENT_RUNTIME_CHILD') == '1':
        return {}
    root = Path(root).resolve()
    from project import local
    state = local(root, '.claude/esx-loop.local.md')
    if not state.exists():
        return {}
    with loop_lock(root):
        return _step_locked(root, hook_input)


def _step_locked(root, hook_input):
    """Apply one Stop event, returning JSON for Claude and preserving finite limits."""
    root = Path(root).resolve()
    state = root / '.claude/esx-loop.local.md'
    if not state.exists():
        return {}
    original = state.read_bytes()
    try:
        parsed = parse_state(original.decode('utf-8'))
    except (ValueError, UnicodeError) as exc:
        return archive(root, state, original, 'SUSPEND', '?', str(exc))
    n, limit = parsed['iteration'], parsed['limit']
    if parsed['active'] not in ('true', 'false'):
        return archive(root, state, original, 'SUSPEND', n, 'active must be true or false')
    if parsed['active'] == 'false':
        return {}
    if limit and n >= limit:
        # Reserve one bounded notification-only handoff after the last work turn.
        # The saved marker prevents unavailable delivery from extending work forever.
        if 'notification_finalizer: true' not in parsed['header'] and (root / 'esx/project.json').exists():
            import notifications
            try:
                notifications.synchronize(root, terminal=f'iteration budget {limit} reached')
                delivery_needed = bool(notifications.pending(root))
            except (ValueError, OSError, KeyError, TypeError) as exc:
                log(root, 'NOTIFICATION_ERROR', n, str(exc))
                delivery_needed = False
            if delivery_needed:
                from project import atomic_bytes
                header = parsed['header'] + '\nnotification_finalizer: true'
                atomic_bytes(state, ('---\n' + header + '\n---\n' + parsed['prompt']).encode())
                return {'decision': 'block', 'reason':
                    f'The loop reached its iteration budget of {limit}. This is not a cost or spend limit: '
                    'cost and effort are measured, never capped, and max_iterations is the only enforced '
                    'terminal bound. This is one notification-only finalization turn. '
                    'Use esx-announce to deliver pending notifications and record receipts or concrete failures. '
                    'Do not select issues, dispatch agents, run --next, or start another loop. '
                    'Report unfinished work and undelivered events, then stop without a completion promise.',
                    'systemMessage': f'Loop iteration budget {limit} reached; notification finalization only.'}
        return archive(root, state, original, 'END', n, f'iteration budget {limit} reached')
    if parsed['promise']:
        normalize = lambda value: ' '.join(value.split())
        def fulfilled(text):
            promises = re.findall(r'<promise>(.*?)</promise>', text or '', re.S)
            return any(normalize(p) == normalize(parsed['promise']) for p in promises)
        # The CLI supplies the current turn's final text directly; the transcript
        # file may lag behind it (TEAM-LOOP-PROMISE-FLUSH-RACE-001), so it is only
        # a fallback for runtimes that omit last_assistant_message.
        last = hook_input.get('last_assistant_message')
        if isinstance(last, str) and fulfilled(last):
            return archive(root, state, original, 'END', n, 'current completion promise fulfilled')
        try:
            if fulfilled(current_text(hook_input.get('transcript_path', ''))):
                return archive(root, state, original, 'END', n, 'current completion promise fulfilled')
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            log(root, 'DEGRADED', n, f'promise check unavailable; continuing within saved budget: {exc}')
    raw_waits = parsed['header_fields'].get('dispatch_waits', '0')
    waits = int(raw_waits) if raw_waits.isdigit() else MAX_DISPATCH_WAITS
    if waits < MAX_DISPATCH_WAITS and dispatch_in_flight(root):
        # Waiting on a live retained dispatch is not an iteration of work
        # (TEAM-LOOP-WAIT-BURNS-ITERATION-001); a small cap keeps the loop finite.
        header = parsed['header']
        if re.search(r'(?m)^dispatch_waits:', header):
            header = re.sub(r'(?m)^dispatch_waits:.*$', 'dispatch_waits: ' + str(waits + 1), header)
        else:
            header += '\ndispatch_waits: ' + str(waits + 1)
        from project import atomic_bytes
        atomic_bytes(state, ('---\n' + header + '\n---\n' + parsed['prompt']).encode())
        log(root, 'WAIT', n, f'retained dispatch in flight; iteration not advanced ({waits + 1}/{MAX_DISPATCH_WAITS})')
        return {'decision': 'block', 'reason': 'A retained ESX dispatch for the active issue is still running. '
                'Wait in-turn for its completion record (do not end the turn to wait), then continue with '
                'tools/esx/loop_gate.py --next.',
                'systemMessage': f'ESX iteration {n} held: dispatch in flight ({waits + 1}/{MAX_DISPATCH_WAITS}).'}
    header = re.sub(r'(?m)^[ \t]*iteration[ \t]*:[ \t]*[^\r\n]*$',
                    'iteration: ' + str(n + 1), parsed['header'])
    header = re.sub(r'(?m)^dispatch_waits:.*\n?', '', header).rstrip('\n')
    updated = ('---\n' + header + '\n---\n' + parsed['prompt']).encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=state.parent, prefix='.esx-counter-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(state.stat().st_mode & 0o777)
        if not state.exists() or state.read_bytes() != original:
            log(root, 'CANCELLED', n, 'state removed or replaced during Stop; continuation withheld')
            return {}
        os.replace(temporary, state)
    except OSError as exc:
        return archive(root, state, original, 'SUSPEND', n, f'cannot persist next iteration: {exc}')
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    log(root, 'CONTINUE', n + 1, f'budget={limit}')
    return {'decision': 'block', 'reason': parsed['prompt'],
            'systemMessage': f'ESX iteration {n + 1}; limit {limit}.'}


def project_root(hook_input):
    """Select the explicit project root without falling back after cancellation.

    The launcher hands off by absolute path, so the handler is reached from any
    directory and must decide for itself which project it is serving. An
    explicit signal is preferred over the bare working directory, and each
    candidate is authoritative even when its state has already been removed.
    This deliberately does NOT consider the handler's own repository: the hook
    serves whichever project raised the Stop event, so preferring the installing
    repository would let one project's loop drive another's state file.
    """
    # Explicit scratch/project selection is authoritative even without loop state.
    # A cancelled selected project must never fall through to another live loop.
    override = os.environ.get('ESX_RALPH_PROJECT_DIR')
    if override:
        return Path(override)
    for candidate in (os.environ.get('CLAUDE_PROJECT_DIR'), hook_input.get('cwd')):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def main():
    """Serve the project Stop hook; diagnostics use stderr, JSON uses stdout."""
    try:
        value = json.load(sys.stdin)
        if not isinstance(value, dict):
            value = {}
    except ValueError:
        value = {}
    try:
        result = step(project_root(value), value)
    except (OSError, ValueError) as exc:
        print(f'ESX loop suspended: could not process saved loop state: {exc}', file=sys.stderr)
        return 1
    if result:
        print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
