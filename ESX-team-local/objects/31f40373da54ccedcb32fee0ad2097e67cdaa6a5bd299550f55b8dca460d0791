#!/usr/bin/env python3
"""Retained Claude CLI role sessions and truthful dispatch evidence.

``start`` creates a persisted ``claude --agent ROLE --session-id UUID`` session;
``followup`` uses ``--resume UUID`` and refuses a changed runtime contract.
The bridge is an explicit alternative transport when native subagent messaging
is unavailable. It does not resume native Agent IDs. Each role's tools, model,
skills and current project permissions remain effective. Concurrent turns on
one identity are refused; separate identities can run concurrently.

Reports, input, stderr, runtime output and timing are saved locally. A successful
process without a matching structured footer is incomplete. Provider errors,
timeouts and identity mismatches are failures. Neither can serve as a completed
review. ``probe`` exercises actual retained history with two provider requests;
unit tests use a fake executable and establish only transport behavior.
See the deployment kit tests/test_runtime.py; live qualification is explicit.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import threading
import uuid
import runtime_recovery
import team_accounting
import team_budget
import team_retrospective
import footer_contract
import shlex

TOOL_CALL_TIMEOUT_S = 600
WATCHDOG_POLL_S = 0.1
from project import local


ROOT = Path(__file__).resolve().parents[2]
ROLES = {"bob", "richard", "scout", "prober", "bisector", "auditor"}
CONFIG_ENV = {"CLAUDE_CONFIG_DIR", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
              "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_EFFORT_LEVEL",
              "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value, out, indent=2)
            out.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def reference(path, root):
    path = Path(path)
    try:
        name = str(path.relative_to(root))
    except ValueError:
        name = str(path)
    return {"path": name, "sha256": digest(path.read_bytes())}


@contextmanager
def locked(path):
    """Reject simultaneous turns while releasing the lock on crashes/exceptions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("session already has a running turn") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def append_record(root, record):
    log = local(Path(root), "devel-loop/loop_state/dispatch_log.jsonl")
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as out:
        fcntl.flock(out, fcntl.LOCK_EX)
        out.write(json.dumps(record) + "\n")
        out.flush()


def footer_from(message):
    """Read the final JSON fence only; malformed final reports cannot reuse an earlier one."""
    matches = list(re.finditer(r"```json\s*\n?(.*?)```", message, re.S))
    if not matches:
        return None
    try:
        value = json.loads(matches[-1].group(1))
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def transcript_report(path):
    """The subagent's final report from its own transcript: the last SubagentHandback
    message, else the last assistant text. Never another agent's or the parent's text."""
    try:
        lines = Path(path).read_text(errors="replace").splitlines() if path else []
    except (OSError, TypeError, ValueError):
        return None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        message = row.get("message") if isinstance(row, dict) else None
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
        for block in reversed(blocks):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "SubagentHandback":
                text = (block.get("input") or {}).get("message")
                if isinstance(text, str) and text.strip():
                    return text
            if block.get("type") == "text" and isinstance(block.get("text"), str) and block["text"].strip():
                return block["text"]
    return None


