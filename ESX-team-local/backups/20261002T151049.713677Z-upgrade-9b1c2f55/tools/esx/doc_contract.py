#!/usr/bin/env python3
"""Create and validate issue-local navigation and documentation evidence.

Artifacts are immutable, content-addressed JSON beneath loop_state/maintenance.
The gate validates identities, coverage and freshness. Authors and reviewers
remain responsible for whether the recorded explanations match the program.
"""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import sys

from doc_inventory import MAP, changes, digest, excerpt, git, local, snapshot

from project import STATE
STORE = f'{STATE}/maintenance'
ROLES = ('arch', 'bob', 'richard', 'scout', 'prober', 'bisector', 'auditor')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def explanation(value):
    return isinstance(value, str) and len(value.strip()) >= 40


def evidence_path(root, name):
    """Resolve stored evidence without traversing symlink parents or leaves."""
    from issue_candidates import safe_path
    path = safe_path(root, name)
    require(not path.is_symlink(), f'evidence path cannot be a symlink: {name}')
    return path


def save(root, payload):
    """Write once under a digest-derived name; identical payloads reuse one artifact."""
    sha = digest(payload)
    ref = {'path': f'{STORE}/{sha}.json', 'sha256': sha}
    path = evidence_path(root, ref['path'])
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x') as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write('\n')
    except FileExistsError:
        require(json.loads(path.read_text()) == payload, 'existing evidence artifact is corrupt')
    return ref


def load(root, ref, kind, issue):
    require(isinstance(ref, dict), f'{kind} evidence reference is required')
    sha, name = ref.get('sha256'), ref.get('path')
    require(isinstance(sha, str) and len(sha) == 64 and name == f'{STORE}/{sha}.json',
            f'{kind} must reference a content-addressed maintenance artifact')
    payload = json.loads(evidence_path(root, name).read_text())
    require(digest(payload) == sha, f'{kind} evidence hash mismatch')
    require(isinstance(payload, dict), f'{kind} evidence must be an object')
    require(payload.get('version') == 1 and payload.get('kind') == kind,
            f'invalid {kind} evidence version/type')
    require(payload.get('issue_id') == issue, f'{kind} evidence belongs to another issue')
    if kind == 'baseline':
        require(isinstance(payload.get('files'), dict) and MAP in payload['files'],
                'baseline must include the code map and source inventory')
        if payload.get('source_snapshot'):
            from issue_candidates import load as load_candidate
            load_candidate(root, payload['source_snapshot'], issue)
    return payload


def envelope(kind, issue):
    require(isinstance(issue, str) and bool(issue.strip()), 'issue ID is required')
    return {'version': 1, 'kind': kind, 'issue_id': issue,
            'created_at': dt.datetime.now(dt.timezone.utc).isoformat()}


def baseline(root, issue, git_base=None, reason=None):
    """Reuse the issue's original baseline across every correction and loop turn.

    A write-once pin prevents a fresh working-tree capture from hiding cumulative
    edits. Existing issue history supplies the earliest recorded baseline when
    adopting an issue. Explicit commit recovery is for an absent original only.
    """
    require(not git_base or explanation(reason), 'commit recovery requires a substantive recovery reason')
    original = original_baseline(root, issue)
    if original:
        require(not git_base, 'original maintenance baseline already exists; commit recovery cannot replace it')
        pin_baseline(root, issue, original)
        return original
    payload = envelope('baseline', issue)
    commit = git(root, 'rev-parse', '--verify', git_base + '^{commit}').decode().strip() if git_base else None
    payload.update(files=snapshot(root, commit), recovery={'git_base': commit, 'requested_ref': git_base, 'reason': reason})
    if not commit:
        from issue_candidates import capture, load as load_candidate
        source_ref = capture(root, issue)
        captured = load_candidate(root, source_ref, issue)['files']
        require(set(payload['files']).issubset(captured)
                and all(name in captured and (captured[name]['kind'] == 'symlink'
                    or captured[name]['sha256'] == info['sha256'])
                    for name, info in payload['files'].items()),
                'source changed during baseline capture; capture again after edits finish')
        payload['source_snapshot'] = source_ref
    ref = save(root, payload)
    pin_baseline(root, issue, ref)
    return ref


def pin_path(root, issue):
    """Key original-baseline registrations by issue identity without path interpolation."""
    require(isinstance(issue, str) and issue.strip(), 'issue ID is required')
    return evidence_path(root, f'{STORE}/original/{digest(issue)}.json')


