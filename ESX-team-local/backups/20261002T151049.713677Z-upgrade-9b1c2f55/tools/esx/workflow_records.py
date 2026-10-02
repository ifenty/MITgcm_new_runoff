#!/usr/bin/env python3
"""Assemble exact agent evidence and compact issue handoffs without editing live state.

The closeout command prints an unfinished draft. Arch supplies technical judgments
and the normal loop gate validates the completed record. Referenced milestones and
diagnosis evidence use content hashes, so unrelated appended records remain usable.
"""
import argparse
from copy import deepcopy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import os
import tempfile
from workflow_handoff import input_file

ROLES = ('bob', 'richard', 'scout', 'prober', 'bisector', 'auditor')
from project import STATE
PROTECTED = {'issue-start.json', 'loop_history.jsonl', 'dispatch_log.jsonl',
             'workflow_events.jsonl', 'baseline-locks.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_file(root, name):
    """Resolve a repository-relative file while excluding traversal and symlinks."""
    require(isinstance(name, str) and bool(name.strip()), 'a relative path is required')
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts,
            'path must remain relative to the project root')
    require(not set(path.parts) & {'.git', '.claude-worktrees'}, 'protected path')
    root = Path(root).resolve()
    current = root
    for part in path.parts:
        current = current / part
        require(not current.is_symlink(), f'symlink paths are unsupported: {name}')
    require(current != root, 'a file path is required')
    return current


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    """Fail visibly on a truncated or malformed evidence log."""
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f'{path}:{number}: malformed JSON evidence') from exc
        require(isinstance(row, dict), f'{path}:{number}: evidence must be an object')
        rows.append(row)
    return rows


def timestamp(value):
    require(isinstance(value, str), 'a UTC-aware timestamp is required')
    try:
        result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'invalid timestamp: {value}') from exc
    require(result.tzinfo is not None, 'timestamps must include their timezone')
    return result


def import_completion(start, records, selection, historical=False):
    """Copy one uniquely identified hook footer; never infer an agent's actions.

Historical entries may predate this iteration, but must still identify the same
issue and their own correction round. New selections must follow its start time.
"""
    require(isinstance(selection, dict), 'completion selection must be an object')
    role = selection.get('agent')
    require(role in ROLES, 'completion selection needs a known agent role')
    agent, event = selection.get('dispatch_id'), selection.get('dispatch_event_id')
    require(isinstance(agent, str) and agent and isinstance(event, str) and event,
            'completion selection needs exact dispatch_id and dispatch_event_id')
    matches = [r for r in records if r.get('event_id') == event]
    require(len(matches) == 1, f'{event}: missing or ambiguous completion event')
    record = matches[0]
    require(record.get('agent_id') == agent and record.get('agent_type') == role,
            f'{event}: completion agent identity/role mismatch')
    if record.get('status', 'completed') != 'completed':
        require(record.get('status') in ('incomplete', 'failed', 'running'),
                f'{event}: runtime completion is incomplete or failed')
        round_number = selection.get('correction_round')
        require(type(round_number) is int and round_number >= 0
                and type(record.get('correction_round')) is int
                and record['correction_round'] == round_number,
                f'{event}: failed-turn correction round mismatch or absent')
        require(record.get('issue_id') == start.get('id'),
                f'{event}: failed-turn issue identity mismatch')
        if not historical:
            require(timestamp(record.get('ts')) >= timestamp(start.get('timestamp')),
                    f'{event}: attempt predates this iteration; retain it through --prior (prepare-done '
                    f'uses the accepted prior closeout in {STATE}/closed/ automatically) or select it with '
                    f'"selection_scope": "history"')
        footer = record.get('footer')
        if isinstance(footer, dict):
            require(footer.get('issue_id', start['id']) == start['id'],
                    f'{event}: failed-turn footer issue identity mismatch')
        # An interrupted process can leave a plausible-looking approval footer.
        # Preserve its measured failure and identity; full output remains in the
        # exact hook event. A later completion supplies the role's final evidence.
        return {'agent': role, 'issue_id': start['id'], 'correction_round': round_number,
                'dispatch_id': agent, 'dispatch_event_id': event, 'status': record['status'],
                'attempt': {key: deepcopy(record[key]) for key in
                    ('ts', 'started_at', 'finished_at', 'elapsed_seconds', 'duration_seconds', 'returncode', 'error')
                    if key in record}}
    footer = record.get('footer')
    require(isinstance(footer, dict) and footer, f'{event}: missing structured footer')
    require((footer.get('agent') or footer.get('agent_name')) == role,
            f'{event}: footer role mismatch')
    require(footer.get('issue_id') == start.get('id'), f'{event}: footer issue mismatch')
    round_number = selection.get('correction_round')
    require(type(round_number) is int and round_number >= 0,
            f'{event}: selection needs its nonnegative correction_round')
    require(type(footer.get('correction_round')) is int
            and footer['correction_round'] == round_number,
            f'{event}: footer correction round mismatch or absent')
    if not historical:
        require(footer.get('iteration_timestamp') == start.get('timestamp'),
                f'{event}: completion belongs to another iteration')
        require(timestamp(record.get('ts')) >= timestamp(start.get('timestamp')),
                f'{event}: completion predates this iteration; retain it through --prior')
    result = deepcopy(footer)
    for field, value in (('dispatch_id', agent), ('dispatch_event_id', event)):
        require(field not in result or result[field] == value,
                f'{event}: footer contains conflicting {field}')
        result[field] = value
    # The captured structured result is itself a substantive report source.
    # Preserve a supplied digest verbatim; an absent one gets exact serialization.
    if 'report_digest' not in result:
        result['report_digest'] = json.dumps(footer, sort_keys=True, ensure_ascii=False)
    return result


