# Create and tear down droplets on demand

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

The guild manager needs a link to try the prototype. A droplet costs money while it runs and is only needed during feedback sessions. Setting one up by hand takes several manual steps.

## Decision

Droplets are created and torn down on demand with invoke tasks:

* `inv droplet.up` creates the project's one droplet, named `wgm`, with `doctl` (Ubuntu 24.04, `s-1vcpu-1gb`, `sfo3`), writes the Ansible inventory from its IP, provisions it with Ansible, deploys the site and prints the link. Each step can also run alone.
* `inv droplet.down` deletes the droplet after its name is typed to confirm, and removes the inventory.
* `inv droplet.status` shows the droplet, its IP and its link.
* The droplet is tagged `wgm`. Teardown only deletes a droplet with that tag and that name.
* Provisioning uses Ansible and nginx templates, hardened with a `deploy` user, no root or password SSH login, and a firewall that allows only ports 22, 80 and 443.
* The DigitalOcean token stays in `doctl auth init`, never in the repo.

## Consequences

### Positive

* A working site in one command and no cost when it is down.
* Servers are rebuilt from code every time, so nothing drifts.
* Other droplets on the account are never touched.

### Negative

* A new droplet gets a new IP, so the link changes each time (see ADR 0006).
* Requires `doctl` installed and authenticated on the machine running the tasks.

## Considered Alternatives

* A long-lived droplet set up by hand: no changing link, but costs money all the time and drifts.
* Terraform: strong for larger setups, but more than one droplet needs.
* DigitalOcean App Platform static sites: no server to manage, but moves away from the droplet and Ansible setup that later phases need.
