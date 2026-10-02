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
from pathlib import Path
import sys
import ledger_transaction
from project import STATE, atomic_json, digest, json_file, local, require


def prepare_done(root, packet, verification, metadata):
    import team_accounting
    start = json_file(root, STATE + '/issue-start.json')
    with team_accounting.phase(root, start['id'], 'closeout', role='arch'):
        return _prepare_done(root, start, packet, verification, metadata)


def _prepare_done(root, start, packet, verification, metadata):
    require(packet.get('id') == start['id'] and packet.get('timestamp') == start['timestamp'], 'packet must match the active iteration')
    allowed = {'summary', 'tests_status', 'milestone', 'lessons', 'lessons_na', 'rules_updated', 'rules_updated_na', 'git', 'communication'}
    require(isinstance(metadata, dict) and set(metadata) <= allowed, 'metadata has unsupported fields')
    require(len(str(metadata.get('summary', ''))) >= 40 and metadata.get('tests_status') in ('passing','failing','not_run'),
            'metadata needs a substantive summary and tests_status')
    require(isinstance(metadata.get('git'), dict) and isinstance(metadata.get('communication'), dict), 'record explicit Git and communication dispositions')
    done = dict(packet, **metadata, outcome='completed', state_version=start.get('state_version',1),
                iteration=start['iteration'], start_timestamp=start['timestamp'], open_issues_md_updated=False)
    done['verification'] = dict(packet.get('verification') or {}, final_owner=start['workflow']['final_verify_owner'])
    if start['workflow']['kind'] == 'scientific_change':
        require(verification.get('receipt') and verification.get('scientific'), 'supply the final_verification.py run result')
        done['verification'].update(receipt=verification['receipt'], scientific=verification['scientific'])
    import verify
    done['verification']['structural'] = verify.structural_evidence(root)
    done.setdefault('milestone', {'logged': False})
    atomic_json(root / STATE / 'issue-done.json', done)
    return {'status':'prepared', 'path': STATE + '/issue-done.json', 'accepted':False}


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
    sub.add_parser('rebind-receipt',help='bind the passing execution to issue-done.json (no suite run) and cite the receipt there')
    a=p.parse_args();root=a.root.resolve()
    try:
        if a.command=='promote':
            value=ledger_transaction.promote(root,'esx',a.issue,json_file(root,a.closure),a.expected_sha256,a.apply)
        elif a.command=='rebind-receipt':
            value=rebind_receipt(root)
        else:
            value=prepare_done(root,json_file(root,a.packet),json_file(root,a.verification),json_file(root,a.metadata))
        print(json.dumps(value,indent=2));return 0
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)}));return 1


if __name__=='__main__':
    raise SystemExit(main())
