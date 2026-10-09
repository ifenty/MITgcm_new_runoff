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
import re
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


def classify(root):
    """Every recurring process finding with its ONE authoritative classification.

    esx-fix.md C: preparation, the start check, --next and retained dispatch all
    enforced process debt independently, and recurrence alone made a finding
    project-blocking -- on 2026-10-09 TEAM-ARCH-UNVERIFIED-CLAIM-001 recurred and
    stopped every scientific issue until a process fix was implemented. A finding
    is ADVISORY unless its ledger entry carries a valid `Blocking` field naming
    the scope it stops, the evidence and the clearing condition; only then does
    it block, and only work in that scope.
    """
    import self_improvement as si
    rows = {r.uuid: r for r in si.parse(Path(root) / si.OPEN)}
    out = {}
    for uuid in recurring_issues(root, set(rows)):
        value = rows[uuid].fields.get('Blocking')
        parsed = si.parse_blocking(value) if value and not si.blocking_error(value) else None
        out[uuid] = {'classification': 'blocking' if parsed else 'advisory',
                     'scope': parsed[0] if parsed else None,
                     'evidence': parsed[1] if parsed else None,
                     'clears': parsed[2] if parsed else None}
    return out


TRIGGER = re.compile(r'(closeouts):([1-9][0-9]*)|(issue):([A-Za-z0-9_-]+)|(milestone):(.{3,})')


def trigger_fired(root, decision, history):
    """Whether a persistent deferral's trigger has fired (esx-fix.md C)."""
    match = TRIGGER.fullmatch(str(decision.get('trigger') or ''))
    if not match:
        return True
    if match.group(1):
        return len(history) >= decision.get('closeouts_at_decision', 0) + int(match.group(2))
    if match.group(3):
        from records import validate_records
        _, closed, _ = validate_records(root)
        return match.group(4) in closed
    status = Path(root) / 'current_status.md'
    headings = [line for line in status.read_text().splitlines() if line.startswith('#')] if status.exists() else []
    return any(match.group(6).strip().lower() in line.lower() for line in headings)


def decided(root, uuid, classification, history):
    """Whether a recorded decision currently settles this finding.

    An `implemented` decision, and a legacy deferral with no trigger, bind to the
    latest closeout exactly as before. A deferral WITH a trigger persists across
    unrelated closeouts until the trigger fires, so an unchanged recurrence needs
    no new justification; and it is void the moment the finding's classification
    differs from the one it was recorded against -- new evidence reopens triage
    promptly, and a deferral is never an indefinite correctness waiver.
    """
    if not history:
        return False
    for row in reversed(accounting.rows(Path(root) / accounting.STATE / 'improvement_decisions.jsonl')):
        if row.get('issue') != uuid or row.get('disposition') not in ('implemented', 'deferred'):
            continue
        if row.get('disposition') == 'deferred' and row.get('trigger'):
            if row.get('classification', 'advisory') != classification:
                return False
            return not trigger_fired(root, row, history)
        return row.get('closes_timestamp') == history[-1]['timestamp']
    return False


def applies(scope, issue, kind):
    return scope == 'all' or scope == f'issue:{issue}' or scope == f'kind:{kind}'


def followup_due(root, issue=None, kind=None):
    """Blocking process findings that stop THIS work: in scope and not decided.

    With no issue and kind this is the set that stops selection itself, i.e. the
    `all`-scoped blockers. Advisory findings never appear here.
    """
    history = accounting.rows(Path(root) / accounting.STATE / 'loop_history.jsonl')
    if not history:
        return []
    return [uuid for uuid, c in classify(root).items()
            if c['classification'] == 'blocking' and uuid != issue and applies(c['scope'], issue, kind)
            and not decided(root, uuid, 'blocking', history)]


def advisories(root):
    """Recurring findings to surface as information: advisory and not deferred."""
    history = accounting.rows(Path(root) / accounting.STATE / 'loop_history.jsonl')
    return [uuid for uuid, c in classify(root).items()
            if c['classification'] == 'advisory' and not decided(root, uuid, 'advisory', history)]


def scoped_blockers(root):
    """Blocking findings whose scope is narrower than `all`: (uuid, scope)."""
    history = accounting.rows(Path(root) / accounting.STATE / 'loop_history.jsonl')
    return [(uuid, c['scope']) for uuid, c in classify(root).items()
            if c['classification'] == 'blocking' and c['scope'] != 'all'
            and not decided(root, uuid, 'blocking', history)]


def require_followup(root, issue=None, kind=None):
    due = followup_due(root, issue, kind)
    if due:
        rows = classify(root)
        detail = '; '.join(f"{u} blocks {rows[u]['scope']} ({rows[u]['clears']})" for u in due)
        raise ValueError('IMPROVEMENT_FOLLOWUP_REQUIRED: ' + detail
                         + '; run self_improvement.py plan and record a fix or a deferral with a trigger')


