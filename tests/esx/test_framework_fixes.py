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
import signal
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
# TEAM-PAUSE-EARLY-LIFT-001 / TEAM-PAUSE-DEADLINE-CLAMP-001 (the latter reverted)
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


def test_a_live_scope_deadline_and_an_owner_extension_still_bound_the_turn():
    """Owner-authorized wall-clock limits bound a turn; a pause does not extend them.

    TEAM-PAUSE-DEADLINE-CLAMP-001's local fix (af5165f) let a scope deadline bind
    a turn only while it left half the turn's horizon. That was broader than the
    pause it targeted: ESX-Team's own suite measured a live 10-minute deadline no
    longer bounding a long turn, and -- worse -- an OWNER-AUTHORIZED 20-minute
    extension bounding the resumed turn at 6000 s instead of 4200 s, i.e. past
    what the owner authorized. esx-fix.md D: "Waiting does not extend
    owner-authorized money or wall-clock limits." Reverted to upstream; a turn
    resumed near its deadline is what budget.extend is for.
    """
    import team_budget
    import time as clock
    from pathlib import Path
    import tempfile
    assert not hasattr(team_budget, 'USABLE_TURN_FRACTION'), 'the horizon rule is back'
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        cap = team_budget.limits(override={'minutes': 10})
        reservation = team_budget.reserve(root, 'one', 'TEST', cap, turn_seconds=99_999)
        assert reservation['deadline'] < clock.time() + 10 * 60 + 1


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


ATTEMPT = r"""
import json, os, sys
sys.path.insert(0, %(tools)r)
import verify
from pathlib import Path
real_config, real_fingerprint = verify.config, verify.fingerprint
timeout = %(timeout)r
if timeout is not None:
    verify.config = lambda root: dict(real_config(root), command_timeout_seconds=timeout)
if %(drift)r:
    calls = []
    def drifting(*a):
        calls.append(1)
        return real_fingerprint(*a) if len(calls) == 1 else 'moved'
    verify.fingerprint = drifting
try:
    result = verify._run(Path(%(root)r), 'focused', 'esx-test', True, %(argv)r)
    print(json.dumps({'type': 'PASS', 'evidence': result['evidence']}))
except BaseException as exc:
    print(json.dumps({'type': type(exc).__name__, 'message': str(exc), 'log': getattr(exc, 'log', None)}))
"""


def _attempt(argv, *, timeout=None, drift=False, signal_runner=None):
    """Run one real verification attempt in a child runner and return (result, record).

    Drives `verify._run` itself -- the runner, its signal handler, its process
    group handling and its record -- rather than a text-matching helper, which is
    what esx-fix.md B.5 asks for. `signal_runner` sends that signal to the
    runner's whole process group once the command is running, the RUNOFF-040
    shape.
    """
    script = ATTEMPT % {'tools': str(TOOLS), 'root': str(ROOT), 'argv': argv,
                        'timeout': timeout, 'drift': drift}
    runner = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, text=True,
                              start_new_session=True)
    if signal_runner:
        time.sleep(3.0)
        os.killpg(runner.pid, signal_runner)
    out, _ = runner.communicate(timeout=300)
    result = json.loads(out.strip().splitlines()[-1])
    log = result.get('log') or (result.get('evidence') and json.loads(
        (ROOT / result['evidence']['path']).read_text())['log'])
    record = next((json.loads(f.read_text()) for f in (ROOT / 'devel-loop/loop_state/verification').glob('*.json')
                   if not f.name.startswith(('cache-', 'lock-'))
                   and json.loads(f.read_text()).get('log') == log), None)
    return result, record


SLEEP = "import time; time.sleep(30)"


