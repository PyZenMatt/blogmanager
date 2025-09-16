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
