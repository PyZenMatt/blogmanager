# Sicurezza accesso GitHub tramite token

## Best practice

- Il token GitHub (`GITHUB_TOKEN`) deve essere impostato solo tramite variabili d’ambiente lato server.
- Lo scope del token deve essere minimo (consigliato solo `repo`).
- Il token non deve mai essere stampato in chiaro nei log o salvato in file di codice/configurazione.
- Nei log, il token deve essere mascherato (es: `ghp_***MASKED***`).
- I settings devono leggere il token solo da env e non salvarlo in file o codice.

## Applicazione

- Verificare che in `settings.py` il token sia letto solo da variabili d’ambiente.
- Aggiungere filtri/mask nei log per evitare la stampa accidentale del token.
- Effettuare controlli periodici su codice e log per assicurarsi che il token non sia presente in chiaro.

## Esempio

```python
import os
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
```

## Logging sicuro

```python
import logging

def mask_token(token):
    if token and len(token) > 8:
        return token[:4] + '***MASKED***'
    return token

logging.info(f"GitHub token: {mask_token(GITHUB_TOKEN)}")
```

## Checklist
- [x] Token solo in env
- [x] Scope minimo
- [x] Mask nei log
- [x] Controllo settings
