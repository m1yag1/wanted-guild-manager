# Keep separate staging and production environments

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

We want to try changes somewhere safe before the guild manager or guild members see them, and later promote a known version to production. The app will have about 5 users, so cost and simplicity matter more than isolation.

## Decision

* Staging and production share the one droplet from ADR 0005. Each is its own nginx site with its own hostname (ADR 0006) and its own release folder.
* For now only staging exists. Production is added as a second site on the same droplet when the guild is ready to use it.
* `--env` on deploy tasks defaults to staging. Production will only happen when `--env production` is typed.
* Production will receive a version (a git tag, see ADR 0008) that has already run on staging.

## Consequences

### Positive

* One small droplet, so the cost stays at one droplet.
* Mistakes land on staging by default.

### Negative

* A bad provisioning run or a droplet outage affects both environments.
* Teardown removes both environments at once.

## Considered Alternatives

* One droplet per environment: better isolation, but double the cost and more to manage for an app with about 5 users.
* Production only: simplest, but no safe place to try changes.