def original_baseline(root, issue):
    """Find the durable original or earliest retained history without changing records."""
    path = pin_path(root, issue)
    if path.exists():
        require(not path.is_symlink(), 'original maintenance baseline pin cannot be a symlink')
        record = json.loads(path.read_text())
        require(record.get('issue_id') == issue, 'original baseline pin identity mismatch')
        ref = record.get('baseline')
        load(root, ref, 'baseline', issue)
        return ref
    history = evidence_path(root, f'{STATE}/loop_history.jsonl')
    if history.exists():
        for line in history.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            require(isinstance(row, dict), 'baseline history row must be an object')
            ref = (row.get('maintenance') or {}).get('baseline')
            if row.get('id') == issue and ref:
                load(root, ref, 'baseline', issue)
                return ref
    start = evidence_path(root, f'{STATE}/issue-start.json')
    if start.exists():
        row = json.loads(start.read_text())
        ref = (row.get('maintenance') or {}).get('baseline')
        if row.get('id') == issue and ref:
            load(root, ref, 'baseline', issue)
            return ref
    return None


def pin_baseline(root, issue, ref):
    """Write the original registration once; concurrent attempts must agree."""
    load(root, ref, 'baseline', issue)
    path = pin_path(root, issue)
    require(not path.is_symlink(), 'original maintenance baseline pin cannot be a symlink')
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'issue_id': issue, 'baseline': ref}
    try:
        with path.open('x') as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write('\n')
    except FileExistsError:
        require(json.loads(path.read_text()) == payload,
                'original maintenance baseline is already pinned; preserve cumulative issue changes')


def navigate(root, issue, base_ref, role, map_ref, targets, docs, use):
    import team_accounting
    with team_accounting.phase(root, issue, 'orientation', role=role):
        return _navigate(root, issue, base_ref, role, map_ref, targets, docs, use)


def _navigate(root, issue, base_ref, role, map_ref, targets, docs, use, reused_from=None):
    """Print selected references and record how the role will use this dependency slice."""
    load(root, base_ref, 'baseline', issue)
    require(role in ROLES, 'unknown orientation role')
    require(map_ref.startswith(MAP + '#'), 'select a heading in the code map')
    require(len(set(targets)) >= 2 and all('::' in t for t in targets),
            'name an owning symbol/file and at least one distinct caller, consumer or test')
    require(bool(docs), 'name an applicable documentation or instruction contract')
    require(explanation(use), 'explain how these references guide this issue (at least 40 characters)')
    refs = list(dict.fromkeys([map_ref, *targets, *docs]))
    entries = [excerpt(root, r) for r in refs]
    for entry in entries:
        # Bound each display. Large symbols still require a focused Read/rg follow-up.
        lines = entry['text'].splitlines()
        print(f"\n--- {entry['ref']} ({len(lines)} lines; sha256={entry['sha256']}) ---", file=sys.stderr)
        print('\n'.join(lines[:65]), file=sys.stderr)
        if len(lines) > 65:
            print('Excerpt truncated: use a focused Read/rg for the relevant body.', file=sys.stderr)
    payload = envelope('orientation', issue)
    payload.update(baseline=base_ref, role=role, map=map_ref, targets=targets,
                   documents=docs, use=use,
                   references=[{k: e[k] for k in ('ref', 'sha256', 'components')} for e in entries])
    if reused_from is not None:
        payload['reused_from'] = reused_from
    return save(root, payload)


def reuse_navigate(root, issue, original_ref, use, base_ref=None, role=None):
    import team_accounting
    with team_accounting.phase(root, issue, 'orientation'):
        return _reuse_navigate(root, issue, original_ref, use, base_ref, role)


def _reuse_navigate(root, issue, original_ref, use, base_ref=None, role=None):
    """Re-run a prior orientation's map, targets and documents under a fresh use.

    This removes only the retyping of identical arguments. The current excerpt of
    every reference is still printed through `_navigate`, and the caller must write
    a new use explanation; no hash or other value echoed by a stale-orientation
    refusal is accepted. When a changed reference is not one of the original's
    declared targets or documents (the map heading), or a declared reference no
    longer resolves, the slice moved beyond what was read and full navigate is
    required.
    """
    record = load(root, original_ref, 'orientation', issue)
    require(base_ref is None or record.get('baseline') == base_ref,
            'reused orientation belongs to another baseline; run full navigate')
    require(role is None or record.get('role') == role,
            'reused orientation belongs to another role; run full navigate')
    validate_orientation(root, original_ref, issue, record.get('baseline'), record.get('role'), fresh=False)
    require(isinstance(use, str) and use.strip(),
            'navigate --reuse-args requires a freshly written --use explaining the current excerpts')
    words = lambda text: ' '.join(str(text).split()).casefold()
    require(words(use) != words(record['use']),
            '--use repeats the original orientation; write a fresh explanation after reading the current excerpts')
    declared = set(record['targets']) | set(record['documents'])
    outside, missing, echoed = [], [], {original_ref.get('sha256')}
    for entry in record['references']:
        echoed.add(entry['sha256'])
        try:
            current = excerpt(root, entry['ref'])
        except (OSError, ValueError):
            missing.append(entry['ref'])
            continue
        echoed.add(current['sha256'])
        if current['sha256'] != entry['sha256'] and entry['ref'] not in declared:
            outside.append(entry['ref'])
    require(not any(value and value in use for value in echoed),
            '--use cites orientation hashes; hashes echoed by a stale-orientation refusal are not an '
            'acknowledgement, so explain what the current excerpts show')
    require(not outside, 'navigate --reuse-args refused: changed targets lie outside the original orientation\'s '
            f'declared targets and documents: {json.dumps(outside)}; the dependency slice moved beyond what was read, '
            'so run full navigate with explicit --map/--target/--doc')
    require(not missing, f'navigate --reuse-args refused: recorded references no longer resolve: {json.dumps(missing)}; '
            'run full navigate with the current owning references')
    return _navigate(root, issue, record['baseline'], record['role'], record['map'], record['targets'],
                     record['documents'], use, reused_from=original_ref)


