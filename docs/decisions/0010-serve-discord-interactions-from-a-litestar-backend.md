# Serve Discord interactions from a Litestar backend

* Status: accepted
* Date: 2026-11-26

## Context and Problem Statement

A Discord app can receive slash commands over a gateway connection it keeps open, or as HTTPS requests Discord sends to a public endpoint. We want a base that holds up as features grow and can later serve a web page or an API too.

## Decision

a Litestar backend receives Discord interactions over HTTPS.

* Discord sends every slash command, button press and autocomplete request to `POST /discord/interactions`. The server checks the Ed25519 signature with the application's public key and rejects anything unsigned.
* Litestar with type hints, laid out as `src/wgm/server` (app factory, plugins) and `src/wgm/domain/<area>` (controllers, schemas, services) per the Litestar skill, always built by a `create_app()` factory, following the Litestar agent skills in `.claude/skills/`. Served by Granian through `litestar-granian`'s `GranianPlugin` and `litestar run`, as a systemd service on the droplet, behind nginx with certbot (ADR 0006).
* Route handlers stay thin and call plain, typed functions for the rules. Tests use pytest and Litestar's test client at 100% (ADR 0003), with a generated test key for signatures.
* Unit tests run fully offline: incoming interactions are realistic payloads signed with a test key; outgoing Discord calls use `httpx` and are mocked with `respx` using recorded responses in `tests/fixtures/discord/`. Manual tries happen on the staging droplet.
* Structured JSON logs (Litestar's structlog plugin) go to journald. `inv logs` and `inv status` show logs, service state, version and certificate expiry without logging in by hand. Tokens and message contents are never logged.
* Commands answer within Discord's 3-second limit. Anything slower is deferred and finished with a follow-up message.
* `inv discord.register-commands` sends the `/wgm` definitions to Discord. `inv droplet.up` sets the application's interactions endpoint URL through Discord's API after each deploy, because a new droplet gets a new sslip.io hostname.
* Reminders run as a background task in the server, posting through Discord's REST API.
* Staging and production are two Discord applications, each pointing at its own service and hostname on the shared droplet (ADR 0007).
* Secrets (bot token, public key) are read from the environment: a gitignored `.env` locally, a root-only file on the droplet.

## Consequences

### Positive

* An ordinary web server: easy to test, and ready to serve `/api` routes or a web page later.
* No long-lived connection to keep alive. Each request stands alone.

### Negative

* Needs a public HTTPS endpoint, so a laptop cannot receive commands without a tunnel. Manual tries happen on the staging droplet.
* The endpoint URL must be updated whenever the droplet's IP changes.
* The server never sees gateway events such as "bot joined a server", so role setup relies on Discord's webhook events, `/wgm setup` or the command line.

## Considered Alternatives

* Gateway bot with discord.py: no public URL needed and simple reminders, but a long-running connection and no natural place for a web API.
* Serverless endpoint (Cloudflare Workers, DigitalOcean Functions): no server, but a new platform and storage, and a move away from Python and the droplet.
* FastAPI with uvicorn: equally suitable; Litestar and Granian were chosen to match Mike's other projects.

## More Information

* https://docs.litestar.dev
* https://github.com/emmett-framework/granian
* https://discord.com/developers/docs/interactions/overview