def test_verification_outcome_is_decided_by_the_runner_not_the_log():
    """Each outcome is classified from the runner's own state, before sealing.

    TEAM-VERIFY-SIGNAL-MISCLASSIFIED-001, corrected per esx-fix.md work package
    B. The first fix searched the WHOLE log -- the commands' own output included
    -- for `verification received signal N`, and after the arm reordering that
    search could only ever match command output. Demonstrated on 2026-10-09: a
    real failed assertion whose pytest output echoed this file's own literal of
    that string was reported as an interruption with no verdict. A launch
    failure shared the timeout arm, and a child that crashed with SIGSEGV was
    called an interruption.
    """
    import verify
    py = sys.executable
    marker = 'verification received signal 15'

    # Normal success: a complete, reusable PASS.
    result, record = _attempt([py, '-c', 'pass'])
    assert result['type'] == 'PASS'
    assert (record['outcome'], record['completed_commands'], record['planned_commands']) == ('pass', 1, 1)
    verify.load_evidence(ROOT, result['evidence'])

    # THE demonstrated defect: a real failure that prints the marker stays a failure.
    result, record = _attempt([py, '-c', f'print({marker!r}); raise SystemExit(1)'])
    assert result['type'] == 'ValueError' and 'verification failed' in result['message'], result
    assert record['outcome'] == 'failed' and record['termination'] is None
    # ...and a passing command that prints it is still a pass.
    assert _attempt([py, '-c', f'print({marker!r})'])[0]['type'] == 'PASS'

    # A command returning 124 has failed; 124 is not read as our timeout.
    result, record = _attempt([py, '-c', 'raise SystemExit(124)'])
    assert result['type'] == 'ValueError' and record['outcome'] == 'failed'

    # A real per-command timeout says which command timed out.
    result, record = _attempt([py, '-c', SLEEP], timeout=1)
    assert result['type'] == 'RunTimedOut' and record['outcome'] == 'timeout'
    assert 'command 1' in record['reason'] and 'timed out after 1 s' in record['reason']

    # A launch failure is infrastructure, with no verdict on the candidate.
    result, record = _attempt(['/nonexistent/esx-no-such-executable'])
    assert result['type'] == 'RunInfrastructure' and record['outcome'] == 'infrastructure'

    # A crash is a failure of the candidate, not an interruption...
    result, record = _attempt([py, '-c', 'import os, signal; os.kill(os.getpid(), signal.SIGSEGV)'])
    assert result['type'] == 'ValueError' and record['outcome'] == 'failed' and 'crashed' in record['reason']
    # ...a termination signal is an interruption, established by the return code
    # itself (ESX-Team's own suite SIGTERMs the suite's child and requires it)...
    result, record = _attempt([py, '-c', 'import os, signal; os.kill(os.getpid(), signal.SIGKILL)'])
    assert result['type'] == 'RunInterrupted' and (record['outcome'], record['termination']) == ('interrupted', 9)
    assert record['completed_commands'] == 0, 'a command ended by a signal did not complete'
    # ...and any other signal has no established cause: infrastructure, no verdict.
    result, record = _attempt([py, '-c', 'import os, signal; os.kill(os.getpid(), signal.SIGUSR1)'])
    assert result['type'] == 'RunInfrastructure' and record['termination'] == signal.SIGUSR1

    # Process-group SIGTERM to the runner, the RUNOFF-040 shape: interrupted,
    # with the signal recorded from the handler rather than parsed from text.
    result, record = _attempt([py, '-c', SLEEP], signal_runner=signal.SIGTERM)
    assert result['type'] == 'RunInterrupted', result
    assert (record['outcome'], record['termination'], record['completed_commands']) == ('interrupted', 15, 0)

    # Source drift during the run prevents acceptance.
    result, record = _attempt([py, '-c', 'pass'], drift=True)
    assert result['type'] == 'SourceChanged' and record['outcome'] == 'source_changed'


def test_failed_fresh_attempt_cannot_expose_an_earlier_pass(tmp_path):
    """esx-fix.md B.7: already implemented in verify._run, so it gets coverage, not a rewrite."""
    flag = tmp_path / 'exit'
    argv = [sys.executable, '-c', f'raise SystemExit(int(open({str(flag)!r}).read()))']
    import verify
    from project import digest
    index = ROOT / f"devel-loop/loop_state/verification/cache-{digest(['focused', [argv]])}.json"
    flag.write_text('0')
    assert _attempt(argv)[0]['type'] == 'PASS' and index.exists()
    flag.write_text('1')
    assert _attempt(argv)[0]['type'] == 'ValueError'
    assert not index.exists(), 'a failed fresh attempt left the earlier PASS reachable'


