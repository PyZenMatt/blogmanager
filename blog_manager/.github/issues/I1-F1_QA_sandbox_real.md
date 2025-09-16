Title: I1-F1 — QA sandbox: verify delete_file on real repo

Description:

Run manual verification of `GitHubClient.delete_file` against a real sandbox repo.

Steps:

- Create or use a sandbox repo and ensure the token has `contents: write` permissions.
- Create a file at `path/to/file.md` on `main`.
- Call `delete_file(owner, repo, path, branch='main', message='test delete')`.
- Verify: first call returns `status: deleted` and `commit_sha` populated; commit visible on GitHub.
- Call again same path; verify it returns `status: already_absent` and no exception.
- Record evidence: commit URL and screenshots in `docs/EVIDENCE_LOG.md`.

DoD:

- Evidence (commit URL + screenshot) added to `docs/EVIDENCE_LOG.md`.
- No errors on repeated delete; idempotent behaviour confirmed.
