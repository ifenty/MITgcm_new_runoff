#!/usr/bin/env python3
"""Preserve review candidates as verified bytes, modes and relative symlinks.

The default scope follows the documentation inventory and includes configured source, tests, framework and configuration
files, including ignored and untracked additions. Explicit paths add witness inputs, including ignored files.
Content-addressed blobs make repeated captures inexpensive. Extraction writes
only to a new or empty scratch directory; it never changes the working tree.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

from doc_inventory import digest, paths as inventory_paths

from project import STATE
STORE = f'{STATE}/candidates'


def require(value, message):
    if not value:
        raise ValueError(message)


def safe_name(name):
    """Accept a canonical repository-relative path without traversal components."""
    require(isinstance(name, str) and name and '\0' not in name,
            'candidate path must be nonempty text')
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == name
            and name != '.', f'unsafe candidate path: {name!r}')
    return name


def safe_path(root, name):
    """Reject symlink parents so reads and artifact writes stay in their scope."""
    root = Path(root).resolve()
    path = root / safe_name(name)
    for parent in path.parents:
        if parent == root:
            break
        require(not parent.is_symlink(), f'candidate path has symlink parent: {name}')
    return path


def safe_link(name, target):
    """Require a relative symlink whose lexical destination stays in the snapshot."""
    require(isinstance(target, str) and target and '\0' not in target
            and not PurePosixPath(target).is_absolute(), f'unsafe symlink target: {name}')
    parts = list(PurePosixPath(name).parent.parts)
    for part in PurePosixPath(target).parts:
        if part == '..':
            require(parts, f'symlink leaves snapshot: {name}')
            parts.pop()
        elif part != '.':
            parts.append(part)


def validate_links(files):
    """Resolve links within the manifest to reject escaping chains and cycles."""
    for name, entry in files.items():
        if entry.get('kind') != 'symlink':
            continue
        remaining = list(PurePosixPath(name).parts)
        resolved, followed = [], 0
        while remaining:
            part = remaining.pop(0)
            if part == '..':
                require(resolved, f'symlink chain leaves snapshot: {name}')
                resolved.pop()
                continue
            if part == '.':
                continue
            candidate = '/'.join([*resolved, part])
            link = files.get(candidate, {})
            if link.get('kind') == 'symlink':
                followed += 1
                require(followed <= 40, f'cyclic or excessive symlink chain: {name}')
                safe_link(candidate, link.get('target'))
                remaining = list(PurePosixPath(link['target']).parts) + remaining
            else:
                resolved.append(part)
        require(files.get('/'.join(resolved), {}).get('kind') == 'file',
                f'symlink destination is absent from snapshot: {name}')


def write_once(root, name, data):
    """Store identical evidence once and detect replaced or damaged artifacts."""
    path = safe_path(root, name)
    require(not path.is_symlink(), f'evidence is a symlink: {name}')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(data)
    except FileExistsError:
        require(path.read_bytes() == data, f'candidate artifact is corrupt: {name}')


def measure(root, scope, save_blobs=False):
    """Capture all selected regular files and links without following link leaves."""
    require(isinstance(scope, dict) and scope.get('inventory') is True
            and isinstance(scope.get('extra'), list), 'invalid candidate scope')
    names = sorted(set(inventory_paths(root)) | {safe_name(n) for n in scope['extra']})
    files = {}
    for name in names:
        if name in files:
            continue
        path = safe_path(root, name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        mode = stat.S_IMODE(info.st_mode) & 0o777
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            safe_link(name, target)
            try:
                require(path.resolve().is_relative_to(Path(root).resolve()),
                        f'symlink leaves repository: {name}')
            except RuntimeError as exc:
                raise ValueError(f'cyclic symlink: {name}') from exc
            files[name] = {'kind': 'symlink', 'target': target}
            # Retain the local link destination as bytes as well. This makes a
            # symlink into a configured output directory reproducible and makes
            # changes to the consumed target invalidate the snapshot.
            destination = Path(os.path.normpath(str(Path(name).parent / target))).as_posix()
            destination = safe_name(destination)
            require(safe_path(root, destination).is_file(),
                    f'candidate symlink must resolve to a regular file: {name}')
            if destination not in files:
                names.append(destination)
        else:
            require(stat.S_ISREG(info.st_mode), f'candidate input is not a regular file: {name}')
            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            files[name] = {'kind': 'file', 'sha256': sha, 'size': len(data), 'mode': mode}
            if save_blobs:
                write_once(root, f'{STORE}/blobs/{sha}', data)
    validate_links(files)
    return dict(sorted(files.items()))


def capture(root, issue, baseline=None, paths=None):
    """Return a stable content-addressed reference for the current candidate."""
    require(isinstance(issue, str) and issue.strip(), 'candidate issue ID is required')
    scope = {'inventory': True, 'extra': sorted(set(paths or []))}
    files = measure(root, scope, save_blobs=True)
    payload = {'version': 1, 'kind': 'candidate', 'issue_id': issue, 'baseline': baseline,
               'scope': scope, 'files': files, 'signature': digest(files)}
    sha = digest(payload)
    ref = {'path': f'{STORE}/{sha}.json', 'sha256': sha}
    write_once(root, ref['path'], (json.dumps(payload, sort_keys=True, indent=2) + '\n').encode())
    return ref


def blob(root, sha):
    """Read and verify one raw file without following evidence symlinks."""
    require(isinstance(sha, str) and len(sha) == 64
            and all(c in '0123456789abcdef' for c in sha), 'invalid candidate blob hash')
    path = safe_path(root, f'{STORE}/blobs/{sha}')
    require(not path.is_symlink(), 'candidate blob cannot be a symlink')
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == sha, 'candidate blob hash mismatch')
    return data


def load(root, ref, issue):
    """Validate identity, path safety and every retained file's actual contents."""
    require(isinstance(ref, dict), 'candidate reference is required')
    sha = ref.get('sha256')
    require(isinstance(sha, str) and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha)
            and ref.get('path') == f'{STORE}/{sha}.json', 'invalid candidate reference')
    path = safe_path(root, ref['path'])
    require(not path.is_symlink(), 'candidate manifest cannot be a symlink')
    record = json.loads(path.read_text())
    require(digest(record) == sha, 'candidate manifest hash mismatch')
    require(record.get('version') == 1 and record.get('kind') == 'candidate'
            and record.get('issue_id') == issue, 'candidate identity/version mismatch')
    files = record.get('files')
    require(isinstance(files, dict) and record.get('signature') == digest(files),
            'candidate signature mismatch')
    for name, entry in files.items():
        safe_name(name)
        require(isinstance(entry, dict), 'invalid candidate file entry')
        for parent in PurePosixPath(name).parents:
            require(str(parent) not in files, f'candidate parent is also a file: {name}')
        if entry.get('kind') == 'symlink':
            safe_link(name, entry.get('target'))
        else:
            require(entry.get('kind') == 'file' and type(entry.get('mode')) is int
                    and 0 <= entry['mode'] <= 0o777, f'invalid file mode/type: {name}')
            require(len(blob(root, entry.get('sha256'))) == entry.get('size'),
                    f'candidate file size mismatch: {name}')
    scope = record.get('scope')
    require(isinstance(scope, dict) and scope.get('inventory') is True
            and isinstance(scope.get('extra'), list), 'invalid candidate scope')
    for name in scope['extra']:
        safe_name(name)
    validate_links(files)
    return record


