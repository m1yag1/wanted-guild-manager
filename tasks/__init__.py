"""Project tasks, run with invoke: `uv run inv --list`."""

from invoke.collection import Collection

from tasks import github

ns = Collection(github)
