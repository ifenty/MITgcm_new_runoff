"""Run project checks and reuse content-matching successful evidence.

Commands are argv arrays and execute without a shell. Failures, empty suites,
timeouts, source drift and modified logs cannot establish a passing gate.
"""
import argparse
import fcntl
import json
import os
import re
import shlex
import signal
import threading
from pathlib import Path
import subprocess
import sys
import time
import uuid

from project import (STATE, atomic_json, command, config, digest, environment,
                     file_hash, json_file, local, named_sha, now, require, source_signature)


class RunInterrupted(ValueError, InterruptedError):
    """The suite did not finish: no verdict exists about the candidate.

    Also an `InterruptedError`: when the runner itself receives a signal, callers that
    catch the signal exception keep catching it, while the record names the outcome."""
    def __init__(self, message, log, reason):
        super().__init__(message)
        self.log, self.reason = log, reason


class SourceChanged(ValueError):
    """Inputs moved under the run, so its outcome describes no single candidate."""
    def __init__(self, message, log=None):
        super().__init__(message)
        self.log = log


class RunTimedOut(ValueError):
    """A command exceeded the configured per-command timeout: a verdict on a hung candidate."""
    def __init__(self, message, log):
        super().__init__(message)
        self.log = log


class RunInfrastructure(ValueError):
    """A command could not run, or ended for a cause not established: no verdict on the candidate."""
    def __init__(self, message, log):
        super().__init__(message)
        self.log = log


FAILURE_LINE = re.compile(r'\b(FAILED|ERROR)\b')
# pytest ends every completed session with e.g. "==== 3 passed in 0.12s ====".
# Used only for the one case a return code cannot settle: a pytest session that
# started and exited non-zero without this line (see `interruption`). It never
# overrides what the runner itself observed.
PYTEST_SUMMARY = re.compile(r'^=+ .+ in [0-9.]+s\b.*=+\s*$', re.M)


def failure_lines(text):
    """Count failure-marked output lines, excluding the verifier's COMMAND echoes.

    Zero establishes only that no such line was observed, never that every
    started test passed.
    """
    return sum(1 for line in text.splitlines() if not line.startswith('COMMAND ') and FAILURE_LINE.search(line))


#: A command killed by one of these crashed on its own; that is a failure of
#: the candidate, not an interruption of the run.
CRASH_SIGNALS = frozenset(s for s in (getattr(signal, n, None) for n in
                          ('SIGSEGV', 'SIGBUS', 'SIGFPE', 'SIGILL', 'SIGABRT', 'SIGTRAP', 'SIGSYS')) if s)
#: Requests to stop, delivered from outside: the command was interrupted.
TERMINATION_SIGNALS = frozenset(s for s in (getattr(signal, n, None) for n in
                                ('SIGTERM', 'SIGINT', 'SIGHUP', 'SIGKILL', 'SIGQUIT')) if s)


def classify(index, argv, rc, error):
    """The outcome of the command that ended a run, from the RUNNER's own state.

    Decided from what the runner observed -- whether its own signal handler
    fired, whether ``wait`` timed out, whether the command could be launched,
    and the command's return code -- and never from the log text. The log
    carries the commands' own output, so any test could print a signal-looking
    line; the earlier version searched that text for
    ``verification received signal N`` and so would report a REAL failed
    assertion as an interruption with no verdict whenever the failing output
    echoed the string -- which this project's own test file contains as a
    literal. After the arm reordering the genuine signal path raised before
    that search, so the search could only ever match command output
    (TEAM-VERIFY-SIGNAL-MISCLASSIFIED-001, corrected per esx-fix.md B.4).

    Returns ``(outcome, termination, reason)``.
    """
    where = f'command {index + 1} ({" ".join(argv)})'
    if isinstance(error, (KeyboardInterrupt, InterruptedError)):
        signum = getattr(error, 'signum', None)
        return 'interrupted', signum, f'the verification runner received signal {signum} during {where}'
    if isinstance(error, subprocess.TimeoutExpired):
        return 'timeout', None, f'{where} timed out after {error.timeout} s'
    if isinstance(error, OSError):
        return 'infrastructure', None, f'{where} could not run: {error}'
    if rc < 0:
        if -rc in CRASH_SIGNALS:
            return 'failed', -rc, f'{where} crashed with signal {-rc}'
        if -rc in TERMINATION_SIGNALS:
            # The operating system reports that the command was TERMINATED by a
            # signal it did not raise by crashing: external termination is
            # established by the return code itself, so this is an interruption
            # with no verdict (esx-fix.md B: "Direct SIGTERM ... produce
            # interrupted attempts when the cause is established"). Measured
            # against ESX-Team's own suite, which terminates the suite's child
            # with SIGTERM and requires "interrupted".
            return 'interrupted', -rc, f'{where} was terminated from outside the runner by signal {-rc}'
        return 'infrastructure', -rc, (f'{where} ended on signal {-rc}, a cause the runner did not observe and '
                                       'cannot attribute to the candidate')
    # A positive status is the command's own report. 124 is NOT read as a
    # timeout and 128+N is NOT read as an interruption: the runner records its
    # own timeouts and signals separately, so a command returning either has
    # simply failed (esx-fix.md B.5).
    hint = f' (128+{rc - 128} suggests the command itself was signalled)' if 128 < rc < 160 else ''
    return 'failed', None, f'{where} exited {rc}{hint}'


