# Store events and sign ups in SQLite

* Status: proposed
* Date: 2026-11-25

## Context and Problem Statement

With a bot, sign ups are shared by the whole guild, so they can no longer live in each browser (ADR 0002). The app has about 5 managers and a few dozen members at most.

## Decision

Proposed: store events and sign ups in a single SQLite file next to the bot, using Python's built-in `sqlite3` module.

* A small storage module with plain functions (`create_event`, `add_signup` and so on) and a schema created on start.
* Tests use an in-memory database.
* On the droplet the file lives outside the release folder so deploys keep the data. A copy is taken before each deploy.

## Consequences

### Positive

* No database server to run or pay for.
* Backups are copying one file.

### Negative

* One process writes at a time, which is fine at this size.
* Moving to a server database later means a migration.

## Considered Alternatives

* PostgreSQL (managed or on the droplet): more than this size needs.
* A JSON file: simple, but easy to corrupt if two writes overlap.
* An ORM such as SQLAlchemy: more abstraction than a handful of tables needs.
