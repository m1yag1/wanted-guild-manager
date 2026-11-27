"""Project tasks, run with invoke: `uv run inv --list`."""

from invoke.collection import Collection

from tasks import deploy, discord, droplet, github, observe

ns = Collection(github, droplet, deploy, discord)
ns.add_task(observe.logs_task)
ns.add_task(observe.status_task)
