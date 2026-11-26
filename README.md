# Wanted Guild Manager

Create and track sign ups for Wanted Guild PvX events in Throne and Liberty.

This is a prototype. The plan and its reasons are in [docs/decisions](docs/decisions).

## Requirements

- [uv](https://docs.astral.sh/uv/) for Python packages
- [invoke](https://www.pyinvoke.org/) for tasks
- [git-cliff](https://git-cliff.org/) for the changelog
- Node.js 24 (see `.nvmrc`) for the site

## Setup

```bash
uv sync
npm ci
```

## The backend

A Litestar app served by Granian (ADR 0010). It follows the Litestar agent
skills in `.claude/skills/`: the app is always built by `create_app()`.

```bash
uv run litestar --app wgm.app:create_app run   # http://127.0.0.1:8000/ping
uv run pytest                                  # tests with the 100% coverage gate
uv run ruff check && uv run ruff format --check && uv run mypy
```

## The site (parked)

```bash
npm run dev     # local dev server
npm run check   # format check, tests with the 100% coverage gate, build
```

The site is plain HTML, CSS and JavaScript (ADR 0002). Event and sign-up rules
live in `src/events.js`, saving in `src/storage.js`, page building in
`src/render.js`, and `src/app.js` wires them to the page.

## Commits and releases

Commits follow [Conventional Commits](https://www.conventionalcommits.org/),
for example `feat(signup): block sign ups when an event is full`.
`git-cliff` builds `CHANGELOG.md` from them when we release.