def prepare_done(start, records, selections, prior=None):
    """Return a draft with verbatim footers and explicitly pending human judgments.

The optional prior record carries earlier completions and continuity across
iterations. It supplies no fresh outcome, approval, verification, or delivery claim.
"""
    require(isinstance(start, dict) and start.get('id') and start.get('title'),
            'start needs an issue id and title')
    timestamp(start.get('timestamp'))
    require(isinstance(selections, list), 'selections must be a JSON array')
    draft = {key: deepcopy(start[key]) for key in
             ('state_version', 'id', 'title', 'iteration', 'workflow', 'agent_continuity', 'maintenance', 'diagnosis_checkpoint') if key in start}
    draft.update(outcome=None, summary='', tests_status=None,
                 open_issues_md_updated=None, remaining_open_count=None,
                 timestamp=start['timestamp'], start_timestamp=start['timestamp'], subagents={}, scope_decisions=[],
                 # These four default to schema-valid, ready-to-use values (not
                 # null/absent) so a draft with genuinely nothing to report on
                 # them already passes check_done()/check_milestone() without
                 # reverse-engineering their exact required shape one
                 # ValueError at a time. Callers with a real decision for any
                 # of these still overwrite the default.
                 milestone={'logged': False, 'reason': 'No milestone applicable this iteration.'}, lessons=[],
                 rules_updated=[], rules_updated_na='No rule changes needed this iteration.',
                 git={'committed': False, 'reason': 'Not committed; pending explicit owner authorization.'},
                 communication={'status': 'pending', 'detail': 'Arch must record the authorized communication disposition.'},
                 next_step='', verification={'status': 'pending',
                    'final_owner': (start.get('workflow') or {}).get('final_verify_owner')})
    pending = ['outcome, summary, tests_status and issue disposition',
               'scope decisions and remaining blockers',
               'milestone, lesson and rule decisions (defaulted to none; override if there is a real one)',
               'git and communication disposition (defaulted to not-committed/pending; override if there is a real disposition)',
               'verification and documentation evidence']
    selected = []
    if prior is not None:
        require(isinstance(prior, dict) and prior.get('id') == start['id'],
                'prior closeout belongs to another issue')
        require((prior.get('maintenance') or {}).get('baseline') ==
                (start.get('maintenance') or {}).get('baseline'),
                'prior closeout uses a different issue baseline')
        subs = prior.get('subagents') or {}
        require(isinstance(subs, dict), 'prior subagents must be an object')
        for role, entries in subs.items():
            require(role in ROLES and isinstance(entries, list), 'invalid prior role records')
            for entry in entries:
                require(isinstance(entry, dict) and not entry.get('waived'),
                        'prior completions must contain captured evidence')
                selection = {**entry, 'agent': role}
                if 'correction_round' not in selection:
                    captured = [r for r in records if r.get('event_id') == entry.get('dispatch_event_id')]
                    require(len(captured) == 1, 'prior completion event is missing or ambiguous')
                    footer = captured[0].get('footer') or {}
                    selection['correction_round'] = captured[0].get('correction_round', footer.get('correction_round'))
                imported = import_completion(start, records, selection, True)
                # Compare every field preserved from the hook. Additional Arch
                # dispositions are retained without replacing captured evidence.
                for key, value in imported.items():
                    if key == 'report_digest' and key not in next(
                            r['footer'] for r in records if r.get('event_id') == imported['dispatch_event_id']):
                        continue
                    require(key not in entry or entry[key] == value,
                            f'prior completion disagrees with captured {key}')
                selected.append(imported if imported.get('status') in ('incomplete', 'failed', 'running')
                                else {**imported, **deepcopy(entry)})
        for key in ('scope_decisions', 'review_supersessions', 'deliverables'):
            if key in prior:
                draft[key] = deepcopy(prior[key])
    retained = {entry['dispatch_event_id'] for entry in selected}
    # A pre-iteration event already retained from the prior closeout needs no
    # second, current-iteration import; the prior carries its exact record.
    selected += [import_completion(start, records, selection, selection.get('selection_scope') == 'history')
                 for selection in selections
                 if not (prior is not None and isinstance(selection, dict)
                         and selection.get('dispatch_event_id') in retained)]
    by_event = {}
    for entry in selected:
        event = entry['dispatch_event_id']
        if event in by_event:
            require(entry == by_event[event], f'{event}: conflicting duplicate completion')
            continue
        by_event[event] = entry
        role = entry.get('agent') or entry['agent_name']
        draft['subagents'].setdefault(role, []).append(entry)
        if entry.get('status') in ('incomplete', 'failed', 'running'):
            if entry['status'] == 'running':
                pending.append(f'{event}: running attempt awaits a terminal record')
            continue
        missing = []
        for field in ('orientation',):
            if not entry.get(field):
                missing.append(field)
        if role == 'richard' and not entry.get('independent_check'):
            missing.append('independent_check')
        if missing:
            pending.append(f'{event}: ' + ', '.join(missing))
    skeleton = replacement_skeleton(start, records, draft)
    if skeleton:
        continuity = draft.setdefault('agent_continuity', {})
        existing = continuity.setdefault('replacements', [])
        known = {(r.get('role'), r.get('old_id')) for r in existing if isinstance(r, dict)}
        for entry in skeleton:
            if (entry['role'], entry['old_id']) in known:
                continue
            existing.append(entry)
            pending.append(f"agent_continuity.replacements: {entry['role']} {entry['old_id']} -> "
                           f"{entry['new_id'] or '(choose new_id)'} needs reason and evidence_refs "
                           f"(or select a later completed continuation of the same agent instead)")
    draft['preparation'] = {'status': 'draft', 'start_timestamp': start['timestamp'],
                            'imported_event_ids': list(by_event), 'pending': pending}
    return draft


