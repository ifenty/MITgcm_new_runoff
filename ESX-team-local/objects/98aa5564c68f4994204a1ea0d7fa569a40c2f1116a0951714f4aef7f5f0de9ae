"""Validate workflow decisions and candidate-specific review evidence.

These checks establish record consistency. Arch judges semantic risk, scope,
and the adequacy of the mathematical oracle.
"""
import re

KINDS = ("scientific_change", "harness_change", "documentation", "investigation")
ROLES = ("bob", "richard", "scout", "prober", "bisector", "auditor")
RISKS = ("guard_relaxation", "supported_semantics", "fundamental_algorithm",
         "correctness_disagreement")
SIGNATURE = re.compile(r"[0-9a-f]{64}\Z")
# separate_new records a separate issue the closeout itself opened (e.g. a gap a
# reviewer found); separate_existing one it merely references. Both name it.
SCOPE_CLASSIFICATIONS = ("dependency", "introduced_regression", "separate_existing",
                         "separate_new", "unknown")
SEPARATE_CLASSIFICATIONS = ("separate_existing", "separate_new")
VERIFICATION_KEYS = ("structural", "scientific", "receipt")


def verification_reference_message(kind, suite):
    """Name every verification key a completed closeout needs, not only what is absent."""
    needed = VERIFICATION_KEYS if kind == "scientific_change" else VERIFICATION_KEYS[:1]
    return (f"verification reference is required: verification.{suite} is missing or not an evidence reference. "
            "A completed closeout's verification block names three references separately: "
            "'structural' (the verify.py --suite structural evidence reference), 'scientific' and "
            "'receipt' (both returned by final_verification.py run; required for scientific_change). "
            f"This {kind} closeout needs: " + ", ".join(needed) + ".")


def default_workflow(kind, verify_signature, risks=(), numerical_signature=None):
    """Return a small issue-start fragment using measured initial source state."""
    roles = ["bob", "richard"] if kind == "scientific_change" else []
    minimum = 1 if kind == "scientific_change" else 0
    if risks:
        minimum = 2
        if "richard" not in roles:
            roles.append("richard")
    return {"version": 1, "execution_version": 1, "kind": kind, "required_roles": roles,
            "minimum_reviewers": minimum, "review_reasons": list(risks),
            "final_verify_owner": "arch", "verify_signature_at_start": verify_signature,
            "numerical_signature_at_start": numerical_signature or verify_signature}


def validate_workflow(workflow):
    if not isinstance(workflow, dict):
        return ["workflow must be an object"]
    errors = []
    if type(workflow.get("version")) is not int or workflow["version"] != 1:
        errors.append("workflow.version must be 1")
    if 'execution_version' in workflow and (type(workflow['execution_version']) is not int or workflow['execution_version'] != 1):
        errors.append('workflow.execution_version must be 1')
    kind = workflow.get("kind")
    if kind not in KINDS:
        errors.append(f"workflow.kind must be one of {KINDS}")
    roles = workflow.get("required_roles")
    if not isinstance(roles, list) or any(r not in ROLES for r in roles):
        errors.append("workflow.required_roles must list known roles")
        roles = []
    elif len(roles) != len(set(roles)):
        errors.append("workflow.required_roles contains duplicates")
    count = workflow.get("minimum_reviewers")
    if type(count) is not int or count not in (0, 1, 2):
        errors.append("workflow.minimum_reviewers must be 0, 1, or 2")
        count = 0
    risks = workflow.get("review_reasons")
    if not isinstance(risks, list) or any(r not in RISKS for r in risks):
        errors.append(f"workflow.review_reasons must list criteria from {RISKS}")
        risks = []
    if risks and count < 2:
        errors.append("a recorded review risk requires two independent reviewers")
    if count == 2 and not risks:
        errors.append("two reviewers require an explicit review risk")
    if count and "richard" not in roles:
        errors.append("required reviewers must include richard in required_roles")
    if kind == "scientific_change" and (count < 1 or not {"bob", "richard"}.issubset(roles)):
        errors.append("scientific_change requires Bob and at least one Richard")
    if workflow.get("final_verify_owner") not in ("arch", "bob", "richard"):
        errors.append("workflow.final_verify_owner must be arch, bob, or richard")
    if not SIGNATURE.fullmatch(str(workflow.get("verify_signature_at_start", ""))):
        errors.append("workflow.verify_signature_at_start must be a measured 64-digit signature")
    if not SIGNATURE.fullmatch(str(workflow.get("numerical_signature_at_start", ""))):
        errors.append("workflow.numerical_signature_at_start must be a measured 64-digit signature")
    return errors


def validate_transition(start, done, amendment=None):
    """Require an explicit record of changed scope or review requirements."""
    if start.get('execution_version') != done.get('execution_version'):
        return ['workflow amendment must preserve execution_version']
    if start == done:
        return []
    if (not isinstance(amendment, dict) or amendment.get("previous") != start
            or not str(amendment.get("reason", "")).strip()):
        return ["workflow changed: record workflow_amendment.previous and its reason"]
    return []


