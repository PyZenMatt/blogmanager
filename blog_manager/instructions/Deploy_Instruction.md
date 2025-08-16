## Database
L’app supporta due backend:

- **MySQL** (default in produzione)
- **SQLite** (fallback emergenziale / low-traffic)

Selezione via `.env`:
- `DB_ENGINE=mysql|sqlite`
- Con `sqlite` in ambiente **prod** è richiesto `ALLOW_SQLITE_IN_PROD=true`.

Trade-off SQLite:
- ottimo per low-traffic e backend read-heavy;
- rischio di lock su scritture concorrenti; dimensione file e backup semplici;
- consigliato come soluzione temporanea o per ambienti con poche scritture.
