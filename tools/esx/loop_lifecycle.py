#!/usr/bin/env python3
"""Explicit closeout preparation and recoverable scientific issue promotion.

Preparation copies the reviewed packet and guarded receipt; mandatory judgments
come from metadata. It creates an unaccepted draft and leaves the open entry in
open_issues.md: loop_gate.py --check-done moves it to closed_issues.md only on
acceptance. Promotion (optional) stages a curated closed entry through the full gate.
rebind-receipt re-points a prepared closeout at a later matching final receipt.
"""
import argparse
import json
import re
from pathlib import Path
import sys
import ledger_transaction
import workflow_policy as workflow
from project import STATE, atomic_json, digest, json_file, local, require
from records import json_lines


def prepare_done(root, packet, verification, metadata):
    import team_accounting
    start = json_file(root, STATE + '/issue-start.json')
    with team_accounting.phase(root, start['id'], 'closeout', role='arch'):
        return _prepare_done(root, start, packet, verification, metadata)


METADATA_FIELDS = ('summary', 'tests_status', 'milestone', 'lessons', 'lessons_na', 'rules_updated',
                   'rules_updated_na', 'git', 'communication')
TESTS_STATUS = ('passing', 'failing', 'not_run')


def metadata_problems(metadata):
    """Every shape problem in closeout metadata, in one pass.

    These checks used to run one `require` at a time, and several shapes were
    enforced only later by --check-done, so a closer learned them one refusal at
    a time. On RUNOFF-042: unsupported fields, then `tests_status` (an enum the
    message did not name), then -- at --check-done -- `lessons` (a list of
    lesson ids: a string is iterated as characters), `git.committed` (a
    boolean) and `milestone.logged` (esx-fix.md E). Each message states the
    shape required, so the next attempt can be right.
    """
    if not isinstance(metadata, dict):
        return ['metadata must be a JSON object']
    problems = []
    unknown = sorted(set(metadata) - set(METADATA_FIELDS))
    if unknown:
        problems.append(f'unsupported field(s) {unknown}; allowed: {list(METADATA_FIELDS)}')
    if len(str(metadata.get('summary', ''))) < 40:
        problems.append('summary must be a substantive explanation of at least 40 characters')
    if metadata.get('tests_status') not in TESTS_STATUS:
        problems.append(f'tests_status must be one of {list(TESTS_STATUS)}, not {metadata.get("tests_status")!r}')
    lessons = metadata.get('lessons', [])
    if not (isinstance(lessons, list) and all(isinstance(x, str) and re.fullmatch(r'LL-\d+', x) for x in lessons)):
        problems.append('lessons must be a list of registered lesson ids such as ["LL-019"]; put prose in summary')
    git = metadata.get('git')
    if not isinstance(git, dict) or type(git.get('committed')) is not bool:
        problems.append('git must be an object with a boolean "committed", plus "sha" when committed or a "reason" '
                        'of at least 20 characters when not')
    elif git['committed'] and not re.fullmatch(r'[0-9a-fA-F]{7,40}', str(git.get('sha', ''))):
        problems.append('git.sha must be the 7-40 hex digit commit when git.committed is true')
    elif not git['committed'] and len(str(git.get('reason', '')).strip()) < 20:
        problems.append('git.reason must explain the uncommitted disposition in at least 20 characters')
    if not isinstance(metadata.get('communication'), dict):
        problems.append('communication must be an object recording the delivery result or non-delivery reason')
    if 'milestone' in metadata:
        milestone = metadata['milestone']
        if not isinstance(milestone, dict) or type(milestone.get('logged')) is not bool:
            problems.append('milestone must be an object with a boolean "logged", and when logged a "reference" '
                            'of {path, heading, sha256} from workflow_records.milestone_reference')
    return problems


