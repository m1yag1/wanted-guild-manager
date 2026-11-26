"""Fake command line tools that record their calls and return canned output."""

import json
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

SCRIPT = """#!{python}
import json, os, pathlib, sys
rules = json.loads({rules!r})
args = sys.argv[1:]
call = {{
    "args": args,
    "env": {{k: os.environ.get(k) for k in {env_keys!r}}},
    "stdin": sys.stdin.read() if "--input" in args else None,
}}
with open({log!r}, "a") as log:
    log.write(json.dumps(call) + "\\n")
joined = " ".join(args)
reply = next((r for needle, r in rules if needle in joined), {{}})
for path in reply.get("files", []):
    pathlib.Path(path).write_text("")
sys.stdout.write(reply.get("stdout", ""))
sys.stderr.write(reply.get("stderr", ""))
sys.exit(reply.get("code", 0))
"""

Rule = tuple[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class FakeCommand:
    """A fake executable on disk and the calls made to it."""

    path: Path
    log: Path

    def calls(self) -> list[dict[str, Any]]:
        """Every call so far, as `{"args": [...], "env": {...}, "stdin": ...}`."""
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def args(self) -> list[list[str]]:
        """Just the arguments of every call."""
        return [call["args"] for call in self.calls()]


MakeFakeCommand = Callable[..., FakeCommand]


@pytest.fixture
def fake_command(tmp_path: Path) -> MakeFakeCommand:
    """Build a fake executable.

    `rules` is a list of `(needle, reply)`: the first rule whose needle appears in
    the joined arguments decides the reply, which may set "stdout", "stderr",
    "code" (exit status) and "files" (paths to create).
    """

    def make(
        name: str, rules: list[Rule] | None = None, env_keys: tuple[str, ...] = ()
    ) -> FakeCommand:
        path = tmp_path / "bin" / name
        path.parent.mkdir(exist_ok=True)
        log = tmp_path / f"{name}-calls.jsonl"
        path.write_text(
            SCRIPT.format(
                python=sys.executable,
                rules=json.dumps(rules or []),
                env_keys=list(env_keys),
                log=str(log),
            )
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return FakeCommand(path=path, log=log)

    return make