def validate_orientation(root, ref, issue, base_ref, role, fresh=True):
    record = load(root, ref, 'orientation', issue)
    require(record.get('baseline') == base_ref and record.get('role') == role,
            f'{role} orientation must belong to this baseline and role')
    require(explanation(record.get('use')), f'{role} orientation lacks a substantive use explanation')
    require(isinstance(record.get('map'), str) and record['map'].startswith(MAP + '#'),
            f'{role} orientation must select a map heading')
    targets, docs = record.get('targets'), record.get('documents')
    require(isinstance(targets, list) and all(isinstance(t, str) and '::' in t for t in targets)
            and len(set(targets)) >= 2, f'{role} orientation needs owner and related code/test targets')
    require(isinstance(docs, list) and docs and all(isinstance(d, str) for d in docs),
            f'{role} orientation lacks its documentation contract')
    entries = record.get('references')
    require(isinstance(entries, list) and all(isinstance(e, dict) for e in entries),
            f'{role} orientation lacks reference hashes')
    require({e.get('ref') for e in entries} == {record['map'], *targets, *docs},
            f'{role} orientation references are incomplete')
    stale = []
    for entry in entries:
        require(isinstance(entry.get('sha256'), str) and len(entry['sha256']) == 64,
                f'{role} orientation has invalid hashes')
        if fresh:
            try:
                current = excerpt(root, entry['ref'])
                if current['sha256'] == entry['sha256']:
                    continue
                before, after = entry.get('components', {}), current.get('components', {})
                components = [key for key in before.keys() | after.keys() if before.get(key) != after.get(key)]
                stale.append({'target': entry['ref'], 'changed': components or ['legacy_hash'],
                              'before': entry['sha256'], 'after': current['sha256']})
            except (OSError, ValueError) as exc:
                stale.append({'target': entry['ref'], 'before': entry['sha256'], 'after': None, 'error': str(exc)})
    require(not stale, f'stale {role} orientation: receipt={ref}; changes={json.dumps(stale)}; '
            f'resume the same {role}, inspect every changed target, navigate again '
            '(`doc_contract.py navigate --issue <id> --reuse-args <receipt> --use <fresh explanation>` reprints the '
            'same map, targets and documents), run the affected independent check and return a fresh footer')
    return record


def framework_supplied(root):
    """Map framework path -> byte states this project's applied upgrades supplied.

    An upgrade changes framework files, which land in every open issue's candidate
    diff and would otherwise force each issue to disposition symbols it never
    touched: one issue measured 18 of 18 targets attributable purely to an upgrade.
    The applied deployment records name each file's before and result digests, so a
    state an upgrade actually produced is provably framework-supplied rather than
    project-authored.

    A locally patched framework file does NOT appear here, because its bytes match
    no recorded upgrade state, so it still requires an explicit judgment.
    """
    supplied = {}
    folder = Path(root) / 'ESX-team-local/deployments'
    if not folder.is_dir():
        return supplied
    for record_path in sorted(folder.glob('*.json')):
        try:
            record = json.loads(record_path.read_text())
        except (ValueError, OSError):
            continue
        if record.get('status') != 'applied':
            continue
        for entry in record.get('files', []):
            if entry.get('ownership') != 'framework' or not entry.get('path'):
                continue
            for key in ('before_sha256', 'result_sha256', 'master_sha256'):
                value = entry.get(key)
                if value:
                    supplied.setdefault(entry['path'], {})[value] = {
                        'deployment_id': record.get('deployment_id'),
                        'record': str(record_path.relative_to(Path(root))),
                        'from_version': record.get('from_version')}
    return supplied


