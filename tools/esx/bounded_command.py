#!/usr/bin/env python3
"""Execute one shell command in an isolated process group with a hard timeout.

Optional receipts identify this tool's process group for the launcher watchdog.
The coordinator can use this wrapper directly. Exit 124 means timed out; command
output streams unchanged. Signal cleanup never targets another command group.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import team_accounting as accounting


def receipt_path(folder, tool_id):
    return Path(folder) / 'tool_processes' / (hashlib.sha256(tool_id.encode()).hexdigest() + '.json')


def terminate_group(pgid, process=None):
    try: os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError: return
    except PermissionError:
        if process is None or process.poll() is None: raise
        return
    if process is not None:
        try: process.wait(timeout=.2)
        except subprocess.TimeoutExpired: pass
    else:
        time.sleep(.1)
    try: os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError: pass
    except PermissionError:
        # macOS can report EPERM for the now-empty group after the leader exits.
        # Never suppress a denial while our owned process is still running.
        if process is None or process.poll() is None: raise


def run(command, timeout, folder=None, tool_id=None):
    if not accounting.number(timeout) or timeout <= 0: raise ValueError('positive finite timeout required')
    proc = subprocess.Popen(command, start_new_session=True)
    receipt = {'pid': proc.pid, 'pgid': proc.pid, 'started_at': accounting.now(), 'tool_use_id': tool_id, 'status': 'running'}
    path = receipt_path(folder, tool_id) if folder and tool_id else None
    if path: accounting.atomic(path, receipt)
    try:
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_group(proc.pid, proc); proc.wait(); rc = 124
        except BaseException:
            terminate_group(proc.pid, proc); proc.wait(); raise
        return rc
    finally:
        # A successful shell may still leave background descendants in its group.
        terminate_group(proc.pid, proc)
        receipt.update(status='finished', returncode=proc.returncode, finished_at=accounting.now())
        if path: accounting.atomic(path, receipt)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--timeout', type=float, required=True)
    p.add_argument('--folder'); p.add_argument('--tool-id')
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args(); cmd = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not cmd: p.error('command required after --')
    raise SystemExit(run(cmd, a.timeout, a.folder, a.tool_id))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
