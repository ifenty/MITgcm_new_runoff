"""Process validation for TEAM-DOC-DISPOSITION-DRIFT-001 on the deployed kit (ESX-Team 1.6.0).

Checks the rule that decides which documentation judgments carry forward between
rounds: only `updated`/`removed` judgments on code or test files are bound to
their own file; `reviewed_unchanged` and document/config targets keep the
whole-inventory binding.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools' / 'esx'))
import doc_contract as dc  # noqa: E402

code = {'target': 'src/a.py::f', 'action': 'updated'}
assert dc.file_bound(code)
assert dc.file_bound({'target': 'tests/t.py::test_x', 'action': 'removed'})
assert not dc.file_bound({'target': 'src/a.py::f', 'action': 'reviewed_unchanged'})
assert not dc.file_bound({'target': 'docs/model.md::<module>', 'action': 'updated'})
assert not dc.file_bound({'target': 'esx/project.json::<module>', 'action': 'updated'})

sealed = {'target': 't1', 'references': ['r1'], 'dependency_contexts': [], 'dependency_inventory': 'inv-old',
          'file_sha256': 'f1'}
other_file_changed = dict(sealed, dependency_inventory='inv-new')
assert dc.same_judgment(sealed, other_file_changed, code), 'code judgment must carry forward when another file changes'
assert not dc.same_judgment(sealed, dict(other_file_changed, file_sha256='f2'), code), 'own-file edit must blank it'
doc = {'target': 'docs/model.md::<module>', 'action': 'updated'}
assert not dc.same_judgment(sealed, other_file_changed, doc), 'document judgment must not carry forward'
unchanged = {'target': 'src/a.py::f', 'action': 'reviewed_unchanged'}
assert not dc.same_judgment(sealed, other_file_changed, unchanged), 'reviewed_unchanged must not carry forward'
legacy = {k: v for k, v in sealed.items() if k != 'file_sha256'}
assert not dc.same_judgment(legacy, other_file_changed, code), 'a legacy report keeps the whole-inventory rule'
print('plan-reuse rule validated: 10 assertions passed')
