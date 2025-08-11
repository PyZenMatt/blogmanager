# CI (Django)

[![CI (Django)](https://github.com/PyZenMatt/blogmanager/actions/workflows/ci-django.yml/badge.svg)](https://github.com/PyZenMatt/blogmanager/actions/workflows/ci-django.yml)

Questo workflow esegue linting (Black, Isort, Flake8) e test (pytest/pytest-django o Django test) su Python 3.11 e 3.12 ad ogni push/PR.

## Uso

- Il badge sopra mostra lo stato della CI.
- La pipeline verifica:
  - Lint pulito (Black, Isort, Flake8)
  - Migrazioni e check Django
  - Test automatici (pytest o Django test)

## Configurazione

- Variabili d'ambiente usate:
  - `DJANGO_SETTINGS_MODULE=blog_manager.settings`
  - `SECRET_KEY=ci-not-secret`
  - `DEBUG=0`

## File workflow

Vedi `.github/workflows/ci-django.yml` per dettagli e personalizzazione.
