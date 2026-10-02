"""Read-only closeout dry run: report every unmet requirement at once.

`loop_gate.py --check-done` stops at the first unmet condition, so a closer
learns the requirement set one rejection at a time. This module evaluates the
same conditions independently, using the same validators, and returns all of
them as a `findings` list (the shape `workflow_handoff.readiness` uses). It then
replays the strict gate on a copy; the report is `ready` only when that strict
gate accepts, so the dry run can never claim more than `--check-done` would.
Nothing is written: no history, no ledger, no accounting phase.
"""
from copy import deepcopy
import json
import re
import subprocess
import sys

import audit
import doc_contract as maintenance
import final_verification
import loop_iteration
import verify
import workflow_policy as workflow
import workflow_records
from project import ROLES, STATE, json_file, local, source_signature
from records import json_lines, validate_records
from workflow_handoff import finding

ERRORS = (ValueError, OSError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError)

ORDERING = ('Finalize every signed field before taking the final verification receipt. '
            'final_verification.py run binds its receipt to review_signature, a digest over the closeout fields '
            'listed here; editing any of them afterwards makes --check-done report "final verification receipt '
            'is stale". A stale receipt caused only by such a bookkeeping edit does not need a fresh scientific '
            'execution: rerun final_verification.py run without --fresh and it rebinds the unchanged execution '
            'to the current acceptance.')


def signature_notice(done, current_ref=None):
    """Describe the review_signature dependency and whether a receipt still matches."""
    fields = list(final_verification.REVIEW_SIGNATURE_FIELDS)
    notice = {'fields': fields, 'ordering': ORDERING, 'current': None, 'receipt': None}
    if isinstance(done, dict):
        notice['current'] = final_verification.review_signature(done)
    if isinstance(current_ref, dict):
        notice['receipt'] = current_ref.get('review_signature')
    return notice


