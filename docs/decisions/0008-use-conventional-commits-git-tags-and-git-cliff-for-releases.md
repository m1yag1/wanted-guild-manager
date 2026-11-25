# Use Conventional Commits, git tags and git-cliff for releases

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

We want versioning tracked from the start and a changelog at each release, without hand-writing either.

## Decision

* Every commit follows Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:` and so on, with an optional scope).
* The git tag (`vX.Y.Z`) is the only source of the version. The site build reads it with `git describe` and shows it in the footer and in `/version.json`.
* `inv release` runs `git cliff --bump` to choose the next version from the commits, writes `CHANGELOG.md`, commits it as `chore(release): prepare for vX.Y.Z` and tags the commit.
* `cliff.toml` follows the dark-madr setup: Keep a Changelog format, commits grouped as Added, Fixed, Documentation and so on.
* The code stays in a local repository until a remote is needed.

## Consequences

### Positive

* Changelogs and version numbers come from history, with no manual bookkeeping.
* Every deployed site can say exactly which version it runs.

### Negative

* Commit messages must follow the format, or they land in the changelog badly.

## Considered Alternatives

* Version in `package.json` or `pyproject.toml`: a second place to keep in sync with tags.
* Hand-written changelog: easy to forget.

## More Information

* https://www.conventionalcommits.org
* https://git-cliff.org
