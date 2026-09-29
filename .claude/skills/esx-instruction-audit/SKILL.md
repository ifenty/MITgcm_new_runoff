---
name: esx-instruction-audit
description: Use when role, contract, configuration or workflow enforcement changes.
---

# esx-instruction-audit

Find the authoritative instruction and its enforcing function before editing.
Run `python3 tools/esx/audit.py`. It checks configuration readiness, six role files,
hook routing, Markdown links, mapped Python symbols and issue/lesson consistency.
It cannot prove scientific adequacy, arbitrary prose consistency, runtime provider
availability or user authorization. Check those through the applicable evidence.

Keep one owner for each rule and explicit links from roles/procedures. Test both
accepted and deliberately invalid cases when changing a gate. Preserve existing
project decisions. Report exact mismatches and checks performed; do not create an
issue loop or multiply reviewers solely to complete this audit.
