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

#: Verification entry points whose runs the loop must wait out rather than
#: charge for. Both are long by nature: the scientific suite is ~60 commands.
VERIFICATION_SCRIPTS = ('tools/esx/final_verification.py', 'tools/esx/verify.py')

#: Upper bound on how long such a run may hold the loop. Above it the process is
#: treated as abandoned so a wedged run cannot stall the loop forever; the
#: per-command timeout is an hour and a full scientific pass is about two.
VERIFICATION_STALE_SECONDS = 5 * 3600

#: One foreground wait on an untracked verification run, kept under the Bash
#: tool's 600 s ceiling so the wait command itself never times out the tool.
VERIFY_WAIT_SECONDS = 590

#: Enough waits to outlast VERIFICATION_STALE_SECONDS, after which the run is
#: treated as abandoned anyway; the cap is what keeps the loop finite.
MAX_VERIFY_WAITS = VERIFICATION_STALE_SECONDS // VERIFY_WAIT_SECONDS + 1
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


def pause_request(parsed):
    """(reason, until) while the loop is paused, else None (TEAM-LOOP-USAGE-LIMIT-PAUSE-001).

    ``until`` is epoch seconds or None. A pause with a time that has passed is no
    pause: the next Stop behaves normally again. Nothing resumes by itself; an
    expiry only lifts the hold.
    """
    fields = parsed['header_fields']
    if fields.get('paused') != 'true':
        return None
    raw = fields.get('pause_reason', '')
    try:
        reason = json.loads(raw) if raw.startswith('"') else raw
    except ValueError:
        reason = raw
    reason = reason if isinstance(reason, str) and reason.strip() else 'paused by the coordinator'
    try:
        until = float(fields['paused_until']) if fields.get('paused_until') else None
    except ValueError:
        until = None
    if until is not None and clock() >= until:
        return None
    return reason, until


def pause_source(parsed):
    """Who paused the loop: 'provider_limit' when this hook paused it, else 'owner'."""
    return parsed['header_fields'].get('pause_source') or 'owner'


def set_pause(root, state, parsed, reason, until, source):
    """Write (reason given) or clear (reason None) the pause; return the re-read state and bytes."""
    from project import atomic_bytes
    header = parsed['header']
    for key in ('paused', 'pause_reason', 'paused_until', 'pause_source'):
        header = set_field(header, key, None)
    if reason is not None:
        header = set_field(header, 'paused', 'true')
        header = set_field(header, 'pause_reason', json.dumps(reason))
        if until is not None:
            header = set_field(header, 'paused_until', f'{until:.0f}')
        if source:
            header = set_field(header, 'pause_source', source)
    data = ('---\n' + header + '\n---\n' + parsed['prompt']).encode()
    atomic_bytes(state, data)
    return parse_state(data.decode()), data


def queue_loop_event(root, kind, text):
    """Queue a loop_paused / loop_resumed notice; delivery waits for a working turn."""
    if not (Path(root) / 'esx/project.json').exists():
        return
    try:
        import notifications
        notifications.loop_event(root, kind, text)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        log(root, 'NOTIFICATION_ERROR', '?', str(exc))


def synthetic_limit(record):
    """True for the record the CLI writes when the provider refuses a request for a usage limit.

    All of: an assistant record, error "rate_limit", the API-error flag (camelCase in
    session transcripts, snake_case in stream output) and the CLI's synthetic model.
    The human text, which names the reset time, is never parsed.
    """
    if not isinstance(record, dict) or record.get('type') != 'assistant' or record.get('error') != 'rate_limit':
        return False
    if not (record.get('isApiErrorMessage') is True or record.get('is_api_error_message') is True):
        return False
    message = record.get('message')
    return isinstance(message, dict) and message.get('model') == '<synthetic>'


def provider_turn(path):
    """How the current turn of a transcript ended: 'limited', 'working' or None.

    'limited' when its last assistant record is a provider usage-limit refusal;
    'working' when it has real assistant output and did not end refused; None
    when that cannot be read. Only the transcript's last 2 MB are read.
    """
    if not path:
        return None
    try:
        with Path(path).open('rb') as handle:
            size = handle.seek(0, 2)
            handle.seek(max(0, size - 2 * 1024 * 1024))
            if size > 2 * 1024 * 1024:
                handle.readline()
            lines = handle.read().decode('utf-8', errors='replace').splitlines()
    except OSError:
        return None
    last, real = None, False
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        message = record.get('message') if isinstance(record.get('message'), dict) else {}
        if record.get('type') == 'user' or message.get('role') == 'user':
            content = message.get('content')
            if isinstance(content, list) and content and all(
                    isinstance(c, dict) and c.get('type') == 'tool_result' for c in content):
                continue
            last, real = None, False  # a new turn begins
        elif record.get('type') == 'assistant':
            last = record
            if not synthetic_limit(record):
                real = True
    if last is None:
        return None
    return 'limited' if synthetic_limit(last) else ('working' if real else None)


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


