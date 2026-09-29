"""Disk-backed ESX issue loop: selection, preparation, evidence and closeout.

The coordinator supplies scientific judgments; this gate checks their records,
current source, captured agent completions and executed verification evidence.
Successful closeout saves history. It never commits or sends external messages.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys

import audit
import notifications
import doc_contract as maintenance
import workflow_policy as workflow
import verify
import workflow_records
import loop_iteration
import team_retrospective
import team_budget
import team_accounting
from project import (STATE, ROLES, atomic_json, config, json_file, local, now,
                     require, source_signature)
from records import json_lines, save_history, validate_records

PROMISE = 'ESX-LOOP-NO-ACTIONABLE-WORK'
SELF_ASSESSMENT_WINDOW = 10


def announcement(record):
    ts = record.get('slack_ts')
    if ts is not None:
        require(isinstance(ts, str) and re.fullmatch(r'\d{10}\.\d{6}', ts), 'invalid returned Slack timestamp')
    else:
        communication = record.get('communication')
        require(bool(record.get('slack_error')) or isinstance(communication, dict)
                and communication.get('status') in ('pending', 'sent', 'unavailable', 'unauthorized', 'disabled')
                and bool(communication.get('detail')), 'record the communication result or non-delivery reason')
        if isinstance(communication, dict) and communication.get('status') == 'sent':
            require(communication.get('receipt'), 'successful communication needs its returned receipt/link')


class Gate:
    def __init__(self, root, ledger_overrides=None):
        self.ledger_overrides = ledger_overrides
        self.root = Path(root).resolve()
        self.cfg = config(self.root)

    def read(self, name):
        return json_file(self.root, f'{STATE}/{name}')

    def prepare(self, issue, kind, risks, owner, priority, map_ref, targets, docs, use, diagnosis=None, budget_kind=None):
        team_retrospective.require_clear(self.root)
        team_retrospective.require_followup(self.root)
        audit.check(self.root, self.ledger_overrides)
        opened, _, _ = validate_records(self.root, self.ledger_overrides)
        require(issue in opened and opened[issue]['state'] != 'blocked', 'select an actionable open issue')
        require(opened[issue]['anchors'], 'file source/test anchors in the issue before preparing work')
        hist = json_lines(local(self.root, f'{STATE}/loop_history.jsonl'))
        state = local(self.root, f'{STATE}/issue-start.json')
        if state.exists():
            old = json.loads(state.read_text())
            hist = json_lines(local(self.root, f'{STATE}/loop_history.jsonl'))
            require(hist and (hist[-1]['id'], hist[-1]['timestamp']) == (old['id'], old['timestamp']),
                    'finish the active iteration before preparing another')
        base = maintenance.baseline(self.root, issue)
        nav = maintenance.navigate(self.root, issue, base, 'arch', map_ref, targets, docs, use)
        policy = workflow.default_workflow(kind, source_signature(self.root), risks,
                                           source_signature(self.root, scientific=True))
        first = next((row for row in hist if row.get('id') == issue), None)
        if first:
            for key in ('verify_signature_at_start', 'numerical_signature_at_start'):
                policy[key] = first['workflow'][key]
        policy['final_verify_owner'] = owner
        require(priority and priority.strip(), 'record the selection reason')
        start = {'state_version': 2, 'budget': team_budget.limits(budget_kind or kind), 'id': issue, 'title': opened[issue]['title'], 'timestamp': now(),
                 'priority_reason': priority, 'workflow': policy,
                 'iteration': 1 + sum(row.get('id') == issue for row in hist),
                 'maintenance': {'baseline': base, 'orientation': nav},
                 'communication': {'status': 'pending', 'detail': 'Arch will record authorized delivery or its disposition.'}}
        if diagnosis is not None:
            start['diagnosis_checkpoint'] = diagnosis
        self.check_diagnosis(start, hist)
        require(not workflow.validate_workflow(policy), 'invalid workflow decision')
        previous_done = local(self.root, f'{STATE}/issue-done.json')
        if previous_done.exists():
            from project import file_hash
            archived = local(self.root, f'{STATE}/closed/issue-done-{file_hash(previous_done)}.json')
            if not archived.exists():
                from project import atomic_bytes
                atomic_bytes(archived, previous_done.read_bytes())
            previous_done.unlink()
        atomic_json(state, start)
        return start

    def check_start(self):
        with team_accounting.phase(self.root, self.read('issue-start.json')['id'], 'orientation', role='arch'):
            return self._check_start()

    def _check_start(self):
        team_retrospective.require_clear(self.root)
        team_retrospective.require_followup(self.root)
        start = self.read('issue-start.json')
        opened, _, _ = validate_records(self.root, self.ledger_overrides)
        require(start['id'] in opened and opened[start['id']]['state'] != 'blocked', 'start issue is not selectable')
        self.check_diagnosis(start, json_lines(local(self.root, f'{STATE}/loop_history.jsonl')))
        errors = workflow.validate_workflow(start['workflow']) + maintenance.check_start(self.root, start)
        require(not errors, '; '.join(errors))
        maintenance.validate_orientation(self.root, start['maintenance']['orientation'], start['id'],
                                         start['maintenance']['baseline'], 'arch')
        announcement(start)
        notifications.synchronize(self.root)
        require(not notifications.pending(self.root), notifications.notice(self.root) or 'pending communication')
        loop_iteration.record_start(self.root, start)
        return start

    def check_diagnosis(self, start, history):
        """Require a reproduced premise decision after two failed correction rounds."""
        if start.get('workflow', {}).get('execution_version') != 1:
            return
        earlier = [row for row in history if (row.get('id'), row.get('timestamp')) != (start.get('id'), start.get('timestamp'))]
        rounds = workflow_records.rejected_correction_rounds(earlier, start['id'])
        if len(rounds) >= 2:
            errors = workflow_records.validate_checkpoint(self.root, start.get('diagnosis_checkpoint'), start['id'], max(rounds))
            require(not errors, '; '.join(errors))

    def check_done(self):
        """Validate the closeout; accepting completed work moves its open entry.

        The ledger move is a consequence of acceptance, never a precondition:
        the staged move must pass this gate before either ledger is written.
        """
        start = self.read('issue-start.json')
        moved, accepted_at = None, now()
        if self.ledger_overrides is None:
            draft = self.read('issue-done.json')
            if draft.get('outcome') == 'completed' and draft.get('id') == start['id']:
                import ledger_transaction
                moved = ledger_transaction.close_on_acceptance(self.root, start['id'], accepted_at,
                                                               draft.get('summary', ''), start['timestamp'])
        try:
            with team_accounting.phase(self.root, start['id'], 'closeout', role='arch'):
                done = self._check_done()
        except BaseException:
            if moved:
                import ledger_transaction
                ledger_transaction.revert(self.root, *moved)
            raise
        if done['outcome'] == 'completed':
            done['open_issues_md_updated'] = True
        if moved:
            done['closed_at'] = accepted_at
        return done

    def _check_done(self, done=None):
        """Validate complete, partial or blocked work without manufacturing PASS.

        Completed work requires configured final checks and sealed documentation.
        Partial/blocked work retains observations and a concrete next step. Every
        claimed agent completion is correlated to its actual hook-captured footer.
        """
        audit.check(self.root, self.ledger_overrides)
        start = self.read('issue-start.json')
        done = self.read('issue-done.json') if done is None else done
        require((done.get('id'), done.get('timestamp')) == (start['id'], start['timestamp']),
                'done must preserve start id and iteration timestamp')
        done['start_validation'] = loop_iteration.start_status(self.root, start)
        if start.get('state_version', 1) >= 2 or done.get('state_version', 1) >= 2:
            require(loop_iteration.matches(start, done), 'closeout must preserve exact iteration identity')
            require(done['start_validation']['validated'], 'successful --check-start receipt required for this iteration')
        require(done.get('outcome') in ('completed', 'partial', 'blocked') and done.get('summary'), 'record outcome and summary')
        errors = workflow.validate_workflow(start['workflow']) + workflow.validate_workflow(done.get('workflow', {}))
        errors += workflow.validate_transition(start['workflow'], done.get('workflow'), done.get('workflow_amendment'))
        errors += workflow.validate_scope_decisions(done.get('scope_decisions', []), done['outcome'] == 'completed')
        errors += maintenance.check_start(self.root, start)
        require(not errors, '; '.join(errors))
        self.check_diagnosis(start, json_lines(local(self.root, f'{STATE}/loop_history.jsonl')))
        require((done.get('maintenance') or {}).get('baseline') == start['maintenance']['baseline'], 'completion must preserve original maintenance baseline')
        policy = done['workflow']
        for key in ('verify_signature_at_start', 'numerical_signature_at_start'):
            require(policy[key] == start['workflow'][key], 'workflow amendment must preserve measured initial signatures')
        opened, closed, lessons = validate_records(self.root, self.ledger_overrides)
        if done['outcome'] == 'completed':
            require(done['id'] in closed and done['id'] not in opened, 'completed issue must be in closed_issues.md')
            if source_signature(self.root, scientific=True) != policy['numerical_signature_at_start']:
                require(policy['kind'] == 'scientific_change', 'scientific source/tests/configuration changed: amend workflow kind')
        else:
            require(done['id'] in opened and done.get('next_step'), 'incomplete work needs its open entry and next_step')
            if done['outcome'] == 'blocked':
                require(opened[done['id']]['state'] == 'blocked' and done.get('blocked_by') == opened[done['id']]['blocker'], 'record the exact open-entry blocker')
        require(set(done.get('lessons', [])).issubset(lessons), 'claimed lesson is missing from index/evidence')
        announcement(done)
        require(not done.get('slack_ts') or done.get('slack_ts') != start.get('slack_ts'), 'start and done need distinct Slack receipts')
        git = done.get('git')
        require(isinstance(git, dict) and type(git.get('committed')) is bool, 'record git.committed and SHA or reason')
        if git['committed']:
            sha = git.get('sha', '')
            require(isinstance(sha, str) and re.fullmatch(r'[0-9a-fA-F]{7,40}', sha), 'record a Git commit SHA')
            result = subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'HEAD'], cwd=self.root, capture_output=True)
            require(result.returncode == 0, 'recorded commit does not exist in this repository')
        else:
            require(isinstance(git.get('reason'), str) and len(git['reason'].strip()) >= 20, 'explain the uncommitted disposition')
        records = json_lines(local(self.root, f'{STATE}/dispatch_log.jsonl'))
        history = json_lines(local(self.root, f'{STATE}/loop_history.jsonl'))
        subs = done.get('subagents', {})
        require(isinstance(subs, dict) and set(subs).issubset(ROLES[1:]), 'subagents must map known roles to completion arrays')
        used, agents = set(), {}
        for role, entries in subs.items():
            require(isinstance(entries, list), f'{role}: completions must be a list')
            agents[role] = set()
            for entry in entries:
                matches = [r for r in records if r.get('event_id') == entry.get('dispatch_event_id')
                           and r.get('agent_id') == entry.get('dispatch_id') and r.get('agent_type') == role]
                require(len(matches) == 1 and matches[0]['event_id'] not in used, f'{role}: missing or duplicated exact completion')
                event = matches[0]
                used.add(event['event_id'])
                agents[role].add(event['agent_id'])
                if not workflow.completed(event):
                    if done['outcome'] == 'completed':
                        require(workflow.resolved_dispatch(event, records, done), f'{role}: failed or incomplete turn remains unresolved')
                    else:
                        require(entry.get('status') == event.get('status'), f'{role}: preserve the failed turn status')
                    continue
                footer = event.get('footer')
                require(isinstance(footer, dict) and footer.get('agent') == role and footer.get('issue_id') == done['id']
                        and workflow.known_completion_iteration(event, start, history), f'{role}: footer belongs to another role/iteration')
                for key in ('verdict', 'must_fix', 'independent_check', 'orientation', 'candidate_signature', 'documentation_review'):
                    if key in entry:
                        require(entry[key] == footer.get(key), f'{role}: copied {key} differs from captured footer')
                maintenance.validate_orientation(self.root, footer.get('orientation'), done['id'],
                                                 start['maintenance']['baseline'], role, fresh=False)
        continuity = done.get('agent_continuity', {})
        require(isinstance(continuity, dict), 'agent_continuity must be an object')
        for role in ('bob', 'richard'):
            if agents.get(role):
                assignment = continuity.get(role, [])
                require(isinstance(assignment, list) and set(assignment) == agents[role],
                        f'record stable {role} runtime identities: agent_continuity.{role} must list exactly the '
                        f'dispatch_ids already in subagents.{role}, originals first: {sorted(agents[role])}')
                initial_count = 1 if role == 'bob' else max(1, policy['minimum_reviewers'])
                for replacement_id in assignment[initial_count:]:
                    require(any(isinstance(r, dict) and r.get('role') == role
                                and r.get('new_id') == replacement_id and r.get('old_id') in agents[role]
                                and r.get('old_id') != replacement_id and r.get('reason')
                                for r in continuity.get('replacements', [])), f'{role}: explain each replacement runtime identity')
        require(not agents.get('bob', set()) & agents.get('richard', set()), 'implementation and review require distinct runtime identities')
        failed = continuity.get('unsuccessful_since_checkpoint', 0)
        require(type(failed) is int and failed >= 0, 'invalid unsuccessful correction count')
        if failed >= 2 and done['outcome'] == 'completed':
            checkpoint = continuity.get('diagnosis_checkpoint', {})
            require(all(checkpoint.get(k) for k in ('evidence', 'premise', 'next_change', 'acceptance')),
                    'two unsuccessful corrections require the diagnosis checkpoint')
        candidate = source_signature(self.root)
        if done['outcome'] == 'completed':
            for role in policy['required_roles']:
                require(agents.get(role), f'missing required role: {role}')
            review_errors = workflow.validate_reviews(done, records, candidate)
            require(not review_errors, '; '.join(review_errors))
            for role_entries in subs.values():
                for entry in role_entries:
                    event = next(r for r in records if r['event_id'] == entry['dispatch_event_id'])
                    if not workflow.completed(event):
                        continue
                    footer = event['footer']
                    if workflow.current_review(event, records, done, candidate) and footer.get('verdict') in ('APPROVE', 'APPROVE_WITH_FIXES'):
                        check = verify.load_evidence(self.root, footer.get('independent_check', {}).get('evidence'))
                        require(check['owner'] == event['agent_id'] and check['started_at'] >= start['timestamp'],
                                'independent check must have been executed by this reviewer during this iteration')
            required = ['structural'] + (['scientific'] if policy['kind'] == 'scientific_change' else [])
            verification = done.get('verification', {})
            require(verification.get('final_owner') == policy['final_verify_owner'], 'record the assigned final verification owner')
            for suite in required:
                require(isinstance(verification.get(suite), dict), workflow.verification_reference_message(policy['kind'], suite))
                evidence = verify.load_evidence(self.root, verification.get(suite))
                require(evidence['suite'] == suite and evidence['commands'] == self.cfg['verification'][suite],
                        f'{suite}: evidence must run the complete configured suite')
            if policy.get('execution_version') == 1 and policy['kind'] == 'scientific_change':
                import final_verification
                final_verification.check_receipt(self.root, done)
            errors = maintenance.check_done(self.root, start, done, records, candidate)
            require(not errors, '; '.join(errors))
        errors = workflow_records.check_milestone(self.root, done, allow_legacy=policy.get('execution_version') != 1)
        require(not errors, '; '.join(errors))
        done.setdefault('start_timestamp', start['timestamp'])
        prior = next((row for row in json_lines(local(self.root, f'{STATE}/loop_history.jsonl'))
                      if loop_iteration.matches(start, row)), {})
        done.setdefault('closed_at', prior.get('closed_at') or now())
        return done

    def self_assessment_notice(self, window=SELF_ASSESSMENT_WINDOW):
        """Advisory only; never blocks --next. See loop_contract.md's lesson-recording step.

        Counts completed loop_history.jsonl rows newer than lessons_learned.md's
        own last edit. This is a cheap proxy for "iterations since a process
        lesson was last recorded" -- it cannot tell whether a real retrospective
        happened without a code edit, only that none was saved.
        """
        lessons = local(self.root, 'lessons_learned.md')
        if not lessons.exists():
            return None
        since = dt.datetime.fromtimestamp(lessons.stat().st_mtime, dt.timezone.utc).isoformat()
        history = json_lines(local(self.root, f'{STATE}/loop_history.jsonl'))
        count = sum(1 for row in history if str(row.get('start_timestamp') or row.get('timestamp') or '') > since)
        if count >= window:
            return (f'SELF-ASSESSMENT: {count} loop iterations completed since lessons_learned.md was last '
                    f'updated (threshold {window}). Record a process lesson (or an explicit '
                    f'"nothing new this window" entry) before continuing -- see ARCHITECT.md#closure-and-communication. '
                    f'A process lesson is about the loop itself, not the science: e.g. repeated correction rounds on '
                    f'the same footer field, discarded review identities, or a recurring dispatch failure mode.')
        return None

    def next(self):
        for notice in team_retrospective.rule_notices(self.root):
            print(notice)
        audit.check(self.root, self.ledger_overrides)
        opened, closed, _ = validate_records(self.root, self.ledger_overrides)
        notifications.synchronize(self.root)
        message = notifications.notice(self.root)
        if message:
            print(message)
            return 0
        start_path = local(self.root, f'{STATE}/issue-start.json')
        history = json_lines(local(self.root, f'{STATE}/loop_history.jsonl'))
        if start_path.exists():
            start = json.loads(start_path.read_text())
            if not history or (history[-1]['id'], history[-1]['timestamp']) != (start['id'], start['timestamp']):
                print(f"NEXT: finish active iteration {start['id']} and run --check-done")
                return 0
        due = team_retrospective.pending(self.root)
        if due:
            print('NEXT: RETROSPECTIVE for ' + due['id'] + '; run --draft-retro, review, then --check-retro')
            return 0
        followup = team_retrospective.followup_due(self.root)
        if followup:
            print('NEXT: PROCESS FOLLOW-UP: ' + ', '.join(followup) + '; run tools/esx/self_improvement.py plan')
            return 0
        actionable = [row for row in opened.values() if row['state'] != 'blocked']
        for row in opened.values():
            if row['blocker'] and row['blocker'].split(' — ', 1)[0] in closed:
                print(f"UNBLOCKABLE: {row['id']}; inspect the dependency and update its status")
        if actionable:
            notice = self.self_assessment_notice()
            if notice:
                print(notice)
            print('NEXT: select an issue by impact, dependency and bounded acceptance')
            for row in actionable:
                print(f"  {row['id']}: {row['title']}")
            return 0
        notifications.synchronize(self.root, terminal='no actionable work')
        message = notifications.notice(self.root)
        if message:
            print(message)
            return 0
        print(f'NEXT: no actionable work; {len(opened)} blocked issue(s) remain')
        loop = local(self.root, '.claude/esx-loop.local.md')
        if loop.exists() and re.search(r'(?m)^active:\s*true\s*$', loop.read_text()):
            print(PROMISE)
            return 3
        print('Loop inactive; no completion promise emitted.')
        return 4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ('next', 'check-start', 'check-done', 'closeout-doctor', 'doctor', 'code-sig', 'draft-retro', 'check-retro', 'timings'):
        mode.add_argument('--' + name, action='store_true')
    mode.add_argument('--prepare', metavar='ISSUE')
    parser.add_argument('--kind', choices=workflow.KINDS, default='investigation')
    parser.add_argument('--risk', choices=workflow.RISKS, action='append', default=[])
    parser.add_argument('--owner', choices=('arch', 'bob', 'richard'), default='arch')
    parser.add_argument('--priority')
    parser.add_argument('--budget-kind', choices=tuple(team_budget.DEFAULTS), help='allocation class; scientific_small retains full scientific review')
    parser.add_argument('--map', default='docs/code_map.md#pipeline')
    parser.add_argument('--target', action='append', default=[])
    parser.add_argument('--doc', action='append', default=[])
    parser.add_argument('--use')
    parser.add_argument('--diagnosis', type=json.loads, help='agreed diagnosis checkpoint JSON after repeated failed corrections')
    parser.add_argument('--done', help='--closeout-doctor: draft closeout to inspect instead of loop_state/issue-done.json')
    args = parser.parse_args()
    try:
        gate = Gate(args.root)
        if args.next:
            return gate.next()
        if args.draft_retro:
            result = team_retrospective.draft(gate.root)
            atomic_json(local(gate.root, f'{STATE}/retrospective-draft.json'), result)
        elif args.check_retro:
            with team_accounting.phase(gate.root, gate.read('retrospective.json')['id'], 'retrospective', role='arch'):
                result = team_retrospective.accept(gate.root, gate.read('retrospective.json'))
        elif args.timings:
            result = team_accounting.summary(gate.root)
        elif args.closeout_doctor:
            # Read-only dry run: lists every unmet closeout requirement at once.
            import closeout_doctor
            result = closeout_doctor.diagnose(gate, args.done)
            print(json.dumps(result, indent=2))
            return 0 if result['status'] == 'ready' else 1
        elif args.doctor:
            result = audit.check(gate.root)
        elif args.code_sig:
            result = {'candidate_signature': source_signature(gate.root)}
        elif args.prepare:
            result = gate.prepare(args.prepare, args.kind, args.risk, args.owner, args.priority,
                                  args.map, args.target, args.doc, args.use, args.diagnosis, args.budget_kind)
        elif args.check_start:
            result = gate.check_start()
        else:
            result = gate.check_done()
            atomic_json(local(gate.root, f'{STATE}/issue-done.json'), result)
            save_history(gate.root, result)
            notifications.synchronize(gate.root)
            if notifications.notice(gate.root):
                print(notifications.notice(gate.root), file=sys.stderr)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError) as exc:
        print(f'ESX gate: BLOCKED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
