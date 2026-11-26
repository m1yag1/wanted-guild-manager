# Serve HTTPS with sslip.io hostnames and certbot

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

The site must always be served over HTTPS, with certificates managed on the server. There is no domain yet.

## Decision

Until there is a domain, each droplet is reached through an `sslip.io` hostname built from its IP, for example `143-198-10-20.sslip.io` for production and `staging.143-198-10-20.sslip.io` for staging. These resolve to the IP with no DNS setup.

The provisioning playbook installs certbot, gets a Let's Encrypt certificate for each hostname with the webroot method (so certbot never edits the nginx config Ansible manages), and relies on certbot's renewal timer, which reloads nginx after each renewal. nginx redirects every HTTP request to HTTPS and sends an HSTS header.

The hostname is one inventory variable, `domain_name`, so a real domain replaces it without other changes.

## Consequences

### Positive

* HTTPS from the first deploy, with automatic renewal.
* No domain purchase or DNS work needed to start.

### Negative

* sslip.io is a free shared service, so it can have outages or hit Let's Encrypt rate limits.
* The hostname changes when the droplet's IP changes.

## Considered Alternatives

* Paths on the bare IP (`/` and `/staging/`): needs the site built for a sub-path and a certificate for an IP.
* A Let's Encrypt certificate for the IP itself: lasts only days, so renewal must run very often, and it needs an ACME client with IP support.
* Buy a domain now: the best long-term option, about $10 to $15 a year, and easy to switch to later.

## More Information

* https://sslip.io
* https://certbot.eff.org
