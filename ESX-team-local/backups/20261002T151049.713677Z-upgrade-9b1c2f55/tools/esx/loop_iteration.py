"""Content-bound successful-start receipts using ESX's frozen iteration timestamp."""
import hashlib
import json
from pathlib import Path
from project import STATE, atomic_json, digest, now


def matches(start, done):
    if not isinstance(start, dict) or not isinstance(done, dict):
        return False
    return (bool(start.get('timestamp')) and start.get('id') == done.get('id')
            and start['timestamp'] == done.get('timestamp')
            and (start.get('state_version', 1) < 2 or start.get('iteration') == done.get('iteration')))


def finished(start, history):
    return any(matches(start, row) for row in history)


def record_start(root, start):
    record = {'version': 1, 'id': start['id'], 'iteration': start.get('iteration'),
              'timestamp': start['timestamp'], 'start_sha256': digest(start), 'validated_at': now()}
    atomic_json(Path(root) / STATE / 'start-receipts' / (digest(start) + '.json'), record)
    return record


def start_status(root, start):
    if not start:
        return {'validated': False, 'reason': 'missing start'}
    path = Path(root) / STATE / 'start-receipts' / (digest(start) + '.json')
    try:
        receipt = json.loads(path.read_text())
        if receipt.get('start_sha256') != digest(start) or not matches(start, receipt) or not receipt.get('validated_at'):
            raise ValueError('start receipt mismatch')
        return {'validated': True, 'receipt': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    except (ValueError, OSError, TypeError):
        return {'validated': False, 'reason': 'no matching successful start', 'legacy': start.get('state_version', 1) < 2}
