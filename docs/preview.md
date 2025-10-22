# PR Preview (Pages) — Overview

This document describes how BlogManager can orchestrate preview builds for Jekyll sites via GitHub Pages.

Goals
- Each PR created from BlogManager should produce a preview under `/previews/pr-<NUM>/` on the same Pages site.
- Previews are identical to production (same layout/assets) but are noindex and have analytics disabled.
- BlogManager shows preview URL and preview status in the post UI and saves logs.

Setup summary
1. Enable GitHub Pages for the Jekyll repo (branch `gh-pages` or `main` + folder).
2. Add deploy capability for BlogManager: either a Deploy Key with write access to `gh-pages`, or a Fine-grained PAT stored in BlogManager secrets.
3. Add the GitHub Actions workflow `/.github/workflows/pr-preview-pages.yml` (this repo contains an example template).
4. Ensure `_config.yml` of the Jekyll site supports override via `--config _config.yml,_preview.yml` and that templates check `site.preview` to disable analytics and add `noindex`.

How it works (high-level)
- BlogManager creates a PR on the Jekyll repo (via `GitHubClient.create_pull_request`) or updates an existing PR branch.
- The Actions workflow triggers on PR events, builds Jekyll with drafts/future, overriding `baseurl` to `/previews/pr-<NUM>/` and pushes files into `gh-pages/previews/pr-<NUM>/`.
- Action comments the PR with the preview URL. BlogManager reads the PR comment (or receives webhook) and displays the preview URL & status.
- When PR is closed, another workflow (not provided here) deletes `previews/pr-<NUM>/` and posts a comment in the PR that the preview was removed.

Security notes
- Prefer `GITHUB_TOKEN` with `contents: write` and `issues: write` for Actions. For server-side operations from BlogManager, prefer a fine-grained PAT with minimal scopes.
- Do not expose tokens in logs.

Operational checklist
- Test on a staging repo first.
- Implement `_preview.yml` to override `url`/`baseurl`.
- Add template gating for analytics using `{% unless site.preview %}...{% endunless %}`.

