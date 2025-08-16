# Setup Export verso GitHub

## Opzione A – Configura per singolo sito (Site.repo_path)

1. Clona la working copy:

```bash
git clone https://github.com/OWNER/REPO.git /path/to/sites/mysite
```
2. In Admin → Site imposta `repo_path = /path/to/sites/mysite`.

## Opzione B – Base comune (BLOG_REPO_BASE)

1. In `.env` aggiungi:

```
BLOG_REPO_BASE=/path/to/sites
```
2. Clona ogni repo in `BLOG_REPO_BASE/<site.slug>`.

### Credenziali push

```bash
export GIT_TOKEN=ghp_xxx
export GIT_USERNAME=x-access-token
export BLOG_EXPORT_GIT_BRANCH=main
```

### Verifica

```bash
python manage.py check_export_repos
python manage.py export_pending_posts
```

### FAQ

* `repo_dir invalido`: manca working copy per quel sito ⇒ configura `repo_path` o crea la cartella fallback.
* Rumore `favicon.ico` nei log: gestito con redirect interno.