def replacement_skeleton(start, records, draft):
    """Draft one replacement disposition per unresolved failed identity.

The dispatch log supplies role, old_id and, when exactly one later completed
identity of the same role exists in this iteration, new_id. Judgment fields
(reason, evidence_refs) stay empty, so resolved_dispatch still refuses the draft
until the closer supplies them. Nothing here resolves a turn by itself.
"""
    import workflow_policy
    issue, iteration = start.get('id'), start.get('timestamp')
    referenced = {e.get('dispatch_event_id'): role for role, entries in (draft.get('subagents') or {}).items()
                  for e in entries if isinstance(e, dict)}
    candidates = [r for r in records if (r.get('issue_id') or (r.get('footer') or {}).get('issue_id')) == issue]
    skeleton, seen = [], set()
    for position, event in enumerate(candidates):
        role, old = event.get('agent_type'), event.get('agent_id')
        if event.get('status') not in ('failed', 'incomplete') or role not in ROLES or (role, old) in seen:
            continue
        if role == 'richard':
            # Reviews are judged by each reviewer's latest turn for the issue.
            if any(r.get('agent_type') == role and r.get('agent_id') == old for r in candidates[position + 1:]):
                continue
        elif event.get('event_id') not in referenced:
            continue  # Only closeout-referenced implementation turns are validated.
        if workflow_policy.resolved_dispatch(event, records, draft):
            continue
        later = [r for r in candidates[position + 1:] if r.get('agent_type') == role
                 and workflow_policy.completed(r) and r.get('agent_id') != old
                 and workflow_policy.identity(r, 'iteration_timestamp') == iteration]
        chosen = {r.get('agent_id') for r in later if r.get('event_id') in referenced} or {r.get('agent_id') for r in later}
        # A same-agent continuation resolves the turn without a replacement.
        if any(r.get('agent_type') == role and r.get('agent_id') == old and workflow_policy.completed(r)
               and workflow_policy.identity(r, 'iteration_timestamp') == iteration for r in candidates[position + 1:]):
            continue
        seen.add((role, old))
        skeleton.append({'role': role, 'old_id': old, 'new_id': chosen.pop() if len(chosen) == 1 else None,
                         'failed_event_id': event.get('event_id'), 'reason': '', 'evidence_refs': []})
    return skeleton


