# Contributing to Lang3s

Thanks for your interest in contributing.

## Ground rules

- Be respectful and constructive.
- Keep pull requests focused and reasonably small.
- Discuss major changes in an issue before implementing.

## Development setup

1. Fork and clone the repo.
2. Install dependencies:

```bash
pnpm install
```

3. Frontend env setup:

```bash
cd frontend
cp .env.example .env
cd ..
```

4. Run the stack:

```bash
pnpm dev
```

## Before submitting a PR

Please run checks for the area you changed.

For frontend changes:

```bash
cd frontend
pnpm lint
pnpm tsc --noEmit
pnpm build
```

For backend changes, run relevant lint/tests for touched packages.

For security checks locally (recommended before PR):

```bash
# secret scanning
# (if installed) gitleaks detect --source . --no-git

# frontend dependency vulnerabilities
cd frontend && pnpm audit --prod --audit-level high && cd ..

# backend dependency vulnerabilities
cd backend && uv sync --all-packages --frozen && uv run --with pip-audit pip-audit && cd ..
```

## Good first issues and labels

We use labels to help contributors find appropriate work.

- Start with issues labeled `good first issue` for small, self-contained tasks.
- Use `help wanted` for community-priority work that may be larger.
- Common triage labels include `frontend`, `backend`, `documentation`, `ci`, and `security`.
- Label guidance for maintainers lives at `.github/LABELS.md`.

## Pull request checklist

- [ ] Code builds and passes checks locally
- [ ] Changes are documented (README/docs/comments where appropriate)
- [ ] No secrets or credentials added
- [ ] PR description explains **what** changed and **why**

## Commit guidance

Use clear, descriptive commit messages. Example:

- `feat(frontend): add ontology selector filtering`
- `fix(auth): remove hardcoded debug logging`

## Licensing

By contributing, you agree that your contributions are licensed under the
project license (GPL-3.0-or-later).