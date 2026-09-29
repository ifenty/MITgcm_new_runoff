"""Local deployment, instruction-link, code-map and project-record checks.

These checks establish structure and resolvable references. Runtime availability,
scientific truth and understanding of prose require the assigned people/agents.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from project import ROLES, config, local, require, mutable_loop_path
from records import validate_records


def audit_code_map(root):
    from doc_inventory import excerpt
    findings = []
    text = local(root, 'docs/code_map.md').read_text()
    if 'TODO_ESX' in text:
        findings.append('complete docs/code_map.md')
    for ref in re.findall(r'`([^`\n]+::[^`\n]+)`', text):
        try:
            excerpt(root, ref)
        except (ValueError, OSError, SyntaxError) as exc:
            findings.append(str(exc))
    return {'findings': findings}


def audit_mirrors(root, cfg):
    """Flag a mirror whose bytes have drifted from its configured canonical source.

    Some build/compile steps need their own local copy of shared source
    because no import mechanism is available at that layer (e.g. per-experiment
    Fortran instrumentation copied into several build directories). A mirror
    silently going stale relative to its canonical source is real, previously
    invisible data-corruption risk, not merely untidiness -- this is a
    generalization of a stale-Fortran-instrumentation bug found in a real
    project (see self-improvement/improvements_2026-09-23_from_1D_Mixing_Experiment.md).
    """
    findings = []
    for entry in cfg.get('mirrored_paths', []):
        canonical_path = local(root, entry['canonical'])
        if not canonical_path.is_file():
            findings.append(f"mirrored_paths: canonical file missing: {entry['canonical']}")
            continue
        canonical_bytes = canonical_path.read_bytes()
        for mirror in entry['mirrors']:
            mirror_path = local(root, mirror)
            if not mirror_path.exists():
                findings.append(f"{mirror}: missing entirely (should mirror {entry['canonical']})")
            elif mirror_path.read_bytes() != canonical_bytes:
                findings.append(f"{mirror}: drifted from canonical source {entry['canonical']}")
    return {'findings': findings}


def audit_instructions(root, files=None, cfg=None):
    """Check that every relative Markdown link and heading anchor resolves.

    An explicit `files` list is checked as given. Discovery instead skips loop
    state, administrative records and configured `archive_paths` documentation,
    whose links describe a superseded layout on purpose.
    """
    from doc_inventory import markdown_sections
    from project import administrative, archived, config
    if files is None and cfg is None:
        cfg = config(root, ready=False)
    names = files or [p.relative_to(root).as_posix() for folder in ('.claude', 'devel-loop', 'docs', 'esx')
                      for p in (root / folder).rglob('*.md') if 'loop_state' not in p.parts and not mutable_loop_path(p.relative_to(root).as_posix())
                      and not administrative(p.relative_to(root).as_posix())
                      and not archived(p.relative_to(root).as_posix(), cfg)]
    if files is None:
        names.append('CLAUDE.md')
    findings = []
    for name in names:
        text = local(root, name).read_text()
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if re.match(r'^[a-zA-Z][\w+.-]*:', target):
                continue
            part, _, anchor = target.strip('<>').partition('#')
            path = (root / name).parent / part if part else root / name
            if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
                findings.append(f'{name}: missing/locality-invalid link {target}')
            elif anchor and path.suffix == '.md' and anchor not in markdown_sections(path.read_text()):
                findings.append(f'{name}: unresolved heading {target}')
    return {'findings': findings}


def check(root, overrides=None):
    cfg = config(root)
    validate_records(root, overrides)
    import self_improvement
    if (root / self_improvement.OPEN).exists():
        errors = self_improvement.validate(root, overrides)
        require(not errors, '; '.join(errors))
    for name in ('project.py', 'loop_gate.py', 'verify.py', 'records.py', 'hooks.py',
                 'audit.py', 'doc_inventory.py', 'doc_contract.py', 'workflow_policy.py', 'orient.py',
                 'agent_runtime.py', 'notifications.py', 'ralph_stop.py', 'loop_control.py', 'check_ralph_hook.py',
                 'issue_candidates.py', 'workflow_records.py', 'final_verification.py',
                 'team_accounting.py', 'team_budget.py', 'team_retrospective.py', 'self_improvement.py',
                 'loop_iteration.py', 'ledger_transaction.py', 'process_evidence.py', 'brief.py',
                 'footer_contract.py', 'bounded_command.py', 'runtime_tool_hook.py', 'team_driver.py', 'loop_lifecycle.py',
                 'closeout_doctor.py'):
        require(local(root, 'tools/esx/' + name).is_file(), f'missing framework utility: {name}')
    require(local(root, '.claude/commands/esx-loop.md').is_file(), 'missing /esx-loop command')
    require(local(root, 'devel-loop/autonomous_prompt.md').is_file(), 'missing autonomous loop prompt')
    for skill in ('common', 'verify', 'code-map', 'investigate', 'announce', 'instruction-audit'):
        require(local(root, f'.claude/skills/esx-{skill}/SKILL.md').is_file(), f'missing ESX skill: {skill}')
    for role in ROLES[1:]:
        path = local(root, f'.claude/agents/{role}.md')
        text = path.read_text()
        require(text.startswith('---\n') and f'name: {role}\n' in text, f'{role}: invalid role frontmatter')
        require('Read' in text, f'{role}: needs Read access for on-demand skills')
        for ref in re.findall(r'`(\.claude/skills/[^`\n]+/SKILL\.md)`', text):
            require(local(root, ref).is_file(), f'{role}: missing on-demand skill {ref}')
    settings = json.loads(local(root, '.claude/settings.json').read_text())
    for event, marker in [('SessionStart', 'session-start'), ('SubagentStop', 'subagent-stop'), ('PostToolUse', 'records')]:
        entries = settings.get('hooks', {}).get(event, [])
        matches = [hook for entry in entries for hook in entry.get('hooks', [])
                   if 'tools/esx/hooks.py' in hook.get('command', '') and marker in hook.get('command', '')]
        require(len(matches) == 1, f'{event}: install exactly one ESX {marker} hook')
    from check_ralph_hook import check as check_stop
    check_stop(root)
    findings = audit_code_map(root)['findings'] + audit_instructions(root, cfg=cfg)['findings'] + audit_mirrors(root, cfg)['findings']
    require(not findings, '\n'.join(findings))
    return {'status': 'PASS', 'roles': 6, 'map_and_links': 'checked', 'records': 'checked'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.root.resolve()), indent=2))
    except (ValueError, OSError, KeyError, TypeError, SyntaxError) as exc:
        parser.exit(1, f'ESX audit: {exc}\n')
