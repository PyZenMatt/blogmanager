# Roadmap: Gestione immagini per blog multi-sito con Django + Cloudinary compatibile Jekyll

## Obiettivo
Gestire immagini per post multi-blog in Django, con storage su Cloudinary, URL assoluti pubblici, struttura organizzata per sito/post, e integrazione Markdown compatibile Jekyll.

---

## Fasi principali

### 1. Analisi e setup
- [ ] Definire struttura desiderata degli URL e dei path su Cloudinary
- [ ] Scegliere/aggiungere i pacchetti Python necessari (`django-cloudinary-storage`)
- [ ] Aggiornare `requirements.txt` e installare dipendenze

### 2. Configurazione Django
- [ ] Configurare Cloudinary in `settings.py` (chiavi, storage, media URL)
- [ ] Impostare `DEFAULT_FILE_STORAGE` su Cloudinary
- [ ] Verificare che i file caricati vadano su Cloudinary e siano pubblici

### 3. Modelli e upload path
- [ ] Creare funzione `upload_to_post_image(instance, filename)` che genera path tipo `uploads/<blog>/post-<id>/<filename>`
- [ ] Aggiornare il modello `Post` (o modello immagini) per usare `ImageField`/`FileField` con upload personalizzato
- [ ] Migrare il database se necessario

### 4. Serializzazione e API
- [ ] Aggiornare serializer per includere URL assoluti delle immagini
- [ ] Assicurarsi che l’API restituisca i link Cloudinary già pronti per Markdown

### 5. Markdown e compatibilità Jekyll
- [ ] Aggiornare la logica di generazione del campo `body_markdown` per inserire solo link Markdown con URL Cloudinary
- [ ] Verificare che nessun link sia relativo o HTML

### 6. Test e validazione
- [ ] Caricare immagini da admin/API e verificare che siano accessibili via URL pubblico
- [ ] Generare un post di esempio e controllare la compatibilità con Jekyll
- [ ] Testare multi-blog: immagini di blog diversi non si mischiano

### 7. Documentazione
- [ ] Aggiornare la documentazione per sviluppatori e redattori
- [ ] Esempi di uso e best practice

---

## Extra (opzionale)
- [ ] Script di migrazione immagini esistenti su Cloudinary
- [ ] Supporto a thumbnail/ottimizzazione immagini via Cloudinary
- [ ] Validazione automatica dei link immagini nei Markdown

---

> Una volta approvata la roadmap, procederò con l’implementazione step-by-step.
