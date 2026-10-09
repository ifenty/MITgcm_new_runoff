"""Run project checks and reuse content-matching successful evidence.

Commands are argv arrays and execute without a shell. Failures, empty suites,
timeouts, source drift and modified logs cannot establish a passing gate.
"""
import argparse
import fcntl
import json
import os
import re
import signal
import threading
from pathlib import Path
import subprocess
import sys
import time
import uuid

from project import (STATE, atomic_json, command, config, digest, environment,
                     file_hash, json_file, local, now, require, source_signature)


class RunInterrupted(ValueError):
    """The suite did not finish: no verdict exists about the candidate."""
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
# Retained for consumers that inspect a log, as ESX-Team's own suite does; it is
# deliberately NOT used to classify an outcome, which comes from the runner.
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


def structural_evidence(root):
    """Read current complete structural PASS without executing another suite."""
    commands = config(root)['verification']['structural']
    ref = json_file(root, f'{STATE}/verification/cache-{digest(["structural", commands])}.json')
    evidence = load_evidence(root, ref)
    require(evidence['suite'] == 'structural' and evidence['commands'] == commands,
            'structural receipt must cover the complete configured suite')
    return ref


def load_evidence(root, ref):
    import self_improvement
    if (Path(root) / self_improvement.OPEN).exists():
        errors = self_improvement.validate(root)
        require(not errors, '; '.join(errors))
    require(isinstance(ref, dict) and ref.get('path') and ref.get('sha256'),
            "verification reference is required -- a plain command (e.g. bare pytest) has no evidence file of its "
            "own; run it through verify.py (e.g. 'verify.py --suite focused --owner <id> --fresh') and cite that "
            "command's own returned evidence reference instead")
    sha = ref.get('sha256')
    require(ref.get('path') == f'{STATE}/verification/{sha}.json', 'invalid verification artifact path')
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
    require(record['signature'] == fingerprint(root, record['suite'], record['commands']), 'verification evidence is stale')
    require(file_hash(local(root, record['log'])) == record['log_sha256'], 'verification log is missing or modified')
    return record


def run(root, suite, owner, fresh=False, override=None, _lease=None):
    """Serialize matching suites; independent fresh runs execute after acquiring the lock."""
    import team_accounting
    if suite == 'structural':
        import self_improvement
        if (Path(root) / self_improvement.OPEN).exists():
            errors = self_improvement.validate(root)
            require(not errors, '; '.join(errors))
    if suite == 'scientific':
        import final_verification
        final_verification.authorize(root, _lease)
    lock = local(root, f'{STATE}/verification/lock-{digest([suite, override])}')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        if suite == 'scientific':
            final_verification.authorize(root, _lease)
        active = local(root, f'{STATE}/issue-start.json')
        issue = json.loads(active.read_text()).get('id') if active.exists() else None
        with team_accounting.phase(root, issue, 'verification', role=owner if isinstance(owner, str) else None):
            return _run(root, suite, owner, fresh, override)


def _run(root, suite, owner, fresh, override):
    cfg = config(root)
    require(suite in cfg['verification'], f'unknown verification suite: {suite}')
    require(isinstance(owner, str) and owner.strip(), 'record the actual verification owner')
    require(override is None or suite == 'focused', 'custom commands are restricted to focused checks')
    commands = [override] if override else cfg['verification'][suite]
    require(commands and all(isinstance(a, list) and a and all(isinstance(s, str) and s for s in a) for a in commands), 'verification suite is empty or invalid')
    signature = fingerprint(root, suite, commands)
    index = local(root, f'{STATE}/verification/cache-{digest([suite, commands])}.json')
    if not fresh and index.exists():
        ref = json.loads(index.read_text())
        try:
            record = load_evidence(root, ref)
            if record['signature'] == signature:
                return {'status': 'REUSED EVIDENCE', 'evidence': ref, 'original_finished_at': record['finished_at']}
        except (ValueError, OSError, KeyError):
            pass
    # A failed or interrupted fresh attempt must not expose an older PASS for
    # the same fingerprint on the next invocation.
    index.unlink(missing_ok=True)
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
    if outcome == 'pass' and not stable:
        outcome, reason = 'source_changed', 'the source changed while the suite ran'
    text = path.read_text(errors='replace')
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
    sha = digest(record)
    ref = {'path': f'{STATE}/verification/{sha}.json', 'sha256': sha}
    atomic_json(local(root, ref['path']), record)
    progress = (f'{completed} of {len(commands)} commands completed; {record["failure_lines"]} failure-marked '
                f'lines were observed (which does not establish that the rest passed); inspect {log}')
    if outcome == 'interrupted':
        raise RunInterrupted(f'verification interrupted ({reason}); the suite reached no verdict; {progress}',
                             log, reason)
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


def execute(argv, root, stream, timeout):
    """Bound a complete process group and remove descendants on every exit path."""
    process = subprocess.Popen(argv, cwd=root, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    previous = {}
    def interrupt(signum, frame):
        # The signal number travels on the exception, so the outcome is decided
        # from the runner's own observation rather than from a log line.
        error = InterruptedError(f'verification received signal {signum}')
        error.signum = signum
        raise error
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[sig] = signal.signal(sig, interrupt)
    try:
        return process.wait(timeout=timeout)
    finally:
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
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--suite', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--command', type=json.loads, help='one focused argv array')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.root.resolve(), args.suite, args.owner, args.fresh, args.command), indent=2))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'ESX verification: {exc}\n')


if __name__ == '__main__':
    main()
