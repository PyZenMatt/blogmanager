# ADR-001: Editorial Workflow Architecture

## Status
Proposed

## Context
This ADR defines the editorial workflow for content creation and publication using Django as the writing platform and Jekyll (GitHub Pages) as the publishing platform, automated via GitHub Actions.

## Decision
- **Writing**: Content is drafted and managed in Django (admin or custom editor).
- **Workflow**: Content follows the states: `Draft → Review → Published`.
- **Publication**: Once content is ready, it is exported (manually or automatically) to a GitHub repository containing the Jekyll site.
- **Automation**: GitHub Actions handle the build and deployment of the Jekyll site to GitHub Pages.
- **Review**: Optionally, publication can require a Pull Request (PR) for review before merging to `main`.

### Roles & Responsibilities
- **Writer**: Creates and edits drafts in Django.
- **Reviewer**: Reviews content before publication (can be enforced via PRs).
- **Publisher**: Approves and merges PRs, triggers publication.

### Fallbacks
- If GitHub Actions fail, manual deployment is possible.
- If review is skipped, direct publish to `main` is allowed (configurable).

## Pros & Cons
### Pros
- Clear separation of writing and publishing.
- Automated, reproducible deployments.
- Version control and review via PRs.
- Easy rollback and audit trail.

### Cons
- Requires integration between Django and Jekyll repo.
- Review process may slow down urgent publications.
- GitHub Actions dependency for automation.

## Workflow Schema
```mermaid
flowchart TD
    A[Draft in Django] --> B[Review]
    B -->|Approved| C[Export to Jekyll Repo]
    C --> D[PR (optional)]
    D -->|Merged| E[GitHub Actions Build]
    E --> F[Published on Pages]
    D -->|Direct Publish| E
```

## Alternatives Considered
- Direct publish from Django to Pages (skips Jekyll repo, less control)
- Manual build/deploy (less automation)

## References
- [GitHub Pages](https://pages.github.com/)
- [Jekyll](https://jekyllrb.com/)
- [GitHub Actions](https://docs.github.com/en/actions)

---
**Link this ADR from the README for visibility.**
