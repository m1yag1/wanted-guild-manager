# Keep separate staging and production environments

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

We want to try changes somewhere safe before the guild manager or guild members see them, and to promote a known version to production.

## Decision

* There are two environments, staging and production, each with its own Ansible inventory (`ansible/inventories/staging.yaml`, `ansible/inventories/production.yaml`) and run by the same playbook.
* `--env` defaults to staging. Production only happens when `--env production` is typed.
* Production receives a version (a git tag, see ADR 0008) that has already run on staging.
* To start, each environment is its own small droplet, created and torn down as in ADR 0005.

## Consequences

### Positive

* Mistakes land on staging by default.
* Production always runs a tagged, already-tried version.

### Negative

* Two droplets cost twice as much while both are up.
* Inventories are generated from droplet IPs, so they are not committed.

## Considered Alternatives

* One droplet serving both environments: cheaper, but a bad deploy or provisioning run can affect both.
* Production only: simplest, but no safe place to try changes.
