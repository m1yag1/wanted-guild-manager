# Use uv for Python packages and invoke as the task runner

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

We need one simple way to install tools and run every task (tests, build, deploy, droplet management) on a laptop now and in CI later.

## Decision

* uv manages Python: `pyproject.toml`, `uv.lock` and the Python version. Python tools such as Ansible and dark-madr come in as dev dependencies.
* invoke is the single task runner. Every step is an invoke task (`inv check`, `inv deploy`, `inv droplet.up`), and CI will call the same tasks.
* npm stays only for the site's JavaScript tooling, called from invoke tasks.
* No tox for now.

## Consequences

### Positive

* One command list to learn: `inv --list`.
* CI and laptops run the same thing, so "works on my machine" problems shrink.
* uv is fast and pins exact versions.

### Negative

* Two package managers (uv and npm), because the site is JavaScript.
* invoke must be installed (globally, or through `uv run inv`).

## Considered Alternatives

* tox: useful for testing against several Python versions, but uv already creates environments and invoke already runs steps. Add tox with the `tox-uv` plugin if we ever need a version matrix.
* Make: available everywhere, but harder to write and test than Python tasks.
* Plain shell scripts, as in do-jupyterhub: simple, but harder to test to 100%.

## More Information

* https://docs.astral.sh/uv/
* https://www.pyinvoke.org/