def upgrade_attribution(root, target, base_files, current, supplied=None):
    """Return deployment provenance when a target changed only through an upgrade.

    Both endpoints must be states a recorded upgrade supplied; a project edit on
    either side breaks the chain and the target needs a real judgment.
    """
    supplied = framework_supplied(root) if supplied is None else supplied
    path = target.split('::')[0]
    states = supplied.get(path)
    if not states:
        return None
    before = (base_files.get(path) or {}).get('sha256')
    after = (current.get(path) or {}).get('sha256')
    if not before or not after or before == after:
        return None
    if before not in states or after not in states:
        return None
    return dict(states[after], path=path, before_sha256=before, after_sha256=after)


def judged_elsewhere(root, issue):
    """Map target -> {state: provenance} already judged under another issue's accepted closeout.

    A pinned baseline means an issue left open while the tree moved inherits every
    other issue's changes into its own candidate diff: one issue here needed 85
    judgments, the large majority another issue's work that had already been
    dispositioned and accepted. Re-judging those adds no integrity and misattributes
    them.

    The proof is exact rather than by baseline ancestry: a sealed disposition records
    its target's own byte state in `judgment_inputs.target.sha256`, so a target whose
    CURRENT state equals a state already judged and accepted elsewhere has genuinely
    been reviewed. A target that changed since that seal has a different state and
    still requires a judgment.
    """
    judged = {}
    history = Path(root) / f'{STATE}/loop_history.jsonl'
    if not history.is_file():
        return judged
    for line in history.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get('id') == issue or row.get('outcome') != 'completed':
            continue
        ref = (row.get('maintenance') or {}).get('documentation')
        if not ref:
            continue
        try:
            report = load(root, ref, 'documentation', row['id'])
        except (ValueError, OSError, KeyError, TypeError):
            continue
        if 'references' not in report:
            continue
        for row_d in report.get('dispositions', []):
            state = ((row_d.get('judgment_inputs') or {}).get('target') or {}).get('sha256')
            if state and row_d.get('action') in ('updated', 'reviewed_unchanged', 'removed'):
                judged.setdefault(row_d['target'], {})[state] = {
                    'issue': row['id'], 'report': ref, 'action': row_d['action'],
                    'target_sha256': state}
    return judged


def carried_attribution(root, target, current, judged=None, issue=None):
    """Return provenance when this exact target state was judged under another issue."""
    judged = judged_elsewhere(root, issue) if judged is None else judged
    states = judged.get(target)
    if not states:
        return None
    inputs = unit_inputs(current, target)
    state = (inputs or {}).get('sha256')
    if not state or state not in states:
        return None
    return states[state]


def prefill(root, row, base_files, current, supplied=None, issue=None):
    """Blank a disposition for judgment, or attribute it to a recorded upgrade."""
    provenance = upgrade_attribution(root, row['target'], base_files, current, supplied)
    if provenance is None:
        carried = carried_attribution(root, row['target'], current, None, issue)
        if carried is not None:
            return {**row, 'action': 'carried_forward', 'reason': (
                'This exact byte state of this target was already judged and accepted under issue '
                + str(carried['issue']) + ', which dispositioned it as ' + carried['action'] + '. Re-judging it '
                'here would restate another issue work rather than add review, so its provenance is cited '
                'instead.'), 'references': [], 'carried': carried}
        return {**row, 'action': '', 'reason': '', 'references': []}
    return {**row, 'action': 'upgrade_supplied', 'reason': (
        'Framework file supplied by a recorded ESX upgrade, not authored by this issue. Both the baseline and '
        'current bytes are states deployment ' + str(provenance['deployment_id']) + ' recorded, so this target '
        'carries no project judgment: its documentation is the upgrade\'s own. See ' + provenance['record'] + '.'),
        'references': [], 'deployment': provenance}


def draft(root, issue, base_ref, previous_ref=None):
    """Build complete coverage, optionally retaining measured unchanged judgments.

    Explicit dependency references permit selective reuse. Judgments with no
    declared dependency slice conservatively depend on the whole inventory.
    Every changed or unmeasured judgment remains blank for human review.
    """
    base = load(root, base_ref, 'baseline', issue)
    current = snapshot(root)
    payload = envelope('documentation', issue)
    payload.update(baseline=base_ref, candidate=digest(current),
                   changes=changes(base['files'], current),
                   dispositions=[prefill(root, r, base['files'], current, issue=issue)
                                 for r in changes(base['files'], current)],
                   map_delta={'status': '', 'reason': '', 'references': []})
    if previous_ref:
        previous = load(root, previous_ref, 'documentation', issue)
        require(previous.get('baseline') == base_ref, 'prior documentation report uses a different baseline')
        require('references' in previous, 'reuse requires a sealed documentation report')
        prior_rows = {r['target']: r for r in previous.get('dispositions', [])}
        for index, row in enumerate(payload['dispositions']):
            prior = prior_rows.get(row['target'])
            if prior and prior.get('change') == row['change'] and prior.get('judgment_inputs'):
                try:
                    valid = prior['judgment_inputs'] == judgment_inputs(root, prior, current)
                except (ValueError, OSError, KeyError):
                    valid = False
                if valid:
                    payload['dispositions'][index] = copy.deepcopy(prior)
                    payload['dispositions'][index]['reused_from'] = previous_ref
        delta = previous.get('map_delta', {})
        # Map judgments discuss routes across the entire inventory. Their reuse
        # requires the same inventory, retaining coverage of new dependencies.
        if previous.get('candidate') == payload['candidate'] and delta:
            payload['map_delta'] = copy.deepcopy(delta)
        payload['previous_report'] = previous_ref
    return payload