def test_evidence_consumers_require_a_complete_pass(tmp_path):
    """`stable` means only that the fingerprint did not move (esx-fix.md B.6)."""
    import verify
    result, record = _attempt([sys.executable, '-c', 'pass'])
    forged = dict(record, outcome='interrupted')
    from project import digest, atomic_json
    sha = digest(forged)
    path = f'devel-loop/loop_state/verification/{sha}.json'
    atomic_json(ROOT / path, forged)
    try:
        with pytest.raises(ValueError, match='outcome is interrupted'):
            verify.load_evidence(ROOT, {'path': path, 'sha256': sha})
    finally:
        (ROOT / path).unlink()


def test_zero_failure_lines_is_not_reported_as_no_failure():
    """esx-fix.md B.8: missing failure tokens establish only that none was observed."""
    source = (TOOLS / 'final_verification.py').read_text()
    assert "'no test failed before the interruption' if" not in source
    assert 'does not establish that' in source


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
    and the gate said so only at --check-done, after two rounds and four reviews.
    Since esx-fix.md F1 the boundary it enforces is the right one: a scientific
    owner still requires scientific_change, and an ESX-test-only issue no longer
    does -- the coupling this check briefly hardened.
    """
    import loop_gate
    from project import config
    cfg = config(ROOT)
    oracle = ['tests/rnf/refusal_check.py::cases', 'tests/rnf/refusal_check.py::main']
    assert loop_gate.kind_contradiction(ROOT, cfg, 'harness_change', oracle), 'a scientific oracle owner'
    assert loop_gate.kind_contradiction(
        ROOT, cfg, 'harness_change', ['MITgcm/pkg/rnf/rnf_summary.F::<module>', 'tests/rnf/refusal_check.py::cases'])
    assert loop_gate.kind_contradiction(ROOT, cfg, 'scientific_change', oracle) is None
    # No false refusals: ESX tests and framework code are outside the scientific
    # identity, and a document owner may orient on a test as its consumer.
    assert loop_gate.kind_contradiction(
        ROOT, cfg, 'harness_change',
        ['tests/esx/test_framework_fixes.py::<module>', 'tools/esx/ralph_stop.py::_step_locked']) is None
    assert loop_gate.kind_contradiction(
        ROOT, cfg, 'harness_change', ['tests/footprint_claim_sweep.py::tracked', 'docs/code_map.md::<module>']) is None
    assert loop_gate.kind_contradiction(
        ROOT, cfg, 'documentation', ['docs/code_map.md::<module>', 'tests/rnf/refusal_check.py::cases']) is None
    # It INFORMS and never refuses: whether the work will edit its owner is
    # unknown at --prepare, and as a refusal it rejected 44 of ESX-Team's own
    # regression fixtures, each an `investigation` over a source it only reads.
    import inspect
    src = inspect.getsource(loop_gate.Gate.prepare)
    assert 'kind_contradiction' in src and 'notices.append' in src
    assert 'require(contradiction' not in src


def test_framework_tests_leave_the_scientific_identity_only():
    """esx-fix.md F1: framework tests are structural, never scientific witnesses.

    The project's tests tree was wholly in scientific scope, ESX regression tests
    included, so editing one changed the numerical execution identity and forced
    a full scientific qualification -- RUNOFF-042 paid 6467 s for exactly that.
    The acceptance side must not move: framework tests are still reviewed and
    still run in `structural`.
    """
    import project
    cfg = project.config(ROOT)
    sci = set(project.inventory_paths(ROOT, cfg, True))
    every = set(project.inventory_paths(ROOT, cfg, False))
    for path in ('tests/esx/test_framework_fixes.py', 'tests/footprint_claim_sweep.py'):
        assert path not in sci and path in every, path
    for path in ('tests/rnf/refusal_check.py', 'tests/mitgcm_oracle.sh', 'tests/runoff/test_convert.py'):
        assert path in sci and path in every, path

    # Legacy configuration stays conservative until explicitly migrated.
    legacy = {k: v for k, v in cfg.items() if k != 'framework_test_paths'}
    assert project.selected('tests/esx/test_framework_fixes.py', legacy, scientific=True)
    assert not project.selected('tests/esx/test_framework_fixes.py', cfg, scientific=True)
    assert project.selected('tests/esx/test_framework_fixes.py', cfg, scientific=False)


def test_a_scientific_witness_cannot_be_declared_a_framework_test(tmp_path):
    """A test executed by a scientific-inventory suite must not be moved out of it."""
    import project
    shutil.copytree(ROOT / 'esx', tmp_path / 'esx')
    (tmp_path / 'tests/rnf').mkdir(parents=True)
    (tmp_path / 'tests/rnf/budget_check.py').write_text('')
    cfg = json.loads((ROOT / 'esx/project.json').read_text())
    cfg.update(source_paths=[], configuration_paths=[], mirrored_paths=[], archive_paths=[],
               test_paths=['tests'], framework_test_paths=['tests/rnf/budget_check.py'])
    (tmp_path / 'esx/project.json').write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='executed by the focused suite'):
        project.config(tmp_path, ready=False)
    cfg['framework_test_paths'] = ['docs']
    (tmp_path / 'esx/project.json').write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match='inside a configured test_paths root'):
        project.config(tmp_path, ready=False)


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
    # Reported to Arch as a warning, never a refusal (esx-fix.md E): unknown
    # free-text claims need review rather than a machine refusal that could be
    # false. It is wired into main(), not build().
    import inspect
    assert 'citation_errors' not in inspect.getsource(brief.build)
    assert 'citation_errors' in inspect.getsource(brief.main)


def test_brief_checks_instructions_not_the_quoted_packet():
    """Quoted history is not an order; an order naming a bad flag still is refused.

    esx-fix.md E: validate the executable instructions separately from quoted
    prior packets, rather than keep extending a prose regex. The embedded packet
    carries earlier footers whose commands are history; checking them produced
    the false refusals that the quote terminator in COMMAND_PATTERN was added to
    suppress (TEAM-BRIEF-COMMAND-SPAN-QUOTES-001).
    """
    import brief
    start_path = ROOT / 'devel-loop/loop_state/issue-start.json'
    if not start_path.exists():
        pytest.skip('needs an issue-start record to build a brief against')
    start = json.loads(start_path.read_text())
    bad = 'tools/esx/verify.py --suite focused --mpi 2'
    packet = dict(start, subagents={'bob': [{'agent': 'bob', 'evidence': ['ran ' + bad + ' earlier']}]})
    text = brief.build(ROOT, 'bob', start['id'], 'Implement the bounded change.', packet=packet)
    assert bad in text, 'the packet must still be embedded verbatim for the agent to read'
    with pytest.raises(ValueError, match='does not accept --mpi'):
        brief.build(ROOT, 'bob', start['id'], 'Run ' + bad + ' afterwards.', packet=packet)


def test_closeout_metadata_problems_are_reported_in_one_pass():
    """esx-fix.md E: every metadata shape problem at once, each stating the shape required.

    RUNOFF-042's closeout learned these one refusal at a time: unsupported
    fields, then a tests_status enum the message never named, then -- at
    --check-done -- lessons as a list of ids, git.committed as a boolean, and
    milestone.logged.
    """
    import loop_lifecycle
    first = {'communication': {'status': 'unauthorized', 'detail': 'x'}, 'git': {'sha': 'caa6c92'},
             'scientific_outcome': 'x' * 50}
    problems = loop_lifecycle.metadata_problems(first)
    assert len(problems) == 4, problems
    assert any("['passing', 'failing', 'not_run']" in p for p in problems), 'the enum must be named'
    later = {'summary': 's' * 60, 'tests_status': 'passing', 'lessons': 'prose, not ids',
             'milestone': 'one line', 'git': {'sha': 'caa6c92'}, 'communication': {}}
    problems = loop_lifecycle.metadata_problems(later)
    assert {p.split()[0] for p in problems} == {'lessons', 'git', 'milestone'}, problems
    valid = dict(later, lessons=['LL-019'], milestone={'logged': False}, git={'committed': True, 'sha': 'caa6c92'})
    assert loop_lifecycle.metadata_problems(valid) == []


def test_check_done_refusal_shows_every_unmet_requirement(monkeypatch, capsys):
    """The closeout doctor already found everything at once; nothing pointed to it."""
    import loop_gate
    import closeout_doctor
    monkeypatch.setattr(loop_gate.Gate, 'check_done', lambda self: (_ for _ in ()).throw(ValueError('first one')))
    findings = [{'code': c, 'field': f, 'recovery': r, 'status': 'blocked'} for c, f, r in
                (('GIT_DISPOSITION', 'git', 'record git.committed'), ('LESSON_UNKNOWN', 'lessons', 'use LL ids'),
                 ('MILESTONE_INVALID', 'milestone', 'record milestone.logged'))]
    monkeypatch.setattr(closeout_doctor, 'diagnose', lambda gate, done=None: {'findings': findings})
    monkeypatch.setattr(sys, 'argv', ['loop_gate.py', '--root', str(ROOT), '--check-done'])
    assert loop_gate.main() == 1
    err = capsys.readouterr().err
    assert 'BLOCKED: first one' in err and 'all 3 unmet closeout requirement(s)' in err
    for code in ('GIT_DISPOSITION', 'LESSON_UNKNOWN', 'MILESTONE_INVALID'):
        assert code in err
    # A doctor failure must never mask the original refusal.
    monkeypatch.setattr(closeout_doctor, 'diagnose', lambda gate, done=None: 1 / 0)
    assert loop_gate.main() == 1
    err = capsys.readouterr().err
    assert 'BLOCKED: first one' in err and 'closeout doctor unavailable' in err


def test_loop_cannot_complete_over_an_unattempted_notification():
    """Work comes before notifications, but completion does not.

    TEAM-NOTIFY-OUTAGE-NO-BACKOFF-001 (af5165f) rightly stopped a notification
    demand from hiding the work -- but it deferred the notice past the
    no-actionable-work branch too, so the loop could emit its completion promise
    with a required notification never attempted. Found only by running ESX-Team's
    own suite against this project's tools:
    test_autonomous_loop::test_required_pending_prevents_completion_until_attempt
    (rc 3 where 0 was required). esx-fix.md D keeps the delivery-attempt policy.
    A structural backstop, because this project does not run that suite.
    """
    import inspect
    import loop_gate
    src = inspect.getsource(loop_gate.Gate._next_instruction)
    tail = src[src.index("terminal='no actionable work'"):]
    gate, promise = tail.index('if self._deferred_notice:'), tail.index('print(PROMISE)')
    assert gate < promise, 'the completion promise is reachable before the pending notice is honoured'
    assert 'return 0' in tail[gate:promise]


def _process_fixture(root, *, blocking=None, closeouts=3):
    """A disposable root with one process finding recurring across `closeouts` retrospectives."""
    state = root / 'devel-loop/loop_state'
    ledger = root / 'devel-loop/self-improvement/open-ESX-team-issues.md'
    state.mkdir(parents=True)
    ledger.parent.mkdir(parents=True)
    fields = ('**Date Identified**: 2026-10-09  01:00\n**Status**: Proposed\n**UUID**: TEAM-FIXTURE-001\n'
              '**Category**: fixture\n**Severity**: High\n')
    if blocking:
        fields += f'**Blocking**: {blocking}\n'
    ledger.write_text('# Open\n\n## \U0001F534 PROPOSED: fixture\n\n' + fields + '\n### Issue\nx\n')
    history, retros = [], []
    for n in range(closeouts):
        stamp = f'2026-10-0{n + 1}T00:00:00+00:00'
        history.append({'id': f'RUNOFF-90{n}', 'timestamp': stamp})
        retros.append({'id': f'RUNOFF-90{n}', 'closes_timestamp': stamp,
                       'problems': [{'category': 'fixture', 'summary': 's' * 20, 'evidence': 'e' * 20,
                                     'minutes_lost': 1}],
                       'solutions': [{'problem': 0, 'action': 'filed', 'issue': 'TEAM-FIXTURE-001'}]})
    for name, rows in (('loop_history.jsonl', history), ('retrospective_history.jsonl', retros)):
        (state / name).write_text(''.join(json.dumps(r) + '\n' for r in rows))
    return state


def _close_one_more(state, n):
    stamp = f'2026-10-1{n}T00:00:00+00:00'
    with (state / 'loop_history.jsonl').open('a') as handle:
        handle.write(json.dumps({'id': f'RUNOFF-95{n}', 'timestamp': stamp}) + '\n')


def test_a_recurring_advisory_finding_blocks_no_work(tmp_path):
    """esx-fix.md C: recurrence surfaces a recommendation, never a project-wide stop.

    On 2026-10-09 TEAM-ARCH-UNVERIFIED-CLAIM-001 recurred and every scientific
    issue was refused until a process fix was implemented, because recurrence
    alone made a finding `required_before_next_start`.
    """
    import team_retrospective as retro
    _process_fixture(tmp_path)
    assert retro.classify(tmp_path)['TEAM-FIXTURE-001']['classification'] == 'advisory'
    assert retro.followup_due(tmp_path) == [] and retro.followup_due(tmp_path, 'RUNOFF-008', 'scientific_change') == []
    retro.require_followup(tmp_path, 'RUNOFF-008', 'scientific_change')      # preparable and dispatchable
    assert retro.advisories(tmp_path) == ['TEAM-FIXTURE-001'], 'it is still surfaced'


def test_a_blocking_finding_stops_only_the_work_it_names(tmp_path):
    """A blocker names its scope, evidence and clearing condition, and stops only that scope."""
    import team_retrospective as retro
    import self_improvement as si
    assert si.blocking_error('all; evidence that is long enough; clears when x') is not None, 'condition too short'
    assert si.blocking_error('everything; e; clears when the receipt is fixed') is not None, 'scope'
    _process_fixture(tmp_path, blocking='issue:RUNOFF-008; the receipt for this issue is corrupt; '
                                        'clears when the receipt is re-issued from a clean run')
    assert retro.followup_due(tmp_path, 'RUNOFF-008', 'scientific_change') == ['TEAM-FIXTURE-001']
    with pytest.raises(ValueError, match='blocks issue:RUNOFF-008'):
        retro.require_followup(tmp_path, 'RUNOFF-008', 'scientific_change')
    retro.require_followup(tmp_path, 'RUNOFF-014', 'scientific_change')      # unrelated work proceeds
    assert retro.followup_due(tmp_path) == [], 'a scoped blocker does not stop selection itself'
    assert retro.scoped_blockers(tmp_path) == [('TEAM-FIXTURE-001', 'issue:RUNOFF-008')]


def test_a_deferral_persists_until_its_trigger_and_reopens_on_new_evidence(tmp_path):
    """Unchanged recurrence needs no renewed justification; its trigger brings it back once."""
    import team_retrospective as retro
    state = _process_fixture(tmp_path, blocking='all; the evidence index is corrupt for every suite; '
                                                'clears when the index is rebuilt and verified')
    assert retro.followup_due(tmp_path) == ['TEAM-FIXTURE-001']
    with pytest.raises(ValueError, match='needs --trigger'):
        retro.decide_followup(tmp_path, 'TEAM-FIXTURE-001', 'deferred', 'r' * 50)
    retro.decide_followup(tmp_path, 'TEAM-FIXTURE-001', 'deferred', 'deferred until four more closeouts ' * 2,
                          trigger='closeouts:4')
    for n in range(3):                       # three unrelated closeouts: still deferred, no renewal
        _close_one_more(state, n)
        assert retro.followup_due(tmp_path) == [], n
    _close_one_more(state, 3)                # the fourth fires the trigger: one reconsideration
    assert retro.followup_due(tmp_path) == ['TEAM-FIXTURE-001']

    # A milestone trigger fires when current_status.md gains the heading.
    retro.decide_followup(tmp_path, 'TEAM-FIXTURE-001', 'deferred', 'deferred until the tracer milestone ' * 2,
                          trigger='milestone:two-tracer closure')
    assert retro.followup_due(tmp_path) == []
    (tmp_path / 'current_status.md').write_text('# Milestones\n\n## 2026-11-01 — two-tracer closure (RUNOFF-008)\n')
    assert retro.followup_due(tmp_path) == ['TEAM-FIXTURE-001']


def test_a_deferral_is_void_when_its_classification_changes(tmp_path):
    """New evidence reopens triage promptly; a deferral is no indefinite waiver."""
    import team_retrospective as retro
    _process_fixture(tmp_path)
    retro.decide_followup(tmp_path, 'TEAM-FIXTURE-001', 'deferred', 'advisory, deferred to the next milestone ' * 2,
                          trigger='closeouts:10')
    assert retro.advisories(tmp_path) == []
    ledger = tmp_path / 'devel-loop/self-improvement/open-ESX-team-issues.md'
    ledger.write_text(ledger.read_text().replace(
        '**Severity**: High\n', '**Severity**: High\n**Blocking**: all; a receipt was found forged in the index; '
                                'clears when the index is rebuilt and verified\n'))
    assert retro.followup_due(tmp_path) == ['TEAM-FIXTURE-001'], 'the advisory deferral must not cover a blocker'


def test_pending_commentary_is_listed_and_merged_not_blocking(tmp_path):
    """Lightweight reflection: measurements now, commentary later, nothing invented to pass."""
    import team_retrospective as retro
    state = _process_fixture(tmp_path, closeouts=2)
    rows = [json.loads(l) for l in (state / 'retrospective_history.jsonl').read_text().splitlines()]
    rows.append({'id': 'RUNOFF-902', 'closes_timestamp': '2026-10-03T00:00:00+00:00', 'commentary': 'pending',
                 'problems': [], 'solutions': []})
    (state / 'retrospective_history.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert retro.pending_commentary(tmp_path) == ['RUNOFF-902']
    with (state / retro.COMMENTARY).open('w') as handle:
        handle.write(json.dumps({'id': 'RUNOFF-902', 'closes_timestamp': '2026-10-03T00:00:00+00:00',
                                 'problems': rows[0]['problems'], 'solutions': rows[0]['solutions']}) + '\n')
    assert retro.pending_commentary(tmp_path) == []
    merged = retro.reflections(tmp_path)
    assert len(merged) == 3 and merged[-1]['problems'] == rows[0]['problems'], 'completion merged, not appended'
    assert 'TEAM-FIXTURE-001' in retro.classify(tmp_path)


def test_self_assessment_is_advisory_and_demands_nothing_invented(tmp_path):
    """esx-fix.md C: no inherited "before continuing" obligation, no invented entry."""
    import loop_gate
    lessons = tmp_path / 'lessons_learned.md'
    lessons.write_text('# Lessons\n')
    os.utime(lessons, (0, 0))
    state = tmp_path / 'devel-loop/loop_state'
    state.mkdir(parents=True)
    (state / 'loop_history.jsonl').write_text(''.join(
        json.dumps({'id': f'X-{n}', 'timestamp': f'2026-10-0{n % 9 + 1}T00:00:00+00:00'}) + '\n' for n in range(12)))
    gate = loop_gate.Gate.__new__(loop_gate.Gate)
    gate.root = tmp_path
    text = gate.self_assessment_notice()
    assert text and 'advisory, does not block' in text
    assert 'before continuing' not in text and 'nothing new this window' not in text
    assert 'nothing is required' in text


def test_a_consultation_turn_is_an_explicit_non_approval(tmp_path, monkeypatch):
    """esx-fix.md E: a consultation gets its own disposition, never review, never a defect."""
    import agent_runtime
    import footer_contract
    import workflow_policy
    import loop_gate
    footer = footer_contract.consultation('richard', 'X-1', START['timestamp'], 0)
    assert footer == {'agent': 'richard', 'issue_id': 'X-1', 'iteration_timestamp': START['timestamp'],
                      'correction_round': 0, 'consultation': True}
    monkeypatch.setattr(agent_runtime, 'transcript_report', lambda path: None)
    (tmp_path / 'devel-loop/loop_state').mkdir(parents=True)
    event = {'agent_type': 'richard', 'agent_id': 'r1', 'stop_reason': 'end_turn', 'session_id': 's',
             'last_assistant_message': 'Prose answer.\n```json\n' + json.dumps(footer) + '\n```'}
    agent_runtime.stop_record(tmp_path, event)
    record = json.loads((tmp_path / 'devel-loop/loop_state/dispatch_log.jsonl').read_text().splitlines()[-1])
    assert (record['status'], record['error']) == ('consultation', None)
    assert not workflow_policy.completed(record), 'a consultation must never count as review'
    gate = loop_gate.Gate.__new__(loop_gate.Gate)
    gate.root = tmp_path
    assert gate.defective_completions(START) == [], 'nor raise an uncaptured-completion notice'
