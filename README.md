# Wanted Guild Manager

Create and track sign ups for Wanted Guild PvX events in Throne and Liberty,
from Discord slash commands.

The plan and its reasons are in [docs/decisions](docs/decisions).

## Requirements

- [uv](https://docs.astral.sh/uv/) for Python packages
- [invoke](https://www.pyinvoke.org/) for tasks
- [git-cliff](https://git-cliff.org/) for the changelog

## Setup

```bash
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
```

## The backend

A Litestar app served by Granian (ADR 0010). It follows the Litestar agent
skills in `.claude/skills/`, and the app is always built by `create_app()`.

```bash
uv run litestar --app wgm.server.app:create_app run   # http://127.0.0.1:8000/ping
uv run pytest                                         # tests with the 100% coverage gate
uv run pre-commit run --all-files                     # ruff, mypy and file checks
```

## Layout

```text
src/wgm/
  server/          create_app() and plugins
  domain/<area>/   controllers, schemas and services for one area
tests/unit/        mirrors src/wgm
```

## Commits and releases

Commits follow [Conventional Commits](https://www.conventionalcommits.org/),
for example `feat(signup): block sign ups when an event is full`. A hook checks
each message. `git-cliff` builds `CHANGELOG.md` from them when we release.

The earlier static web prototype is kept under the git tag `web-prototype`.