def unit_inputs(current, target):
    """Include enclosing definitions that supply closures or class-level values."""
    path, _, symbol = target.partition('::')
    units = current.get(path, {}).get('units', {})
    unit = units.get(symbol)
    if unit is None:
        return None
    result = {k: unit.get(k) for k in ('sha256', 'context', 'docs')}
    parents = ['.'.join(symbol.split('.')[:n]) for n in range(1, len(symbol.split('.')))]
    result['parents'] = {name: units[name]['sha256'] for name in parents if name in units}
    return result


def judgment_inputs(root, row, current):
    """Measure a target's context, explicit dependencies and cited explanations."""
    target = unit_inputs(current, row['target'])
    dependencies = row.get('dependencies', [])
    require(isinstance(dependencies, list) and all(isinstance(d, str) for d in dependencies),
            f"{row['target']}: dependencies must be a list of references")
    refs = sorted(set(row.get('references', []) + dependencies))
    hashes = [{k: entry[k] for k in ('ref', 'sha256', 'components')} for entry in (excerpt(root, r) for r in refs)]
    return {'target': target, 'references': hashes,
            'dependency_contexts': {ref: unit_inputs(current, ref) for ref in dependencies if '::' in ref},
            'dependency_inventory': None if dependencies else digest(current)}


def docs_measure(files, ref):
    """Compare source prose separately from executable text for an 'updated' claim."""
    path, _, symbol = ref.partition('::')
    path, sep, anchor = path.partition('#')
    file = files.get(path, {})
    if sep:
        value = file.get('sections', {}).get(anchor)
        return value, value is not None
    unit = file.get('units', {}).get(symbol or '<module>', {})
    return unit.get('docs'), unit.get('has_docs', False)


