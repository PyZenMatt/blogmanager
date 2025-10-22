# Setup: GitHub Workflow per blogmanager-previews

⚠️ **IMPORTANTE**: Il workflow `.github/workflows/pr-preview.yml` deve essere aggiunto manualmente su GitHub perché il token corrente non ha lo scope `workflow`.

## Opzione 1: Aggiungere via GitHub UI

1. Vai su https://github.com/PyZenMatt/blogmanager-previews
2. Crea la directory `.github/workflows/`
3. Crea il file `pr-preview.yml` con il contenuto da:
   ```
   /home/teo/Project/blogmanager/blog_manager/exported_repos/blogmanager-previews/.github/workflows/pr-preview.yml
   ```

## Opzione 2: Aggiornare Token con scope workflow

1. Vai su https://github.com/settings/tokens
2. Genera nuovo token con scopes:
   - `repo` (full control)
   - `workflow` (aggiornare workflow files)
3. Aggiorna `GITHUB_TOKEN` in `.env`
4. Riprova il push:
   ```bash
   cd exported_repos/blogmanager-previews
   git push origin main
   ```

## Workflow File Location

Il file è già pronto in:
```
/home/teo/Project/blogmanager/blog_manager/exported_repos/blogmanager-previews/.github/workflows/pr-preview.yml
```

## Verifica Post-Setup

Dopo aver aggiunto il workflow, crea una PR di test:
```bash
cd exported_repos/blogmanager-previews
git checkout -b test-workflow
echo "test" > sites/messymindit/_posts/test.md
git add sites/messymindit/_posts/test.md
git commit -m "Test workflow"
git push origin test-workflow
# Apri PR su GitHub
```

Il workflow dovrebbe:
1. Detectare `messymindit` come changed site
2. Buildare Jekyll per messymindit
3. Deployare su `public/messymindit/post/{PR}/`
4. Commentare la PR con URL preview
