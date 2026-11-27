# Group commands into plugins turned on by settings

* Status: proposed
* Date: 2026-11-27

## Context and Problem Statement

`/wgm` keeps growing: events now, then reminders and attendance. Each area also needs a way to try it by hand on staging, such as posting test events. All of it lives in one command module, so every environment gets every command. Test tools must never reach production, and new areas should be addable without editing the core.

## Decision

Each area of the app is a plugin. `WGM_PLUGINS` lists the plugins an environment turns on (default `event`).

* Plugins are found by name through the `wgm.plugins` entry point group in `pyproject.toml`, so another package could add one later.
* A plugin is any object with the shape of `WgmPlugin`: a name, the settings it reads, its `/wgm <name> ...` subcommands, its dev subcommands, the button prefixes it answers, its background jobs and a step for `/wgm setup`.
* Each plugin owns its own testing tools. Its dev subcommands, such as `/wgm event seed` for test events, live in the same group as its other commands. They exist only when the core setting `WGM_DEV_MODE=true` is on, which staging sets and production never does. Without it they're neither registered with Discord nor answered. No plugin reaches into another plugin's data to make test data.
* A plugin declares its settings as `SettingSpec`s, read from `WGM_<PLUGIN>_<KEY>`. Turning a plugin on adds its settings to the app's configuration.
* `create_app()` loads the plugins once and keeps them in app state. `inv discord.register-commands` loads them from the same settings file, so Discord shows exactly the commands the server answers.
* Problems stop the server at startup with a clear message: an unknown plugin, a plugin using a core command name, or a missing or invalid setting. Skipping a plugin quietly would leave commands missing in Discord with no explanation.
* Background jobs belong to plugins, as described below.
* `help`, `setup` and `config` stay in the core. Discord allows only `/wgm <group> <subcommand>`, so each plugin is one group.
* All tables stay in one migration history. Turning a plugin off hides its commands but never removes its data.

### Background jobs

Some plugins need work done on a timer, not in answer to a command. Examples are locking event posts when sign-ups close, sending reminders, and refreshing a cache.

* **Declaring a job:** a plugin returns its jobs from `jobs(config)`. Each `Job` has a name, an interval in seconds, and an async `run(context)`. The interval usually comes from one of the plugin's settings, such as `WGM_EVENT_CLOSE_CHECK_SECONDS`. A job that must happen at a set time, such as a reminder an hour before an event, still runs on an interval. Each run asks the database what is due as of now, so a restart or a late run catches up instead of missing work.
* **What a job gets:** each run receives a `JobContext` with the database config, the Discord client and the plugin's parsed settings. It opens its own database session per run.
* **Starting and stopping:** `create_app()` adds one lifespan step that starts a task for each job of each plugin that is on. On shutdown it cancels them and waits for them to finish. Plugins that are off have no jobs running.
* **Errors:** each run is wrapped, so an exception is logged with the job's name and the job runs again at its next interval. Each job has its own task, so one failing job never stops another.
* **Idempotent runs:** a run must be safe to repeat. For example, the close-lock job marks each post it locks. Granian runs one worker, so each job runs once per interval. If that changes, jobs will need a lock, or only one worker should run them.
* **Testing without sleeping:** `run` is a plain async function that takes the current time from its context or arguments, so tests call it directly with a fixed time. The loop that repeats jobs takes its sleep function as an argument, so its tests pass one that returns at once.

## Consequences

### Positive

* Staging can run each plugin's test tools, which production never registers or answers.
* New areas plug in without changing the core command code.

### Negative

* Adding or renaming a plugin needs the package reinstalled, since entry points are read from the installed package.
* Plugins share one database schema, so a plugin's tables exist even where it is off.

## Considered Alternatives

* Keep one command list with an `if staging` check: simple, but the check spreads to every command and handler.
* A separate `dev` plugin for all test tools: it would have to reach into every other plugin's data, so it would break whenever they change.
* Litestar's own plugin protocol: built for adding routes and app config, while these plugins add Discord commands and jobs.
* Installing plugins at runtime per server: more than the guild needs now, and per-server settings already live in the database.
