# Changelog

## [Unreleased]

### Changed

- `.env.example` aggiornato con chiavi DB e fallback SQLite.
- Ignorati file SQLite in `.gitignore`.


## [0.x.x] - 2025-08-14

### Fix

- Emoji/Unicode 4-byte su MySQL (utf8mb4)
- Doppio submit nel writer eliminato (nessun falso 400)

### Hardening

- Unicità slug per sito + 409 su duplicati

### DX

- Creazione post atomica (M2M post-save in transazione)

### Safe-deploy

- Migrazioni additive; nessuna cancellazione DB


### Fixed

- Export su GitHub resilient: scrittura se file mancante/non tracciato, push anche in assenza di modifiche se `HEAD` è ahead di `origin`. Aggiornamento `export_hash` solo dopo push OK. Nuovo comando `export_pending_posts`.
- Export validation: aggiunti `Site.slug` / `Site.repo_path`, fallback `BLOG_REPO_BASE/<slug>`, comando `check_export_repos`, redirect favicon.


### Added

- Idempotent publish support: added `Post.last_published_hash` to record the hash of the last published content (front-matter + body). Migration `0022_add_last_published_hash.py` and index migration `0023_add_index_last_published_hash.py` included.
- `publish_post` now computes content hash and skips GitHub upsert when no changes are detected; an `ExportJob` is created with `export_error="no_changes"` in that case.
- Management command `backfill_last_published_hash` added to populate missing hashes for previously published posts (supports `--dry-run` and `--force`).


### Notes

- Feature flags: `EXPORT_ENABLED` controls signal-driven exports; `ALLOW_REPO_DELETE` controls whether admin delete can remove repository files. Tests added to cover idempotent publish and backfill flows.
