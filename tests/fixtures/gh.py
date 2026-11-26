"""A fake `gh` executable that records calls and returns canned responses."""

import json
import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

SCRIPT = """#!{python}
import json, sys
responses = json.loads({responses!r})
args = sys.argv[1:]
call = {{"args": args, "stdin": sys.stdin.read() if "--input" in args else None}}
with open({log!r}, "a") as log:
    log.write(json.dumps(call) + "\\n")
reply = responses.get(args[2] + " " + args[3], {{}})
sys.stdout.write(reply.get("stdout", ""))
sys.stderr.write(reply.get("stderr", ""))
sys.exit(reply.get("code", 0))
"""


@dataclass(frozen=True, slots=True)
class FakeGh:
    """A fake gh on disk and the calls made to it."""

    path: Path
    log: Path

    def calls(self) -> list[dict[str, Any]]:
        """Every call so far, as `{"args": [...], "stdin": str | None}`."""
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


MakeFakeGh = Callable[[dict[str, dict[str, Any]]], FakeGh]


@pytest.fixture
def fake_gh(tmp_path: Path) -> MakeFakeGh:
    """Build a fake gh. Responses are keyed by "METHOD path".

    Each response may set "stdout", "stderr" and "code" (exit status).
    """

    def make(responses: dict[str, dict[str, Any]]) -> FakeGh:
        path = tmp_path / "gh"
        log = tmp_path / "gh-calls.jsonl"
        path.write_text(
            SCRIPT.format(
                python=sys.executable,
                responses=json.dumps(responses),
                log=str(log),
            )
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return FakeGh(path=path, log=log)

    return make
