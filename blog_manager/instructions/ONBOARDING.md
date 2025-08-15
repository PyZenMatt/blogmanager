# ONBOARDING

## Avvio rapido (Django 5.x)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Imposta i settings (sviluppo di default)
export DJANGO_SETTINGS_MODULE=blog_manager.settings.dev

python blog_manager/manage.py check
python blog_manager/manage.py migrate
python blog_manager/manage.py runserver
```

### Struttura attesa

```
repo-root/
  blog_manager/
    manage.py
    blog_manager/
      __init__.py
      settings/
        __init__.py
        base.py
        dev.py
        prod.py
      asgi.py
      wsgi.py
```

Se ottieni `ModuleNotFoundError: No module named 'blog_manager'`:
1) Assicurati che `blog_manager/blog_manager/__init__.py` esista.  
2) Lancia i comandi dalla root repo o prefixa il path: `python blog_manager/manage.py check`.  
3) Verifica `echo $DJANGO_SETTINGS_MODULE` → `blog_manager.settings.dev`.