def fingerprint(root, suite, commands):
    cfg = config(root)
    return digest({'source': source_signature(root, scientific=suite != 'structural'),
                   'framework': {p.name: file_hash(p) for p in (root / 'tools/esx').glob('*.py')},
                   'commands': commands, 'environment': environment(root, cfg), 'suite': suite})


def interruption(rc, text):
    """Why a non-zero run never reached a verdict on pytest's own evidence, else None.

    `classify` decides from what the runner observed; this keeps the one judgement a return code
    cannot settle (release 1.6.5): a pytest session that started and ended with a positive status
    but without its summary line. A negative status is a child ended by a signal.
    """
    why = None
    if rc < 0:
        why = f'child ended by signal {-rc}'
    elif rc > 0 and 'test session starts' in text and not PYTEST_SUMMARY.search(text):
        why = f'exit {rc} before the pytest summary line'
    return why


def structural_evidence(root):
    """Read current complete structural PASS without executing another suite."""
    commands = config(root)['verification']['structural']
    ref = json_file(root, f'{STATE}/verification/cache-{digest(["structural", commands])}.json')
    evidence = load_evidence(root, ref)
    require(evidence['suite'] == 'structural' and evidence['commands'] == commands,
            'structural receipt must cover the complete configured suite')
    return ref


def load_evidence(root, ref):
    """A suite receipt: a single-suite record, or in a grouped project the aggregate.

    A group record is refused here: it covers only part of the suite, so it can
    never stand for the scientific suite on its own.
    """
    return _load(root, ref)


def groups_of(cfg):
    """The configured scientific groups, or None for a single-suite project."""
    return cfg['verification'].get('scientific_groups')


def _load(root, ref, allow_group=False):
    import self_improvement
    if (Path(root) / self_improvement.OPEN).exists():
        errors = self_improvement.validate(root)
        require(not errors, '; '.join(errors))
    require(isinstance(ref, dict) and ref.get('path') and ref.get('sha256'),
            "verification reference is required -- a plain command (e.g. bare pytest) has no evidence file of its "
            "own; run it through verify.py (e.g. 'verify.py --suite focused --owner <id> --fresh') and cite that "
            "command's own returned evidence reference instead")
    sha = ref.get('sha256')
    require(ref.get('path') == f'{STATE}/verification/{sha}.json',
            f"invalid verification artifact path: the path names {named_sha(ref.get('path'))} but sha256 is {sha}")
    record = json_file(root, ref['path'])
    require(digest(record) == sha, 'verification artifact was modified')
    require(record.get('exit') == 0 and type(record.get('exit')) is int and record.get('stable') is True,
            'verification did not finish successfully on a stable candidate')
    require(record.get('commands'), 'verification ran no commands')
    # A record that states how it ended must say it passed AND ran everything;
    # `stable` alone only means the fingerprint did not move (esx-fix.md B.6).
    # A legacy record without `outcome` was written to the evidence index only
    # on a PASS, so its exit-0-and-stable test above remains its contract.
    if 'outcome' in record:
        require(record['outcome'] == 'pass', f"verification outcome is {record['outcome']}, not pass")
        require(record.get('completed_commands') == record.get('planned_commands') == len(record['commands']),
                'verification did not complete every configured command')
    require(record['signature'] == fingerprint(root, record['suite'], record['commands']),
            f"verification evidence is stale (sealed {ref['path']}, suite {record['suite']}, owner "
            f"{record.get('owner')}); rerun: {rerun_command(record)}")
    if record.get('groups') is not None:
        _check_aggregate(root, record, ref)
        return record
    if record['suite'] == 'scientific' and not record.get('group') and groups_of(config(root)):
        raise ValueError('this project configures scientific_groups: a flat scientific record is not accepted; '
                         'run final_verification.py run and cite its aggregate')
    require(allow_group or record.get('group') is None,
            f"evidence {ref.get('path')} is the record of scientific group {record.get('group')}, not of the whole suite; "
            'cite the aggregate returned by final_verification.py run')
    require(file_hash(local(root, record['log'])) == record['log_sha256'], 'verification log is missing or modified')
    return record