def locate_prior(root, start):
    """Return the latest accepted earlier closeout of this issue from loop_state/closed/.

Only closeouts recorded in loop_history (accepted), sharing the issue baseline
and belonging to an earlier iteration qualify. None when there is none.
"""
    root = Path(root).resolve()
    directory = root / STATE / 'closed'
    if not directory.is_dir():
        return None
    accepted = {(row.get('id'), row.get('timestamp'))
                for row in read_jsonl(local_file(root, f'{STATE}/loop_history.jsonl'))}
    baseline = (start.get('maintenance') or {}).get('baseline')
    found = []
    for path in sorted(directory.glob('issue-done-*.json')):
        try:
            record = read_json(local_file(root, str(path.relative_to(root))))
        except (ValueError, OSError):
            continue
        if (isinstance(record, dict) and record.get('id') == start.get('id')
                and record.get('timestamp') != start.get('timestamp')
                and (record.get('id'), record.get('timestamp')) in accepted
                and (record.get('maintenance') or {}).get('baseline') == baseline):
            found.append((str(record.get('timestamp')), path))
    return max(found)[1] if found else None


def continuation_packet(start, histories, dispatches):
    """Expose current assignments and unresolved findings with exact older references.

All findings in the latest completion per agent are kept. Full report bodies stay
in the dispatch log, which the packet identifies by immutable completion IDs.
"""
    relevant = [row for row in histories if row.get('id') == start.get('id')]
    last = relevant[-1] if relevant else {}
    latest = {}
    for record in dispatches:
        footer = record.get('footer') or {}
        if (record.get('issue_id') or footer.get('issue_id')) == start.get('id'):
            latest[(record.get('agent_type'), record.get('agent_id'))] = record
    rounds = {}
    for (role, _), record in latest.items():
        number = record.get('correction_round', (record.get('footer') or {}).get('correction_round'))
        if type(number) is int:
            rounds[role] = max(rounds.get(role, 0), number)
    reports, historical = [], []
    for (role, agent_id), record in latest.items():
        footer = record.get('footer') or {}
        number = record.get('correction_round', footer.get('correction_round'))
        if type(number) is int and number < rounds.get(role, number):
            historical.append({'agent': role, 'dispatch_id': agent_id,
                               'dispatch_event_id': record.get('event_id'),
                               'status': record.get('status', 'completed'),
                               'correction_round': number, 'verdict': footer.get('verdict'),
                               'had_blocking_findings': bool(footer.get('must_fix'))})
            continue
        reports.append({'agent': role, 'dispatch_id': agent_id,
                        'dispatch_event_id': record.get('event_id'),
                        'status': record.get('status', 'completed'),
                        'correction_round': number,
                        'iteration_timestamp': record.get('iteration_timestamp', footer.get('iteration_timestamp')),
                        **{key: deepcopy(footer[key]) for key in
                           ('correction_round', 'candidate_signature', 'verdict',
                            'must_fix', 'escalate', 'untested_cells', 'blocked_on') if key in footer}})
    return {'issue_id': start.get('id'), 'title': start.get('title'),
            'iteration_timestamp': start.get('timestamp'),
            'maintenance': deepcopy(start.get('maintenance')),
            'agent_continuity': deepcopy(start.get('agent_continuity') or last.get('agent_continuity')),
            'last_outcome': last.get('outcome'), 'next_step': last.get('next_step'),
            'scope_decisions': deepcopy(last.get('scope_decisions', [])),
            'deliverables': deepcopy(last.get('deliverables')),
            'review_supersessions': deepcopy(last.get('review_supersessions', [])),
            'latest_completions': reports,
            'historical_completions': historical,
            'historical_findings': 'Read the exact referenced footer when a prior finding needs disposition.',
            'history_refs': [{'id': row['id'], 'timestamp': row.get('timestamp')}
                             for row in relevant],
            'source_logs': [f'{STATE}/loop_history.jsonl', f'{STATE}/dispatch_log.jsonl']}


