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

Baseline backend test suite:

```bash
cd backend
uv run pytest -q tests
```

For security checks locally (recommended before PR):

```bash
# secret scanning
# (if installed) gitleaks detect --source . --no-git

# frontend dependency vulnerabilities
cd frontend && pnpm audit --prod --audit-level high && cd ..

# backend dependency vulnerabilities (raw report)
cd backend && uv sync --all-packages --frozen && uv run --with pip-audit pip-audit -f json -o pip-audit-report.json && cd ..

# enforce repo policy (fails on non-allowlisted packages)
python .github/scripts/check_pip_audit.py
```

### Dependency security overrides

To keep CI security audits green, the repo defines pnpm workspace overrides in
`pnpm-workspace.yaml` for vulnerable transitive dependencies (currently `sharp`
and `postcss`).

When upgrading Next.js or related frontend dependencies:
- run `pnpm audit --prod --audit-level high`
- verify resolved versions via `pnpm why sharp` and `pnpm why postcss`
- update/remove overrides only when upstream dependencies are fully patched

Backend pip-audit policy uses package-level allowlisting at
`.github/security/pip-audit-allowlist.txt` for temporary exceptions (currently
ML stack packages with compatibility constraints). Keep this list minimal.

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