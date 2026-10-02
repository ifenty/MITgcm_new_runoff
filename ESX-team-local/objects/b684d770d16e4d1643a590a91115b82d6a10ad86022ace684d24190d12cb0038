#!/usr/bin/env python3
"""Shared retrospective debt, generated measurements and recurrence scheduling.

Legacy accepted records remain visible as schema 1. New records bind schema-2
or schema-3 measurements to reconciled accounting; schema 3 adds a
``confirmations`` array for validated approaches worth repeating, which carry no
minutes_lost or disposition and never feed recurring-category scheduling. No
numerical outcome is inferred from process metrics. Stop paths preserve debt
without extending a spending limit.
"""
import hashlib
import json
from pathlib import Path
import team_accounting as accounting

SCHEMA_VERSIONS = (2, 3)
DRAFT_SCHEMA = 3
ENTRY_FLOOR = 20        # summary/evidence length for any problem or confirmation
EXPLANATION_FLOOR = 60  # no_problem_reason, or one confirmation's evidence, for empty problems


def pending(root):
    state = Path(root) / accounting.STATE
    history = accounting.rows(state / 'loop_history.jsonl')
    if not history: return None
    last = history[-1]
    for record in accounting.rows(state / 'retrospective_history.jsonl'):
        if (record.get('id'), record.get('closes_timestamp')) == (last.get('id'), last.get('timestamp')):
            return None
    return last


def require_clear(root):
    debt = pending(root)
    if debt: raise ValueError('RETROSPECTIVE_REQUIRED: ' + debt['id'] + '; run --draft-retro then --check-retro')


def followup_due(root):
    """Recurring process owners need a measured fix or explicit bounded deferral.

    Decisions bind to the latest closeout, so another recurrence cannot inherit an
    indefinite deferral. This is a process queue, never a scientific candidate.
    """
    import self_improvement as si
    open_ids = {r.uuid for r in si.parse(Path(root) / si.OPEN)}
    history = accounting.rows(Path(root) / accounting.STATE / 'loop_history.jsonl')
    if not history:
        return []
    last = history[-1]
    decisions = accounting.rows(Path(root) / accounting.STATE / 'improvement_decisions.jsonl')
    decided = {r['issue'] for r in decisions if r.get('closes_timestamp') == last['timestamp']
               and r.get('disposition') in ('implemented', 'deferred')}
    return [issue for issue in recurring_issues(root, open_ids) if issue not in decided]


def require_followup(root, issue=None):
    due = followup_due(root)
    if due and issue not in due:
        raise ValueError('IMPROVEMENT_FOLLOWUP_REQUIRED: ' + ', '.join(due)
                         + '; run self_improvement.py plan and record a fix or bounded deferral')


def decide_followup(root, issue, disposition, reason, evidence=None):
    """Record a current fix or explicit one-iteration deferral; no provider launch."""
    if disposition not in ('implemented', 'deferred') or len(reason.strip()) < 40:
        raise ValueError('implemented/deferred disposition and substantive reason required')
    if issue not in followup_due(root):
        raise ValueError('issue is not currently due for process follow-up')
    if disposition == 'implemented':
        from process_evidence import validation_errors
        errors = validation_errors(root, evidence)
        if errors:
            raise ValueError('; '.join(errors))
    last = accounting.rows(Path(root) / accounting.STATE / 'loop_history.jsonl')[-1]
    record = {'issue': issue, 'disposition': disposition, 'reason': reason, 'evidence': evidence,
              'closes_timestamp': last['timestamp'], 'recorded_at': accounting.now()}
    accounting.append(Path(root) / accounting.STATE / 'improvement_decisions.jsonl', record)
    return record


def persist_debt(root, reason):
    debt = pending(root)
    path = Path(root) / accounting.STATE / 'retrospective_debt.json'
    if debt:
        accounting.atomic(path, {'id': debt['id'], 'closes_timestamp': debt['timestamp'], 'reason': reason})
    elif path.exists(): path.unlink()
    return debt


