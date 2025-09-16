Title: Issue 2 — Publish idempotent with `last_published_hash`

Description:

Implement idempotent publish: calculate a content hash (front-matter + body normalized) and store it on Post as `last_published_hash`. On publish, if hash unchanged -> return `no_changes` and skip commit.

Tasks:

- Add `last_published_hash` field to `Post` model (migration).
- Update exporter/publish flow to compute hash and compare with `last_published_hash`.
- Update `upsert_file` logic to return `no_changes` when content identical (optional: compute hash before calling upsert).
- Add tests for create/update/no_changes.

DoD:

- Migration added; exporter publishes and sets `last_published_hash`.
- Re-publish without changes returns `no_changes` and does not create a new commit.
