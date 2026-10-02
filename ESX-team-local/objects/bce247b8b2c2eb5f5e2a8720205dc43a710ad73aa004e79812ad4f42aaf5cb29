"""Qualify one reviewed scientific candidate with one accountable run owner.

Preparation validates actual review completions, independent executed checks,
sealed documentation and exact source snapshots before a scientific suite starts.
Receipts bind these judgments to source, inputs, configuration and toolchain.
"""
import argparse
import fcntl
import json
from pathlib import Path
import sys

import doc_contract as maintenance
import issue_candidates
import verify
import workflow_policy as workflow
from project import STATE, atomic_json, config, digest, json_file, local, now, require, source_signature
from records import json_lines

# A lease is held by the same Python process throughout the owner-serialized run.
# Child verification programs receive no authority to launch another final suite.
_LEASES = {}


def active_start(root):
    path = local(root, f'{STATE}/issue-start.json')
    if not path.exists():
        return None
    start = json.loads(path.read_text())
    history = json_lines(local(root, f'{STATE}/loop_history.jsonl'))
    if history and (history[-1].get('id'), history[-1].get('timestamp')) == (start.get('id'), start.get('timestamp')):
        return None
    return start


def authorize(root, lease):
    """Permit standalone qualification or the prepared owner's in-process lease."""
    start = active_start(root)
    if not start:
        return
    require(lease in _LEASES, 'active issue scientific verification requires final_verification.py run after reviews and documentation are ready')
    review, owner, identity = _LEASES[lease]
    require(ready(root, review, owner) == identity, 'final verification lease is stale')


# Closeout fields bound into every receipt. Finalize all of them before taking
# the receipt: a later edit to any one makes check_receipt report it stale.
REVIEW_SIGNATURE_FIELDS = ('id', 'timestamp', 'workflow', 'workflow_amendment', 'scope_decisions',
                           'subagents', 'agent_continuity', 'review_supersessions', 'maintenance',
                           'map_delta', 'candidate', 'diagnosis_checkpoint')


def review_signature(review):
    return digest({key: review.get(key) for key in REVIEW_SIGNATURE_FIELDS})


