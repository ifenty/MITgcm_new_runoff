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
NATIVE_STALE_SECONDS = 6 * 3600
# No real iteration of work ends in under about 20 s, so this many loop advances
# inside the window means something other than the coordinator is driving the loop.
MAX_ADVANCES = 6
ADVANCE_WINDOW_SECONDS = 120


def clock():
    """Wall-clock seconds; a seam for tests of the advance-rate guard."""
    import time as _time
    return _time.time()


def set_field(header, key, value):
    """Return the frontmatter with one scalar field set (value None removes it)."""
    header = re.sub(r'(?m)^' + re.escape(key) + r':.*\n?', '', header).rstrip('\n')
    return header if value is None else header + '\n' + key + ': ' + str(value)


def cancel_request(parsed):
    """The owner's pending cancellation reason, or None (TEAM-LOOP-CANCEL-DRAIN-001)."""
    fields = parsed['header_fields']
    if fields.get('stop_after_current') != 'true':
        return None
    raw = fields.get('cancel_reason', '')
    try:
        reason = json.loads(raw) if raw.startswith('"') else raw
    except ValueError:
        reason = raw
    return reason if isinstance(reason, str) and reason.strip() else 'cancelled by the project owner'


def work_in_progress(root):
    """The issue whose iteration (or owed retrospective) is unfinished, else None.

    A cancellation never interrupts this work: the active iteration runs through
    review, closeout and its retrospective, and only then does the loop end.
    """
    root = Path(root)
    start_path = root / 'devel-loop/loop_state/issue-start.json'
    history_path = root / 'devel-loop/loop_state/loop_history.jsonl'
    try:
        start = json.loads(start_path.read_text()) if start_path.is_file() else None
        rows = [json.loads(line) for line in history_path.read_text().splitlines() if line.strip()] \
            if history_path.is_file() else []
    except (OSError, ValueError):
        return None
    if isinstance(start, dict) and start.get('id'):
        last = rows[-1] if rows else {}
        if (last.get('id'), last.get('timestamp')) != (start.get('id'), start.get('timestamp')):
            return start['id']
    if (root / 'esx/project.json').exists():
        try:
            import team_retrospective
            due = team_retrospective.pending(root)
            if due:
                return due['id']
        except (ValueError, OSError, KeyError, TypeError):
            return None
    return None


