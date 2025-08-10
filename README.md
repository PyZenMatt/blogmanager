# Blog Manager – Django Headless Backend per Jekyll

[![CI (Django)](https://github.com/PyZenMatt/blogmanager/actions/workflows/ci-django.yml/badge.svg)](https://github.com/PyZenMatt/blogmanager/actions/workflows/ci-django.yml)

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
5. **Applica le migrazioni:**
   ```bash
   python manage.py migrate
   ```
6. **Avvia il server di sviluppo:**
   ```bash
   python manage.py runserver
   ```

## Roadmap e documentazione
- [Roadmap dettagliata Fase 2](./ROADMAP_FASE2.md)
- Documentazione interna: cartella `instructions/`
- [Guida Assistant AI](./docs/AI_ASSISTANT.md)

## CI automatica
La pipeline CI esegue linting (Black, Isort, Flake8), migrazioni e test (pytest/pytest-django o Django test) su Python 3.11 e 3.12 ad ogni push/PR. Vedi [instructions/CI_DJANGO.md](instructions/CI_DJANGO.md) per dettagli.

## Best practice
- Usa commit semantici (`feat:`, `fix:`, `test:`...)
- Non commettere mai segreti: usa `.env.example` e `.gitignore`
- Aggiorna la documentazione se modifichi API o struttura
- Consulta la roadmap per task e priorità

## Licenza
MIT – vedi file `LICENSE`
