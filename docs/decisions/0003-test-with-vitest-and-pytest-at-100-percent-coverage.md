# Test with Vitest and pytest at 100 percent coverage

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

We want tests from the start and quick, safe changes while iterating with the guild manager. The project has JavaScript (the site) and Python (the tasks that manage droplets).

## Decision

* JavaScript is tested with Vitest using jsdom, so tests can drive the real page markup.
* Python is tested with pytest and pytest-cov.
* Both require 100% line and branch coverage. `inv check` fails if either drops below it.
* Code is written to be easy to test: logic in plain functions, side effects (DOM, storage, `doctl`, `ssh`) at the edges and passed in where practical.

## Consequences

### Positive

* Every change is covered, so refactoring during feedback rounds is safe.
* The coverage gate catches untested branches early, while the code is still small.

### Negative

* 100% can push toward low-value tests for trivial lines. We keep such code small rather than excluding it.
* Two test tools to learn, one per language.

## Considered Alternatives

* Node's built-in test runner: no dependency, but weaker DOM testing and coverage tooling than Vitest.
* A lower coverage target such as 90%: less effort, but lets gaps grow quietly.

## More Information

* https://vitest.dev
* https://docs.pytest.org