def native_running(root, session_id):
    """Agent-tool subagents this session launched that have not stopped.

    Markers come from the SubagentStart hook and are removed by SubagentStop. A
    marker older than NATIVE_STALE_SECONDS (a lost stop event) is ignored.
    """
    folder = Path(root) / 'devel-loop/loop_state/native_inflight'
    if not session_id or not folder.is_dir():
        return []
    running = []
    for marker in sorted(folder.glob('*.json')):
        try:
            value = json.loads(marker.read_text())
            age = clock() - marker.stat().st_mtime
        except (OSError, ValueError):
            continue
        if age < NATIVE_STALE_SECONDS and isinstance(value, dict) and value.get('session_id') == session_id:
            running.append({'agent_id': value.get('agent_id'), 'agent_type': value.get('agent_type') or 'subagent',
                            'minutes': int(age // 60)})
    return running


def native_in_flight(root, session_id):
    """True when this session launched an Agent-tool subagent that has not stopped."""
    return bool(native_running(root, session_id))


def dispatch_in_flight(root, session_id=None):
    """True when a retained CLI turn for the active issue holds its turn lock,
    or this session has a native Agent-tool subagent running (SubagentStart)."""
    return native_in_flight(root, session_id) or retained_in_flight(root)


def retained_in_flight(root):
    """True when a retained CLI turn for the active issue holds its turn lock."""
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


def finalize(root, state, original, parsed, kind, reason, explain, system_message):
    """End the loop, first reserving one notification-only turn when delivery is owed.

    The saved marker prevents an unavailable provider from extending work forever.
    """
    n = parsed['iteration']
    if 'notification_finalizer: true' not in parsed['header'] and (root / 'esx/project.json').exists():
        import notifications
        try:
            notifications.synchronize(root, terminal=reason)
            delivery_needed = bool(notifications.pending(root))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            log(root, 'NOTIFICATION_ERROR', n, str(exc))
            delivery_needed = False
        if delivery_needed:
            from project import atomic_bytes
            header = parsed['header'] + '\nnotification_finalizer: true'
            atomic_bytes(state, ('---\n' + header + '\n---\n' + parsed['prompt']).encode())
            return {'decision': 'block', 'reason':
                explain + ' This is one notification-only finalization turn. '
                'Use esx-announce to deliver pending notifications and record receipts or concrete failures. '
                'Do not select issues, dispatch agents, run --next, or start another loop. '
                'Report unfinished work and undelivered events, then stop without a completion promise.',
                'systemMessage': system_message}
    return archive(root, state, original, kind, n, reason)


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
    owner = parsed['header_fields'].get('owner_session')
    caller = hook_input.get('session_id')
    if owner and caller and caller != owner:
        # Another Claude process in the project directory (e.g. a bare `claude --print`)
        # must never advance, end or announce the owner's loop (TEAM-LOOP-FOREIGN-STOP-001).
        log(root, 'FOREIGN_STOP', n, f'ignored Stop from session {caller}; loop owned by {owner}')
        return {}
    cancelled = cancel_request(parsed)
    if cancelled is not None and work_in_progress(root) is None:
        # The owner's cancel takes effect here, where a new iteration would start
        # from the top; the iteration that was active has been closed out.
        return finalize(root, state, original, parsed, 'CANCELLED', 'cancelled: ' + cancelled,
                        f'The owner cancelled the loop ({cancelled}) and the iteration that was active is finished.',
                        'Loop cancelled by the owner; notification finalization only.')
    if limit and n >= limit:
        return finalize(root, state, original, parsed, 'END', f'iteration budget {limit} reached',
                        f'The loop reached its iteration budget of {limit}. This is not a cost or spend limit: '
                        'cost and effort are measured, never capped, and max_iterations is the only enforced '
                        'terminal bound.',
                        f'Loop iteration budget {limit} reached; notification finalization only.')
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
    if (root / 'esx/project.json').exists():
        try:
            import notifications
            notifications.heartbeat(root)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            log(root, 'NOTIFICATION_ERROR', n, str(exc))
    running = native_running(root, hook_input.get('session_id'))
    if running:
        # A background Agent-tool subagent re-invokes this session when it reports,
        # so the turn may end quietly: no block (the CLI renders every Stop block as
        # "Stop hook error"), no iteration consumed and no progress post
        # (TEAM-LOOP-INFLIGHT-BLOCK-NOISE-001, TEAM-LOOP-WAIT-BURNS-ITERATION-001).
        who = ', '.join(f"{r['agent_type']} ({r['minutes']} min)" for r in running)
        log(root, 'HOLD', n, f'native subagent running: {who}; stop allowed, iteration not advanced')
        return {'systemMessage': f'ESX loop holding at iteration {n}/{limit}: {who} still running. '
                                 'The loop resumes when it reports; nothing is wrong.'}
    raw_waits = parsed['header_fields'].get('dispatch_waits', '0')
    waits = int(raw_waits) if raw_waits.isdigit() else MAX_DISPATCH_WAITS
    if waits < MAX_DISPATCH_WAITS and retained_in_flight(root):
        # A retained CLI turn sends no completion notification, so this session has
        # to stay in its turn. Waiting is not an iteration of work, and a small cap
        # keeps the loop finite.
        header = set_field(parsed['header'], 'dispatch_waits', waits + 1)
        from project import atomic_bytes
        atomic_bytes(state, ('---\n' + header + '\n---\n' + parsed['prompt']).encode())
        log(root, 'WAIT', n, f'retained dispatch in flight; iteration not advanced ({waits + 1}/{MAX_DISPATCH_WAITS})')
        return {'decision': 'block', 'reason': 'ESX status, not an error: a retained role turn for the active issue '
                'is still running. Block on it with `python3 tools/esx/agent_runtime.py wait` as a foreground command '
                'with a 600000 ms tool timeout (repeat while it reports running, and print a one-line status for '
                'the owner between waits), '
                'then continue with tools/esx/loop_gate.py --next.',
                'systemMessage': f'ESX iteration {n} held: retained dispatch in flight ({waits + 1}/{MAX_DISPATCH_WAITS}).'}
    stamps = []
    for token in parsed['header_fields'].get('advance_times', '').split(','):
        try:
            stamps.append(float(token))
        except ValueError:
            pass
    moment = clock()
    recent = [t for t in stamps if 0 <= moment - t < ADVANCE_WINDOW_SECONDS]
    if len(recent) >= MAX_ADVANCES:
        # No real iteration of work finishes this fast, so something is driving the
        # loop that should not be. Keep the state and withhold the continuation.
        log(root, 'ANOMALY', n, f'{len(recent)} loop advances within {ADVANCE_WINDOW_SECONDS} s; continuation withheld, state kept')
        return {'systemMessage': f'ESX loop paused: {len(recent)} advances within {ADVANCE_WINDOW_SECONDS} s is not normal work. '
                                 'The loop state is preserved; check .claude/esx-loop-exit.log, then run /esx-loop '
                                 'to continue.'}
    header = re.sub(r'(?m)^[ \t]*iteration[ \t]*:[ \t]*[^\r\n]*$',
                    'iteration: ' + str(n + 1), parsed['header'])
    header = set_field(header, 'dispatch_waits', None)
    header = set_field(header, 'advance_times',
                       ','.join(f'{t:.0f}' for t in (recent + [moment])[-MAX_ADVANCES:]))
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