def validate_report(root, report, issue, base_ref, current=None):
    base = load(root, base_ref, 'baseline', issue)
    require(report.get('version') == 1 and report.get('kind') == 'documentation' and report.get('issue_id') == issue
            and report.get('baseline') == base_ref, 'documentation report identity/baseline mismatch')
    current = snapshot(root) if current is None else current
    require(report.get('candidate') == digest(current), 'documentation report is stale; regenerate the change inventory')
    expected = changes(base['files'], current)
    require(report.get('changes') == expected, 'documentation change inventory omits or misstates affected targets')
    rows = report.get('dispositions')
    require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), 'documentation dispositions are required')
    require(len(rows) == len(expected) and {r.get('target') for r in rows} == {r['target'] for r in expected},
            'documentation dispositions must cover every affected function/module exactly once')
    expected_by_target = {r['target']: r['change'] for r in expected}
    refs = set()
    for row in rows:
        target = row['target']
        require(row.get('change') == expected_by_target[target], f'{target}: incorrect change kind')
        action = row.get('action')
        require(action in ('updated', 'reviewed_unchanged', 'removed', 'upgrade_supplied', 'carried_forward'),
                f'{target}: missing documentation action')
        require(action != 'removed' or row['change'] == 'removed', f'{target}: only a removed target can use removed')
        require(explanation(row.get('reason')), f'{target}: explain the resulting contract or why its descriptions remain accurate')
        if action == 'carried_forward':
            # Re-derived, never trusted from the report: the whole force of this
            # action is that some OTHER accepted closeout already judged this exact
            # state, and a report cannot be allowed to assert that about itself.
            proven = carried_attribution(root, target, current, None, issue)
            require(proven is not None,
                    f'{target}: carried_forward requires this exact target state to have been judged under '
                    'another issue accepted closeout; a state judged nowhere needs a real judgment')
            require(row.get('carried') == proven, f'{target}: carried provenance differs from the sealed record')
            continue
        if action == 'upgrade_supplied':
            # Attribution must be re-derived, never accepted from the report: a
            # claimed upgrade origin is exactly what a project edit could forge.
            proven = upgrade_attribution(root, target, base['files'], current)
            require(proven is not None,
                    f'{target}: upgrade_supplied requires both byte states to come from a recorded applied '
                    'upgrade; a locally edited framework file needs a real judgment')
            require(row.get('deployment') == proven, f'{target}: upgrade provenance differs from the deployment record')
            # Deliberately not added to `refs`: deployment records live under the
            # ignored ESX-team-local/ tree, so sealing a reference to one would
            # break in a fresh clone. Provenance is re-derived here instead, and
            # absent records fail validation loudly rather than passing silently.
            continue
        links = row.get('references')
        require(isinstance(links, list) and links and all(isinstance(r, str) for r in links), f'{target}: documentation references are required')
        for link in links:
            excerpt(root, link)
            require(docs_measure(current, link)[1], f'{target}: {link} contains no inventoried documentation')
        if action == 'updated':
            require(any(docs_measure(base['files'], r)[0] != docs_measure(current, r)[0] for r in links),
                    f'{target}: updated requires a measured documentation edit; executable edits alone do not qualify')
        refs.update(links)
        measured = judgment_inputs(root, row, current)
        if 'judgment_inputs' in row:
            require(row['judgment_inputs'] == measured, f'{target}: documentation judgment inputs changed')
        if row.get('reused_from'):
            previous = load(root, row['reused_from'], 'documentation', issue)
            require(previous.get('baseline') == base_ref and 'references' in previous,
                    f'{target}: invalid documentation reuse source')
            found = [r for r in previous.get('dispositions', []) if r.get('target') == target]
            require(len(found) == 1 and found[0].get('judgment_inputs') == measured,
                    f'{target}: reused judgment has changed target, dependencies or references')
            require(all(row.get(k) == found[0].get(k) for k in
                        ('action', 'change', 'reason', 'references', 'dependencies')),
                    f'{target}: reused judgment text differs from its sealed source')
    delta = report.get('map_delta')
    require(isinstance(delta, dict) and delta.get('status') in ('updated', 'MAP-OK'), 'map_delta needs updated or MAP-OK status')
    require(explanation(delta.get('reason')), 'map_delta requires a concrete explanation of the affected route/contracts')
    mapped = delta.get('references')
    require(isinstance(mapped, list) and mapped and all(isinstance(r, str) and r.startswith(MAP + '#') for r in mapped),
            'map_delta must reference the relevant map headings')
    changed = base['files'].get(MAP, {}).get('sha256') != current.get(MAP, {}).get('sha256')
    require((delta['status'] == 'updated') == changed, 'map_delta status disagrees with measured map changes')
    refs.update(mapped)
    hashes = [{k: e[k] for k in ('ref', 'sha256', 'components')} for e in (excerpt(root, r) for r in sorted(refs))]
    if 'references' in report:
        require(report['references'] == hashes, 'documentation reference hashes are stale or incomplete')
    return hashes


def seal(root, report):
    """Validate a human-authored disposition plan and seal exactly the current candidate."""
    require(isinstance(report, dict), 'documentation plan must be an object')
    current = snapshot(root)
    report['references'] = validate_report(root, report, report.get('issue_id'), report.get('baseline'), current)
    for row in report['dispositions']:
        row['judgment_inputs'] = judgment_inputs(root, row, current)
    return save(root, report)


def check_start(root, start):
    """Check the recorded initial orientation; it remains historical during corrections."""
    errors = []
    try:
        state = start.get('maintenance')
        require(isinstance(state, dict), 'issue-start.maintenance is required before implementation')
        load(root, state.get('baseline'), 'baseline', start.get('id'))
        original = original_baseline(root, start.get('id'))
        require(not original or state.get('baseline') == original,
                'issue-start must preserve the original maintenance baseline across iterations')
        validate_orientation(root, state.get('orientation'), start.get('id'), state['baseline'], 'arch', fresh=False)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    return errors


def historical_completion(entry, record, base, base_ref):
    """Recognize an explicitly retained completion predating commit-based recovery.

    This preserves the original hook evidence. It supplies no navigation or final
    documentation approval; current reviewers must establish those independently.
    """
    history = entry.get('maintenance_history')
    if history is None:
        return False
    recovery = base.get('recovery') or {}
    require(recovery.get('git_base') and explanation(recovery.get('reason')),
            'historical completion requires explicit commit-based baseline recovery')
    require(isinstance(history, dict) and history.get('status') == 'predates_recovery'
            and history.get('baseline') == base_ref and explanation(history.get('reason')),
            'invalid maintenance_history disposition')
    timestamp = record.get('ts')
    require(isinstance(timestamp, str), 'historical completion needs the captured hook timestamp')
    captured = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    recovered = dt.datetime.fromisoformat(base['created_at'])
    require(captured.tzinfo and recovered.tzinfo and captured + dt.timedelta(seconds=1) <= recovered,
            'completion does not predate recovered baseline')
    return True