def rejected_correction_rounds(history, issue_id):
    """Return distinct trailing failed repair rounds evidenced in issue history.

The initial attempt is round zero. Repeated validation of one iteration and
historical reviewer reports cannot add failures. Work on another issue does not
erase this issue's unresolved correction streak.
"""
    failures, checkpoint_after = set(), -1
    for row in reversed(history):
        if row.get('id') != issue_id:
            continue
        if row.get('outcome') != 'partial':
            break
        continuity = row.get('agent_continuity') or {}
        reports = (row.get('subagents') or {}).get('richard') or []
        round_number = continuity.get('correction_round')
        legacy_round = False
        if type(round_number) is not int:
            rounds = [r.get('correction_round') for r in reports if isinstance(r, dict)
                      and type(r.get('correction_round')) is int]
            round_number = max(rounds, default=0)
            reviewer = continuity.get('richard')
            reviewer_rounds = reviewer.get('rounds') if isinstance(reviewer, dict) else None
            if not rounds and type(reviewer_rounds) is int:
                round_number, legacy_round = reviewer_rounds, True
        if round_number <= 0:
            break
        checkpoint = row.get('diagnosis_checkpoint') or {}
        if (isinstance(checkpoint, dict) and checkpoint.get('status') == 'agreed'
                and checkpoint.get('issue_id') == issue_id
                and type(checkpoint.get('after_round')) is int
                and 0 <= checkpoint['after_round'] <= round_number):
            checkpoint_after = max(checkpoint_after, checkpoint['after_round'])
        if round_number <= checkpoint_after:
            break
        current_reports = [r for r in reports if isinstance(r, dict)
                           and (r.get('correction_round') == round_number or legacy_round)]
        rejected = any(r.get('verdict') == 'REJECT' or r.get('must_fix') for r in current_reports)
        decisions = row.get('scope_decisions') or []
        unresolved = any(isinstance(d, dict) and d.get('classification') in
                         ('dependency', 'introduced_regression', 'unknown')
                         and d.get('status') != 'resolved' for d in decisions)
        # A failing build can end a correction before a reviewer can run.
        failed_test = row.get('tests_status') == 'failing'
        if not (rejected or unresolved or failed_test):
            break
        failures.add(round_number)
    return sorted(failures)


