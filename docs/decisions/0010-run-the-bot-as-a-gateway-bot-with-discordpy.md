# Run the bot as a gateway bot with discord.py

* Status: proposed
* Date: 2026-11-25

## Context and Problem Statement

A Discord bot can receive slash commands in two ways: over a gateway connection it keeps open, or as HTTPS requests Discord sends to a public endpoint. We want the simplest setup that the manager can try soon and that later runs on the droplet (ADR 0005).

## Decision

Proposed: run the bot as a gateway bot written in Python with discord.py.

* Command handlers are thin. They call plain, typed functions for the rules, which are tested with pytest at 100% (ADR 0003).
* The first prototype runs on Mike's machine against a test Discord server.
* Later it runs on the droplet as a systemd service, deployed by invoke and Ansible.
* The bot token is read from the environment: a gitignored `.env` file locally, a root-only file on the droplet. It is never committed.

## Consequences

### Positive

* Only outbound connections, so no public URL, certificate or domain is needed for the bot.
* Buttons, updating posts and timed reminders are straightforward.
* Python with type hints, matching the task tooling.

### Negative

* One process must stay running. If it stops, commands fail until it restarts (systemd restarts it on the droplet).
* discord.py event handlers are harder to unit test, which is why logic stays outside them.

## Considered Alternatives

* HTTP interactions endpoint (for example FastAPI on the droplet): no always-on connection, but needs a stable public HTTPS URL, must answer within 3 seconds, and needs a separate scheduler for reminders. The sslip.io hostname changes with each new droplet.
* Serverless endpoint (Cloudflare Workers, DigitalOcean Functions): no server, but a new platform and storage, and a move away from Python.

## More Information

* https://discordpy.readthedocs.io
