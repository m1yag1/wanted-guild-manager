# Create and tear down droplets on demand

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

The guild manager needs a link to try the prototype. A droplet costs money while it runs and is only needed during feedback sessions. Setting one up by hand, as in do-jupyterhub, takes several manual steps.

## Decision

Droplets are created and torn down on demand with invoke tasks:

* `inv droplet.up --env <env>` creates the droplet with `doctl` (Ubuntu 24.04, `s-1vcpu-1gb`, `sfo3`), writes its Ansible inventory from the new IP, provisions it with Ansible, deploys the site and prints the link. Each step can also run alone.
* `inv droplet.down --env <env>` deletes the droplet after the environment name is typed to confirm, and removes its inventory.
* `inv droplet.status` lists this project's droplets.
* Every droplet is tagged `wgm` and `wgm-<env>`. Teardown only deletes a droplet with both tags and the expected name.
* Provisioning follows do-jupyterhub (Ansible and nginx templates), hardened: a `deploy` user, no root or password SSH login, and a firewall that allows only ports 22, 80 and 443.
* The DigitalOcean token stays in `doctl auth init`, never in the repo.

## Consequences

### Positive

* A working site in one command and no cost when it is down.
* Servers are rebuilt from code every time, so nothing drifts.
* Other droplets on the account, such as JupyterHub, are never touched.

### Negative

* A new droplet gets a new IP, so the link changes each time (see ADR 0006).
* Requires `doctl` installed and authenticated on the machine running the tasks.

## Considered Alternatives

* A long-lived droplet set up by hand: no changing link, but costs money all the time and drifts.
* Terraform: strong for larger setups, but more than one droplet needs.
* DigitalOcean App Platform static sites: no server to manage, but moves away from the droplet and Ansible setup that later phases need.

## More Information

Based on /Users/blackbird/Projects/01_personal/do-jupyterhub.