def ready(root, review, owner):
    """Validate the candidate without requiring bookkeeping that follows success."""
    root = Path(root).resolve()
    start = json_file(root, f'{STATE}/issue-start.json')
    if start.get('state_version', 1) >= 2:
        import loop_iteration
        require(loop_iteration.start_status(root, start)['validated'], 'successful --check-start receipt required before final verification')
    from workflow_handoff import active_attempts
    active = active_attempts(root, start.get('id'))
    if active:
        raise ValueError('running retained assignments prevent final verification: ' + json.dumps(active))
    require((review.get('id'), review.get('timestamp')) == (start['id'], start['timestamp']), 'review packet must preserve issue and iteration timestamp')
    policy = review.get('workflow', {})
    errors = workflow.validate_workflow(policy)
    errors += workflow.validate_transition(start['workflow'], policy, review.get('workflow_amendment'))
    errors += workflow.validate_scope_decisions(review.get('scope_decisions', []), completed=True)
    require(not errors, '; '.join(errors))
    require(policy['kind'] == 'scientific_change', 'final scientific qualification requires scientific_change workflow')
    require(owner == policy['final_verify_owner'], 'only the assigned final verification owner may qualify this candidate')
    for field in ('verify_signature_at_start', 'numerical_signature_at_start'):
        require(policy[field] == start['workflow'][field], 'preserve measured initial workflow signatures')
    candidate = issue_candidates.check_current(root, review.get('candidate'), review['id'])
    require(candidate.get('baseline') == start['maintenance']['baseline'], 'candidate must preserve original maintenance baseline')
    if (review.get('preparation') or {}).get('pending'):
        raise ValueError('review packet still has pending preparation fields')
    records = json_lines(local(root, f'{STATE}/dispatch_log.jsonl'))
    history = json_lines(local(root, f'{STATE}/loop_history.jsonl'))
    subs = review.get('subagents') or {}
    require(isinstance(subs, dict), 'subagents must map roles to captured completions')
    selected = []
    used = set()
    agents = {}
    for role, entries in subs.items():
        require(role in workflow.ROLES and isinstance(entries, list), 'invalid role completion collection')
        agents[role] = set()
        for entry in entries:
            matches = [r for r in records if r.get('event_id') == entry.get('dispatch_event_id')
                       and r.get('agent_id') == entry.get('dispatch_id') and r.get('agent_type') == role]
            require(len(matches) == 1 and matches[0]['event_id'] not in used, f'{role}: missing or duplicated exact completion')
            event = matches[0]
            used.add(event['event_id'])
            selected.append(event)
            require(workflow.resolved_dispatch(event, records, review), f'{role}: failed or incomplete turn remains unresolved')
            if not workflow.completed(event):
                continue
            footer = event.get('footer') or {}
            require(footer.get('agent') == role and footer.get('issue_id') == review['id']
                    and workflow.known_completion_iteration(event, start, history), f'{role}: completion belongs to another role or iteration')
            agents[role].add(event['agent_id'])
    for role in policy['required_roles']:
        require(agents.get(role), f'missing required role: {role}')
    require(not agents.get('bob', set()) & agents.get('richard', set()), 'implementation and review require distinct identities')
    completed = dict(review, outcome='completed')
    signature = source_signature(root)
    errors = workflow.validate_reviews(completed, records, signature)
    errors += maintenance.check_done(root, start, completed, records, signature)
    require(not errors, '; '.join(errors))
    for event in selected:
        footer = event.get('footer') or {}
        if workflow.current_review(event, records, review, signature) and footer.get('verdict') in ('APPROVE', 'APPROVE_WITH_FIXES'):
            check = verify.load_evidence(root, footer.get('independent_check', {}).get('evidence'))
            require(check['owner'] == event['agent_id'] and check['started_at'] >= start['timestamp'], 'reviewer needs an independent check executed under its identity during this iteration')
    cfg = config(root)
    return {'version': 1, 'issue_id': review['id'], 'timestamp': start['timestamp'],
            'owner': owner, 'candidate': review['candidate'], 'review_signature': review_signature(review),
            'dispatch_signature': digest(selected),
            'scientific_fingerprint': verify.fingerprint(root, 'scientific', cfg['verification']['scientific'])}


def latest_attempt(root):
    """Return the most recent attempt reference and record, or (None, None)."""
    path = local(root, f'{STATE}/final-verification/latest.json')
    try:
        ref = json.loads(path.read_text())
        require(ref.get('path') == f"{STATE}/final-verification/{ref.get('sha256')}.json", 'invalid attempt path')
        record = json_file(root, ref['path'])
        require(digest(record) == ref['sha256'], 'attempt record was modified')
        return ref, record
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return None, None


def no_current_receipt(root, done):
    """Explain the absence of current.json from the latest recorded attempt."""
    ref, record = latest_attempt(root)
    if record is None:
        return 'no current final verification receipt and no readable recorded attempt; run final_verification.py run'
    status, log = record.get('status'), record.get('log') or 'not recorded'
    head = f"no current final verification receipt: the latest attempt {ref['path']} is {status} (log {log})"
    identity = record.get('identity') or {}
    if (identity.get('issue_id'), identity.get('timestamp')) != (done.get('id'), done.get('timestamp')):
        head += ' and belongs to another iteration'
    if status == 'INTERRUPTED':
        failures = record.get('failure_lines')
        verdict = ('no test failed before the interruption' if failures == 0 else
                   f'{failures} failure lines were logged before the interruption' if failures else
                   'the suite reached no verdict')
        return f"{head}; the run was interrupted ({record.get('error')}), {verdict}; re-run final_verification.py run"
    if status == 'SOURCE_CHANGED':
        return f"{head}; source or review changed during the run, so it reached no verdict on the candidate; re-run after edits finish"
    if status == 'FAILED':
        return f"{head}; the scientific suite reported a failure ({record.get('error')}); inspect the log"
    return f'{head}; a later attempt cleared the current receipt; re-run final_verification.py run'


