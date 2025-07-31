Ecco la roadmap dettagliata per la Fase 1 (Contact API) del progetto, seguendo le tue istruzioni e best practice:

---

## Roadmap Fase 1 – Contact API per Jekyll

### 1. Bootstrap progetto Django
- Crea un nuovo progetto Django (`contact_api`) e una virtualenv.
- Installa dipendenze: `django`, `django-cors-headers`, `python-dotenv`, `pytest-django`.

### 2. Crea l’app “contact” e il modello
- Genera l’app `contact`.
- Definisci il modello `ContactMessage` con i campi: `name`, `email`, `message`, `sent_at`.
- Esegui le migrazioni iniziali.

### 3. Implementa l’endpoint API
- Crea una view JSON POST (`/api/contact/submit/`) esente da CSRF.
- Valida i dati in ingresso (nome, email, messaggio).
- Salva il messaggio nel database.
- Rispondi con `{ "success": true }` o `{ "success": false, "error": "..." }`.

### 4. Configura CORS e settings
- Aggiungi `corsheaders` a `INSTALLED_APPS` e middleware.
- Imposta `CORS_ALLOWED_ORIGINS` solo per i due domini Jekyll.
- Carica variabili da `.env` (usando `python-dotenv`).

### 5. (Opzionale) Notifica email
- Configura invio email con `django.core.mail.send_mail`.
- Prepara `.env.example` con placeholder SMTP.

### 6. Anti-spam
- Implementa honeypot (campo invisibile che deve restare vuoto) oppure rate limiting (`django-ratelimit`).

### 7. Test automatici
- Scrivi test per il modello e la view (happy path, errori di validazione).

### 8. Logging
- Configura logging in formato JSON per produzione.

### 9. Test manuale locale
- Fornisci comando `curl` per testare l’endpoint e output atteso.

### 10. Deploy su PythonAnywhere
- Task list: crea webapp, clona repo, crea venv, installa dipendenze, aggiorna WSGI, applica migrazioni, imposta variabili ambiente, reload.

### 11. Snippet frontend Jekyll
- Fornisci HTML+JS per il form che invia POST JSON all’API.

### 12. Checklist produzione
- Verifica: `DEBUG=False`, `ALLOWED_HOSTS`, secret key in env, email funzionante, HTTPS, CORS, logging.

---

Se vuoi, posso generare subito i comandi per il bootstrap o la struttura iniziale dei file. Vuoi partire dalla creazione del progetto Django?