def stop_record(root, event, *, transport="native_subagent"):
    """Persist a native hook stop without equating a stop with a completed report."""
    event = event if isinstance(event, dict) else {}
    message = event.get("last_assistant_message") or ""
    if not isinstance(message, str):
        message = ""
    report_source = "last_assistant_message"
    if footer_from(message) is None:
        # A subagent may deliver its report through the SubagentHandback tool, leaving
        # the final assistant text empty; recover the same report from its transcript.
        recovered = transcript_report(event.get("agent_transcript_path"))
        if recovered and footer_from(recovered) is not None:
            message, report_source = recovered, "agent_transcript"
    footer = footer_from(message)
    status, error = "completed", None
    if event.get("is_error") or event.get("error"):
        status, error = "failed", str(event.get("error") or "runtime reported an error")
    elif event.get("stop_reason") not in (None, "end_turn", "stop_sequence"):
        status, error = "incomplete", "runtime did not finish its report"
    elif not event.get("agent_id") or not event.get("agent_type"):
        status, error = "incomplete", "missing runtime identity"
    elif not footer or footer.get("agent", footer.get("agent_name")) != event.get("agent_type"):
        status, error = "incomplete", "missing, malformed, or mismatched structured footer"
    event_id = uuid.uuid4().hex
    report_path = local(Path(root), "devel-loop/loop_state/agent_reports/" + event_id + ".md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(message)
    record = {
        "event_id": event_id, "ts": now(), "runtime": transport,
        "agent_type": event.get("agent_type"), "agent_id": event.get("agent_id"),
        "session_id": event.get("session_id"),
        "transcript": event.get("agent_transcript_path") or event.get("transcript_path"),
        "status": status, "error": error, "footer": footer,
        "issue_id": (footer or {}).get("issue_id"),
        "iteration_timestamp": (footer or {}).get("iteration_timestamp"),
        "correction_round": (footer or {}).get("correction_round", 0),
        "message_chars": len(message), "report_source": report_source,
        "report": reference(report_path, Path(root)),
    }
    append_record(root, record)
    return record


def role_contract(root, role):
    path = root / ".claude/agents" / (role + ".md")
    if role not in ROLES or not path.is_file():
        raise ValueError("unknown or missing role: " + role)
    text = path.read_text()
    header = text.split("---", 2)[1] if text.startswith("---\n") and len(text.split("---", 2)) == 3 else ""
    fields = {}
    for name in ("model", "tools", "skills"):
        match = re.search(r"^" + name + r":\s*(.+)$", header, re.M)
        fields[name] = match.group(1).strip() if match else ""
    if not fields["tools"]:
        raise ValueError("role must explicitly define its built-in tools")
    allowed = {"Read", "Grep", "Glob", "Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"}
    listed = [name.strip() for name in fields["tools"].split(",")]
    if any(name not in allowed for name in listed):
        raise ValueError("role contains an unsupported built-in tool; external MCP tools need an explicit adapter")
    return fields


def runtime_contract(root, executable="claude", role=None):
    """Hash executable/settings/instructions without returning authentication contents."""
    binary = shutil.which(executable)
    if not binary:
        raise ValueError("Claude executable not found: " + executable)
    resolved = Path(binary).resolve()
    version = subprocess.run([str(resolved), "--version"], capture_output=True,
                             text=True, check=True, timeout=10).stdout.strip()
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    paths = [config_dir / "settings.json", root / ".claude/settings.json",
             root / ".claude/settings.local.json", root / "CLAUDE.md",
             root / ".claude/ESX-team/ARCHITECT.md", Path(__file__).resolve()]
    if role:
        paths.append(root / ".claude/agents" / (role + ".md"))
        fields = role_contract(root, role)
        for skill in fields["skills"].split(","):
            if skill.strip():
                paths.append(root / ".claude/skills" / skill.strip() / "SKILL.md")
    paths += [Path(runtime_recovery.__file__).resolve(), root / "devel-loop/recovery.md", root / 'esx/templates/agent_report.json']
    paths += [Path(__file__).with_name(name + '.py') for name in
              ('team_accounting', 'team_budget', 'team_retrospective', 'footer_contract', 'runtime_tool_hook', 'bounded_command', 'permission_match')]
    registry = config_dir / "plugins/installed_plugins.json"
    paths.append(registry)
    if registry.is_file():
        for entries in json.loads(registry.read_text()).get("plugins", {}).values():
            for entry in entries if isinstance(entries, list) else []:
                if entry.get("installPath"):
                    install = Path(entry["installPath"])
                    paths += [install / "hooks/hooks.json", install / ".claude-plugin/plugin.json"]
    rows = [{"path": str(p), "sha256": digest(p.read_bytes()) if p.is_file() else None}
            for p in paths]
    # A Claude Bash subprocess inherits settings.env; a direct CLI caller may
    # not. Normalize both to the same effective configuration. Parent identities
    # and CLAUDECODE are transport metadata and must not invalidate a peer turn.
    effective_env = {}
    for path in paths[:3]:
        if path.is_file():
            effective_env.update(json.loads(path.read_text()).get("env", {}))
    effective_env.update(os.environ)
    env = {k: digest(str(v).encode()) for k, v in effective_env.items()
           if k.startswith("ANTHROPIC") or k in CONFIG_ENV}
    body = {"binary": str(resolved), "binary_sha256": digest(resolved.read_bytes()),
            "version": version, "files": rows, "environment": env,
            "transport": "claude_cli_session", "permission_mode": "inherited_settings"}
    body["effective_manifest"] = runtime_recovery.manifest(paths)
    return dict(body, sha256=digest(json.dumps(body, sort_keys=True).encode()))


def session_path(root, session):
    try:
        session = str(uuid.UUID(session))
    except ValueError as exc:
        raise ValueError("session must be a CLI session UUID") from exc
    return local(root, "devel-loop/loop_state/agent_runtime/sessions/" + session)


# Below the 600 s cap of a foreground tool call, so one wait is one blocking call.
WAIT_DEFAULT_SECONDS = 540
ROLE_TURN_SECONDS = {"bob": 3600}
DEFAULT_TURN_SECONDS = 1800
TIMEOUT_HELP = ("wall-clock seconds for this turn; default: runtime.turn_timeout_seconds in esx/project.json "
                "(a number, or a per-role object), else 3600 for bob and 1800 for other roles")


def turn_timeout(root, role, requested=None):
    """Wall-clock limit for one retained turn.

    An implementation turn is usually longer than a review or search turn, so
    the default depends on the role, and a project can size it from its own
    measured turns. An explicit --timeout always wins.
    """
    if requested is not None:
        return requested
    configured = None
    path = Path(root) / "esx/project.json"
    if path.is_file():
        configured = (json.loads(path.read_text()).get("runtime") or {}).get("turn_timeout_seconds")
    if isinstance(configured, dict):
        configured = configured.get(role, configured.get("default"))
    if configured is not None:
        if isinstance(configured, bool) or not isinstance(configured, (int, float)) or configured <= 0:
            raise ValueError("runtime.turn_timeout_seconds must be a positive number or a per-role object of them")
        return configured
    return ROLE_TURN_SECONDS.get(role, DEFAULT_TURN_SECONDS)


def wait_for_turns(root, timeout, session=None, poll=2.0):
    """Block until no retained turn is running, or until ``timeout`` seconds pass.

    With ``session`` it watches that session's turn lock; otherwise every running
    retained turn of the active issue. A retained turn sends no completion event
    to the coordinator, so this is how a coordinator waits for one inside its own
    turn without a busy loop of its own.
    """
    import ralph_stop
    root = Path(root).resolve()
    begun = time.monotonic()

    def running():
        if session is None:
            return ralph_stop.retained_in_flight(root)
        lock = session_path(root, session) / ".turn.lock"
        if not lock.exists():
            return False
        with lock.open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(handle, fcntl.LOCK_UN)
        return False

    def report(status, following):
        # A long in-turn wait fires no Stop event, so the owner's status line and
        # the channel heartbeat are produced here.
        result = {"status": status, "waited_seconds": round(time.monotonic() - begun, 1), "next": following}
        if (root / "esx/project.json").is_file():
            try:
                import loop_control
                import notifications
                result["status_line"] = loop_control.status_line(root)
                if notifications.heartbeat(root):
                    result["heartbeat"] = "due: deliver the queued loop_heartbeat (tools/esx/notifications.py pending)"
            except (ValueError, OSError, KeyError, TypeError):
                pass
        return result

    while running():
        if time.monotonic() - begun >= timeout:
            return report("running", "the turn is still running; print status_line for the owner, then run wait again")
        time.sleep(poll)
    return report("idle", "no retained turn is running; continue with tools/esx/loop_gate.py --next")


def role_runtime_settings(root):
    """Retain project hooks and permissions while excluding the parent's Ralph loop."""
    disabled = {}
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
    for path in (config_dir / "settings.json", root / ".claude/settings.json",
                 root / ".claude/settings.local.json"):
        if path.is_file():
            config = json.loads(path.read_text())
            for name in config.get("enabledPlugins", {}):
                if "ralph" in name.lower():
                    disabled[name] = False
    return {"enabledPlugins": disabled}


def replacement_record(root, agent_id, role, issue, reason):
    """Require an observed same-role assignment and a reason for a new correction identity."""
    if not agent_id or not reason or len(reason.strip()) < 20:
        raise ValueError("a correction needs followup, or --replaces-agent plus a substantive --replacement-reason")
    log = root / "devel-loop/loop_state/dispatch_log.jsonl"
    records = []
    for line in log.read_text().splitlines() if log.is_file() else []:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("agent_id") == agent_id:
            records.append(record)
    if not records:
        raise ValueError("replacement agent has no recorded dispatch")
    previous = records[-1]
    previous_issue = previous.get("issue_id") or (previous.get("footer") or {}).get("issue_id")
    if previous.get("agent_type") != role or previous_issue != issue:
        raise ValueError("replacement must preserve the recorded role and issue")
    return {"agent_id": agent_id, "event_id": previous.get("event_id"), "reason": reason.strip()}


def stream_events(path):
    """Yield every JSON object row of a saved stream, skipping partial lines."""
    if not Path(path).is_file():
        return
    for line in Path(path).read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def permission_denials(path):
    """Tool calls the CLI denied, so a blocked role is visible in its turn record."""
    tools = {}
    for event in stream_events(path):
        message = event.get("message")
        if event.get("type") == "assistant" and isinstance(message, dict):
            for item in message.get("content") or []:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    tools[item.get("id")] = item.get("input")
    return [{"tool_name": e.get("tool_name"), "tool_use_id": e.get("tool_use_id"),
             "reason": e.get("decision_reason") or e.get("message"),
             "input": tools.get(e.get("tool_use_id"))}
            for e in stream_events(path)
            if e.get("type") == "system" and e.get("subtype") == "permission_denied"]


APPROVAL_ERROR = 'approval needs a successful executed check and no must_fix findings'


def changes_requested(role, footer, errors):
    """A well-formed Richard review whose only defect is approving with must_fix items."""
    if role != 'richard' or not isinstance(footer, dict) or not footer.get('must_fix'):
        return None
    if footer.get('verdict') not in ('APPROVE', 'APPROVE_WITH_FIXES'):
        return None
    return 'changes_requested' if errors and all(APPROVAL_ERROR in e for e in errors) else None


def recover_orphans(root, session, reason):
    """Close turns that never wrote record.json (a crashed dispatcher), anywhere in history.

    A recovered turn is recorded as failed, never successful, with its saved
    stream, denials and the stated reason, so review can cite or replace it.
    Refused while the session's turn lock is held (a live turn is not an orphan).
    """
    if not reason or len(reason.strip()) < 20:
        raise ValueError("recover requires a substantive --reason")
    root = Path(root).resolve()
    folder = session_path(root, session)
    state_file = folder / "session.json"
    if not state_file.is_file():
        raise ValueError("unknown CLI session")
    recovered = []
    with locked(folder / ".turn.lock"):
        state = json.loads(state_file.read_text())
        turns = sorted((folder / "turns").glob("*/"), key=lambda p: p.stat().st_mtime)
        for turn in turns:
            if (turn / "record.json").exists() or not (turn / "invocation.json").exists():
                continue
            event_id = turn.name
            _, message, init = parse_stream(turn / "stdout.jsonl") if (turn / "stdout.jsonl").exists() else (None, "", None)
            (turn / "report.md").write_text(message or "")
            record = {"event_id": event_id, "ts": now(), "runtime": "claude_cli_session",
                      "agent_type": state["role"], "agent_id": session, "session_id": session,
                      "issue_id": state["issue_id"], "correction_round": None,
                      "iteration_timestamp": None, "status": "failed",
                      "error": "orphaned turn recovered: " + reason.strip(),
                      "footer": None, "execution_phase": "recovered_orphan",
                      "message_chars": len(message or ""), "started_at": None,
                      "finished_at": now(), "returncode": None,
                      "effective_permission_mode": (init or {}).get("permissionMode"),
                      "permission_denials": permission_denials(turn / "stdout.jsonl"),
                      "report": reference(turn / "report.md", root),
                      "invocation": reference(turn / "invocation.json", root),
                      "stream": reference(turn / "stdout.jsonl", root) if (turn / "stdout.jsonl").exists() else None,
                      "recovered": True}
            atomic_json(turn / "partial.json", {"status": "failed", "error": record["error"]})
            atomic_json(turn / "record.json", record)
            append_record(root, record)
            if event_id not in state["turns"]:
                state["turns"].append(event_id)
            if state.get("active_event_id") == event_id:
                state.update(status="failed", active_event_id=None, last_event_id=event_id)
            recovered.append(event_id)
        if state.get("status") == "running" and not state.get("active_event_id"):
            state["status"] = "failed"
        atomic_json(state_file, state)
    return {"status": "recovered" if recovered else "nothing_to_recover", "session_id": session,
            "recovered_event_ids": recovered}


def parse_stream(path):
    messages, results, init = [], [], None
    for line in path.read_text(errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("type") == "system" and record.get("subtype") == "init":
            init = record
        if record.get("type") == "result":
            results.append(record)
        if record.get("type") == "assistant":
            payload = record.get("message")
            content = payload.get("content", []) if isinstance(payload, dict) else []
            if isinstance(content, str):
                messages.append(content)
            elif isinstance(content, list):
                messages.append("\n".join(x["text"] for x in content if isinstance(x, dict)
                                           and x.get("type") == "text" and isinstance(x.get("text"), str)))
    result = results[-1] if results else None
    message = result.get("result", "") if result else ""
    if not isinstance(message, str):
        message = ""
    return result, message or (messages[-1] if messages else ""), init


def review_context(root, packet, issue, baseline=None):
    """Validate a candidate handoff and return compact, exact evidence references.

    The existing maintenance and candidate validators check identity, hashes,
    coverage and freshness. This preflight supplies no scientific approval or
    reviewer orientation. A stored packet is revalidated on every resumed turn;
    stale source or prose requires a refreshed packet. Tests use real sealed
    artifacts in tools/tests/test_agent_runtime.py.
    """
    import doc_contract as maintenance
    import issue_candidates
    active_path = root / 'devel-loop/loop_state/issue-start.json'
    active = json.loads(active_path.read_text()) if active_path.is_file() else {}
    if active.get('state_version', 1) >= 2:
        import verify
        try:
            verify.structural_evidence(root)
        except (ValueError, OSError, KeyError) as exc:
            raise ValueError('STRUCTURAL_STALE_OR_FAILING: run verify.py --suite structural --owner arch before paid review: ' + str(exc)) from exc
    if not isinstance(packet, dict) or packet.get("id") != issue:
        raise ValueError("review packet must name the assigned issue")
    state = packet.get("maintenance")
    if not isinstance(state, dict):
        raise ValueError("review packet needs maintenance.baseline and maintenance.documentation")
    base = state.get("baseline")
    if baseline is not None and base != baseline:
        raise ValueError("review packet must preserve the assigned issue baseline")
    report_ref = state.get("documentation")
    report = maintenance.load(root, report_ref, "documentation", issue)
    if "references" not in report:
        raise ValueError("review packet needs a sealed documentation report")
    maintenance.validate_report(root, report, issue, base)
    candidate = issue_candidates.check_current(root, packet.get("candidate"), issue)
    if candidate.get("baseline") != base:
        raise ValueError("review candidate must preserve the documentation baseline")
    return {"id": issue, "candidate": packet["candidate"],
            "maintenance": {"baseline": base, "documentation": report_ref},
            "map_delta": report["map_delta"],
            **({"handoff": packet["handoff"]} if "handoff" in packet else {}),
            **({"subagents": packet["subagents"]} if "subagents" in packet else {})}


def _read_tool_events(path, offset, remainder, open_tools):
    """Tail complete stream rows and update active tool-use state."""
    if not Path(path).exists():
        return offset, remainder
    with Path(path).open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
        offset = handle.tell()
    if not data:
        return offset, remainder
    text = remainder + data.decode(errors="replace")
    rows = text.splitlines(keepends=True)
    if rows and not rows[-1].endswith(("\n", "\r")):
        remainder = rows.pop()
    else:
        remainder = ""
    for row in rows:
        try:
            event = json.loads(row)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        # Any event shape is legal: permission_denied system events carry a
        # string `message`, and the watchdog must never die on one.
        message = event.get("message")
        content = message.get("content", []) if isinstance(message, dict) else []
        if event.get("type") == "assistant":
            for item in content if isinstance(content, list) else []:
                if isinstance(item, dict) and item.get("type") == "tool_use" and item.get("id"):
                    open_tools.setdefault(item["id"], {"name": item.get("name"), "start": time.monotonic(),
                                                       "handled": False})
        elif event.get("type") == "user":
            for item in content if isinstance(content, list) else []:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    open_tools.pop(item.get("tool_use_id"), None)
    return offset, remainder


def _check_watchdog(proc, stdout_path, offset, remainder, open_tools, watchdog_kills, tool_timeout):
    offset, remainder = _read_tool_events(stdout_path, offset, remainder, open_tools)
    if tool_timeout and tool_timeout > 0:
        current = time.monotonic()
        for tool_id, info in list(open_tools.items()):
            if info.get("handled"):
                continue
            elapsed = current - info["start"]
            if elapsed >= tool_timeout:
                from bounded_command import receipt_path, terminate_group
                receipt = receipt_path(Path(stdout_path).parent, tool_id)
                if not receipt.exists():
                    # Never kill arbitrary concurrent tools when identity is unknown.
                    raise subprocess.TimeoutExpired('unmapped tool ' + tool_id, tool_timeout)
                owner = json.loads(receipt.read_text())
                killed = []
                if owner.get('status') == 'running' and owner.get('tool_use_id') == tool_id:
                    terminate_group(owner['pgid'])
                    killed = [owner['pgid']]
                info["handled"] = True
                watchdog_kills.append({"tool_use_id": tool_id, "name": info.get("name"),
                                       "elapsed_s": elapsed, "killed_pids": killed, "ts": now()})
    return offset, remainder


def _execute(root, folder, state, command, prompt, timeout, tool_timeout, stdout_name="stdout.jsonl"):
    """Launch the retained CLI turn, enforce total and per-tool timeouts, parse output."""
    stdout_path = folder / stdout_name
    error, code, proc = None, None, None
    watchdog_kills, open_tools = [], {}
    offset, remainder = 0, ""
    with stdout_path.open("w") as stdout, (folder / "stderr.txt").open("a") as stderr:
        try:
            child_env = os.environ.copy()
            # This is an intentionally independent, retained CLI session.
            # Preserve authentication and permissions; remove the nesting sentinel.
            child_env.pop("CLAUDECODE", None)
            child_env["ESX_AGENT_RUNTIME_CHILD"] = "1"
            child_env["CLAUDE_PROJECT_DIR"] = str(root)
            if (folder / 'runtime_context.json').exists():
                child_env['ESX_RUNTIME_CONTEXT'] = str(folder / 'runtime_context.json')
            proc = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE,
                                    stdout=stdout, stderr=stderr, text=True,
                                    start_new_session=True, env=child_env)
            def feed_prompt():
                # A provider that never reads stdin must still hit its timeout.
                try:
                    proc.stdin.write(prompt)
                except (BrokenPipeError, OSError, ValueError):
                    pass
                finally:
                    try:
                        proc.stdin.close()
                    except (BrokenPipeError, OSError, ValueError):
                        pass
            writer = threading.Thread(target=feed_prompt, daemon=True)
            writer.start()
            deadline = time.monotonic() + timeout if timeout is not None else None
            while True:
                offset, remainder = _check_watchdog(proc, stdout_path, offset, remainder,
                                                    open_tools, watchdog_kills, tool_timeout)
                code = proc.poll()
                if code is not None:
                    offset, remainder = _check_watchdog(proc, stdout_path, offset, remainder,
                                                        open_tools, watchdog_kills, tool_timeout)
                    break
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    sleep_for = min(WATCHDOG_POLL_S, remaining)
                else:
                    sleep_for = WATCHDOG_POLL_S
                time.sleep(sleep_for)
            code = proc.returncode
        except OSError as exc:
            error = "launch failed: " + str(exc)
            if proc is not None and proc.poll() is None:
                from bounded_command import terminate_group
                terminate_group(proc.pid, proc)
                proc.wait()
                code = proc.returncode
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            error = "timeout" if isinstance(exc, subprocess.TimeoutExpired) else "interrupted"
            if proc is not None:
                from bounded_command import terminate_group
                terminate_group(proc.pid, proc)
                proc.wait()
                code = proc.returncode
        except Exception as exc:  # noqa: BLE001 - a dispatcher defect must still end in a recorded turn
            error = "dispatcher error: " + type(exc).__name__ + ": " + str(exc)
            if proc is not None and proc.poll() is None:
                from bounded_command import terminate_group
                terminate_group(proc.pid, proc)
                proc.wait()
            code = proc.returncode if proc is not None else None
        finally:
            if proc is not None:
                from bounded_command import terminate_group
                terminate_group(proc.pid, proc)
                proc.wait()
                if 'writer' in locals():
                    writer.join(timeout=1)
    result, message, init = parse_stream(stdout_path)
    return result, message, init, code, error, watchdog_kills



def _run_turn(root, *, role=None, issue=None, prompt, session=None, correction_round=0,
             executable="claude", timeout=None, probe=False, from_session=None,
             replaces_agent=None, replacement_reason=None, progress=None, review_packet=None, transition=None, tool_timeout=600, turn_calls=60,
             witness=False):
    """Execute one retained turn, recording failures before returning non-success."""
    root = Path(root).resolve()
    resumed = session is not None
    if type(correction_round) is not int or correction_round < 0:
        raise ValueError("correction round must be nonnegative")
    if timeout is not None and (not isinstance(timeout, (float, int)) or timeout <= 0):
        raise ValueError("timeout must be positive")
    replacement = None
    if not resumed and (correction_round > 0 or replaces_agent or replacement_reason):
        replacement = replacement_record(root, replaces_agent, role, issue, replacement_reason)
    session = session or str(uuid.uuid4())
    folder = session_path(root, session)
    with locked(folder / ".turn.lock"):
        state_file = folder / "session.json"
        if resumed:
            if not state_file.is_file():
                raise ValueError("unknown CLI session; native subagent IDs cannot use this bridge")
            state = json.loads(state_file.read_text())
            role, issue, probe = state["role"], state["issue_id"], state["probe"]
        else:
            if state_file.exists():
                raise ValueError("session already exists")
            state = {"session_id": session, "role": role, "issue_id": issue,
                     "probe": probe, "turns": [], "created_at": now()}
        timeout = turn_timeout(root, role, timeout)
        if from_session:
            sender_path = session_path(root, from_session) / "session.json"
            if not sender_path.is_file():
                raise ValueError("message sender is not a recorded CLI session")
            sender = json.loads(sender_path.read_text())
            if sender["issue_id"] != issue:
                raise ValueError("peer message must stay within the assigned issue")
        if not probe:
            team_retrospective.require_clear(root)
            team_retrospective.require_followup(root, issue)
        issue_budget, run_budget = team_budget.assignment(root, issue)
        source_signature = None
        if (root / "esx/project.json").is_file():
            from project import source_signature as measure_source
            source_signature = measure_source(root)
        start_path = root / "devel-loop/loop_state/issue-start.json"
        active = json.loads(start_path.read_text()) if start_path.is_file() and not probe else {}
        if active and active.get("id") != issue:
            import loop_iteration
            import self_improvement
            history = team_accounting.rows(root / team_accounting.STATE / 'loop_history.jsonl')
            process_owners = {row.uuid for row in self_improvement.parse(root / self_improvement.OPEN)}
            if loop_iteration.finished(active, history) and issue in process_owners:
                active = {}  # bounded process follow-up after the scientific closeout
            else:
                raise ValueError("active iteration belongs to a different issue")
        iteration_timestamp = active.get("timestamp")
        packet = review_packet if review_packet is not None else state.get("review_packet")
        review = None
        if not probe:
            if role == "richard" and active and packet is None:
                raise ValueError("Richard review requires --review-packet with candidate and sealed documentation")
            if packet is not None:
                review = review_context(root, packet, issue, (active.get("maintenance") or {}).get("baseline"))
        if not probe and active.get('state_version', 1) >= 2:
            import loop_iteration
            if not loop_iteration.start_status(root, active)['validated']:
                raise ValueError('successful --check-start required before dispatch')
        contract = runtime_contract(root, executable, None if probe else role)
        transition_result = runtime_recovery.compatibility(
            root, state, contract, transition, probe=lambda: probe_status(root, executable)) if resumed else None
        event_id = uuid.uuid4().hex
        turn = folder / "turns" / event_id
        turn.mkdir(parents=True)
        reservation = team_budget.reserve(root, event_id, issue or 'RUNTIME-PROBE-001', issue_budget,
            run=run_budget.get('id'), run_budget=run_budget.get('limits'), correction=correction_round,
            turn_seconds=timeout, turn_calls=turn_calls)
        timeout = min(timeout, max(.01, reservation['deadline'] - time.time()))
        atomic_json(turn / 'runtime_context.json', {'root': str(root), 'folder': str(turn),
                    'event_id': event_id, 'tool_timeout': tool_timeout})
        command = [contract["binary"], "--print", "--output-format", "stream-json", "--verbose"]
        if probe and witness:
            # Tool-permission witness: project settings and the real runtime hook,
            # exactly as a role sees them, with Bash as the only tool.
            command += ["--tools", "Bash", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                        "--settings", '{"enabledPlugins":{}}',
                        "--system-prompt", "Follow the supplied test instructions exactly."]
        elif probe:
            command += ["--permission-mode", "dontAsk", "--tools", "", "--setting-sources", "user",
                        "--settings", '{"disableAllHooks":true,"enabledPlugins":{}}',
                        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                        "--system-prompt", "Follow the supplied test instructions exactly."]
        else:
            fields = role_contract(root, role)
            command += ["--agent", role, "--tools", fields["tools"],
                        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                        "--settings", json.dumps(role_runtime_settings(root))]
            if fields["model"]:
                command += ["--model", fields["model"]]
            deadline = datetime.now(timezone.utc) + timedelta(seconds=timeout)
            assignment = {"agent": role, "agent_id": session, "session_id": session,
                          "issue_id": issue, "iteration_timestamp": iteration_timestamp,
                          "correction_round": correction_round,
                          "sender_session_id": from_session,
                          "baseline": (active.get("maintenance") or {}).get("baseline"),
                          "turn_minutes": round(timeout / 60, 1),
                          "turn_deadline_utc": deadline.strftime('%Y-%m-%dT%H:%M:%SZ')}
            if review is not None:
                assignment["review"] = review
                state["review_packet"] = review
            # A file, not an argv string: Linux caps one argument at 131,072 bytes
            # (MAX_ARG_STRLEN) and the review context grows with each round.
            (turn / "assignment.txt").write_text(
                "ESX dispatcher assignment: " + json.dumps(assignment)
                + "\nUse agent_id as your verification owner and peer sender identity. "
                "Use the supplied issue, iteration and correction round in your footer. "
                "The baseline identifies issue maintenance evidence. Follow the bounded brief, "
                "record your own orientation and preserve project permissions. "
                "Read supplied review references and confirm the exact sealed documentation in your footer. "
                "This turn is stopped at turn_deadline_utc and anything not on disk is lost: write each finished "
                "unit to disk as you go, before starting a long unit read the clock with `python3 -c \"import datetime; print(datetime.datetime.now(datetime.timezone.utc))\"`, and when less than a fifth "
                "of turn_minutes remains, finish the unit in hand and report with your footer, listing what is left.")
            command += ["--append-system-prompt-file", str(turn / "assignment.txt")]
        if transition_result and transition_result["classification"] == "assessed":
            prompt = "Assessed runtime transition for this retained session. Read changed instruction files before acting: " + json.dumps(transition_result) + "\n" + prompt
        (turn / "prompt.txt").write_text(prompt)
        # No provider-side spend cap. The reservation records what this turn was
        # expected to cost so settle() can measure the difference; capping the
        # provider here would truncate a turn mid-work over a pricing estimate.
        if not probe or witness:
            index = command.index('--settings') + 1
            settings = json.loads(command[index])
            settings['hooks'] = {'PreToolUse': [{'matcher': '.*', 'hooks': [{'type': 'command',
                'command': shlex.join([sys.executable, str(Path(__file__).with_name('runtime_tool_hook.py'))]), 'timeout': 10}]}]}
            command[index] = json.dumps(settings)
        command += ["--resume" if resumed else "--session-id", session]
        atomic_json(turn / "invocation.json", {"argv": command, "cwd": str(root),
                    "runtime": contract, "prompt": reference(turn / "prompt.txt", root)})
        state.update(status="running", runtime_fingerprint=contract["sha256"],
                     runtime_contract=contract, runtime_transition=transition_result,
                     active_event_id=event_id, started_at=now())
        atomic_json(state_file, state)
        if progress:
            progress({"status": "running", "session_id": session, "event_id": event_id,
                      "role": role, "issue_id": issue})
        started = time.monotonic()
        with team_accounting.phase(root, issue, 'review' if role == 'richard' else 'implementation', role=role):
            result, message, init, code, error, watchdog_kills = _execute(
                root, turn, state, command, prompt, timeout, tool_timeout)
        usage = team_accounting.stream_usage(turn / 'stdout.jsonl')
        if code is None:
            usage['cost_usd'] = 0
        if usage.get('cost_usd') is not None and not team_accounting.number(usage['cost_usd']):
            error = 'invalid provider cost; full reservation retained'
            usage['cost_usd'] = None
        settlement = team_budget.settle(root, event_id, usage.get('cost_usd'))
        # Reservations are nominal (team_budget): an overshoot is recorded data, never a
        # turn failure. A retained session's per-turn cost grows with its context.
        provider_overshoot = bool(settlement.get('provider_overshoot'))
        footer = footer_from(message)
        review_outcome = None
        status = "completed"
        if error or code != 0 or not result or result.get("is_error"):
            status = "failed"
            error = error or (result or {}).get("result") or "missing result or nonzero process exit"
        elif result.get("session_id") != session or not init or init.get("session_id") != session:
            status, error = "failed", "runtime returned a different or missing session identity"
        elif result.get("stop_reason") not in ("end_turn", "stop_sequence"):
            status, error = "incomplete", "runtime stopped before the end of its report"
        elif (not footer or footer.get("agent") != role or footer.get("issue_id") != issue
              or footer.get("correction_round") != correction_round
              or (iteration_timestamp and footer.get("iteration_timestamp") != iteration_timestamp)):
            status, error = "incomplete", "missing, malformed, or mismatched report footer"
        if status == 'completed' and not probe:
            errors = footer_contract.validate(root, role, footer, issue, correction_round, active, session,
                                             ((review or {}).get('maintenance') or {}).get('documentation'))
            if errors:
                status, error = 'incomplete', '; '.join(errors)
                review_outcome = changes_requested(role, footer, errors)
                if review_outcome:
                    error = ('review requested changes: verdict ' + str(footer.get('verdict')) + ' with '
                             + str(len(footer['must_fix'])) + ' must_fix item(s) is recorded as a non-approving '
                             'review, not a dispatch failure; relay must_fix to Bob. (Contract: required changes '
                             'use REJECT with must_fix; APPROVE_WITH_FIXES needs an empty must_fix.)')
        (turn / "report.md").write_text(message)
        turn_source_signature = None
        if source_signature is not None:
            try:
                from project import source_signature as measure_source
                turn_source_signature = measure_source(root)
            except (ValueError, OSError, KeyError, TypeError):
                # An unreadable tree must not mask the turn's own outcome; leaving
                # this None records honestly that the comparison was unavailable.
                turn_source_signature = None
        record = {"event_id": event_id, "ts": now(), "runtime": "claude_cli_session",
                  "agent_type": role, "agent_id": session, "session_id": session,
                  "issue_id": issue, "correction_round": correction_round,
                  "iteration_timestamp": iteration_timestamp,
                  "status": status, "error": error, "footer": footer,
                  "review_outcome": review_outcome,
                  "provider_overshoot": provider_overshoot,
                  "execution_phase": ("launch_failed" if code is None else
                      "approved" if status == "completed" and (footer or {}).get("verdict") in ("APPROVE", "APPROVE_WITH_FIXES")
                      else "completed" if status == "completed" else "executed_" + status),
                  "message_chars": len(message), "started_at": state["started_at"],
                  "finished_at": now(), "duration_seconds": time.monotonic() - started,
                  "returncode": code, "runtime_fingerprint": contract["sha256"],
                  "source_signature_at_dispatch": source_signature,
                  # Whether this turn left durable work behind. A turn cut short by
                  # a timeout is usually recoverable by resuming rather than
                  # restarting, but only if its edits actually landed -- and a bare
                  # 'failed' status cannot say which. Recording the comparison here
                  # means recovery reads a field instead of guessing.
                  "source_changed_during_turn": (None if turn_source_signature is None
                                                 else turn_source_signature != source_signature),
                  "source_signature_at_finish": turn_source_signature,
                  "resumed_from_event_id": state["turns"][-1] if state["turns"] else None,
                  "sender_session_id": from_session,
                  "replacement": replacement,
                  "effective_permission_mode": (init or {}).get("permissionMode"),
                  "permission_denials": permission_denials(turn / "stdout.jsonl"),
                  "report": reference(turn / "report.md", root),
                  "invocation": reference(turn / "invocation.json", root),
                  "stream": reference(turn / "stdout.jsonl", root),
                  "transcript": str(turn / "stdout.jsonl"),
                  "stderr": reference(turn / "stderr.txt", root),
                  "usage": (result or {}).get("usage"),
                  "cost_usd": usage.get('cost_usd'), 'budget': reservation,
                  'accounting_components': [dict(usage, event_id=event_id, kind='turn')],
                  'tool_watchdog_kills': watchdog_kills}
        atomic_json(turn / 'handoff.json', footer_contract.handoff(record))
        record['handoff'] = reference(turn / 'handoff.json', root)
        if status != 'completed':
            atomic_json(turn / 'partial.json', {'status': status, 'error': error, 'handoff': record['handoff']})
        atomic_json(turn / "record.json", record)
        append_record(root, record)
        state["turns"].append(event_id)
        state.update(status=status, active_event_id=None, last_event_id=event_id)
        atomic_json(state_file, state)
        return record


def probe_runtime(root, executable="claude", timeout=55):
    """Test a hidden random token across a real saved history; save PASS or FAIL."""
    root = Path(root).resolve()
    token = "ESX-CONTINUITY-" + uuid.uuid4().hex
    issue, role = "RUNTIME-CONTINUITY", "scout"
    first = run_turn(root, role=role, issue=issue, executable=executable, timeout=timeout,
                     prompt='Remember token ' + token + '. Reply only this JSON fence:\n```json\n'
                     + json.dumps({"agent": role, "issue_id": issue, "correction_round": 0,
                                   "ready": True}) + '\n```', probe=True)
    second = None
    if first["status"] == "completed":
        second = run_turn(root, session=first["session_id"], executable=executable,
                          timeout=timeout, correction_round=1,
                          prompt='Return only a JSON fence with agent="scout", '
                          'issue_id="RUNTIME-CONTINUITY", correction_round=1, and '
                          'remembered_token equal to the token from the previous turn.')
    continuity = bool(second and second["status"] == "completed"
                      and second["footer"].get("remembered_token") == token
                      and second["session_id"] == first["session_id"])
    permissions = permission_witness(root, executable, max(timeout, 90)) if continuity else None
    passed = continuity and bool(permissions and permissions["status"] == "passed")
    evidence = {"version": 2, "status": "passed" if passed else "failed", "ts": now(),
                "runtime_fingerprint": first["runtime_fingerprint"],
                "first": first, "second": second, "permissions": permissions,
                "limits": "Two real tools-disabled continuity turns plus one real Bash turn through the "
                          "retained-role PreToolUse hook: one project-allowed command must run and one "
                          "command the project does not allow must not run. Other role tools are not exercised."}
    path = local(root, "devel-loop/loop_state/agent_runtime/probes/" + uuid.uuid4().hex + ".json")
    atomic_json(path, evidence)
    return dict(evidence, evidence=reference(path, root))


ALLOWED_CANDIDATES = ("printf %s {m}", "echo {m}", "python3 -c 'print(\"{m}\")'", "pwd", "ls", "true")
# Each creates exactly {t} and nothing else; the first one the settings do not allow is used.
DENIED_CANDIDATES = ("mkdir {t}", "touch {t}", "ln -s /dev/null {t}", "cp /dev/null {t}", "install -d {t}")


def permission_witness(root, executable="claude", timeout=90):
    """Live witness that retained-role Bash honours the project's allow list.

    Picks a harmless command the merged settings allow and a directory creation
    they do not, runs both in one real turn under the runtime hook, and checks
    the stream and the filesystem. Tools-disabled probes cannot see ESX-002.
    """
    import permission_match
    root = Path(root).resolve()
    rules = permission_match.load_rules(root)
    marker = "ESX-PERM-" + uuid.uuid4().hex[:12]
    allowed = next((c.format(m=marker) for c in ALLOWED_CANDIDATES
                    if permission_match.decide(c.format(m=marker), rules) == "allow"), None)
    target = local(root, "devel-loop/loop_state/agent_runtime/probes/denied-" + marker)
    if allowed is None:
        return {"status": "failed", "reason": "no harmless command is allowed by project settings "
                "(tried: " + ", ".join(ALLOWED_CANDIDATES) + "); the allow path cannot be witnessed"}
    denied = next((c.format(t=target) for c in DENIED_CANDIDATES
                   if permission_match.decide(c.format(t=target), rules) != "allow"), None)
    issue, role = "RUNTIME-PERMISSIONS", "scout"
    turn = run_turn(root, role=role, issue=issue, executable=executable, timeout=timeout, probe=True, witness=True,
                    prompt="Run these two Bash commands, exactly as written, as two separate tool calls, in order. "
                    "Do not modify, combine or retry them, and do not run anything else.\n1. " + allowed
                    + ("\n2. " + denied if denied else "") + "\nThen reply only this JSON fence:\n```json\n"
                    + json.dumps({"agent": role, "issue_id": issue, "correction_round": 0}) + "\n```")
    stream = local(root, turn["stream"]["path"]) if turn.get("stream") else None
    calls, results = {}, {}
    for event in stream_events(stream) if stream else []:
        message = event.get("message")
        for item in (message.get("content") or []) if isinstance(message, dict) else []:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                calls[item.get("id")] = (item.get("input") or {}).get("command")
            elif isinstance(item, dict) and item.get("type") == "tool_result":
                results[item.get("tool_use_id")] = item
    ran = [i for i, c in calls.items() if c == allowed and i in results and not results[i].get("is_error")
           and (marker in json.dumps(results[i].get("content")) or "{m}" not in next(
               c for c in ALLOWED_CANDIDATES if c.format(m=marker) == allowed))]
    attempted_denied = [i for i, c in calls.items() if denied and c == denied]
    denied_held = bool(attempted_denied) and not (target.exists() or target.is_symlink())
    mode = turn.get("effective_permission_mode")
    # A denial is only witnessable when the settings leave some write command unallowed
    # and the CLI is not bypassing permissions; otherwise only the allow path is checked.
    witnessable = denied is not None and mode != "bypassPermissions"
    passed = bool(ran) and (denied_held or not witnessable)
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        target.rmdir()
    return {"status": "passed" if passed else "failed", "allowed_command": allowed, "denied_command": denied,
            "allowed_ran": bool(ran), "denied_attempted": bool(attempted_denied), "denied_held": denied_held,
            "effective_permission_mode": mode, "permission_denials": turn.get("permission_denials"),
            "turn": {k: turn.get(k) for k in ("event_id", "session_id", "status", "error", "stream")},
            "note": ("bypassPermissions: a denial cannot be witnessed; only the allowed path was checked"
                     if mode == "bypassPermissions" else
                     "project settings allow every candidate write command (" + ", ".join(
                         c.split(" ")[0] for c in DENIED_CANDIDATES) + "); only the allowed path was checked"
                     if denied is None else None)}


def probe_status(root, executable="claude"):
    """Return reusable live continuity evidence only for the measured configuration."""
    root = Path(root).resolve()
    contract = runtime_contract(root, executable)
    directory = root / "devel-loop/loop_state/agent_runtime/probes"
    for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            evidence = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if evidence.get("runtime_fingerprint") == contract["sha256"]:
            return {"status": evidence.get("status"), "reused_evidence": True,
                    "runtime_fingerprint": contract["sha256"], "evidence": reference(path, root),
                    "limits": evidence.get("limits")}
    return {"status": "missing", "reused_evidence": False,
            "runtime_fingerprint": contract["sha256"],
            "reason": "no live continuity result for this runtime configuration"}


def run_turn(root, **kwargs):
    """Record preflight refusals without creating a completion or correction round."""
    root = Path(root).resolve()
    begun = time.monotonic()
    launched = False
    caller_progress = kwargs.get("progress")
    def progress(value):
        """Mark launch independently of concurrent agents appending to the log."""
        nonlocal launched
        launched = True
        if caller_progress:
            caller_progress(value)
    kwargs["progress"] = progress
    try:
        return _run_turn(root, **kwargs)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        if not launched:
            identity = dict(kwargs)
            if kwargs.get("session"):
                try:
                    path = session_path(root, kwargs["session"]) / "session.json"
                except ValueError:
                    path = root / "devel-loop/loop_state/nonexistent-session"
                if path.is_file():
                    state = json.loads(path.read_text())
                    identity.update(role=state.get("role"), issue=state.get("issue_id"))
            try:
                runtime_recovery.preflight_event(root, identity, exc, time.monotonic() - begun)
            except (ValueError, OSError):
                # Preserve the primary refusal when the evidence directory is
                # itself inaccessible or violates path containment.
                pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--claude", default="claude")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--role", choices=sorted(ROLES), required=True)
    start.add_argument("--issue", required=True)
    start.add_argument("--prompt-file", type=Path, required=True)
    start.add_argument("--review-packet", type=Path)
    start.add_argument("--correction-round", type=int, default=0)
    start.add_argument("--timeout", type=float, help=TIMEOUT_HELP)
    start.add_argument("--replaces-agent", help="recorded native or CLI identity being replaced")
    start.add_argument("--replacement-reason")
    follow = sub.add_parser("followup", aliases=["message"])
    follow.add_argument("--session", required=True)
    follow.add_argument("--transition", type=Path, help="JSON reference returned by assess-transition")
    follow.add_argument("--prompt-file", type=Path, required=True)
    follow.add_argument("--review-packet", type=Path)
    follow.add_argument("--correction-round", type=int, required=True)
    follow.add_argument("--timeout", type=float, help=TIMEOUT_HELP)
    follow.add_argument("--from-session", help="recorded peer identity for an issue-scoped message")
    status = sub.add_parser("status")
    status.add_argument("--session", required=True)
    hold = sub.add_parser("wait", help="block until no retained turn is running (or the timeout passes)")
    hold.add_argument("--session", help="watch one session; default: every running turn of the active issue")
    hold.add_argument("--timeout", type=float, default=WAIT_DEFAULT_SECONDS)
    recover = sub.add_parser("recover", help="close crashed turns that never wrote a record")
    recover.add_argument("--session", required=True)
    recover.add_argument("--reason", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("--timeout", type=float, default=55)
    sub.add_parser("fingerprint")
    sub.add_parser("probe-status")
    sub.add_parser("hook")
    doctor = sub.add_parser("hook-doctor")
    doctor.add_argument("--event", help="exact dispatch event for measured process diagnostics")
    assess = sub.add_parser("assess-transition")
    assess.add_argument("--session", required=True)
    assess.add_argument("--judgment", type=Path, required=True)
    for command_parser in (start, follow):
        command_parser.add_argument('--tool-timeout', type=float, default=600)
        command_parser.add_argument('--max-tool-calls', type=int, default=60)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "hook":
            try:
                event = json.load(sys.stdin)
            except ValueError:
                event = {}
            stop_record(root, event)
            return 0
        if args.command == "hook-doctor":
            value = runtime_recovery.hook_doctor(root, event_id=args.event)
        elif args.command == "assess-transition":
            from workflow_handoff import input_file
            state = json.loads((session_path(root, args.session) / "session.json").read_text())
            contract = runtime_contract(root, args.claude, None if state["probe"] else state["role"])
            value = runtime_recovery.assess(root, state, contract, json.loads(input_file(root, args.judgment).read_text()))
        elif args.command == "fingerprint":
            value = runtime_contract(root, args.claude)
        elif args.command == "status":
            value = json.loads((session_path(root, args.session) / "session.json").read_text())
        elif args.command == "wait":
            print(json.dumps(wait_for_turns(root, args.timeout, args.session), indent=2))
            return 0
        elif args.command == "recover":
            value = recover_orphans(root, args.session, args.reason)
        elif args.command == "probe":
            value = probe_runtime(root, args.claude, args.timeout)
        elif args.command == "probe-status":
            value = probe_status(root, args.claude)
        else:
            kwargs = {"prompt": (args.prompt_file if args.prompt_file.is_absolute() else root / args.prompt_file).read_text(), "executable": args.claude,
                      "timeout": args.timeout, "correction_round": args.correction_round,
                      "tool_timeout": args.tool_timeout, "turn_calls": args.max_tool_calls,
                      "progress": lambda value: print(json.dumps(value), file=sys.stderr, flush=True)}
            if args.review_packet is not None:
                path = args.review_packet if args.review_packet.is_absolute() else root / args.review_packet
                kwargs["review_packet"] = json.loads(path.read_text())
            if args.command == "start":
                kwargs.update(role=args.role, issue=args.issue)
                kwargs.update(replaces_agent=args.replaces_agent, replacement_reason=args.replacement_reason)
            else:
                kwargs["session"] = args.session
                kwargs["from_session"] = args.from_session
                if args.transition:
                    from workflow_handoff import input_file
                    kwargs["transition"] = json.loads(input_file(root, args.transition).read_text())
            value = run_turn(root, **kwargs)
        print(json.dumps(value, indent=2))
        if value.get("review_outcome") == "changes_requested":
            return 0  # a review that asks for changes is a successful dispatch
        return 0 if value.get("status") not in ("failed", "incomplete", "missing") else 1
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    # Bash timeouts and an explicit kill must reach run_turn's cleanup, so the
    # retained CLI child cannot keep editing after its transport parent exits.
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main())
