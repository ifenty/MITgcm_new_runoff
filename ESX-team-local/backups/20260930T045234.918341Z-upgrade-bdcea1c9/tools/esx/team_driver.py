#!/usr/bin/env python3
"""Measured outer-loop driver with coordinator usage receipts and durable stops.

No provider spend cap is imposed. Allocations are nominal expectations recorded so
an overrun can be reported; `max_iterations` is the loop's only enforced terminal
bound. Copilot bills in AI credits with no published exchange rate, so an explicit
USD liability per credit allocation is still required -- not to cap the run, but
because otherwise its cost cannot be measured at all. Unknown usage retains its
reservation so a retry cannot double-count. Original run ID, deadline and nominal
allocation survive restarts. Tests use injected fake executables.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid
import team_accounting as accounting
import team_budget as budget
import team_retrospective as retrospective
import bounded_command

ROOT = Path(__file__).resolve().parents[2]


def _run(root, *, host='claude', model=None, max_passes=5, usd=30, minutes=120,
        calls=500, turn_usd=5, credits=None, credit_usd_ceiling=None):
    root = Path(root).resolve()
    if type(max_passes) is not int or max_passes <= 0:
        raise ValueError('max-passes must be positive')
    state = root / '.claude/esx-loop.local.md'
    if not state.exists(): raise ValueError('start the Ralph loop first')
    if host == 'copilot' and (not accounting.number(credits) or not credits or
                              not accounting.number(credit_usd_ceiling) or not credit_usd_ceiling):
        raise ValueError('Copilot needs --max-ai-credits and --credit-usd-ceiling to measure cost at all; '
                         'its credit/dollar rate is unpublished. These record the expected cost, they do not cap it')
    cap = budget.limits(override={'usd':usd,'minutes':minutes,'calls':calls,'turn_usd':turn_usd,'corrections':2})
    path = root / accounting.STATE / 'run_budget.json'
    if path.exists():
        run_state = json.loads(path.read_text())
        if run_state['limits'] != cap: raise ValueError('existing run budget differs; resume with its original limits')
        if run_state.get('status') == 'finished': raise ValueError('finished run: explicitly archive run_budget.json before a new run')
    else:
        run_state = {'id':str(uuid.uuid4()),'limits':cap,'status':'running','created_at':accounting.now()}
        accounting.atomic(path, run_state)
    if 'created_at' not in run_state:
        ledger = json.loads(budget.file_for(root).read_text()) if budget.file_for(root).exists() else {}
        begun = ledger.get('scopes',{}).get('run:'+run_state['id'],{}).get('started',time.time())
        run_state['created_at'] = dt.datetime.fromtimestamp(begun,dt.timezone.utc).isoformat()
    run_state.setdefault('coordinator_session_id', str(uuid.uuid4()))
    accounting.atomic(path,run_state)
    failures = 0
    for attempt in range(max_passes):
        if not state.exists(): break
        prompt = state.read_text().split('---',2)[-1].strip()
        event = uuid.uuid4().hex
        folder = root / accounting.STATE / 'coordinator' / event
        folder.mkdir(parents=True)
        issue = None
        issue_cap = cap
        start_path = root/accounting.STATE/'issue-start.json'
        if start_path.exists():
            active = json.loads(start_path.read_text())
            closed = any(r.get('id')==active.get('id') and r.get('timestamp')==active.get('timestamp')
                         for r in accounting.rows(root/accounting.STATE/'loop_history.jsonl'))
            if active.get('id') and not closed:
                issue = active['id']; issue_cap, _ = budget.assignment(root,issue)
        # Reserving records the expected cost; it never refuses a launch.
        reservation = budget.reserve(root,event,issue or 'COORDINATOR-'+run_state['id'],issue_cap,
            run=run_state['id'],run_budget=cap,
            amount=credit_usd_ceiling if host == 'copilot' else min(turn_usd,issue_cap['turn_usd']))
        context = {'root':str(root),'folder':str(folder),'event_id':event,'tool_timeout':600}
        accounting.atomic(folder/'runtime_context.json',context)
        env = os.environ.copy(); env.pop('CLAUDECODE',None)
        env['CLAUDE_PROJECT_DIR'] = str(root)
        env['ESX_RUNTIME_CONTEXT'] = str(folder/'runtime_context.json')
        if host == 'claude':
            hook = {'hooks':{'PreToolUse':[{'matcher':'.*','hooks':[{'type':'command',
                'command':shlex.join([sys.executable,str(ROOT/'tools/esx/runtime_tool_hook.py')]),'timeout':10}]}]}}
            # No --max-budget-usd: the reservation is a recorded expectation, not a cap.
            command = [host,'--print','--output-format','stream-json','--verbose',
                       '--settings',json.dumps(hook),
                       '--resume' if run_state.get('session_started') else '--session-id',run_state['coordinator_session_id']]
        else:
            command = [host,'-p',prompt,'--session-id',run_state['coordinator_session_id'],
                       '--usage-output-file',str(folder/'usage.json')]
        if model: command += ['--model',model]
        (folder/'prompt.txt').write_text(prompt)
        accounting.atomic(folder/'invocation.json', {'argv':command,'host':host,'model':model})
        started = accounting.now(); error = None; proc = None
        print(f'Coordinator pass {attempt+1}: reserved ${reservation["reserved_usd"]:.2f}',flush=True)
        try:
            with accounting.phase(root, issue, 'coordination', role='arch'), (folder/'stdout.jsonl').open('w') as output, (folder/'stderr.txt').open('w') as stderr:
                proc = subprocess.Popen(command,cwd=root,env=env,stdin=subprocess.PIPE,
                                        stdout=output,stderr=stderr,text=True,start_new_session=True)
                proc.communicate(prompt if host=='claude' else None,
                                 timeout=max(.01,reservation['deadline']-time.time()))
        except (OSError,subprocess.TimeoutExpired,KeyboardInterrupt) as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            if proc is not None:
                bounded_command.terminate_group(proc.pid, proc); proc.wait()
        usage = accounting.stream_usage(folder/'stdout.jsonl') if host=='claude' else {
            'cost_usd':None,'tool_calls':None,'usage':json.loads((folder/'usage.json').read_text()) if (folder/'usage.json').exists() else None}
        if proc is None: usage['cost_usd'] = 0
        if host == 'claude' and proc is not None:
            if not usage.get('usage_complete') or usage.get('result_is_error') or usage.get('result_subtype') != 'success':
                error = error or 'provider returned missing, incomplete or failed result'
        if usage['cost_usd'] is not None and not accounting.number(usage['cost_usd']):
            error = 'invalid provider cost; retain full reservation'
            usage['cost_usd'] = None
        settlement = budget.settle(root,event,usage['cost_usd'])
        if settlement.get('provider_overshoot'): error = 'provider exceeded reservation; run stopped'
        record = {'event_id':event,'agent_type':'arch','issue_id':issue,'run_id':run_state['id'],
                  'session_id':run_state['coordinator_session_id'],'started_at':started,'finished_at':accounting.now(),
                  'status':'completed' if proc is not None and proc.returncode==0 and not error else 'failed',
                  'error':error,'provider':host,'budget':reservation,
                  'accounting_components':[{'event_id':event,'kind':'coordinator',**usage}]}
        accounting.atomic(folder/'record.json',record)
        if proc is not None: run_state['session_started'] = True
        accounting.atomic(path,run_state)
        failures = failures+1 if record['status']=='failed' else 0
        print(accounting.concise(accounting.summary(root, start=run_state['created_at'], end=accounting.now(), run_id=run_state['id'])),flush=True)
        if error or failures>=2: break
    run_state['status'] = 'paused' if state.exists() else 'finished'
    accounting.atomic(path,run_state)
    retrospective.persist_debt(root,'outer driver stopped: '+run_state['status'])
    return 3 if state.exists() else 0


def run(root, **kwargs):
    """Permit one coordinator per repository; ledger locking separately protects children."""
    path = Path(root)/accounting.STATE/'driver.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise ValueError('a coordinator is already running') from exc
        return _run(root, **kwargs)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--host',choices=('claude','copilot'),default='claude')
    p.add_argument('--model');p.add_argument('--max-passes',type=int,default=5)
    p.add_argument('--max-usd',type=float,default=30);p.add_argument('--max-minutes',type=float,default=120)
    p.add_argument('--max-calls',type=int,default=500);p.add_argument('--turn-usd',type=float,default=5)
    p.add_argument('--max-ai-credits',type=float);p.add_argument('--credit-usd-ceiling',type=float)
    a=p.parse_args()
    try:
        return run(a.root,host=a.host,model=a.model,max_passes=a.max_passes,usd=a.max_usd,
                   minutes=a.max_minutes,calls=a.max_calls,turn_usd=a.turn_usd,
                   credits=a.max_ai_credits,credit_usd_ceiling=a.credit_usd_ceiling)
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'blocked','error':str(exc)}));return 1


if __name__=='__main__': raise SystemExit(main())
