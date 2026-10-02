#!/usr/bin/env python3
"""Validate and summarize the separate ESX-team self-improvement issue ledger.

Read-only check/list/inspect/classify/plan use repository-contained evidence.
Index regenerates the closed-record view; promote/recover delegate to a locked,
recoverable transaction. Follow-up decisions are recorded in ignored loop state.
New closure requires successful hashed command evidence tied to a landed commit;
legacy exemptions match the frozen migration manifest exactly.
"""

from __future__ import annotations

import argparse
from contextvars import ContextVar

STAGED_RECORDS = ContextVar("staged_process_records", default=None)
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import process_evidence


ROOT = Path(__file__).resolve().parents[2]
BASE = Path("devel-loop/self-improvement")
OPEN = BASE / "open-ESX-team-issues.md"
CLOSED = BASE / "closed-ESX-team-issues.md"
INDEX = BASE / "process_changelog.md"
ROOT_LEDGERS = (Path("open_issues.md"), Path("closed_issues.md"))

UUID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){2,}$")
FIELD_RE = re.compile(r"^\*\*([^*]+)\*\*:\s*(.*)$")
HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)
OPEN_STATUSES = {
    "Proposed",
    "Investigating",
    "Implementing",
    "Implemented — awaiting publication/effectiveness evidence",
    "Blocked",
}
CLOSED_STATUSES = {
    "Verified effective",
    "Implemented/validated",
    "Superseded",
    "False positive",
}
REQUIRED_SECTIONS = ("Issue", "Evidence", "Potential Impact", "Proposed Fix")
PROCESS_HINTS = re.compile(
    r"\b(loop|gate|dispatch|review|reviewer|agent|brief|footer|hook|ralph|"
    r"retrospect|workflow|budget|accounting|close-?out|documentation seal|"
    r"candidate signature|process changelog|lessons index)\b",
    re.IGNORECASE,
)
SCIENTIFIC_HINTS = re.compile(
    r"\b(gradient|adjoint|tangent|finite difference|tape|recompute|fortran|"
    r"compiler|generated code|intrinsic|common block|derivative|execution model)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    path: Path
    title: str
    line: int
    text: str
    fields: dict[str, str]
    sections: dict[str, str]

    @property
    def uuid(self) -> str:
        return self.fields.get("UUID", "")

    @property
    def legacy(self) -> bool:
        return self.fields.get("Record-Version", "").startswith("1")


def rel(root: Path, path: Path) -> str:
    """Return a stable repository-relative display path."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def parse(path: Path, strict=False, text=None) -> list[Issue]:
    """Parse issue blocks beginning with an H2 heading and containing a UUID field."""
    if text is None and not path.is_file():
        return []
    text = path.read_text(encoding="utf-8") if text is None else text
    visible = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            visible.append(" " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line))
        elif fenced:
            visible.append(" " * (len(line) - 1) + "\n" if line.endswith("\n") else " " * len(line))
        else:
            visible.append(line)
    searchable = "".join(visible)
    matches = list(HEADING_RE.finditer(searchable))
    issues: list[Issue] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start():end].rstrip() + "\n"
        visible_block = searchable[match.start():end]
        fields: dict[str, str] = {}
        for line in visible_block.splitlines():
            field = FIELD_RE.match(line)
            if field:
                if strict and field.group(1).strip() in fields:
                    raise ValueError(f'{path}: duplicate field {field.group(1)}')
                fields[field.group(1).strip()] = field.group(2).strip()
        if "UUID" not in fields:
            if strict and not match.group(1).startswith('Template'):
                raise ValueError(f'{path}: issue heading without UUID: {match.group(1)}')
            continue
        sections: dict[str, str] = {}
        section_matches = list(re.finditer(r"^### (.+)$", block, re.MULTILINE))
        for section_index, section in enumerate(section_matches):
            section_end = (
                section_matches[section_index + 1].start()
                if section_index + 1 < len(section_matches)
                else len(block)
            )
            sections[section.group(1).strip()] = block[section.end():section_end].strip()
        issues.append(
            Issue(
                path=path,
                title=match.group(1).strip(),
                line=text[:match.start()].count("\n") + 1,
                text=block,
                fields=fields,
                sections=sections,
            )
        )
    return issues


def git_commit_exists(root: Path, value: str) -> bool:
    """Publication for this checkout means ancestor of HEAD, not object existence."""
    return process_evidence.landed(root, value)


def evidence_exists(root: Path, value: str) -> bool:
    """Check a content-bound regular file contained in the repository."""
    try:
        process_evidence.reference(root, value)
        return True
    except (ValueError, OSError, TypeError):
        return False


def root_uuids(root: Path) -> dict[str, Path]:
    """Return UUID ownership in the ESX transformation issue ledgers."""
    result: dict[str, Path] = {}
    for ledger in ROOT_LEDGERS:
        for issue in parse(root / ledger):
            result[issue.uuid] = ledger
    return result


def check_issue(root: Path, issue: Issue, closed: bool) -> list[str]:
    """Validate one current or explicitly legacy-migrated issue."""
    at = f"{rel(root, issue.path)}:{issue.line} {issue.uuid or '<missing UUID>'}"
    errors: list[str] = []
    if not UUID_RE.fullmatch(issue.uuid):
        errors.append(f"{at}: invalid UUID")
    if issue.legacy:
        try:
            record = json.loads((root / BASE / 'migration_manifest.json').read_text())['records'][issue.uuid]
            if (record['sha256'] != hashlib.sha256(issue.text.encode()).hexdigest()
                    or record['source'] != issue.fields.get('Migration-Source')
                    or record['ledger'] != rel(root, issue.path)):
                raise ValueError('legacy record differs from frozen migration')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{at}: unverified migration: {exc}')
        return errors

    for field in ("Date Identified", "Status", "Category", "Severity", "Assessment", "Anchors"):
        if not issue.fields.get(field):
            errors.append(f"{at}: missing field {field}")
    for section in REQUIRED_SECTIONS:
        if len(issue.sections.get(section, "")) < 20:
            errors.append(f"{at}: section {section!r} must contain at least 20 characters")
    try:
        process_evidence.reference(root, issue.fields.get('Assessment', ''), require_hash=False)
        for anchor in issue.fields.get('Anchors', '').split(';'):
            token = anchor.strip().split('(', 1)[0].strip()
            name, _, target = token.partition(':')
            target = target.lstrip(':')
            data = process_evidence.reference(root, name, require_hash=False)
            if target:
                if target.isdigit():
                    if not 1 <= int(target) <= len(data.splitlines()):
                        raise ValueError('anchor line is outside file: ' + token)
                elif name.endswith('.py'):
                    from doc_inventory import python_units
                    units = python_units(data.decode(), name)
                    if not any(unit == target or unit.endswith('.' + target) for unit in units):
                        raise ValueError('anchor symbol does not exist: ' + token)
    except (ValueError, OSError, TypeError) as exc:
        errors.append(f'{at}: invalid assessment/anchor: {exc}')

    status = issue.fields.get("Status", "")
    if closed:
        if status not in CLOSED_STATUSES:
            errors.append(f"{at}: closed Status must be one of {sorted(CLOSED_STATUSES)}")
        if not issue.fields.get("Date Resolved"):
            errors.append(f"{at}: closed record needs Date Resolved")
        for section in ("Implementation", "Validation", "Remaining Limitations"):
            if len(issue.sections.get(section, "")) < 20:
                errors.append(f"{at}: closed section {section!r} must contain at least 20 characters")
        if status in {"Implemented/validated", "Verified effective"}:
            commit = issue.fields.get("Implementation-Commit", "")
            if not git_commit_exists(root, commit):
                errors.append(f"{at}: Implementation-Commit is not a reachable commit")
            evidence = issue.fields.get("Validation-Evidence", "")
            errors += [f'{at}: Validation-Evidence: {e}' for e in process_evidence.validation_errors(root, evidence, commit)]
        if status == "Verified effective":
            measurement = issue.fields.get("Effectiveness-Evidence", "")
            errors += [f'{at}: Effectiveness-Evidence: {e}' for e in process_evidence.effectiveness_errors(root, measurement)]
    else:
        if status not in OPEN_STATUSES:
            errors.append(f"{at}: open Status must be one of {sorted(OPEN_STATUSES)}")
        for section in ("Acceptance Criteria", "Expected Effect"):
            if len(issue.sections.get(section, "")) < 20:
                errors.append(f"{at}: open section {section!r} must contain at least 20 characters")
        if status.startswith("Implemented") and not issue.fields.get("Implementation-Reference"):
            errors.append(f"{at}: implemented-open record needs Implementation-Reference")
        if status == "Blocked" and not issue.fields.get("Blocked-By"):
            errors.append(f"{at}: Blocked record needs Blocked-By")
    return errors


def index_text(closed: list[Issue]) -> str:
    """Generate the compact process changelog from the closed issue ledger."""
    entries = []
    for issue in closed:
        date = issue.fields.get("Date Resolved", "UNKNOWN").split()[0]
        status = issue.fields.get("Status", "Legacy")
        commit = issue.fields.get("Implementation-Commit", "LEGACY")
        summary = issue.sections.get("Implementation") or issue.sections.get("Resolution")
        if not summary:
            summary = issue.title
        summary = " ".join(summary.split())
        if len(summary) > 180:
            summary = summary[:177].rstrip() + "..."
        entries.append((date, issue.uuid, commit, status, summary))
    entries.sort(key=lambda row: (row[0], row[1]), reverse=True)
    lines = [
        "# ESX-team process changelog (generated)",
        "",
        "Generated from `closed-ESX-team-issues.md` by `python3 tools/esx/self_improvement.py index`.",
        "Do not edit this file manually; the closed ledger is authoritative.",
        "",
        "## Log",
        "",
    ]
    for date, uuid, commit, status, summary in entries:
        lines.append(f"- {date} `{commit}` **{uuid}** [{status}] — {summary}")
    return "\n".join(lines) + "\n"


def validate(root: Path, overrides=None) -> list[str]:
    """Validate both ledgers and the generated changelog."""
    staged = STAGED_RECORDS.get()
    if overrides is None and staged and staged[0] == str(Path(root).resolve()):
        overrides = staged[1]
    overrides = overrides or {}
    if not overrides and (root / 'devel-loop/loop_state/ledger-transactions/pending.json').exists():
        return ['pending ledger transaction; run self_improvement.py recover before reading records']
    try:
        open_issues = parse(root / OPEN, strict=True, text=overrides.get(str(OPEN)))
        closed_issues = parse(root / CLOSED, strict=True, text=overrides.get(str(CLOSED)))
    except ValueError as exc:
        return [str(exc)]
    errors: list[str] = []
    if not (root / OPEN).is_file():
        errors.append(f"missing {OPEN}")
    if not (root / CLOSED).is_file():
        errors.append(f"missing {CLOSED}")
    seen: dict[str, str] = {}
    for closed, issues in ((False, open_issues), (True, closed_issues)):
        for issue in issues:
            errors.extend(check_issue(root, issue, closed))
            if issue.uuid in seen:
                errors.append(f"duplicate ESX-team UUID {issue.uuid}: {seen[issue.uuid]} and {rel(root, issue.path)}")
            seen[issue.uuid] = rel(root, issue.path)
    for uuid, owner in root_uuids(root).items():
        if uuid in seen:
            errors.append(f"UUID {uuid} exists in both ESX-team and ESX ledgers ({owner})")
    expected = index_text(closed_issues)
    index = root / INDEX
    current = overrides.get(str(INDEX), index.read_text(encoding='utf-8') if index.is_file() else None)
    if current != expected:
        errors.append(f"{INDEX} is stale; run `python3 tools/esx/self_improvement.py index`")
    return errors


def classify(root: Path) -> list[str]:
    """Report likely operational entries still present in the ESX ledgers."""
    rows: list[str] = []
    for ledger in ROOT_LEDGERS:
        for issue in parse(root / ledger):
            sample = issue.title + "\n" + issue.text[:2000]
            process = len(PROCESS_HINTS.findall(sample))
            scientific = len(SCIENTIFIC_HINTS.findall(sample))
            if process >= 2 and process > scientific:
                rows.append(f"{ledger}:{issue.line}\t{issue.uuid}\t{issue.title}")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    listing = sub.add_parser("list")
    listing.add_argument("--status", choices=("open", "closed", "all"), default="all")
    inspect = sub.add_parser('inspect')
    inspect.add_argument('--family', choices=('team', 'esx'), default='team')
    inspect.add_argument('--issue', required=True)
    index = sub.add_parser("index")
    index.add_argument("--check", action="store_true")
    sub.add_parser("classify")
    sub.add_parser('plan')
    followup = sub.add_parser('followup')
    followup.add_argument('--issue', required=True)
    followup.add_argument('--disposition', choices=('implemented', 'deferred'), required=True)
    followup.add_argument('--reason', required=True)
    followup.add_argument('--evidence', metavar='PATH#SHA256',
                          help='for --disposition implemented: a process validation receipt as PATH#SHA256, where '
                               'PATH is the JSON written by `process_evidence.py --output PATH --source FILE -- '
                               'COMMAND` (it must record version 1 PASS) and SHA256 is the hash that command '
                               'printed. Example: devel-loop/self-improvement/assessments/x/check.json#3fa9...')
    promote = sub.add_parser('promote')
    promote.add_argument('--issue', required=True)
    promote.add_argument('--closure', required=True, help='JSON fields and sections; original sections preserved')
    promote.add_argument('--expected-sha256', required=True, help='hash of the original issue block')
    promote.add_argument('--apply', action='store_true')
    recovery = sub.add_parser('recover')
    recovery.add_argument('--rollback', action='store_true')
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == 'inspect':
        ledger = OPEN if args.family == 'team' else Path('open_issues.md')
        rows = [r for r in parse(root / ledger) if r.uuid == args.issue]
        if len(rows) != 1:
            raise ValueError('expected exactly one open issue')
        print(json.dumps({'issue': args.issue, 'sha256': hashlib.sha256(rows[0].text.encode()).hexdigest(),
                          'record': rows[0].text}, indent=2))
        return 0
    if args.command in ('plan', 'followup'):
        import team_retrospective
        if args.command == 'plan':
            due = team_retrospective.followup_due(root)
            value = {'required_followup': due, 'queue': [
                {'issue': r.uuid, 'status': r.fields.get('Status'), 'severity': r.fields.get('Severity'),
                 'required_before_next_start': r.uuid in due}
                for r in sorted(parse(root / OPEN), key=lambda r: (r.uuid not in due, r.uuid))]}
        else:
            value = team_retrospective.decide_followup(root, args.issue, args.disposition, args.reason, args.evidence)
        print(json.dumps(value, indent=2))
        return 0
    if args.command in ('promote', 'recover'):
        import ledger_transaction
        if args.command == 'recover':
            value = ledger_transaction.recover(root, rollback=args.rollback)
        else:
            closure = json.loads((root / args.closure).read_text())
            value = ledger_transaction.promote(root, 'team', args.issue, closure, args.expected_sha256, args.apply)
        print(json.dumps(value, indent=2))
        return 0

    if args.command == "check":
        errors = validate(root)
        for error in errors:
            print("ERROR:", error)
        if not errors:
            print(
                f"ESX-team self-improvement: PASS "
                f"({len(parse(root / OPEN))} open, {len(parse(root / CLOSED))} closed)"
            )
        return 1 if errors else 0
    if args.command == "list":
        groups = []
        if args.status in ("open", "all"):
            groups.append(("OPEN", parse(root / OPEN)))
        if args.status in ("closed", "all"):
            groups.append(("CLOSED", parse(root / CLOSED)))
        for label, issues in groups:
            for issue in issues:
                print(f"{label}\t{issue.uuid}\t{issue.fields.get('Status', '')}\t{issue.title}")
        return 0
    if args.command == "index":
        expected = index_text(parse(root / CLOSED))
        path = root / INDEX
        if args.check:
            return 0 if path.is_file() and path.read_text(encoding="utf-8") == expected else 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
        print(rel(root, path))
        return 0
    if args.command == "classify":
        for row in classify(root):
            print(row)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
