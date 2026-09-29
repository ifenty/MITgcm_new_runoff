"""Read human project records and retain one validated history row per iteration."""
import json
import re
from project import STATE, atomic_bytes, local, require


def unfenced(text):
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None:
            lines.append(line)
    return '\n'.join(lines)


def issues(root, closed=False, overrides=None):
    """Parse level-two issue entries; fenced blank examples are never live issues."""
    name = 'closed_issues.md' if closed else 'open_issues.md'
    text = unfenced(overrides[name] if overrides and name in overrides else local(root, name).read_text())
    entries = {}
    for block in re.split(r'(?m)^## ', text)[1:]:
        uuid = re.search(r'^\*\*UUID\*\*\s*:\s*(\S+)\s*$', block, re.M)
        if not uuid:
            require(not re.search(r'UNRESOLVED|INVESTIGATING|BLOCKED|RESOLVED|FALSE POSITIVE', block.splitlines()[0]),
                    f'{name}: issue heading lacks a UUID')
            continue
        iid = uuid[1]
        require(iid not in entries, f'{name}: duplicate UUID {iid}')
        status = re.search(r'^\*\*Status\*\*\s*:\s*([^\n]+)', block, re.M)
        require(status, f'{iid}: missing Status')
        state = status[1].split(' — ')[0].strip().lower()
        allowed = ('resolved', 'false positive') if closed else ('unresolved', 'investigating', 'blocked')
        require(state in allowed, f'{iid}: invalid status {state}')
        blocker = re.search(r'^\*\*Blocked-By\*\*\s*:\s*([^\n]+)', block, re.M)
        require((state == 'blocked') == bool(blocker), f'{iid}: blocked status and Blocked-By must agree')
        if blocker:
            require(' — ' in blocker[1] and blocker[1].split(' — ', 1)[1].strip(), f'{iid}: explain the blocker')
        anchors = re.search(r'^\*\*Anchors\*\*\s*:\s*([^\n]+)', block, re.M)
        entries[iid] = {'id': iid, 'title': block.splitlines()[0], 'state': state,
                        'blocker': blocker[1] if blocker else None,
                        'anchors': anchors[1] if anchors else None, 'text': block}
    return entries


def validate_records(root, overrides=None):
    opened, closed = issues(root, overrides=overrides), issues(root, True, overrides)
    require(not opened.keys() & closed.keys(), 'an issue appears in both open and closed records')
    for row in opened.values():
        if row['blocker']:
            dependency = row['blocker'].split(' — ', 1)[0]
            require(dependency in opened or dependency in closed or dependency in ('EXTERNAL', 'OWNER-DECISION'),
                    f"{row['id']}: unknown blocker {dependency}")
    index = unfenced(local(root, 'lessons_learned.md').read_text())
    evidence = unfenced(local(root, 'lessons_learned_evidence.md').read_text())
    active = re.findall(r'\[(LL-\d+)\]', index)
    archived = re.findall(r'^## .*\[(LL-\d+)\]', evidence, re.M)
    require(len(active) == len(set(active)), 'duplicate lesson ID in active index')
    require(len(archived) == len(set(archived)), 'duplicate lesson ID in evidence archive')
    require(set(active).issubset(archived), 'active lesson lacks an evidence entry')
    return opened, closed, set(active)


def json_lines(path):
    """Refuse malformed records so incomplete evidence cannot enter the history."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def save_history(root, done):
    """Persist full validated closeout data, including Git and communication.

    Revalidation of the last (id, timestamp) refreshes its snapshot atomically.
    Earlier physical lines are preserved, and identical repeats perform no write.
    One coordinating loop owns this file; concurrent writers are unsupported.
    """
    path = local(root, f'{STATE}/loop_history.jsonl')
    rows = json_lines(path)
    data = (json.dumps(done, sort_keys=True) + '\n').encode()
    if rows and (rows[-1]['id'], rows[-1]['timestamp']) == (done['id'], done['timestamp']):
        if rows[-1] == done:
            return False
        lines = path.read_bytes().splitlines(keepends=True)
        last = max(i for i, line in enumerate(lines) if line.strip())
        lines[last] = data
        atomic_bytes(path, b''.join(lines))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('ab') as stream:
            stream.write(data)
    return True