def _check_aggregate(root, record, ref):
    """An aggregate stands for the suite only while every configured group is intact, passing, current and ours."""
    configured = groups_of(config(root))
    require(configured, 'aggregate scientific evidence in a project that configures no scientific_groups')
    require(record['suite'] == 'scientific' and record.get('group') is None, 'aggregate must be for the scientific suite')
    listed = record['groups']
    require(isinstance(listed, list) and all(isinstance(g, dict) for g in listed)
            and [g.get('name') for g in listed] == [g['name'] for g in configured],
            'aggregate groups differ from the configured scientific groups (missing, reordered or renamed)')
    flat = []
    for entry, group in zip(listed, configured):
        leaf = _load(root, entry.get('evidence'), allow_group=True)
        require(leaf.get('group') == group['name'] and leaf['suite'] == 'scientific' and leaf.get('groups') is None,
                f"group {group['name']}: evidence belongs to another group or is not a group record")
        require(leaf['commands'] == group['commands'], f"group {group['name']}: its commands differ from the configuration")
        require(leaf['owner'] == record.get('owner'), f"group {group['name']}: owned by {leaf['owner']}, not by the aggregate's owner {record.get('owner')}")
        flat += leaf['commands']
    require(record['commands'] == flat == config(root)['verification']['scientific'] and
            record.get('command_digest') == digest(flat), 'aggregate commands differ from the configured scientific suite')


def rerun_command(record):
    """The command line that reproduces a record's suite under its owner."""
    if record.get('groups') is not None:
        return ('python3 tools/esx/final_verification.py run --review devel-loop/loop_state/review.json '
                f"--owner {shlex.quote(str(record.get('owner')))}")
    argv = ['python3', 'tools/esx/verify.py', '--suite', record['suite'], '--owner', str(record.get('owner')), '--fresh']
    if record.get('group'):
        argv += ['--group', record['group']]
    if record['suite'] == 'focused' and len(record['commands']) == 1:
        argv += ['--command', json.dumps(record['commands'][0])]
    return ' '.join(shlex.quote(a) for a in argv)


def stale_evidence(root, owner):
    """The owner's latest record per suite and commands whose signature differs from the current fingerprint."""
    root = Path(root)
    latest = {}
    for path in sorted((root / STATE / 'verification').glob('*.json')):
        if not re.fullmatch(r'[0-9a-f]{64}', path.stem):
            continue
        try:
            record = json.loads(path.read_text())
            if record.get('owner') != owner or digest(record) != path.stem:
                continue
            key = digest([record['suite'], record['commands']])
            if key not in latest or record['finished_at'] > latest[key][1]['finished_at']:
                latest[key] = (path, record)
        except (ValueError, OSError, KeyError, TypeError, AttributeError):
            continue
    stale = []
    for path, record in latest.values():
        try:
            current = fingerprint(root, record['suite'], record['commands'])
        except (ValueError, OSError, KeyError, subprocess.SubprocessError):
            continue
        if record['signature'] != current:
            stale.append({'evidence': {'path': f'{STATE}/verification/{path.name}', 'sha256': path.stem},
                          'suite': record['suite'], 'finished_at': record['finished_at'],
                          'rerun': rerun_command(record)})
    return stale


def intact_owner(root, ref):
    """Owner recorded in an unmodified evidence file, or None; freshness is not judged here."""
    try:
        sha = ref.get('sha256')
        if ref.get('path') != f'{STATE}/verification/{sha}.json':
            return None
        record = json_file(root, ref['path'])
        return record.get('owner') if digest(record) == sha else None
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return None


