"""Recoverable, compare-and-swap promotion for scientific and team ledgers.

Stage and validate complete text before touching originals. A locked, fsynced
journal preserves before/after bytes across multi-file replacements. Cooperative
readers refuse a pending transaction. Recovery validates before completing or
rolls back; unexpected third-party edits are never overwritten.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from doc_inventory import local
import self_improvement as si

STATE = Path('devel-loop/loop_state/ledger-transactions')


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest() if text is not None else None


def read(root, name):
    path = local(root, name)
    return path.read_text() if path.is_file() else None


def replace(root, name, text):
    path = local(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is None:
        path.unlink(missing_ok=True)
    else:
        fd, tmp = tempfile.mkstemp(prefix='.ledger-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            Path(tmp).unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def lock(root):
    folder = Path(root) / STATE
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'writer.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def pending(root):
    return (Path(root) / STATE / 'pending.json').is_file()


def validate(root, family, updates):
    if family == 'team':
        return si.validate(root, updates)
    if family != 'esx':
        return ['unknown ledger family']
    from loop_gate import Gate
    token = si.STAGED_RECORDS.set((str(Path(root).resolve()), updates))
    try:
        done = Gate(root, updates).check_done()
        return [] if done.get('outcome') == 'completed' else ['scientific promotion requires completed closeout']
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return [str(exc)]
    finally:
        si.STAGED_RECORDS.reset(token)


def transact(root, family, updates, expected, apply=False):
    root = Path(root).resolve()
    with lock(root):
        if pending(root):
            raise ValueError('pending ledger transaction; run self_improvement.py recover first')
        before = {name: read(root, name) for name in updates}
        if {name: digest(text) for name, text in before.items()} != expected:
            raise ValueError('ledger changed since preparation; regenerate promotion')
        errors = validate(root, family, updates)
        if errors:
            raise ValueError('; '.join(errors))
        result = {'status': 'applied' if apply else 'preview', 'family': family, 'paths': sorted(updates)}
        if not apply:
            return result
        record = {'version': 1, 'family': family, 'before': before, 'after': updates}
        transaction_id = digest(json.dumps(record, sort_keys=True))
        journal = str(STATE / 'pending.json')
        replace(root, journal, json.dumps(record, sort_keys=True, indent=2))
        try:
            for name, text in updates.items():
                if read(root, name) != before[name]:
                    raise ValueError('concurrent edit during promotion: ' + name)
                replace(root, name, text)
        except Exception:
            # Ordinary failures restore originals. Hard termination leaves the
            # journal for restart recovery. Never erase an unrelated concurrent edit.
            for name in reversed(list(updates)):
                if read(root, name) == updates[name]:
                    replace(root, name, before[name])
            if all(read(root, name) == before[name] for name in updates):
                replace(root, journal, None)
            raise
        replace(root, str(STATE / (transaction_id + '.json')), json.dumps(record, sort_keys=True, indent=2))
        replace(root, journal, None)
        result['transaction'] = transaction_id
        return result


def recover(root, rollback=False):
    root = Path(root).resolve()
    with lock(root):
        journal = str(STATE / 'pending.json')
        if not pending(root):
            return {'status': 'no_pending_transaction'}
        record = json.loads(local(root, journal).read_text())
        for name in record['after']:
            if read(root, name) not in (record['before'][name], record['after'][name]):
                raise ValueError('recovery refuses concurrent edit: ' + name)
        if not rollback:
            errors = validate(root, record['family'], record['after'])
            if errors:
                raise ValueError('recovery validation failed; rollback remains available: ' + '; '.join(errors))
        target = record['before'] if rollback else record['after']
        for name, text in target.items():
            replace(root, name, text)
        transaction_id = digest(json.dumps(record, sort_keys=True))
        replace(root, str(STATE / (transaction_id + '.json')), json.dumps(record, sort_keys=True, indent=2))
        replace(root, journal, None)
        return {'status': 'rolled_back' if rollback else 'completed', 'transaction': transaction_id}


def resolved_entry(text, resolved_at, summary, iteration):
    """Return an open entry in its closed form; every other byte is preserved."""
    lines = text.splitlines(keepends=True)
    lines[0] = '## 🟢 RESOLVED: ' + lines[0][3:].split(':', 1)[-1].strip() + '\n'
    text = re.sub(r'^\*\*Status\*\*\s*:.*$', '**Status**: Resolved', ''.join(lines), count=1, flags=re.M)
    stamp = '**Date Resolved**: ' + resolved_at
    if re.search(r'^\*\*Date Resolved\*\*\s*:.*$', text, re.M):
        text = re.sub(r'^\*\*Date Resolved\*\*\s*:.*$', lambda _: stamp, text, count=1, flags=re.M)
    else:
        anchor = re.search(r'^\*\*Date Identified\*\*\s*:.*$', text, re.M) or re.search(r'^\*\*Status\*\*.*$', text, re.M)
        text = text[:anchor.end()] + '\n' + stamp + text[anchor.end():]
    note = ' '.join(str(summary).split())
    return (text.rstrip() + '\n\n### Gate acceptance\n\nAccepted by `loop_gate.py --check-done` at ' + resolved_at
            + ' for iteration ' + str(iteration) + '. ' + note + '\n')


def close_on_acceptance(root, uuid, resolved_at, summary, iteration):
    """Move an open ESX entry to closed_issues.md only if the staged move passes --check-done.

    Returns the applied (before, after) texts, or None when there is no single open
    entry to move. A validation failure raises and leaves both ledgers untouched.
    """
    root = Path(root).resolve()
    staged = staged_close(root, uuid, resolved_at, summary, iteration)
    if staged is None:
        return None
    before, after = staged
    transact(root, 'esx', after, {name: digest(text) for name, text in before.items()}, apply=True)
    return before, after


def staged_close(root, uuid, resolved_at, summary, iteration):
    """Return the (before, after) ledger texts of an acceptance move without writing, or None."""
    root = Path(root).resolve()
    names = ('open_issues.md', 'closed_issues.md')
    old_open, old_closed = (read(root, name) for name in names)
    if old_open is None or old_closed is None:
        return None
    matches = [row for row in si.parse(root / names[0], text=old_open) if row.uuid == uuid]
    if len(matches) != 1 or any(row.uuid == uuid for row in si.parse(root / names[1], text=old_closed)):
        return None
    issue = matches[0]
    start = sum(len(line) for line in old_open.splitlines(keepends=True)[:issue.line - 1])
    end = start + len(issue.text.rstrip())
    end += len(old_open[end:]) - len(old_open[end:].lstrip())
    remaining = old_open[:start] + old_open[end:] if end < len(old_open) else old_open[:start].rstrip() + '\n'
    after = {names[0]: remaining,
             names[1]: old_closed.rstrip() + '\n\n' + resolved_entry(issue.text, resolved_at, summary, iteration)}
    return {names[0]: old_open, names[1]: old_closed}, after


def with_staged(root, updates, check):
    """Run check(gate) against staged ledger texts, writing nothing."""
    from loop_gate import Gate
    token = si.STAGED_RECORDS.set((str(Path(root).resolve()), updates))
    try:
        return check(Gate(root, updates))
    finally:
        si.STAGED_RECORDS.reset(token)


def revert(root, before, after):
    """Restore ledgers moved by close_on_acceptance when final acceptance fails."""
    with lock(root):
        for name in after:
            if read(root, name) == after[name]:
                replace(root, name, before[name])


def promote(root, family, uuid, closure, expected_sha256, apply=False):
    root = Path(root).resolve()
    opened, closed = (si.OPEN, si.CLOSED) if family == 'team' else (Path('open_issues.md'), Path('closed_issues.md'))
    old_open, old_closed = read(root, str(opened)), read(root, str(closed))
    if old_open is None or old_closed is None:
        raise ValueError('both ledgers must exist before promotion')
    matches = [row for row in si.parse(root / opened, text=old_open) if row.uuid == uuid]
    existing = [row for row in si.parse(root / closed, text=old_closed) if row.uuid == uuid]
    closure_sha = digest(json.dumps(closure, sort_keys=True))
    if not matches and len(existing) == 1 and existing[0].fields.get('Original-SHA256') == expected_sha256:
        if existing[0].fields.get('Closure-SHA256') != closure_sha:
            raise ValueError('already promoted with a different closure request')
        errors = validate(root, family, {})
        if errors:
            raise ValueError('; '.join(errors))
        return {'status': 'already_promoted', 'issue': uuid}
    if len(matches) != 1 or existing:
        raise ValueError('issue must have exactly one open owner and no closed owner')
    issue = matches[0]
    if digest(issue.text) != expected_sha256:
        raise ValueError('issue changed since closure preparation')
    fields = closure.get('fields', {})
    sections = closure.get('sections', {})
    if family == 'esx':
        from loop_gate import Gate
        done = Gate(root).read('issue-done.json')
        if not done or done.get('id') != uuid:
            raise ValueError('prepare issue-done.json for this UUID before promotion')
        if not fields.get('Date Resolved') or len(sections.get('Resolution', '')) < 20:
            raise ValueError('ESX closure needs Date Resolved and a substantive Resolution section')
    if any(k in fields for k in ('UUID', 'Date Identified', 'Record-Version', 'Migration-Source', 'Original-SHA256', 'Original-Record', 'Closure-SHA256')):
        raise ValueError('closure may not replace original identity/provenance')
    if set(sections) & set(issue.sections):
        raise ValueError('closure sections must append; original sections are preserved')
    text = issue.text
    text = re.sub(r'^## .*$', '## 🟢 RESOLVED: ' + issue.title.split(':', 1)[-1].strip(), text, count=1, flags=re.M)
    text = re.sub(r'^\*\*(?:Record-Version|Migration-Source)\*\*:.*\n', '', text, flags=re.M)
    for name, value in fields.items():
        if '\n' in name or '\n' in str(value):
            raise ValueError('closure fields must be single lines')
        pattern = r'^\*\*' + re.escape(name) + r'\*\*:.*$'
        replacement = '**' + name + '**: ' + str(value)
        text = re.sub(pattern, lambda _: replacement, text, flags=re.M) if re.search(pattern, text, re.M) else text + '\n' + replacement + '\n'
    text += '\n**Original-SHA256**: ' + expected_sha256 + '\n'
    text += '**Closure-SHA256**: ' + closure_sha + '\n'
    original = str(si.BASE / 'records' / (expected_sha256 + '.md'))
    text += '**Original-Record**: ' + original + '#' + expected_sha256 + '\n'
    for name, body in sections.items():
        if '\n' in name:
            raise ValueError('invalid closure section name')
        text += '\n### ' + name + '\n\n' + body.strip() + '\n'
    # UUID source span uses parser's exact normalized block; preserve all other bytes.
    start = sum(len(line) for line in old_open.splitlines(keepends=True)[:issue.line - 1])
    end = start + len(issue.text.rstrip())
    updates = {str(opened): old_open[:start] + old_open[end:],
               str(closed): old_closed.rstrip() + '\n\n' + text,
               original: issue.text}
    index_path = str(si.INDEX) if family == 'team' else None
    expected = {str(opened): digest(old_open), str(closed): digest(old_closed),
                original: digest(read(root, original))}
    if index_path:
        expected[index_path] = digest(read(root, index_path))
    if expected[original] not in (None, digest(issue.text)):
        raise ValueError('original archive exists with different bytes')
    if family == 'team':
        updates[str(si.INDEX)] = si.index_text(si.parse(root / closed, text=updates[str(closed)]))
    return transact(root, family, updates, expected, apply)