def unsuccessful_corrections(history, issue_id):
    return len(rejected_correction_rounds(history, issue_id))


def section_bytes(root, path, heading, occurrence=None):
    """Extract one exact Markdown heading and its subtree, excluding code fences."""
    require(isinstance(heading, str) and heading.strip(), 'milestone needs a heading')
    lines = local_file(root, path).read_text(encoding='utf-8').splitlines(keepends=True)
    headings, fence = [], None
    for number, line in enumerate(lines):
        stripped = line.strip()
        marker = re.match(r'^(`{3,}|~{3,})', stripped)
        if marker:
            symbol = marker.group(1)
            if fence is None:
                fence = symbol
            elif symbol[0] == fence[0] and len(symbol) >= len(fence):
                fence = None
            continue
        match = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', line) if fence is None else None
        if match:
            headings.append((number, len(match.group(1)), match.group(2)))
    wanted = re.sub(r'^#{1,6}\s+', '', heading.strip()).rstrip('#').strip()
    matches = [h for h in headings if h[2] == wanted]
    if occurrence is None:
        require(len(matches) == 1, 'milestone heading must exist and be unique; specify occurrence if repeated')
        chosen = matches[0]
    else:
        require(type(occurrence) is int and 1 <= occurrence <= len(matches),
                'milestone heading occurrence is invalid')
        chosen = matches[occurrence - 1]
    first, level, _ = chosen
    end = next((n for n, depth, _ in headings if n > first and depth <= level), len(lines))
    return ''.join(lines[first:end]).encode('utf-8')


def milestone_reference(root, path, heading, occurrence=None):
    data = section_bytes(root, path, heading, occurrence)
    ref = {'path': path, 'heading': heading, 'sha256': hashlib.sha256(data).hexdigest()}
    if occurrence is not None:
        ref['occurrence'] = occurrence
    return ref


def check_milestone(root, done, today=None, allow_legacy=True):
    """Validate an exact milestone section or the explicit legacy tail convention."""
    if 'milestone' not in done:
        return []
    milestone = done.get('milestone')
    if not isinstance(milestone, dict) or type(milestone.get('logged')) is not bool:
        return ['milestone.logged must record a boolean decision']
    if not milestone['logged']:
        return []
    ref = milestone.get('reference', milestone)
    if not isinstance(ref, dict):
        return ['milestone reference must be an object']
    if any(key in ref for key in ('path', 'heading', 'sha256')):
        try:
            measured = milestone_reference(root, ref.get('path'), ref.get('heading'), ref.get('occurrence'))
            require(ref.get('sha256') == measured['sha256'], 'milestone section hash mismatch')
            return []
        except (ValueError, OSError) as exc:
            return [str(exc)]
    if not allow_legacy:
        return ['milestone needs its path, heading and sha256 reference']
    path = Path(root) / 'current_status.md'
    lines, fence = [], None
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            marker = re.match(r'^\s*(`{3,}|~{3,})', line)
            if marker:
                token = marker.group(1)
                if fence is None:
                    fence = token
                elif token[0] == fence[0] and len(token) >= len(fence):
                    fence = None
            elif fence is None:
                lines.append(line)
    date = today or dt.date.today().isoformat()
    return [] if date in '\n'.join(lines[-40:]) else [
        f'legacy milestone needs {date} in the last 40 lines; use an explicit section reference']


