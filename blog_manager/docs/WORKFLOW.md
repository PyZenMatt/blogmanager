# Workflow & QA Matrix — BlogManager

Overview
- The application performs three main admin-driven external actions against Jekyll repos:
  - `Publish`: create/update a post file via GitHub API (commit).
  - `Refresh`: read post file from repo and compare against DB content.
  - `Delete`: remove file from repo and optionally delete DB record.

Audit schema (ExportJob)
- `action`: `publish` | `refresh` | `delete_db_only` | `delete_repo_and_db`
- `export_status`: `success` | `failed` | `pending`
- `message`: short reason/details (`no_changes`, `ok`, `drift_absent`, `drift_content`, `Token mancante o permessi insufficienti`, `Rate limit raggiunto`)

Operational flags
- `EXPORT_ENABLED` (bool): enable/disable automatic exports and some management behavior.
- `ALLOW_REPO_DELETE` (bool): if `False`, admin UI will not attempt repo deletions; protects production repos.

QA Matrix (cases and expected behavior)
- Publish
  - ok (content changed): `action=publish`, `export_status=success`, `message=None` (commit recorded in `commit_sha`)
  - no_changes (idempotent): `action=publish`, `export_status=success`, `message=no_changes`
  - auth/perm denied (401/403): `action=publish`, `export_status=failed`, `message=Token mancante o permessi insufficienti`
  - rate-limited (429): `action=publish`, `export_status=failed`, `message=Rate limit raggiunto`

- Refresh
  - ok (remote matches): `action=refresh`, `export_status=success`, `message=ok`
  - drift_absent (file missing): `action=refresh`, `export_status=failed`, `message=drift_absent`
  - drift_content (content mismatch): `action=refresh`, `export_status=failed`, `message=drift_content`
  - auth/perm denied (401/403): `action=refresh`, `export_status=failed`, `message=Token mancante o permessi insufficienti`
  - rate-limited (429): `action=refresh`, `export_status=failed`, `message=Rate limit raggiunto`

- Delete
  - already_absent: service returns `already_absent` and `ExportJob` created with `export_status=success`, `action=delete_db_only` (or `delete_repo_and_db` per flow), `message=None`.
  - deleted: `export_status=success`, `action=delete_repo_and_db`, `message=None`
  - auth/perm denied (401/403): `export_status=failed`, `action` appropriate, `message=Token mancante o permessi insufficienti`

Admin messaging guidelines
- Map GitHub 401/403 to: "Token mancante o permessi insufficienti" and suggest checking `GITHUB_TOKEN` and repo permissions.
- Map rate-limit errors (429) to: "Rate limit raggiunto: riprova più tardi" and suggest retrying after some minutes.
- For drift cases, the Admin will show warnings indicating absent or differing content and an `ExportJob` will record the short message.

Examples & quick checks
- Use `ExportJob.objects.filter(action="publish", message="no_changes")` to find idempotent publishes.
- Use `ExportJob.objects.filter(action="refresh", message="drift_content")` to find content drift incidents to triage.
## Delete via API (GitHub)

Semantica di delete usata dal sistema:

- `deleted`: il file è stato rimosso dal repo con un commit; il sistema registra `commit_sha` (se disponibile) e `html_url`.
- `already_absent`: il file non esisteva nel repo al momento della chiamata; considerare successo idempotente.
- `no_repo_path`: post senza `repo_path` non verranno toccati.

Audit e Admin messages:

- `deleted` -> "Eliminazione su repo completata — commit: <short_sha>"
- `already_absent` -> "File già assente nel repo — allineamento DB completato"
- `no_repo_path` -> "Nessun percorso repo registrato per il post"
- errori 401/403 -> "Permessi GitHub insufficienti (401/403) per owner/repo@branch path: ..."

Flow suggerito per Delete (DB+Repo):

1. Chiama `GitHubClient.delete_file(...)`.
2. Se `status == 'deleted'` -> registra commit in audit, poi rimuovi/archivia il record nel DB.
3. Se `status == 'already_absent'` -> registra evento di idempotenza e procedi con la rimozione DB.
4. Se errore -> non modificare DB; mostra messaggio Admin e riprova manuale.