def run(root, suite, owner, fresh=False, override=None, _lease=None, group=None):
    """Serialize matching suites; independent fresh runs execute after acquiring the lock.

    In a project with ``scientific_groups`` the scientific suite is a sequence of
    groups: ``group`` runs exactly one of them (reusing its intact current PASS
    unless ``fresh``), and no group runs every group in order and seals the aggregate.
    """
    import team_accounting
    if group is not None or suite == 'scientific':
        groups = groups_of(config(root)) if suite == 'scientific' else None
        require(group is None or suite == 'scientific' and groups,
                '--group needs the scientific suite of a project that configures scientific_groups')
        require(group is None or group in [g['name'] for g in groups],
                f"unknown scientific group {group!r}; configured: {', '.join(g['name'] for g in groups or [])}")
        if groups and group is None:
            require(override is None, 'custom commands are restricted to focused checks')
            return run_groups(root, owner, fresh, _lease)
    if suite == 'structural':
        import self_improvement
        if (Path(root) / self_improvement.OPEN).exists():
            errors = self_improvement.validate(root)
            require(not errors, '; '.join(errors))
    if suite == 'scientific':
        import final_verification
        final_verification.authorize(root, _lease)
    lock = local(root, f'{STATE}/verification/lock-{digest([suite, override] + ([group] if group else []))}')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        if suite == 'scientific':
            final_verification.authorize(root, _lease)
        active = local(root, f'{STATE}/issue-start.json')
        issue = json.loads(active.read_text()).get('id') if active.exists() else None
        with team_accounting.phase(root, issue, 'verification', role=owner if isinstance(owner, str) else None):
            return _run(root, suite, owner, fresh, override, group)


def group_commands(cfg, name):
    return next(g['commands'] for g in groups_of(cfg) if g['name'] == name)


def group_pointer(root, commands, name):
    return local(root, f'{STATE}/verification/cache-{digest(["scientific", commands, name])}.json')


def aggregate_pointer(root, cfg):
    return local(root, f"{STATE}/verification/aggregate-{digest(['scientific', cfg['verification']['scientific']])}.json")


