Title: Issue 5 — Admin Action: Delete (DB-only | DB+Repo)

Description:

Implement an Admin action to delete posts with confirmation radio: `DB only` or `DB+Repo`.

Tasks:

- Add ModelAdmin action with confirmation form (radio choice).
- If `DB+Repo` and `ALLOW_REPO_DELETE=true`, call `delete_post_from_repo` to remove file and record ExportJob/audit.
- On `deleted` or `already_absent`, proceed to delete/soft-delete the DB record.
- Ensure DRY_RUN support and clear admin messages on outcome.

DoD:

- Admin action available and tested in staging with `ALLOW_REPO_DELETE=false` and `true` variants.
- Audit records for repo deletes include commit_sha and message.