def decide_followup(root, issue, disposition, reason, evidence=None, trigger=None):
    """Record a fix, or a deferral bound to a trigger; no provider launch.

    `trigger` is closeouts:N, issue:ID (fires when that issue closes) or
    milestone:TEXT (fires when current_status.md gains a heading containing it).
    """
    if disposition not in ('implemented', 'deferred') or len(reason.strip()) < 40:
        raise ValueError('implemented/deferred disposition and substantive reason required')
    findings = classify(root)
    if issue not in findings:
        raise ValueError('issue is not a recurring process finding')
    if disposition == 'deferred':
        if not TRIGGER.fullmatch(str(trigger or '')):
            raise ValueError('a deferral needs --trigger closeouts:N, issue:ID or milestone:TEXT, so it persists '
                             'across unrelated closeouts and resurfaces when its condition changes')
    if disposition == 'implemented':
        from process_evidence import validation_errors
        errors = validation_errors(root, evidence)
        if errors:
            raise ValueError('; '.join(errors))
    history = accounting.rows(Path(root) / accounting.STATE / 'loop_history.jsonl')
    record = {'issue': issue, 'disposition': disposition, 'reason': reason, 'evidence': evidence,
              'closes_timestamp': history[-1]['timestamp'], 'recorded_at': accounting.now(),
              'classification': findings[issue]['classification']}
    if disposition == 'deferred':
        record.update(trigger=trigger, closeouts_at_decision=len(history))
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


COMMENTARY = 'retrospective_commentary.jsonl'


def reflections(root, last=3):
    """The latest accepted retrospectives, each merged with its completed commentary.

    A retrospective accepted with commentary pending (esx-fix.md C, lightweight
    reflection) carries measurements only; its problems arrive later in a
    separate commentary record. Kept in its own file so a completion is never
    mistaken for an extra retrospective in the recurrence window.
    """
    state = Path(root) / accounting.STATE
    completions = {(r.get('id'), r.get('closes_timestamp')): r for r in accounting.rows(state / COMMENTARY)}
    out = []
    for record in accounting.rows(state / 'retrospective_history.jsonl')[-last:]:
        done = completions.get((record.get('id'), record.get('closes_timestamp')))
        out.append(dict(record, **{k: done[k] for k in ('problems', 'solutions', 'confirmations')
                                   if k in done}) if done else record)
    return out


def pending_commentary(root):
    """Accepted retrospectives whose human commentary is still pending."""
    state = Path(root) / accounting.STATE
    completed = {(r.get('id'), r.get('closes_timestamp')) for r in accounting.rows(state / COMMENTARY)}
    return [r['id'] for r in accounting.rows(state / 'retrospective_history.jsonl')
            if r.get('commentary') == 'pending' and (r.get('id'), r.get('closes_timestamp')) not in completed]


def recurring_issues(root, open_ids):
    """A twice-recurring categorized problem prioritizes its owning process issue."""
    records = reflections(root)
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
    prior = {p.get('category') for r in reflections(root)
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
    require(record.get('commentary', 'complete') in ('complete', 'pending'),
            'commentary must be "complete" or "pending"')
    if record.get('commentary') == 'pending':
        # Lightweight reflection (esx-fix.md C): the measurements are captured
        # automatically and validated above; the human commentary may follow,
        # and neither it nor a missing cost observation blocks unrelated work.
        # Nothing has to be invented to clear the gate -- the 60-character
        # explanation floor pushed exactly that.
        require(record.get('problems') == [] and record.get('solutions') == [] and not record.get('confirmations'),
                'a pending-commentary retrospective carries measurements only; add problems later with '
                '--complete-retro')
        require(isinstance(record.get('carry_forward'), list), 'carry_forward must be a list')
    else:
        content_checks(root, record, require_explanation=True)
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
    return {'status': 'accepted', 'id': record['id'], 'already_accepted': existing is not None,
            'commentary': record.get('commentary', 'complete')}


def complete_commentary(root, record):
    """Add the human commentary to a retrospective accepted with it pending."""
    from project import require
    state = Path(root) / accounting.STATE
    key = (record.get('id'), record.get('closes_timestamp'))
    accepted = next((r for r in accounting.rows(state / 'retrospective_history.jsonl')
                     if (r.get('id'), r.get('closes_timestamp')) == key), None)
    require(accepted is not None and accepted.get('commentary') == 'pending',
            'no accepted retrospective with pending commentary for that id and closes_timestamp')
    require(key not in {(r.get('id'), r.get('closes_timestamp')) for r in accounting.rows(state / COMMENTARY)},
            'commentary already completed for that retrospective')
    content_checks(root, dict(accepted, **record, schema_version=accepted.get('schema_version')),
                   require_explanation=True)
    entry = {k: record[k] for k in ('id', 'closes_timestamp', 'problems', 'solutions', 'confirmations',
                                    'no_problem_reason', 'carry_forward') if k in record}
    entry['completed_at'] = accounting.now()
    accounting.append(state / COMMENTARY, entry)
    return {'status': 'commentary completed', 'id': record['id']}


def content_checks(root, record, require_explanation):
    """Validate a reflection's problems, solutions and confirmations; raise on the first defect."""
    import self_improvement as si
    from project import require
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
    if require_explanation:
        require(bool(problems) or confirmed or len(str(record.get('no_problem_reason', ''))) >= EXPLANATION_FLOOR,
                'explain a no-problem result using measured evidence: a no_problem_reason or a confirmation '
                'whose evidence is at least %d characters, or accept it with "commentary": "pending"'
                % EXPLANATION_FLOOR)
    errors = recurrence_errors(root, record, opened)
    require(not errors, '; '.join(errors))


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
