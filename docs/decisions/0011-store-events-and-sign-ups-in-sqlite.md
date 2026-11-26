# Store events and sign ups in SQLite

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

With a bot, sign ups are shared by the whole guild, so they can no longer live in each browser (ADR 0002). The app has about 5 managers and a few dozen members at most.

## Decision

Store events and sign ups in a single SQLite file on the droplet, through Advanced Alchemy (SQLAlchemy for Litestar) with the aiosqlite driver, as in byob-backend. SQLAlchemy keeps the database swappable: moving to PostgreSQL or another backend is a connection change.

* A few tables (events, sign ups, server settings), with migrations from Advanced Alchemy's Alembic integration.
* Tests use a temporary database.
* Each environment has its own file, kept outside the release folder so deploys keep the data. A copy is taken before each deploy.

## Consequences

### Positive

* No database server to run or pay for.
* Backups are copying one file.

### Negative

* One process writes at a time, which is fine at this size.
* Moving to PostgreSQL later is mostly a connection change, though data still needs copying.

## Considered Alternatives

* PostgreSQL (managed or on the droplet): more than this size needs.
* A JSON file: simple, but easy to corrupt if two writes overlap.
* Plain `sqlite3`: fewer dependencies, but blocking calls inside an async server and hand-written migrations.
