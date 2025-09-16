Ruolo: Sei Tech Lead + Issue Architect + Django/DRF Senior Operativo del progetto Blog Manager, backend headless (Django 5.x + DRF) per servire blog multi-sito Jekyll (JSON per siti statici). L’app include: contenuti, endpoint REST, contact POST /api/contact/submit/, storage locale (opzione Cloudinary/S3), CI, deploy su PythonAnywhere.


## Checklist (rapida)

1. Definisci **missione e scope** (commit diretto via GitHub API, zero repo locali).
2. Fissa **guardrails** (sicurezza, idempotenza, niente wall-of-code, micro-commit).
3. Descrivi **workflow**: Publish, Refresh, Delete (DB-only / DB+Repo).
4. Imposta **feature flag** e configurazioni.
5. Stabilisci **DoD**, **Stop-rules**, **fallback** e **rollback**.
6. Aggiungi **QA checklist** e casi limite.
7. Pianifica **telemetria/audit** e messaggistica Admin.

---

# 📄 AGENT_PLAYBOOK — BlogManager (Publish via GitHub API, no terminal)

> File suggerito: `docs/AGENT_PLAYBOOK_BlogManager.md`

## 1) Missione

Rendere la pubblicazione di articoli **one-click** dal pannello Admin, senza usare il terminale e senza repo clonati in locale. Il sistema deve:

* Scrivere/aggiornare file Markdown nei repo target **via GitHub API** con **commit diretto** sul branch di default.
* Offrire un **Refresh** per riallineare lo stato DB↔GitHub (commit, presenza file).
* Gestire la **cancellazione** con scelta esplicita: **solo DB** oppure **DB + file nel repo**.

## 2) Scope (in / out)

**In scope**

* Pubblicazione articoli: generazione contenuto MD (front-matter già incluso nel body testuale), path calcolato, commit diretto.
* Elenco target blog (repo, branch, path base) letto da DB/config esistente.
* Admin Actions: **Publish**, **Refresh**, **Delete (DB-only / DB+Repo)**.
* Telemetria base: audit log per ogni Publish/Refresh/Delete con esito, SHA, URL commit.

**Out of scope (per ora)**

* Frontend pubblico per la pubblicazione.
* Normalizzazione o generazione automatica del front-matter.
* PR/branch multipli, auto-merge, workflow complessi.
* Storage e gestione asset immagine.

## 3) Principi e Guardrails

* **Zero repo locali**: dismettere pull/rebase. Solo GitHub API.
* **Idempotenza**: calcolo **content hash** (front-matter + body normalizzato). Se invariato → no nuovo commit.
* **Atomicità visibile**: un articolo = un commit; ok più commit se necessario, ma evitare rumore.
* **Sicurezza**: usare **GitHub App** o token con permessi minimi; feature flag per operazioni distruttive.
* **Messaggi Admin** chiari**:** link al commit, stato (success/warning/error), motivazione (e.g., “no changes”).
* **Micro-patch**: modifiche piccole e reversibili; niente refactor massivi.
* **Log/audit** obbligatori: sempre traccia di cosa è stato fatto e dove.

## 4) Definizioni operative

* **Article**: record con testo completo (incluso front-matter nel corpo), slug, target blog associato, stato: `draft|ready|published`.
* **Target blog**: repo (`owner/name`), branch default, `content_root` (path base), policy di commit diretto.
* **PublishRun** (audit): esecuzione di publish con `status`, `message`, `commit_sha`, `repo_path`, `duration_ms`.

## 5) Workflow

### 5.1 Publish (Admin Action)

1. **Input**: article id (o batch), target (implicito o multiplo).
2. **Pre-check**: validare slug e path (`content_root/yyyy/mm/slug.md` o schema attuale).
3. **Content hash**: se hash==`last_published_hash` → **STOP**: “nessuna modifica” (idempotenza).
4. **Commit diretto** (branch default):

   * Se file non esiste: create.
   * Se file esiste: update.
   * Messaggio commit: `content/publish: {title} (#{id})`.
5. **Post-azione**:

   * Aggiorna `last_published_hash`, `last_commit_sha`, `repo_path`.
   * Stato: `published`.
   * Audit: registra esito con URL commit.

**Errori gestiti**

* 404 repo/path: crea file.
* 409/412 (sha mismatch): rileggi sha e ritenta una volta (backoff minimo).
* 403/401: segnalare permessi/token; non cambiare stato dell’articolo.

### 5.2 Refresh (Admin Action)

1. Se `repo_path` esiste: leggi file via API nel branch default.
2. Se presente:

   * Confronta contenuto con DB → se drift inatteso, mostra warning (“contenuti divergenti”).
   * Mostra `last_commit_sha` noto vs più recente.
3. Se assente:

   * Se DB dice `published`: mostra warning e propone correzione stato o republish.
4. Audit: logga esito confronto.

### 5.3 Delete con scelta (Admin Action con conferma)

**Opzione A — Solo DB**

* Hard delete o soft delete (preferibile soft con `deleted_at`), **senza** toccare GitHub.
* Audit: `action=delete_db_only`.

**Opzione B — DB + Repo**

* Se `repo_path` valorizzato: delete via API sul branch default.
* Commit message: `content/remove: {title} (#{id})`.
* Se 404 (già assente): considerare **successo idempotente**.
* Poi elimina/archivia in DB.
* Pulisci i campi `repo_path`, `last_commit_sha` (o sposta in storico).
* Audit: `action=delete_repo_and_db`, con `commit_sha` e URL commit se disponibile.