def evidence_reference(root, name):
    path = local_file(root, name)
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_checkpoint(root, record, issue_id, minimum_round):
    """Require a reproduced premise and a concrete, evidenced correction decision.

This verifies provenance and completeness. Arch and the assigned agents assess
whether the reproduction settles the disputed mathematics or design question.
"""
    errors = []
    if not isinstance(record, dict):
        return ['diagnosis checkpoint must be an object']
    if record.get('issue_id') != issue_id:
        errors.append('diagnosis checkpoint issue identity mismatch')
    if type(record.get('after_round')) is not int or record['after_round'] < minimum_round:
        errors.append('diagnosis checkpoint predates the rejected correction rounds')
    if record.get('status') != 'agreed':
        errors.append('diagnosis checkpoint must have an agreed next action')
    for field in ('premise', 'next_change', 'acceptance'):
        value = record.get(field)
        if not isinstance(value, str) or len(value.strip()) < 20:
            errors.append(f'diagnosis checkpoint needs a concrete {field}')
    if record.get('decision') not in ('revise_design', 'split_scope', 'gather_evidence'):
        errors.append('diagnosis checkpoint needs revise_design, split_scope or gather_evidence decision')
    reproduction = record.get('reproduction')
    if not isinstance(reproduction, dict) or (not reproduction.get('cmd')
            or reproduction.get('executed') is not True
            or type(reproduction.get('exit')) is not int
            or not str(reproduction.get('result', '')).strip()):
        errors.append('diagnosis checkpoint needs an executed reproduction and its observed result')
    refs = record.get('evidence_refs')
    if not isinstance(refs, list) or not refs:
        errors.append('diagnosis checkpoint needs hashed evidence_refs')
    else:
        for ref in refs:
            try:
                require(isinstance(ref, dict), 'diagnosis evidence must have path and sha256')
                require(evidence_reference(root, ref.get('path')) == ref,
                        'diagnosis evidence hash mismatch')
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    return errors


def summarize_timings(records, issue_id=None):
    """Summarize captured runtime spans; missing starts remain unmeasured.

Per-role work adds individual durations. Observed elapsed time takes the union of
intervals so concurrent reviewer work does not count twice. These numbers exclude
unrecorded orchestration and gaps, which cannot be recovered from stop hooks alone.
"""
    spans, roles, intervals, seen = [], {}, [], set()
    for record in records:
        issue = record.get('issue_id') or (record.get('footer') or {}).get('issue_id')
        if issue_id is not None and issue != issue_id:
            continue
        event = record.get('event_id')
        require(event and event not in seen, 'timings require unique completion event IDs')
        seen.add(event)
        role = record.get('agent_type', 'unknown')
        start, finish = record.get('started_at'), record.get('finished_at')
        duration = None
        if start is not None and finish is not None:
            first, last = timestamp(start), timestamp(finish)
            require(last >= first, f'{event}: finish predates start')
            duration = record.get('duration_seconds')
            if duration is None:
                duration = (last - first).total_seconds()
            require(type(duration) in (int, float) and duration >= 0,
                    f'{event}: invalid captured duration')
            require(math.isfinite(duration), f'{event}: captured duration must be finite')
            intervals.append((first.timestamp(), last.timestamp()))
        total = roles.setdefault(role, {'measured_seconds': 0.0, 'measured_turns': 0,
                                       'unmeasured_turns': 0})
        if duration is None:
            total['unmeasured_turns'] += 1
        else:
            total['measured_seconds'] += duration
            total['measured_turns'] += 1
        spans.append({'dispatch_event_id': event, 'agent': role, 'seconds': duration,
                      'status': record.get('status', 'completed')})
    merged = []
    for first, last in sorted(intervals):
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    return {'issue_id': issue_id, 'by_role': roles, 'turns': spans,
            'observed_elapsed_seconds': sum(b - a for a, b in merged) if intervals else None,
            'coverage': 'Captured agent turns only; orchestration and gaps are unmeasured.'}