SOLUTION_GUIDE = {
    'problem': '{"category": short label, "summary": >=20 chars, "evidence": >=20 chars, "minutes_lost": integer >= 0}',
    'solution': 'one per problem: {"problem": index into problems, "action": ..., plus the fields that action needs}',
    'actions': 'solution actions are: "filed" (needs "issue": an OPEN process-ledger id); '
               '"deferred" (needs "issue": an OPEN process-ledger id and "reason" >= 40 chars); '
               '"fixed" (needs "reference": the commit, released version or file that fixed it, and "reason" >= 40 '
               'chars; for a problem resolved inside the issue or already released upstream); '
               '"implemented" (needs "issue": a CLOSED process-ledger id, "changelog" equal to its '
               'Implementation-Commit, "effectiveness": landed|verified and "expected_effect" >= 20 chars)',
    'recurrence': 'a problem category seen in the last three retrospectives needs an open owner or a verified fix; '
                  '"fixed" alone does not satisfy it',
    'confirmation': '{"category", "summary", "evidence"}: something that worked and should be kept',
    'note': 'delete this "guide" object or leave it; it is ignored at --check-retro'}


def draft(root):
    state = Path(root) / accounting.STATE
    history = accounting.rows(state / 'loop_history.jsonl')
    if not history: raise ValueError('no iteration to reflect on')
    last = history[-1]
    report = accounting.summary(root, last['id'], last.get('start_timestamp') or last['timestamp'], last.get('closed_at', last['timestamp']))
    data = json.dumps(report, sort_keys=True, allow_nan=False).encode()
    digest = hashlib.sha256(data).hexdigest()
    path = state / 'accounting' / (digest + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {'schema_version': DRAFT_SCHEMA, 'id': last['id'], 'iteration': last.get('iteration'),
            'closes_timestamp': last['timestamp'], 'timestamp': accounting.now().split('.')[0] + 'Z',
            'accounting': {'path': str(path.relative_to(root)), 'sha256': digest},
            'measured': accounting.measured(report), 'problems': [], 'solutions': [],
            'confirmations': [], 'carry_forward': [], 'no_problem_reason': '', 'guide': SOLUTION_GUIDE}


def validate_measurements(root, record, last):
    errors = []
    if record.get('schema_version') not in SCHEMA_VERSIONS:
        return ['new retrospectives require schema_version 2 or 3; generate --draft-retro']
    try:
        ref = record['accounting']
        path = (Path(root) / ref['path']).resolve()
        if not path.is_relative_to((Path(root) / accounting.STATE / 'accounting').resolve()):
            raise ValueError('accounting receipt must be in loop_state/accounting')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != ref['sha256']: raise ValueError('accounting hash mismatch')
        saved = json.loads(data)
        current = accounting.summary(root, last['id'], last.get('start_timestamp') or last['timestamp'], last.get('closed_at', last['timestamp']))
        if saved != current: raise ValueError('accounting is stale or differs from runtime evidence')
        if record.get('measured') != accounting.measured(saved): raise ValueError('measured block differs from accounting receipt')
    except (ValueError, OSError, KeyError, TypeError) as exc: errors.append(str(exc))
    return errors


def substantive(value, floor):
    return isinstance(value, str) and len(value.strip()) >= floor


def confirmation_errors(record):
    """Schema-3 confirmations: category, summary and evidence; no cost, no owner.

    Returns (errors, explains) where explains is true when at least one
    confirmation's evidence meets the floor an empty problems list must supply.
    """
    if record.get('schema_version') != 3:
        if 'confirmations' in record:
            return ['confirmations require schema_version 3'], False
        return [], False
    confirmations = record.get('confirmations')
    if not isinstance(confirmations, list):
        return ['confirmations must be a list'], False
    errors = []
    for i, entry in enumerate(confirmations):
        if not (isinstance(entry, dict) and isinstance(entry.get('category'), str) and entry['category'].strip()
                and substantive(entry.get('summary'), ENTRY_FLOOR) and substantive(entry.get('evidence'), ENTRY_FLOOR)):
            errors.append('confirmation %d needs category and concrete summary/evidence' % i)
    explains = not errors and any(substantive(c.get('evidence'), EXPLANATION_FLOOR) for c in confirmations)
    return errors, explains


def recurring_issues(root, open_ids):
    """A twice-recurring categorized problem prioritizes its owning process issue."""
    records = accounting.rows(Path(root) / accounting.STATE / 'retrospective_history.jsonl')[-3:]
    occurrences = {}
    for record in records:
        seen = set()
        for solution in record.get('solutions', []):
            index = solution.get('problem')
            problems = record.get('problems', [])
            if type(index) is not int or not 0 <= index < len(problems): continue
            category = problems[index].get('category')
            owner = solution.get('issue') or solution.get('reference')
            if category and owner in open_ids and solution.get('effectiveness') != 'verified':
                seen.add((category, owner))
        for pair in seen: occurrences[pair] = occurrences.get(pair, 0) + 1
    return sorted({owner for (_, owner), n in occurrences.items() if n >= 2})


def effectiveness_errors(root, ref):
    """Verify a content-bound before/after measurement, without inferring causality."""
    from process_evidence import effectiveness_errors as check
    return check(root, ref)


def recurrence_errors(root, record, open_ids):
    """A repeated unresolved problem must have an open owner or a verified new fix."""
    prior = {p.get('category') for r in accounting.rows(Path(root)/accounting.STATE/'retrospective_history.jsonl')[-3:]
             for p in r.get('problems',[]) if isinstance(p,dict)}
    errors=[]
    for i, problem in enumerate(record.get('problems',[]) or []):
        if not isinstance(problem,dict) or problem.get('category') not in prior: continue
        solutions=[s for s in record.get('solutions',[]) or [] if isinstance(s,dict) and s.get('problem')==i]
        owned=any((s.get('issue') or s.get('reference')) in open_ids or
                  (s.get('effectiveness')=='verified' and not effectiveness_errors(root,s.get('measurement'))) for s in solutions)
        if not owned: errors.append('recurring category '+problem['category']+' needs an owning open issue or verified fix')
    return errors


def accept(root, record):
    """Validate an exact measured closeout reflection before saving it once."""
    import self_improvement as si
    from project import require
    history = accounting.rows(Path(root) / accounting.STATE / 'loop_history.jsonl')
    require(bool(history), 'no completed iteration to reflect on')
    last = history[-1]
    require(isinstance(record, dict) and record.get('id') == last['id']
            and record.get('closes_timestamp') == last['timestamp'], 'retrospective must match the last closeout')
    record = {key: value for key, value in record.items() if key != 'guide'}
    errors = validate_measurements(root, record, last)
    errors += si.validate(Path(root))
    require(not errors, '; '.join(errors))
    problems, solutions = record.get('problems'), record.get('solutions')
    require(isinstance(problems, list) and isinstance(solutions, list), 'problems and solutions must be lists')
    require(isinstance(record.get('carry_forward'), list) and all(isinstance(r, str) and r.strip() for r in record['carry_forward']), 'carry_forward must be a list of nonempty strings')
    require(not {rule_key(r) for r in record['carry_forward']} & {rule_key(r) for r in standing_rules(root)}, 'do not repeat standing rules in carry_forward')
    opened = {row.uuid for row in si.parse(Path(root) / si.OPEN)}
    closed = {row.uuid: row for row in si.parse(Path(root) / si.CLOSED)}
    for problem in problems:
        require(isinstance(problem, dict) and isinstance(problem.get('category'), str) and problem['category']
                and len(str(problem.get('summary', ''))) >= 20 and len(str(problem.get('evidence', ''))) >= 20
                and type(problem.get('minutes_lost')) is int and problem['minutes_lost'] >= 0,
                'each problem needs category, concrete summary/evidence and nonnegative integer minutes_lost')
    covered = set()
    for solution in solutions:
        require(isinstance(solution, dict), 'solution must be an object')
        index = solution.get('problem')
        require(type(index) is int and 0 <= index < len(problems), 'solution must index an observed problem')
        covered.add(index)
        action = solution.get('action')
        owner = solution.get('issue') or solution.get('reference')
        if action in ('filed', 'deferred'):
            require(owner in opened, f'{action} solution needs "issue": an open process-ledger id '
                    '(devel-loop/self-improvement/open-ESX-team-issues.md); a problem already resolved uses action "fixed"')
            if action == 'deferred':
                require(len(str(solution.get('reason', solution.get('reference', '')))) >= 40, 'substantive deferral reason required')
        elif action == 'implemented':
            require(owner in closed, 'implemented solution needs a closed process owner; unpublished work uses filed')
            errors = si.check_issue(Path(root), closed[owner], True)
            require(not errors, '; '.join(errors))
            require(solution.get('changelog') == closed[owner].fields.get('Implementation-Commit'), 'cite the owning implementation commit')
            require(solution.get('effectiveness') in ('landed', 'verified')
                    and len(str(solution.get('expected_effect', ''))) >= 20, 'record landed/verified and expected measurable effect')
            if solution['effectiveness'] == 'verified':
                errors = effectiveness_errors(root, solution.get('measurement'))
                require(not errors, '; '.join(errors))
        elif action == 'fixed':
            # Resolved inside the issue itself, or already released upstream: nothing
            # is left for a process owner to do, so cite what fixed it.
            require(isinstance(solution.get('reference'), str) and solution['reference'].strip()
                    and len(str(solution.get('reason', ''))) >= 40,
                    'fixed solution needs "reference" (the commit, released version or file that fixed it) '
                    'and a "reason" of at least 40 characters')
        else:
            raise ValueError('unknown solution action ' + repr(action) + '; ' + SOLUTION_GUIDE['actions'])
    require(covered == set(range(len(problems))), 'each problem needs a disposition')
    errors, confirmed = confirmation_errors(record)
    require(not errors, '; '.join(errors))
    require(bool(problems) or confirmed or len(str(record.get('no_problem_reason', ''))) >= EXPLANATION_FLOOR,
            'explain a no-problem result using measured evidence: a no_problem_reason or a confirmation '
            'whose evidence is at least %d characters' % EXPLANATION_FLOOR)
    errors = recurrence_errors(root, record, opened)
    require(not errors, '; '.join(errors))
    path = Path(root) / accounting.STATE / 'retrospective_history.jsonl'
    existing = next((r for r in accounting.rows(path) if (r.get('id'), r.get('closes_timestamp')) ==
                    (record['id'], record['closes_timestamp'])), None)
    require(existing is None or existing == record, 'accepted retrospective is immutable; retain the original evidence')
    if existing is None:
        archived = {'retrospective': record, 'accounting': json.loads((Path(root) / record['accounting']['path']).read_text())}
        key = hashlib.sha256(json.dumps(archived, sort_keys=True).encode()).hexdigest()
        accounting.atomic(Path(root) / si.BASE / 'assessments/retrospectives' / (key + '.json'), archived)
        accounting.append(path, record)
    persist_debt(root, 'retrospective accepted')
    return {'status': 'accepted', 'id': record['id'], 'already_accepted': existing is not None}


def rule_key(rule):
    return ' '.join(rule.replace('`', '').split()).lower().rstrip('.')


def standing_rules(root):
    path = Path(root) / 'devel-loop/loop_rules.md'
    rules, active = [], False
    for line in path.read_text().splitlines() if path.exists() else []:
        if line.startswith('## '):
            active = line == '## Rules'
        elif active and line.startswith('- '):
            rules.append(line[2:].strip())
    if len(rules) > 25:
        raise ValueError('standing rule budget is 25; retire rules now enforced by code')
    return rules


def rule_notices(root):
    standing = standing_rules(root)
    notices = ['STANDING RULE: ' + r for r in standing]
    known = {rule_key(r) for r in standing}
    recent = {}
    for row in accounting.rows(Path(root) / accounting.STATE / 'retrospective_history.jsonl')[-3:]:
        for rule in set(row.get('carry_forward', [])):
            key = rule_key(rule)
            if key not in known:
                count, _ = recent.get(key, (0, rule))
                recent[key] = (count + 1, rule)
    return notices + [('PROMOTE OR RETIRE: ' if count >= 2 else 'CARRY FORWARD: ') + rule for count, rule in recent.values()]
