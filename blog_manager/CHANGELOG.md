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
