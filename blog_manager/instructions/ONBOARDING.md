
# Onboarding: Setup MySQL locale per test charset/collation

## 1. Installazione MySQL 8.x

Ubuntu/Debian:
```bash
sudo apt update && sudo apt install mysql-server
sudo systemctl enable mysql
sudo mysql_secure_installation
```

## 2. Creazione database e utente
Accedi a MySQL:
```bash
sudo mysql -u root -p
```
Esegui:
```sql
CREATE DATABASE blogmanager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'bm_user'@'localhost' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON blogmanager.* TO 'bm_user'@'localhost';
FLUSH PRIVILEGES;
```

## 3. Configurazione Django
Modifica `.env` locale:
```
DB_ENGINE=django.db.backends.mysql
DB_NAME=blogmanager
DB_USER=bm_user
DB_PASSWORD=password
DB_HOST=127.0.0.1
DB_PORT=3306
```

## 4. Migrazioni
```bash
python manage.py migrate
```

## 5. Test emoji/charset
Esegui:
```bash
pytest -k "test_create_post_with_emoji_ok"
```
Oppure crea manualmente un post con API contenente emoji 4-byte (es: 👩🏽‍💻😄✨) e verifica status 201.

## Note
- Assicurati che la versione MySQL locale sia la stessa (major) di produzione.
- Se MySQL è già in uso, crea un DB separato per test.

---

## Slug Unicità e Gestione

- Lo slug dei post è ora **univoco per sito** (`(site, slug)`), non globale.
- In assenza di slug esplicito, il backend genera uno slug e **aggiunge suffisso** in caso di collisione (`titolo`, `titolo-2`, `titolo-3`).
- Un `POST` con slug già presente nello stesso sito ritorna **409 Conflict** con messaggio esplicativo; con slug mancante, il server genera uno slug valido.
- Lo slug generato resta **stabile** dopo la creazione; cambi slug → redirect lato Jekyll a carico del frontend se necessario.

## API e Error Handling

- Se si tenta di creare un post con slug duplicato nello stesso sito, la risposta è **409 Conflict**.
- Slug identici su siti diversi sono permessi.

## SEO

- Lo slug è stabile e non viene rigenerato automaticamente dopo la creazione.
- In caso di update, la validazione blocca i conflitti ma non rigenera lo slug.

## Test e Runbook

- Test automatici coprono casi di titoli uguali nello stesso sito, titoli uguali in siti diversi, e collisione simultanea.
- Vedi `tests/api/test_slug_integrity.py` per esempi.

## Rollout

1. Migrazione: rimozione `unique=True` sul campo, data migration per de‑dup, `UniqueConstraint(site, slug)`.
2. Test: `pytest -q` (coverage ≥85%).
3. Deploy: `python manage.py migrate` su staging/prod.
4. Smoke test: POST due volte stesso titolo sullo stesso sito → slug `x` e `x-2`. POST slug esplicito duplicato → **409**.
