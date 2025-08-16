# Deployment Playbook

## Migrazione a MySQL (PythonAnywhere)

### 1. Provisioning MySQL
Crea il database MySQL su PythonAnywhere (tab Databases) e annota:
- HOST: es. yourusername.mysql.pythonanywhere-services.com
- NAME: es. yourusername$default
- USER: il tuo username
- PASSWORD: la password scelta

### 2. Dipendenze
Aggiungi a requirements.txt:
```
mysqlclient>=2.2
```
Installa con pip:
```
pip install -r requirements.txt
```

### 3. Variabili ambiente
Imposta su PythonAnywhere (Web → Environment Variables):
- DJANGO_SETTINGS_MODULE=blog_manager.settings.prod
- MYSQL_NAME=...
- MYSQL_USER=...
- MYSQL_PASSWORD=...
- MYSQL_HOST=...
- MYSQL_PORT=3306
- CONN_MAX_AGE=60

### 4. Configurazione settings
In `blog_manager/settings/prod.py`:
```python
from .base import *
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_NAME"),
        "USER": env("MYSQL_USER"),
        "PASSWORD": env("MYSQL_PASSWORD"),
        "HOST": env("MYSQL_HOST"),
        "PORT": env("MYSQL_PORT"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "use_unicode": True,
            "init_command": "SET sql_mode='STRICT_ALL_TABLES', time_zone='+00:00'",
        },
        "CONN_MAX_AGE": env.int("CONN_MAX_AGE", default=60),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

### 5. Migrazione schema
Esegui:
```
python manage.py migrate --noinput
```

### 6. Dump e migrazione dati
Da SQLite (ambiente attuale):
```
python manage.py dumpdata --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.Permission \
  --exclude admin.logentry \
  --format=json --indent=2 > dump.json
```
Su MySQL (produzione):
```
python manage.py loaddata dump.json
```

Se ricevi errori di FK, separa in due dump: prima tassonomie (Sites, Authors, Categories, Tags), poi Posts/Contact.

### 7. Sanity check
Esegui:
```
python manage.py shell -c "from blog.models import Post, Site; print(Site.objects.count(), 'sites,', Post.objects.count(), 'posts')"
```

### 8. Backup & rollback
Conserva dump.json e annota istruzioni per tornare a SQLite o ripristinare dati.

---

This guide standardizes deployment and rollback operations for the blog_manager project on PythonAnywhere (production) and local development environments.

## 1. Required Environment Variables

| Variable Name         | Description                        | Example Value                | Where to Set         |
|----------------------|------------------------------------|------------------------------|----------------------|
| DJANGO_SECRET_KEY    | Django secret key                  | <random-string>              | .env / PA Web config |
| DJANGO_SETTINGS_MODULE | Django settings module            | blog_manager.settings.prod    | .env / PA Web config |
| DATABASE_URL         | Database connection string         | sqlite:///db.sqlite3         | .env / PA Web config |
| CONN_MAX_AGE         | Database connection max age (sec)  | 60                           | .env / PA Web config |
| CLOUDINARY_URL       | Cloudinary API URL (if used)       | cloudinary://...             | .env / PA Web config |
| EMAIL_HOST           | SMTP server                        | smtp.gmail.com               | .env / PA Web config |
| EMAIL_HOST_USER      | SMTP username                      | user@gmail.com               | .env / PA Web config |
| EMAIL_HOST_PASSWORD  | SMTP password                      | <password>                   | .env / PA Web config |
| ...                  | ...                                | ...                          | ...                  |

## 2. Migration Commands

**Production (PythonAnywhere):**
```bash
# Activate virtualenv if needed
workon <your-virtualenv>
cd ~/blog_manager
python manage.py migrate
```

**Local Development:**
```bash
cd /path/to/blog_manager
python manage.py migrate
```

## 3. Static and Media Routes

- **Production:**
    - Configure static and media files in PythonAnywhere Web tab:
        - Static: `/home/<user>/blog_manager/static/`
        - Media: `/home/<user>/blog_manager/media/`
    - Update `settings.py`:
        ```python
        STATIC_ROOT = os.path.join(BASE_DIR, 'static')
        MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
        ```
    - Collect static files:
        ```bash
        python manage.py collectstatic
        ```
- **Local:**
    - Static/media served automatically in development.

## 4. Post-Deploy Checks

- Visit `/health/` endpoint to confirm app is running.
- Access `/admin/` to verify admin login.
- Run an export test (if available):
    ```bash
    python manage.py export_test
    # or test via UI if feature exists
    ```

## 5. Rollback Procedure

1. Revert to previous commit:
    ```bash
    git log # find commit hash
    git revert <commit-hash>
    git push
    ```
2. Re-deploy (repeat migration/static steps above).
3. Republish posts if needed (via admin or management command).

---

## Gherkin Acceptance Criteria

```
Given a new team member
When they follow this playbook
Then they can deploy without assistance
```

---

For further details, see `README.md` and environment-specific settings in `settings/`.
