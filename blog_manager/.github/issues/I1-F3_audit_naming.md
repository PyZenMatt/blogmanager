Title: I1-F3 — Audit naming: normalize actions/status values

Description:

Ensure audit records use canonical action and status naming from the playbook: actions in `publish|refresh|delete_db_only|delete_repo_and_db` and statuses in `success|no_changes|warning|error`.

Tasks:

- Search for ExportJob and any audit records and ensure values match the canonical list.
- Update `blog/services/github_ops.py` to store `action='delete_repo_and_db'` and `export_status` mapping to `success|failed` or translate to the canonical statuses in an envelope.
- Add tests to assert naming consistency for delete flow.

DoD:

- Audit records for delete flow use canonical action `delete_repo_and_db` and a mapped status compatible with the playbook.
