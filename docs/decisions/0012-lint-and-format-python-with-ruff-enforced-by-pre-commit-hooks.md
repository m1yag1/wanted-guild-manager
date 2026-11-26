# Lint and format Python with ruff, enforced by pre-commit hooks

* Status: accepted
* Date: 2026-11-26

## Context and Problem Statement

Python code must be formatted and checked the same way on every commit, without relying on memory. black and pre-commit hooks were requested. The Litestar styleguide skill says to use `ruff format` and never combine it with black.

## Decision

* `ruff check --fix` lints and `ruff format` formats Python. `ruff format` produces black's style, so black itself is not added.
* pre-commit runs on every commit: file hygiene checks, ruff, and mypy (strict, through `uv run`).
* The commit-msg hook enforces Conventional Commits (ADR 0008).
* The pre-push hook runs pytest with the 100% coverage gate (ADR 0003).
* Hooks that need project tools run through `uv run` so their versions match `uv.lock`.

## Consequences

### Positive

* One tool for linting and formatting, and it is fast.
* Bad formatting, type errors, untested code and unconventional commit messages are caught before they land.

### Negative

* Contributors must run `pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push` once.
* The pre-push hook takes a few seconds.

## Considered Alternatives

* black plus ruff for linting: works, but two tools for overlapping jobs, and ruff's formatter matches black's output.
* prek instead of the pre-commit CLI: faster, reads the same config, and can replace it later without changes.
