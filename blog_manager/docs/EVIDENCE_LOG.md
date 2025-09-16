# Evidence Log — last_published_hash / idempotent publish

This file documents the key artifacts, commands and test outputs that demonstrate the implementation of idempotent publish via `last_published_hash`.

## What changed

- Added `Post.last_published_hash` (char, 64) to record a content hash (front-matter + body) for the last published version.
- Migration files:
  - `blog/migrations/0022_add_last_published_hash.py` — adds field
  - `blog/migrations/0023_add_index_last_published_hash.py` — adds DB index
- `publish_post` now computes `content_hash(post)` and skips GitHub upsert when unchanged. When skipped, an `ExportJob` is created with `message="no_changes"`.
- Management command `backfill_last_published_hash` added to populate hashes for posts with evidence of prior publish. Supports `--dry-run` and `--force`.

## Commands used during development

- Run all tests:

```bash
pytest -q
```

# Evidence Log — last_published_hash / idempotent publish

This file documents the key artifacts, commands and test outputs that demonstrate the implementation of idempotent publish via `last_published_hash`.

## What changed

- Added `Post.last_published_hash` (char, 64) to record a content hash (front-matter + body) for the last published version.
- Migration files:
  - `blog/migrations/0022_add_last_published_hash.py` — adds field
  - `blog/migrations/0023_add_index_last_published_hash.py` — adds DB index
- `publish_post` now computes `content_hash(post)` and skips GitHub upsert when unchanged. When skipped, an `ExportJob` is created with `message="no_changes"`.
- Management command `backfill_last_published_hash` added to populate hashes for posts with evidence of prior publish. Supports `--dry-run` and `--force`.

## Commands used during development

- Run all tests:

```bash
pytest -q
```

- Run specific tests:

```bash
pytest blog/tests/test_publish_idempotency.py -q
pytest blog/tests/test_backfill_command.py -q
pytest blog/tests/test_repo_edge_cases.py::test_delete_repo_already_absent -q
```

## Test outputs (examples)

- Full test suite (abridged):

```text
...........
[100%]
```

- Targeted publish tests:

```text
.. [100%]
```

- Backfill test:

```text
. [100%]
```

## Flags and DoD

- `EXPORT_ENABLED`: when `False` prevents signal-driven automatic exports during tests.
- `ALLOW_REPO_DELETE`: controls whether admin delete may remove repository files; default is `False` for safety.

DoD met:
- Field and migrations added and applied.
- Backfill implemented with `--dry-run`.
- Publish idempotency implemented and tested (first publish sets hash; unchanged publishes skip upsert).

*** End of evidence log
