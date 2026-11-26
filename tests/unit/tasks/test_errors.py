import pytest
from invoke.exceptions import Exit

from tasks.errors import friendly_errors
from tasks.shell import CommandError


def _raise(error: Exception) -> None:
    raise error


def test_passes_results_through() -> None:
    assert friendly_errors(lambda: 42)() == 42


def test_failed_commands_show_their_error() -> None:
    task = friendly_errors(_raise)

    with pytest.raises(Exit) as raised:
        task(CommandError(["/usr/bin/doctl", "x"], 3, "not authorized\n"))

    assert raised.value.message == "Error: doctl failed (not authorized)."
    assert raised.value.code == 3


def test_failed_commands_without_stderr_point_at_their_output() -> None:
    with pytest.raises(Exit) as raised:
        friendly_errors(_raise)(CommandError(["ansible-playbook"], 2, ""))

    assert raised.value.message == (
        "Error: ansible-playbook failed (see the output above)."
    )


@pytest.mark.parametrize(
    "error", [ValueError("bad env"), FileNotFoundError("no inventory")]
)
def test_expected_errors_become_one_line(error: Exception) -> None:
    with pytest.raises(Exit) as raised:
        friendly_errors(_raise)(error)

    assert raised.value.message == f"Error: {error}"
    assert raised.value.code == 1


def test_unexpected_errors_keep_their_traceback() -> None:
    with pytest.raises(KeyError):
        friendly_errors(_raise)(KeyError("bug"))
