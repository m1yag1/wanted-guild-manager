# Build the prototype as a static site with browser storage

* Status: accepted
* Date: 2026-11-25

## Context and Problem Statement

Guild managers need a way to create PvX events and collect sign ups. Before building anything larger we want the guild manager's feedback on the screens and the flow. What is the smallest thing that lets them try it?

## Decision

Build the prototype as a static site: plain HTML, CSS and JavaScript, built with Vite, with no server and no login.

Events and sign ups are saved in the browser's `localStorage`, behind two small functions (`loadEvents`, `saveEvents`). The event and sign-up rules live in plain functions with no DOM or storage code, so they can move to a server later unchanged.

## Consequences

### Positive

* Nothing to run but a web server, so it deploys as a folder of files.
* Fast to build and easy to test.
* The guild manager can try it on a phone or a desktop.

### Negative

* Each browser keeps its own data. Members cannot see each other's sign ups, so the guild cannot use it for real yet.
* Anyone can create or delete events. Fine for a prototype only.

## Considered Alternatives

* Start with a backend (for example FastAPI and SQLite) and Discord login: shared data from day one, but much more to build before getting any feedback.
* A front-end framework (React, Vue): more tooling than a two-screen prototype needs.

## More Information

Revisit after the guild manager's feedback. A shared backend will supersede the storage part of this decision.
