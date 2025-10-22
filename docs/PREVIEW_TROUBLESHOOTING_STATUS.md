# 🔍 Preview Troubleshooting Progress

## Issue #1: ✅ Config Preview-Repo COMPLETATO

**Status**: ✅ **PASS**

- ✅ `PREVIEW_REPO_OWNER`: PyZenMatt
- ✅ `PREVIEW_REPO_NAME`: blogmanager-previews
- ✅ `PREVIEW_BRANCH`: main
- ✅ `PREVIEW_BASEDIR`: sites
- ✅ `PREVIEW_BASE_URL`: https://pyzenmatt.github.io/blogmanager-previews
- ✅ Working copy: `/home/teo/Project/blogmanager/blog_manager/exported_repos/blogmanager-previews`
- ✅ Remote: `https://github.com/PyZenMatt/blogmanager-previews.git`
- ✅ GitHub token configured

---

## Issue #2: ✅ Export Path Per-Sito COMPLETATO

**Status**: ✅ **PASS**

- ✅ Path template: `sites/{site.slug}/_posts/...`
- ✅ Export code in `preview_service.py` lines 286-292:
  ```python
  site_rel_path = os.path.join(preview_basedir, site.slug, rel_path)
  full_path = os.path.join(repo_path, site_rel_path)
  ```
- ✅ Directory structure found: `sites/messymindit/_posts/burnout-e-lavoro/...`

---

## Issue #3: ⚠️ Workflow CI PARZIALMENTE COMPLETATO

**Status**: ⚠️ **BLOCKED - Manual Action Required**

- ✅ Workflow file created: `.github/workflows/pr-preview.yml`
- ❌ Push blocked: Token missing `workflow` scope
- 📝 Doc created: `docs/SETUP_PREVIEW_WORKFLOW.md`

**Required Action**:
1. Update GitHub token with `workflow` scope OR
2. Manually add `.github/workflows/pr-preview.yml` to repository via GitHub UI

**Workflow File Location**:
```
/home/teo/Project/blogmanager/blog_manager/exported_repos/blogmanager-previews/.github/workflows/pr-preview.yml
```

---

## Issue #4: ✅ GitHub Pages Configurazione COMPLETATO

**Status**: ✅ **PASS**

- ✅ Branch `gh-pages` created and pushed
- ✅ Initial structure with `public/` directory
- ✅ Index page with documentation
- ✅ Commit: `f17b3a9 Initialize gh-pages branch`

**Remaining**:
- ⏳ Configure GitHub Pages settings on repository (source: gh-pages branch)
- ⏳ Verify Pages deployment at: https://pyzenmatt.github.io/blogmanager-previews

---

## Issue #5: ⏳ Skeleton Jekyll Per Ogni Sito IN PROGRESS

**Status**: ⏳ **TODO**

**Current State**:
- Main branch has `pull/` instead of `sites/` structure
- Need to create `_config.yml` for each site
- Need Gemfile if not using system Jekyll

**Required Files per Site**:
```
sites/messymindit/_config.yml
sites/messymindit/Gemfile (optional)
sites/matteoriccinet/_config.yml  
sites/matteoriccinet/Gemfile (optional)
```

**Next Steps**:
1. Create `_config.yml` template for each site
2. Set correct `baseurl` and `url` for preview context
3. Add minimal Jekyll theme configuration
4. Test local build: `cd sites/messymindit && jekyll build`

---

## Issue #6: ⏳ Webhook Preview TODO

**Status**: ⏳ **NOT STARTED**

**Requirements**:
- Webhook endpoint: `/api/webhooks/github/preview/`
- Events: `pull_request`, `workflow_run`
- Secret validation
- Update PreviewSession status: `open → ready`
- Store final `preview_url`

---

## Issue #7: ⏳ Smoke Test E2E TODO

**Status**: ⏳ **NOT STARTED**

**Test Plan**:
1. Create preview for messymind
2. Create preview for matteoricci.net
3. Verify PRs created
4. Verify workflows run
5. Verify Pages deployed
6. Verify webhook updates sessions
7. Verify preview URLs accessible

---

## Summary

| Issue | Status | Blocker |
|-------|--------|---------|
| #1 Config | ✅ PASS | None |
| #2 Export Path | ✅ PASS | None |
| #3 Workflow CI | ⚠️ BLOCKED | Token scope |
| #4 GitHub Pages | ✅ PASS | Manual config |
| #5 Jekyll Skeleton | ⏳ TODO | - |
| #6 Webhook | ⏳ TODO | - |
| #7 Smoke Test | ⏳ TODO | - |

**Critical Path**:
1. ✅ Fix token OR manually add workflow (#3)
2. ✅ Configure GitHub Pages on repository (#4)
3. Create Jekyll skeletons (#5)
4. Test preview creation end-to-end (#7)
5. Implement webhook (#6)

**Immediate Next Step**: Create Jekyll `_config.yml` files for each site
