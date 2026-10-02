"""Portable review-packet assembly and read-only readiness diagnostics.

Inputs may be outside the project. Evidence references remain validated by the
owning maintenance, candidate, and final-verification modules. No approval or
human documentation judgment is inferred by this module.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path


def input_file(root, name):
    """Resolve a read-only CLI input against --root, accepting absolute paths."""
    path = Path(name)
    return path if path.is_absolute() else Path(root) / path


def finding(code, field, observed, recovery, *, status='blocked', agent=None, event=None):
    """Represent one actionable failure identically in text and JSON output."""
    return dict(code=code, field=field, observed=str(observed), recovery=recovery,
                status=status, agent=agent, dispatch_event_id=event)


def active_attempts(root, issue):
    """Read running retained sessions, including turns with no completion event yet."""
    import workflow_records as records
    root = Path(root).resolve()
    directory = records.local_file(root, records.STATE + '/agent_runtime/sessions')
    attempts = []
    for path in sorted(directory.glob('*/session.json')):
        path = records.local_file(root, str(path.relative_to(root)))
        state = records.read_json(path)
        if state.get('issue_id') == issue and state.get('status') == 'running':
            attempts.append(dict(agent=state.get('role'), session_id=state.get('session_id'),
                                 dispatch_event_id=state.get('active_event_id'), path=str(path.relative_to(root))))
    return attempts


def readiness(root, packet, stage='review', owner=None):
    """Collect independent prerequisite failures before invoking final validators.

    Final review and suite gates remain authoritative. Missing prerequisites mark
    dependent checks pending, avoiding misleading approval errors for a packet
    whose source or documentation has not yet been established.
    """
    import doc_contract as docs
    import issue_candidates as candidates
    import workflow_records as records
    findings = []
    def check(code, field, action, recovery, **identity):
        """Record one failed prerequisite without suppressing independent checks."""
        try:
            return action()
        except (ValueError, OSError, KeyError, TypeError) as exc:
            findings.append(finding(code, field, exc, recovery, **identity))
    start = check('START_INVALID', 'issue-start', lambda: records.read_json(
        Path(root) / records.STATE / 'issue-start.json'), 'Restore the matching issue-start record.')
    if not isinstance(packet, dict) or not isinstance(start, dict):
        findings.append(finding('PACKET_INVALID', 'packet', 'A packet and issue-start object are required.',
                                'Supply the exact review packet JSON.'))
        return dict(status='blocked', stage=stage, findings=findings)
    if start.get('state_version', 1) >= 2:
        import verify
        check('STRUCTURAL_STALE_OR_FAILING', 'verification.structural', lambda: verify.structural_evidence(Path(root)),
              'Run the complete configured structural suite before preparing review.')
    issue = start.get('id')
    active = check('RUNTIME_STATE_INVALID', 'runtime.sessions', lambda: active_attempts(root, issue),
                   'Inspect the named retained-session state before preparing the candidate.')
    for attempt in active or []:
        findings.append(finding('ATTEMPT_RUNNING', attempt['path'], 'turn has no terminal completion yet',
                                'Wait for or explicitly recover this running assignment.',
                                agent=attempt['session_id'], event=attempt['dispatch_event_id']))
    if packet.get('id') != issue:
        findings.append(finding('ISSUE_MISMATCH', 'id', packet.get('id'), 'Use the active issue identity.'))
    maintenance = packet.get('maintenance') or {}
    if not isinstance(maintenance, dict):
        findings.append(finding('MAINTENANCE_INVALID', 'maintenance', 'expected an object', 'Supply baseline, documentation and orientation references.'))
        maintenance = {}
    base = (start.get('maintenance') or {}).get('baseline')
    if maintenance.get('baseline') != base or not base:
        findings.append(finding('BASELINE_MISMATCH', 'maintenance.baseline', maintenance.get('baseline'),
                                'Retain the original issue baseline from issue-start.'))
    candidate = check('CANDIDATE_INVALID', 'candidate',
        lambda: candidates.check_current(root, packet.get('candidate'), issue),
        'Capture the finished source candidate and rebuild this packet.')
    if candidate and candidate.get('baseline') != base:
        findings.append(finding('CANDIDATE_BASELINE', 'candidate.baseline', candidate.get('baseline'),
                                'Capture with the original issue baseline.'))
    def documentation():
        """Bind the packet map disposition to its exact sealed report."""
        report = docs.load(root, maintenance.get('documentation'), 'documentation', issue)
        docs.require('references' in report, 'documentation report must be sealed')
        docs.validate_report(root, report, issue, base)
        docs.require(packet.get('map_delta') == report['map_delta'], 'map_delta must match the sealed report')
        return report
    check('DOCUMENTATION_INVALID', 'maintenance.documentation', documentation,
          'Complete and seal the documentation report; rebuild using its exact reference.')
    check('ARCH_ORIENTATION_INVALID', 'maintenance.orientation',
          lambda: docs.validate_orientation(root, maintenance.get('orientation'), issue, base, 'arch'),
          'Arch must inspect changed targets and record a fresh orientation; when only declared targets or '
          'documents changed, `doc_contract.py navigate --issue <id> --reuse-args <receipt> --use <fresh explanation>` '
          'reprints them without retyping the arguments.')
    handoff = packet.get('handoff') or {}
    if not isinstance(handoff, dict):
        handoff = {}
    for field in ('outcome', 'constraints', 'acceptance_tests'):
        if not (isinstance(handoff.get(field), list) if field == 'constraints' else bool(handoff.get(field))):
            findings.append(finding('BRIEF_INCOMPLETE', 'handoff.' + field, 'missing',
                                    'Supply the agreed behavior, constraints and acceptance tests.'))
    dispatches = check('DISPATCH_LOG_INVALID', 'dispatch_log', lambda: records.read_jsonl(
        Path(root) / records.STATE / 'dispatch_log.jsonl'), 'Repair the evidence log using original runtime artifacts.')
    if dispatches is not None:
        selected = []
        subagents = packet.get('subagents') or {}
        if not isinstance(subagents, dict):
            findings.append(finding('SUBAGENTS_INVALID', 'subagents', 'expected an object', 'Rebuild from exact event selections.'))
            subagents = {}
        for role, entries in subagents.items():
            if not isinstance(entries, list):
                findings.append(finding('COMPLETION_INVALID', 'subagents.' + role, 'expected a list', 'Rebuild from exact event selections.'))
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    findings.append(finding('COMPLETION_INVALID', 'subagents.' + role, 'expected a completion object', 'Select an exact event.'))
                    continue
                imported = check('COMPLETION_INVALID', 'subagents.' + role,
                    lambda e=entry, r=role: records.import_completion(start, dispatches, dict(e, agent=r), True),
                    'Select a unique recorded event belonging to this issue, agent and round.',
                    agent=entry.get('dispatch_id'), event=entry.get('dispatch_event_id'))
                if imported:
                    if any(entry.get(k) != value for k, value in imported.items() if k != 'report_digest'):
                        findings.append(finding('COMPLETION_ALTERED', 'subagents.' + role, 'captured evidence differs',
                                                'Reimport the exact runtime footer.', agent=entry.get('dispatch_id'),
                                                event=entry.get('dispatch_event_id')))
                    selected.append(imported)
                    if imported.get('status') == 'running':
                        findings.append(finding('ATTEMPT_RUNNING', 'subagents.' + role, 'turn still running',
                                                'Wait for the recorded terminal event.', agent=entry.get('dispatch_id'),
                                                event=entry.get('dispatch_event_id')))
        import workflow_policy as lifecycle
        for entry in selected:
            if (entry.get('agent') or entry.get('agent_name')) == 'bob':
                event = next(e for e in dispatches if e['event_id'] == entry['dispatch_event_id'])
                if not lifecycle.resolved_dispatch(event, dispatches, packet):
                    findings.append(finding('IMPLEMENTATION_UNRESOLVED', 'subagents.bob', 'latest implementation attempt is unresolved',
                                            'Select the completed continuation or provide an explicit replacement disposition.',
                                            agent=entry['dispatch_id'], event=entry['dispatch_event_id']))
        if stage == 'final':
            latest = {}
            for event in dispatches:
                footer = event.get('footer') or {}
                if event.get('agent_type') == 'richard' and event.get('issue_id', footer.get('issue_id')) == issue:
                    latest[event['agent_id']] = event
            chosen = {entry['dispatch_event_id'] for entry in selected}
            for agent, event in latest.items():
                if event.get('event_id') in chosen and event.get('status', 'completed') == 'completed':
                    check('REVIEWER_ORIENTATION_INVALID', 'subagents.richard.orientation',
                          lambda e=event: docs.validate_orientation(root, e['footer'].get('orientation'), issue, base, 'richard'),
                          'Resume this reviewer with the listed delta, refresh its own orientation and affected check.',
                          agent=agent, event=event['event_id'])
        if not any((e.get('agent') or e.get('agent_name')) == 'bob' and
                   e.get('status', 'completed') == 'completed' for e in selected):
            findings.append(finding('IMPLEMENTATION_MISSING', 'subagents.bob', 'no completed implementation evidence',
                                    'Resume Bob and select the successful completion event.'))
    if stage == 'final':
        if findings:
            findings.append(finding('FINAL_CHECK_PENDING', 'reviews', 'prerequisites are incomplete',
                                    'Resolve the independent findings, then repeat readiness.', status='pending'))
        else:
            import final_verification
            check('FINAL_EVIDENCE_INVALID', 'reviews', lambda: final_verification.ready(root, packet, owner),
                  'Resolve the reported approval, scope, orientation or owner failure; retain reviewer identities.')
    return dict(status='ready' if not findings else 'blocked', stage=stage, findings=findings)


def assemble(root, start, dispatches, selections, candidate, documentation, handoff, prior=None, orientation=None):
    """Build one explicit review packet; source and sealed-report validation are separate."""
    import workflow_records as records
    import doc_contract as docs
    packet = records.prepare_done(start, dispatches, selections, prior)
    packet['candidate'] = deepcopy(candidate)
    if orientation is not None:
        packet.setdefault('maintenance', {})['orientation'] = deepcopy(orientation)
    packet.setdefault('maintenance', {})['documentation'] = deepcopy(documentation)
    try:
        report = docs.load(root, documentation, 'documentation', start['id'])
        packet['map_delta'] = deepcopy(report['map_delta'])
    except (ValueError, OSError, KeyError, TypeError):
        # Readiness reports this failure alongside other independent findings.
        packet['map_delta'] = None
    packet['handoff'] = deepcopy(handoff)
    # Administrative closeout questions remain visible without being treated as
    # prerequisites for Richard or an authorized final scientific run.
    packet['closeout_pending'] = packet.pop('preparation')
    return packet


def add_commands(sub, state):
    """Attach packet, readiness and identity-selection operations to the records CLI."""
    build = sub.add_parser('review-packet', help='assemble an immutable handoff from explicit evidence')
    build.add_argument('--start', default=f'{state}/issue-start.json')
    build.add_argument('--select', required=True, help='read-only JSON input; absolute paths accepted')
    build.add_argument('--candidate', required=True, help='JSON input containing the candidate reference')
    build.add_argument('--documentation', required=True, help='JSON input containing the sealed report reference')
    build.add_argument('--orientation', required=True, help='JSON input containing Arch current orientation reference')
    build.add_argument('--handoff', required=True, help='JSON input with outcome, constraints and acceptance_tests')
    build.add_argument('--prior')
    build.add_argument('--output', required=True, help='new project-relative JSON path below loop_state')
    build.add_argument('--stage', choices=('review', 'final'), default='review')
    build.add_argument('--owner', default='arch')
    inspect = sub.add_parser('readiness', help='read-only aggregate diagnostics; performs no agent or suite runs')
    inspect.add_argument('--review', required=True)
    inspect.add_argument('--stage', choices=('review', 'final'), default='final')
    inspect.add_argument('--owner', default='arch')
    inspect.add_argument('--format', choices=('json', 'text'), default='json')
    select = sub.add_parser('selections', help='list exact event identities for explicit selection')
    select.add_argument('--start', default=f'{state}/issue-start.json')


def command(root, args):
    """Run a records subcommand; publish only after two successful readiness checks."""
    import workflow_records as records
    read = lambda name: records.read_json(input_file(root, name))
    if args.command == 'readiness':
        result = readiness(root, read(args.review), args.stage, args.owner)
    else:
        start = read(args.start)
        events = records.read_jsonl(Path(root) / records.STATE / 'dispatch_log.jsonl')
        if args.command == 'selections':
            result = []
            for event in events:
                footer = event.get('footer') or {}
                if event.get('issue_id', footer.get('issue_id')) != start['id']:
                    continue
                result.append(dict(agent=event['agent_type'], dispatch_id=event['agent_id'],
                    dispatch_event_id=event['event_id'], correction_round=event.get('correction_round', footer.get('correction_round')),
                    status=event.get('status', 'completed'),
                    selection_scope='history' if event.get('ts', '') < start['timestamp'] else 'current'))
            print(json.dumps(result, indent=2))
            return 0
        packet = assemble(root, start, events, read(args.select), read(args.candidate),
                          read(args.documentation), read(args.handoff), read(args.prior) if args.prior else None, read(args.orientation))
        result = readiness(root, packet, args.stage, args.owner)
        if result['status'] == 'ready':
            # Revalidate source/report and dispatch identity immediately before
            # atomic publication. Consumers also validate on every use.
            result = readiness(root, packet, args.stage, args.owner)
            if result['status'] == 'ready':
                path = records.local_file(root, args.output)
                if not path.is_relative_to(Path(root) / records.STATE):
                    raise ValueError('review packet output must be below project loop_state')
                records.write_output(root, args.output, packet)
                result['packet'] = args.output
    if getattr(args, 'format', 'json') == 'text':
        print(result['status'].upper())
        for row in result['findings']:
            print(f"{row['code']} [{row['field']}]: {row['observed']}\n  Recovery: {row['recovery']}")
    else:
        print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'ready' else 1