**Regola di sicurezza**: l’opzione B è attiva solo se `ALLOW_REPO_DELETE=true`.

## 6) Feature Flags & Settings

* `COMMIT_DIRECT=true` (no PR).
* `ALLOW_REPO_DELETE` (default: false in dev/staging, true on-demand).
* `DRY_RUN=false` (se true, simula operazioni senza scrivere).
* `GITHUB_APP_ENABLED` (preferibile a PAT).
* `MAX_RETRY=1` su update con SHA mismatch; backoff breve.

## 7) Telemetria & Audit

Per **ogni** azione:

* `action`: publish | refresh | delete_db_only | delete_repo_and_db
* `status`: success | no_changes | warning | error
* `message`: breve motivo umano-leggibile
* `repo`: owner/name, `branch`
* `path`: repo_path
* `commit_sha`, `commit_url` (quando applicabile)
* `content_hash` attuale
* `duration_ms`, `timestamp`
* (facolt.) `details` JSON con risposta minima API

## 8) QA Checklist (per l’agente)

* **Publish**

  * Nuovo articolo → create → stato published, commit visibile.
  * Articolo aggiornato → update → nuovo commit; hash cambia.
  * Nessuna modifica → “no changes”, nessun commit.
* **Refresh**

  * File presente e coerente → OK.
  * Divergenza contenuto → warning con azione suggerita.
  * File assente ma DB published → warning.
* **Delete**

  * Solo DB → record rimosso/archiviato, repo intatto.
  * DB+Repo → commit di delete; idempotente su 404.
* **Rate limit/permessi**: messaggi espliciti, nessuna modifica DB in caso di errore.

## 9) Stop-Rules (quando fermarsi)

* Manca `repo_path` atteso e non è calcolabile → STOP con errore guidato.
* Token/permessi GitHub non validi → STOP e richiedi configurazione.
* Flag `DRY_RUN=true` in produzione → STOP (se non intenzionale).
* `ALLOW_REPO_DELETE=false` per azione DB+Repo → STOP con messaggio.

## 10) Fallback & Rollback

* **Publish fallito**: nessuna modifica di stato; audit con errore. Riprova dopo fix.
* **Update con mismatch SHA**: un solo retry; se fallisce, STOP (evitare loop).
* **Delete DB+Repo fallita**: non cancellare DB; proporre retry o fallback “Solo DB”.
* **Rollback**: ripristinare contenuto da commit precedente (manuale via GitHub UI; link nel log).

## 11) Requisiti di accettazione (DoD)

* Da Admin:

  * Posso pubblicare senza console; vedo link al commit.
  * Posso fare Refresh e leggere la coerenza DB↔repo.
  * Posso eliminare scegliendo **DB** o **DB+Repo** con conferma.
* Telemetria completa per **tutte** le azioni.
* Idempotenza verificata: “no changes” non crea commit.

## 12) Note implementative (senza codice)

* Estendere il **client GitHub** con `delete_file` (gestisce 404 come “already absent”).
* Mantenere `upsert_file` esistente per publish.
* Aggiungere field `last_published_hash` (se non presente).
* `ModelAdmin`:

  * Action “Publish”
  * Action “Refresh”
  * Action “Delete (con scelta)” → form di conferma con radio: `DB only` / `DB+Repo`
* Messaggi Admin sintetici con link agli artefatti (commit).

## 13) Governance del lavoro (per l’agente)

* **Micro-piani a 3 step**. Esegui 1 step → verifica → prosegui.
* **Commit piccoli** con messaggi “content/publish”, “ops/delete”, “ops/refresh”.
* Aggiorna `docs/CHANGELOG.md` e `docs/EVIDENCE_LOG.md` al termine di ogni step significativo.
* Non introdurre dipendenze nuove senza approvazione.

---

Questo playbook è pronto per essere messo nel repo sotto `docs/`.
Vuoi che adesso apra le **issue operative** (piccole e sequenziali) in base a questo playbook?

## 14) Issue Intake & Implementation (operational agreement)

Per evitare fraintendimenti, la procedura che seguirò quando mi fornisci issue pronte è la seguente:

* **Formato issue richiesto**: ogni issue deve includere breve descrizione, criterio di accettazione (DoD), file/moduli interessati, e se applicabile `DRY_RUN=true` per operazioni distruttive.
* **Approccio di lavoro**: implemento cambiamenti direttamente sul branch `main` solo per modifiche non rischiose e documentazionali; per codice di produzione sensibile creerò un branch feature e aprirò una PR se vuoi revisione.
* **Commit e messaggi**: ogni cambiamento sarà un micro-commit con messaggio chiaro (`ops/<area>: breve descrizione` o `content/publish: ...`).
* **Testing**: eseguo test automatici disponibili (`pytest`) per le aree toccate; se i test non esistono aggiungerò test minimi quando appropriato.
* **Rollback**: aggiungerò note di rollback nelle issue e, quando possibile, un test che dimostri lo stato atteso dopo rollback.
* **Temp flag**: per operazioni distruttive o delete repo userò `DRY_RUN=true` come default e ti chiederò conferma per disabilitarlo.
* **Audit & Telemetria**: ogni operazione importante aggiornerà i log in `docs/EVIDENCE_LOG.md` con riferimento commit, timestamp e risultato.

Se vuoi, posso ora trasformare il playbook aggiornato in una serie di issue operative pronte (titoli + descrizioni + DoD). Dimmi il numero di issue che preferisci generare in batch (es: 5). 
