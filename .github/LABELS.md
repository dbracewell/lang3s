# Issue Label Guidance

Use labels consistently so contributors can find work quickly.

## Core labels

- `good first issue`
  - Small, self-contained tasks with clear acceptance criteria
  - Suitable for first-time contributors
  - Should include context + pointers to files/functions

- `help wanted`
  - Maintainers want community help
  - May be larger than `good first issue`

- `bug`
  - Incorrect behavior, regressions, or reliability issues

- `enhancement`
  - New feature or improvement to existing behavior

- `documentation`
  - Docs/readme/comments/process updates

- `ci` / `infra`
  - Build pipelines, tooling, docker, orchestration changes

## Optional triage labels

- `frontend`
- `backend`
- `docker`
- `security`
- `blocked`
- `needs reproduction`
- `needs design`

## Recommendations for `good first issue`

Each issue should include:
- Why the task matters
- Exact files likely to change
- A suggested implementation approach
- Definition of done / acceptance checks

Avoid marking as `good first issue` when:
- It spans many subsystems
- It requires deep domain context
- Requirements are still unclear
