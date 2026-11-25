# Wanted Guild Manager

Create and track sign ups for Wanted Guild PvX events in Throne and Liberty.

This is a prototype. The plan and its reasons are in [docs/decisions](docs/decisions).

## Requirements

- [uv](https://docs.astral.sh/uv/) for Python packages
- [invoke](https://www.pyinvoke.org/) for tasks
- [git-cliff](https://git-cliff.org/) for the changelog

## Setup

```bash
uv sync
```

## Commits and releases

Commits follow [Conventional Commits](https://www.conventionalcommits.org/),
for example `feat(signup): block sign ups when an event is full`.
`git-cliff` builds `CHANGELOG.md` from them when we release.
