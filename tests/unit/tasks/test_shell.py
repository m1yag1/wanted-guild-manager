import pytest
from invoke.context import Context

from tasks.shell import CommandError, Shell
from tests.fixtures.commands import MakeFakeCommand


def test_returns_captured_output(fake_command: MakeFakeCommand) -> None:
    tool = fake_command("tool", [("hello", {"stdout": "hi\n"})])

    assert Shell(Context()).run([str(tool.path), "hello"]) == "hi\n"


def test_passes_extra_environment(fake_command: MakeFakeCommand) -> None:
    tool = fake_command("tool", env_keys=("WGM_TEST",))

    Shell(Context(), env={"WGM_TEST": "yes"}).run([str(tool.path)])

    assert tool.calls()[0]["env"] == {"WGM_TEST": "yes"}


def test_uncaptured_runs_return_nothing(fake_command: MakeFakeCommand) -> None:
    tool = fake_command("tool", [("", {"stdout": "shown\n"})])

    assert Shell(Context()).run([str(tool.path)], capture=False) == ""


def test_failures_raise_with_stderr(fake_command: MakeFakeCommand) -> None:
    tool = fake_command("tool", [("", {"code": 3, "stderr": "boom"})])

    with pytest.raises(CommandError, match="exited with 3: boom") as raised:
        Shell(Context()).run([str(tool.path)])

    assert raised.value.returncode == 3


def test_failures_without_stderr(fake_command: MakeFakeCommand) -> None:
    tool = fake_command("tool", [("", {"code": 1})])

    with pytest.raises(CommandError) as raised:
        Shell(Context()).run([str(tool.path)], capture=False)

    assert raised.value.stderr == ""


def test_sends_stdin(fake_command: MakeFakeCommand) -> None:
    tool = fake_command("tool")

    Shell(Context()).run([str(tool.path), "--input", "-"], stdin='{"a": 1}')

    assert tool.calls()[0]["stdin"] == '{"a": 1}'
