#!/usr/bin/env python3
"""Atomic cost and effort measurement shared by coordinator, children and repairs.

These allocations are **nominal expectations, not caps**. Nothing here refuses a
launch or a tool call. Every dimension that is exceeded -- spend, wall clock, tool
calls, correction rounds, provider overshoot -- is recorded as a dated observation
on the scope, with its magnitude, so a retrospective can report what an iteration
actually cost against what was expected. The only enforced terminal bound in the
kit is the loop's own `max_iterations`.

Reserve before launch so a turn's expected cost is on record. Settle known usage
afterward; unknown or interrupted usage retains its entire reservation, so a retry
cannot silently double-count it. Scope identifiers and original deadlines stay
immutable, because monitoring is worthless if the baseline moves. Provider billing
overshoot is recorded, never misrepresented as a guarantee about an invoice.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import time
import team_accounting as accounting

DEFAULTS = {
    'scientific_small': {'minutes': 30, 'usd': 15, 'calls': 120, 'corrections': 1, 'turn_usd': 5},
    'scientific_change': {'minutes': 120, 'usd': 60, 'calls': 500, 'corrections': 2, 'turn_usd': 12},
    'harness_change': {'minutes': 45, 'usd': 20, 'calls': 180, 'corrections': 1, 'turn_usd': 5},
    'documentation': {'minutes': 30, 'usd': 15, 'calls': 120, 'corrections': 1, 'turn_usd': 5},
    'investigation': {'minutes': 45, 'usd': 20, 'calls': 180, 'corrections': 2, 'turn_usd': 5}}


class Exhausted(ValueError):
    """Retained for callers that still catch it. This module never raises it.

    Allocations are monitoring expectations rather than caps, so an exceeded
    dimension is recorded through `observe` instead of refusing the work.
    """


def observe(scope, dimension, expected, actual, detail):
    """Record one dated overrun observation, once per dimension, on a scope.

    Monitoring must not itself become a cost: repeated crossings of the same
    dimension update the observed magnitude rather than appending unboundedly.
    """
    overruns = scope.setdefault('overruns', {})
    entry = overruns.get(dimension)
    if entry is None:
        entry = {'dimension': dimension, 'expected': expected, 'first_observed_at': accounting.now(),
                 'observations': 0}
        overruns[dimension] = entry
    entry.update(actual=actual, detail=detail, last_observed_at=accounting.now())
    entry['observations'] += 1
    return entry


def scope_effort(root, key):
    """Summed dispatch duration for an issue scope, in minutes, or None.

    This is the effort measure. Elapsed calendar time is recorded separately and
    deliberately not conflated with it: a scope's clock starts at its first
    dispatch, so an issue carried across iterations accrues every hour spent on
    other work. Returns None when no dispatch record exists to measure.
    """
    if not key.startswith('issue:'):
        return None
    issue = key[len('issue:'):]
    path = Path(root) / accounting.STATE / 'dispatch_log.jsonl'
    if not path.is_file():
        return None
    total, seen = 0.0, False
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('issue_id') == issue and accounting.number(row.get('duration_seconds')):
            total += row['duration_seconds']
            seen = True
    return total / 60 if seen else None


def limits(kind='investigation', override=None):
    value = dict(DEFAULTS[kind])
    if override: value.update(override)
    if set(value) != set(DEFAULTS[kind]) or any(not accounting.number(n) for n in value.values()):
        raise ValueError('budget must contain finite nonnegative minutes/usd/calls/corrections/turn_usd')
    if any(value[k] <= 0 for k in ('minutes', 'usd', 'calls', 'turn_usd')):
        raise ValueError('time, spend and call budgets must be positive')
    if type(value['calls']) is not int or type(value['corrections']) is not int:
        raise ValueError('call and correction limits must be integers')
    return value


def file_for(root):
    return Path(root) / accounting.STATE / 'budget_ledger.json'


@contextmanager
def transaction(root, write=True):
    path = file_for(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = json.loads(path.read_text()) if path.exists() else {'version': 1, 'scopes': {}, 'reservations': {}}
        yield value
        if write:
            accounting.atomic(path, value)


def reserve(root, event, issue, budget, *, run=None, run_budget=None, correction=0, amount=None, turn_seconds=None, turn_calls=None):
    budget = limits(override=budget)
    amount = budget['turn_usd'] if amount is None else amount
    if not accounting.number(amount) or amount <= 0: raise ValueError('positive reservation required')
    if turn_seconds is not None and (not accounting.number(turn_seconds) or turn_seconds <= 0): raise ValueError('positive turn timeout required')
    if turn_calls is not None and (type(turn_calls) is not int or turn_calls <= 0): raise ValueError('positive turn call cap required')
    scopes = [('issue:' + issue, budget)]
    if run:
        scopes.append(('run:' + run, limits(override=run_budget or budget)))
    with transaction(root) as ledger:
        if event in ledger['reservations']: raise ValueError('event already reserved')
        for key, cap in scopes:
            saved = ledger['scopes'].setdefault(key, {'limits': cap, 'started': time.time(), 'calls': []})
            if saved['limits'] != cap: raise ValueError('budget cannot change/reset during scope: ' + key)
            # Nominal expectations. Each exceeded dimension is recorded and the
            # work proceeds; only the loop's own max_iterations terminates a run.
            # Effort is measured as summed dispatch duration, not calendar span.
            # A scope's clock starts at its first dispatch and an issue worked
            # across several iterations accrues every hour spent elsewhere, so
            # elapsed time is not a measure of effort: one issue here reported 437
            # calendar minutes against 92 minutes of actual dispatch.
            effort = scope_effort(root, key)
            if effort is not None and effort > cap['minutes']:
                observe(saved, 'minutes', cap['minutes'], effort,
                        'summed dispatch duration exceeds its expected allocation')
            deadline = saved.get('deadline', saved['started'] + cap['minutes'] * 60)
            if time.time() >= deadline:
                observe(saved, 'calendar_minutes', cap['minutes'], (time.time() - saved['started']) / 60,
                        'elapsed time since this scope first dispatched; includes work on other issues '
                        'and is not a measure of this issue effort')
            if correction > cap['corrections']:
                observe(saved, 'corrections', cap['corrections'], correction,
                        'correction round exceeds its expected allocation; consider a diagnosis checkpoint')
            spent = sum(r['charged_usd'] for r in ledger['reservations'].values() if key in r['scopes'])
            if spent + amount > cap['usd'] + 1e-8:
                observe(saved, 'usd', cap['usd'], spent + amount,
                        'reserved spend exceeds its expected allocation')
        # The returned deadlines bound THIS TURN's liveness; they are not a
        # cumulative cap. A scope whose nominal wall time already elapsed has its
        # overrun recorded above, but it must not hand back a past deadline: that
        # would kill every later turn at launch. So only still-future scope
        # deadlines constrain the turn, and the turn always gets a real horizon.
        now = time.time()
        horizon = now + turn_seconds if turn_seconds is not None else now + min(c['minutes'] for _, c in scopes) * 60
        soft_horizon = now + turn_seconds * .8 if turn_seconds is not None else now + min(c['minutes'] for _, c in scopes) * 48
        deadlines = [horizon] + [d for d in (ledger['scopes'][k].get('deadline', ledger['scopes'][k]['started'] + c['minutes'] * 60)
                                            for k, c in scopes) if d > now]
        soft_deadlines = [soft_horizon] + [d for d in (ledger['scopes'][k].get('soft_deadline', ledger['scopes'][k]['started'] + c['minutes'] * 48)
                                                      for k, c in scopes) if d > now]
        receipt = {'event_id': event, 'scopes': [k for k, _ in scopes], 'reserved_usd': amount,
                   'charged_usd': amount, 'reported_usd': None, 'status': 'reserved',
                   'deadline': min(deadlines), 'soft_deadline': min(soft_deadlines),
                   'call_limit': turn_calls, 'calls': []}
        ledger['reservations'][event] = receipt
    return receipt


def settle(root, event, reported):
    if reported is not None and not accounting.number(reported): raise ValueError('invalid provider amount')
    with transaction(root) as ledger:
        entry = ledger['reservations'][event]
        if entry['status'] != 'reserved':
            if entry['reported_usd'] != reported: raise ValueError('conflicting settlement')
            return entry
        entry.update(reported_usd=reported, charged_usd=reported if reported is not None else entry['reserved_usd'],
                     status='settled' if reported is not None else 'unknown_reserved')
        entry['provider_overshoot'] = reported is not None and reported > entry['reserved_usd'] + 1e-8
        # Recorded, never enforced: a provider charging more than expected is
        # information about the estimate, not grounds for refusing further work.
        if entry['provider_overshoot']:
            for key in entry['scopes']:
                observe(ledger['scopes'][key], 'provider_overshoot', entry['reserved_usd'], reported,
                        'provider reported more than this turn reserved')
    return entry


def allow_tool(root, event, tool_id):
    with transaction(root) as ledger:
        entry = ledger['reservations'][event]
        identity = event + ':' + tool_id
        if all(identity in ledger['scopes'][k]['calls'] for k in entry['scopes']): return
        # Effort monitoring only: crossing an expectation is recorded, never refused.
        if entry.get('call_limit') and len(entry['calls']) >= entry['call_limit']:
            for key in entry['scopes']:
                observe(ledger['scopes'][key], 'turn_calls', entry['call_limit'], len(entry['calls']) + 1,
                        'turn made more tool calls than expected')
        for key in entry['scopes']:
            scope = ledger['scopes'][key]
            if time.time() >= entry['soft_deadline']:
                observe(scope, 'soft_deadline', scope['limits']['minutes'],
                        (time.time() - scope['started']) / 60,
                        'turn continued past the point a partial handoff was expected')
            if len(scope['calls']) >= scope['limits']['calls']:
                observe(scope, 'calls', scope['limits']['calls'], len(scope['calls']) + 1,
                        'scope made more tool calls than expected')
        identity = event + ':' + tool_id
        for key in entry['scopes']:
            calls = ledger['scopes'][key]['calls']
            if identity not in calls: calls.append(identity)
        entry.setdefault('calls', []).append(identity)


def assignment(root, issue):
    path = Path(root) / accounting.STATE / 'issue-start.json'
    start = json.loads(path.read_text()) if path.exists() else {}
    if start.get('id') != issue: start = {}
    kind = (start.get('workflow') or {}).get('kind', 'investigation')
    budget = limits(kind, start.get('budget'))
    # An explicit owner-authorized extension updates this same cumulative scope.
    ledger_path = file_for(root)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    existing = ledger.get('scopes', {}).get('issue:' + issue)
    if existing:
        budget = limits(override=existing['limits'])
    run_path = Path(root) / accounting.STATE / 'run_budget.json'
    run = json.loads(run_path.read_text()) if run_path.exists() else {}
    return budget, run


def scope_digest(scope):
    return hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()


def extend(root, authorization, apply=False):
    """Preview/apply a recorded Owner revision of the nominal allocation.

    Allocations no longer gate work, so this is not a way to unblock anything. It
    exists to correct an expectation that measurement has shown to be wrong, so
    that later monitoring compares against a realistic baseline instead of
    reporting a permanent overrun. Prior spend and calls are never reset.

    Authorization is an operator-supplied hashed JSON reference, not something a
    role may invent. CAS and unique authorization IDs make stale/repeated requests
    safe. Active reservations still require resolution first, because revising a
    baseline mid-turn would make that turn's own measurement uninterpretable.
    """
    from process_evidence import reference
    request = json.loads(reference(root, authorization))
    for key in ('issue', 'authorization_id', 'evidence', 'reason', 'expected_scope_sha256'):
        if not isinstance(request.get(key), str) or not request[key].strip():
            raise ValueError('authorization missing ' + key)
    if request.get('authorized_by') != 'Owner':
        raise ValueError('explicit Owner authorization required')
    additions = {key: request.get('add_' + key, 0) for key in ('usd', 'minutes', 'calls', 'corrections')}
    if any(not accounting.number(n) for n in additions.values()) or additions['minutes'] <= 0:
        raise ValueError('nonnegative allocations and positive additional minutes required')
    if any(type(additions[k]) is not int for k in ('calls', 'corrections')):
        raise ValueError('additional calls/corrections must be integers')
    with transaction(root, write=apply) as ledger:
        key = 'issue:' + request['issue']
        scope = ledger['scopes'][key]
        prior = next((r for r in scope.get('extensions', [])
                      if r['request']['authorization_id'] == request['authorization_id']), None)
        if prior:
            if prior['request'] != request:
                raise ValueError('conflicting authorization ID')
            return {'status': 'already_applied', 'scope': scope}
        if scope_digest(scope) != request['expected_scope_sha256']:
            raise ValueError('scope changed since authorization; refresh its expected hash')
        if any(key in r['scopes'] and r['status'] == 'reserved' for r in ledger['reservations'].values()):
            raise ValueError('cannot extend with active reservations')
        updated = json.loads(json.dumps(scope))
        for name, amount in additions.items():
            updated['limits'][name] += amount
        updated['limits'] = limits(override=updated['limits'])
        begun = max(time.time(), scope.get('deadline', scope['started'] + scope['limits']['minutes'] * 60))
        updated['deadline'] = begun + additions['minutes'] * 60
        updated['soft_deadline'] = begun + additions['minutes'] * 48
        updated.setdefault('extensions', []).append({'request': request, 'authorization': authorization,
                                                    'applied_at': accounting.now()})
        if apply:
            ledger['scopes'][key] = updated
        return {'status': 'applied' if apply else 'preview', 'scope': updated,
                'retained_charged_usd': sum(r['charged_usd'] for r in ledger['reservations'].values() if key in r['scopes'])}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect')
    inspect.add_argument('--issue', required=True)
    renewal = sub.add_parser('extend')
    renewal.add_argument('--authorization', required=True, help='repository path#sha256 of Owner request')
    renewal.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.command == 'inspect':
        ledger = json.loads(file_for(args.root).read_text())
        scope = ledger['scopes']['issue:' + args.issue]
        result = {'scope': scope, 'expected_scope_sha256': scope_digest(scope)}
    else:
        result = extend(args.root, args.authorization, args.apply)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