def _run(root, suite, owner, fresh, override, group=None):
    cfg = config(root)
    require(suite in cfg['verification'] and suite != 'scientific_groups', f'unknown verification suite: {suite}')
    require(group is None or suite == 'scientific', 'groups belong to the scientific suite')
    require(not (suite == 'scientific' and groups_of(cfg) and group is None),
            'the scientific suite of this project is grouped; run it through final_verification.py run or verify.py without --command')
    require(isinstance(owner, str) and owner.strip(), 'record the actual verification owner')
    require(override is None or suite == 'focused', 'custom commands are restricted to focused checks')
    commands = group_commands(cfg, group) if group else [override] if override else cfg['verification'][suite]
    require(commands and all(isinstance(a, list) and a and all(isinstance(s, str) and s for s in a) for a in commands), 'verification suite is empty or invalid')
    signature = fingerprint(root, suite, commands)
    index = group_pointer(root, commands, group) if group else local(root, f'{STATE}/verification/cache-{digest([suite, commands])}.json')
    if not fresh and index.exists():
        ref = json.loads(index.read_text())
        try:
            record = _load(root, ref, allow_group=bool(group))
            # A group is reused only for the same group and the same accountable owner.
            if record['signature'] == signature and (not group or (record.get('group'), record['owner']) == (group, owner)):
                return {'status': 'REUSED EVIDENCE', 'evidence': ref, 'original_finished_at': record['finished_at']}
        except (ValueError, OSError, KeyError):
            pass
    # A failed or interrupted fresh attempt must not expose an older PASS for
    # the same fingerprint on the next invocation.
    index.unlink(missing_ok=True)
    if group:
        # Re-running any group voids the aggregate and the receipt that cites it,
        # so a later failure cannot leave an older qualification usable.
        aggregate_pointer(root, cfg).unlink(missing_ok=True)
        local(root, f'{STATE}/final-verification/current.json').unlink(missing_ok=True)
    log = f'{STATE}/verification/run-{uuid.uuid4().hex}.log'
    path = local(root, log)
    path.parent.mkdir(parents=True, exist_ok=True)
    started_at, start, rc = now(), time.monotonic(), 0
    outcome, termination, reason, completed, ended_at = 'pass', None, None, 0, None
    with path.open('w') as stream:
        for index_, argv in enumerate(commands):
            stream.write('COMMAND ' + json.dumps(command(argv, cfg)) + '\n')
            stream.flush()
            error = None
            try:
                rc = execute(command(argv, cfg), root, stream, cfg.get('command_timeout_seconds', 3600))
            # THE SIGNAL ARM MUST COME FIRST. `InterruptedError` is a subclass
            # of `OSError`, so while the OSError arm was above it every signal
            # was caught there and recorded as a timeout -- how RUNOFF-040's
            # externally killed final verification (process-group SIGTERM after
            # 3542.95 s, 35 of 36 started commands passing) came to be recorded
            # as "verification failed (exit 124)" against an approved candidate
            # (TEAM-VERIFY-SIGNAL-MISCLASSIFIED-001).
            except (KeyboardInterrupt, InterruptedError) as exc:
                stream.write('INTERRUPTED ' + repr(exc) + '\n')
                rc, error = 130, exc
            except subprocess.TimeoutExpired as exc:
                stream.write(f'TIMED OUT after {exc.timeout} s\n')
                rc, error = 124, exc
            except OSError as exc:
                # Launch failure (missing executable, permissions): the runner
                # could not run the command, so nothing about the candidate is
                # known. It used to share the timeout arm and read as a hung
                # candidate (esx-fix.md B).
                stream.write(f'COULD NOT RUN {exc!r}\n')
                rc, error = 127, exc
            if error is None and rc == 0:
                completed += 1
                continue
            outcome, termination, reason = classify(index_, argv, rc, error)
            if error is None and rc > 0:
                # It ran to its own exit, with a failure status. A command ended
                # by a signal did NOT complete; counting it once made an
                # interrupted record claim "2 of 2 commands completed".
                completed += 1
            ended_at = {'index': index_, 'argv': argv, 'exit': rc}
            break
    try:
        stable = signature == fingerprint(root, suite, commands)
    except (ValueError, OSError, subprocess.SubprocessError):
        stable = False
    text = path.read_text(errors='replace')
    if outcome == 'failed' and error is None and rc > 0:
        # A pytest session that started and exited non-zero without its summary line
        # never reached a verdict (release 1.6.5 behaviour, kept).
        why = interruption(rc, text)
        if why:
            outcome, reason = 'interrupted', why
    if outcome in ('pass', 'failed', 'timeout') and not stable:
        outcome, reason = 'source_changed', 'the source changed while the suite ran'
    # Classified BEFORE sealing, so the stored record, the raised exception and
    # every later explanation say the same thing (esx-fix.md B.3). `stable`
    # keeps its meaning -- the fingerprint did not move -- and `outcome` is the
    # separate statement of whether the run completed and passed (B.6).
    record = {'version': 1, 'suite': suite, 'owner': owner, 'commands': commands,
              'signature': signature, 'started_at': started_at, 'finished_at': now(),
              'elapsed_seconds': time.monotonic() - start, 'exit': rc, 'stable': stable,
              'outcome': outcome, 'termination': termination, 'reason': reason,
              'completed_commands': completed, 'planned_commands': len(commands),
              'ended_at': ended_at, 'failure_lines': failure_lines(text),
              'log': log, 'log_sha256': file_hash(path)}
    if group:
        record['group'] = group
    sha = digest(record)
    ref = {'path': f'{STATE}/verification/{sha}.json', 'sha256': sha}
    atomic_json(local(root, ref['path']), record)
    progress = (f'{completed} of {len(commands)} commands completed; {record["failure_lines"]} failure-marked '
                f'lines were observed (which does not establish that the rest passed); inspect {log}')
    if isinstance(error, KeyboardInterrupt):
        error.log = log
        raise error
    if outcome == 'interrupted':
        raise RunInterrupted(f'verification interrupted ({reason}); the suite reached no verdict; {progress}',
                             log, reason) from (error if isinstance(error, InterruptedError) else None)
    if outcome == 'infrastructure':
        raise RunInfrastructure(f'verification could not complete ({reason}); no verdict on the candidate; '
                                f'{progress}', log)
    if outcome == 'source_changed':
        raise SourceChanged(f'source changed during verification; {progress}', log)
    if outcome == 'timeout':
        # Worded as a failure, as upstream consumers match it: a timeout is the
        # configured verdict on a hung candidate. Its own class and status keep
        # it distinct from a completed failure (esx-fix.md B.1).
        raise RunTimedOut(f'verification failed: timed out ({reason}); {progress}', log)
    if outcome == 'failed':
        failure = ValueError(f'verification failed ({reason}); {progress}')
        failure.log = log
        raise failure
    atomic_json(index, ref)
    return {'status': 'EXECUTED PASS', 'evidence': ref, 'elapsed_seconds': record['elapsed_seconds']}


