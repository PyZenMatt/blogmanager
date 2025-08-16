# Changelog



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
