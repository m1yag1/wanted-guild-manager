# Use Discord slash commands as the main interface

* Status: proposed
* Date: 2026-11-25

## Context and Problem Statement

The guild manager tried the idea of the web prototype (ADR 0002) and prefers running events from Discord with slash commands. The guild already lives in Discord, so a separate site is one more place to check.

## Decision

Proposed: Discord slash commands become the main interface for creating events and signing up.

* Every command sits under one top-level `/wgm` command: `/wgm help`, `/wgm event list|create|edit|cancel`, `/wgm signup`, `/wgm withdraw` and `/wgm roster`.
* Everyone can list events, sign up, withdraw, see rosters and get help. Creating, editing and cancelling events need a manager role.
* Discord's command permissions only apply to the whole `/wgm` command, so the bot checks the member's roles for each subcommand. Role names come from config, and `/wgm help` shows only the commands the member can use.
* The bot creates the roles it needs (to start, `WGM Manager`) with one idempotent setup step: automatically when Discord reports the app was added to a server (the invite asks for Manage Roles), again with `/wgm setup` (Manage Server only), or from the command line with `inv discord.setup-roles --guild <id>`. It never deletes or renames roles and never assigns them to members.
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
