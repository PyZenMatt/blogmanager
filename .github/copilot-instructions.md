## Purpose
Short, actionable guidance for AI coding agents working on this Django-based backend (Blog Manager).

## Quick architecture summary
- Backend: Django 5 on Python 3.12 (project package: `blog_manager`).
- Apps of interest: `blog/` (posts, sites, sync/export logic), `writer/` (auth/editor UI), `contact/` (contact API).
- Sync/export: the project exports content for Jekyll: see `blog/exporter.py`, `blog/github_client.py` and `reports/` + `exported_repos/` for outputs.
- API routing: primary DRF router in `blog_manager/urls.py` registers `sites` and `posts` (see `PostViewSet`, `SiteViewSet` in `blog.views`). OpenAPI via `drf-spectacular` exposed at `/api/schema/`, `/api/docs/swagger/` and `/api/docs/redoc/`.

## How to run & common commands (examples)
- Create venv and install deps:
  - `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Local dev server (explicit):
  - `export DJANGO_SETTINGS_MODULE=blog_manager.settings.dev`
  - `python manage.py migrate && python manage.py runserver`
- Docker compose (local prod-like):
  - `cp .env.example .env && docker compose up --build`
- Tests & linters:
  - `pytest` (project uses `pytest-django`) and pre-commit hooks (Black/Isort/Flake8) — see `pytest.ini` and CI workflows in `.github/workflows/`.

## Important environment variables and side-effects
- `.env` controls many behaviors. Key vars to check before editing code that touches I/O or external services:
  - `GITHUB_TOKEN` / `GIT_TOKEN`: used by `blog/github_client.py` and exporter for repo operations.
  - `BLOG_REPO_BASE`: local path where exported repos are stored (used across exporter code).
  - `EXPORT_ENABLED`: feature flag for export tasks.
  - `ALLOW_REPO_DELETE`: when `True` the admin action "DB + Repo" may attempt to delete files from the repository — proceed with caution.

## Project-specific patterns & conventions (concrete examples)
- manage.py bootstrap: `manage.py` injects the package dir and sets `ENV_FILE` to the project root `.env` when unset — prefer setting `.env` at repo root instead of changing sys.path hacks.
- Settings selection: if `DJANGO_SETTINGS_MODULE` isn't set, `manage.py` chooses `settings.prod` when `ENVIRONMENT=production` or when `ENV_FILE` ends with `.prod`; otherwise `settings.dev`.
- DRF router usage: look at `blog_manager/urls.py` for how viewsets are exposed. Example: `router.register(r"sites", SiteViewSet, basename="site")`.
- Health endpoint: `/api/health/` returns a small JSON indicating liveness; useful for smoke tests.

## Where to look when changing sync/export behavior
- `blog/exporter.py`: orchestration for export jobs.
- `blog/github_client.py`: interactions with GitHub and PyGithub usage.
- `reports/` and `exported_repos/`: produced artifacts and JSON sync reports — use these for debugging export flows.

## Tests, CI and formatting
- Tests: `pytest` (uses `pytest-django`). Run subset: `pytest blog/tests -q`.
- CI: workflows perform Black/Isort/Flake8, migrations and tests. Respect the code style in the repository to avoid CI failures.
- Pre-commit: `pre-commit install` and `pre-commit run --all-files` are expected in local dev.

## Debugging tips
- If imports fail when running `manage.py`, check that the project root `.env` exists or set `DJANGO_SETTINGS_MODULE` explicitly (see top of `manage.py`).
- For issues with external services, verify `GITHUB_TOKEN`, `CLOUDINARY_URL`, and `DATABASE` vars in `.env`.

## Quick pointers for AI agents
- Prefer minimal, focused edits. When changing API shapes, update `serializers.py`, `views.py`, and the OpenAPI schema (drf-spectacular) and add/adjust tests in `blog/tests/`.
- When creating migrations, run `python manage.py makemigrations` and include the migration files in the commit.
- Avoid touching export/delete admin actions unless `ALLOW_REPO_DELETE` and `GITHUB_TOKEN` are intentionally set for integration testing.

## Files to reference
- Routing & entry: `blog_manager/urls.py`, `blog_manager/wsgi.py`, `blog_manager/asgi.py`, `manage.py`.
- App logic: `blog/` (models, views, serializers, exporter, github_client), `writer/` (UI & auth), `contact/`.
- Env example: `.env.example` and `README.md` for onboarding steps.

If anything here is unclear or you'd like more detail (examples of common refactors, test targets, or CI failure patterns), tell me which area to expand.
