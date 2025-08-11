Ecco i prossimi due step della roadmap, chiari e sintetici:

---

## 1. Deploy su PythonAnywhere (guida step-by-step)

**Prerequisiti:** account PythonAnywhere gratuito, repository git aggiornato.

### Passaggi:
1. **Crea una nuova Web App su PythonAnywhere**  
   - Scegli “Manual configuration” → Python 3.12

2. **Clona il tuo repository**
   ```bash
   git clone <URL_DEL_TUO_REPO>
   cd <cartella_progetto>
   ```

3. **Crea e attiva la virtualenv**
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configura le variabili d’ambiente**
   - Carica il file `.env` (puoi copiarlo via SFTP o ricrearlo da interfaccia PA)
   - Assicurati che sia nella root del progetto

5. **Aggiorna il file WSGI**
   - Modifica il path nel file WSGI di PythonAnywhere per puntare alla tua app Django

6. **Applica le migrazioni**
   ```bash
   python manage.py migrate
   ```

7. **(Opzionale) Crea superuser**
   ```bash
   python manage.py createsuperuser
   ```

8. **Ricarica la webapp da dashboard PythonAnywhere**

**Checklist rapida:**
- `.env` presente e corretto
- `DEBUG=False` in produzione
- `ALLOWED_HOSTS` contiene il dominio PythonAnywhere
- Tutte le dipendenze installate

---

## 2. Snippet frontend per Jekyll

Aggiungi questo form HTML+JS dove vuoi nel tuo sito Jekyll:

```html
<form id="contactForm">
  <input type="text" name="name" placeholder="Nome" required>
  <input type="email" name="email" placeholder="Email" required>
  <textarea name="message" placeholder="Messaggio" required></textarea>
  <!-- Honeypot anti-spam -->
  <input type="text" name="honeypot" style="display:none">
  <button type="submit">Invia</button>
</form>

<script>
document.getElementById('contactForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  const form = e.target;
  const data = {
    name: form.name.value,
    email: form.email.value,
    message: form.message.value,
    honeypot: form.honeypot.value
  };
  const response = await fetch("https://PyZenMatt.pythonanywhere.com/api/contact/submit/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  const result = await response.json();
  alert(result.success ? "Messaggio inviato!" : "Errore: " + result.error);
});
</script>
```