def write_output(root, name, payload, inputs=()):
    """Create an explicit new output file; preserve state and existing user files."""
    path = local_file(root, name)
    require(path.name not in PROTECTED, 'output would replace protected active state')
    require(path.suffix == '.json', 'output must be a JSON file')
    require(path.resolve() not in {Path(p).resolve() for p in inputs}, 'output aliases an input')
    require(not path.exists(), 'output already exists; choose a new draft path')
    data = json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.packet-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Atomic publication, preserving existing paths.
    finally:
        os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare-done', help='print an unfinished draft from exact hook completions')
    prepare.add_argument('--start', default=f'{STATE}/issue-start.json')
    prepare.add_argument('--select', required=True, help='JSON array of exact completion identities')
    prepare.add_argument('--prior', help='previous closeout to preserve earlier completion records '
                         '(default: the latest accepted closeout of this issue in loop_state/closed/)')
    prepare.add_argument('--no-prior', action='store_true', help='do not locate a prior closeout automatically')
    prepare.add_argument('--output', help='create this new relative JSON path; default prints only')
    packet = sub.add_parser('continuation', help='print compact current issue assignments and findings')
    packet.add_argument('--start', default=f'{STATE}/issue-start.json')
    milestone = sub.add_parser('milestone', help='hash the exact status section being reported')
    milestone.add_argument('--path', default='current_status.md')
    milestone.add_argument('--heading', required=True)
    milestone.add_argument('--occurrence', type=int)
    timings = sub.add_parser('timings', help='summarize measured runtime turns without double-counting overlap')
    timings.add_argument('--issue')
    from workflow_handoff import add_commands
    add_commands(sub, STATE)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.command in ('review-packet', 'readiness', 'selections'):
            from workflow_handoff import command
            return command(root, args)
        if args.command == 'milestone':
            payload = milestone_reference(root, args.path, args.heading, args.occurrence)
        elif args.command == 'timings':
            payload = summarize_timings(read_jsonl(local_file(root, f'{STATE}/dispatch_log.jsonl')), args.issue)
            events = read_jsonl(local_file(root, f'{STATE}/runtime-preflight.jsonl'))
            payload['preflight'] = {category: {'attempts': len([e for e in events if
                e.get('category') == category and (not args.issue or e.get('issue_id') == args.issue)]),
                'measured_seconds': sum(e.get('duration_seconds', 0) for e in events if
                e.get('category') == category and (not args.issue or e.get('issue_id') == args.issue))}
                for category in ('configuration_recovery', 'packet_repair')}
            payload['preflight']['coverage'] = 'Preflight costs are separate; overlapping role time is not added to elapsed time.'
        else:
            start_path = input_file(root, args.start)
            start = read_json(start_path)
            records = read_jsonl(local_file(root, f'{STATE}/dispatch_log.jsonl'))
            if args.command == 'continuation':
                payload = continuation_packet(start,
                    read_jsonl(local_file(root, f'{STATE}/loop_history.jsonl')), records)
            else:
                selected_path = input_file(root, args.select)
                prior_path = input_file(root, args.prior) if args.prior else (
                    None if args.no_prior else locate_prior(root, start))
                try:
                    payload = prepare_done(start, records, read_json(selected_path),
                                           read_json(prior_path) if prior_path else None)
                except ValueError as exc:
                    if prior_path and not args.prior:
                        raise ValueError(f'{exc} (using the automatically located prior closeout '
                                         f'{prior_path.relative_to(root)}; pass --prior or --no-prior to override)') from exc
                    raise
                if prior_path and not args.prior:
                    payload['preparation']['prior'] = {'path': str(prior_path.relative_to(root)), 'located': 'automatic'}
                if args.output:
                    write_output(root, args.output, payload,
                                 [start_path, selected_path, *([prior_path] if prior_path else [])])
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(f'workflow records: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