def run_groups(root, owner, fresh, lease):
    """Run (or reuse) every scientific group in order, then seal the aggregate.

    A failed or interrupted group raises with its own log and leaves the groups
    before it reusable; re-running resumes at that group.
    """
    root = Path(root)
    cfg = config(root)
    flat = cfg['verification']['scientific']
    aggregate_pointer(root, cfg).unlink(missing_ok=True)
    results = []
    for group in groups_of(cfg):
        results.append((group, run(root, 'scientific', owner, fresh, _lease=lease, group=group['name'])))
    records = []
    for group, result in results:
        try:
            records.append(_load(root, result['evidence'], allow_group=True))
        except ValueError as exc:
            raise SourceChanged(f"scientific group {group['name']} no longer matches the candidate after the grouped run: {exc}",
                                json_file(root, result['evidence']['path']).get('log')) from exc
    aggregate = {'version': 1, 'suite': 'scientific', 'owner': owner, 'commands': flat, 'command_digest': digest(flat),
                 'signature': fingerprint(root, 'scientific', flat),
                 'groups': [{'name': g['name'], 'evidence': r['evidence']} for g, r in results],
                 'started_at': min(r['started_at'] for r in records), 'finished_at': now(),
                 'elapsed_seconds': sum(r['elapsed_seconds'] for r in records), 'exit': 0, 'stable': True}
    sha = digest(aggregate)
    ref = {'path': f'{STATE}/verification/{sha}.json', 'sha256': sha}
    atomic_json(local(root, ref['path']), aggregate)
    _load(root, ref)
    atomic_json(aggregate_pointer(root, cfg), ref)
    executed = [r for _, r in results if r['status'] == 'EXECUTED PASS']
    return {'status': 'EXECUTED PASS' if executed else 'REUSED EVIDENCE', 'evidence': ref,
            'elapsed_seconds': sum(r['elapsed_seconds'] for r in executed),
            'groups': [{'name': g['name'], 'status': r['status'], 'evidence': r['evidence']} for g, r in results],
            'log': records[-1]['log']}


def group_status(root, owner):
    """Per-group state for the owner: current, missing (no passing evidence) or stale (with the reason)."""
    cfg = config(root)
    rows = []
    for group in groups_of(cfg) or []:
        pointer = group_pointer(root, group['commands'], group['name'])
        row = {'name': group['name'], 'status': 'missing'}
        if pointer.exists():
            try:
                ref = json.loads(pointer.read_text())
                record = _load(root, ref, allow_group=True)
                require(record.get('group') == group['name'], 'pointer names another group')
                require(record['owner'] == owner, f"owned by {record['owner']}, not {owner}")
                row.update(status='current', evidence=ref)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                row.update(status='stale', reason=str(exc)[:160])
        rows.append(row)
    return rows


def execute(argv, root, stream, timeout):
    """Bound a complete process group and remove descendants on every exit path."""
    previous = {}
    process = None
    def interrupt(signum, frame):
        # The signal number travels on the exception, so the outcome is decided
        # from the runner's own observation rather than from a log line.
        error = InterruptedError(f'verification received signal {signum}')
        error.signum = signum
        raise error
    # Handlers go in before the child starts: a signal in between must interrupt
    # the run (and leave its record), not kill the runner.
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[sig] = signal.signal(sig, interrupt)
    try:
        process = subprocess.Popen(argv, cwd=root, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        return process.wait(timeout=timeout)
    finally:
        try:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--suite', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--command', type=json.loads, help='one focused argv array')
    parser.add_argument('--group', help='run one scientific group (projects with verification.scientific_groups)')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.root.resolve(), args.suite, args.owner, args.fresh, args.command, group=args.group), indent=2))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'ESX verification: {exc}\n')


if __name__ == '__main__':
    main()
