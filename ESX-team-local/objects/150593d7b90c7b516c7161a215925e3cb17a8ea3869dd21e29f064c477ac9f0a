"""Role-specific report generation and early evidence checks for ESX dispatch.

Identity comes from the dispatcher. Examples never manufacture scientific checks,
orientation or approval. Legacy transport-only fixtures retain identity checking.
"""
import json
from pathlib import Path


def example(root, role):
    value = json.loads((Path(root) / 'esx/templates/agent_report.json').read_text())
    value['agent'] = role
    if role != 'richard':
        for key in ('candidate_signature', 'verdict', 'must_fix', 'independent_check', 'documentation_review'):
            value.pop(key, None)
    else:
        value['verdict'] = 'APPROVE|APPROVE_WITH_FIXES|REJECT'
        value['documentation_review']['status'] = 'confirmed'
    return value


def stale_citation(cited, expected):
    """Name both hashes when a reviewer cites a seal other than the current one.

    Every implementer correction re-seals the documentation report, so a
    confirming reviewer can carry a superseded reference from an earlier round.
    Reporting it at capture lets the reviewer correct it in the same turn.
    """
    if not isinstance(expected, dict) or cited == expected:
        return None
    sha = cited.get('sha256') if isinstance(cited, dict) else None
    return ('documentation_review.report cites a superseded or different sealed documentation report: cited sha256 '
            + str(sha) + ', expected current sha256 ' + str(expected.get('sha256')) + ' at '
            + str(expected.get('path')) + '; read that exact file and cite it verbatim')


def validate(root, role, footer, issue, correction_round, start=None, agent_id=None, expected_report=None):
    """Return capture-time footer errors.

    expected_report is the current sealed documentation reference from the
    validated review packet; a Richard approval citing any other report fails.
    """
    errors = []
    if not isinstance(footer, dict):
        return ['missing structured footer']
    for key, value in (('agent', role), ('issue_id', issue), ('correction_round', correction_round)):
        if footer.get(key) != value:
            errors.append('footer must use dispatcher ' + key)
    if not start or start.get('state_version', 1) < 2:
        return errors
    def shape_errors(value, template, at='footer'):
        if template is None:
            return []
        if type(value) is not type(template):
            return [at + ' must be ' + type(template).__name__]
        if isinstance(template, dict):
            found = []
            for key, expected in template.items():
                if key not in value:
                    found.append(at + '.' + key + ' is required')
                else:
                    found.extend(shape_errors(value[key], expected, at + '.' + key))
            return found
        return []
    try:
        errors += shape_errors(footer, example(root, role))
    except (ValueError, OSError, TypeError) as exc:
        errors.append('invalid report template: ' + str(exc))
    if errors:
        return errors
    if footer.get('iteration_timestamp') != start['timestamp']:
        errors.append('footer must preserve iteration_timestamp')
    if role in ('bob', 'richard'):
        try:
            import doc_contract as docs
            docs.validate_orientation(Path(root), footer.get('orientation'), issue,
                                      start['maintenance']['baseline'], role)

            if role == 'richard':
                if footer.get('verdict') not in ('APPROVE', 'APPROVE_WITH_FIXES', 'REJECT'):
                    raise ValueError('verdict must be APPROVE, APPROVE_WITH_FIXES, or REJECT')
                if not isinstance(footer.get('must_fix'), list):
                    raise ValueError('must_fix must be a list')
                if footer['verdict'] != 'REJECT':
                    import verify
                    from project import source_signature
                    check = footer.get('independent_check') or {}
                    if (check.get('executed') is not True or type(check.get('exit')) is not int
                            or check['exit'] != 0 or not check.get('cmd') or footer['must_fix']):
                        raise ValueError('approval needs a successful executed check and no must_fix findings')
                    evidence = verify.load_evidence(Path(root), check.get('evidence'))
                    if agent_id and evidence.get('owner') != agent_id:
                        raise ValueError('independent check must be owned by the actual reviewer identity')
                    if footer.get('candidate_signature') != source_signature(Path(root)):
                        raise ValueError('candidate_signature must come from project.py signature')
                    review = footer.get('documentation_review') or {}
                    if not docs.explanation(review.get('notes')):
                        raise ValueError('documentation_review.notes needs a substantive explanation')
                    if review.get('status') != 'confirmed':
                        raise ValueError('documentation_review.status must be confirmed')
                    stale = stale_citation(review.get('report'), expected_report)
                    if stale:
                        raise ValueError(stale)
                    report = docs.load(Path(root), review.get('report'), 'documentation', issue)
                    docs.validate_report(Path(root), report, issue, start['maintenance']['baseline'])
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append(str(exc))
    return errors


def reference_errors(root, role, footer, start, agent_id=None):
    """The mechanical part of the contract: every reference the footer cites resolves.

    Applied when a native agent stops, where the full shape contract is not
    enforced. A reference is checked only when the footer gives one: the
    orientation receipt, the independent check's evidence (which must also be
    owned by the reporting agent) and the documentation report under review.
    """
    if not isinstance(footer, dict) or not isinstance(start, dict) or start.get('state_version', 1) < 2:
        return []
    import doc_contract as docs
    import verify
    errors = []
    issue = footer.get('issue_id')
    orientation = footer.get('orientation')
    if isinstance(orientation, dict) and (orientation.get('path') or orientation.get('sha256')):
        try:
            docs.validate_orientation(Path(root), orientation, issue, start['maintenance']['baseline'], role,
                                      fresh=False)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append('orientation: ' + str(exc))
    cited = (footer.get('independent_check') or {}).get('evidence')
    if isinstance(cited, dict) and (cited.get('path') or cited.get('sha256')):
        try:
            evidence = verify.load_evidence(Path(root), cited)
            if agent_id and evidence.get('owner') != agent_id:
                errors.append(f'independent_check.evidence is owned by {evidence.get("owner")}, not by the '
                              f'reporting agent {agent_id}')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append('independent_check.evidence: ' + str(exc))
    report = (footer.get('documentation_review') or {}).get('report')
    if isinstance(report, dict) and (report.get('path') or report.get('sha256')):
        try:
            docs.load(Path(root), report, 'documentation', issue)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            errors.append('documentation_review.report: ' + str(exc))
    return errors


def handoff(record):
    footer = record.get('footer') or {}
    return {'outcome': footer.get('summary') or record.get('status'),
            'constraints': footer.get('limits', []), 'acceptance_tests': footer.get('evidence', []),
            'dispatch_event_id': record['event_id'], 'report': record.get('report'), 'footer': footer}
