# Use Discord slash commands as the main interface

* Status: proposed
* Date: 2026-11-25

## Context and Problem Statement

The guild manager tried the idea of the web prototype (ADR 0002) and prefers running events from Discord with slash commands. The guild already lives in Discord, so a separate site is one more place to check.

## Decision

Proposed: Discord slash commands become the main interface for creating events and signing up.

* Managers run `/event create` (title, type, start time, capacity) and `/event cancel`.
* Everyone can use `/event list`, `/signup`, `/withdraw` and `/roster`.
* Each event is posted in the channel with the start time in every reader's time zone (Discord timestamps), counts per role, and Tank, Healer, DPS and Withdraw buttons. The post updates on every change.
* The event and sign-up rules from the web prototype move to a Python module with the same behaviour and tests.
* The web prototype stays in the repository, parked. If accepted, this ADR supersedes ADR 0002.

## Consequences

### Positive

* Members sign up where they already talk, with no new link or login.
* Discord identifies who signed up, so no login system is needed.

### Negative

* We depend on Discord's API and its limits on command options and message formatting.
* Typing a start time is clumsier than a date picker.

## Considered Alternatives

* Keep the web page as the main interface and only post links in Discord: more to build, and the manager prefers commands.
* Both a full web page and commands: two interfaces to keep in step for about 5 users.

## More Information

Open questions in the plan: button vs command sign up, manager role, time zone, character names, reminders.