def attempt_status(exc):
    if isinstance(exc, (KeyboardInterrupt, InterruptedError, verify.RunInterrupted)):
        return 'INTERRUPTED'
    if isinstance(exc, verify.SourceChanged):
        return 'SOURCE_CHANGED'
    return 'FAILED'


def check_receipt(root, done):
    """Require one intact, successful qualification of the exact reviewed candidate."""
    ref = (done.get('verification') or {}).get('receipt')
    require(isinstance(ref, dict), 'final scientific verification receipt is required')
    sha = ref.get('sha256')
    require(ref.get('path') == f'{STATE}/final-verification/{sha}.json', 'invalid final verification receipt path')
    if not local(root, f'{STATE}/final-verification/current.json').exists():
        raise ValueError(no_current_receipt(root, done))
    require(json_file(root, f'{STATE}/final-verification/current.json') == ref, 'final verification receipt was invalidated by a later attempt')
    record = json_file(root, ref['path'])
    require(digest(record) == sha, 'final verification receipt was modified')
    require(record.get('status') == 'PASS', 'final verification receipt did not pass')
    owner = done['workflow']['final_verify_owner']
    require(record.get('identity') == ready(root, done, owner), 'final verification receipt is stale')
    evidence = verify.load_evidence(root, record.get('scientific'))
    require(evidence['suite'] == 'scientific' and evidence['owner'] == owner, 'scientific evidence belongs to a different suite or owner')
    require(evidence['commands'] == config(root)['verification']['scientific'], 'scientific evidence omits configured commands')
    require((done.get('verification') or {}).get('scientific') == record['scientific'], 'closeout scientific evidence differs from its receipt')
    return record


def _reissue(root, review, owner, identity, index):
    """Issue a receipt for ``review`` from the current receipt's unchanged execution.

    Never executes the suite. Raises when the source, configuration, toolchain,
    owner or commands of the earlier execution no longer match.
    """
    old_ref = json.loads(index.read_text())
    require(old_ref.get('path') == f"{STATE}/final-verification/{old_ref.get('sha256')}.json", 'invalid prior receipt path')
    old = json_file(root, old_ref['path'])
    require(digest(old) == old_ref['sha256'] and old.get('status') == 'PASS', 'invalid prior receipt')
    require(all(old['identity'].get(k) == identity.get(k) for k in
        ('issue_id', 'owner', 'scientific_fingerprint')), 'execution dependencies changed')
    evidence = verify.load_evidence(root, old['scientific'])
    require(evidence['suite'] == 'scientific' and evidence['owner'] == owner, 'wrong execution owner')
    require(evidence['commands'] == config(root)['verification']['scientific'], 'commands changed')
    require(identity == ready(root, review, owner), 'acceptance changed during reuse')
    record = {'version': 1, 'status': 'PASS', 'identity': identity,
              'scientific': old['scientific'], 'execution_receipt': old_ref,
              'executed': False, 'finished_at': now()}
    sha = digest(record)
    ref = {'path': f'{STATE}/final-verification/{sha}.json', 'sha256': sha}
    atomic_json(local(root, ref['path']), record)
    atomic_json(index, ref)
    atomic_json(local(root, f'{STATE}/final-verification/latest.json'), ref)
    return {'status': 'REUSED EVIDENCE', 'receipt': ref, 'scientific': old['scientific']}