def diagnose(gate, done_path=None):
    """Return every unmet closeout requirement for the active iteration."""
    root = gate.root
    findings = []

    def add(code, field, observed, recovery, **identity):
        findings.append(finding(code, field, observed, recovery, **identity))

    def check(code, field, action, recovery, **identity):
        try:
            return action()
        except ERRORS as exc:
            add(code, field, exc, recovery, **identity)
            return None

    def many(code, field, errors, recovery):
        for message in errors:
            add(code, field, message, recovery)

    def need(condition, code, field, observed, recovery, **identity):
        if not condition:
            add(code, field, observed, recovery, **identity)
        return bool(condition)

    check('AUDIT_FAILED', 'project', lambda: audit.check(root, gate.ledger_overrides),
          'Run loop_gate.py --doctor and repair the reported project structure.')
    start = check('START_MISSING', 'issue-start.json', lambda: gate.read('issue-start.json'),
                  'Prepare the iteration with loop_gate.py --prepare.')
    if done_path:
        from workflow_handoff import input_file
        done = check('DONE_MISSING', done_path, lambda: json.loads(input_file(root, done_path).read_text()),
                     'Supply the draft closeout JSON path.')
    else:
        done = check('DONE_MISSING', 'issue-done.json', lambda: gate.read('issue-done.json'),
                     'Draft it with workflow_records.py prepare-done or loop_lifecycle.py prepare-done.')
    if not isinstance(start, dict) or not isinstance(done, dict):
        return report(findings, None, done, 'not evaluated: issue-start or closeout draft is unreadable')

    # Iteration identity and outcome.
    need((done.get('id'), done.get('timestamp')) == (start.get('id'), start.get('timestamp')), 'ITERATION_MISMATCH',
         'id/timestamp', (done.get('id'), done.get('timestamp')), 'Copy id and timestamp exactly from issue-start.json.')
    validation = loop_iteration.start_status(root, start)
    if start.get('state_version', 1) >= 2 or done.get('state_version', 1) >= 2:
        need(loop_iteration.matches(start, done), 'ITERATION_IDENTITY', 'state_version/iteration',
             'closeout must preserve exact iteration identity', 'Copy state_version, id, iteration and timestamp from issue-start.json.')
        need(validation['validated'], 'START_NOT_VALIDATED', 'start_validation', validation.get('reason'),
             'Run loop_gate.py --check-start for this iteration.')
    outcome = done.get('outcome')
    need(outcome in ('completed', 'partial', 'blocked') and done.get('summary'), 'OUTCOME_MISSING', 'outcome/summary',
         (outcome, bool(done.get('summary'))), 'Record outcome completed, partial or blocked and a summary.')
    completed = outcome == 'completed'

    # Workflow, scope and maintenance start.
    start_policy = start.get('workflow') or {}
    policy = done.get('workflow')
    many('WORKFLOW_INVALID', 'workflow', workflow.validate_workflow(start_policy) + workflow.validate_workflow(policy or {}),
         'Copy the workflow from issue-start.json or record a valid amendment.')
    if isinstance(policy, dict):
        many('WORKFLOW_TRANSITION', 'workflow_amendment',
             workflow.validate_transition(start_policy, policy, done.get('workflow_amendment')),
             'Record workflow_amendment.previous (the start workflow) and its reason.')
    many('SCOPE_DECISION_INVALID', 'scope_decisions', workflow.validate_scope_decisions(done.get('scope_decisions', []), completed),
         'Classify each decision as ' + ', '.join(workflow.SCOPE_CLASSIFICATIONS) + ' with status and evidence_refs; '
         'separate_existing and separate_new also need issue_id.')
    many('MAINTENANCE_START', 'maintenance', check('MAINTENANCE_START', 'maintenance', lambda: maintenance.check_start(root, start),
         'Restore the start maintenance records.') or [], 'Restore the start maintenance records.')
    history = json_lines(local(root, f'{STATE}/loop_history.jsonl'))
    check('DIAGNOSIS_REQUIRED', 'diagnosis_checkpoint', lambda: gate.check_diagnosis(start, history),
          'Record the agreed diagnosis checkpoint after two rejected correction rounds.')
    need((done.get('maintenance') or {}).get('baseline') == (start.get('maintenance') or {}).get('baseline'),
         'BASELINE_MISMATCH', 'maintenance.baseline', 'completion must preserve original maintenance baseline',
         'Copy maintenance.baseline from issue-start.json.')
    if isinstance(policy, dict):
        for key in ('verify_signature_at_start', 'numerical_signature_at_start'):
            need(policy.get(key) == start_policy.get(key), 'SIGNATURE_NOT_PRESERVED', 'workflow.' + key,
                 'workflow amendment must preserve measured initial signatures', 'Copy it from issue-start.json.')
    else:
        policy = {}

    # Ledger, lessons, communication and git.
    ledgers = check('LEDGER_INVALID', 'open_issues.md/closed_issues.md',
                    lambda: validate_records(root, gate.ledger_overrides), 'Repair the issue ledgers.')
    if ledgers:
        opened, closed, lessons = ledgers
        issue = done.get('id')
        if completed:
            need((issue in closed) != (issue in opened), 'LEDGER_ENTRY_INVALID', 'open_issues.md/closed_issues.md',
                 'completed issue must appear in exactly one ledger',
                 'Leave the entry in open_issues.md; --check-done moves it on acceptance.')
            if policy.get('numerical_signature_at_start') and policy.get('kind') != 'scientific_change':
                need(source_signature(root, scientific=True) == policy['numerical_signature_at_start'],
                     'KIND_AMENDMENT_REQUIRED', 'workflow.kind',
                     'scientific source/tests/configuration changed: amend workflow kind',
                     'Amend the workflow to scientific_change with a recorded reason.')
        elif outcome in ('partial', 'blocked'):
            need(issue in opened and done.get('next_step'), 'OPEN_ENTRY_OR_NEXT_STEP', 'next_step',
                 'incomplete work needs its open entry and next_step', 'Keep the open entry and record next_step.')
            if outcome == 'blocked' and issue in opened:
                need(opened[issue]['state'] == 'blocked' and done.get('blocked_by') == opened[issue]['blocker'],
                     'BLOCKER_MISMATCH', 'blocked_by', done.get('blocked_by'), 'Mirror the open entry blocker exactly.')
        need(set(done.get('lessons', [])).issubset(lessons), 'LESSON_UNKNOWN', 'lessons', done.get('lessons'),
             'Cite only active lesson IDs, or an empty list.')
    # The gate's own module (it may be running as __main__).
    announcement = sys.modules[type(gate).__module__].announcement
    check('COMMUNICATION_MISSING', 'communication', lambda: announcement(done),
          'Record communication status and detail, or the returned receipt.')
    need(not done.get('slack_ts') or done.get('slack_ts') != start.get('slack_ts'), 'SLACK_REUSED', 'slack_ts',
         done.get('slack_ts'), 'Start and done need distinct receipts.')
    git = done.get('git')
    if need(isinstance(git, dict) and type(git.get('committed')) is bool, 'GIT_DISPOSITION', 'git', git,
            'Record git.committed with a SHA, or false with a reason.'):
        if git['committed']:
            sha = git.get('sha', '')
            if need(isinstance(sha, str) and re.fullmatch(r'[0-9a-fA-F]{7,40}', sha), 'GIT_SHA', 'git.sha', sha,
                    'Record the commit SHA.'):
                run = subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'HEAD'], cwd=root, capture_output=True)
                need(run.returncode == 0, 'GIT_SHA', 'git.sha', 'recorded commit does not exist in this repository',
                     'Record a commit reachable from HEAD.')
        else:
            need(isinstance(git.get('reason'), str) and len(git['reason'].strip()) >= 20, 'GIT_REASON', 'git.reason',
                 git.get('reason'), 'Explain the uncommitted disposition in at least 20 characters.')

    # Captured completions and runtime identities.
    records = json_lines(local(root, f'{STATE}/dispatch_log.jsonl'))
    subs = done.get('subagents', {})
    agents, used, selected = {}, set(), []
    if need(isinstance(subs, dict) and set(subs).issubset(ROLES[1:]), 'SUBAGENTS_INVALID', 'subagents', 'unknown role or not an object',
            'Map known roles to arrays of exact completions (workflow_records.py prepare-done).'):
        for role, entries in subs.items():
            if not need(isinstance(entries, list), 'SUBAGENTS_INVALID', 'subagents.' + role, 'completions must be a list',
                        'Rebuild from exact event selections.'):
                continue
            agents[role] = set()
            for entry in entries:
                entry = entry if isinstance(entry, dict) else {}
                ident = dict(agent=entry.get('dispatch_id'), event=entry.get('dispatch_event_id'))
                matches = [r for r in records if r.get('event_id') == entry.get('dispatch_event_id')
                           and r.get('agent_id') == entry.get('dispatch_id') and r.get('agent_type') == role]
                if not need(len(matches) == 1 and matches[0]['event_id'] not in used, 'COMPLETION_MISSING', 'subagents.' + role,
                            f'{role}: missing or duplicated exact completion',
                            'Select a unique recorded event (workflow_records.py selections).', **ident):
                    continue
                event = matches[0]
                used.add(event['event_id'])
                agents[role].add(event['agent_id'])
                selected.append(event)
                if not workflow.completed(event):
                    if completed:
                        need(workflow.resolved_dispatch(event, records, done), 'TURN_UNRESOLVED', 'subagents.' + role,
                             f'{role}: failed or incomplete turn remains unresolved',
                             'Select the later completed continuation of the same agent, or fill the '
                             'agent_continuity.replacements entry (role, old_id, new_id, reason, evidence_refs) '
                             'that prepare-done drafts for it.', **ident)
                    else:
                        need(entry.get('status') == event.get('status'), 'FAILED_STATUS', 'subagents.' + role,
                             f'{role}: preserve the failed turn status', 'Copy the captured status.', **ident)
                    continue
                footer = event.get('footer')
                if not need(isinstance(footer, dict) and footer.get('agent') == role and footer.get('issue_id') == done.get('id')
                            and workflow.known_completion_iteration(event, start, history), 'COMPLETION_FOREIGN',
                            'subagents.' + role, f'{role}: footer belongs to another role/iteration',
                            'Select this iteration\'s completion, or retain older ones through --prior.', **ident):
                    continue
                for key in ('verdict', 'must_fix', 'independent_check', 'orientation', 'candidate_signature', 'documentation_review'):
                    if key in entry:
                        need(entry[key] == footer.get(key), 'COMPLETION_ALTERED', f'subagents.{role}.{key}',
                             f'{role}: copied {key} differs from captured footer', 'Reimport the exact footer.', **ident)
                check('ORIENTATION_INVALID', f'subagents.{role}.orientation',
                      lambda f=footer, r=role: maintenance.validate_orientation(
                          root, f.get('orientation'), done.get('id'), start['maintenance']['baseline'], r, fresh=False),
                      'Resume the agent to refresh its orientation.', **ident)
    continuity = done.get('agent_continuity', {})
    if need(isinstance(continuity, dict), 'CONTINUITY_INVALID', 'agent_continuity', 'must be an object',
            'Record agent_continuity as an object.'):
        for role in ('bob', 'richard'):
            if not agents.get(role):
                continue
            assignment = continuity.get(role, [])
            need(isinstance(assignment, list) and set(assignment) == agents[role], 'CONTINUITY_IDENTITIES',
                 f'agent_continuity.{role}', f'record stable {role} runtime identities',
                 f'Set agent_continuity.{role} to exactly the dispatch_ids already in subagents.{role}, '
                 f'originals first: {sorted(agents[role])}.')
            if isinstance(assignment, list):
                initial = 1 if role == 'bob' else max(1, policy.get('minimum_reviewers') or 0)
                for replacement_id in assignment[initial:]:
                    need(any(isinstance(r, dict) and r.get('role') == role and r.get('new_id') == replacement_id
                             and r.get('old_id') in agents[role] and r.get('old_id') != replacement_id and r.get('reason')
                             for r in continuity.get('replacements', [])), 'REPLACEMENT_UNEXPLAINED',
                         'agent_continuity.replacements', f'{role}: explain each replacement runtime identity ({replacement_id})',
                         'Add {role, old_id, new_id, reason, evidence_refs} for this identity.')
        failed = continuity.get('unsuccessful_since_checkpoint', 0)
        if need(type(failed) is int and failed >= 0, 'CONTINUITY_INVALID', 'agent_continuity.unsuccessful_since_checkpoint',
                failed, 'Record a nonnegative integer.') and failed >= 2 and completed:
            checkpoint = continuity.get('diagnosis_checkpoint', {})
            need(all(checkpoint.get(k) for k in ('evidence', 'premise', 'next_change', 'acceptance')), 'DIAGNOSIS_REQUIRED',
                 'agent_continuity.diagnosis_checkpoint', 'two unsuccessful corrections require the diagnosis checkpoint',
                 'Record evidence, premise, next_change and acceptance.')
    need(not agents.get('bob', set()) & agents.get('richard', set()), 'IDENTITY_OVERLAP', 'subagents',
         'implementation and review require distinct runtime identities', 'Use a distinct reviewer identity.')

    # Completed-work evidence.
    current_ref = None
    if completed:
        candidate = source_signature(root)
        for role in policy.get('required_roles', []):
            need(agents.get(role), 'ROLE_MISSING', 'subagents.' + role, f'missing required role: {role}',
                 'Select the completion of each required role.')
        if isinstance(policy.get('minimum_reviewers'), int):
            many('REVIEW_INVALID', 'subagents.richard', check('REVIEW_INVALID', 'subagents.richard',
                 lambda: workflow.validate_reviews(done, records, candidate), 'Repair the review record.') or [],
                 'Obtain or select the current approving review; never waive a failed one.')
        for event in selected:
            footer = event.get('footer') or {}
            if (workflow.completed(event) and workflow.current_review(event, records, done, candidate)
                    and footer.get('verdict') in ('APPROVE', 'APPROVE_WITH_FIXES')):
                def independent(e=event, f=footer):
                    evidence = verify.load_evidence(root, f.get('independent_check', {}).get('evidence'))
                    if not (evidence['owner'] == e['agent_id'] and evidence['started_at'] >= start['timestamp']):
                        raise ValueError('independent check must have been executed by this reviewer during this iteration')
                check('INDEPENDENT_CHECK_INVALID', 'subagents.richard.independent_check', independent,
                      'The reviewer runs verify.py under its own identity this iteration and cites that evidence.',
                      agent=event.get('agent_id'), event=event.get('event_id'))
        verification = done.get('verification') if isinstance(done.get('verification'), dict) else {}
        need(verification.get('final_owner') == policy.get('final_verify_owner'), 'VERIFICATION_OWNER',
             'verification.final_owner', verification.get('final_owner'), 'Record the assigned final verification owner.')
        kind = policy.get('kind')
        for suite in ['structural'] + (['scientific'] if kind == 'scientific_change' else []):
            if not need(isinstance(verification.get(suite), dict), 'VERIFICATION_REFERENCE_MISSING', 'verification.' + suite,
                        workflow.verification_reference_message(kind, suite),
                        'Cite the evidence reference returned by verify.py (structural) or final_verification.py run (scientific, receipt).'):
                continue

            def suite_evidence(s=suite):
                evidence = verify.load_evidence(root, verification.get(s))
                if not (evidence['suite'] == s and evidence['commands'] == gate.cfg['verification'][s]):
                    raise ValueError(f'{s}: evidence must run the complete configured suite')
            check('VERIFICATION_INVALID', 'verification.' + suite, suite_evidence, f'Rerun verify.py --suite {suite}.')
        if policy.get('execution_version') == 1 and kind == 'scientific_change':
            pending = (done.get('preparation') or {}).get('pending')
            need(not pending, 'PREPARATION_PENDING', 'preparation.pending', pending,
                 'Resolve each listed item, then remove preparation.pending BEFORE taking the receipt (it is not signed, '
                 'but final_verification.py refuses a packet that still has pending fields).')
            index = local(root, f'{STATE}/final-verification/current.json')
            if index.exists():
                current = check('RECEIPT_INVALID', 'final-verification/current.json', lambda: json_file(
                    root, json_file(root, f'{STATE}/final-verification/current.json')['path']),
                    'Rerun final_verification.py run.')
                current_ref = (current or {}).get('identity')
            if need(isinstance(verification.get('receipt'), dict), 'VERIFICATION_REFERENCE_MISSING', 'verification.receipt',
                    workflow.verification_reference_message(kind, 'receipt'),
                    'Cite the receipt returned by final_verification.py run, after finalizing every signed field.'):
                if (current_ref and current_ref.get('review_signature')
                        != final_verification.review_signature(done)):
                    add('RECEIPT_SIGNATURE_STALE', 'verification.receipt',
                        'the receipt was taken before these signed closeout fields reached their current values: '
                        + ', '.join(final_verification.REVIEW_SIGNATURE_FIELDS),
                        'Finish all signed fields, then rerun final_verification.py run (no --fresh): it reuses the '
                        'unchanged scientific execution and issues a receipt bound to the current fields.')
                else:
                    check('RECEIPT_INVALID', 'verification.receipt', lambda: final_verification.check_receipt(root, done),
                          'Finalize every signed field, then rerun final_verification.py run.')
        many('DOCUMENTATION_INVALID', 'maintenance.documentation', check(
            'DOCUMENTATION_INVALID', 'maintenance.documentation',
            lambda: maintenance.check_done(root, start, done, records, candidate), 'Repair the documentation record.') or [],
            'Complete and seal the documentation report; cite its exact reference.')
    many('MILESTONE_INVALID', 'milestone', workflow_records.check_milestone(
        root, done, allow_legacy=policy.get('execution_version') != 1), 'Record milestone.logged false, or an exact section reference.')

    # The strict gate remains authoritative; replay it without side effects.
    # --check-done moves a completed entry to closed_issues.md on acceptance, so
    # replay against that staged move rather than the unmoved ledgers.
    try:
        staged = None
        if (gate.ledger_overrides is None and start and done.get('outcome') == 'completed'
                and done.get('id') == start['id']):
            import ledger_transaction
            from project import now
            staged = ledger_transaction.staged_close(root, start['id'], now(), done.get('summary', ''),
                                                     start['timestamp'])
        if staged:
            ledger_transaction.with_staged(root, staged[1], lambda staged_gate: staged_gate._check_done(deepcopy(done)))
        else:
            gate._check_done(deepcopy(done))
        strict = 'accepted'
    except ERRORS as exc:
        strict = f'refused: {exc}'
        observed = [row['observed'] for row in findings]
        if not all(any(part in text for text in observed) for part in str(exc).split('; ')):
            add('GATE_REFUSED', 'check-done', exc, 'Resolve this strict gate condition.')
    return report(findings, current_ref, done, strict)


def report(findings, current_ref, done, strict):
    ready = strict == 'accepted'
    if ready:
        # The strict gate is authoritative; any residual row is advisory only.
        for row in findings:
            row['status'] = 'advisory'
    return {'status': 'ready' if ready else 'blocked',
            'issue_id': done.get('id') if isinstance(done, dict) else None,
            'outcome': done.get('outcome') if isinstance(done, dict) else None,
            'unmet': sum(row['status'] == 'blocked' for row in findings),
            'findings': findings,
            'review_signature': signature_notice(done, current_ref),
            'strict_gate': strict,
            'note': 'Dry run only: nothing was written. --check-done remains the accepting gate.'}
