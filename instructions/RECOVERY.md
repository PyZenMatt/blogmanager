# Recovery to a known-good commit (pre-loop)

## Prerequisiti
- Identifica `LAST_GOOD_SHA` (commit immediatamente precedente all'inizio del loop).
- _Opzionale_: elenca SHA di fix sicuri da **cherry-pick**.

## Comandi (locale/Codespaces)
```bash
# 1) Verifica history intorno alla finestra del problema
git log --since="2025-08-15 20:00" --until="2025-08-15 23:59" --oneline --decorate

# 2) Crea branch di recovery staccato dal known-good
export LAST_GOOD_SHA=97ab3c1  # sostituisci con il tuo SHA
export TODAY=$(date +%Y%m%d)
export SHORT_SHA=${LAST_GOOD_SHA:0:7}
git switch --detach $LAST_GOOD_SHA
git switch -c recovery/${TODAY}${SHORT_SHA}

# 3) (Opzionale) Cherry-pick di fix sicuri
git cherry-pick 1a2b3c4  # esempio: fix CI
git cherry-pick d5e6f7a  # esempio: docs hotfix

# 4) Lint e test prima del push
ruff check . --fix
black --check .
isort --check-only .
pytest -q --cov=blog_manager --cov-report=term-missing

# 5) Push del branch di recovery
git push -u origin recovery/${TODAY}${SHORT_SHA}
```

## Apertura PR
1. Vai su GitHub e apri una PR da `recovery/<YYYYMMDD><shortsha>` verso `main`
2. Usa questo template per la descrizione:

```markdown
## Recovery: Restore to known-good @ <LAST_GOOD_SHA>

### Contesto
- **Problema**: Loop di commit con errore 500
- **Known-good SHA**: <LAST_GOOD_SHA>  
- **Finestra temporale problema**: <TIMESTAMP_INIZIO> - <TIMESTAMP_FINE>
- **Cherry-pick applicati**: <SHA_LIST o "nessuno">

### Verifiche pre-merge
- [ ] Test suite passa (cov ≥85%)
- [ ] Lint/format OK
- [ ] Smoke test export: `python manage.py check_export --site <slug> --dry-run`

### Post-merge
- [ ] Tag: `git tag hotfix/recovery<YYYYMMDD><shortsha> && git push --tags`
- [ ] Monitor export (no loop)

### Rollback Plan
Se questa PR causa regressioni:
1. `git revert -m 1 <merge-commit-sha>`
2. Push e apri PR di revert
```

## Note importanti
- **Niente reset forzati su `main`**: operare sempre via branch + PR.
- Evitare cherry-pick di commit che reintroducono il loop.
- Dopo merge: **tag** `hotfix/recovery<YYYYMMDD><shortsha>`.

## Rollback (PR)
Se la PR causasse regressioni:
1. `git revert -m 1 <merge-commit-sha>`
2. Push e apri PR di revert.

## Smoke test post-merge
1. `python manage.py check_export --site <slug> --dry-run`  
2. Salva/aggiorna un post: verifica log exporter = `OK` o `NO_CHANGES`, **mai loop**.

## Runbook completo

### A) Preparazione
1. Identifica `LAST_GOOD_SHA` usando `git log` o GitHub commit history
2. Stima finestra temporale del problema
3. Lista eventuali fix da preservare via cherry-pick

### B) Recovery workflow
1. Crea branch: `git switch --detach LAST_GOOD_SHA && git switch -c recovery/<YYYYMMDD><shortsha>`
2. (Opz.) Cherry-pick: `git cherry-pick <sha...>` dei fix confermati
3. Lint e test: `ruff`, `black --check`, `isort --check-only`, `pytest -q` (cov ≥85%)
4. `git push -u origin recovery/...`
5. Aprire PR con:
   - descrizione recovery
   - link a commit/compare
   - esito test
   - piano rollback
6. Dopo merge: tag `hotfix/recovery<YYYYMMDD><shortsha>`.

### C) Definition of Done
- Branch creato da LAST_GOOD_SHA, PR aperta e test verdi
- Smoke `python manage.py check_export --site <slug> --dry-run` OK
- Export reale: commit e push singolo (no loop)

### D) Rollback
- `git revert -m 1 <merge-commit-sha>` + PR di revert.