def validate_scope_decisions(decisions, completed=False):
    if not isinstance(decisions, list):
        return ["scope_decisions must be a list"]
    errors = []
    for i, decision in enumerate(decisions):
        label = f"scope_decisions[{i}]"
        if not isinstance(decision, dict):
            errors.append(f"{label} must be an object")
            continue
        kind = decision.get("classification")
        if kind not in SCOPE_CLASSIFICATIONS:
            errors.append(f"{label} needs a valid classification (one of {', '.join(SCOPE_CLASSIFICATIONS)})")
        if decision.get("status") not in ("resolved", "open", "blocked"):
            errors.append(f"{label} needs status resolved, open, or blocked")
        evidence = decision.get("evidence_refs")
        if isinstance(evidence, list) and any(isinstance(e, dict) for e in evidence):
            errors.append(f"{label} evidence_refs must be project-relative path strings, "
                          'not {"path", "sha256"} objects')
        elif (not isinstance(evidence, list) or not evidence
                or any(not isinstance(e, str) or not e.strip() for e in evidence)):
            errors.append(f"{label} needs evidence_refs (a non-empty list of project-relative path strings)")
        if kind in SEPARATE_CLASSIFICATIONS and not str(decision.get("issue_id", "")).strip():
            errors.append(f"{label} needs the separate issue_id ({kind})")
        if completed and (kind == "unknown" or
                          kind in ("dependency", "introduced_regression")
                          and decision.get("status") != "resolved"):
            errors.append(f"{label} prevents completion until its correctness dependency is resolved")
    return errors


def completed(record):
    """Accept explicit successful completions and footer-bearing legacy events."""
    return record.get('status', 'completed' if isinstance(record.get('footer'), dict) else 'incomplete') == 'completed'


def identity(record, key):
    return record.get(key) or (record.get('footer') or {}).get(key)


def known_completion_iteration(event, start, histories):
    """Admit current events and exact completions retained by an earlier closeout."""
    if identity(event, 'issue_id') != start.get('id'):
        return False
    iteration = identity(event, 'iteration_timestamp')
    if iteration == start.get('timestamp'):
        return True
    return any(row.get('id') == start.get('id') and row.get('timestamp') == iteration
        and (row.get('maintenance') or {}).get('baseline') == start['maintenance']['baseline']
        and any(entry.get('dispatch_event_id') == event.get('event_id')
                and entry.get('dispatch_id') == event.get('agent_id')
                for entry in (row.get('subagents') or {}).get(event.get('agent_type'), []))
        for row in histories)


def duplicate(record):
    """A stop that only repeats an earlier completion of the same agent (see agent_runtime.duplicate_completion)."""
    return isinstance(record, dict) and bool(record.get('duplicate_of'))


def current_review(event, records, done, candidate_signature):
    """Identify the latest successful reviewer turn for this iteration and source."""
    if (event.get('agent_type') != 'richard' or not completed(event)
            or identity(event, 'issue_id') != done.get('id')
            or identity(event, 'iteration_timestamp') != done.get('timestamp')
            or (event.get('footer') or {}).get('candidate_signature') != candidate_signature):
        return False
    latest = next((row for row in reversed(records)
                   if row.get('agent_type') == 'richard' and row.get('agent_id') == event.get('agent_id')
                   and identity(row, 'issue_id') == done.get('id') and not duplicate(row)), None)
    return latest is not None and latest.get('event_id') == event.get('event_id')


def resolved_dispatch(event, records, done):
    """Resolve a failed turn only with a referenced successful later continuation.

    Replacement identities require an explicit disposition. A failed later turn
    remains unresolved until its own subsequent completed continuation is recorded.
    """
    if completed(event):
        return True
    role = event.get('agent_type')
    referenced = {e.get('dispatch_event_id') for e in (done.get('subagents') or {}).get(role, []) if isinstance(e, dict)}
    try:
        position = records.index(event)
    except ValueError:
        return False
    for later in records[position + 1:]:
        if not completed(later) or later.get('event_id') not in referenced or later.get('agent_type') != role:
            continue
        if identity(later, 'issue_id') != done.get('id') or identity(later, 'iteration_timestamp') != done.get('timestamp'):
            continue
        if identity(event, 'issue_id') != done.get('id'):
            continue
        same = later.get('agent_id') == event.get('agent_id')
        # A later completed turn of the same retained agent is its continuation,
        # whether Arch resumed it within the same correction round (a timeout, a
        # stale orientation) or in a later one. A recovered orphan has no round.
        if same and (later.get('correction_round') or 0) >= (event.get('correction_round') or 0):
            return True
        replacements = (done.get('agent_continuity') or {}).get('replacements', [])
        if any(isinstance(r, dict) and r.get('role') == role
               and r.get('old_id') == event.get('agent_id') and r.get('new_id') == later.get('agent_id')
               and r.get('reason') and r.get('evidence_refs') for r in replacements):
            return True
    return False


