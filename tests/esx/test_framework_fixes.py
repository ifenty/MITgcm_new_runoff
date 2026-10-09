"""Regression guards for the ESX-Team framework fixes made on 2026-10-06.

Why this file exists
====================

`tools/esx/` is a vendored ESX-Team kit (``ESX-team-local/version`` records the
installed release) and ``ESX-team-local/deployments/`` shows that upgrades
overwrite it. A fix applied here can therefore be silently reverted by the next
upgrade. Each test below pins one fixed defect by its *observable behaviour*, so
a revert fails the structural suite instead of passing quietly.

That is the same discipline the fixes themselves are about (lesson LL-014): a
list of applied patches is not coverage, because nothing measures it. These
tests perturb the mechanism and require the output to change.

Every test names the framework issue it guards.
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "esx"
sys.path.insert(0, str(TOOLS))


def interpreters():
    """Every distinct CPython on this host, newest-version-first, deduplicated.

    The cross-version guards need at least two; they skip rather than fail when
    only one exists, because that is a host property and not a defect.
    """
    found = {}
    for candidate in (sys.executable,
                      "/home/ifenty/miniforge3/envs/ecco/bin/python",
                      "/home/ifenty/miniforge3/bin/python3",
                      shutil.which("python3"),
                      "/usr/bin/python3"):
        if not candidate or not os.path.exists(candidate):
            continue
        try:
            version = subprocess.run(
                [candidate, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if version:
            found.setdefault(version, candidate)
    return found


# --------------------------------------------------------------------------
# TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001
# --------------------------------------------------------------------------

CONTEXT_PROBE = r"""
import sys
sys.path.insert(0, %r)
import doc_inventory
units = doc_inventory.python_units(open(%r).read(), 'probe.py')
print(units['<module>']['context'])
"""


def test_module_context_digest_is_interpreter_independent():
    """The module-context digest must not depend on the running interpreter.

    Guards TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001. The original implementation
    digested ``ast.dump(...)`` of a definition-stripped tree, which renders
    whichever fields the running interpreter's AST carries. Sealing a
    documentation report under one interpreter and checking it under another
    reported an unmodified tree as stale and blamed the document; measured on
    RUNOFF-005 at 3.10.19 against 3.13.12, and it cost two reviewers a must-fix
    each.

    Measured when this guard was written: the old form digested
    ``0b8ee0a7552f988d`` under 3.10.19 and ``0d6e7051475b14b9`` under 3.13.12,
    while the replacement gives ``a76a3507d87c09ab`` under both.
    """
    pythons = interpreters()
    if len(pythons) < 2:
        pytest.skip(f"needs two interpreters, found {sorted(pythons)}")
    target = TOOLS / "project.py"
    digests = {}
    for version, executable in pythons.items():
        proc = subprocess.run([executable, "-c", CONTEXT_PROBE % (str(TOOLS), str(target))],
                              capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, f"{version}: {proc.stderr[-400:]}"
        digests[version] = proc.stdout.strip()
    assert len(set(digests.values())) == 1, (
        "module-context digest differs by interpreter, so a sealed report will "
        f"read as stale under a different Python: {digests}")


def test_module_context_digest_tracks_module_level_code():
    """The digest must still change when module-level code changes.

    The companion to the test above: an interpreter-independent digest is
    worthless if it has become insensitive. A changed module-level constant
    must move the digest, and an edit confined to a function body must not.
    """
    import doc_inventory
    base = "VALUE = 1\n\n\ndef f():\n    return VALUE\n"
    constant_changed = "VALUE = 2\n\n\ndef f():\n    return VALUE\n"
    body_changed = "VALUE = 1\n\n\ndef f():\n    return VALUE + 0\n"

    def context(text):
        return doc_inventory.python_units(text, "probe.py")["<module>"]["context"]

    assert context(base) != context(constant_changed), (
        "a changed module-level constant must change the context digest")
    assert context(base) == context(body_changed), (
        "an edit confined to a function body must not change the context digest")


def test_module_context_does_not_use_ast_dump():
    """Structural backstop: the context digest must not be built from ast.dump.

    Cheap, and it survives a refactor that reintroduces the coupling while the
    cross-interpreter test happens to be skipped on a single-Python host.
    """
    source = (TOOLS / "doc_inventory.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and node.attr == "dump"
                and isinstance(node.value, ast.Name) and node.value.id == "ast"):
            raise AssertionError(
                "doc_inventory calls ast.dump again; its output is "
                "interpreter-dependent (TEAM-DOCCONTRACT-AST-DUMP-DIGEST-001)")


# --------------------------------------------------------------------------
# TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001
# --------------------------------------------------------------------------

def test_truncated_stale_listing_cannot_be_counted_as_a_total():
    """A partial stale listing must not be readable under the 'hits' key.

    Guards TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001. `lines` and the listing
    answer different questions inside one returned dict, and the listing is the
    natural thing to count. On RUNOFF-005 that produced the figure 199 -- the
    capped list of 200 minus one self-reference -- in permanent prose in the
    documentation contract, where the true total was 335. It survived a reviewer
    pass and was caught only because a reviewer re-measured a number it had no
    particular reason to doubt.

    So a truncated result carries 'hits_sample', not 'hits': counting it is
    still possible, but reading it under the old key now raises instead of
    returning a plausible wrong number.
    """
    import doc_contract
    figures = [{'old': 'e', 'new': '', 'note': 'matches almost every line'}]

    full = doc_contract.stale_lines(ROOT, figures, limit=10 ** 6)
    assert full['truncated'] == 0
    assert 'hits' in full and 'hits_sample' not in full
    assert len(full['hits']) == full['lines']

    partial = doc_contract.stale_lines(ROOT, figures, limit=5)
    assert partial['lines'] > 5, "probe figure must overflow the limit to be a real test"
    assert 'hits' not in partial, (
        "a truncated listing is still readable as 'hits', so counting it yields "
        "a plausible wrong total")
    assert partial['hits_sample'] and len(partial['hits_sample']) == 5
    assert partial['truncated'] == partial['lines'] - 5
    assert partial['limit'] == 5
    assert doc_contract.listed(partial) == partial['hits_sample']
    assert doc_contract.listed(full) == full['hits']


def test_stale_listing_callers_use_the_accessor():
    """No caller may index 'hits' directly, which breaks on a truncated result.

    `brief.py` reads the listing with limit=60 and would raise on any project
    with more matches; the accessor is the supported route.
    """
    for name in sorted(p.name for p in TOOLS.glob("*.py")):
        if name == "doc_contract.py":
            continue
        source = (TOOLS / name).read_text()
        assert "['hits']" not in source and '["hits"]' not in source, (
            f"{name} indexes a stale_lines listing directly; use "
            "doc_contract.listed() (TEAM-DOCCONTRACT-STALE-HITS-TRUNCATION-001)")


# --------------------------------------------------------------------------
# TEAM-DOCCONTRACT-NAVIGATE-REUSE-MAP-001
# --------------------------------------------------------------------------

def test_reuse_args_accepts_a_change_to_its_own_declared_map():
    """An orientation's own --map section must be inside its declared scope.

    Guards TEAM-DOCCONTRACT-NAVIGATE-REUSE-MAP-001. `--reuse-args` tested
    changed references for membership in targets+documents, but an orientation
    stores its map in a third field, so a change confined to the declared map
    section was reported as "outside the original orientation's declared
    targets and documents" and the caller had to retype every argument the
    receipt already held. Reproduced four times across three agents on
    RUNOFF-013, with a positive control: it accepted when the changed reference
    was a declared --target.

    This test reads the membership set that decides the refusal, rather than
    driving the CLI, because constructing a real stale orientation needs a
    sealed baseline and a mutated tree.
    """
    source = (TOOLS / "doc_contract.py").read_text()
    tree = ast.parse(source)
    assignments = [node for node in ast.walk(tree)
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "declared" for t in node.targets)]
    assert assignments, "doc_contract no longer builds a 'declared' membership set"
    for node in assignments:
        fields = {n.value for n in ast.walk(node.value)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        assert "map" in fields, (
            "the 'declared' set omits the orientation's own map field, so a change "
            "confined to the declared --map section will be refused as outside its "
            "own scope (TEAM-DOCCONTRACT-NAVIGATE-REUSE-MAP-001); fields seen: "
            f"{sorted(fields)}")
        assert {"targets", "documents"} <= fields, (
            "the 'declared' set must still contain targets and documents, so a "
            f"genuinely undeclared reference is still refused; fields: {sorted(fields)}")


# --------------------------------------------------------------------------
# TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001
# TEAM-ACCEPTANCE-POLICY-EDIT-STRANDS-APPROVALS-001
# --------------------------------------------------------------------------

def test_stale_sweep_reaches_record_documents():
    """A superseded figure in a record document must be findable.

    Guards TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001. Records are excluded
    from `inventory_paths` on purpose, because that set is also the acceptance
    scope -- but "outside acceptance" was being read as "outside every
    mechanism", so a stale figure in `open_issues.md`, `lessons_learned.md` or a
    closed-issue entry received neither a sweep hit nor a disposition. On
    RUNOFF-013 that left `closed_issues.md:350` carrying, in the present tense,
    the same two stale tokens that had been a must-fix in
    `esx/project_profile.md` two rounds earlier.

    Measured when this guard was written: a figure present only in record
    documents gave 0 hits under the inventory-only scope and 2 under the
    inventory-plus-records scope. This test uses a controlled probe written into
    a temporary record document, so it does not depend on any current content.
    """
    import doc_contract
    import project
    from doc_inventory import paths

    # Assembled at runtime so the literal never appears in this file. A literal
    # would be found by the sweep in the test source itself -- `tests/` is
    # inside the inventory -- which is the self-reference trap that made a
    # hit count unusable on RUNOFF-013 (see LL-015).
    token = "zzprobe" + "figure " + str(21 * 202) + " qqxz"
    probe = ROOT / "zz_probe_record_do_not_commit.md"
    assert not probe.exists(), "probe file already present; a previous run left it behind"
    figures = [{"old": token, "new": "", "note": "probe"}]
    try:
        probe.write_text(f"# probe\n\nThe figure {token} appears only here.\n")
        assert probe.name in set(project.record_paths(ROOT)) - set(paths(ROOT)), (
            "the probe is not a record outside the inventory, so this test is vacuous")
        hits = doc_contract.stale_lines(ROOT, figures, limit=10 ** 6)
        found = {hit["path"] for hit in doc_contract.listed(hits)}
        assert probe.name in found, (
            "the stale sweep does not reach record documents, so a superseded "
            "figure in one cannot be found by any mechanism; swept "
            f"{hits['lines']} line(s), found {sorted(found)[:4]}")
    finally:
        probe.unlink(missing_ok=True)

    # Negative control: with the record gone the probe must find nothing, so the
    # hit above came from the record and not from somewhere in the inventory.
    assert doc_contract.stale_lines(ROOT, figures, limit=10 ** 6)["lines"] == 0, (
        "the probe token survives the probe file, so the positive result above "
        "may be a self-reference rather than a record-document hit")


def test_record_membership_is_enumerated_not_listed():
    """Record membership must be derived, so a new record cannot land outside.

    Guards the acceptance criterion of TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001.
    Three successive hand-counts of this boundary gave 1, 10 and 44, and only the
    mechanical enumeration was right (lesson LL-016), so the test creates a new
    record document and requires it to be picked up without any constant being
    edited.
    """
    import importlib
    import project

    probe = ROOT / "zz_probe_record_do_not_commit.md"
    assert not probe.exists(), "probe file already present; a previous run left it behind"
    try:
        probe.write_text("# probe\n\nA new record document.\n")
        importlib.reload(project)
        assert probe.name in project.record_paths(ROOT), (
            "a newly added root-level record document is not picked up, so record "
            "membership is a hand-maintained list rather than an enumeration")
    finally:
        probe.unlink(missing_ok=True)
        importlib.reload(project)


def test_acceptance_boundary_is_queryable_and_correct():
    """A coordinator must be able to ask whether an edit strands approvals.

    Guards TEAM-ACCEPTANCE-POLICY-EDIT-STRANDS-APPROVALS-001. `source_signature`
    digests exactly `inventory_paths`, so the sealed documentation report and
    every reviewer approval are invalidated by the same files in one event. On
    RUNOFF-013 an Arch edit to one policy file after the seal stranded an
    approval and cost a correction round for no code change, and the boundary
    was not knowable in advance from anything but a remembered list.
    """
    import project

    policy = project.acceptance_scope(ROOT, "devel-loop/documentation_contract.md")
    assert policy["in_acceptance"] is True, (
        "a policy document inside FRAMEWORK_PATHS must report as inside the "
        "acceptance scope, since editing it strands every approval")
    assert policy["is_record"] is False
    assert "invalidates the sealed documentation report" in policy["effect"]

    for name in ("open_issues.md", "lessons_learned.md", "closed_issues.md"):
        record = project.acceptance_scope(ROOT, name)
        assert record["in_acceptance"] is False, (
            f"{name} reports as inside the acceptance scope; a record-only "
            "correction round would then strand every reviewer approval")
        assert record["is_record"] is True
        assert record["swept_for_stale_figures"] is True, (
            f"{name} is outside acceptance and also unswept, which is the hole "
            "TEAM-DOCINVENTORY-LEDGER-UNINVENTORIED-001 describes")

    # The one carve-out: an issue's own acceptance criteria are policy in
    # substance, because they are what a reviewer judges against.
    assert "Proposed action and acceptance" in project.acceptance_scope(ROOT, "open_issues.md")["effect"]


def test_signature_scope_still_excludes_records():
    """Records must stay out of source_signature, or the corollary dies.

    The two framework issues are in tension: inventorying the records would move
    them inside the signature and silently void the rule that a record-only
    round need not strand an approval. This test pins the resolution -- the
    sweep scope was widened, the acceptance scope was not.
    """
    import project
    from doc_inventory import paths

    inventory = set(paths(ROOT))
    for name in ("open_issues.md", "lessons_learned.md", "closed_issues.md",
                 "devel-loop/self-improvement/open-ESX-team-issues.md"):
        assert name not in inventory, (
            f"{name} entered the inventory, which is also the acceptance scope, so "
            "editing it now strands every reviewer approval "
            "(TEAM-ACCEPTANCE-POLICY-EDIT-STRANDS-APPROVALS-001)")

    before = project.source_signature(ROOT)
    probe = ROOT / "zz_probe_record_do_not_commit.md"
    try:
        probe.write_text("# probe\n")
        assert project.source_signature(ROOT) == before, (
            "adding a record document moved the candidate signature, so a "
            "record-only correction round strands approvals")
    finally:
        probe.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# TEAM-NOTIFY-OUTAGE-NO-BACKOFF-001
# --------------------------------------------------------------------------

def test_settled_outage_backs_off_instead_of_probing_every_iteration():
    """A provider that keeps answering `down` must be asked less often.

    Guards TEAM-NOTIFY-OUTAGE-NO-BACKOFF-001. On RUNOFF-013 a Slack provider
    that had never been configured was probed 73 times across 85 loop
    iterations, every probe returning the identical `claude mcp list` output,
    with 14 renewals on top; loop iterations 13-85 produced no scientific work.

    The streak counts consecutive `down` results rather than identical evidence,
    because the RUNOFF-013 probe evidence was free text that differed by an
    iteration number each time -- an evidence comparison would never have fired.

    Measured when this guard was written: replaying the same 85-iteration shape
    demands 6 probes with backoff against 85 without.
    """
    import notifications

    outage = {"down_streak": 0, "last_probe_iteration": 1,
              "bound_iteration": 1, "covered_since_probe": 0}
    demanded = 0
    for iteration in range(1, 86):
        if notifications.probe_due(outage, iteration):
            demanded += 1
            outage["last_probe_iteration"] = iteration
            outage["down_streak"] += 1
            if notifications.expired(outage, iteration):
                outage["bound_iteration"] = iteration
    assert demanded <= 12, (
        f"a settled outage still demands {demanded} probes across 85 iterations; "
        "RUNOFF-013 spent 73 of 100 loop iterations this way")
    assert notifications.backoff(outage) == notifications.OUTAGE_BACKOFF_MAX


def test_outage_backoff_stays_tight_for_a_provider_that_might_recover():
    """Backoff must not slow the cadence for an unsettled outage.

    The companion control: a fresh outage, and one whose streak was reset,
    keeps the per-iteration cadence, because that is a provider that might come
    back and whose queued events should go out promptly.
    """
    import notifications

    fresh = {"down_streak": 0, "last_probe_iteration": 4,
             "bound_iteration": 4, "covered_since_probe": 0}
    assert notifications.backoff(fresh) == 1
    assert notifications.probe_due(fresh, 5), (
        "a fresh outage must still be re-probed on the next iteration")
    assert not notifications.probe_due(fresh, 4), (
        "a probe recorded this iteration must satisfy the demand")


def test_communication_demand_does_not_hide_the_next_instruction():
    """The gate must report the work even when a communication demand is due.

    Guards the second half of TEAM-NOTIFY-OUTAGE-NO-BACKOFF-001. `next()` used
    to print the communication notice and return, so an idle cycle paid the
    probe toll before learning there was nothing new to do.
    """
    source = (TOOLS / "loop_gate.py").read_text()
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef)}
    assert "_next_instruction" in functions, (
        "loop_gate.next no longer defers the communication notice")
    body = ast.get_source_segment(source, functions["_next_instruction"]) or ""
    offending = [line for line in body.splitlines()
                 if "notifications.notice" in line and "_deferred_notice" not in line]
    assert not offending, (
        "the communication notice is consumed inside the instruction path again, "
        f"which lets it pre-empt the work: {offending}")


# --------------------------------------------------------------------------
# TEAM-LOOPGATE-CHECKSTART-CORRECTION-ROUND-001
# --------------------------------------------------------------------------

def test_check_start_has_an_honest_correction_round_path():
    """A correction round must be able to pass --check-start without lying.

    Guards TEAM-LOOPGATE-CHECKSTART-CORRECTION-ROUND-001. The gate compared the
    prepare-time orientation against the working tree, so once any work had
    legitimately changed an oriented target it could never pass again. The
    remedy it printed -- navigate again -- did not clear it, leaving only
    `--late-reason` (which overwrites an honest on-time receipt with one
    asserting the gate was skipped) or `--prepare` (which destroys the round's
    review history). Reproduced end to end on RUNOFF-013 after an implementer
    refused both escape hatches on record-integrity grounds.

    The fix accepts a freshly re-navigated orientation **only** when the
    iteration already has a validated start receipt, so a genuinely skipped
    gate still refuses.
    """
    import doc_contract

    assert hasattr(doc_contract, "latest_orientation"), (
        "doc_contract.latest_orientation is gone, so --check-start has no way to "
        "accept a re-navigated orientation in a correction round")

    source = (TOOLS / "loop_gate.py").read_text()
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef)}
    body = ast.get_source_segment(source, functions["_check_start"]) or ""

    assert "latest_orientation" in body, (
        "_check_start does not consult a refreshed orientation, so a correction "
        "round is back to falsifying the receipt or resetting the iteration")
    assert "start_status" in body, (
        "_check_start accepts a refreshed orientation without requiring a prior "
        "validated receipt, so work that began unauthorized would now pass")
    # The late path must survive: it is what a genuinely skipped gate needs.
    assert "late_reason" in body


def test_latest_orientation_rejects_other_issues_roles_and_baselines(monkeypatch, tmp_path):
    """The refreshed orientation must belong to this issue, baseline and role.

    Isolates the filter: `validate_orientation` is stubbed to accept, so the
    only thing under test is which receipts are considered candidates at all. A
    receipt from another issue, role or baseline must never be returned, because
    that would let --check-start pass on an orientation nobody wrote for this
    work.
    """
    import doc_contract

    store = tmp_path / "devel-loop" / "loop_state" / "maintenance"
    store.mkdir(parents=True)
    base = {"path": "b.json", "sha256": "b" * 64}
    other = {"path": "c.json", "sha256": "c" * 64}

    def write(name, **overrides):
        record = {"kind": "orientation", "issue_id": "ISSUE-1", "role": "arch",
                  "baseline": base, "created_at": "2026-01-01T00:00:00+00:00"}
        record.update(overrides)
        (store / f"{name}.json").write_text(json.dumps(record))

    write("a" * 64, created_at="2026-01-01T00:00:00+00:00")
    write("d" * 64, created_at="2026-02-01T00:00:00+00:00")       # newest match
    write("e" * 64, issue_id="ISSUE-2", created_at="2026-03-01T00:00:00+00:00")
    write("f" * 64, role="scout", created_at="2026-03-01T00:00:00+00:00")
    write("0" * 64, baseline=other, created_at="2026-03-01T00:00:00+00:00")

    monkeypatch.setattr(doc_contract, "validate_orientation",
                        lambda *a, **k: None)

    picked = doc_contract.latest_orientation(tmp_path, "ISSUE-1", base, "arch")
    assert picked is not None and picked["sha256"] == "d" * 64, (
        f"the newest matching orientation was not chosen: {picked}")
    assert doc_contract.latest_orientation(tmp_path, "ISSUE-2", base, "arch")["sha256"] == "e" * 64
    assert doc_contract.latest_orientation(tmp_path, "NO-SUCH", base, "arch") is None
    assert doc_contract.latest_orientation(tmp_path, "ISSUE-1", base, "bob") is None, (
        "an orientation recorded for another role was accepted")
    # A baseline no receipt was written against must find nothing. (`other` is
    # deliberately not used here: a receipt *was* written against it, so finding
    # that one is correct behaviour, not a leak.)
    unused = {"path": "z.json", "sha256": "9" * 64}
    assert doc_contract.latest_orientation(tmp_path, "ISSUE-1", unused, "arch") is None, (
        "an orientation recorded against another baseline was accepted")
    assert doc_contract.latest_orientation(tmp_path, "ISSUE-1", other, "arch")["sha256"] == "0" * 64


def test_latest_orientation_requires_a_fresh_receipt(monkeypatch, tmp_path):
    """A stale candidate must be skipped, not returned.

    Without this, --check-start would accept a re-navigation that is itself out
    of date, which is the condition it exists to detect.
    """
    import doc_contract

    store = tmp_path / "devel-loop" / "loop_state" / "maintenance"
    store.mkdir(parents=True)
    base = {"path": "b.json", "sha256": "b" * 64}
    (store / f"{'a' * 64}.json").write_text(json.dumps(
        {"kind": "orientation", "issue_id": "ISSUE-1", "role": "arch",
         "baseline": base, "created_at": "2026-01-01T00:00:00+00:00"}))

    def refuse(*args, **kwargs):
        raise ValueError("stale arch orientation: receipt=...")

    monkeypatch.setattr(doc_contract, "validate_orientation", refuse)
    assert doc_contract.latest_orientation(tmp_path, "ISSUE-1", base, "arch") is None, (
        "a stale orientation was accepted as a refresh")


# --------------------------------------------------------------------------
# TEAM-PAUSE-EARLY-LIFT-001 / TEAM-PAUSE-DEADLINE-CLAMP-001
# --------------------------------------------------------------------------

def test_provider_limit_pause_is_not_lifted_before_a_known_reset():
    """A pause carrying a reset time must not be lifted by a 'working' turn.

    Guards TEAM-PAUSE-EARLY-LIFT-001. `pause_for_provider_limit` paused with
    `paused_until` set to the reset, and the Stop hook then classified a turn
    that merely ended with a summary message under the grace allowance as real
    work, lifted the pause and advanced the iteration about 90 minutes before
    the reset -- spending an iteration on a provider still refusing.

    With the reset unknown the lift is still correct, because nothing else can
    say the limit has cleared; this test pins both halves.
    """
    source = (TOOLS / "ralph_stop.py").read_text()
    tree = ast.parse(source)
    conditions = [node for node in ast.walk(tree)
                  if isinstance(node, ast.Compare)
                  and any(isinstance(c, ast.Constant) and c.value == "provider_limit"
                          for c in node.comparators)]
    assert conditions, "the provider-limit pause branch is gone from ralph_stop"

    # The branch that lifts the pause must also require an unknown reset time.
    lift = [seg for seg in source.split("elif ")
            if "pause_source(parsed) == 'provider_limit'" in seg]
    assert lift, "no elif branch lifts a provider-limit pause"
    assert "paused[1] is None" in lift[0], (
        "the auto-lift does not require an unknown reset time, so a 'working' "
        "turn can resume the loop before the provider limit has reset "
        "(TEAM-PAUSE-EARLY-LIFT-001)")


def test_a_nearly_spent_scope_deadline_does_not_kill_the_turn():
    """A scope deadline must leave a usable horizon or not bound the turn.

    Guards TEAM-PAUSE-DEADLINE-CLAMP-001. The scope clock runs through a
    provider-limit pause, so after a 93-minute outage the first resumed turn was
    clamped to the original issue deadline and killed after 33 minutes of work.
    The fully-elapsed case was already excluded; a deadline a few minutes in the
    future is equally fatal and was not.

    This module's own doctrine is that an exceeded nominal dimension is recorded
    and the work proceeds, so a nearly-spent deadline is an overrun to observe,
    not a turn to kill.
    """
    import team_budget

    assert 0 < team_budget.USABLE_TURN_FRACTION <= 1
    source = (TOOLS / "team_budget.py").read_text()
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef)}
    body = ast.get_source_segment(source, functions["reserve"]) or ""
    assert "USABLE_TURN_FRACTION" in body, (
        "reserve() no longer requires a scope deadline to leave a usable horizon")
    assert "if d > now]" not in body, (
        "a scope deadline is again accepted merely for being in the future, so a "
        "turn resumed near the deadline is killed at launch "
        "(TEAM-PAUSE-DEADLINE-CLAMP-001)")


def test_manual_pause_is_never_auto_lifted():
    """An owner or coordinator pause must only be cleared by an explicit resume.

    Measured on RUNOFF-013: a manual pause taken at iteration 85 held across
    several Stop-hook cycles without advancing the iteration, which is what
    bounds TEAM-PAUSE-EARLY-LIFT-001 to provider-limit pauses.
    """
    source = (TOOLS / "ralph_stop.py").read_text()
    lift = [seg for seg in source.split("elif ")
            if "pause_source(parsed) == 'provider_limit'" in seg]
    assert lift, "no elif branch lifts a provider-limit pause"
    assert "pause_source(parsed) == 'provider_limit'" in lift[0], (
        "the auto-lift no longer restricts itself to provider-limit pauses, so an "
        "owner pause could be cleared without an explicit resume")


# --------------------------------------------------------------------------
# TEAM-BRIEF-UNVALIDATED-INTERFACE-001
# --------------------------------------------------------------------------

def test_brief_interface_check_catches_nonexistent_flags():
    """A brief naming a flag the tool does not accept must be refused.

    Guards TEAM-BRIEF-UNVALIDATED-INTERFACE-001. On RUNOFF-013 a brief told the
    implementer to run `loop_gate.py --check-start --issue RUNOFF-013 --agent
    bob`; neither flag exists, and the gate is Arch's own rather than a
    per-agent permission check. The implementer measured that instead of
    complying; a less careful agent would have stalled or used an escape hatch
    that corrupts a receipt.
    """
    import brief

    bad = brief.interface_errors(
        ROOT, "run tools/esx/loop_gate.py --check-start --issue RUNOFF-013 --agent bob")
    assert any("--issue" in e for e in bad) and any("--agent" in e for e in bad), (
        f"the real RUNOFF-013 brief defect is no longer caught: {bad}")
    assert brief.interface_errors(ROOT, "tools/esx/nope_missing.py --x"), (
        "a brief naming a tool that does not exist is accepted")


def test_brief_interface_check_has_no_false_positives():
    """Legitimate commands must not be refused; a false refusal is worse.

    Subcommand flags are not listed by a top-level parser, and several brief
    sections name two commands on one line. Both produced false positives while
    this check was being written, which would have blocked every real brief.
    """
    import brief

    legitimate = [
        "tools/esx/loop_gate.py --check-start",
        "tools/esx/doc_contract.py navigate --issue X --reuse-args R --use Y",
        "tools/esx/verify.py --suite focused --owner abc --fresh",
        "tools/esx/notifications.py reprobe --provider slack --tool T --result down --probe-evidence E",
        "tools/esx/project.py signature",
        # Two commands on one line: the first must not be blamed for the second's flags.
        "Use tools/esx/project.py signature then tools/esx/verify.py --suite focused --owner X --fresh",
        # A *project* script after an ESX one: its flags belong to it, not to the
        # ESX command. This was the second false positive the check produced, on
        # a real brief, because the boundary only stopped at the next
        # `tools/esx/` path rather than at any following script.
        "Run tools/esx/verify.py --suite focused --owner X --fresh then "
        "tests/rnf/tendency_term_check.py --build",
        "tools/esx/doc_contract.py draft --issue X --previous P then "
        "tests/rnf/exf_heat_check.py --control --build",
    ]
    for command in legitimate:
        assert brief.interface_errors(ROOT, command) == [], (
            f"legitimate command refused, which would block real briefs: {command} -> "
            f"{brief.interface_errors(ROOT, command)}")


def test_generated_brief_states_the_required_footer_identity():
    """The brief must name the exact `agent` value, since a wrong one is silent.

    An agent cannot otherwise know that a descriptive name voids its record. On
    RUNOFF-013 all four completions of one reviewer were recorded `incomplete`
    because its footer said `richard-a`, a name Arch had used in every brief.
    """
    import brief

    # The active issue, not a hardcoded one: brief.build refuses a brief that
    # names any other issue ("brief must name the active issue"), so hardcoding
    # one makes this guard fail as soon as the loop moves on -- which it did.
    start = ROOT / "devel-loop" / "loop_state" / "issue-start.json"
    if not start.is_file():
        pytest.skip("no active iteration, so brief.build has no issue to name")
    issue = json.loads(start.read_text())["id"]
    design = ROOT / "devel-loop" / "loop_state" / "brief-probe-design.txt"
    design.parent.mkdir(parents=True, exist_ok=True)
    design.write_text("Probe design and acceptance for the brief identity guard.\n")
    try:
        text = brief.build(ROOT, "bob", issue, design.read_text())
    finally:
        design.unlink(missing_ok=True)
    assert 'The "agent" field must be exactly "bob"' in text, (
        "the brief no longer states the required footer agent value")
    assert "records the whole turn as `incomplete`" in text, (
        "the brief no longer says what a wrong agent value costs")


def test_gate_reports_uncaptured_completions():
    """The gate must surface a completion that failed capture validation.

    `agent_runtime` computes the exact error -- footer identity, unresolvable
    reference -- writes it to the dispatch log, and tells nobody. On RUNOFF-013
    four correct reviews sat unusable for hours because of that silence.
    """
    source = (TOOLS / "loop_gate.py").read_text()
    tree = ast.parse(source)
    functions = {node.name: node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef)}
    assert "defective_completions" in functions, (
        "loop_gate no longer detects uncaptured agent completions")
    body = ast.get_source_segment(source, functions["_next_instruction"]) or ""
    assert "defective_completions" in body, (
        "uncaptured completions are detected but never reported by --next, which "
        "is the silence that cost four reviews on RUNOFF-013")


# --------------------------------------------------------------------------
# TEAM-TRANSITION-EVIDENCE-001
# --------------------------------------------------------------------------

def test_transition_judgment_accepts_a_verify_evidence_reference(monkeypatch):
    """A judgment may cite a verify.py evidence reference exactly as returned.

    Guards TEAM-TRANSITION-EVIDENCE-001. `verify.py` names its artifact by a
    canonical-JSON digest and returns that digest as `sha256`, while the
    assessment validator hashed the raw file bytes -- so on RUNOFF-010 the first
    assessment citing a verify.py reference unchanged failed with "compatibility
    check evidence hash mismatch" and passed only after re-hashing the file by
    hand.
    """
    import runtime_recovery
    import verify

    seen = {}

    def accept(root, ref):
        seen["ref"] = ref
        return {"exit": 0, "stable": True}

    monkeypatch.setattr(verify, "load_evidence", accept)
    record = {"decision": "resume", "assessor": "arch",
              "reason": "The changed clause does not alter any interface this session depends on.",
              "check": {"command": "verify.py --suite focused", "executed": True, "exit": 0,
                        "evidence": {"path": "devel-loop/loop_state/verification/" + "a" * 64 + ".json",
                                     "sha256": "a" * 64}}}
    runtime_recovery.validate_assessment(ROOT, record)   # must not raise
    assert seen["ref"]["sha256"] == "a" * 64, (
        "the assessment no longer validates its evidence through verify.load_evidence")


def test_transition_judgment_still_rejects_a_bad_artifact(monkeypatch):
    """A reference that is neither valid verify.py evidence nor byte-matching fails."""
    import runtime_recovery
    import verify

    def refuse(root, ref):
        raise ValueError("invalid verification artifact path")

    monkeypatch.setattr(verify, "load_evidence", refuse)
    record = {"decision": "resume", "assessor": "arch",
              "reason": "The changed clause does not alter any interface this session depends on.",
              "check": {"command": "probe", "executed": True, "exit": 0,
                        "evidence": {"path": "devel-loop/loop_state/verification/" + "b" * 64 + ".json",
                                     "sha256": "b" * 64}}}
    with pytest.raises(ValueError, match="compatibility check evidence hash mismatch"):
        runtime_recovery.validate_assessment(ROOT, record)


def test_assess_transition_help_shows_the_judgment_format():
    """The judgment format must be in --help, not only in the source.

    Its acceptance criterion: "`--help` shows the required fields".
    """
    proc = subprocess.run([sys.executable, str(TOOLS / "agent_runtime.py"),
                           "assess-transition", "--help"],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-400:]
    for field in ('"decision"', '"assessor"', '"reason"', '"check"', '"evidence"', "exit"):
        assert field in proc.stdout, (
            f"assess-transition --help does not document {field}, so the judgment "
            "format is still source-only (TEAM-TRANSITION-EVIDENCE-001)")


def _gate_with_log(tmp_path, rows):
    """A Gate rooted at tmp_path whose dispatch log holds exactly `rows`."""
    import loop_gate
    state = tmp_path / 'devel-loop/loop_state'
    state.mkdir(parents=True)
    (state / 'dispatch_log.jsonl').write_text(
        ''.join(json.dumps(r) + '\n' for r in rows))
    gate = loop_gate.Gate.__new__(loop_gate.Gate)
    gate.root = tmp_path
    return gate


START = {'id': 'X-1', 'timestamp': '2026-01-01T00:00:00+00:00'}


def _record(status, *, agent='bob', agent_id='a1', rnd=1, footer=True, error=None):
    row = {'agent_type': agent, 'agent_id': agent_id, 'status': status,
           'issue_id': 'X-1', 'correction_round': rnd}
    if footer:
        row['footer'] = {'issue_id': 'X-1', 'iteration_timestamp': START['timestamp'],
                         'correction_round': rnd}
    if error:
        row['error'] = error
    return row


def test_defective_completion_cleared_by_reemission(tmp_path):
    """An incomplete record followed by a completed one for the same round is silent.

    TEAM-GATE-DEFECT-NOTICE-NOT-SUPERSEDED-001. Measured on RUNOFF-030: the log
    held one incomplete bob round-1 record and three completed round-1 records,
    and the gate still advised resuming the agent to re-emit a footer it had
    re-emitted five records earlier.
    """
    gate = _gate_with_log(tmp_path, [
        _record('incomplete', error='evidence is stale'),
        _record('completed'),
        _record('completed'),
    ])
    assert gate.defective_completions(START) == []


def test_defective_completion_still_reported_when_never_repaired(tmp_path):
    """The case the notice exists for must survive the suppression."""
    gate = _gate_with_log(tmp_path, [_record('incomplete', error='stale orientation')])
    assert gate.defective_completions(START) == [('bob', 'a1', 1, 'stale orientation')]


def test_defective_completion_suppression_is_per_round(tmp_path):
    """Repairing round 1 must not vouch for a broken round 2."""
    gate = _gate_with_log(tmp_path, [
        _record('incomplete', rnd=1, error='bad'),
        _record('completed', rnd=1),
        _record('incomplete', rnd=2, error='round two broken'),
    ])
    assert gate.defective_completions(START) == [('bob', 'a1', 2, 'round two broken')]


def test_footerless_consultation_turn_is_not_a_defect(tmp_path):
    """A turn instructed to emit no footer, later superseded, is not uncaptured.

    The RUNOFF-030 diagnosis checkpoint brief said verbatim "Answer in plain
    prose. No footer, no orientation receipt, no suite run." The capture gate
    recorded the result as a malformed footer, and the notice then advised
    resuming an agent that had done exactly as instructed -- penalising the
    cheapest correct way to hold a checkpoint.
    """
    rows = [
        _record('completed', agent='richard', agent_id='r1', rnd=3),
        {'agent_type': 'richard', 'agent_id': 'r1', 'status': 'incomplete',
         'issue_id': 'X-1', 'error': 'missing, malformed, or mismatched structured footer'},
        _record('completed', agent='richard', agent_id='r1', rnd=4),
    ]
    assert _gate_with_log(tmp_path, rows).defective_completions(START) == []


def test_footerless_turn_reported_when_agent_never_reports_again(tmp_path):
    """A genuinely lost completion is not excused by the footer-less rule."""
    rows = [{'agent_type': 'richard', 'agent_id': 'r9', 'status': 'incomplete',
             'issue_id': 'X-1', 'error': 'missing, malformed, or mismatched structured footer'}]
    assert _gate_with_log(tmp_path, rows).defective_completions(START) == [
        ('richard', 'r9', None, 'missing, malformed, or mismatched structured footer')]


def test_verification_run_holds_the_iteration(tmp_path):
    """A live project-owned verification run is detected, so the loop can hold it.

    TEAM-LOOPHOLD-ARCH-BACKGROUND-WORK-001. The final scientific verification is
    Arch-owned by workflow design and runs about two hours, so before this check
    every Stop cycle during it advanced the iteration: measured on RUNOFF-030 as
    CONTINUE iteration=4 and iteration=5 eighty seconds apart during a 6629 s
    run. The negative control is the point of the test -- a run in a DIFFERENT
    checkout must not hold this loop.
    """
    import ralph_stop
    script = tmp_path / 'tools/esx/final_verification.py'
    script.parent.mkdir(parents=True)
    script.write_text('import time\ntime.sleep(30)\n')
    other = tmp_path / 'other'
    other.mkdir()

    proc = subprocess.Popen([sys.executable, str(script)], cwd=tmp_path)
    foreign = subprocess.Popen([sys.executable, str(script)], cwd=other)
    try:
        for _ in range(50):
            found = ralph_stop.verification_running(tmp_path)
            if found:
                break
            time.sleep(0.1)
        assert [r['script'] for r in found] == ['tools/esx/final_verification.py']
        assert found[0]['pid'] == proc.pid
        # The same script running in another checkout is not this loop's work.
        assert [(r['script'], r['minutes'], r['pid']) for r in ralph_stop.verification_running(other)] == [
            ('tools/esx/final_verification.py', 0, foreign.pid)]
        assert len(ralph_stop.verification_running(tmp_path)) == 1
    finally:
        proc.kill(); foreign.kill()
        proc.wait(); foreign.wait()
    assert ralph_stop.verification_running(tmp_path) == []


def test_command_span_stops_at_a_quote():
    """A command inside embedded JSON must not absorb that payload's prose.

    TEAM-BRIEF-COMMAND-SPAN-QUOTES-001. `brief.build` embeds the whole reviewed
    packet, so a command recorded in a captured footer is followed by the
    footer's own prose. On RUNOFF-040 an implementer's independent_check held
    `tools/esx/verify.py --suite focused --owner ... --fresh` and its coverage
    then mentioned `--mpi 2`; with no `.py` between them the span swallowed the
    prose and the brief was refused for a flag it never named, blocking the
    review dispatch. This check validates commands a brief tells an agent to
    run, not payload it quotes.
    """
    import brief
    payload = ('"cmd": "python tools/esx/verify.py --suite focused --owner a1 --fresh", '
               '"coverage": "refusal_check --mpi 2 was run outside verify.py"')
    # Rooted at the real tree, so the tools resolve and the flags are really
    # introspected; rooted at a scratch dir this would pass vacuously.
    assert brief.interface_errors(ROOT, payload) == []

    # The real flag error this check exists for is still caught.
    assert brief.interface_errors(
        ROOT, 'run tools/esx/loop_gate.py --check-start --issue X --agent bob') == [
        'loop_gate.py does not accept --agent',
        'loop_gate.py does not accept --issue']


def test_signal_is_not_classified_as_a_timeout():
    """A signalled run must not be filed as a verdict on the candidate.

    TEAM-VERIFY-SIGNAL-MISCLASSIFIED-001. The filed root cause was wrong and
    this records the real one: `InterruptedError` is a subclass of `OSError`,
    so while the `except (OSError, TimeoutExpired)` arm sat above the signal
    arm, every signal was caught there and recorded as `rc, timed_out = 124,
    True`. `timed_out` then short-circuits `interruption()`, so RUNOFF-040's
    killed final verification was recorded as "verification failed (exit 124)"
    -- suite scientific, stable TRUE -- against a candidate two reviewers had
    approved, with zero FAIL tokens in its log.
    """
    import verify
    assert issubclass(InterruptedError, OSError), 'the whole defect rests on this'

    source = (ROOT / 'tools/esx/verify.py').read_text()
    signal_arm = source.index('except (KeyboardInterrupt, InterruptedError)')
    oserror_arm = source.index('except (OSError, subprocess.TimeoutExpired)')
    assert signal_arm < oserror_arm, 'the signal arm must precede the OSError arm'

    # The marker test does not depend on the sign of rc, which is the second
    # half: a process-group signal arrives as a POSITIVE status.
    killed = 'COMMAND x\nverification received signal 15'
    assert verify.interruption(124, killed) == 'run received signal 15'
    assert verify.interruption(-15, 'no marker') == 'child terminated by signal 15'

    # A genuine per-command timeout must STILL be a verdict on a hung
    # candidate, which is what verify.py:173 intends; over-reaching here would
    # convert real hangs into interruptions.
    assert verify.interruption(124, 'Command timed out after 3600 seconds') is None
    assert verify.interruption(0, killed) is None


def test_implementer_footer_citing_a_superseded_seal_is_caught(tmp_path):
    """The gap that no gate covered: an implementer's own stale report citation.

    TEAM-FOOTER-ORIENTATION-FRESHNESS-001. `validate` compares against an
    `expected_report` that only a validated reviewer packet supplies, so a bob
    footer citing a superseded seal passed `reference_errors` AND `validate`.
    The implementer is the role that re-seals every round, so its citation is
    the likeliest to go stale and was the only one nothing checked.
    """
    import doc_contract, footer_contract
    state = tmp_path / 'devel-loop/loop_state/maintenance'
    state.mkdir(parents=True)

    def seal(created, note):
        payload = {'version': 1, 'kind': 'documentation', 'issue_id': 'X-1',
                   'created_at': created, 'references': [], 'note': note}
        sha = doc_contract.digest(payload)
        (state / f'{sha}.json').write_text(json.dumps(payload, indent=2, sort_keys=True))
        return {'path': f'devel-loop/loop_state/maintenance/{sha}.json', 'sha256': sha}

    old = seal('2026-01-01T00:00:00+00:00', 'round 1')
    new = seal('2026-01-02T00:00:00+00:00', 'round 2')

    assert doc_contract.latest_seal(tmp_path, 'X-1') == new
    assert doc_contract.latest_seal(tmp_path, 'OTHER') is None

    start = {'state_version': 2, 'timestamp': 'T0',
             'maintenance': {'baseline': {'path': 'b', 'sha256': 'b'}}}
    footer = {'issue_id': 'X-1', 'iteration_timestamp': 'T0',
              'documentation_review': {'report': old}}
    errors = footer_contract.reference_errors(tmp_path, 'bob', footer, start)
    assert any('superseded' in e for e in errors), errors

    # Citing the current seal is clean.
    footer['documentation_review']['report'] = new
    assert footer_contract.reference_errors(tmp_path, 'bob', footer, start) == []

    # A completion imported from an EARLIER iteration keeps its own seal and is
    # not refused -- the same exemption the orientation rule relies on.
    footer['documentation_review']['report'] = old
    footer['iteration_timestamp'] = 'T-EARLIER'
    assert footer_contract.reference_errors(tmp_path, 'bob', footer, start) == []


def test_report_identity_is_checked_on_a_rejecting_verdict():
    """A REJECT is the turn after which the implementer re-seals.

    TEAM-FOOTER-ORIENTATION-FRESHNESS-001, the third gap. `validate`'s deep
    block is skipped for a REJECT because a rejection does not gate closure --
    but that made a rejecting footer the likeliest place to cite a superseded
    seal and the only verdict where nothing objected. Measured on RUNOFF-030
    by a reviewer substituting the superseded report into a REJECT footer.
    """
    source = (ROOT / 'tools/esx/footer_contract.py').read_text()
    identity = source.index('stale_any = stale_citation')
    approving = source.index("if footer['verdict'] != 'REJECT':")
    assert identity < approving, 'identity must be tested before the approving-only block'


def test_stale_orientation_targets_are_named_not_swallowed(tmp_path):
    """Capture may accept a stale receipt, but the record must name what moved.

    TEAM-FOOTER-ORIENTATION-FRESHNESS-001's own acceptance allows acceptance
    *provided the changed targets are named*, because a completion imported
    from an earlier correction round legitimately keeps its orientation. Before
    this, the two gates disagreed about one artifact with no trace of which.
    """
    import doc_contract
    # A receipt that cannot be loaded at all is not a staleness report.
    assert doc_contract.stale_targets(tmp_path, {'path': 'nope', 'sha256': 'x'},
                                      'X-1', {'path': 'b', 'sha256': 'b'}, 'bob') == []
    source = (ROOT / 'tools/esx/agent_runtime.py').read_text()
    assert 'stale_orientation_targets' in source, 'the record must carry the moved targets'
    assert source.index('stale_orientation = []') < source.index('stale_orientation = moved')


def _loop_state(root, iteration=3):
    state = root / '.claude/esx-loop.local.md'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(f'---\nactive: true\niteration: {iteration}\nmax_iterations: 20\n'
                     'completion_promise: null\n---\ncontinue the loop\n')
    return state


def _verification_script(root, seconds):
    script = root / 'tools/esx/final_verification.py'
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(f'import time\ntime.sleep({seconds})\n')
    return script


def _detached(root, script):
    """Launch `script` exactly as RUNOFF-042's final verification was launched.

    A launcher Popens it with start_new_session=True and exits at once, so the
    run is reparented to PID 1 and has no ancestor in this process tree.
    """
    marker = root / 'detached.pid'
    launcher = ('import subprocess, sys\n'
                f'p = subprocess.Popen([sys.executable, {str(script)!r}], cwd={str(root)!r},\n'
                '                     start_new_session=True, stdin=subprocess.DEVNULL,\n'
                '                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n'
                f'open({str(marker)!r}, "w").write(str(p.pid))\n')
    subprocess.run([sys.executable, '-c', launcher], check=True)
    return int(marker.read_text())


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    return predicate()


def test_verification_hold_releases_and_does_not_stall(tmp_path, monkeypatch):
    """A detached verification must not let the loop stop on a promise nobody keeps.

    TEAM-LOOPHOLD-NO-RELEASE-001. The hold allowed the stop and said "the loop
    resumes when it finishes; nothing is wrong", but the harness re-invokes a
    session only for work it tracks. RUNOFF-042's suite was a detached Popen:
    it passed at 17:06:29Z and the loop then sat idle about 8 h 44 min until the
    owner asked whether Arch was in the loop. All three verification holds in the
    exit log were followed by a dead gap. The fix this replaces was validated
    twice, both times for HOLDING and never for RELEASING -- so this test checks
    the release as well.
    """
    import ralph_stop
    # The pytest process stands in for the session's `claude` process, so the
    # test does not depend on what it happens to be running under.
    monkeypatch.setattr(ralph_stop, 'session_process', lambda start=None: os.getpid())
    state = _loop_state(tmp_path)
    script = _verification_script(tmp_path, 30)

    # 1. Untracked: the loop must NOT be allowed to stop, and the wait it is told
    #    to run must name the real process.
    pid = _detached(tmp_path, script)
    try:
        assert _wait_for(lambda: ralph_stop.verification_running(tmp_path))
        assert ralph_stop.parent_pid(pid) == 1, 'the launch must reproduce the detached form'
        assert [r['pid'] for r in ralph_stop.untracked_runs(ralph_stop.verification_running(tmp_path))] == [pid]
        result = ralph_stop._step_locked(tmp_path, {})
        assert result.get('decision') == 'block', result
        assert f'tail --pid={pid}' in result['reason']
        assert 'run_in_background' in result['reason']
        assert 'nothing is wrong' not in json.dumps(result), 'the false promise is back'
        assert 'verify_waits: 1' in state.read_text()
        assert 'iteration: 3' in state.read_text(), 'a wait must not spend the iteration'
    finally:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass

    # 2. Released: once the run is gone the loop must ADVANCE and clear the
    #    counter -- the half that was never tested.
    assert _wait_for(lambda: not ralph_stop.verification_running(tmp_path))
    ralph_stop._step_locked(tmp_path, {})
    text = state.read_text()
    assert 'iteration: 4' in text, text
    assert 'verify_waits' not in text

    # 3. Tracked: a run launched under the session is notified on exit, so the
    #    quiet stop is correct and its message is true.
    child = subprocess.Popen([sys.executable, str(script)], cwd=tmp_path)
    try:
        assert _wait_for(lambda: ralph_stop.verification_running(tmp_path))
        assert ralph_stop.untracked_runs(ralph_stop.verification_running(tmp_path)) == []
        result = ralph_stop._step_locked(tmp_path, {})
        assert result.get('decision') != 'block', result
        assert 're-invoked when it finishes' in result['systemMessage']
        assert 'iteration: 4' in state.read_text()
    finally:
        child.kill(); child.wait()


def test_unidentified_session_counts_as_untracked():
    """Fail safe: a wrong 'tracked' costs hours, a needless wait a status line."""
    import ralph_stop
    run = [{'script': 'tools/esx/final_verification.py', 'minutes': 0, 'pid': os.getpid()}]
    assert ralph_stop.untracked_runs(run, session=0) == run
    assert ralph_stop.untracked_runs(run, session=os.getpid()) == []


def test_issueless_consultation_turn_is_not_reflagged_forever(tmp_path):
    """A footer-less turn belonging to no iteration clears once its agent reports again.

    TEAM-GATE-CONSULTATION-NOTICE-PERMANENT-001. Such a record carries no issue,
    so the filter admitted it to EVERY iteration, while its agent's superseding
    completions named their own issue and were filtered out. A closed RUNOFF-030
    reviewer's consultation turn (its report ends "no footer, per your
    instruction") was therefore re-flagged on RUNOFF-040, RUNOFF-016 and
    RUNOFF-042, with a remedy that would have attached it to an unrelated issue.
    """
    consultation = {'agent_type': 'richard', 'agent_id': 'old', 'status': 'incomplete',
                    'issue_id': None, 'iteration_timestamp': None, 'correction_round': 0,
                    'error': 'missing, malformed, or mismatched structured footer'}
    closed = lambda rnd: {'agent_type': 'richard', 'agent_id': 'old', 'status': 'completed',
                          'issue_id': 'CLOSED-1', 'correction_round': rnd,
                          'footer': {'issue_id': 'CLOSED-1', 'correction_round': rnd}}
    gate = _gate_with_log(tmp_path, [closed(1), consultation, closed(2)])
    assert gate.defective_completions(START) == []


def test_issueless_turn_whose_agent_never_reported_is_still_flagged(tmp_path):
    """The alarm and the suppression are one predicate; a fix that silences one silences both."""
    lost = {'agent_type': 'richard', 'agent_id': 'gone', 'status': 'incomplete',
            'issue_id': None, 'iteration_timestamp': None, 'correction_round': 0,
            'error': 'missing, malformed, or mismatched structured footer'}
    earlier = {'agent_type': 'richard', 'agent_id': 'gone', 'status': 'completed',
               'issue_id': 'CLOSED-1', 'correction_round': 1,
               'footer': {'issue_id': 'CLOSED-1', 'correction_round': 1}}
    # A completion BEFORE the lost turn proves nothing about the lost turn.
    gate = _gate_with_log(tmp_path, [earlier, lost])
    assert gate.defective_completions(START) == [
        ('richard', 'gone', 0, 'missing, malformed, or mismatched structured footer')]


def test_prepare_refuses_a_kind_its_owning_target_contradicts():
    """The kind is checked when it is chosen, not at closeout.

    TEAM-PREPARE-KIND-UNCHECKED-001. RUNOFF-042 was prepared as harness_change
    with every target under tests/, which is in the scientific inventory, and
    the gate said so only at --check-done, after two rounds and four reviews.
    """
    import loop_gate
    from project import config
    cfg = config(ROOT)
    sweep = ['tests/footprint_claim_sweep.py::tracked', 'tests/footprint_claim_sweep.py::sweep']
    assert loop_gate.kind_contradiction(ROOT, cfg, 'harness_change', sweep), 'the RUNOFF-042 shape'
    assert loop_gate.kind_contradiction(ROOT, cfg, 'scientific_change', sweep) is None
    # No false refusals: a document owner may orient on a test as its consumer,
    # and framework work lives outside the scientific inventory.
    assert loop_gate.kind_contradiction(
        ROOT, cfg, 'documentation', ['docs/code_map.md::<module>', 'tests/rnf/refusal_check.py::cases']) is None
    assert loop_gate.kind_contradiction(
        ROOT, cfg, 'harness_change',
        ['tools/esx/ralph_stop.py::_step_locked', 'tests/esx/test_framework_fixes.py::<module>']) is None


def test_design_citation_that_resolves_nowhere_is_refused():
    """A citation in the coordinator's design must point at something.

    The mechanical edge of TEAM-ARCH-UNVERIFIED-CLAIM-001, which says plainly
    that it would have caught none of that issue's twelve instances; it is the
    one shape of an unchecked claim a program can see. Measured before it was
    made a refusal: 43 citations across all 16 existing designs, 0 refused.
    """
    import brief
    real = sum(1 for _ in (ROOT / 'tests/rnf/refusal_check.py').open('rb'))
    assert brief.citation_errors(ROOT, f'see `tests/rnf/refusal_check.py:{real}`') == []
    assert brief.citation_errors(ROOT, f'see tests/rnf/refusal_check.py:{real + 1}') == [
        f'tests/rnf/refusal_check.py:{real + 1}: the file has {real} lines']
    assert brief.citation_errors(ROOT, 'see tests/rnf/refusal_check.py:10-999999')
    assert brief.citation_errors(ROOT, 'see tests/no_such/file.py:3') == ['tests/no_such/file.py:3: no such file']
    # Model citations are written relative to MITgcm/, and a bare filename is
    # ambiguous between trees, so neither may be refused.
    assert brief.citation_errors(ROOT, 'pkg/rnf/RNF.h:1 and update_surf_dr.F:999999') == []
    # And it is wired into build(), not merely defined.
    import inspect
    assert 'citation_errors(root, design)' in inspect.getsource(brief.build)
