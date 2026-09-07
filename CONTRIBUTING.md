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