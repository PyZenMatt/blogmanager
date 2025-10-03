# Issue: Export → Rispettare cartelle cluster/subcluster

## 🎯 Obiettivo

Allineare la pubblicazione al layout su GitHub Pages con routing gerarchico basato su front-matter:

- **Solo cluster** → `_posts/<cluster>/YYYY-MM-DD-<slug>.md`
- **Cluster + subcluster** → `_posts/<cluster>/<subcluster>/YYYY-MM-DD-<slug>.md`

## 📋 Checklist Tecnica

- [ ] **1. Sorgente**: Validazione front-matter (`categories=[cluster]`, `subcluster?`)
- [ ] **2. Mappatura path**: `_posts/<cluster>/<subcluster?>/YYYY-MM-DD-<slug>.md`
- [ ] **3. Move atomico**: Su cambio cluster/subcluster con rimozione vecchio file
- [ ] **4. Gestione collisioni**: Strategia configurabile `fail` o suffisso incrementale
- [ ] **5. Dry-run**: Modalità simulazione con log dettagliati
- [ ] **6. Test coverage**: 4 casi principali (vedi sotto)
- [ ] **7. Rollback**: Gestione errori I/O con ripristino stato precedente

## 🗂️ Regole di Mapping

### Input da Front-Matter
```yaml
categories: [django]        # cluster = categories[0] (obbligatorio)
subcluster: tutorials       # subcluster (opzionale)
date: 2024-01-15           # per filename (fallback: created_at)
```

### Output Path Logic
```
cluster = categories[0]
subcluster = frontmatter.subcluster

dest_dir:
  - con subcluster: _posts/{cluster}/{subcluster}
  - senza subcluster: _posts/{cluster}

filename: {YYYY-MM-DD}-{post-slug}.md
```

### Esempi
- `categories: [django]` → `_posts/django/2024-01-15-my-post.md`
- `categories: [django], subcluster: tutorials` → `_posts/django/tutorials/2024-01-15-my-post.md`

## 🔄 Gestione Cambiamenti

### Move Automatico
Quando `cluster` o `subcluster` cambiano tra versioni:
1. Calcola nuovo `dest_path`
2. Se diverso da `last_export_path`: esegui move atomico
3. Rimuovi vecchio file
4. Aggiorna metadati post (`last_export_path`)

### Strategia Collisioni
Se `dest_file` già esistente:
- **Policy `fail`**: Blocca export con errore
- **Policy `increment`**: Suffisso `-1`, `-2`, etc.
- Log WARNING sempre

## 📊 Logging Dettagliato

### INFO Level
```
[export][routing] post_id=123 cluster='django' subcluster='tutorials'
[export][routing] post_id=123 dest_path='_posts/django/tutorials/2024-01-15-my-post.md'
[export][action] post_id=123 action=create|update|move|skip
```

### WARNING Level
```
[export][collision] post_id=123 dest_path exists, applying policy=increment
[export][normalize] post_id=123 slug normalized: 'My Post!' → 'my-post'
```

### ERROR Level
```
[export][io] post_id=123 failed to write: permission denied
[export][path] post_id=123 dest_dir not writable: /path/to/_posts/cluster
```

## 🧪 Dry-Run Mode

### Funzionalità
- Simula tutte le operazioni senza scrivere files
- Mostra path mappings e azioni da eseguire
- Identifica collisioni e problemi prima del rollout
- **Obbligatoria** prima di deploy in produzione

### Output Esempio
```
[DRY-RUN] post_id=123 action=move
  From: _posts/old-cluster/2024-01-15-my-post.md
  To:   _posts/django/tutorials/2024-01-15-my-post.md

[DRY-RUN] post_id=456 action=create
  Path: _posts/python/2024-01-16-new-post.md

[DRY-RUN] post_id=789 collision detected
  Path: _posts/django/2024-01-15-existing.md (exists)
  Policy: increment → _posts/django/2024-01-15-existing-1.md
```

## 🧪 Casi di Test

### Test Case 1: Solo Cluster
```python
# Input FM
categories: [django]

# Expected Output
path: _posts/django/2024-01-15-my-post.md
action: create|update
```

### Test Case 2: Cluster + Subcluster  
```python
# Input FM
categories: [django]
subcluster: tutorials

# Expected Output  
path: _posts/django/tutorials/2024-01-15-my-post.md
action: create|update
```

### Test Case 3: Cambio Subcluster
```python
# Before
last_export_path: _posts/django/basics/2024-01-15-my-post.md

# After FM
categories: [django]
subcluster: advanced

# Expected Actions
1. move: _posts/django/basics/2024-01-15-my-post.md → _posts/django/advanced/2024-01-15-my-post.md
2. update: post.last_export_path = '_posts/django/advanced/2024-01-15-my-post.md'
```

### Test Case 4: Collisione Filename
```python
# Existing file: _posts/django/2024-01-15-tutorial.md
# New post: categories=[django], slug='tutorial', date=2024-01-15

# Policy=increment Expected
path: _posts/django/2024-01-15-tutorial-1.md
warning: collision detected, incremented suffix
```

## ✅ Criteri di Accettazione

### Funzionalità Core
- [ ] **100%** dei post pubblicati nella cartella attesa in base al front-matter
- [ ] **0** post finiscono in `_posts/` directory root (flat)
- [ ] Log mostra mapping completo e azione eseguita per ogni post
- [ ] Dry-run elenca correttamente **tutte** le operazioni without side effects

### Robustezza
- [ ] Move atomico: fallimento non lascia files orfani
- [ ] Rollback su errore I/O ripristina stato precedente
- [ ] Gestione slug non URL-safe con normalizzazione
- [ ] Path length limits rispettati (filesystem constraints)

### Performance
- [ ] Operazioni batch efficienti (non N+1 queries)
- [ ] Move files solo se necessario (path changed)
- [ ] Minimal filesystem I/O per operations di check

## 🔧 Vincoli Tecnici

### Path Safety
- Solo slug URL-safe: `[a-z0-9-]`
- Length limits: cluster ≤ 50, subcluster ≤ 50, filename ≤ 255
- No directory traversal: blocca `..`, absolute paths

### Front-Matter Requirements  
- **Prerequisito**: validazione FM già attiva e passante
- `categories=[cluster]` format (no legacy `cluster/subcluster`)
- Slug validation e normalization automatica

### Backward Compatibility
- Non modificare tassonomia esistente
- Graceful handling di post senza `last_export_path`
- Support per migration da flat structure a nested

## 🚀 Implementation Notes

### Configuration
```python
# settings.py
EXPORT_COLLISION_POLICY = 'increment'  # or 'fail'
EXPORT_DRY_RUN = False  # safety default
```

### API Extension
```python
# Management command
python manage.py export_posts --dry-run --site=mysite
python manage.py export_posts --collision=fail --verbose
```

### Monitoring
- Export success/failure metrics
- Path collision frequency tracking  
- Performance timing per operation type