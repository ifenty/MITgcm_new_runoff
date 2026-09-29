"""Project configuration, path boundaries and reproducible source signatures.

Framework filenames are stable across deployments. Scientific paths, commands,
inputs and environment probes belong to esx/project.json. No module imports a
project's scientific code or sends external messages.
"""
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

STATE = 'devel-loop/loop_state'
FRAMEWORK_PATHS = ['tools/esx', '.claude', 'devel-loop', 'docs', 'esx', 'CLAUDE.md', '.gitignore']
EXCLUDED_PARTS = {'.git', '__pycache__', '.pytest_cache', 'loop_state'}
ROLES = ('arch', 'bob', 'richard', 'scout', 'prober', 'bisector', 'auditor')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def local(root, name):
    """Resolve a relative project path; reject traversal and external symlinks."""
    root = Path(root).resolve()
    require(isinstance(name, str) and name and name != '.' and not Path(name).is_absolute()
            and '..' not in Path(name).parts, f'invalid project path: {name!r}')
    path = root / name
    require(path.resolve().is_relative_to(root), f'path leaves project: {name}')
    return path


def config(root, ready=True):
    cfg = json.loads(local(root, 'esx/project.json').read_text())
    require(isinstance(cfg, dict), 'project.json must be an object')
    require(cfg.get('version') == 1, 'project.json version must be 1')
    for key in ('source_paths', 'test_paths', 'configuration_paths', 'output_paths', 'external_inputs', 'environment_variables'):
        require(isinstance(cfg.get(key), list) and all(isinstance(x, str) and x for x in cfg[key]), f'{key} must be a list of paths/names')
    for name in cfg['source_paths'] + cfg['test_paths'] + cfg['configuration_paths'] + cfg['output_paths']:
        local(root, name)
    for output in cfg['output_paths']:
        for source in cfg['source_paths'] + cfg['test_paths'] + cfg['configuration_paths'] + FRAMEWORK_PATHS:
            require(not (source == output or source.startswith(output.rstrip('/') + '/')),
                    f'output path would hide configured source/framework: {output}')
    require(isinstance(cfg.get('verification'), dict), 'verification must define named suites')
    for suite, commands in cfg['verification'].items():
        require(isinstance(commands, list), f'verification.{suite} must be a list of argv arrays')
        for argv in commands:
            require(isinstance(argv, list) and argv and all(isinstance(s, str) and s for s in argv), f'{suite}: invalid command')
    require(isinstance(cfg.get('toolchain_commands'), list), 'toolchain_commands must be argv arrays')
    for argv in cfg['toolchain_commands']:
        require(isinstance(argv, list) and argv and all(isinstance(s, str) and s for s in argv), 'invalid toolchain command')
    require(type(cfg.get('command_timeout_seconds')) in (int, float) and math.isfinite(cfg['command_timeout_seconds']) and cfg['command_timeout_seconds'] > 0,
            'command_timeout_seconds must be finite and positive')
    require(isinstance(cfg.get('mirrored_paths', []), list), 'mirrored_paths must be a list')
    for entry in cfg.get('mirrored_paths', []):
        require(isinstance(entry, dict) and isinstance(entry.get('canonical'), str) and entry['canonical']
                and isinstance(entry.get('mirrors'), list) and entry['mirrors']
                and all(isinstance(m, str) and m for m in entry['mirrors']),
                'each mirrored_paths entry needs a canonical path and a nonempty list of mirror paths')
        for name in [entry['canonical']] + entry['mirrors']:
            local(root, name)
    # Superseded documentation retained for provenance. Its links are expected to
    # be stale, so audit.py excludes it from instruction-link checking. Keeping
    # this in configuration means a project never edits framework code to retain
    # its own archive, and the exclusion stays visible in one reviewed place.
    require(isinstance(cfg.get('archive_paths', []), list)
            and all(isinstance(x, str) and x for x in cfg.get('archive_paths', [])),
            'archive_paths must be a list of project paths')
    for name in cfg.get('archive_paths', []):
        local(root, name)
    if ready:
        for key in ('project_id', 'project_name', 'mission'):
            require(isinstance(cfg.get(key), str) and cfg[key].strip(), f'complete esx/project.json: {key}')
        require(cfg['source_paths'] and cfg['test_paths'], 'configure source_paths and test_paths')
        require(cfg['verification'].get('structural') and cfg['verification'].get('scientific'),
                'configure nonempty structural and scientific acceptance suites')
        require(cfg.get('toolchain_commands'), 'configure toolchain_commands')
        for name in cfg['source_paths'] + cfg['test_paths'] + cfg['configuration_paths']:
            require(local(root, name).exists(), f'configured input is missing: {name}')
        # mirrored_paths existence/drift is checked by audit.py::audit_mirrors,
        # which gives a more specific message (what it should mirror, or
        # whether it's the canonical side that's missing) than a bare
        # "configured input is missing" would.
        for name in ('esx/project_profile.md', 'docs/code_map.md'):
            require('TODO_ESX' not in local(root, name).read_text(), f'complete {name}')
    return cfg


def mutable_loop_path(name):
    """Keep local loop state, locks, logs and terminal archives outside candidates."""
    return name.startswith(('.claude/esx-loop', '.claude/ralph-loop'))


def administrative(name):
    """Exclude records, not policy or executable witnesses, from acceptance."""
    base = 'devel-loop/self-improvement/'
    if name in {base + item for item in ('open-ESX-team-issues.md', 'closed-ESX-team-issues.md', 'process_changelog.md')}:
        return True
    return ((name.startswith(base + 'assessments/') and Path(name).suffix in ('.md','.json','.txt','.log'))
            or (name.startswith(base + 'records/') and Path(name).suffix == '.md'))