def validate_reviews(done, records, candidate_signature):
    """Count distinct current reviewers using exact hook completions and their footers.

Historical candidate reports remain in the arrays. The latest completion of each
participating reviewer determines its current verdict. A replacement reviewer may
supersede an unavailable reviewer only through an explicit disposition with evidence.
"""
    workflow = done["workflow"]
    minimum = workflow["minimum_reviewers"]
    if done.get("outcome") != "completed" or (not minimum and not (done.get("subagents") or {}).get("richard")):
        return []
    if not SIGNATURE.fullmatch(str(candidate_signature)):
        return ["cannot measure the current review candidate signature"]
    errors, latest, referenced = [], {}, {}
    for record in records:
        if (record.get("agent_type") == "richard" and identity(record, "issue_id") == done.get("id")
                and not duplicate(record)):
            latest[record.get("agent_id")] = record
    for entry in (done.get("subagents") or {}).get("richard", []):
        if isinstance(entry, dict) and not entry.get("waived"):
            referenced.setdefault(entry.get("dispatch_id"), []).append(entry)
    for agent_id, record in latest.items():
        footer = record.get("footer") or {}
        if (identity(record, "issue_id") == done.get("id")
                and (footer.get("candidate_signature") == candidate_signature or not completed(record))
                and agent_id not in referenced):
            message = f"{agent_id}: current issue review completion is missing from subagents.richard"
            if any(isinstance(e, dict) and e.get("waived") and e.get("dispatch_id") == agent_id
                   for e in (done.get("subagents") or {}).get("richard", [])):
                message += (" -- it is marked waived, but waiving is not a valid disposition for a failed or "
                            "incomplete review: it would erase the record of a review that did not happen. "
                            "Keep the entry unwaived and resolve it through a later completed continuation of "
                            "the same reviewer, or an agent_continuity.replacements entry (role, old_id, new_id, "
                            "reason, evidence_refs) naming the reviewer that replaced it")
            errors.append(message)
    approved = set()
    superseded = done.get("review_supersessions", [])
    if not isinstance(superseded, list):
        return ["review_supersessions must be a list"]
    for agent_id, entries in referenced.items():
        record = latest.get(agent_id)
        if not record:
            continue  # Dispatch correlation reports the missing evidence.
        final = next((e for e in entries if e.get("dispatch_event_id") == record.get("event_id")), None)
        if final is None or not record.get("event_id"):
            errors.append(f"{agent_id}: final review must reference the latest completion event")
            continue
        footer = record.get("footer") or {}
        if not completed(record):
            if not resolved_dispatch(record, records, done):
                errors.append(f"{agent_id}: latest review failed or is incomplete")
            continue
        if footer.get("issue_id") != done.get("id"):
            errors.append(f"{agent_id}: review footer belongs to another issue")
            continue
        # Prior candidates are retained as history and supply no final approval.
        if not current_review(record, records, done, candidate_signature):
            if identity(record, "iteration_timestamp") != done.get("timestamp"):
                errors.append(f"{agent_id}: review's iteration_timestamp does not match the active issue "
                               f"(review a fresh candidate under the current iteration, not a prior one)")
            elif footer.get("candidate_signature") != candidate_signature:
                errors.append(f"{agent_id}: candidate_signature {footer.get('candidate_signature')!r} does not match "
                               f"the live source signature {candidate_signature!r} -- recompute it with "
                               f"'python3 tools/esx/project.py signature' (not issue_candidates.py's own signature, "
                               f"a different hash scheme) and resubmit")
            else:
                errors.append(f"{agent_id}: a later review of this issue exists; only its most recent completion counts")
            continue
        for field in ("verdict", "independent_check", "must_fix", "candidate_signature"):
            if field in final and final[field] != footer.get(field):
                errors.append(f"{agent_id}: pasted {field} disagrees with the hook footer")
        disposition = next((x for x in superseded if isinstance(x, dict)
                            and x.get("event_id") == record["event_id"]), None)
        if disposition:
            replacement = next((r for r in records if r.get("event_id") == disposition.get("by_event_id")), {})
            rf = replacement.get("footer") or {}
            if (not disposition.get("reason") or not disposition.get("evidence_refs")
                    or replacement.get("agent_id") == agent_id
                    or replacement.get("agent_type") != "richard" or not completed(replacement)
                    or rf.get("issue_id") != done.get("id")
                    or rf.get("candidate_signature") != candidate_signature
                    or rf.get("verdict") != "APPROVE" or rf.get("must_fix") != []
                    or replacement.get("agent_id") not in referenced):
                errors.append(f"{agent_id}: review supersession needs a distinct current approval and disposition evidence")
            continue
        if footer.get("verdict") not in ("APPROVE", "APPROVE_WITH_FIXES") or footer.get("must_fix") != []:
            errors.append(f"{agent_id}: current review has unresolved blocking findings")
            continue
        check = footer.get("independent_check")
        if (not isinstance(check, dict) or not str(check.get("cmd", "")).strip()
                or type(check.get("exit")) is not int or check["exit"] != 0
                or check.get("executed") is not True):
            errors.append(f"{agent_id}: final review requires an executed, successful independent check")
            continue
        approved.add(agent_id)
    if len(approved) < minimum:
        errors.append(f"current candidate has {len(approved)} independent approvals; {minimum} required")
    return errors
