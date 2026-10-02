#!/usr/bin/env python3
"""Generate bounded role briefs with exact assignment and evidence interfaces."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import doc_contract
import footer_contract
from project import STATE, json_file, require
import project

SWEEP_LIMIT = 50
SWEEP_MAX_BYTES = 2 * 1024 * 1024
SWEEP_LINES_PER_FILE = 20


def current_seal(packet):
    """Standalone reviewer section naming the current sealed documentation report.

    Implementer corrections re-seal, so a confirming reviewer may still hold an
    earlier seal in context. This section is the required footer input.
    """
    report = packet['maintenance']['documentation']
    return ('# Current sealed documentation report (required footer input)\n'
            'path: ' + report['path'] + '\nsha256: ' + report['sha256'] + '\n'
            'Set documentation_review.report to exactly ' + json.dumps(report, sort_keys=True) + '. '
            'Read that exact file now. Do not assume it matches a report you saw in an earlier round: every '
            'correction re-seals, and a footer citing any other sha256 is rejected when your report is captured.')


def _sweep_candidates(root, cfg):
    """List project text files a symbol sweep reads, independent of the candidate.

    Stale documents are by definition ones the change did not touch, and they
    often live outside the scientific inventory (validation reports, notes), so
    the sweep covers the whole project tree: Git's tracked and unignored files
    when available, else a walk. Loop state, VCS internals, worktrees, output and
    archive roots and ESX self-improvement records are excluded.
    """
    names = None
    if (root / '.git').exists():
        run = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                             capture_output=True)
        if run.returncode == 0:
            names = [n for n in run.stdout.decode('utf-8', 'surrogateescape').split('\0') if n]
    if names is None:
        names = []
        for directory, folders, files in os.walk(root):
            base = Path(directory).relative_to(root)
            folders[:] = sorted(f for f in folders if f not in project.EXCLUDED_PARTS
                                and not (base / f).is_symlink())
            names.extend((base / f).as_posix() for f in files)
    skipped = cfg.get('output_paths', []) + cfg.get('archive_paths', []) + ['.claude/worktrees']
    for name in sorted(set(names)):
        if (project.EXCLUDED_PARTS.intersection(Path(name).parts) or project.mutable_loop_path(name)
                or project.administrative(name)
                or any(name == p or name.startswith(p.rstrip('/') + '/') for p in skipped)):
            continue
        path = root / name
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= SWEEP_MAX_BYTES:
            yield name, path


def sweep(root, symbols, limit=SWEEP_LIMIT):
    """Return (files, omitted) for every whole-word mention of the declared symbols.

    Each file entry keeps all of its mentioning line numbers; the cap applies to
    files, so one verbose file cannot push another mentioning file out of view.
    """
    root = Path(root).resolve()
    symbols = list(dict.fromkeys(symbols or ()))
    for symbol in symbols:
        require(isinstance(symbol, str) and symbol.strip() == symbol and symbol, f'invalid sweep symbol: {symbol!r}')
    if not symbols:
        return [], 0
    try:
        cfg = project.config(root, ready=False)
    except (ValueError, OSError):
        cfg = {}
    pattern = re.compile('(?<![A-Za-z0-9_])(?:' + '|'.join(re.escape(s) for s in symbols) + ')(?![A-Za-z0-9_])')
    files = []
    for name, path in _sweep_candidates(root, cfg):
        data = path.read_bytes()
        if b'\0' in data[:8192]:
            continue
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            continue
        lines = [number for number, line in enumerate(text.splitlines(), 1) if pattern.search(line)]
        if lines:
            files.append({'path': name, 'lines': lines})
    return files[:limit], max(0, len(files) - limit)


def sweep_section(root, symbols, limit=SWEEP_LIMIT, lines_per_file=SWEEP_LINES_PER_FILE):
    """Render the declared-symbol enumeration, or None when nothing is declared."""
    symbols = list(dict.fromkeys(symbols or ()))
    if not symbols:
        return None
    files, omitted = sweep(root, symbols, limit)
    names = ', '.join('`' + s + '`' for s in symbols)
    out = ['# Documents mentioning ' + names,
           'The coordinator declared that this change affects the meaning of ' + names + '. Every file below '
           'currently mentions it at the listed lines (whole-word match across the project tree, whether or not '
           'your change touches the file). Each is an explicit target: update every stale statement, or say in '
           'your report why it remains correct. A mention left stating the old meaning is a defect, not a follow-up.']
    for entry in files:
        shown = entry['lines'][:lines_per_file]
        more = len(entry['lines']) - len(shown)
        out.append('  ' + entry['path'] + ':' + ','.join(map(str, shown))
                   + (' (+%d more line(s) in this file)' % more if more else ''))
    if not files:
        out.append('  (no mentions found)')
    if omitted:
        out.append('  ... %d further mentioning file(s) omitted at the %d-file cap; run a whole-word search for the '
                   'full list.' % (omitted, limit))
    return '\n'.join(out)


WORKING_RULES = {
    False: '# Working rules\n'
           '- A comparison against an existing quantity calls or cites the function and line that computes it. '
           'Do not re-derive the formula: a re-derivation that differs by a factor passes a loose assertion and '
           'puts wrong figures in the record.\n'
           '- A characterization test asserts the measured figure with a stated margin, not only a loose bound '
           'that would also hold for a wrong figure.\n'
           '- After your last edit, search the repository for statements your change makes stale, including in '
           'files you did not otherwise touch (READMEs, contracts, validation reports), and correct them.\n'
           '- You draft and seal the documentation plan from the live source, reusing the last sealed report with '
           '`doc_contract.py draft --previous`, and report the sealed reference. Give each changed target its own '
           'judgment; do not copy one reason across targets.\n'
           '- Write each finished unit to disk before starting the next, so an interrupted turn loses one unit.',
    True: '# Working rules\n'
          '- Review against the supported input classes stated in the design. A real defect in a supported class '
          'is a must_fix. A real case outside them is a note with your evidence: the coordinator records it as a '
          'documented limit or a separate issue, and it does not block this one.\n'
          '- Check every reference quantity against the source line that computes it, not against the '
          'implementer\'s description of it.\n'
          '- Search for statements the change makes stale in files outside the change set; a stale statement the '
          'change caused is a must_fix.\n'
          '- Run your orientation command last, after your reading and checks.'}


def build(root, role, issue, design, question=None, packet=None, correction_round=0, sweep_symbols=()):
    start = json_file(root, STATE + '/issue-start.json')
    require(start['id'] == issue, 'brief must name the active issue')
    require(isinstance(design, str) and design.strip(), 'provide the bounded design and acceptance tests')
    if role == 'richard':
        require(question and packet, 'Richard needs a distinct question and reviewed packet')
        import agent_runtime
        agent_runtime.review_context(root, packet, issue, start['maintenance']['baseline'])
    context = packet or start
    nav = doc_contract.load(root, context['maintenance']['orientation'], 'orientation', issue)
    command = [sys.executable, 'tools/esx/doc_contract.py', 'navigate', '--issue', issue,
               '--baseline', json.dumps(nav['baseline']), '--role', role, '--map', nav['map']]
    for target in nav['targets']:
        command += ['--target', target]
    for doc in nav['documents']:
        command += ['--doc', doc]
    command += ['--use', 'Inspect the assigned owner and test to evaluate the bounded design and independent acceptance question.']
    footer = footer_contract.example(root, role)
    reseal = ('# Reseal before reporting\n'
              'Implementation normally edits the very targets this orientation was taken against, which '
              'invalidates the receipt and leaves an otherwise complete turn unreviewable. So as the FINAL steps '
              'after your last edit, in this order: re-run the orientation command above with your own --use '
              'sentence, then run ' + shlex.join([sys.executable, 'tools/esx/project.py', 'signature']) + '. Put '
              'both results in your footer. Running them before your last edit does not count; the receipt must '
              'bind to the bytes a reviewer will see.\nOriented targets, any of which triggers this:\n'
              + '\n'.join('  ' + target for target in nav['targets']))
    footer.update(issue_id=issue, iteration_timestamp=start['timestamp'], correction_round=correction_round)
    if role == 'richard':
        footer['documentation_review']['report'] = dict(packet['maintenance']['documentation'])
    swept = sweep_section(root, sweep_symbols)
    return '\n\n'.join([
        '# ' + role + ': ' + issue, '# Design and acceptance\n' + design, *([swept] if swept else []),
        '# Question\n' + (question or 'Implement the bounded design and report actual focused checks.'),
        '# Expected cost and effort\n' + json.dumps(start.get('budget', {})) +
        '\nThese are recorded expectations, not caps: nothing will stop you at them, and exceeding one is measured '
        'rather than refused. Report a partial handoff when the work genuinely reaches a clean stopping point, not '
        'because a number was reached. If you do exceed an expectation, say by how much and why -- that measurement '
        'is how the expectation gets corrected.',
        '# Own orientation\n' + shlex.join(command) + '\nUse the returned orientation receipt, not the baseline.',
        reseal,
        WORKING_RULES[role == 'richard'],
        '# Evidence\nUse tools/esx/project.py signature for candidate_signature. Execute independent checks through '
        'tools/esx/verify.py --suite focused --owner YOUR_RUNTIME_AGENT_ID --fresh and cite its returned evidence. '
        'Your runtime agent id is the agent_id in your dispatcher assignment (retained session) or the id stated '
        'in your session-start context (native subagent); `' + shlex.join([sys.executable, 'tools/esx/hooks.py',
        'whoami', '--role', role]) + '` prints it. Evidence sealed under any other owner is refused at closeout. '
        'Richard confirms the exact sealed documentation reference in this packet: ' + json.dumps(packet),
        *([current_seal(packet)] if role == 'richard' else []),
        '# Report\nKeep actual identity, evidence and limitations. Required values cannot be invented.\n```json\n'
        + json.dumps(footer, indent=2) + '\n```']) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument('--role', choices=('bob', 'richard'), required=True)
    p.add_argument('--issue', required=True)
    p.add_argument('--design', type=Path, required=True)
    p.add_argument('--question')
    p.add_argument('--packet', type=Path)
    p.add_argument('--round', type=int, default=0)
    p.add_argument('--output', type=Path)
    p.add_argument('--sweep-symbol', action='append', default=[], metavar='NAME',
                   help='a default, symbol or contract name whose meaning this change affects; repeatable. '
                        'The brief lists every file:line in the project that mentions it as an explicit target.')
    a = p.parse_args()
    value = build(a.root.resolve(), a.role, a.issue, (a.root / a.design).read_text(), a.question,
                  json.loads((a.root / a.packet).read_text()) if a.packet else None, a.round,
                  a.sweep_symbol)
    if a.output:
        (a.root / a.output).write_text(value)
    else:
        print(value, end='')


if __name__ == '__main__':
    main()