def check_current(root, ref, issue):
    """Reject source, mode, link, addition or deletion changes since capture."""
    record = load(root, ref, issue)
    require(record['files'] == measure(root, record['scope']),
            'candidate snapshot is stale; capture and review the changed candidate')
    return record


def compare(root, before_ref, after_ref, issue):
    """Compare retained bytes directly, including untracked and deleted files."""
    before, after = load(root, before_ref, issue)['files'], load(root, after_ref, issue)['files']
    rows, text = [], []
    for name in sorted(before.keys() | after.keys()):
        a, b = before.get(name), after.get(name)
        if a == b:
            continue
        rows.append({'path': name, 'change': 'added' if a is None else 'removed' if b is None else 'modified',
                     'before': a, 'after': b})
        def lines(entry):
            if entry is None:
                return []
            data = blob(root, entry['sha256']) if entry['kind'] == 'file' else entry['target'].encode()
            return data.decode('utf-8').splitlines(keepends=True)
        try:
            text.extend(difflib.unified_diff(lines(a), lines(b), fromfile='before/' + name, tofile='after/' + name))
        except UnicodeDecodeError:
            text.append(f'Binary content changed: {name}\n')
    return {'before': before_ref, 'after': after_ref, 'changes': rows, 'diff': ''.join(text)}


def extract(root, ref, issue, destination):
    """Extract verified evidence to empty scratch storage without traversing links."""
    record = load(root, ref, issue)
    dest = Path(destination).absolute()
    require(dest == dest.resolve(), 'scratch destination or parent is a symlink')
    require(not dest.exists() or (dest.is_dir() and not any(dest.iterdir())),
            'scratch destination must be a new or empty directory')
    require(not dest.is_relative_to(Path(root).resolve()), 'scratch destination must be outside the repository')
    dest.mkdir(parents=True, exist_ok=True)
    for name, entry in record['files'].items():
        path = safe_path(dest, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if entry['kind'] == 'symlink':
            path.symlink_to(entry['target'])
        else:
            with path.open('xb') as stream:
                stream.write(blob(root, entry['sha256']))
            path.chmod(entry['mode'])
    return {'destination': str(dest), 'files': len(record['files']), 'signature': record['signature']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    capture_parser = sub.add_parser('capture', help='retain the working candidate and extra witness inputs')
    capture_parser.add_argument('--issue', required=True)
    capture_parser.add_argument('--baseline', type=json.loads)
    capture_parser.add_argument('--path', action='append', default=[])
    for name in ('check', 'extract', 'diff'):
        command = sub.add_parser(name)
        command.add_argument('--issue', required=True)
        command.add_argument('--candidate', type=json.loads, required=True)
        if name == 'extract':
            command.add_argument('--destination', type=Path, required=True)
        if name == 'diff':
            command.add_argument('--before', type=json.loads, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'capture':
            result = capture(args.root, args.issue, args.baseline, args.path)
        elif args.command == 'check':
            result = {'valid': True, 'signature': check_current(args.root, args.candidate, args.issue)['signature']}
        elif args.command == 'extract':
            result = extract(args.root, args.candidate, args.issue, args.destination)
        else:
            result = compare(args.root, args.before, args.candidate, args.issue)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f'candidate snapshot: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
