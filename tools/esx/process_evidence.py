#!/usr/bin/env python3
"""Content-bound process validation and effectiveness evidence.

References must name regular repository-contained files. Validation receipts bind
successful command outputs to source bytes; optional commit checking binds those
bytes to published implementation. Historical receipts do not track today's tree.
The CLI executes an argv command with a timeout and records failures honestly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from doc_inventory import local


def reference(root, value, require_hash=True):
    if isinstance(value, str):
        name, _, digest = value.partition('#')
    elif isinstance(value, dict):
        name, digest = value.get('path'), value.get('sha256')
    else:
        raise ValueError('evidence needs path and sha256')
    path = local(root, name)
    if not path.is_file():
        raise ValueError('evidence must be a regular file: ' + str(name))
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if (require_hash or digest) and digest != actual:
        raise ValueError('evidence hash missing or mismatched: ' + str(name))
    return data


def ref(root, path):
    path = Path(path)
    return {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def landed(root, commit):
    import re
    if not re.fullmatch(r'[0-9a-f]{7,40}', str(commit)):
        return False
    return subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'],
                          cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def validation_errors(root, value, commit=None):
    try:
        receipt = json.loads(reference(root, value))
        if receipt.get('status') != 'PASS' or receipt.get('version') != 1 or receipt.get('stable') is False:
            raise ValueError('validation receipt must record version 1 PASS')
        checks = receipt.get('checks')
        if not isinstance(checks, list) or not checks:
            raise ValueError('validation needs executed checks')
        for check in checks:
            if (not check.get('command') or check.get('executed') is not True
                    or type(check.get('exit')) is not int or check['exit'] != 0):
                raise ValueError('validation check did not execute successfully')
            reference(root, check['output'])
        sources = receipt.get('source_sha256')
        if not isinstance(sources, dict) or not sources:
            raise ValueError('validation needs source_sha256 inputs')
        for name, digest in sources.items():
            path = local(root, name)
            if commit:
                proc = subprocess.run(['git', 'show', f'{commit}:{name}'], cwd=root, capture_output=True)
                if proc.returncode:
                    raise ValueError('validated source absent from implementation commit: ' + name)
                data = proc.stdout
            else:
                data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('validated source differs: ' + name)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [str(exc)]
    return []


def effectiveness_errors(root, value):
    try:
        import math
        measurement = json.loads(reference(root, value))
        before, after = measurement['before'], measurement['after']
        if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (before, after)):
            raise ValueError('finite nonnegative measurements required')
        if not all(isinstance(measurement.get(k), str) and measurement[k].strip()
                   for k in ('metric', 'unit', 'method')):
            raise ValueError('measurement needs metric, unit and reproducible method')
        direction = measurement.get('direction')
        if not ((direction == 'lower' and after < before) or (direction == 'higher' and after > before)):
            raise ValueError('verified effectiveness must show the stated improvement direction')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [str(exc)]
    return []


def record(root, output, sources, command, timeout=600):
    """Execute a bounded check once; changing source during it makes the receipt FAIL."""
    from team_accounting import atomic, number
    from bounded_command import terminate_group
    if not number(timeout) or timeout <= 0:
        raise ValueError('positive finite timeout required')
    root = Path(root).resolve()
    path = local(root, output)
    if path.exists():
        raise ValueError('evidence already exists; choose a new output')
    before = {name: hashlib.sha256(local(root, name).read_bytes()).hexdigest() for name in sources}
    if not before or not command:
        raise ValueError('source inputs and command required')
    path.parent.mkdir(parents=True, exist_ok=True)
    log = path.with_suffix('.txt')
    if log.exists():
        raise ValueError('output log already exists')
    with log.open('xb') as stream:
        proc = None
        try:
            proc = subprocess.Popen(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            code = 124
        except OSError as exc:
            stream.write(str(exc).encode())
            code = 127
        finally:
            if proc is not None:
                terminate_group(proc.pid, proc)
                proc.wait()
    after = {name: hashlib.sha256(local(root, name).read_bytes()).hexdigest()
             if local(root, name).is_file() else None for name in sources}
    receipt = {'version': 1, 'status': 'PASS' if code == 0 and before == after else 'FAIL',
               'source_sha256': before, 'stable': before == after,
               'checks': [{'command': command, 'executed': True, 'exit': code, 'output': ref(root, log)}]}
    atomic(path, receipt)
    return ref(root, path), receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', required=True)
    parser.add_argument('--source', action='append', required=True)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    evidence, receipt = record(args.root, args.output, args.source, command, args.timeout)
    print(json.dumps(evidence))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