def _prepare_done(root, start, packet, verification, metadata):
    require(packet.get('id') == start['id'] and packet.get('timestamp') == start['timestamp'], 'packet must match the active iteration')
    problems = metadata_problems(metadata)
    require(not problems, f'closeout metadata has {len(problems)} problem(s): ' + '; '.join(problems))
    done = dict(packet, **metadata, outcome='completed', state_version=start.get('state_version',1),
                iteration=start['iteration'], start_timestamp=start['timestamp'], open_issues_md_updated=False)
    done['verification'] = dict(packet.get('verification') or {}, final_owner=start['workflow']['final_verify_owner'])
    if start['workflow']['kind'] == 'scientific_change':
        require(verification.get('receipt') and verification.get('scientific'), 'supply the final_verification.py run result')
        done['verification'].update(receipt=verification['receipt'], scientific=verification['scientific'])
    import verify
    done['verification']['structural'] = verify.structural_evidence(root)
    done.setdefault('milestone', {'logged': False})
    # The gate requires agent_continuity.<role> to list exactly the dispatch_ids in
    # subagents.<role>; a packet that lacks the lists would be refused for it.
    if isinstance(done.get('agent_continuity', {}), dict) and isinstance(done.get('subagents'), dict):
        for role in ('bob', 'richard'):
            ids = list(dict.fromkeys(e['dispatch_id'] for e in done['subagents'].get(role, [])
                                     if isinstance(e, dict) and e.get('dispatch_id')))
            if ids and role not in done.get('agent_continuity', {}):
                done.setdefault('agent_continuity', {})[role] = ids
    atomic_json(root / STATE / 'issue-done.json', done)
    return {'status':'prepared', 'path': STATE + '/issue-done.json', 'accepted':False}


def edit_done(root, change):
    """Apply ``change(start, done, records)`` to issue-done.json through the atomic writer.

    The helpers below exist so a closeout record is never hand-edited as JSON; each
    validates with the rules closeout_doctor and the strict gate apply, and prints
    the entry it wrote.
    """
    start = json_file(root, STATE + '/issue-start.json')
    done = json_file(root, STATE + '/issue-done.json')
    require((done.get('id'), done.get('timestamp')) == (start.get('id'), start.get('timestamp')),
            'the closeout draft belongs to another iteration; run prepare-done first')
    require(isinstance(done.get('agent_continuity', {}), dict), 'agent_continuity must be an object')
    entry = change(start, done, json_lines(local(root, STATE + '/dispatch_log.jsonl')))
    atomic_json(root / STATE / 'issue-done.json', done)
    return entry


def add_replacement(root, role, old_id, new_id, reason, evidence_refs):
    """Record why a runtime identity was replaced (agent_continuity.replacements)."""
    import workflow_records

    def change(start, done, records):
        require(role in ('bob', 'richard'), 'replacements are recorded for bob or richard')
        require(isinstance(reason, str) and len(reason.strip()) >= 20, 'the replacement reason needs at least 20 characters')
        require(evidence_refs and all(isinstance(ref, str) and ref.strip() for ref in evidence_refs),
                'give at least one --evidence-ref (a project-relative path)')
        for ref in evidence_refs:
            workflow_records.local_file(root, ref)
        ids = {e.get('dispatch_id') for e in (done.get('subagents') or {}).get(role, []) if isinstance(e, dict)}
        require(old_id in ids, f'{old_id} is not among subagents.{role}; the gate resolves the old identity there')
        require(old_id != new_id, 'old_id and new_id must differ')
        require(new_id in ids or any(r.get('agent_type') == role and r.get('agent_id') == new_id
                                     and workflow.identity(r, 'issue_id') == done.get('id') for r in records),
                f'{new_id} was never dispatched as {role} for {done.get("id")} (dispatch_log.jsonl)')
        replacements = done.setdefault('agent_continuity', {}).setdefault('replacements', [])
        require(isinstance(replacements, list), 'agent_continuity.replacements must be a list')
        entry = {'role': role, 'old_id': old_id, 'new_id': new_id, 'reason': reason.strip(), 'evidence_refs': list(evidence_refs)}
        # Complete the entry prepare-done drafted for this identity rather than duplicate it.
        for index, existing in enumerate(replacements):
            if (isinstance(existing, dict) and existing.get('role') == role and existing.get('old_id') == old_id
                    and existing.get('new_id') in (new_id, None, '')):
                replacements[index] = {**existing, **entry}
                return replacements[index]
        replacements.append(entry)
        return entry
    return edit_done(root, change)