def verification_running(root):
    """Verification runs this project owns that are still executing.

    The final scientific verification is Arch's own by workflow design
    (``final_verify_owner``), takes about two hours over ~60 commands, and is
    MANDATORY for every scientific change. It is not a subagent, so
    :func:`native_running` cannot see it, and without this check every Stop
    cycle during it advanced the iteration. Measured on RUNOFF-030: ``CONTINUE
    iteration=4`` and ``CONTINUE iteration=5`` eighty seconds apart during a
    6629 s run, two of an owner-granted twenty spent on waiting. At that rate a
    single run can exhaust a whole budget before the issue it verifies closes,
    so the longest required step of the standard workflow was also the one that
    spent the budget fastest (TEAM-LOOPHOLD-ARCH-BACKGROUND-WORK-001).

    Read from ``/proc`` rather than from ``ps`` output, and skip this process:
    a ``pgrep -f``-style pattern matches the scanning command itself, which is
    how an earlier attempt at exactly this check reported its own shell as the
    running process. Binding to ``cwd`` keeps a run in another checkout from
    holding this loop.
    """
    root = Path(root).resolve()
    running, mine = [], {str(os.getpid()), str(os.getppid())}
    try:
        entries = [p for p in Path('/proc').iterdir() if p.name.isdigit()]
    except OSError:
        return []
    for entry in entries:
        if entry.name in mine:
            continue
        try:
            arguments = [a for a in entry.joinpath('cmdline').read_bytes().split(b'\0') if a]
            if len(arguments) < 2 or b'python' not in arguments[0].rsplit(b'/', 1)[-1]:
                continue
            script = next((s for s in VERIFICATION_SCRIPTS
                           if any(a.decode('utf-8', 'replace').endswith(s) for a in arguments[1:])), None)
            if not script or Path(os.readlink(entry / 'cwd')).resolve() != root:
                continue
            age = clock() - entry.stat().st_mtime
        except (OSError, ValueError, IndexError):
            continue
        if 0 <= age < VERIFICATION_STALE_SECONDS:
            running.append({'script': script, 'minutes': int(age // 60), 'pid': int(entry.name)})
    return running


def parent_pid(pid):
    """The parent of ``pid`` from ``/proc``, or None once it is gone."""
    try:
        stat = Path(f'/proc/{pid}/stat').read_text()
        # The command name is parenthesised and may itself contain spaces or
        # parentheses, so split after the LAST ')'.
        return int(stat[stat.rindex(')') + 2:].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def session_process(start=None):
    """The Claude CLI process this hook runs under, or None if none is found.

    A hook is spawned by the CLI, so walking up from this process reaches it.
    """
    pid = start or os.getpid()
    for _ in range(64):
        try:
            if Path(f'/proc/{pid}/comm').read_text().strip() == 'claude':
                return pid
        except OSError:
            return None
        pid = parent_pid(pid)
        if pid is None or pid <= 1:
            return None
    return None


def descends_from(pid, ancestor):
    """Whether ``ancestor`` is ``pid`` or one of its ancestors."""
    for _ in range(64):
        if pid == ancestor:
            return True
        pid = parent_pid(pid)
        if pid is None or pid <= 1:
            return False
    return False


def untracked_runs(running, session=None):
    """The verification runs this session will NOT be re-invoked for.

    The harness re-invokes a session only for work it launched and tracks: a
    native subagent, or a Bash-tool ``run_in_background`` command, whose process
    is a child of the session's own ``claude`` process. A run launched with
    ``subprocess.Popen(..., start_new_session=True)`` from a launcher that then
    exits is reparented to PID 1, so it has no ``claude`` ancestor and its end
    is an event nobody delivers. Measured on 2026-10-09: the detached form had
    ``ppid=1`` (``systemd``); the ``run_in_background`` form had this session's
    ``claude`` as its direct parent. Both were session leaders, so the session
    id does not tell them apart -- only the ancestry does.

    When the session process cannot be identified, every run counts as
    untracked: a needless wait costs a status line, a wrong "tracked" costs
    hours (TEAM-LOOPHOLD-NO-RELEASE-001).
    """
    session = session_process() if session is None else session
    return [r for r in running if not session or not descends_from(r['pid'], session)]


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
    turn = provider_turn(hook_input.get('transcript_path'))
    paused = pause_request(parsed)
    if turn == 'limited':
        # The provider refused this turn for a usage limit. Pause by ourselves so
        # stopping costs nothing; the pause lifts when a later turn does real work.
        if paused is None:
            parsed, original = set_pause(root, state, parsed, 'provider usage limit', None, 'provider_limit')
            log(root, 'AUTO_PAUSE', n, 'turn ended on a provider usage-limit record; loop paused')
            queue_loop_event(root, 'loop_paused', f'Loop paused at iteration {n}/{limit}: the provider usage limit '
                             'was reached. It resumes by itself when work is possible again.')
        paused = pause_request(parsed) or ('provider usage limit', None)
    elif (paused is not None and turn == 'working' and pause_source(parsed) == 'provider_limit'
            and paused[1] is None):
        # A turn did real work after an automatic pause: the limit has reset. Lift
        # only this kind of pause, then treat the Stop normally. A pause the owner
        # set is never lifted here.
        #
        # Only when the reset time is UNKNOWN (`paused[1] is None`). With a known
        # reset, that time is authoritative and `pause_request` stops reporting
        # the pause by itself once it passes. Lifting on a 'working' turn
        # regardless classified a turn that merely ended with a summary message
        # under the grace allowance as real work, and resumed the loop about 90
        # minutes before the reset (TEAM-PAUSE-EARLY-LIFT-001), which then spent
        # the iteration on a provider that was still refusing.
        parsed, original = set_pause(root, state, parsed, None, None, None)
        log(root, 'AUTO_RESUME', n, 'a turn did real work after a provider-limit pause; pause lifted')
        queue_loop_event(root, 'loop_resumed', f'Loop resumed at iteration {n}/{limit} after the provider '
                         'usage limit reset.')
        paused = None
    if paused is not None:
        # The coordinator cannot work (typically a provider usage limit). Let the
        # turn end and touch nothing: no iteration, no wait count, no heartbeat,
        # no ending. A pending cancel is kept and takes effect after the resume.
        reason, until = paused
        when = ('until ' + dt.datetime.fromtimestamp(until, dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                if until is not None else 'until /esx-loop resumes it')
        log(root, 'PAUSED', n, f'{reason}; {when}; stop allowed, iteration not advanced')
        return {'systemMessage': f'ESX loop paused at iteration {n}/{limit} ({reason}), {when}. Nothing is wrong.'}
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
    verifying = verification_running(root)
    if verifying:
        # Arch's own verification run is work in progress, not a turn of work:
        # waiting for it must cost nothing, or the mandatory final suite spends
        # the budget faster than the issues it qualifies
        # (TEAM-LOOPHOLD-ARCH-BACKGROUND-WORK-001).
        #
        # But "cost nothing" must not become "resume never". Allowing the stop is
        # only safe when something will re-invoke this session when the run ends,
        # and the harness does that only for a run it tracks. This branch used to
        # allow the stop for every run and promise "the loop resumes when it
        # finishes"; for a detached run nothing resumed it, and all three final
        # verifications in the exit log were followed by a dead gap -- 21 h, 7 h 52
        # and, on RUNOFF-042, about 8 h 44 min after the suite had already passed
        # (TEAM-LOOPHOLD-NO-RELEASE-001). The fix that introduced this hold was
        # validated twice, both times for holding and never for releasing.
        what = ', '.join(f"{r['script']} ({r['minutes']} min)" for r in verifying)
        untracked = untracked_runs(verifying)
        if not untracked:
            log(root, 'HOLD', n, f'verification running: {what}; tracked by this session; '
                                 'stop allowed, iteration not advanced')
            return {'systemMessage': f'ESX loop holding at iteration {n}/{limit}: {what} still running. '
                                     'It was launched by this session, which is re-invoked when it finishes.'}
        raw = parsed['header_fields'].get('verify_waits', '0')
        waits = int(raw) if raw.isdigit() else MAX_VERIFY_WAITS
        pid = untracked[0]['pid']
        if waits < MAX_VERIFY_WAITS:
            # Nothing will wake this session when the run ends, so it has to stay in
            # its turn, exactly as for a retained CLI turn below. The block renders as
            # a Stop hook error; that is the price of not stalling, and the reason
            # says how to avoid paying it next time.
            header = set_field(parsed['header'], 'verify_waits', waits + 1)
            from project import atomic_bytes
            atomic_bytes(state, ('---\n' + header + '\n---\n' + parsed['prompt']).encode())
            log(root, 'WAIT', n, f'untracked verification running: {what}; iteration not advanced '
                                 f'({waits + 1}/{MAX_VERIFY_WAITS})')
            return {'decision': 'block', 'reason': (
                'ESX status, not an error: a verification run is executing detached from this session '
                f'(pid {pid}), so nothing will re-invoke the session when it finishes. Wait for it with '
                f'`timeout {VERIFY_WAIT_SECONDS} tail --pid={pid} -f /dev/null` as a foreground command with a '
                '600000 ms tool timeout, repeating while it runs, then continue with tools/esx/loop_gate.py '
                '--next. Launch long runs with the Bash tool and run_in_background instead, which survives the '
                'turn and re-invokes the session on exit, so no wait is needed.'),
                'systemMessage': f'ESX iteration {n} held: detached verification running '
                                 f'({waits + 1}/{MAX_VERIFY_WAITS}).'}
        log(root, 'HOLD', n, f'untracked verification running: {what}; wait cap reached; stop allowed; '
                             'the loop will NOT resume on its own')
        return {'systemMessage': f'ESX loop holding at iteration {n}/{limit}: {what} is running detached from '
                                 'this session, which cannot be notified when it ends. The loop will NOT resume on '
                                 'its own; send any message to wake it.'}
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
    header = set_field(header, 'verify_waits', None)
    for key in ('paused', 'pause_reason', 'paused_until', 'pause_source'):
        header = set_field(header, key, None)
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
