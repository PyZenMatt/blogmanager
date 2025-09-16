Title: I1-F4 — Admin messages mapping for delete outcomes

Description:

Define a mapping from client/service outcomes to short Admin messages.

Mapping:

- `deleted` -> `Eliminazione completata — commit: <short_sha>`
- `already_absent` -> `File già assente — allineamento effettuato`
- `no_repo_path` -> `Nessun percorso repo registrato per il post`
- `401/403` -> `Permessi GitHub insufficienti per owner/repo@branch path: ...`

DoD:

- Mapping added to docs and a small helper function in `blog/services/github_ops.py` or `blog/utils` that converts client response to message.