def add_parallel(root, role, agent_id, reason):
    """Declare a deliberate parallel reviewer (agent_continuity.parallel), not a replacement."""
    def change(start, done, records):
        require(role in ('bob', 'richard'), 'a parallel identity is recorded for bob or richard')
        entry = {'role': role, 'id': agent_id, 'reason': reason.strip() if isinstance(reason, str) else reason}
        errors = workflow.validate_parallel({'parallel': [entry]})
        require(not errors, '; '.join(errors))
        require(workflow.dispatched_in_iteration(records, role, agent_id, done.get('id'), done.get('timestamp')),
                f'{agent_id} was never dispatched as {role} for {done.get("id")} in this iteration (dispatch_log.jsonl); '
                'a declaration alone does not explain a second identity')
        parallel = done.setdefault('agent_continuity', {}).setdefault('parallel', [])
        require(isinstance(parallel, list), 'agent_continuity.parallel must be a list')
        done['agent_continuity']['parallel'] = [e for e in parallel if not (
            isinstance(e, dict) and (e.get('role'), e.get('id')) == (role, agent_id))] + [entry]
        return entry
    return edit_done(root, change)


def amend_kind(root, kind, reason):
    """Amend the workflow kind, recording workflow_amendment.previous (the start workflow) and the reason."""
    def change(start, done, records):
        require(kind in workflow.KINDS, f'kind must be one of {workflow.KINDS}')
        require(isinstance(reason, str) and reason.strip(), 'a reason for the amendment is required')
        previous = start['workflow']
        current = done.get('workflow') or previous
        amendment = {'previous': previous, 'reason': reason.strip()}
        require(current.get('kind') != kind or workflow.validate_transition(previous, current, done.get('workflow_amendment')),
                f'the closeout workflow is already {kind} and its transition is recorded')
        new = json.loads(json.dumps(current))
        new['kind'] = kind
        if kind == 'scientific_change':
            new['required_roles'] = list(new.get('required_roles', [])) + [
                r for r in ('bob', 'richard') if r not in new.get('required_roles', [])]
            new['minimum_reviewers'] = max(1, new.get('minimum_reviewers') or 0)
        errors = workflow.validate_workflow(new) + workflow.validate_transition(previous, new, amendment)
        require(not errors, '; '.join(errors))
        done['workflow'] = new
        if new == previous:
            done.pop('workflow_amendment', None)  # restored to the start workflow: nothing to amend
            return {'workflow': new, 'workflow_amendment': None}
        done['workflow_amendment'] = amendment
        return {'workflow': new, 'workflow_amendment': {'previous_kind': previous.get('kind'), 'reason': amendment['reason']}}
    return edit_done(root, change)