def rebind(root, review, owner):
    """Bind the current passing execution to ``review`` without running the suite.

    ``review`` is normally the prepared closeout (issue-done.json): the review
    packet does not carry agent_continuity, scope_decisions or the other
    closeout fields that review_signature covers, so a receipt taken from the
    packet goes stale as soon as those fields are filled. Raises ValueError
    when the execution cannot be reused; a fresh `run` is then required.
    """
    root = Path(root).resolve()
    lock = local(root, f'{STATE}/final-verification/owner.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        index = local(root, f'{STATE}/final-verification/current.json')
        require(index.exists(), 'no current final verification receipt to rebind; run final_verification.py run first')
        identity = ready(root, review, owner)
        try:
            return _reissue(root, review, owner, identity, index)
        except (OSError, KeyError, TypeError) as exc:
            raise ValueError('cannot reuse the current execution: ' + str(exc)) from exc


def run(root, review, owner, fresh=False):
    """Serialize final runs and rebind unchanged execution to current acceptance."""
    root = Path(root).resolve()
    lock = local(root, f'{STATE}/final-verification/owner.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        identity = ready(root, review, owner)
        index = local(root, f'{STATE}/final-verification/current.json')
        if not fresh and index.exists():
            try:
                old_ref = json.loads(index.read_text())
                packet = dict(review, verification={'receipt': old_ref, 'scientific': json_file(root, old_ref['path']).get('scientific')})
                old = check_receipt(root, packet)
                return {'status': 'REUSED EVIDENCE', 'receipt': old_ref, 'scientific': old['scientific']}
            except (ValueError, OSError, KeyError, TypeError):
                pass
            # Separate fresh acceptance from the immutable scientific execution.
            # Reuse requires current approvals and matching source/config/toolchain.
            try:
                return _reissue(root, review, owner, identity, index)
            except (ValueError, OSError, KeyError, TypeError):
                pass
        index.unlink(missing_ok=True)
        token = object()
        _LEASES[token] = (review, owner, identity)
        try:
            # A new approved identity receives a fresh scientific run. Only the
            # wrapper's intact exact-state receipt permits final result reuse.
            result = verify.run(root, 'scientific', owner, fresh=True, _lease=token)
            log = json_file(root, result['evidence']['path'])['log']
            try:
                after = ready(root, review, owner)
            except ValueError as exc:
                raise verify.SourceChanged(f'candidate no longer ready after final scientific verification: {exc}', log) from exc
            if identity != after:
                raise verify.SourceChanged('source or review changed during final scientific verification', log)
            record = {'version': 1, 'status': 'PASS', 'identity': identity,
                      'scientific': result['evidence'], 'finished_at': now()}
        except BaseException as exc:
            failure = {'version': 1, 'status': attempt_status(exc), 'identity': identity,
                       'error': type(exc).__name__ + ': ' + str(exc), 'finished_at': now()}
            log = getattr(exc, 'log', None)
            if log:
                failure['log'] = log
                try:
                    failure['failure_lines'] = verify.failure_lines(local(root, log).read_text(errors='replace'))
                except OSError:
                    pass
            sha = digest(failure)
            atomic_json(local(root, f'{STATE}/final-verification/{sha}.json'), failure)
            atomic_json(local(root, f'{STATE}/final-verification/latest.json'),
                        {'path': f'{STATE}/final-verification/{sha}.json', 'sha256': sha})
            raise
        finally:
            _LEASES.pop(token, None)
        sha = digest(record)
        ref = {'path': f'{STATE}/final-verification/{sha}.json', 'sha256': sha}
        atomic_json(local(root, ref['path']), record)
        atomic_json(index, ref)
        atomic_json(local(root, f'{STATE}/final-verification/latest.json'), ref)
        return {'status': 'EXECUTED PASS', 'receipt': ref, 'scientific': result['evidence']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('action', choices=('check', 'run'))
    parser.add_argument('--review', required=True, help='read-only prepared review JSON; absolute paths accepted')
    parser.add_argument('--owner', required=True)
    parser.add_argument('--fresh', action='store_true')
    args = parser.parse_args()
    try:
        from workflow_handoff import input_file
        review = json.loads(input_file(args.root, args.review).read_text())
        result = ready(args.root, review, args.owner) if args.action == 'check' else run(args.root, review, args.owner, args.fresh)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, KeyError, TypeError, InterruptedError) as exc:
        parser.exit(1, f'ESX final verification: {exc}\n')


if __name__ == '__main__':
    # verify.py's lazy `import final_verification` must resolve to this running
    # module. Executed as a script this module is registered as '__main__', so a
    # plain import would build a second instance with its own empty _LEASES and
    # authorize() would refuse every lease this process just granted.
    sys.modules.setdefault('final_verification', sys.modules['__main__'])
    main()
