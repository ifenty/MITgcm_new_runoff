---
name: esx-code-map
description: Use before changing or explaining a source mechanism or its documentation.
---

# esx-code-map

Read docs/code_map.md and the relevant project contract. Obtain live Python
locations with `python3 tools/esx/orient.py --outline path/to/file.py`; inspect
one definition using `--ref path/to/file.py::qualified.symbol`. For other languages,
use a language-aware index or bounded source search and reference the file as
`path::<module>`. A Python AST is a structural representation of source. Confirm runtime call
relationships by inspecting imports, dispatch and consumers.

Read devel-loop/documentation_contract.md. Save an orientation receipt tied to
the issue baseline using tools/esx/doc_contract.py navigate. Choose the actual
owner, a related consumer/test, applicable docs, and explain how they guide the
work. Refresh when selected inputs change. Update comments, docstrings, contracts
and map together. Seal and review every generated affected-target disposition.