def rebind_receipt(root):
    """Bind the passing final execution to the prepared closeout and cite it there.

    One command for the usual case: the receipt was taken from the review packet,
    and the closeout fields that review_signature covers (scope_decisions,
    agent_continuity, maintenance and the others) were filled afterwards. When
    current.json was issued for a different review signature, a receipt for the
    closeout's own signature is issued from the unchanged execution, without
    running the suite, and issue-done.json is pointed at it. Refuses when the
    execution cannot be reused; the rebound record must pass the receipt check.
    """
    import final_verification
    path = root / STATE / 'issue-done.json'
    done = json_file(root, STATE + '/issue-done.json')
    old = (done.get('verification') or {}).get('receipt')
    require(isinstance(old, dict), 'no prepared closeout receipt to re-bind; run prepare-done first')
    if not local(root, STATE + '/final-verification/current.json').exists():
        raise ValueError(final_verification.no_current_receipt(root, done))
    ref = json_file(root, STATE + '/final-verification/current.json')
    require(ref.get('path') == f"{STATE}/final-verification/{ref.get('sha256')}.json", 'invalid current receipt path')
    record = json_file(root, ref['path'])
    require(digest(record) == ref['sha256'], 'current final verification receipt was modified')
    require(record.get('status') == 'PASS', 'current final verification receipt did not pass')
    recorded, expected = (record.get('identity') or {}).get('review_signature'), final_verification.review_signature(done)
    reissued = False
    if recorded != expected:
        owner = (done.get('verification') or {}).get('final_owner') or (done.get('workflow') or {}).get('final_verify_owner')
        require(owner, 'the closeout names no final verification owner (verification.final_owner or '
                       'workflow.final_verify_owner); it is needed to rebind the receipt')
        try:
            final_verification.rebind(root, done, owner)
        except ValueError as exc:
            raise ValueError(f'current receipt review_signature {recorded} does not match the closeout record {expected}, '
                             f'and the execution could not be rebound to the closeout: {exc}') from exc
        ref = json_file(root, STATE + '/final-verification/current.json')
        record = json_file(root, ref['path'])
        require((record.get('identity') or {}).get('review_signature') == expected, 'rebound receipt does not match the closeout record')
        reissued = True
    rebound = dict(done, verification=dict(done['verification'], receipt=ref, scientific=record['scientific']))
    final_verification.check_receipt(root, rebound)
    atomic_json(path, rebound)
    return {'status': 'rebound', 'path': STATE + '/issue-done.json', 'previous': old, 'receipt': ref,
            'reissued': reissued, 'executed': False, 'accepted': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    sub=p.add_subparsers(dest='command',required=True)
    done=sub.add_parser('prepare-done')
    for name in ('packet','verification','metadata'):
        done.add_argument('--'+name,required=True)
    promote=sub.add_parser('promote')
    for name in ('issue','closure','expected-sha256'):
        promote.add_argument('--'+name,required=True)
    promote.add_argument('--apply',action='store_true')
    replace=sub.add_parser('add-replacement',help='record why a runtime identity was replaced (agent_continuity.replacements)')
    replace.add_argument('--role',required=True,choices=('bob','richard'))
    replace.add_argument('--old-id',required=True)
    replace.add_argument('--new-id',required=True)
    replace.add_argument('--reason',required=True,help='at least 20 characters')
    replace.add_argument('--evidence-ref',required=True,action='append',help='project-relative path; repeat for more')
    parallel=sub.add_parser('add-parallel',help='declare a deliberate parallel reviewer (agent_continuity.parallel); it must appear in the dispatch log for this iteration')
    parallel.add_argument('--role',required=True,choices=('bob','richard'))
    parallel.add_argument('--id',required=True)
    parallel.add_argument('--reason',required=True,help='at least 20 characters')
    amend=sub.add_parser('amend-kind',help='amend the closeout workflow kind with workflow_amendment.previous and its reason')
    amend.add_argument('--kind',required=True,choices=workflow.KINDS)
    amend.add_argument('--reason',required=True)
    sub.add_parser('rebind-receipt',help='bind the passing execution to issue-done.json (no suite run) and cite the receipt there')
    a=p.parse_args();root=a.root.resolve()
    try:
        if a.command=='promote':
            value=ledger_transaction.promote(root,'esx',a.issue,json_file(root,a.closure),a.expected_sha256,a.apply)
        elif a.command=='rebind-receipt':
            value=rebind_receipt(root)
        elif a.command=='add-replacement':
            value=add_replacement(root,a.role,a.old_id,a.new_id,a.reason,a.evidence_ref)
        elif a.command=='add-parallel':
            value=add_parallel(root,a.role,a.id,a.reason)
        elif a.command=='amend-kind':
            value=amend_kind(root,a.kind,a.reason)
        else:
            value=prepare_done(root,json_file(root,a.packet),json_file(root,a.verification),json_file(root,a.metadata))
        print(json.dumps(value,indent=2));return 0
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)}));return 1


if __name__=='__main__':
    raise SystemExit(main())
