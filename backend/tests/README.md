# Backend Tests

This directory contains the baseline backend test suite for Lang3s.

## Goals

- Keep tests fast and deterministic
- Favor unit tests for pure logic first
- Avoid external side effects in baseline CI tests

## Conventions

- Test files: `test_*.py`
- Test names: `test_<behavior>`
- One logical concern per test module (e.g., pagination, security, exceptions)

## Scope for baseline tests

✅ Preferred:
- Pure functions / small utility behaviors
- Pydantic schema validation and transformations
- Auth/control-flow logic with mocks/monkeypatch

🚫 Avoid in this folder’s baseline:
- Network calls
- Real DB/Redis usage
- Heavy model loading/inference
- File-system mutation outside temp dirs

## Mocking guidance

- Use `pytest` + `monkeypatch` for:
  - environment variables
  - external service calls
  - expensive or stateful module functions
- Keep mocks local to each test where possible.

## Running tests

From `backend/`:

```bash
uv run pytest -q tests
```

Run a single file:

```bash
uv run pytest -q tests/test_security.py
```

## Adding new tests

When adding a bug fix or behavior change:
1. Add/adjust a failing test first when practical.
2. Implement the fix.
3. Keep test runtime minimal.
4. Prefer asserting behavior, not implementation details.
