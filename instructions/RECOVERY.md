# RECOVERY / ROLLBACK PLAYBOOK

Questa documentazione fornisce procedure per il recovery e il rollback del sistema Blog Manager.

## LAST_GOOD_SHA (pre-loop + utf8mb4)
Usa `LAST_GOOD_SHA=6ac4375` come baseline stabile per recovery.
Questa revisione include i fix per slug per sito e supporto a emoji/utf8mb4, senza segnali di export automatico.

### Verifica MySQL utf8mb4
Consulta il Runbook per `SHOW VARIABLES` e, se necessario, esegui:
`ALTER DATABASE ... CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`
`ALTER TABLE ... CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`

### Re-introduzione export
L'export on_publish verrà reintrodotto solo in una patch separata, dietro feature flag.

---

## Runbook (operativo post-PR)

### VS Code (locale)

```bash
export LAST_GOOD_SHA=6ac4375
git switch --detach $LAST_GOOD_SHA
git switch -c recovery/pre-export-automatico-utf8mb4
# applica patch, poi:
black --check . && isort --check-only . && flake8
python manage.py test
git push -u origin $(git branch --show-current)
```

### MySQL verifica/convert (prod)

```sql
SHOW VARIABLES LIKE 'character_set_server';
SHOW VARIABLES LIKE 'collation_server';
SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = 'blogmanager_db';
SELECT TABLE_NAME, TABLE_COLLATION
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'blogmanager_db';
-- Se necessario:
ALTER DATABASE blogmanager_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Per tabelle non conformi:
ALTER TABLE blog_post CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Smoke test manuale

1. Crea 2 post con titolo "Prova 🚀🔥" nello stesso sito → slug diversi, nessun 500.
2. Esegui `python manage.py check_encoding` (dry-run) → nessun crash, eventuali "SUSPECT" elencati.

---

## Acceptance (Gherkin)

```gherkin
Feature: Salvataggio contenuti con emoji su MySQL senza loop
  Scenario: Creazione di due post con stesso titolo (emoji) nello stesso sito
    Given esiste un sito "messymind"
    When creo due post con titolo "Prova 🚀🔥" su "messymind"
    Then i due slug generati devono essere diversi
    And nessun errore di codifica si verifica

  Scenario: Pubblicazione post senza trigger di export automatico
    Given un post draft con emoji
    When imposto is_published=True e salvo
    Then non viene eseguito alcun job di export automatico
    And non si verifica alcun loop di publish
```

## Rischi & Mitigazioni

- **Dati già "sporchi" (mojibake)** → `check_encoding` segnala e può normalizzare soft con `--apply`.
- **Migrazione CONVERT bloccante su tabelle grandi** → eseguire in fascia bassa; avere backup.
- **Ambiente prod non 12-factor** → settings tornano a .env.
- **Loop export** → non incluso; verrà reintrodotto in patch separata con feature flag e test anti-reentrancy.

---

## Emergency Procedures

### Rollback Database Changes

Se la migrazione utf8mb4 causa problemi:

1. **Ripristino da backup:**
   ```bash
   mysql -u user -p database_name < backup_before_utf8mb4.sql
   ```

2. **Rollback migrations:**
   ```bash
   python manage.py migrate blog 0019
   ```

### Settings Rollback

Se la configurazione 12-factor causa problemi, temporary fallback:

1. Commenta `build_database_config` in `settings/base.py`
2. Ripristina configurazione hardcoded temporaneamente
3. Risolvi i problemi di env vars
4. Ripristina configurazione 12-factor

### Verifica Integrità Post-Recovery

Dopo ogni operazione di recovery:

```bash
# Test database connectivity
python manage.py shell -c "from django.db import connection; print('DB OK:', connection.ensure_connection() is None)"

# Check encoding issues
python manage.py check_encoding

# Run critical tests
python manage.py test blog.tests.test_models

# Verify admin access
python manage.py createsuperuser --noinput --username=admin --email=admin@example.com || echo "User exists"
```