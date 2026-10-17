#!/usr/bin/env python3
"""Reconcile ESX effort and provider-reported costs without inventing missing data.

Read retained turns (including historical repair streams), coordinator receipts,
phase events and Arch self-reports. JSON summaries preserve source IDs and
coverage gaps. The ``phase`` context manager appends a timed event, attributed to
a role when the caller knows it. The interactive main session (Arch) is never
dispatched, so ``record-arch`` lets it append a self-reported, sourced record of
its coordination time and cost; those are kept in a separate ``coordinator``
block and never added to dispatched-agent figures. The summary CLI is read-only
unless --output is supplied. No API calls or price assumptions.
Tests: test_team_operations.py, test_coordinator_cost.py.
"""
import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
STATE = Path('devel-loop/loop_state')
SELF_REPORTS = 'coordinator_self_reports.jsonl'
PHASES = ('orientation', 'implementation', 'review', 'verification', 'closeout', 'retrospective', 'waiting', 'coordination')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timestamp(value):
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('timestamp needs a timezone')
    return stamp.timestamp()


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(payload, f, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(payload, allow_nan=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


@contextmanager
def phase(root, issue, name, reason=None, role=None):
    if name not in PHASES or (name == 'waiting' and not reason):
        raise ValueError('phase needs a known name and waits need a reason')
    event = {'event_id': uuid.uuid4().hex, 'issue_id': issue, 'phase': name,
             'started_at': now(), 'reason': reason}
    if role:
        event['role'] = role
    started = time.monotonic()
    try:
        yield event
    finally:
        event.update(finished_at=now(), seconds=time.monotonic() - started)
        append(Path(root) / STATE / 'phase_events.jsonl', event)


def stream_usage(path):
    """Deduplicate streaming message/tool IDs; final result owns cost/usage."""
    final, tools, messages = None, set(), {}
    if path.exists():
        with path.open() as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get('type') == 'result':
                    final = row
                if row.get('type') == 'assistant':
                    message = row.get('message') or {}
                    if message.get('id'):
                        messages[message['id']] = message.get('usage') or {}
                    for item in message.get('content') or []:
                        if isinstance(item, dict) and item.get('type') == 'tool_use' and item.get('id'):
                            tools.add(item['id'])
    usage = (final or {}).get('usage')
    if usage is None and messages:
        usage = {k: sum(v.get(k, 0) for v in messages.values()) for k in
                 ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')}
    return {'cost_usd': (final or {}).get('total_cost_usd'), 'usage': usage,
            'tool_calls': len(tools), 'usage_complete': final is not None,
            'model_usage': (final or {}).get('modelUsage'),
            'result_subtype': (final or {}).get('subtype'), 'result_is_error': (final or {}).get('is_error')}


def turns(root):
    root = Path(root)
    entries = []
    for path in sorted((root / STATE / 'agent_runtime/sessions').glob('*/turns/*/record.json')):
        record = json.loads(path.read_text())
        components = record.get('accounting_components')
        if components is None:
            components = [{'event_id': record['event_id'], 'cost_usd': record.get('cost_usd'),
                           'usage': record.get('usage'), 'tool_calls': record.get('tool_calls'), 'kind': 'turn'}]
            for repair in sorted(path.parent.glob('repair-*.jsonl')):
                components.append({'event_id': repair.stem, 'kind': 'repair', **stream_usage(repair)})
        entries.append({**record, 'accounting_components': components, 'source': str(path.relative_to(root))})
    for path in sorted((root / STATE / 'coordinator').glob('*/record.json')):
        entries.append({**json.loads(path.read_text()), 'source': str(path.relative_to(root))})
    captured = {r['event_id'] for r in entries}
    for record in rows(root / STATE / 'dispatch_log.jsonl'):
        if record.get('runtime') == 'native_subagent' and record.get('event_id') not in captured:
            entries.append(dict(record, source=str(STATE / 'dispatch_log.jsonl'),
                accounting_components=[{'event_id': record['event_id'], 'cost_usd': None,
                    'usage': None, 'tool_calls': None, 'kind': 'unmetered_native'}]))
    unique = {}
    for entry in entries:
        key = entry['event_id']
        if key in unique:
            raise ValueError('duplicate accounting event: ' + key)
        unique[key] = entry
    return list(unique.values())


def union_seconds(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end < start:
            raise ValueError('negative interval')
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return sum(b - a for a, b in merged)


def record_arch(root, issue, name, minutes, source, usd=None):
    """Append one self-reported Arch (main session) record for an iteration phase.

    Tools cannot observe the interactive session, so the figure and its
    provenance come from Arch (e.g. the host's session cost). Recording after
    --check-done attaches the record to the issue's just-closed iteration.
    """
    root = Path(root)
    if not isinstance(issue, str) or not issue.strip(): raise ValueError('record the issue id')
    if name not in PHASES: raise ValueError('unknown phase: ' + str(name))
    if not number(minutes) or minutes <= 0: raise ValueError('minutes must be a positive finite number')
    if usd is not None and not number(usd): raise ValueError('usd must be a non-negative finite number')
    if not isinstance(source, str) or len(source.strip()) < 8:
        raise ValueError('state where the figure came from (--source, at least 8 characters)')
    attach = None
    start_path = root / STATE / 'issue-start.json'
    active = json.loads(start_path.read_text()) if start_path.exists() else {}
    closed = [r for r in rows(root / STATE / 'loop_history.jsonl') if r.get('id') == issue]
    if closed and not (active.get('id') == issue and active.get('timestamp') != closed[-1].get('timestamp')):
        attach = closed[-1].get('start_timestamp') or closed[-1]['timestamp']
    record = {'record_id': uuid.uuid4().hex, 'issue_id': issue, 'role': 'arch', 'kind': 'self_reported',
              'phase': name, 'minutes': minutes, 'usd': usd, 'source': source.strip(),
              'recorded_at': now(), 'iteration_start': attach}
    append(root / STATE / SELF_REPORTS, record)
    return record


def snapshot(root):
    """One fresh read per report, shared by issue summaries; never cached across runs."""
    return {'turns': turns(root), 'phases': rows(Path(root) / STATE / 'phase_events.jsonl'),
            'self_reports': rows(Path(root) / STATE / SELF_REPORTS)}


def coordinator(roles, phase_spans, reports, start, end, issue):
    """Arch figures kept apart from dispatched-agent totals, each with its provenance."""
    chosen = []
    for r in reports:
        if issue and r.get('issue_id') != issue: continue
        if r.get('iteration_start') and start:
            if timestamp(r['iteration_start']) != timestamp(start): continue
        elif (start and timestamp(r['recorded_at']) < timestamp(start)) or (end and timestamp(r['recorded_at']) > timestamp(end)):
            continue
        chosen.append(r)
    driver = roles.get('arch')
    coverage = 'recorded' if driver or chosen else 'missing'
    usd = [r['usd'] for r in chosen if r.get('usd') is not None]
    return {'coverage': coverage,
            'tool_measured': {'elapsed_seconds': union_seconds(phase_spans),
                              'effort_seconds': sum(b - a for a, b in phase_spans), 'events': len(phase_spans),
                              'basis': 'wall time of gate commands run as arch; excludes interactive session time'},
            'provider_reported_usd': driver['reported_usd'] if driver else None,
            'self_reported': {'minutes': sum(r['minutes'] for r in chosen) if chosen else None,
                              'usd': sum(usd) if usd else None,
                              'records_without_usd': sum(r.get('usd') is None for r in chosen),
                              'records': [{k: r.get(k) for k in ('record_id', 'phase', 'minutes', 'usd', 'source', 'recorded_at')}
                                          for r in chosen]},
            'included_in_reported_usd': 'provider_reported_only' if driver else 'no'}


def cost_scope(report):
    """One sentence stating whether coordinator cost is part of the cost figures."""
    c = report['coordinator']
    base = 'cost_usd and span-based figures describe dispatched agents'
    if c['coverage'] == 'missing':
        return (base + ' only; coordinator (Arch) cost is NOT included: no Arch accounting record exists '
                'for this iteration (record one with team_accounting.py record-arch)')
    parts = []
    if c['provider_reported_usd'] is not None:
        parts.append(f"team_driver Arch provider-reported ${c['provider_reported_usd']:.2f} (the only arch entry in cost_usd)")
    s = c['self_reported']
    if s['minutes'] is not None:
        usd = f"${s['usd']:.2f}" if s['usd'] is not None else 'cost unknown'
        parts.append(f"Arch self-reported {s['minutes']:g} min, {usd} (coordinator.self_reported; not added to cost_usd)")
    return base + '; coordinator cost is recorded separately: ' + '; '.join(parts)


def summary(root, issue=None, start=None, end=None, *, evidence=None, run_id=None):
    root = Path(root)
    evidence = snapshot(root) if evidence is None else evidence
    selected = [r for r in evidence['turns'] if issue is None or r.get('issue_id') == issue]
    if run_id: selected = [r for r in selected if r.get('run_id') == run_id
                           or 'run:'+run_id in (r.get('budget') or {}).get('scopes', [])]
    # Bound repeated iterations by observed overlap, never by round counters.
    if start:
        selected = [r for r in selected if timestamp(r.get('finished_at') or r.get('ts')) >= timestamp(start)]
    if end:
        selected = [r for r in selected if timestamp(r.get('started_at') or r.get('ts')) <= timestamp(end)]
    roles, components, seen, intervals = {}, [], set(), []
    for r in selected:
        role = r.get('agent_type', 'unknown')
        group = roles.setdefault(role, {'dispatches': 0, 'rounds': set(), 'seconds': 0.,
                                        'reported_usd': 0., 'unknown_cost_events': 0, 'tool_calls': 0,
                                        'unknown_tool_call_events': 0, 'usage': {}})
        group['dispatches'] += 1
        group['rounds'].add((r.get('session_id'), r.get('correction_round', 0)))
        if r.get('started_at') and r.get('finished_at'):
            a, b = timestamp(r['started_at']), timestamp(r['finished_at'])
            if start: a = max(a, timestamp(start))
            if end: b = min(b, timestamp(end))
            if b >= a:
                if role != 'arch': intervals.append((a, b))
                group['seconds'] += b - a
        for c in r.get('accounting_components') or [r]:
            key = c['event_id']
            if key in seen:
                raise ValueError('duplicate cost component: ' + key)
            seen.add(key)
            cost = c.get('cost_usd')
            if cost is not None and not number(cost):
                raise ValueError('invalid cost for ' + key)
            group['reported_usd'] += cost or 0
            group['unknown_cost_events'] += cost is None
            calls = c.get('tool_calls')
            group['tool_calls'] += calls or 0
            group['unknown_tool_call_events'] += calls is None
            for k, v in (c.get('usage') or {}).items():
                if k.endswith('tokens') and number(v):
                    group['usage'][k] = group['usage'].get(k, 0) + v
            components.append({'event_id': key, 'parent_event_id': r['event_id'], 'role': role,
                               'kind': c.get('kind', 'turn'), 'reported_usd': cost, 'source': r['source']})
    for group in roles.values(): group['rounds'] = len(group['rounds'])
    span = timestamp(end) - timestamp(start) if start and end else None
    if span is not None and span < 0: raise ValueError('close predates start')
    phases = [r for r in evidence['phases'] if not issue or r['issue_id'] == issue]
    phases = [r for r in phases if (not start or timestamp(r.get('finished_at') or r.get('ts')) >= timestamp(start))
              and (not end or timestamp(r.get('started_at') or r.get('ts')) <= timestamp(end))]
    by_phase, arch_spans = {}, []
    for event in phases:
        a, b = timestamp(event['started_at']), timestamp(event['finished_at'])
        if start: a = max(a, timestamp(start))
        if end: b = min(b, timestamp(end))
        if b >= a:
            by_phase.setdefault(event['phase'], []).append((a,b))
            if event.get('role') == 'arch': arch_spans.append((a, b))
    phase_totals = {name: {'elapsed_seconds': union_seconds(spans),
                          'effort_seconds': sum(b-a for a,b in spans), 'events': len(spans)}
                    for name,spans in by_phase.items()}
    child = union_seconds(intervals)
    arch = coordinator(roles, arch_spans, evidence.get('self_reports', []), start, end, issue)
    return {'schema_version': 2, 'issue_id': issue, 'start': start, 'end': end,
            'span_seconds': span, 'child_elapsed_seconds': child,
            'outside_child_intervals_seconds': max(0, span - child) if span is not None else None,
            'by_role': roles, 'reported_usd': sum(c['reported_usd'] or 0 for c in components),
            'unknown_cost_event_ids': [c['event_id'] for c in components if c['reported_usd'] is None],
            'coordinator_coverage': arch['coverage'], 'coordinator': arch,
            'billing_status': 'provider_reported_not_invoice_reconciled',
            'missing_timing_event_ids': [r['event_id'] for r in selected if not r.get('started_at') or not r.get('finished_at')],
            'by_phase': phase_totals, 'phase_events': phases, 'components': components}


def measured(report):
    """Canonical retrospective fields, including honest unknown coverage."""
    c = report['coordinator']
    return {'span_minutes': round(report['span_seconds'] / 60) if report['span_seconds'] is not None else None,
            'dispatches': {r: v['dispatches'] for r, v in report['by_role'].items()},
            'rounds': {r: v['rounds'] for r, v in report['by_role'].items()},
            'cost_usd': {r: v['reported_usd'] for r, v in report['by_role'].items()},
            'unknown_cost_event_ids': report['unknown_cost_event_ids'],
            'coordinator_coverage': report['coordinator_coverage'], 'billing_status': report['billing_status'],
            'coordinator': {'tool_measured_minutes': round(c['tool_measured']['effort_seconds'] / 60, 1),
                            'self_reported_minutes': c['self_reported']['minutes'],
                            'self_reported_usd': c['self_reported']['usd'],
                            'provider_reported_usd': c['provider_reported_usd']},
            'cost_scope': cost_scope(report)}


def concise(report):
    span = report['span_seconds']
    elapsed = f'{span / 60:.1f} min' if span is not None else 'elapsed unknown'
    return (f"{report['issue_id'] or 'RUN'}: {elapsed}; child elapsed {report['child_elapsed_seconds']/60:.1f} min; "
            f"reported ${report['reported_usd']:.2f}; unknown costs {len(report['unknown_cost_event_ids'])}; "
            f"Arch {report['coordinator_coverage']}; not invoice reconciled\n{cost_scope(report)}")


def main(argv=None):
    import sys
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['record-arch']:
        p = argparse.ArgumentParser(prog='team_accounting.py record-arch', description=record_arch.__doc__)
        p.add_argument('--root', type=Path, default=ROOT)
        p.add_argument('--issue', required=True); p.add_argument('--phase', required=True, choices=PHASES)
        p.add_argument('--minutes', type=float, required=True); p.add_argument('--usd', type=float)
        p.add_argument('--source', required=True, help='provenance, e.g. "Claude Code /cost at closeout"')
        a = p.parse_args(argv[1:])
        try:
            print(json.dumps(record_arch(a.root, a.issue, a.phase, a.minutes, a.source, a.usd), indent=2))
        except ValueError as exc:
            print(json.dumps({'status': 'blocked', 'reason': str(exc)})); return 1
        return 0
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--issue'); p.add_argument('--start'); p.add_argument('--end')
    p.add_argument('--output', type=Path); p.add_argument('--concise', action='store_true')
    a = p.parse_args(argv)
    report = summary(a.root, a.issue, a.start, a.end)
    if a.output: atomic(a.output, report)
    print(concise(report) if a.concise else json.dumps(report, indent=2))
    return 0


if __name__ == '__main__': raise SystemExit(main())
