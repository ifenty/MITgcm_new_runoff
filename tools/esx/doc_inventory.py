#!/usr/bin/env python3
"""Content-addressed source inventory for documentation review.

Read configured source paths, including ignored, untracked and pre-existing working
changes. Parse Python without importing it. Qualified symbols include nested
functions; duplicate definitions of one name are reviewed as a group. The module
row covers imports, constants, file headers, non-Python code and documentation.
"""
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tokenize

MAP = 'docs/code_map.md'
from project import config, inventory_paths, selected

ROOT_FILES = {'CLAUDE.md', '.gitignore', '.claude/settings.json', 'esx/project.json'}


def digest(value):
    """Hash canonical JSON; ordering of object keys has no semantic effect."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def local(root, name):
    """Require a repository-relative path and reject symlinks outside the root."""
    root = Path(root).resolve()
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError(f'invalid repository path: {name!r}')
    path = root / name
    if not path.resolve().is_relative_to(root):
        raise ValueError(f'path leaves repository: {name}')
    return path


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, check=True)
    return result.stdout


def included(name, tracked, root):
    return selected(name, config(root, ready=False))


def paths(root):
    """Inventory configured paths, including ignored and untracked source files."""
    return inventory_paths(root, config(root, ready=False))


def python_units(text, filename):
    """Measure lexical and documentation changes for each qualified AST definition.

    Parent spans include nested definitions, so their enclosing contract is also
    reviewed. Comments preceding a definition belong to the module row. Line
    numbers are display data and do not make an otherwise unchanged symbol stale.
    """
    tree = ast.parse(text, filename=filename)
    lines = text.splitlines(keepends=True)
    comments = [(t.start[0], t.string) for t in tokenize.generate_tokens(io.StringIO(text).readline)
                if t.type == tokenize.COMMENT]
    nodes = {}

    def visit(node, parents=()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            parents = (*parents, node.name)
            nodes.setdefault('.'.join(parents), []).append(node)
        for child in ast.iter_child_nodes(node):
            visit(child, parents)

    visit(tree)
    units = {}
    for name, group in nodes.items():
        spans = [(min([n.lineno] + [d.lineno for d in n.decorator_list]), n.end_lineno) for n in group]
        source = [''.join(lines[a-1:b]) for a, b in spans]
        prose = [ast.get_docstring(n, clean=False) for n in group]
        prose += [c for line, c in comments if any(a <= line <= b for a, b in spans)]
        units[name] = {'sha256': digest(source), 'docs': digest(prose),
                       'has_docs': any(prose), 'spans': spans}
    module_prose = [ast.get_docstring(n, clean=False) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    module_prose += [c for _, c in comments]
    units['<module>'] = {'sha256': digest(text), 'docs': digest(module_prose),
                         'has_docs': any(module_prose), 'spans': [[1, len(lines)]]}
    # Constants/imports and module-level execution can change a function's
    # interpretation while its own text stays identical, so every unit carries a
    # digest of the module's non-definition text.
    #
    # This is built textually, by removing the line spans of the top-level
    # definitions, rather than from `ast.dump` of a definition-stripped tree.
    # `ast.dump` renders whichever fields the running interpreter's AST carries,
    # so its output moves between Python versions even for identical source:
    # sealing a report under one interpreter and checking it under another
    # reported the tree as stale and blamed the document
    # (TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001; measured on RUNOFF-005, where the
    # same unmodified tree digested differently under 3.10.19 and 3.13.12 and
    # cost two reviewers a must-fix each). Line numbers and the source text are
    # interpreter-independent, so this form is stable across versions while
    # still changing whenever module-level code does.
    dropped = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            dropped.update(range(first, node.end_lineno + 1))
    context = digest([line for number, line in enumerate(lines, 1)
                      if number not in dropped])
    for unit in units.values():
        unit['context'] = context
    return units


def measure(data, filename):
    if filename.endswith('.py'):
        return python_units(data.decode('utf-8-sig'), filename)
    sha = hashlib.sha256(data).hexdigest()
    suffix = Path(filename).suffix.lower()
    text = data.decode('utf-8', errors='replace')
    if suffix in ('.md', '.rst', '.tex', '.txt'):
        prose = text
    else:
        # Recognize full-line source comments. For languages without a comment
        # extractor, an owning Markdown contract provides reviewable prose.
        prose = '\n'.join(line for line in text.splitlines() if
                          (suffix == '.sh' and line.lstrip().startswith('#')
                           and not line.startswith('#!')) or
                          (suffix in ('.f', '.for', '.inc') and line[:1] in ('c', 'C', '*', '!')) or
                          (suffix == '.f90' and line.lstrip().startswith('!')))
    return {'<module>': {'sha256': sha, 'docs': digest(prose), 'has_docs': bool(prose),
                         'spans': [[1, data.count(b'\n') + 1]]}}


def snapshot(root, git_base=None):
    """Measure the working tree, or a commit for explicit recovery of a lost baseline.

    A commit recovery includes every intervening change, including work predating
    this issue. The review must cover that larger set; no inferred exclusions.
    """
    files = {}
    if git_base:
        commit = git(root, 'rev-parse', '--verify', git_base + '^{commit}').decode().strip()
        names = git(root, 'ls-tree', '-r', '--name-only', '-z', commit).decode().split('\0')
    else:
        commit = None
        names = paths(root)
    for name in names:
        if not name or (git_base and not included(name, True, root)):
            continue
        if git_base:
            data = git(root, 'show', f'{commit}:{name}')
        else:
            path = local(root, name)
            if not path.is_file():
                continue
            data = path.read_bytes()
        files[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'units': measure(data, name)}
        if name.endswith('.md'):
            files[name]['sections'] = {key: digest(value) for key, value in markdown_sections(data.decode()).items()}
    return files


def changes(before, after):
    """Return stable target IDs for file/module and symbol changes, including removals."""
    rows = []
    for path in sorted(before.keys() | after.keys()):
        old, new = before.get(path, {}), after.get(path, {})
        if old.get('sha256') == new.get('sha256'):
            continue
        old_units, new_units = old.get('units', {}), new.get('units', {})
        for symbol in sorted(old_units.keys() | new_units.keys()):
            a, b = old_units.get(symbol), new_units.get(symbol)
            if a and b and a['sha256'] == b['sha256']:
                continue
            rows.append({'target': f'{path}::{symbol}',
                         'change': 'added' if a is None else 'removed' if b is None else 'modified'})
    return rows


def slug(heading):
    return re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')


def markdown_sections(text):
    """Index unique ATX heading slugs, excluding heading-like lines in fences."""
    headings = []
    offset, fence = 0, None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        if fence is None and not marker:
            h = re.match(r'^(#{1,6})[ \t]+(.+?)\s*#*\s*$', line.rstrip('\n'))
            if h:
                headings.append((offset, len(h[1]), slug(h[2])))
        offset += len(line)
    result, duplicates = {}, set()
    for index, (start, level, key) in enumerate(headings):
        end = next((h[0] for h in headings[index+1:] if h[1] <= level), len(text))
        if key in result:
            duplicates.add(key)
        result[key] = text[start:end]
    return {k: v for k, v in result.items() if k not in duplicates}


def excerpt(root, ref):
    """Resolve an exact Markdown heading slug or qualified source symbol.

    Return the selected text and a hash that ignores unrelated sections/symbols.
    Confirm dynamic call relationships by inspecting imports, dispatch and consumers.
    """
    if not isinstance(ref, str):
        raise ValueError('reference must be text')
    if '::' in ref:
        path, symbol = ref.split('::', 1)
        data = local(root, path).read_bytes()
        units = measure(data, path)
        unit = units.get(symbol)
        if unit is None:
            raise ValueError(f'unknown symbol: {ref}')
        lines = data.decode('utf-8-sig').splitlines()
        selected = '\n'.join('\n'.join(lines[a-1:b]) for a, b in unit['spans'])
        parents = ['.'.join(symbol.split('.')[:i]) for i in range(1, len(symbol.split('.')))]
        components = {'source': unit['sha256'], 'module_context': unit.get('context'),
                      'enclosing': digest({name: units[name]['sha256'] for name in parents if name in units})}
        return {'ref': ref, 'sha256': digest(components), 'components': components, 'text': selected}
    path, sep, anchor = ref.partition('#')
    text = local(root, path).read_text(encoding='utf-8')
    if sep:
        selected = markdown_sections(text).get(anchor)
        if selected is None:
            raise ValueError(f'heading must resolve uniquely: {ref}')
        text = selected
    return {'ref': ref, 'sha256': digest(text), 'components': {'documentation': digest(text)}, 'text': text}
