# Blog Manager – Django Headless Backend per Jekyll


[![CI (Django)](https://github.com/PyZenMatt/blogmanager/actions/workflows/ci-django.yml/badge.svg)](https://github.com/PyZenMatt/blogmanager/actions/workflows/ci-django.yml)
[![pre-commit enabled](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com/)
[![Gitleaks](https://github.com/PyZenMatt/blogmanager/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/PyZenMatt/blogmanager/actions/workflows/gitleaks.yml)

## Descrizione
Blog Manager è un backend Django headless per la gestione di blog multi-sito, pensato per servire contenuti a front-end statici Jekyll tramite API RESTful. Ogni sito Jekyll consuma solo i dati di suo interesse, garantendo efficienza e scalabilità.

## Stack tecnologico
- **Backend:** Python 3.12, Django 5.x, SQLite (dev), Django REST Framework (opzionale)
- **Frontend:** Jekyll (multi-sito)
- **Hosting:** PythonAnywhere (free tier) o simili
- **Dev env:** Windows 11 + WSL2 Ubuntu 24.04, VS Code

## Struttura del progetto

```
blog_manager/
├── blog_manager/         # Configurazione Django (settings, urls, wsgi)
│   └── contact/         # App per gestione contatti (esempio)
├── instructions/        # Documentazione interna e roadmap
├── .env.example         # Esempio variabili ambiente
├── .gitignore           # File e cartelle da ignorare
├── LICENSE              # Licenza MIT
├── README.md            # Questo file
├── ROADMAP_FASE2.md     # Roadmap dettagliata sviluppo
└── manage.py            # Entrypoint Django
```

## Onboarding rapido

1. **Clona il repository:**
   ```bash
   git clone <repo-url>
   cd blog_manager
   ```
2. **Crea e attiva un virtualenv:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Installa le dipendenze:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configura le variabili ambiente:**
    - Copia `.env.example` in `.env` e personalizza i valori.

      - Important environment flags:
         - `ALLOW_REPO_DELETE` (optional, default `False`) — when set to `True` the admin action "DB + Repo" will be enabled and will attempt to delete files from the repository. Use with caution and ensure tokens/permissions are correct.

5. **Setup MySQL locale (opzionale, per test charset/collation):**
   - Installa MySQL 8.x:
     ```bash
     sudo apt update && sudo apt install mysql-server
     sudo systemctl enable mysql
     sudo mysql_secure_installation
     ```
   - Crea database e utente:
     ```sql
     CREATE DATABASE blogmanager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
     CREATE USER 'bm_user'@'localhost' IDENTIFIED BY 'password';
     GRANT ALL PRIVILEGES ON blogmanager.* TO 'bm_user'@'localhost';
     FLUSH PRIVILEGES;
     ```
   - Aggiorna `.env` locale:
     ```
     DB_ENGINE=django.db.backends.mysql
     DB_NAME=blogmanager
     DB_USER=bm_user
     DB_PASSWORD=password
     DB_HOST=127.0.0.1
     DB_PORT=3306
     ```
   - Esegui le migrazioni:
     ```bash
     python manage.py migrate
     ```

6. **Imposta il modulo settings desiderato:**
    - Sviluppo:
       ```bash
       export DJANGO_SETTINGS_MODULE=blog_manager.settings.dev
       python manage.py migrate
       python manage.py runserver
       ```
    - Produzione (es. PythonAnywhere):
       ```bash
       export DJANGO_SETTINGS_MODULE=blog_manager.settings.prod
       python manage.py migrate
       python manage.py runserver
       ```
    - Puoi anche impostare la variabile DJANGO_SETTINGS_MODULE direttamente nella configurazione del servizio (es. PythonAnywhere Web → Environment).

7. **Installa e attiva pre-commit:**
   ```bash
   pip install pre-commit
   pre-commit install
   pre-commit run --all-files
   ```

## Roadmap e documentazione
- [Roadmap dettagliata Fase 2](./ROADMAP_FASE2.md)
- Documentazione interna: cartella `instructions/`
- [Guida Assistant AI](./docs/AI_ASSISTANT.md)

## CI automatica
La pipeline CI esegue linting (Black, Isort, Flake8), migrazioni e test (pytest/pytest-django o Django test) su Python 3.11 e 3.12 ad ogni push/PR. Inoltre, il workflow Gitleaks verifica l'assenza di segreti nei commit e nelle PR. Vedi [instructions/CI_DJANGO.md](instructions/CI_DJANGO.md) per dettagli.

## Best practice
- Usa commit semantici (`feat:`, `fix:`, `test:`...)
- Non commettere mai segreti: usa `.env.example` e `.gitignore`
- Aggiorna la documentazione se modifichi API o struttura
- Consulta la roadmap per task e priorità

## Licenza
MIT – vedi file `LICENSE`

**Local production reproduction (Docker Compose)**

- Copy `.env.example` to `.env` and adjust values (especially `SECRET_KEY` and `GIT_TOKEN`).

  ```bash
  cp .env.example .env
  # edit .env and set SECRET_KEY, GIT_TOKEN, DATABASE_URL if needed
  ```
- Build and run with Docker Compose:

  ```bash
  docker compose up --build
  ```
- The app will be available at `http://localhost:8000`. Postgres data is stored in a Docker volume named `db-data`.