def archived(name, cfg):
    """Report whether a path sits under a configured `archive_paths` root.

    Archived documentation is superseded material a project keeps for provenance.
    Its links point at a layout that no longer exists, so link checking would
    report findings no one intends to fix. A configured scientific root always
    wins: real source/tests/configuration never become unchecked by being listed
    here.
    """
    science_roots = cfg['source_paths'] + cfg['test_paths'] + cfg['configuration_paths']
    if any(name == p or name.startswith(p.rstrip('/') + '/') for p in science_roots):
        return False
    return any(name == p or name.startswith(p.rstrip('/') + '/') for p in cfg.get('archive_paths', []))


def selected(name, cfg, scientific=False):
    # Explicit scientific roots always win over administrative conventions.
    science_roots = cfg['source_paths'] + cfg['test_paths'] + cfg['configuration_paths']
    if administrative(name) and not any(name == p or name.startswith(p.rstrip('/') + '/') for p in science_roots):
        return False
    if EXCLUDED_PARTS.intersection(Path(name).parts) or name.endswith(('.pyc', '.pyo')):
        return False
    if mutable_loop_path(name):
        return False
    if name == '.claude/worktrees' or name.startswith('.claude/worktrees/'):
        return False
    if any(name == p or name.startswith(p.rstrip('/') + '/') for p in cfg['output_paths']):
        return False
    roots = cfg['source_paths'] + cfg['test_paths'] + cfg['configuration_paths']
    roots += ['esx/project.json'] if scientific else FRAMEWORK_PATHS
    return any(name == p or name.startswith(p.rstrip('/') + '/') for p in roots)


def inventory_paths(root, cfg, scientific=False):
    """Include additions, deletions and ignored source through explicit path roots.

    Output directories must be separate from source/configuration roots. A source
    symlink leaving the project is refused; external datasets use external_inputs.
    """
    root = Path(root).resolve()
    roots = cfg['source_paths'] + cfg['test_paths'] + cfg['configuration_paths']
    roots += ['esx/project.json'] if scientific else FRAMEWORK_PATHS
    names = set()
    for name in roots:
        path = local(root, name)
        candidates = []
        if path.is_dir():
            require(not path.is_symlink(), f'configure the concrete directory instead of a symlink: {name}')
            for directory, folders, files in os.walk(path):
                folders[:] = [f for f in folders if selected((Path(directory) / f).relative_to(root).as_posix(), cfg, scientific)]
                for folder in folders:
                    require(not (Path(directory) / folder).is_symlink(), f'source directory symlink is not inventoried: {directory}/{folder}')
                candidates.extend(Path(directory) / f for f in files)
        else:
            candidates = [path]
        for candidate in candidates:
            rel = candidate.relative_to(root).as_posix()
            if selected(rel, cfg, scientific) and (candidate.is_file() or candidate.is_symlink()):
                local(root, rel)
                names.add(rel)
    return sorted(names)


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source_signature(root, scientific=False):
    root = Path(root).resolve()
    cfg = config(root)
    return digest({p: {'sha256': file_hash(local(root, p)), 'mode': local(root, p).stat().st_mode,
                       'link': os.readlink(root / p) if (root / p).is_symlink() else None}
                   for p in inventory_paths(root, cfg, scientific)})


def command(argv):
    return [sys.executable if s == '{python}' else s for s in argv]


def missing_inputs(root, cfg):
    """Configured external inputs absent from this checkout (e.g. gitignored captures)."""
    return [name for name in cfg.get('external_inputs', [])
            if not (Path(name) if Path(name).is_absolute() else Path(root) / name).is_file()]


def environment(root, cfg):
    """Measure declared tools, environment and actual external-input file bytes.

    Use small qualification datasets for routine checks. No unverified dataset
    checksum is accepted as a substitute for reading its configured input file.
    """
    probes = []
    for argv in cfg['toolchain_commands']:
        run = subprocess.run(command(argv), cwd=root, capture_output=True, text=True, timeout=30)
        require(run.returncode == 0, f'toolchain probe failed: {argv}')
        probes.append({'argv': command(argv), 'stdout': run.stdout, 'stderr': run.stderr})
    missing = missing_inputs(root, cfg)
    if missing:
        raise ValueError(f'{len(missing)} of {len(cfg["external_inputs"])} configured external_inputs are '
                         'missing from this checkout, so no verification evidence can be measured: '
                         + ', '.join(missing[:5]) + (' ...' if len(missing) > 5 else ''))
    inputs = {}
    for name in cfg['external_inputs']:
        path = Path(name) if Path(name).is_absolute() else root / name
        inputs[str(path.resolve())] = file_hash(path)
    return {'python': sys.version, 'python_optimization': sys.flags.optimize,
            'executable': sys.executable, 'platform': platform.platform(),
            'variables': {k: os.environ.get(k) for k in cfg['environment_variables']},
            'tools': probes, 'inputs': inputs}


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + '\n').encode())


def atomic_bytes(path, data):
    """Publish a complete file in its directory; failed replacement keeps old bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def json_file(root, name):
    return json.loads(local(root, name).read_text())


def main():
    """Print the exact 64-hex signature a footer's candidate_signature field requires.

    Distinct from issue_candidates.py's own content-addressed candidate
    signature: this is project.py::source_signature(root), the value
    workflow_policy.py::current_review and final_verification.py actually
    compare a reviewer's footer against.
    """
    import argparse
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    signature = sub.add_parser('signature', help='print source_signature(root) for a footer candidate_signature field')
    signature.add_argument('--scientific', action='store_true', help='use the narrower scientific-paths inventory')
    args = parser.parse_args()
    try:
        result = {'signature': source_signature(args.root, args.scientific)}
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f'project signature: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
