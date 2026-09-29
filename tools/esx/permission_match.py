#!/usr/bin/env python3
"""Decide whether an original Bash command is already allowed by project settings.

The retained-runtime PreToolUse hook rewrites Bash through bounded_command, and
Claude Code evaluates permissions against the rewritten string, which no project
allow rule can match. The hook therefore judges the ORIGINAL command here and
grants only what the merged settings already grant. The matcher is deliberately
never looser than Claude's own: any construct it cannot split with certainty
(command/process substitution, subshells, file redirection, heredocs, background
jobs) yields no decision, so Claude's normal permission check applies unchanged.
"""
import fnmatch
import json
import os
from pathlib import Path

# Redirections that write nowhere and read nothing; everything else is refused.
SAFE_REDIRECTS = ('2>&1', '1>&2', '>&2', '>/dev/null', '1>/dev/null', '2>/dev/null', '&>/dev/null')
MANAGED = (Path('/etc/claude-code/managed-settings.json'),
           Path('/Library/Application Support/ClaudeCode/managed-settings.json'))


def settings_files(root, config_dir=None):
    """Every settings source that can carry permission rules, most general first."""
    config = Path(config_dir or os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')
    root = Path(root)
    return [*MANAGED, config / 'settings.json', root / '.claude/settings.json',
            root / '.claude/settings.local.json']


def load_rules(root, config_dir=None):
    """Merge allow/ask/deny Bash rules; an unreadable source contributes deny-all."""
    rules = {'allow': [], 'ask': [], 'deny': []}
    for path in settings_files(root, config_dir):
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text())
            permissions = value.get('permissions') or {}
        except (OSError, ValueError, AttributeError):
            rules['deny'].append('Bash')  # fail closed: never grant around a broken policy
            continue
        for kind in rules:
            for rule in permissions.get(kind) or []:
                if isinstance(rule, str) and (rule == 'Bash' or rule.startswith('Bash(')):
                    rules[kind].append(rule)
    return rules


def rule_matches(rule, segment):
    """Match one simple command against one Bash(...) rule."""
    if rule == 'Bash' or rule == 'Bash(*)':
        return True
    if not (rule.startswith('Bash(') and rule.endswith(')')):
        return False
    body = rule[5:-1]
    if body.endswith(':*'):
        prefix = body[:-2]
        return segment == prefix or segment.startswith(prefix + ' ')
    if body.endswith(' *') and '*' not in body[:-2]:
        prefix = body[:-2]
        return segment == prefix or segment.startswith(prefix + ' ')
    if '*' in body:
        return fnmatch.fnmatchcase(segment, body)
    return segment == body


def split_command(command):
    """Split on unquoted ;, &&, ||, | and newlines; None when the shape is uncertain."""
    segments, current, quote, index = [], [], None, 0
    while index < len(command):
        char = command[index]
        pair = command[index:index + 2]
        if quote == "'":
            current.append(char)
            if char == "'":
                quote = None
            index += 1
            continue
        if char == '\\':
            current.append(command[index:index + 2])
            index += 2
            continue
        if char == '`' or pair in ('$(', '<(', '>('):
            return None  # substitution executes text the matcher never sees
        if quote == '"':
            current.append(char)
            if char == '"':
                quote = None
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
            current.append(char)
            index += 1
            continue
        if pair in ('&&', '||'):
            segments.append(''.join(current))
            current = []
            index += 2
            continue
        if char in ';|\n':
            segments.append(''.join(current))
            current = []
            index += 1
            continue
        if char in '(){}':
            return None  # subshells and groups
        if char in '<>&':
            # Only unquoted operators matter; quoted text such as python3 -c "a > b"
            # is data. Discarding output is fine; any other redirect, heredoc or
            # background job gets no decision.
            safe = redirect_at(command, index)
            if safe is None:
                return None
            start, end = safe
            if start < index:
                current.pop()  # the file-descriptor digit already consumed
            index = end
            continue
        current.append(char)
        index += 1
    if quote:
        return None
    segments.append(''.join(current))
    cleaned = [' '.join(segment.split()) for segment in segments if segment.strip()]
    return cleaned or None


def redirect_at(command, index):
    """Span of a whole-token safe redirect at an unquoted operator, else None."""
    for token in sorted(SAFE_REDIRECTS, key=len, reverse=True):
        start = index - 1 if token[0].isdigit() else index
        if start < 0 or not command.startswith(token, start):
            continue
        end = start + len(token)
        before_ok = start == 0 or command[start - 1].isspace()
        after_ok = end == len(command) or command[end].isspace() or command[end] in ';|&'
        if before_ok and after_ok:
            return start, end
    return None


def decide(command, rules):
    """Return 'deny', 'allow', or None (no decision; Claude's own check applies)."""
    whole = ' '.join(command.split())
    if any(rule_matches(rule, whole) for rule in rules['deny']):
        return 'deny'
    segments = split_command(command)
    if segments is None:
        return None
    if any(rule_matches(rule, s) for s in segments for rule in rules['deny']):
        return 'deny'
    if any(rule_matches(rule, s) for s in segments for rule in rules['ask']):
        return None
    if all(any(rule_matches(rule, s) for rule in rules['allow']) for s in segments):
        return 'allow'
    return None
