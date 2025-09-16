Title: I1-F2 — CI sanity: ensure tests & PyGithub installed

Description:

Make sure CI installs `requirements.txt` (with `PyGithub`) and runs the test suite including the new mock tests for `delete_file`.

Steps:

- Ensure `ci-django.yml` installs `-r requirements.txt` (already present).
- Ensure pytest is installed and tests run.
- If CI matrix excludes certain tests, add necessary paths or test markers.

DoD:

- CI pipeline passes on main with new tests included.
- `pytest` runs and new tests pass in CI.