def check_done(root, start, done, records, candidate_signature):
    """Gate completion for every workflow, including records without a workflow field.

    Earlier role completions retain historical navigation. Current Arch and final
    approving reviewers need fresh references; every supplied completion needs
    its own role-bound orientation in the captured hook footer. Report approval
    is independently captured by each reviewer whose candidate is current.
    """
    if done.get('outcome') != 'completed':
        if not (start or {}).get('maintenance'):
            return []
        errors = check_start(root, start)
        if done.get('maintenance') and done['maintenance'].get('baseline') != start['maintenance'].get('baseline'):
            errors.append('partial completion must preserve the original maintenance baseline')
        return errors
    errors = check_start(root, start or {})
    try:
        state = done.get('maintenance')
        initial = (start or {}).get('maintenance') or {}
        require(isinstance(state, dict), 'issue-done.maintenance is required for completion')
        base_ref = initial.get('baseline')
        require(state.get('baseline') == base_ref, 'completion must preserve the original maintenance baseline')
        base = load(root, base_ref, 'baseline', done.get('id'))
        validate_orientation(root, state.get('orientation'), done.get('id'), base_ref, 'arch')
        report_ref = state.get('documentation')
        report = load(root, report_ref, 'documentation', done.get('id'))
        require('references' in report, 'documentation report must be sealed')
        validate_report(root, report, done.get('id'), base_ref)
        require(done.get('map_delta') == report['map_delta'], 'issue-done.map_delta must equal the sealed report disposition')
        from audit import audit_code_map, audit_instructions
        findings = audit_code_map(Path(root))['findings']
        findings += audit_instructions(Path(root), [MAP])['findings']
        require(not findings, f'code map audit has unresolved findings: {findings[:3]}')
        subs = done.get('subagents') or {}
        require(isinstance(subs, dict), 'subagents must be an object')
        receipt_owners = {}
        confirmed_reviewers = set()
        for role, entries in subs.items():
            require(isinstance(entries, list), f'{role}: expected completion list')
            for entry in entries:
                require(isinstance(entry, dict), f'{role}: invalid completion')
                if entry.get('waived'):
                    continue
                found = [r for r in records if r.get('agent_id') == entry.get('dispatch_id')
                         and r.get('event_id') == entry.get('dispatch_event_id')]
                require(len(found) == 1, f'{role}: documentation evidence needs one exact hook completion')
                raw_footer = found[0].get('footer')
                footer = raw_footer if isinstance(raw_footer, dict) else {}
                if found[0].get('status', 'completed') != 'completed':
                    from workflow_policy import resolved_dispatch
                    require(resolved_dispatch(found[0], records, done),
                            f'{role}: incomplete dispatch needs a completed continuation or explicit replacement')
                    # A failed turn may have produced no footer. Its actual
                    # status remains in history; the completed continuation or
                    # replacement supplies current navigation and approval.
                    if footer.get('orientation'):
                        validate_orientation(root, footer['orientation'], done['id'], base_ref, role, fresh=False)
                    continue
                require(isinstance(raw_footer, dict), f'{role}: completed dispatch needs a structured footer')
                if historical_completion(entry, found[0], base, base_ref):
                    continue
                from workflow_policy import current_review
                final_review = current_review(found[0], records, done, candidate_signature)
                validate_orientation(root, footer.get('orientation'), done['id'], base_ref, role, fresh=final_review)
                receipt_id = footer['orientation']['sha256']
                owner = receipt_owners.setdefault(receipt_id, entry.get('dispatch_id'))
                require(owner == entry.get('dispatch_id'), 'distinct agents must record their own navigation')
                if 'orientation' in entry:
                    require(entry['orientation'] == footer.get('orientation'), f'{role}: pasted orientation differs from hook')
                if final_review and footer.get('verdict') in ('APPROVE', 'APPROVE_WITH_FIXES'):
                    review = footer.get('documentation_review')
                    require(isinstance(review, dict), 'Richard must include a documentation_review object in the footer')
                    require(review.get('report') == report_ref,
                            'documentation_review.report must be the exact sealed report reference, not a copy or a different report')
                    require(review.get('status') == 'confirmed',
                            f"documentation_review.status must be the literal string 'confirmed' "
                            f"(describes the reviewer's own act of confirming the report, not the report's own "
                            f"'sealed' state); got {review.get('status')!r}")
                    require(explanation(review.get('notes')), 'documentation_review.notes must be a substantive explanation (40+ characters) of what was confirmed, not a placeholder')
                    if 'documentation_review' in entry:
                        require(entry['documentation_review'] == review, 'pasted documentation review differs from hook')
                    confirmed_reviewers.add(entry.get('dispatch_id'))
        workflow = done.get('workflow') or {}
        require(isinstance(workflow, dict), 'workflow must be an object')
        minimum = workflow.get('minimum_reviewers', 0)
        require(type(minimum) is int and 0 <= minimum <= 2, 'invalid minimum reviewers')
        require(len(confirmed_reviewers) >= minimum,
                'final documentation approval requires the workflow minimum of current reviewers; historical completions cannot supply it')
    except (ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
        errors.append(str(exc))
    return errors


def parse_ref(value):
    """Accept the JSON reference printed by an evidence-producing command, inline or
    as the path of a file holding it (relative paths resolve from the current directory)."""
    text = value.strip()
    if not text.startswith('{'):
        path = Path(text)
        if not path.is_file():
            raise argparse.ArgumentTypeError('expected an inline {"path","sha256"} JSON reference '
                                             'or the path of a file containing one: ' + text)
        text = path.read_text()
    try:
        ref = json.loads(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('reference is not valid JSON: ' + str(exc)) from exc
    if not (isinstance(ref, dict) and isinstance(ref.get('path'), str) and isinstance(ref.get('sha256'), str)):
        raise argparse.ArgumentTypeError('reference must be a JSON object with "path" and "sha256"')
    return ref


def parse_receipt(value):
    """Accept a JSON orientation reference or its bare content digest."""
    text = value.strip()
    if len(text) == 64 and all(c in '0123456789abcdef' for c in text):
        return {'path': f'{STORE}/{text}.json', 'sha256': text}
    return parse_ref(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('baseline', help='save the working source before issue edits')
    capture.add_argument('--issue', required=True)
    capture.add_argument('--git-base', help='recover from a known commit; review every intervening change')
    capture.add_argument('--reason')
    nav = sub.add_parser('navigate', help='display a bounded dependency slice and save role evidence')
    nav.add_argument('--issue', required=True)
    nav.add_argument('--baseline', type=parse_ref, help='required unless --reuse-args; must match when both are given')
    nav.add_argument('--role', choices=ROLES, help='required unless --reuse-args; must match when both are given')
    nav.add_argument('--map')
    nav.add_argument('--target', action='append', help='path::qualified.symbol or path::<module>')
    nav.add_argument('--doc', action='append', help='path#heading or path::symbol')
    nav.add_argument('--reuse-args', type=parse_receipt, metavar='ORIENTATION_REF',
                     help='reload map, targets and documents from a prior orientation receipt; requires a fresh --use')
    nav.add_argument('--use', required=True)
    reuse = sub.add_parser('check-orientation', help='check whether saved navigation can be reused')
    reuse.add_argument('--issue', required=True)
    reuse.add_argument('--baseline', type=parse_ref, required=True)
    reuse.add_argument('--role', choices=ROLES, required=True)
    reuse.add_argument('--receipt', type=parse_ref, required=True)
    plan = sub.add_parser('draft', help='generate a current change inventory with blank dispositions')
    plan.add_argument('--issue', required=True)
    plan.add_argument('--baseline', type=parse_ref, required=True)
    plan.add_argument('--previous', type=parse_ref, help='reuse unchanged judgments from a sealed report')
    for name in ('seal', 'check'):
        command = sub.add_parser(name, help='validate a filled documentation plan' if name == 'check' else 'validate and store a filled plan')
        command.add_argument('plan', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'baseline':
            result = baseline(args.root, args.issue, args.git_base, args.reason)
        elif args.command == 'navigate' and args.reuse_args is not None:
            if args.map or args.target or args.doc:
                parser.error('--reuse-args reloads --map/--target/--doc; omit them or run full navigate')
            result = reuse_navigate(args.root, args.issue, args.reuse_args, args.use, args.baseline, args.role)
        elif args.command == 'navigate':
            missing = [flag for flag, value in (('--baseline', args.baseline), ('--role', args.role), ('--map', args.map),
                       ('--target', args.target), ('--doc', args.doc)) if value is None]
            if missing:
                parser.error('the following arguments are required: ' + ', '.join(missing))
            result = navigate(args.root, args.issue, args.baseline, args.role, args.map, args.target, args.doc, args.use)
        elif args.command == 'draft':
            result = draft(args.root, args.issue, args.baseline, args.previous)
        elif args.command == 'check-orientation':
            validate_orientation(args.root, args.receipt, args.issue, args.baseline, args.role)
            result = {'valid': True, 'evidence': 'reused', 'orientation': args.receipt}
        else:
            report = json.loads(args.plan.read_text())
            require(isinstance(report, dict), 'documentation plan must be an object')
            result = seal(args.root, report) if args.command == 'seal' else {
                'valid': True, 'references': validate_report(args.root, report, report.get('issue_id'), report.get('baseline'))}
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
        parser.exit(1, f'documentation contract: {exc}\n')


if __name__ == '__main__':
    main()
